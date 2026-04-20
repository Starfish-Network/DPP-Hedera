"""
Circuit-breaker invariants (specs/001-guardian-integration/contracts/guardian-client.md §Invariants).

Skipped until /speckit-implement; each case documents the invariant it will exercise.
"""
import pytest


def test_breaker_opens_after_three_counting_failures(mgs_mock):
    """5xx × 3 → breaker open; no further calls until 60 s elapse."""
    pytest.skip("awaiting /speckit-implement")


def test_breaker_does_not_count_451(mgs_mock):
    """451 (ToS not accepted) does not increment the counter (research.md §3)."""
    pytest.skip("awaiting /speckit-implement")


def test_breaker_does_not_count_400_or_409(mgs_mock):
    """Per-request 4xx are client-side faults; not breaker fodder."""
    pytest.skip("awaiting /speckit-implement")


def test_breaker_half_open_probe_success_closes(mgs_mock):
    """After 60 s, next call is a probe; 2xx closes the breaker."""
    pytest.skip("awaiting /speckit-implement")


def test_breaker_half_open_probe_failure_resets_window(mgs_mock):
    """Probe failure resets the 60 s window — ONE failure, not another three."""
    pytest.skip("awaiting /speckit-implement")


def test_submit_document_raises_when_breaker_open(mgs_mock):
    """With breaker open, submit_document raises GuardianBreakerOpen and makes no HTTP call."""
    pytest.skip("awaiting /speckit-implement")


def test_hcs_flow_unaffected_when_breaker_open(mgs_mock):
    """Constitution §IV: core HCS recording completes even when Guardian is unavailable."""
    pytest.skip("awaiting /speckit-implement")
