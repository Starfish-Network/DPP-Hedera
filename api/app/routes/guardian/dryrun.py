"""
Guardian dry-run submission route.

    POST /guardian/dryrun/submit/{policy_slug}
        body:    any JSON object (becomes the credentialSubject)
        returns: { policySlug, policyId, vc, vcId, raw }

Set up the underlying policy with `python3 scripts/bootstrap_dryrun_policy.py`
and configure GUARDIAN_DRYRUN_POLICY_ID + GUARDIAN_DRYRUN_INTAKE_BLOCK_TAG.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.core.config import settings
from app.routes.guardian.identity import get_guardian_client
from app.service.guardian_client import (
    GuardianAuthError,
    GuardianClient,
    GuardianClientError,
    GuardianToSRequired,
    GuardianUnavailable,
)

router = APIRouter()


@router.post(
    "/dryrun/submit/{policy_slug}",
    summary="Submit a payload to the dry-run sandbox policy and return the issued VC",
)
async def dryrun_submit(
    policy_slug: str,
    payload: dict[str, Any] = Body(...),
    client: GuardianClient = Depends(get_guardian_client),
) -> dict[str, Any]:
    pid = settings.GUARDIAN_DRYRUN_POLICY_ID
    block_tag = settings.GUARDIAN_DRYRUN_INTAKE_BLOCK_TAG
    if not (pid and block_tag):
        raise HTTPException(
            status_code=503,
            detail=(
                "dry-run policy is not configured. Run "
                "`python3 scripts/bootstrap_dryrun_policy.py` and set "
                "GUARDIAN_DRYRUN_POLICY_ID + GUARDIAN_DRYRUN_INTAKE_BLOCK_TAG."
            ),
        )
    if not payload:
        raise HTTPException(status_code=422, detail="payload must be a non-empty JSON object")

    try:
        body = await client.submit_dry_run(pid, block_tag, payload)
    except GuardianToSRequired:
        raise HTTPException(status_code=503, detail="tos_required")
    except (GuardianUnavailable, GuardianAuthError):
        raise HTTPException(status_code=503, detail="guardian_unavailable")
    except GuardianClientError as e:
        raise HTTPException(status_code=400, detail=str(e))

    response = body.get("response") if isinstance(body, dict) else None
    vc = response.get("document") if isinstance(response, dict) else None
    return {
        "policySlug": policy_slug,
        "policyId": pid,
        "vc": vc,
        "vcId": (vc or {}).get("id"),
        "raw": body,
    }
