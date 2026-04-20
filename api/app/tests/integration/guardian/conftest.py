"""
Fixtures for Guardian integration tests.

Contract: mocked MGS responses are the default; set GUARDIAN_LIVE=1 to hit a real
MGS tenant (see specs/001-guardian-integration/quickstart.md §7).

Rationale (Constitution §V, §VI): contract tests for `guardian_client.py` run
against the shape declared in specs/001-guardian-integration/contracts/mgs-boundary.openapi.yaml.
"""
import os
import pytest


pytestmark = pytest.mark.integration


@pytest.fixture
def mgs_base_url() -> str:
    return os.environ.get("GUARDIAN_API_URL", "https://mgs.test/api/v1")


@pytest.fixture
def mgs_mock(mgs_base_url):
    """
    Placeholder MGS mock. `/speckit-implement` will replace this with a `respx`
    mock wired against the endpoints in
    specs/001-guardian-integration/contracts/mgs-boundary.openapi.yaml.

    Skips the test if the implementation has not landed yet.
    """
    try:
        import respx  # noqa: F401
    except ImportError:
        pytest.skip("respx not installed yet — add to requirements in /speckit-implement")

    try:
        from app.service.guardian_client import GuardianClient  # noqa: F401
    except ImportError:
        pytest.skip("guardian_client not implemented yet — scheduled for /speckit-implement")

    # Real fixture body lands with the implementation.
    yield None
