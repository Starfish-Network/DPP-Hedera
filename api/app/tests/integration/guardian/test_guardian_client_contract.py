"""
Contract tests for `api/app/service/guardian_client.py`.

Each test maps to an invariant declared in
specs/001-guardian-integration/contracts/guardian-client.md §Invariants.
"""
from __future__ import annotations

import asyncio

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
    GuardianTaskTimeout,
    GuardianToSRequired,
    GuardianUnavailable,
    HealthStatus,
)

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
    mgs_mock.post("/accounts/login").mock(
        side_effect=[
            httpx.Response(200, json={"accessToken": "jwt-1"}),
            httpx.Response(200, json={"accessToken": "jwt-2"}),
        ]
    )
    mgs_mock.get("/profiles/alice").mock(
        side_effect=[
            httpx.Response(401, json={"code": "expired"}),
            httpx.Response(200, json={"username": "alice", "did": "did:hedera:testnet:abc_0.0.42"}),
        ]
    )

    async def scenario() -> str:
        client = _make_client()
        await client.login()
        return await client.get_user_did("alice")

    did = _run(scenario())
    assert did == "did:hedera:testnet:abc_0.0.42"


def test_451_surfaces_as_tos_required_and_sets_breaker(mgs_mock: respx.MockRouter):
    mgs_mock.post("/accounts/login").mock(
        return_value=httpx.Response(451, json={"code": "tos_required", "message": "Accept ToS"})
    )

    async def scenario() -> CircuitBreaker:
        client = _make_client()
        with pytest.raises(GuardianToSRequired):
            await client.login()
        return client.breaker

    breaker = _run(scenario())
    assert breaker.state == "tos_required"


def test_register_user_is_idempotent_on_409(mgs_mock: respx.MockRouter):
    mgs_mock.post("/accounts/register").mock(
        return_value=httpx.Response(409, json={"code": "exists"})
    )
    mgs_mock.get("/profiles/bob").mock(
        return_value=httpx.Response(
            200, json={"username": "bob", "did": "did:hedera:testnet:xyz_0.0.77", "role": "User"}
        )
    )

    async def scenario():
        client = _make_client()
        await client.login()
        return await client.register_user("bob", "pwd")

    record = _run(scenario())
    assert record.did == "did:hedera:testnet:xyz_0.0.77"
    assert record.username == "bob"


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
