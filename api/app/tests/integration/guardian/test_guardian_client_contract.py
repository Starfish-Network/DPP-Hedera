"""
Contract tests for `api/app/service/guardian_client.py`.

Each test maps to an invariant declared in
specs/001-guardian-integration/contracts/guardian-client.md §Invariants.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.guardian import router as guardian_router
from app.routes.guardian.identity import get_guardian_client
from app.service.guardian_client import (
    BreakerState,
    CircuitBreaker,
    GuardianClient,
    GuardianClientError,
    GuardianTaskTimeout,
    GuardianToSRequired,
    GuardianUnavailable,
    HealthStatus,
    SubmitAck,
    TaskHandle,
)
from app.service.schema_mapper import to_credential_subject_gdst

SAMPLES_DIR = Path(__file__).resolve().parents[5] / "samples" / "gdst"

MGS_BASE_URL = "https://mgs.test/api/v1"


def _run(coro):
    return asyncio.run(coro)


def _make_client(
    breaker: CircuitBreaker | None = None, clock=None
) -> GuardianClient:
    return GuardianClient(
        base_url=MGS_BASE_URL,
        sr_username="sr",
        sr_password="secret",
        breaker=breaker,
        clock=clock or (lambda: 0.0),
    )


def test_login_returns_bearer_token_and_refreshes_on_401(mgs_mock: respx.MockRouter):
    mgs_mock.post("/accounts/loginByEmail").mock(
        side_effect=[
            httpx.Response(200, json={"accessToken": "jwt-1"}),
            httpx.Response(200, json={"accessToken": "jwt-2"}),
        ]
    )
    mgs_mock.get("/tasks/task-1").mock(
        side_effect=[
            httpx.Response(401, json={"code": "expired"}),
            httpx.Response(200, json={"taskId": "task-1", "status": "COMPLETED", "result": {}}),
        ]
    )

    async def scenario():
        client = _make_client()
        await client.login()
        return await client.wait_for_task("task-1", timeout=1.0)

    result = _run(scenario())
    assert result.status == "COMPLETED"


def test_mgs_two_token_login_exchanges_refresh_for_access(mgs_mock: respx.MockRouter):
    """MGS returns only a refreshToken from /accounts/login; the client must
    exchange it at /accounts/access-token for the bearer JWT."""
    mgs_mock.post("/accounts/loginByEmail").mock(
        return_value=httpx.Response(
            200,
            json={
                "username": "jprodrigues",
                "role": "TENANT_ADMIN",
                "refreshToken": "refresh-abc",
            },
        )
    )
    exchange = mgs_mock.post("/accounts/access-token").mock(
        return_value=httpx.Response(200, json={"accessToken": "bearer-xyz"})
    )

    async def scenario() -> str:
        client = _make_client()
        return await client.login()

    token = _run(scenario())
    assert token == "bearer-xyz"
    assert exchange.called
    body = json.loads(exchange.calls.last.request.content)
    assert body == {"refreshToken": "refresh-abc"}


def test_451_surfaces_as_tos_required_and_sets_breaker(mgs_mock: respx.MockRouter):
    mgs_mock.post("/accounts/loginByEmail").mock(
        return_value=httpx.Response(451, json={"code": "tos_required", "message": "Accept ToS"})
    )

    async def scenario() -> CircuitBreaker:
        client = _make_client()
        with pytest.raises(GuardianToSRequired):
            await client.login()
        return client.breaker

    breaker = _run(scenario())
    assert breaker.state == "tos_required"


def test_wait_for_task_times_out(mgs_mock: respx.MockRouter):
    mgs_mock.get("/tasks/task-42").mock(
        return_value=httpx.Response(200, json={"taskId": "task-42", "status": "PROCESSING"})
    )

    async def scenario():
        client = _make_client()
        await client.login()
        await client.wait_for_task("task-42", timeout=0.05)

    with pytest.raises(GuardianTaskTimeout):
        _run(scenario())


def test_breaker_transitions_closed_open_halfopen_closed():
    t = {"now": 1000.0}
    breaker = CircuitBreaker(fail_threshold=3, open_duration_s=60.0, clock=lambda: t["now"])

    assert breaker.state == "closed"
    breaker.record_failure(GuardianUnavailable("503"))
    breaker.record_failure(GuardianUnavailable("503"))
    assert breaker.state == "closed"
    breaker.record_failure(GuardianUnavailable("503"))
    assert breaker.state == "open"
    assert not breaker.should_allow_call()

    t["now"] += 59.0
    assert breaker.state == "open"

    t["now"] += 2.0
    assert breaker.state == "half_open"
    assert breaker.should_allow_call()

    breaker.record_success()
    assert breaker.state == "closed"


class _StubClient:
    """Minimal stand-in that drives GET /guardian/health through its four paths."""

    def __init__(self, status: HealthStatus, breaker_state: BreakerState = "closed") -> None:
        self._status = status
        self._breaker_state = breaker_state

    async def get_health(self) -> HealthStatus:
        return self._status

    def circuit_status(self) -> BreakerState:
        return self._breaker_state

    last_failure_at: float | None = None


@pytest.mark.parametrize(
    "status, breaker_state",
    [
        ("ok", "closed"),
        ("tos_required", "tos_required"),
        ("breaker_open", "open"),
        ("unavailable", "closed"),
    ],
)
def test_health_endpoint_surfaces_each_status(status: str, breaker_state: str):
    stub = _StubClient(status=status, breaker_state=breaker_state)
    test_app = FastAPI()
    test_app.include_router(guardian_router)
    test_app.dependency_overrides[get_guardian_client] = lambda: stub
    with TestClient(test_app) as http:
        r = http.get("/guardian/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == status
    assert body["breaker"] == breaker_state


# --- T020: idempotency (FR-004) --------------------------------------------

def _load_sample(name: str) -> dict:
    with (SAMPLES_DIR / f"{name}.json").open() as f:
        return json.load(f)


def test_gdst_idempotent_submission(mgs_mock: respx.MockRouter):
    """
    FR-004: resubmitting the same event returns the same eventHash and makes
    exactly one MGS POST to /external/<policy>/<block>.
    """
    sample = _load_sample("fishing")
    subject = to_credential_subject_gdst(sample, policy_version="1.0.0")
    policy_id = "policy-xyz"
    block_tag = "intake"

    submit_route = mgs_mock.post(f"/external/{policy_id}/{block_tag}").mock(
        return_value=httpx.Response(202, json={"status": "accepted"})
    )

    async def scenario() -> tuple[SubmitAck, SubmitAck, int]:
        client = _make_client()
        await client.login()
        first = await client.submit_document(policy_id, block_tag, subject)
        second = await client.submit_document(policy_id, block_tag, subject)
        return first, second, submit_route.call_count

    first, second, call_count = _run(scenario())

    assert first.cached is False
    assert second.cached is True
    assert first.event_hash == second.event_hash == subject["eventHash"]
    assert call_count == 1


# --- T021: VC retrieval history (FR-007, FR-014) ---------------------------

def _vc_with(subject_overrides: dict, *, base_subject: dict, issued_at: str) -> dict:
    subject = {**base_subject, **subject_overrides}
    return {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "type": ["VerifiableCredential", "GDSTComplianceCredential"],
        "issuer": "did:hedera:testnet:abc_0.0.42",
        "issuanceDate": issued_at,
        "proof": {"type": "Ed25519Signature2018"},
        "credentialSubject": {**subject, "issuedAt": issued_at},
    }


def test_gdst_vc_retrieval_history(mgs_mock: respx.MockRouter):
    """
    FR-007 / FR-014: after a corrective superseding VC is issued for an event,

    - history=False returns the non-superseded ("currently-authoritative") VC
      per guardian-client.md: "the one whose complianceStatus != 'superseded'".
    - history=True returns [oldest, ..., latest] in issuance order so callers
      can audit corrections end-to-end.
    """
    sample = _load_sample("fishing")
    base_subject = to_credential_subject_gdst(sample, policy_version="1.0.0")
    event_hash = base_subject["eventHash"]
    policy_id = "policy-xyz"

    original = _vc_with(
        {"complianceStatus": "compliant"},
        base_subject=base_subject,
        issued_at="2026-03-15T10:31:00Z",
    )
    correction = _vc_with(
        {"complianceStatus": "superseded", "supersedes": event_hash},
        base_subject=base_subject,
        issued_at="2026-03-16T12:00:00Z",
    )
    unrelated = _vc_with(
        {"complianceStatus": "compliant", "eventHash": "0x" + "0" * 64},
        base_subject=base_subject,
        issued_at="2026-03-17T09:00:00Z",
    )

    mgs_mock.get(f"/policies/{policy_id}/documents").mock(
        side_effect=[
            httpx.Response(200, json={"items": [original, correction, unrelated]}),
            httpx.Response(200, json={"items": [original, correction, unrelated]}),
        ]
    )

    async def scenario():
        client = _make_client()
        await client.login()
        latest = await client.get_vc_by_event_hash(policy_id, event_hash, history=False)
        chain = await client.get_vc_by_event_hash(policy_id, event_hash, history=True)
        return latest, chain

    latest, chain = _run(scenario())

    # Non-superseded branch: the original compliant VC is returned.
    assert latest is not None and not isinstance(latest, list)
    assert latest["credentialSubject"]["complianceStatus"] == "compliant"
    assert latest["credentialSubject"]["eventHash"] == event_hash

    assert isinstance(chain, list)
    assert len(chain) == 2
    assert chain[0]["credentialSubject"]["complianceStatus"] == "compliant"
    assert chain[1]["credentialSubject"]["complianceStatus"] == "superseded"
    assert chain[1]["credentialSubject"]["supersedes"] == event_hash
    assert chain[0]["credentialSubject"]["issuedAt"] < chain[1]["credentialSubject"]["issuedAt"]


# --- Bootstrap lifecycle: schema/policy CRUD for the build script ----------

def test_create_schema_posts_to_topic_and_returns_list(mgs_mock: respx.MockRouter):
    topic_id = "0.0.12345"
    new_record = {"id": "sch-1", "uuid": "uuid-1", "name": "GDSTFishingEvent"}
    route = mgs_mock.post(f"/schemas/{topic_id}").mock(
        return_value=httpx.Response(200, json=[new_record])
    )

    async def scenario():
        client = _make_client()
        await client.login()
        return await client.create_schema(topic_id, {"name": "GDSTFishingEvent"})

    records = _run(scenario())
    assert records == [new_record]
    assert route.called
    submitted = json.loads(route.calls.last.request.content)
    assert submitted == {"name": "GDSTFishingEvent"}


def test_publish_schema_returns_task_handle(mgs_mock: respx.MockRouter):
    route = mgs_mock.put("/schemas/push/sch-1/publish").mock(
        return_value=httpx.Response(200, json={"taskId": "task-pub-1"})
    )

    async def scenario() -> TaskHandle:
        client = _make_client()
        await client.login()
        return await client.publish_schema("sch-1", version="1.2.3")

    handle = _run(scenario())
    assert handle.taskId == "task-pub-1"
    body = json.loads(route.calls.last.request.content)
    assert body == {"version": "1.2.3"}


def test_publish_schema_rejects_missing_task_id(mgs_mock: respx.MockRouter):
    mgs_mock.put("/schemas/push/sch-1/publish").mock(
        return_value=httpx.Response(200, json={})
    )

    async def scenario():
        client = _make_client()
        await client.login()
        await client.publish_schema("sch-1")

    with pytest.raises(GuardianClientError):
        _run(scenario())


def test_create_policy_posts_and_returns_list(mgs_mock: respx.MockRouter):
    created = {"id": "pol-1", "uuid": "uuid-pol-1", "name": "GDST Seafood Traceability"}
    route = mgs_mock.post("/policies").mock(
        return_value=httpx.Response(200, json=[created])
    )

    async def scenario():
        client = _make_client()
        await client.login()
        return await client.create_policy({"name": "GDST Seafood Traceability"})

    records = _run(scenario())
    assert records == [created]
    assert route.called


def test_publish_policy_sends_version_and_returns_handle(mgs_mock: respx.MockRouter):
    route = mgs_mock.put("/policies/push/pol-1/publish").mock(
        return_value=httpx.Response(200, json={"taskId": "task-pub-pol"})
    )

    async def scenario() -> TaskHandle:
        client = _make_client()
        await client.login()
        return await client.publish_policy("pol-1", policy_version="1.0.0")

    handle = _run(scenario())
    assert handle.taskId == "task-pub-pol"
    body = json.loads(route.calls.last.request.content)
    assert body == {"policyVersion": "1.0.0"}


def test_export_policy_writes_zip_bytes(mgs_mock: respx.MockRouter, tmp_path):
    payload = b"PK\x03\x04" + b"\x00" * 32  # minimal zip-ish signature
    mgs_mock.get("/policies/pol-1/export/file").mock(
        return_value=httpx.Response(200, content=payload)
    )
    out = tmp_path / "exported" / "gdst.policy"

    async def scenario() -> Path:
        client = _make_client()
        await client.login()
        return await client.export_policy("pol-1", out)

    written = _run(scenario())
    assert written == out
    assert out.read_bytes() == payload


def test_import_policy_file_posts_binary_and_returns_handle(
    mgs_mock: respx.MockRouter,
):
    zip_bytes = b"PK\x03\x04imported"
    route = mgs_mock.post("/policies/push/import/file").mock(
        return_value=httpx.Response(200, json={"taskId": "task-import-1"})
    )

    async def scenario() -> TaskHandle:
        client = _make_client()
        await client.login()
        return await client.import_policy_file(zip_bytes)

    handle = _run(scenario())
    assert handle.taskId == "task-import-1"
    sent = route.calls.last.request
    assert sent.content == zip_bytes
    assert sent.headers.get("content-type") == "application/octet-stream"


def test_get_policy_returns_draft_config(mgs_mock: respx.MockRouter):
    policy = {"id": "pol-1", "name": "GDST", "status": "DRAFT", "topicId": "0.0.555"}
    mgs_mock.get("/policies/pol-1").mock(
        return_value=httpx.Response(200, json=policy)
    )

    async def scenario():
        client = _make_client()
        await client.login()
        return await client.get_policy("pol-1")

    assert _run(scenario()) == policy


def test_update_policy_sends_full_config(mgs_mock: respx.MockRouter):
    updated = {"id": "pol-1", "name": "GDST", "status": "DRAFT",
               "config": {"blockType": "interfaceContainerBlock"}}
    route = mgs_mock.put("/policies/pol-1").mock(
        return_value=httpx.Response(200, json=updated)
    )

    async def scenario():
        client = _make_client()
        await client.login()
        return await client.update_policy("pol-1", updated)

    assert _run(scenario()) == updated
    body = json.loads(route.calls.last.request.content)
    assert body["config"]["blockType"] == "interfaceContainerBlock"


def test_bootstrap_methods_surface_5xx_as_unavailable(mgs_mock: respx.MockRouter):
    """5xx from /schemas or /policies must raise GuardianUnavailable and trip
    the breaker so the bootstrap script stops instead of hammering MGS."""
    mgs_mock.post("/schemas/0.0.99").mock(
        return_value=httpx.Response(503, text="busy")
    )

    client_holder: dict[str, GuardianClient] = {}

    async def scenario():
        client = _make_client()
        client_holder["c"] = client
        await client.login()
        await client.create_schema("0.0.99", {"name": "x"})

    with pytest.raises(GuardianUnavailable):
        _run(scenario())

    # One failure isn't enough to open a 3-strike breaker, but the failure
    # must have been recorded.
    assert client_holder["c"].breaker.consecutive_failures == 1
