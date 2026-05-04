#!/usr/bin/env python3
"""
Bootstrap the GDST Guardian policy on the configured MGS tenant.

Flow (per research.md §3, quickstart.md §3-4):

    1. login() as Standard Registry
    2. POST /policies with a minimal draft -> get {policyId, topicId}
    3. POST /schemas/{topicId} with schemas/gdst/compliance-intake.json
    4. PUT /schemas/push/{schemaId}/publish -> wait_for_task (up to 10 min)
    5. PUT /policies/{policyId} with the full block tree (root ->
       externalDataBlock -> createVcDocumentBlock -> sendToGuardianBlock),
       schema refs resolved to MGS-assigned UUIDs. The middle block wraps
       the credentialSubject in a signed VC envelope; without it the chain
       drops every submission silently.
    6. PUT /policies/push/{policyId}/publish -> wait_for_task (up to 10 min)
    7. GET /policies/{policyId}/export/file ->
       schemas/policies/gdst-seafood-traceability.policy
    8. Print policyId + intake block tag for .env.dev

Runs against live MGS. Requires GUARDIAN_API_URL / GUARDIAN_SR_USERNAME /
GUARDIAN_SR_PASSWORD in the environment (load .env.dev before running).

--resume: if a prior run died between steps 4 and 5 (e.g., wait_for_task
expired while the schema publish was still in flight), re-run with --resume
to skip 1-4 and pick up at step 5 against the existing DRAFT policy.

Intentionally NOT idempotent on a per-tenant basis: if a non-DRAFT policy
with the same policyTag already exists the script aborts and asks the
operator to discontinue it from the MGS portal first (published policies
are on-chain and immutable).
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
POLICY_TAG = "GDST-1-2-seafood-v6"
POLICY_VERSION = "1.0.0"
INTAKE_BLOCK_TAG = "gdst_intake"
CREATE_VC_BLOCK_TAG = "gdst_create_vc"
ISSUE_BLOCK_TAG = "gdst_issue_vc"
ROOT_BLOCK_TAG = "gdst_root"

# Hedera testnet schema/policy publish can take 3-8 minutes when the mirror
# node is lagging. A 120s cap (our client default) routinely expires while
# the async task is still healthy server-side, leaving the tenant in a half-
# bootstrapped state (see scripts/build_gdst_policy.py --resume).
PUBLISH_TIMEOUT_S = 600.0


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
    """Root → externalDataBlock → customLogicBlock → sendToGuardianBlock.

    customLogicBlock sits between the intake and the persist step because MGS
    has no `createVcDocumentBlock` (verified via /policies/blocks/about — its
    57-block taxonomy includes only `requestVcDocumentBlock` for UI input and
    `uploadVcDocumentBlock` for pre-formed VCs). With the default `unsigned:
    false`, customLogicBlock wraps the script's return value in a signed W3C
    VC envelope using the SR DID. The script is a passthrough — Guardian
    handles the @context/type/proof.

    `outputSchema` is REQUIRED when unsigned=false. Guardian's createDocument
    path calls `PolicyUtils.loadSchemaByID(ref, ref.options.outputSchema)` and
    then accesses `outputSchema.iri` + `SchemaHelper.getContext(outputSchema)`;
    if the option is missing the worker thread silently dies and no VC is ever
    produced (see GDST v3/v4 post-mortems). Pointing it at the same intake
    schema makes the issued VC reuse the GDSTComplianceIntake type.

    The script must unwrap to the credentialSubject. customLogicBlock receives
    `documents` as an array of IPolicyDocument wrappers (`{document, owner,
    schema, accounts, signature, ...}`); returning the wrapper makes the
    downstream `verifySubject` fail because its createDocument path spreads
    the wrapper into vcSubject and the schema's required fields end up nested
    one level too deep (see GDST v5 post-mortem). Returning
    `documents[0].document.credentialSubject[0]` hands createDocument exactly
    the GDSTComplianceIntake fields it expects.
    """
    unwrap_script = (
        "function processDocuments(documents) {\n"
        "    const cs = documents[0].document.credentialSubject;\n"
        "    return Array.isArray(cs) ? cs[0] : cs;\n"
        "}\n"
        "done(processDocuments(documents));\n"
    )
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
                        "target": CREATE_VC_BLOCK_TAG,
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
                "blockType": "customLogicBlock",
                "tag": CREATE_VC_BLOCK_TAG,
                "permissions": ["ANY_ROLE"],
                "defaultActive": True,
                "onErrorAction": "no-action",
                "uiMetaData": {},
                "expression": unwrap_script,
                "selectedScriptLanguage": "JAVASCRIPT",
                "unsigned": False,  # signs the output as a VC with the SR DID
                "passOriginal": False,
                "outputSchema": intake_schema_ref,
                "events": [
                    {
                        "source": CREATE_VC_BLOCK_TAG,
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
                "defaultActive": True,
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


async def _finalize(
    client: GuardianClient, policy_id: str, intake_iri: str
) -> dict[str, str]:
    """Steps 5-7: PUT full config, publish policy, export .policy."""
    print("5. Update policy with full config tree...")
    current = await client.get_policy(policy_id)
    current["config"] = _full_config(intake_iri)
    await client.update_policy(policy_id, current)

    print(f"6. Publish policy (async, up to {int(PUBLISH_TIMEOUT_S / 60)} min)...")
    task = await client.publish_policy(policy_id, policy_version=POLICY_VERSION)
    result = await client.wait_for_task(task.taskId, timeout=PUBLISH_TIMEOUT_S)
    if result.status != "COMPLETED":
        raise RuntimeError(f"Policy publish failed: {result.error}")

    print(f"7. Export policy to {EXPORT_PATH.relative_to(REPO_ROOT)}...")
    await client.export_policy(policy_id, EXPORT_PATH)

    return {
        "policyId": policy_id,
        "intakeBlockTag": INTAKE_BLOCK_TAG,
        "exportPath": str(EXPORT_PATH),
    }


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
    schema_dto, _intake_iri = _wrap_schema_dto(intake_base)
    await client.create_schema(topic_id, schema_dto)
    # MGS's POST /schemas response sometimes lists SR-namespace schemas instead
    # of (or alongside) the just-created one — `_pick_created` would happily
    # match an old discontinued schema. Authoritative lookup: list this
    # specific topic's schemas and pick the DRAFT we just created.
    in_topic = await client.list_schemas(topic_id)
    drafts = [
        s for s in in_topic
        if s.get("name") == "GDSTComplianceIntake" and s.get("status") == "DRAFT"
    ]
    if not drafts:
        raise RuntimeError(
            f"No DRAFT GDSTComplianceIntake found in topic {topic_id} after "
            f"create_schema — saw {[(s.get('name'), s.get('status')) for s in in_topic]}"
        )
    created_schema = drafts[-1]
    schema_id = created_schema["id"]
    schema_uuid = created_schema["iri"]
    print(f"   schemaId={schema_id}, iri={schema_uuid}")

    # MGS auto-bumps the IRI version when an earlier GDSTComplianceIntake is
    # already on-chain in the SR namespace, but the bump only inspects the
    # tenant's topic — not the global SR namespace — so the iri may collide
    # with another tenant's `<name>@<version>`. publish_schema_with_bump walks
    # the patch number up until MGS accepts.
    base_version = schema_uuid.rsplit("&", 1)[-1] if "&" in schema_uuid else POLICY_VERSION
    print(f"4. Publish schema starting at version {base_version} (async, up to {int(PUBLISH_TIMEOUT_S / 60)} min)...")
    await client.publish_schema_with_bump(
        schema_id, base_version=base_version, timeout_s=PUBLISH_TIMEOUT_S,
    )
    in_topic = await client.list_schemas(topic_id)
    pub = [s for s in in_topic if s.get("name") == "GDSTComplianceIntake" and s.get("status") == "PUBLISHED"]
    final_iri = pub[-1]["iri"] if pub else schema_uuid
    print(f"   published as {final_iri}")

    return await _finalize(client, policy_id, final_iri)


async def resume(client: GuardianClient) -> dict[str, str]:
    """
    Recover from a partial bootstrap: skip steps 1-4, look up the existing
    DRAFT policy by tag and its already-published intake schema, then do
    steps 5-7.

    Use when a prior run died between steps 4 and 5 (e.g., wait_for_task
    expired during schema publish on slow testnet). Aborts clearly if the
    policy is already PUBLISHED — published policies are on-chain immutable,
    so recovery from that state requires discontinuing in the portal and
    re-running without --resume (bump POLICY_TAG if MGS rejects re-use).
    """
    print("1. Login...")
    await client.login()

    print(f"2. Look up policy by tag {POLICY_TAG!r}...")
    policies = await client.list_policies()
    matches = [p for p in policies if p.get("policyTag") == POLICY_TAG]
    if not matches:
        raise RuntimeError(
            f"no policy with policyTag={POLICY_TAG!r} found — run without --resume first"
        )
    # Last wins if MGS holds multiple drafts under the same tag (rare; the
    # unique index at mgs_policyTag_tenantId_u normally prevents it).
    policy = matches[-1]
    status = policy.get("status")
    if status != "DRAFT":
        raise RuntimeError(
            f"policy {policy['id']} has status={status!r}; --resume requires DRAFT. "
            "If the policy was accidentally published with a stub config, "
            "discontinue it in the MGS portal and re-run without --resume "
            "(bump POLICY_TAG if MGS rejects re-using the tag)."
        )
    policy_id = policy["id"]
    topic_id = policy.get("topicId") or policy.get("instanceTopicId")
    print(f"   policyId={policy_id}, topicId={topic_id}")

    print("3. Find intake schema under topic...")
    schemas = await client.list_schemas(topic_id)
    pub = [s for s in schemas if s.get("name") == "GDSTComplianceIntake" and s.get("status") == "PUBLISHED"]
    drafts = [s for s in schemas if s.get("name") == "GDSTComplianceIntake" and s.get("status") == "DRAFT"]
    if pub:
        intake_iri = pub[-1].get("iri")
        print(f"   already PUBLISHED: {intake_iri}")
    elif drafts:
        # The previous bootstrap died inside step 4 (publish). Pick up there.
        draft = drafts[-1]
        schema_id = draft["id"]
        base_version = (draft.get("iri", "").rsplit("&", 1)[-1] if "&" in draft.get("iri", "") else POLICY_VERSION)
        print(f"   publish DRAFT schema starting at version {base_version} (async)...")
        await client.publish_schema_with_bump(
            schema_id, base_version=base_version, timeout_s=PUBLISH_TIMEOUT_S,
        )
        in_topic = await client.list_schemas(topic_id)
        pub = [s for s in in_topic if s.get("name") == "GDSTComplianceIntake" and s.get("status") == "PUBLISHED"]
        if not pub:
            raise RuntimeError("publish reported COMPLETED but no PUBLISHED schema in topic")
        intake_iri = pub[-1]["iri"]
        print(f"   published as {intake_iri}")
    else:
        seen = [(s.get("name"), s.get("status")) for s in schemas]
        raise RuntimeError(f"no GDSTComplianceIntake in topic {topic_id}; seen={seen}.")

    return await _finalize(client, policy_id, intake_iri)


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
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Skip policy/schema creation; look up the existing DRAFT policy "
            "by tag and its already-published intake schema, then do steps "
            "5-7. Use after a mid-run failure left the policy in DRAFT."
        ),
    )
    args = parser.parse_args()

    if args.dry_run and args.resume:
        raise SystemExit("--dry-run and --resume are mutually exclusive")

    client = _load_client_from_env()
    try:
        if args.resume:
            result = asyncio.run(resume(client))
        else:
            result = asyncio.run(bootstrap(client, dry_run=args.dry_run))
    except GuardianClientError as e:
        raise SystemExit(f"MGS rejected a request: {e}")
    except GuardianError as e:
        raise SystemExit(f"Guardian client error: {e}")
    except RuntimeError as e:
        raise SystemExit(f"Bootstrap error: {e}")

    if args.dry_run:
        return

    print("\nDone. Paste into api/.env.dev:")
    print(f"    GUARDIAN_GDST_POLICY_ID={result['policyId']}")
    print(f"    GUARDIAN_GDST_INTAKE_BLOCK_TAG={result['intakeBlockTag']}")


if __name__ == "__main__":
    main()
