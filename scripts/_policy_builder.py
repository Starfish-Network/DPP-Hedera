"""Shared bootstrap logic for Guardian policy builders.

Both `build_gdst_policy.py` and `build_fsma_policy.py` declare a `PolicySpec`
and call `run(spec)`. The block topology, schema-creation flow, publish +
export steps, recovery semantics, and CLI plumbing all live here.

The topology was finalized after the v1-v7 post-mortem in
`docs/guardian-integration/debug/`. Three invariants matter:

1. permissions=["OWNER"]. The SR's policy role is OWNER; "NO_ROLE" makes
   the runtime report `Block Unavailable` to the SR submitter.
2. Intermediate `sendToGuardianBlock` with `dataSource="hedera"` writes
   the issued VC to a Hedera mirror topic. Without it nothing reaches
   the chain.
3. No explicit event wiring on children — the container auto-wires
   sibling RunEvents in declaration order.

MGS schema/policy publish on Hedera testnet can take 3-8 minutes when the
mirror node is lagging; the 600 s timeout is sized for that.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.service.guardian_client import (  # noqa: E402
    GuardianClient,
    GuardianClientError,
    GuardianError,
)

PUBLISH_TIMEOUT_S = 600.0
POLICY_VERSION = "1.0.0"


@dataclass(frozen=True)
class PolicySpec:
    slug: str
    name: str
    description: str
    policy_tag: str
    intake_schema_path: Path
    export_path: Path
    schema_name: str
    entity_type: str
    env_var_prefix: str

    @property
    def root_tag(self) -> str:
        return f"{self.slug}_root"

    @property
    def intake_tag(self) -> str:
        return f"{self.slug}_intake"

    @property
    def save_hedera_tag(self) -> str:
        return f"{self.slug}_save_hedera"

    @property
    def issue_tag(self) -> str:
        return f"{self.slug}_issue_vc"


def _new_id() -> str:
    return str(uuid.uuid4())


def _wrap_schema_dto(spec: PolicySpec, schema_base: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Build the SchemaDTO MGS expects: a `document` holding the JSON Schema
    with `$id` matching the DTO's top-level `iri`. MGS rejects the simplified
    Guardian DSL with a 500 ("Cannot read properties of undefined")."""
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


def _draft_policy(spec: PolicySpec) -> dict[str, Any]:
    """Minimal policy MGS accepts before schemas exist; we only need topicId
    back. Real config is PUT in step 5."""
    return {
        "name": spec.name,
        "description": spec.description,
        "topicDescription": spec.policy_tag,
        "policyTag": spec.policy_tag,
        "policyRoles": [],
        "policyGroups": [],
        "policyTopics": [],
        "policyTokens": [],
        "categoriesExport": [],
        "categories": [],
        "config": {
            "id": _new_id(),
            "blockType": "interfaceContainerBlock",
            "tag": spec.root_tag,
            "permissions": ["OWNER"],
            "defaultActive": True,
            "onErrorAction": "no-action",
            "uiMetaData": {},
            "options": [],
            "events": [],
            "artifacts": [],
            "children": [],
        },
    }


