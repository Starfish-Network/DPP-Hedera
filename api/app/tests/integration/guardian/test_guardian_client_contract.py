"""
Contract tests for `api/app/service/guardian_client.py`.

Each test here maps to an invariant declared in
specs/001-guardian-integration/contracts/guardian-client.md §Invariants.
Implementation lands under `/speckit-implement`; tests are skipped until then.
"""
import pytest


def test_login_returns_bearer_token(mgs_mock):
    """GuardianClient.login returns the access token and caches it."""
    pytest.skip("awaiting /speckit-implement")


def test_register_user_is_idempotent_on_409(mgs_mock):
    """FR-008: register_user on existing username resolves the DID, does not raise."""
    pytest.skip("awaiting /speckit-implement")


def test_submit_document_fires_and_acks(mgs_mock):
    """submit_document does not block on VC creation (Constitution §IV)."""
    pytest.skip("awaiting /speckit-implement")


def test_get_vc_by_event_hash_filters_client_side(mgs_mock):
    """MGS does not index eventHash; client filters in memory and paginates."""
    pytest.skip("awaiting /speckit-implement")


def test_451_surfaces_as_tos_required(mgs_mock):
    """451 → GuardianToSRequired, does NOT increment the breaker (research.md §3)."""
    pytest.skip("awaiting /speckit-implement")


def test_wait_for_task_times_out_at_120s(mgs_mock):
    """wait_for_task raises GuardianTaskTimeout after its configured timeout."""
    pytest.skip("awaiting /speckit-implement")
