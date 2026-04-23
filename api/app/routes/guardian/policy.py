"""
Guardian policy / VC retrieval endpoints.

    GET /guardian/gdst/vc/{event_hash}   - latest VC (200) or chain with ?history=true
    GET /guardian/fsma/vc/{event_hash}   - same for FSMA 204 (US2, phase 4)

Per SC-007: pending submissions within 30 s return 202; past 5 min return 503
with detail "vc_manual_review". The 202/503 flow requires a submitted-at
timestamp the route cannot synthesise on its own, so v1 surfaces it via
`GuardianClient.get_vc_retrieval_status` (direct caller contract) and the
HTTP route returns 200/404 only.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import settings
from app.routes.guardian.identity import get_guardian_client
from app.service.guardian_client import (
    GuardianAuthError,
    GuardianClient,
    GuardianClientError,
    GuardianNotFound,
    GuardianToSRequired,
    GuardianUnavailable,
)

router = APIRouter()


def _ensure_gdst_configured() -> str:
    policy_id = settings.GUARDIAN_GDST_POLICY_ID
    if not policy_id:
        raise HTTPException(
            status_code=503,
            detail="Guardian GDST policy is not configured",
        )
    return policy_id


@router.get(
    "/gdst/vc/{event_hash}",
    summary="Retrieve the GDST compliance VC for an event hash",
)
async def get_gdst_vc(
    event_hash: str,
    history: bool = Query(False, description="Return the full supersede chain"),
    client: GuardianClient = Depends(get_guardian_client),
) -> Any:
    policy_id = _ensure_gdst_configured()
    try:
        if history:
            chain = await client.get_vc_by_event_hash(
                policy_id, event_hash, history=True
            )
            return {"eventHash": event_hash, "history": chain or []}

        vc = await client.get_vc_by_event_hash(policy_id, event_hash, history=False)
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