def _full_config(spec: PolicySpec, intake_schema_ref: str) -> dict[str, Any]:
    """Root → requestVcDocumentBlock → sendToGuardianBlock(hedera) → sendToGuardianBlock(database)."""
    return {
        "id": _new_id(),
        "blockType": "interfaceContainerBlock",
        "tag": spec.root_tag,
        "permissions": ["OWNER"],
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
                "tag": spec.intake_tag,
                "permissions": ["OWNER"],
                "defaultActive": True,
                "onErrorAction": "no-action",
                "uiMetaData": {},
                "schema": intake_schema_ref,
                "idType": "OWNER",
                "events": [],
                "artifacts": [],
                "children": [],
            },
            {
                "id": _new_id(),
                "blockType": "sendToGuardianBlock",
                "tag": spec.save_hedera_tag,
                "permissions": ["OWNER"],
                "defaultActive": True,
                "onErrorAction": "no-action",
                "uiMetaData": {},
                "options": [],
                "dataSource": "hedera",
                "topic": "root",
                "topicOwner": "owner",
                "events": [],
                "artifacts": [],
                "children": [],
            },
            {
                "id": _new_id(),
                "blockType": "sendToGuardianBlock",
                "tag": spec.issue_tag,
                "permissions": ["OWNER"],
                "defaultActive": True,
                "onErrorAction": "no-action",
                "uiMetaData": {},
                "options": [],
                "dataSource": "database",
                "documentType": "vc",
                "entityType": spec.entity_type,
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


def _topic_drafts(items: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [s for s in items if s.get("name") == name and s.get("status") == "DRAFT"]


def _topic_published(items: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [s for s in items if s.get("name") == name and s.get("status") == "PUBLISHED"]


async def _publish_schema(
    client: GuardianClient, spec: PolicySpec, topic_id: str, schema_id: str, base_version: str,
) -> str:
    print(f"4. Publish schema starting at version {base_version} (async, up to {int(PUBLISH_TIMEOUT_S / 60)} min)...")
    await client.publish_schema_with_bump(
        schema_id, base_version=base_version, timeout_s=PUBLISH_TIMEOUT_S,
    )
    in_topic = await client.list_schemas(topic_id)
    pub = _topic_published(in_topic, spec.schema_name)
    if not pub:
        raise RuntimeError("publish reported COMPLETED but no PUBLISHED schema in topic")
    final_iri = pub[-1]["iri"]
    print(f"   published as {final_iri}")
    return final_iri


async def _finalize(
    client: GuardianClient,
    spec: PolicySpec,
    policy_id: str,
    intake_iri: str,
    *,
    draft_only: bool = False,
) -> dict[str, str]:
    """Steps 5-7: PUT full config, publish policy, export .policy.

    `draft_only=True` stops after step 5. MGS rejects `PUT /policies/{id}/dry-run`
    against PUBLISH state, so the dry-run debug flow requires skipping publish.
    """
    print("5. Update policy with full config tree...")
    current = await client.get_policy(policy_id)
    current["config"] = _full_config(spec, intake_iri)
    await client.update_policy(policy_id, current)

    if draft_only:
        print("   --draft-only: skipping publish + export. Policy left in DRAFT.")
        return {"policyId": policy_id, "intakeBlockTag": spec.intake_tag, "exportPath": ""}

    print(f"6. Publish policy (async, up to {int(PUBLISH_TIMEOUT_S / 60)} min)...")
    task = await client.publish_policy(policy_id, policy_version=POLICY_VERSION)
    result = await client.wait_for_task(task.taskId, timeout=PUBLISH_TIMEOUT_S)
    if result.status != "COMPLETED":
        raise RuntimeError(f"Policy publish failed: {result.error}")

    print(f"7. Export policy to {spec.export_path.relative_to(REPO_ROOT)}...")
    await client.export_policy(policy_id, spec.export_path)
    return {
        "policyId": policy_id,
        "intakeBlockTag": spec.intake_tag,
        "exportPath": str(spec.export_path),
    }


async def _bootstrap(
    client: GuardianClient, spec: PolicySpec, *, dry_run: bool = False, draft_only: bool = False,
) -> dict[str, str]:
    intake_base = json.loads(spec.intake_schema_path.read_text())

    if dry_run:
        dto, iri = _wrap_schema_dto(spec, intake_base)
        print(json.dumps({
            "policy": _draft_policy(spec),
            "schemaDTO": dto,
            "fullConfig": _full_config(spec, iri),
        }, indent=2))
        return {}

    print("1. Login...")
    await client.login()

    print("2. Create policy draft...")
    policies = await client.create_policy(_draft_policy(spec))
    policy = _pick_created(policies, by="policyTag", value=spec.policy_tag)
    policy_id = policy["id"]
    topic_id = policy.get("topicId") or policy.get("instanceTopicId")
    if not topic_id:
        raise RuntimeError(
            f"Draft policy {policy_id} has no topicId — cannot attach schemas. "
            f"Record: {json.dumps(policy)[:400]}"
        )
    print(f"   policyId={policy_id}, topicId={topic_id}")

    print("3. Create intake schema under policy topic...")
    schema_dto, _ = _wrap_schema_dto(spec, intake_base)
    await client.create_schema(topic_id, schema_dto)
    # MGS's POST /schemas response sometimes lists SR-namespace schemas
    # alongside the just-created one; list this topic's schemas authoritatively
    # and pick the DRAFT we just created.
    in_topic = await client.list_schemas(topic_id)
    drafts = _topic_drafts(in_topic, spec.schema_name)
    if not drafts:
        raise RuntimeError(
            f"No DRAFT {spec.schema_name} found in topic {topic_id} — "
            f"saw {[(s.get('name'), s.get('status')) for s in in_topic]}"
        )
    created = drafts[-1]
    print(f"   schemaId={created['id']}, iri={created['iri']}")

    # MGS auto-bumps the IRI version when an earlier same-name schema is
    # already on-chain, but the bump only inspects the tenant's topic — so the
    # iri may collide with another tenant's `<name>@<version>`.
    # publish_schema_with_bump walks the patch number up until MGS accepts.
    base_version = (
        created["iri"].rsplit("&", 1)[-1] if "&" in created["iri"] else POLICY_VERSION
    )
    final_iri = await _publish_schema(
        client, spec, topic_id, created["id"], base_version,
    )
    return await _finalize(client, spec, policy_id, final_iri, draft_only=draft_only)


async def _resume(
    client: GuardianClient, spec: PolicySpec, *, draft_only: bool = False,
) -> dict[str, str]:
    """Recover from a partial bootstrap: skip steps 1-4, look up the existing
    DRAFT policy + already-published schema, then do steps 5-7. Use when a
    prior run died between schema publish and config PUT."""
    print("1. Login...")
    await client.login()

    print(f"2. Look up policy by tag {spec.policy_tag!r}...")
    policies = await client.list_policies()
    matches = [p for p in policies if p.get("policyTag") == spec.policy_tag]
    if not matches:
        raise RuntimeError(
            f"no policy with policyTag={spec.policy_tag!r} — run without --resume first"
        )
    policy = matches[-1]
    if policy.get("status") != "DRAFT":
        raise RuntimeError(
            f"policy {policy['id']} has status={policy.get('status')!r}; "
            "--resume requires DRAFT. Discontinue published versions in the "
            "portal and re-run without --resume (bump POLICY_TAG if needed)."
        )
    policy_id = policy["id"]
    topic_id = policy.get("topicId") or policy.get("instanceTopicId")
    print(f"   policyId={policy_id}, topicId={topic_id}")

    print("3. Find intake schema under topic...")
    schemas = await client.list_schemas(topic_id)
    pub = _topic_published(schemas, spec.schema_name)
    drafts = _topic_drafts(schemas, spec.schema_name)
    if pub:
        intake_iri = pub[-1]["iri"]
        print(f"   already PUBLISHED: {intake_iri}")
    elif drafts:
        draft = drafts[-1]
        base_version = (
            draft["iri"].rsplit("&", 1)[-1] if "&" in draft.get("iri", "") else POLICY_VERSION
        )
        intake_iri = await _publish_schema(client, spec, topic_id, draft["id"], base_version)
    else:
        seen = [(s.get("name"), s.get("status")) for s in schemas]
        raise RuntimeError(f"no {spec.schema_name} in topic {topic_id}; seen={seen}.")

    return await _finalize(client, spec, policy_id, intake_iri, draft_only=draft_only)


def _load_client_from_env() -> GuardianClient:
    base_url = os.environ.get("GUARDIAN_API_URL")
    sr_user = os.environ.get("GUARDIAN_SR_USERNAME")
    sr_pass = os.environ.get("GUARDIAN_SR_PASSWORD")
    if not (base_url and sr_user and sr_pass):
        raise SystemExit(
            "Set GUARDIAN_API_URL, GUARDIAN_SR_USERNAME, GUARDIAN_SR_PASSWORD "
            "(source api/.env.dev) before running this script."
        )
    return GuardianClient(base_url=base_url, sr_username=sr_user, sr_password=sr_pass)


def run(spec: PolicySpec, *, doc: str | None = None) -> None:
    """CLI entry point for a policy builder. Handles --dry-run / --resume /
    --draft-only and prints the env-var lines for `api/.env.dev`."""
    parser = argparse.ArgumentParser(description=doc)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the draft policy + full config JSON without calling MGS.",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Skip policy/schema creation; pick up at step 5 against the "
             "existing DRAFT policy. Use after a mid-run failure.",
    )
    parser.add_argument(
        "--draft-only", action="store_true",
        help="Stop after the config-PUT step (skip publish + export). Required "
             "to flip into MGS dry-run mode for debugging.",
    )
    args = parser.parse_args()

    if args.dry_run and args.resume:
        raise SystemExit("--dry-run and --resume are mutually exclusive")

    client = _load_client_from_env()
    try:
        if args.resume:
            result = asyncio.run(_resume(client, spec, draft_only=args.draft_only))
        else:
            result = asyncio.run(
                _bootstrap(client, spec, dry_run=args.dry_run, draft_only=args.draft_only)
            )
    except GuardianClientError as e:
        raise SystemExit(f"MGS rejected a request: {e}")
    except GuardianError as e:
        raise SystemExit(f"Guardian client error: {e}")
    except RuntimeError as e:
        raise SystemExit(f"Bootstrap error: {e}")

    if args.dry_run:
        return

    print("\nDone. Paste into api/.env.dev:")
    print(f"    {spec.env_var_prefix}POLICY_ID={result['policyId']}")
    print(f"    {spec.env_var_prefix}INTAKE_BLOCK_TAG={result['intakeBlockTag']}")
