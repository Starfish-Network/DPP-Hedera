#!/usr/bin/env python3
"""
Bootstrap the GDST Guardian policy on the configured MGS tenant.

Flow (per research.md §3, quickstart.md §3-4):

    1. login() as Standard Registry
    2. POST /policies with a minimal draft -> get {policyId, topicId}
    3. POST /schemas/{topicId} with schemas/gdst/compliance-intake.json
    4. PUT /schemas/push/{schemaId}/publish -> wait_for_task
    5. PUT /policies/{policyId} with the full block tree (root ->
       externalDataBlock -> sendToGuardianBlock), schema refs resolved to
       MGS-assigned UUIDs
    6. PUT /policies/push/{policyId}/publish -> wait_for_task (120 s)
    7. GET /policies/{policyId}/export/file ->
       schemas/policies/gdst-seafood-traceability.policy
    8. Print policyId + intake block tag for .env.dev

Runs against live MGS. Requires GUARDIAN_API_URL / GUARDIAN_SR_USERNAME /
GUARDIAN_SR_PASSWORD in the environment (load .env.dev before running).

Intentionally NOT idempotent on a per-tenant basis: if a policy with the
same `policyTag` already exists the script aborts and asks the operator to
delete it first from the MGS portal. Re-provisioning a published policy is
out of scope for v1 — schema IRIs are bumped instead (research.md §3).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

# Make `app...` imports work when the script runs from the repo root.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.service.guardian_client import (  # noqa: E402
    GuardianClient,
    GuardianClientError,
    GuardianError,
)

INTAKE_SCHEMA_PATH = REPO_ROOT / "schemas" / "gdst" / "compliance-intake.json"
EXPORT_PATH = REPO_ROOT / "schemas" / "policies" / "gdst-seafood-traceability.policy"

POLICY_NAME = "GDST Seafood Traceability"
POLICY_DESCRIPTION = (
    "Cross-party ruleset compliance for GDST 1.2 critical tracking events. "
    "Issues GDSTComplianceCredential VCs for events submitted via FastAPI."
)
POLICY_TAG = "GDST-1-2-seafood"
POLICY_VERSION = "1.0.0"
INTAKE_BLOCK_TAG = "gdst_intake"
ISSUE_BLOCK_TAG = "gdst_issue_vc"
ROOT_BLOCK_TAG = "gdst_root"


def _new_id() -> str:
    return str(uuid.uuid4())


def _wrap_schema_dto(schema_base: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """
    Transform the human-authored compliance-intake.json into a fully-formed
    MGS SchemaDTO. Returns (dto, iri) so the caller can reuse the iri when
    wiring it into a policy block's `schema:` reference.

    MGS rejects the simplified Guardian DSL (`{name, fields[]}`) with a 500
    ("Cannot read properties of undefined (reading '$id')"). It wants a
    `document` holding the JSON Schema with a `$id` that matches the DTO's
    top-level `iri`.
    """
    schema_uuid = _new_id()
    iri = f"#{schema_uuid}"
    doc = dict(schema_base["document"])
    doc["$id"] = iri
    return (
        {
            "name": schema_base["name"],
            "description": schema_base.get("description", ""),
            "entity": schema_base.get("entity", "VC"),
            "category": "POLICY",
            "uuid": schema_uuid,
            "iri": iri,
            "status": "DRAFT",
            "version": POLICY_VERSION,
            "document": doc,
            "context": schema_base.get("context", {"@context": {"@version": 1.1}}),
        },
        iri,
    )


def _draft_policy() -> dict[str, Any]:
    """
    Minimal policy the MGS can accept before schemas exist. We only need the
    topicId back; the real config tree is PUT in step 5.
    """
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
            "permissions": ["ANY_ROLE"],
            "defaultActive": True,
            "onErrorAction": "no-action",
            "uiMetaData": {},
            "options": [],
            "events": [],
            "artifacts": [],
            "children": [],
        },
    }


def _full_config(intake_schema_ref: str) -> dict[str, Any]:
    """
    Root container -> externalDataBlock -> sendToGuardianBlock.

    Event wiring: externalDataBlock fires RunEvent on receipt, which the
    sendToGuardianBlock consumes to create + sign + persist the VC.
    """
    return {
        "id": _new_id(),
        "blockType": "interfaceContainerBlock",
        "tag": ROOT_BLOCK_TAG,
        "permissions": ["ANY_ROLE"],
        "defaultActive": True,
        "onErrorAction": "no-action",
        "uiMetaData": {},
        "options": [],
        "events": [],
        "artifacts": [],
        "children": [
            {
                "id": _new_id(),
                "blockType": "externalDataBlock",
                "tag": INTAKE_BLOCK_TAG,
                "permissions": ["ANY_ROLE"],
                "defaultActive": True,
                "onErrorAction": "no-action",
                "uiMetaData": {},
                "schema": intake_schema_ref,
                "entityType": "GDSTComplianceIntake",
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
                "permissions": ["ANY_ROLE"],
                "defaultActive": False,
                "onErrorAction": "no-action",
                "uiMetaData": {},
                "options": [],
                "dataSource": "database",
                "documentType": "vc",
                "entityType": "GDSTComplianceIntake",
                "stopPropagation": False,
                "events": [],
                "artifacts": [],
                "children": [],
            },
        ],
    }


def _pick_created(records: list[dict[str, Any]], *, by: str, value: str) -> dict[str, Any]:
    for rec in records:
        if rec.get(by) == value:
            return rec
    raise RuntimeError(
        f"MGS response did not include a record with {by}={value!r}. "
        f"Response: {json.dumps(records)[:400]}"
    )


async def bootstrap(client: GuardianClient, *, dry_run: bool = False) -> dict[str, str]:
    intake_base = json.loads(INTAKE_SCHEMA_PATH.read_text())

    if dry_run:
        dto, iri = _wrap_schema_dto(intake_base)
        cfg = _full_config(iri)
        print(json.dumps({
            "policy": _draft_policy(),
            "schemaDTO": dto,
            "fullConfig": cfg,
        }, indent=2))
        return {}

    print("1. Login...")
    await client.login()

    print("2. Create policy draft...")
    draft = _draft_policy()
    policies = await client.create_policy(draft)
    policy = _pick_created(policies, by="policyTag", value=POLICY_TAG)
    policy_id = policy["id"]
    topic_id = policy.get("topicId") or policy.get("instanceTopicId")
    if not topic_id:
        raise RuntimeError(
            f"Draft policy {policy_id} has no topicId — cannot attach schemas. "
            f"Record: {json.dumps(policy)[:400]}"
        )
    print(f"   policyId={policy_id}, topicId={topic_id}")

    print("3. Create intake schema under policy topic...")
    schema_dto, intake_iri = _wrap_schema_dto(intake_base)
    schemas = await client.create_schema(topic_id, schema_dto)
    created_schema = _pick_created(schemas, by="name", value="GDSTComplianceIntake")
    schema_id = created_schema["id"]
    # MGS may rewrite the IRI (e.g., adding a version suffix); prefer its
    # response over the one we generated.
    schema_uuid = created_schema.get("iri") or intake_iri
    print(f"   schemaId={schema_id}, iri={schema_uuid}")

    print("4. Publish schema (async)...")
    task = await client.publish_schema(schema_id, version=POLICY_VERSION)
    result = await client.wait_for_task(task.taskId, timeout=120.0)
    if result.status != "COMPLETED":
        raise RuntimeError(f"Schema publish failed: {result.error}")
    # Re-fetch to get the final IRI (MGS rewrites it on publish).
    published_policy = await client.get_policy(policy_id)
    # Some MGS versions embed the schema IRI on the schema record; fall back
    # to the one we stored pre-publish.
    intake_iri = schema_uuid

    print("5. Update policy with full config tree...")
    full = dict(published_policy)
    full["config"] = _full_config(intake_iri)
    await client.update_policy(policy_id, full)

    print("6. Publish policy (async, up to 2 min)...")
    task = await client.publish_policy(policy_id, policy_version=POLICY_VERSION)
    result = await client.wait_for_task(task.taskId, timeout=300.0)
    if result.status != "COMPLETED":
        raise RuntimeError(f"Policy publish failed: {result.error}")

    print(f"7. Export policy to {EXPORT_PATH.relative_to(REPO_ROOT)}...")
    await client.export_policy(policy_id, EXPORT_PATH)

    return {
        "policyId": policy_id,
        "intakeBlockTag": INTAKE_BLOCK_TAG,
        "exportPath": str(EXPORT_PATH),
    }


def _load_client_from_env() -> GuardianClient:
    base_url = os.environ.get("GUARDIAN_API_URL")
    sr_user = os.environ.get("GUARDIAN_SR_USERNAME")
    sr_pass = os.environ.get("GUARDIAN_SR_PASSWORD")
    if not (base_url and sr_user and sr_pass):
        raise SystemExit(
            "Set GUARDIAN_API_URL, GUARDIAN_SR_USERNAME, GUARDIAN_SR_PASSWORD "
            "(source api/.env.dev) before running this script."
        )
    return GuardianClient(
        base_url=base_url, sr_username=sr_user, sr_password=sr_pass
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the draft policy + full config JSON without calling MGS.",
    )
    args = parser.parse_args()

    client = _load_client_from_env()
    try:
        result = asyncio.run(bootstrap(client, dry_run=args.dry_run))
    except GuardianClientError as e:
        raise SystemExit(f"MGS rejected a request: {e}")
    except GuardianError as e:
        raise SystemExit(f"Guardian client error: {e}")

    if args.dry_run:
        return

    print("\nDone. Paste into api/.env.dev:")
    print(f"    GUARDIAN_GDST_POLICY_ID={result['policyId']}")
    print(f"    GUARDIAN_GDST_INTAKE_BLOCK_TAG={result['intakeBlockTag']}")


if __name__ == "__main__":
    main()
