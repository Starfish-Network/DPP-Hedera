"""
Circuit-breaker invariants (specs/001-guardian-integration/contracts/guardian-client.md §Invariants).

Each test exercises one invariant from the contract. The breaker MUST:
- open after 3 counting failures
- not count 451 (ToS) — distinct state, no counter increment
- not count 4xx other than 429 — per-request fault, not infra
- after 60 s, allow ONE probe; success closes, failure restarts the 60 s window
- raise GuardianBreakerOpen on submit_document when open, with NO HTTP call
- the forwarder envelope keeps the HCS path unblocked even when breaker is open
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.service.guardian_client import (
    CircuitBreaker,
    GuardianBreakerOpen,
    GuardianClient,
    GuardianClientError,
    GuardianConflict,
    GuardianToSRequired,
    GuardianUnavailable,
)
from app.service.guardian_forwarder import forward_event_to_guardian
from app.service.guardian_policies import PolicyConfig

MGS_BASE_URL = "https://mgs.test/api/v1"


def _make_client(breaker: CircuitBreaker, clock) -> GuardianClient:
    return GuardianClient(
        base_url=MGS_BASE_URL,
        sr_username="sr",
        sr_password="secret",
        breaker=breaker,
        clock=clock,
    )


def _doc(i: int) -> dict:
    """Distinct eventHash per call so the idempotency cache doesn't short-circuit."""
    return {"eventHash": f"0x{i:064x}", "eventType": "creating"}


def _run(coro):
    return asyncio.run(coro)


def test_breaker_opens_after_three_counting_failures(mgs_mock, frozen_clock):
    breaker = CircuitBreaker(fail_threshold=3, open_duration_s=60.0, clock=frozen_clock)
    client = _make_client(breaker, frozen_clock)
    submit_route = mgs_mock.post("/policies/POL/tag/INTAKE/blocks/sync-events").mock(
        return_value=httpx.Response(503, json={"code": "ServiceUnavailable"})
    )

    async def scenario():
        await client.login()
        for i in range(3):
            with pytest.raises(GuardianUnavailable):
                await client.submit_document("POL", "INTAKE", _doc(i))
        assert breaker.state == "open"
        prior = submit_route.call_count
        with pytest.raises(GuardianBreakerOpen):
            await client.submit_document("POL", "INTAKE", _doc(99))
        # 4th call short-circuited at the breaker — no extra HTTP request
        assert submit_route.call_count == prior

    _run(scenario())


def test_breaker_does_not_count_451(mgs_mock, frozen_clock):
    """T056: 451 → GuardianToSRequired, no 3-strikes counter increment.

    `tos_required` is a *distinct* breaker state (research.md §3); subsequent
    calls are blocked at the breaker (no point retrying until the operator
    accepts ToS in the MGS portal), but the 3-strikes counter remains 0 —
    so `tos_required` does NOT decay into the 60 s `open` window.
    """
    breaker = CircuitBreaker(fail_threshold=3, open_duration_s=60.0, clock=frozen_clock)
    client = _make_client(breaker, frozen_clock)
    mgs_mock.post("/policies/POL/tag/INTAKE/blocks/sync-events").mock(
        return_value=httpx.Response(451, json={"code": "ToSRequired"})
    )

    async def scenario():
        await client.login()
        with pytest.raises(GuardianToSRequired):
            await client.submit_document("POL", "INTAKE", _doc(0))
        assert breaker.consecutive_failures == 0
        assert breaker.state == "tos_required"
        # Subsequent attempts are blocked at the breaker until manual portal action.
        with pytest.raises(GuardianBreakerOpen):
            await client.submit_document("POL", "INTAKE", _doc(1))
        # 60 s elapsing must NOT clear `tos_required` (only the operator can).
        frozen_clock.advance(120.0)
        assert breaker.state == "tos_required"

    _run(scenario())


def test_breaker_does_not_count_400_or_409(mgs_mock, frozen_clock):
    breaker = CircuitBreaker(fail_threshold=3, open_duration_s=60.0, clock=frozen_clock)
    client = _make_client(breaker, frozen_clock)
    mgs_mock.post("/policies/POL/tag/INTAKE/blocks/sync-events").mock(
        side_effect=[
            httpx.Response(400, json={"code": "BadRequest"}),
            httpx.Response(409, json={"code": "Conflict"}),
        ]
    )

    async def scenario():
        await client.login()
        with pytest.raises(GuardianClientError):
            await client.submit_document("POL", "INTAKE", _doc(0))
        with pytest.raises(GuardianConflict):
            await client.submit_document("POL", "INTAKE", _doc(1))

    _run(scenario())
    assert breaker.consecutive_failures == 0
    assert breaker.state == "closed"


