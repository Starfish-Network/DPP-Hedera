"""
Guardian VC retrieval endpoint.

    GET /guardian/{policy_slug}/vc/{event_hash}   - latest VC, or chain with ?history=true

HTTP-surface contract: specs/001-guardian-integration/contracts/guardian-http-errors.md.
Pending / manual-review retrieval state is surfaced only via
`GuardianClient.get_vc_retrieval_status()` in v1 (spec.md §Edge Cases).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.routes.guardian.identity import get_guardian_client
from app.service.guardian_client import (
    GuardianAuthError,
    GuardianClient,
    GuardianClientError,
    GuardianNotFound,
    GuardianToSRequired,
    GuardianUnavailable,
)
from app.service.guardian_policies import get_policy

router = APIRouter()


@router.get(
    "/{policy_slug}/policy-vc",
    summary="Retrieve the policy's own self-describing VC (POLICY-type document)",
)
async def get_policy_vc(
    policy_slug: str,
    client: GuardianClient = Depends(get_guardian_client),
) -> Any:
    policy = get_policy(policy_slug)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"unknown policy: {policy_slug}")
    if not policy.enabled:
        raise HTTPException(
            status_code=503,
            detail=f"Guardian {policy_slug.upper()} policy is not configured",
        )
    try:
        vc = await client.get_policy_vc(policy.policy_id)
        if vc is None:
            raise HTTPException(
                status_code=404,
                detail=f"no POLICY-type document for {policy_slug}",
            )
        return vc
    except GuardianToSRequired:
        raise HTTPException(status_code=503, detail="tos_required")
    except (GuardianUnavailable, GuardianAuthError):
        raise HTTPException(status_code=503, detail="guardian_unavailable")
    except GuardianClientError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{policy_slug}/vc/{event_hash}",
    summary="Retrieve the compliance VC for an event hash",
)
async def get_vc(
    policy_slug: str,
    event_hash: str,
    history: bool = Query(False, description="Return the full supersede chain"),
    client: GuardianClient = Depends(get_guardian_client),
) -> Any:
    policy = get_policy(policy_slug)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"unknown policy: {policy_slug}")
    if not policy.enabled:
        raise HTTPException(
            status_code=503,
            detail=f"Guardian {policy_slug.upper()} policy is not configured",
        )
    try:
        if history:
            chain = await client.get_vc_by_event_hash(
                policy.policy_id, event_hash, history=True
            )
            return {"eventHash": event_hash, "history": chain or []}

        vc = await client.get_vc_by_event_hash(policy.policy_id, event_hash, history=False)
        if vc is not None:
            return vc
        raise HTTPException(status_code=404, detail="VC not found for eventHash")
    except GuardianNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GuardianToSRequired:
        raise HTTPException(status_code=503, detail="tos_required")
    except (GuardianUnavailable, GuardianAuthError):
        raise HTTPException(status_code=503, detail="guardian_unavailable")
    except GuardianClientError as e:
        raise HTTPException(status_code=400, detail=str(e))
