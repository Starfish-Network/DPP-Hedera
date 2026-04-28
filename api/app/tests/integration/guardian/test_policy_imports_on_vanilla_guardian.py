"""
T058 + T062 — vanilla-Guardian composability suite.

T058 (import only) and T062 (full publish-submit-retrieve E2E + downstream
trust-chain validation) live in the same file because they share the same
docker-compose Guardian fixture and the same login/skip plumbing.

Exercises spec §SC-004 and US4 acceptance scenarios A4.1 + A4.2.

Skipped in CI. To run locally:
1. Spin up a vanilla Guardian docker-compose stack (Hedera's official
   reference setup at github.com/hashgraph/guardian works); ensure its
   /api/v1 surface is reachable.
2. Pre-provision an SR account in the vanilla Guardian portal.
3. Export:
       GUARDIAN_VANILLA_COMPOSE=1
       VANILLA_GUARDIAN_URL=http://localhost:3000/api/v1   # or wherever your stack listens
       VANILLA_GUARDIAN_SR_USERNAME=<your SR email>
       VANILLA_GUARDIAN_SR_PASSWORD=<your SR password>
4. pytest api/app/tests/integration/guardian/test_policy_imports_on_vanilla_guardian.py
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import pytest

from app.service.guardian_client import GuardianClient
from app.service.guardian_policies import GDST
from app.service.schema_mapper import to_credential_subject

REPO_ROOT = Path(__file__).resolve().parents[5]
POLICY_FILES = [
    REPO_ROOT / "schemas" / "policies" / "gdst-seafood-traceability.policy",
    REPO_ROOT / "schemas" / "policies" / "fsma-204-food-safety.policy",
]
GDST_POLICY_PATH = REPO_ROOT / "schemas" / "policies" / "gdst-seafood-traceability.policy"
GDST_POLICY_TAG = "GDST-1-2-seafood-v2"
GDST_INTAKE_BLOCK = "gdst_intake"
GDST_FISHING_SAMPLE = REPO_ROOT / "samples" / "gdst" / "fishing.json"


pytestmark = pytest.mark.skipif(
    os.environ.get("GUARDIAN_VANILLA_COMPOSE") != "1",
    reason="vanilla Guardian fixture not available; set GUARDIAN_VANILLA_COMPOSE=1 to run",
)


def _vanilla_client() -> GuardianClient:
    base_url = os.environ.get("VANILLA_GUARDIAN_URL", "http://localhost:3000/api/v1")
    sr_user = os.environ.get("VANILLA_GUARDIAN_SR_USERNAME")
    sr_pass = os.environ.get("VANILLA_GUARDIAN_SR_PASSWORD")
    if not (sr_user and sr_pass):
        pytest.skip(
            "set VANILLA_GUARDIAN_SR_USERNAME / VANILLA_GUARDIAN_SR_PASSWORD "
            "to run T058 against a docker-compose vanilla Guardian"
        )
    return GuardianClient(base_url=base_url, sr_username=sr_user, sr_password=sr_pass)


async def _wait_for_vc(
    client: GuardianClient,
    policy_id: str,
    event_hash_hex: str,
    *,
    timeout: float = 300.0,
    poll_interval: float = 5.0,
) -> dict:
    """Poll `get_vc_by_event_hash` until a single VC appears or `timeout` elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        vc = await client.get_vc_by_event_hash(policy_id, event_hash_hex, history=False)
        if vc is not None and not isinstance(vc, list):
            return vc
        await asyncio.sleep(poll_interval)
    raise AssertionError(f"no VC for eventHash={event_hash_hex} after {timeout}s")


@pytest.mark.parametrize(
    "policy_path",
    POLICY_FILES,
    ids=[p.stem for p in POLICY_FILES],
)
def test_policy_imports_on_vanilla_guardian(policy_path: Path):
    """T058 / SC-004 / US4 A4.1: each shipped `.policy` zip imports successfully
    on vanilla Guardian.

    Implicitly proves no Starfish-specific dependencies: if the import task
    transitions to COMPLETED on a clean Guardian, the policy graph has no
    references to private endpoints, schemas, or services.
    """
    assert policy_path.exists(), f"missing export: {policy_path}"
    zip_bytes = policy_path.read_bytes()

    async def scenario():
        client = _vanilla_client()
        await client.login()
        before = await client.list_policies()
        task = await client.import_policy_file(zip_bytes)
        result = await client.wait_for_task(task.taskId, timeout=600.0)
        assert result.status == "COMPLETED", (
            f"import failed for {policy_path.name}: {result.error}"
        )
        after = await client.list_policies()
        assert len(after) > len(before), (
            f"policy count unchanged after import of {policy_path.name}"
        )

    asyncio.run(scenario())


