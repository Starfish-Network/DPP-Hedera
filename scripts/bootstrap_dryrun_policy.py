#!/usr/bin/env python3
"""
Bootstrap a dry-run Guardian policy for the demo sandbox.

Mirrors the production v9/v4 topology (requestVcDocumentBlock →
sendToGuardianBlock) with a permissive single-field schema, so any payload
shape posted to `/guardian/dryrun/submit/{slug}` validates and produces a
real signed VC inside the sandbox.

Idempotent on policyTag: if a draft/dry-run policy with that tag already
exists, prints its id and exits.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.service.guardian_client import GuardianClient  # noqa: E402

POLICY_NAME = "DPP Dry-Run Demo"
POLICY_DESCRIPTION = (
    "Dry-run sandbox for the DPP-Hedera demo. Mirrors the GDST/FSMA v8 "
    "topology (requestVcDocumentBlock → sendToGuardianBlock) so we can "
    "issue real signed VCs while published-policy workers are wedged."
)
POLICY_TAG = "DPP-DRYRUN-demo-v1"
POLICY_VERSION = "1.0.0"
ROOT_BLOCK_TAG = "dryrun_root"
INTAKE_BLOCK_TAG = "dryrun_intake"
ISSUE_BLOCK_TAG = "dryrun_issue"
SCHEMA_NAME = "DryRunPayload"

PUBLISH_TIMEOUT_S = 600.0


def _new_id() -> str:
    return str(uuid.uuid4())


def _draft_policy() -> dict:
    return {
        "name": POLICY_NAME,
        "description": POLICY_DESCRIPTION,
        "topicDescription": POLICY_TAG,
        "policyTag": POLICY_TAG,
        "policyRoles": [],
        "policyGroups": [],
        "policyTopics": [],
        "policyTokens": [],
        "categoriesExport": [],
        "categories": [],
        "config": {
            "id": _new_id(),
            "blockType": "interfaceContainerBlock",
            "tag": ROOT_BLOCK_TAG,
            "permissions": ["NO_ROLE"],
            "defaultActive": True,
            "onErrorAction": "no-action",
            "uiMetaData": {},
            "options": [],
            "events": [],
            "artifacts": [],
            "children": [],
        },
    }


def _full_config(intake_schema_iri: str) -> dict:
    return {
        "id": _new_id(),
        "blockType": "interfaceContainerBlock",
        "tag": ROOT_BLOCK_TAG,
        "permissions": ["NO_ROLE"],
        "defaultActive": True,
        "onErrorAction": "no-action",
        "uiMetaData": {},
        "options": [],
        "events": [],
        "artifacts": [],
        "children": [
            {
                "id": _new_id(),
                "blockType": "requestVcDocumentBlock",
                "tag": INTAKE_BLOCK_TAG,
                "permissions": ["NO_ROLE"],
                "defaultActive": True,
                "onErrorAction": "no-action",
                "uiMetaData": {},
                "schema": intake_schema_iri,
                "idType": "OWNER",
                "events": [
                    {
                        "source": INTAKE_BLOCK_TAG,
                        "target": ISSUE_BLOCK_TAG,
                        "input": "RunEvent",
                        "output": "RunEvent",
                        "actor": "",
                        "disabled": False,
                    }
                ],
                "artifacts": [],
                "children": [],
            },
            {
                "id": _new_id(),
                "blockType": "sendToGuardianBlock",
                "tag": ISSUE_BLOCK_TAG,
                "permissions": ["NO_ROLE"],
                "defaultActive": True,
                "onErrorAction": "no-action",
                "uiMetaData": {},
                "options": [],
                "dataSource": "database",
                "documentType": "vc",
                "stopPropagation": False,
                "events": [],
                "artifacts": [],
                "children": [],
            },
        ],
    }


def _schema_dto() -> tuple[dict, str]:
    schema_uuid = _new_id()
    iri = f"#{schema_uuid}"
    properties = {
        "marker": {
            "$comment": '{ "term": "marker", "@id": "https://schema.org/text" }',
            "title": "marker",
            "type": "string",
            "readOnly": False,
        },
    }
    # Guardian decorates the credentialSubject with these at runtime; declared
    # so MGS's auto-injected `additionalProperties: false` doesn't 422.
    for f in ("policyId", "guardianVersion", "ref"):
        properties[f] = {
            "$comment": f'{{ "term": "{f}", "@id": "https://schema.org/text" }}',
            "title": f,
            "type": "string",
            "readOnly": True,
        }
    return (
        {
            "name": SCHEMA_NAME,
            "description": "Permissive payload schema for the dry-run demo policy.",
            "entity": "VC",
            "category": "POLICY",
            "uuid": schema_uuid,
            "iri": iri,
            "status": "DRAFT",
            "version": POLICY_VERSION,
            "document": {
                "$id": iri,
                "title": SCHEMA_NAME,
                "type": "object",
                "properties": properties,
                "required": ["marker"],
            },
            "context": {"@context": {"@version": 1.1}},
        },
        iri,
    )


async def main() -> None:
    base_url = os.environ["GUARDIAN_API_URL"]
    sr_user = os.environ["GUARDIAN_SR_USERNAME"]
    sr_pass = os.environ["GUARDIAN_SR_PASSWORD"]
    c = GuardianClient(base_url=base_url, sr_username=sr_user, sr_password=sr_pass)
    await c.login()

    # Idempotency: check if the policy already exists.
    pols = await c.list_policies()
    existing = [p for p in pols if p.get("policyTag") == POLICY_TAG]
    if existing:
        p = existing[-1]
        pid = p["id"]
        status = p.get("status")
        print(f"Policy already exists: id={pid} status={status}")
        if status == "DRY-RUN":
            print("\nReady. Paste into api/.env.dev:")
            print(f"    GUARDIAN_DRYRUN_POLICY_ID={pid}")
            print(f"    GUARDIAN_DRYRUN_INTAKE_BLOCK_TAG={INTAKE_BLOCK_TAG}")
            return
        print(f"  status={status!r} — manual cleanup required (discontinue + retry)")
        return

    print("1. Create draft policy...")
    pols = await c.create_policy(_draft_policy())
    policy = next(p for p in pols if p.get("policyTag") == POLICY_TAG)
    pid = policy["id"]
    topic_id = policy.get("topicId") or policy.get("instanceTopicId")
    print(f"   policyId={pid} topicId={topic_id}")

    print("2. Create + publish schema...")
    dto, _ = _schema_dto()
    await c.create_schema(topic_id, dto)
    in_topic = await c.list_schemas(topic_id)
    drafts = [s for s in in_topic if s.get("name") == SCHEMA_NAME and s.get("status") == "DRAFT"]
    if not drafts:
        seen = [(s.get("name"), s.get("status")) for s in in_topic]
        raise SystemExit(f"no DRAFT {SCHEMA_NAME} in topic {topic_id}; seen={seen}")
    sid = drafts[-1]["id"]
    base_version = (drafts[-1].get("iri", "").rsplit("&", 1)[-1]
                    if "&" in drafts[-1].get("iri", "") else POLICY_VERSION)
    await c.publish_schema_with_bump(sid, base_version=base_version, timeout_s=PUBLISH_TIMEOUT_S)
    in_topic = await c.list_schemas(topic_id)
    pub = [s for s in in_topic if s.get("name") == SCHEMA_NAME and s.get("status") == "PUBLISHED"]
    if not pub:
        raise SystemExit("schema publish reported COMPLETED but no PUBLISHED schema in topic")
    intake_iri = pub[-1]["iri"]
    print(f"   schema iri: {intake_iri}")

    print("3. PUT full config...")
    current = await c.get_policy(pid)
    current["config"] = _full_config(intake_iri)
    await c.update_policy(pid, current)

    print("4. Flip to DRY-RUN...")
    r = await c._call_with_refresh("PUT", f"/policies/{pid}/dry-run")
    if r.status_code >= 300:
        raise SystemExit(f"dry-run flip failed ({r.status_code}): {r.text[:400]}")
    body = r.json()
    if not body.get("isValid", True):
        print(f"   warning: validation reports isValid=false: {body}")

    print("\nDone. Paste into api/.env.dev:")
    print(f"    GUARDIAN_DRYRUN_POLICY_ID={pid}")
    print(f"    GUARDIAN_DRYRUN_INTAKE_BLOCK_TAG={INTAKE_BLOCK_TAG}")


if __name__ == "__main__":
    asyncio.run(main())
