"""
Fixtures for Guardian integration tests.

The mock base URL is pinned to a sentinel host so sourcing `.env.dev` (which
sets GUARDIAN_API_URL=guardianservice.app for the FastAPI runtime) doesn't
redirect respx to a different host than the tests' own `_make_client()`
target. Live-MGS mode is a planned future feature and will be a separate
test path, not an env-var override on this fixture.
"""
from __future__ import annotations

from typing import Iterator

import httpx
import pytest
import respx

pytestmark = pytest.mark.integration

MGS_BASE_URL = "https://mgs.test/api/v1"


@pytest.fixture
def mgs_base_url() -> str:
    return MGS_BASE_URL


@pytest.fixture
def mgs_mock() -> Iterator[respx.MockRouter]:
    """
    respx mock for MGS. The fixture installs default success routes for
    login / session / task polling; individual tests override or add routes
    inside the `with` block.
    """
    with respx.mock(base_url=MGS_BASE_URL, assert_all_called=False) as router:
        router.post("/accounts/loginByEmail").mock(
            return_value=httpx.Response(200, json={"accessToken": "test-jwt"})
        )
        router.get("/accounts/session").mock(
            return_value=httpx.Response(
                200, json={"did": "did:hedera:testnet:abc_0.0.42", "role": "STANDARD_REGISTRY"}
            )
        )
        # Note: `submit_document` calls GET /policies/<id> once per policyId
        # to resolve the policy `owner` DID for the request envelope. We
        # deliberately don't mock that here — tests that care about owner
        # register their own /policies/<id> mock; tests that only assert on
        # call_count tolerate the silent fallback in
        # `GuardianClient._get_policy_owner` (returns empty string when the
        # metadata fetch raises).
        yield router


class _FrozenClock:
    """Monotonic-compatible clock whose advance is driven explicitly by tests."""

    def __init__(self, start: float = 1000.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


@pytest.fixture
def frozen_clock() -> _FrozenClock:
    return _FrozenClock()