def test_gdst_policy_publish_and_submit_e2e_on_vanilla_guardian():
    """T062 / SC-004 / US4 A4.1 (full E2E half): import the GDST `.policy`,
    publish it, submit a Fishing sample, retrieve the issued
    GDSTComplianceCredential, and verify trust-chain anchors on the importing
    vanilla SR's DID with `complianceStatus = "compliant"`.

    The point is composability: a clean Guardian with a brand-new SR can
    issue GDSTComplianceCredentials from our policy with zero Starfish-side
    code on the path. The VC's `issuer` will be the vanilla SR's DID, NOT
    Starfish's testnet SR DID — because the importing SR re-issues under its
    own key. That's the desired behavior; Starfish ships the policy, the
    importer owns issuance.
    """
    assert GDST_POLICY_PATH.exists(), f"missing export: {GDST_POLICY_PATH}"
    assert GDST_FISHING_SAMPLE.exists(), f"missing sample: {GDST_FISHING_SAMPLE}"

    async def scenario():
        client = _vanilla_client()
        await client.login()

        # No public get_session() yet; bootstrap scripts use this same
        # _call_with_refresh path. If a third caller appears, promote it.
        r = await client._call_with_refresh("GET", "/accounts/session")
        sr_did = r.json().get("did")
        assert sr_did, "vanilla Guardian session response missing `did`"

        # Check-first import: list once, import only if the tag isn't present.
        # Avoids exception-swallowing the import-task error on re-runs.
        policies = await client.list_policies()
        if not any(p.get("policyTag") == GDST_POLICY_TAG for p in policies):
            task = await client.import_policy_file(GDST_POLICY_PATH.read_bytes())
            result = await client.wait_for_task(task.taskId, timeout=600.0)
            assert result.status == "COMPLETED", f"import failed: {result.error}"
            policies = await client.list_policies()

        gdst = next((p for p in policies if p.get("policyTag") == GDST_POLICY_TAG), None)
        assert gdst, (
            f"imported GDST policy not visible; "
            f"tags seen: {[p.get('policyTag') for p in policies]}"
        )
        policy_id = gdst["id"]

        if gdst.get("status") not in ("PUBLISH", "PUBLISHED"):
            ptask = await client.publish_policy(policy_id, policy_version="1.0.0")
            presult = await client.wait_for_task(ptask.taskId, timeout=600.0)
            assert presult.status == "COMPLETED", f"publish failed: {presult.error}"

        # Pass the production GDST PolicyConfig to the mapper for correct
        # subject shape (source_type_field, type_map, vc_type_field). The
        # actual submission targets `policy_id` from the import above — not
        # the testnet-MGS id baked into GDST.policy_id. Mapper output is
        # policy-id-agnostic.
        event = json.loads(GDST_FISHING_SAMPLE.read_text())
        subject = to_credential_subject(event, GDST)
        event_hash_hex = subject["eventHash"]
        await client.submit_document(
            policy_id=policy_id,
            block_tag=GDST_INTAKE_BLOCK,
            document=subject,
        )

        # Vanilla Guardian on a fresh testnet account can be slower than MGS.
        vc = await _wait_for_vc(client, policy_id, event_hash_hex, timeout=300.0)

        cs = vc.get("credentialSubject")
        if isinstance(cs, list):
            cs = cs[0] if cs else {}
        assert vc.get("issuer") == sr_did, (
            f"VC issuer {vc.get('issuer')!r} does not match vanilla SR DID {sr_did!r}"
        )
        assert cs.get("complianceStatus") == "compliant", (
            f"complianceStatus={cs.get('complianceStatus')!r}"
        )
        assert cs.get("eventHash") == event_hash_hex, (
            f"VC eventHash {cs.get('eventHash')!r} != submitted {event_hash_hex!r}"
        )

    asyncio.run(scenario())


def test_downstream_demo_policy_validates_gdst_vc_on_vanilla_guardian():
    """T062 / US4 A4.2: downstream demo policy receives a GDSTComplianceCredential,
    its trustChainBlock validates the chain back to the SR DID, and it issues
    a CarbonCreditEligibility VC.

    BLOCKED: samples/downstream/carbon-credit-demo.policy.json references a
    `#CarbonCreditEligibility` schema that is intentionally not shipped — that
    schema is the downstream operator's deliverable per T059's policy
    description. To unblock and run this test:

      1. Provide a `CarbonCreditEligibility` VC schema in your SR namespace.
      2. Edit samples/downstream/carbon-credit-demo.policy.json:
         - Regenerate the placeholder block UUIDs.
         - Replace the `TRUSTED_ISSUER` DID in `cc_filter_trusted_issuer`
           with your vanilla SR DID (so the customLogicBlock accepts VCs
           issued by the SR running the upstream test above).
      3. Import + publish the demo policy.
      4. Feed in a GDSTComplianceCredential VC produced by
         `test_gdst_policy_publish_and_submit_e2e_on_vanilla_guardian`.
      5. Verify the demo issues a CarbonCreditEligibility VC and that its
         trust-chain proof references the same SR DID + the input VC's
         eventHash.

    Until those prerequisites land, this test is intentionally inert.
    """
    pytest.skip(
        "downstream demo policy is not directly runnable: requires a "
        "CarbonCreditEligibility schema (downstream operator's deliverable, "
        "not a Starfish ship). See the docstring of this test + the "
        "description field in samples/downstream/carbon-credit-demo.policy.json "
        "for the unblock checklist."
    )
