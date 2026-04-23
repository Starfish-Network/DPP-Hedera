"""
Fixtures for Guardian integration tests.

Contract: mocked MGS responses are the default; set GUARDIAN_LIVE=1 to hit a real
MGS tenant (see specs/001-guardian-integration/quickstart.md §7).
"""
from __future__ import annotations

import os
from typing import Iterator

import httpx
import pytest
import respx

pytestmark = pytest.mark.integration

MGS_BASE_URL = os.environ.get("GUARDIAN_API_URL", "https://mgs.test/api/v1")


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