def test_breaker_half_open_probe_success_closes(mgs_mock, frozen_clock):
    breaker = CircuitBreaker(fail_threshold=3, open_duration_s=60.0, clock=frozen_clock)
    client = _make_client(breaker, frozen_clock)
    mgs_mock.post("/policies/POL/tag/INTAKE/blocks/sync-events").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, json={"accepted": True}),
        ]
    )

    async def scenario():
        await client.login()
        for i in range(3):
            with pytest.raises(GuardianUnavailable):
                await client.submit_document("POL", "INTAKE", _doc(i))
        assert breaker.state == "open"

        frozen_clock.advance(61.0)
        assert breaker.state == "half_open"

        ack = await client.submit_document("POL", "INTAKE", _doc(99))
        assert ack.cached is False
        assert breaker.state == "closed"

    _run(scenario())


def test_breaker_half_open_probe_failure_resets_window(mgs_mock, frozen_clock):
    """ONE failure re-opens the window — not another three."""
    breaker = CircuitBreaker(fail_threshold=3, open_duration_s=60.0, clock=frozen_clock)
    client = _make_client(breaker, frozen_clock)
    mgs_mock.post("/policies/POL/tag/INTAKE/blocks/sync-events").mock(
        return_value=httpx.Response(503)
    )

    async def scenario():
        await client.login()
        for i in range(3):
            with pytest.raises(GuardianUnavailable):
                await client.submit_document("POL", "INTAKE", _doc(i))
        assert breaker.state == "open"

        frozen_clock.advance(61.0)
        assert breaker.state == "half_open"

        with pytest.raises(GuardianUnavailable):
            await client.submit_document("POL", "INTAKE", _doc(99))
        assert breaker.state == "open"

        # Within the new 60 s window, breaker rejects without an HTTP call
        frozen_clock.advance(30.0)
        with pytest.raises(GuardianBreakerOpen):
            await client.submit_document("POL", "INTAKE", _doc(100))

    _run(scenario())


def test_submit_document_raises_when_breaker_open(mgs_mock, frozen_clock):
    """Pre-open the breaker via the public API; verify no HTTP call at the next submit."""
    breaker = CircuitBreaker(fail_threshold=3, open_duration_s=60.0, clock=frozen_clock)
    for _ in range(3):
        breaker.record_failure(GuardianUnavailable("503"))
    assert breaker.state == "open"

    client = _make_client(breaker, frozen_clock)
    submit_route = mgs_mock.post("/policies/POL/tag/INTAKE/blocks/sync-events").mock(
        return_value=httpx.Response(200, json={"accepted": True})
    )

    async def scenario():
        with pytest.raises(GuardianBreakerOpen):
            await client.submit_document("POL", "INTAKE", _doc(0))

    _run(scenario())
    assert submit_route.called is False


def test_hcs_flow_unaffected_when_breaker_open(mgs_mock, frozen_clock):
    """Constitution §IV: forward_event_to_guardian catches GuardianBreakerOpen and
    returns a 'skipped' result instead of raising. Routes that depend on this can
    complete the HCS write and respond 200 even while Guardian is unavailable."""
    breaker = CircuitBreaker(fail_threshold=3, open_duration_s=60.0, clock=frozen_clock)
    for _ in range(3):
        breaker.record_failure(GuardianUnavailable("503"))
    assert breaker.state == "open"

    client = _make_client(breaker, frozen_clock)

    test_policy = PolicyConfig(
        slug="test_breaker",
        policy_id="POL",
        intake_block_tag="INTAKE",
        policy_version="1.0.0",
        source_type_field="eventType",
        vc_type_field="testType",
    )

    submit_route = mgs_mock.post("/policies/POL/tag/INTAKE/blocks/sync-events").mock(
        return_value=httpx.Response(200, json={"accepted": True})
    )

    async def scenario():
        return await forward_event_to_guardian(
            client, test_policy, {"eventType": "creating"}, "0x" + "a" * 64
        )

    result = _run(scenario())
    assert result == {"status": "skipped", "reason": "breaker_open"}
    assert submit_route.called is False
