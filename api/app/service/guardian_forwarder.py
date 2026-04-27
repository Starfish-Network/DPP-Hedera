"""
Shared non-blocking Guardian forwarding for the /events route handlers.

Both /events/gdst and /epcis/compliance run the same shape: build credential
subject → submit_document → envelope errors so HCS path stays unblocked
(Constitution §IV). This module owns the shared pieces; route handlers stay
focused on their pre-Guardian logic.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

from app.core.config import settings
from app.routes.guardian.identity import get_guardian_client
from app.service.guardian_client import (
    GuardianBreakerOpen,
    GuardianClient,
    GuardianError,
)
from app.service.guardian_policies import PolicyConfig
from app.service.schema_mapper import to_credential_subject

logger = logging.getLogger(__name__)


def maybe_get_guardian_client(policy: PolicyConfig) -> GuardianClient | None:
    """Return the client iff Guardian is configured AND `policy.enabled`.

    Constitution §IV: HCS + ComplianceVerifier MUST proceed even when
    Guardian is unconfigured or its breaker is open. Routes that get `None`
    here skip Guardian forwarding without raising.
    """
    if not (
        settings.GUARDIAN_API_URL
        and settings.GUARDIAN_SR_USERNAME
        and settings.GUARDIAN_SR_PASSWORD
        and policy.enabled
    ):
        return None
    try:
        return get_guardian_client()
    except HTTPException:
        return None


async def forward_event_to_guardian(
    client: GuardianClient,
    policy: PolicyConfig,
    event_dict: dict,
    event_hash_hex: str,
) -> dict[str, Any]:
    """Submit `event_dict` to Guardian under `policy`.

    Returns the status dict the route embeds under `"guardian"` in its
    response. T054 will expand the WARN payload to the full FR-006 quartet
    `{event_hash, operator_did, mgs_error_class, breaker_opened_at}`.
    """
    try:
        subject = to_credential_subject(
            event_dict, policy, event_hash_hex=event_hash_hex
        )
        ack = await client.submit_document(
            policy_id=policy.policy_id,
            block_tag=policy.intake_block_tag,
            document=subject,
        )
        return {
            "status": "submitted",
            "cached": ack.cached,
            "submittedAt": ack.submitted_at.isoformat(),
        }
    except GuardianBreakerOpen:
        logger.warning(
            "guardian.skipped",
            extra={"event_hash": event_hash_hex, "reason": "breaker_open"},
        )
        return {"status": "skipped", "reason": "breaker_open"}
    except GuardianError as e:
        logger.warning(
            "guardian.error",
            extra={"event_hash": event_hash_hex, "error": e.__class__.__name__},
        )
        return {"status": "error", "reason": e.__class__.__name__}
