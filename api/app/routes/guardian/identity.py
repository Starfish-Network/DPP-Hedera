"""Guardian identity endpoints."""
from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.service.guardian_client import (
    BreakerState,
    GuardianAuthError,
    GuardianClient,
    GuardianError,
    GuardianNotFound,
    GuardianToSRequired,
    GuardianUnavailable,
    HealthStatus,
)

router = APIRouter()


@lru_cache(maxsize=1)
def get_guardian_client() -> GuardianClient:
    """
    Lazy-init a single GuardianClient. Raises 503 if MGS config is incomplete.
    Overridable via `app.dependency_overrides[get_guardian_client]` in tests.
    """
    if not (settings.GUARDIAN_API_URL and settings.GUARDIAN_SR_USERNAME and settings.GUARDIAN_SR_PASSWORD):
        raise HTTPException(status_code=503, detail="Guardian is not configured")
    return GuardianClient(
        base_url=settings.GUARDIAN_API_URL,
        sr_username=settings.GUARDIAN_SR_USERNAME,
        sr_password=settings.GUARDIAN_SR_PASSWORD,
    )


def _mgs_to_http(exc: GuardianError) -> HTTPException:
    if isinstance(exc, GuardianNotFound):
        return HTTPException(status_code=404, detail=str(exc) or "not_found")
    if isinstance(exc, GuardianToSRequired):
        return HTTPException(status_code=503, detail="tos_required")
    if isinstance(exc, GuardianAuthError):
        return HTTPException(status_code=503, detail="guardian_auth_failed")
    if isinstance(exc, GuardianUnavailable):
        return HTTPException(status_code=503, detail="guardian_unavailable")
    return HTTPException(status_code=503, detail="guardian_error")


class HealthResponse(BaseModel):
    status: HealthStatus
    breaker: BreakerState
    last_failure_at: float | None


class RegisterRequest(BaseModel):
    username: str
    password: str
    acknowledged_vc_disclosure: bool = Field(
        ..., description="Operator consent to have event data published as a VC (FR-015)."
    )
    consent_recorded_at: datetime = Field(..., description="ISO-8601 timestamp of consent capture (FR-015).")
    role: Literal["User", "STANDARD_REGISTRY"] = "User"


class RegisterResponse(BaseModel):
    username: str
    role: str
    did: str | None
    consent_recorded_at: datetime


@router.get("/health", response_model=HealthResponse, summary="Guardian health & breaker state")
async def health(client: GuardianClient = Depends(get_guardian_client)) -> HealthResponse:
    return HealthResponse(
        status=await client.get_health(),
        breaker=client.circuit_status(),
        last_failure_at=client.last_failure_at,
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    summary="Register an operator (idempotent) with explicit VC-disclosure consent",
)
async def register(
    body: RegisterRequest,
    client: GuardianClient = Depends(get_guardian_client),
) -> RegisterResponse:
    if not body.acknowledged_vc_disclosure:
        # FR-015: consent must be explicit — not inferrable from absence.
        raise HTTPException(
            status_code=400,
            detail="acknowledged_vc_disclosure must be true",
        )
    try:
        record = await client.register_user(body.username, body.password, role=body.role)
        handle = await client.set_user_credentials(
            body.username,
            {
                "acknowledged_vc_disclosure": "true",
                "consent_recorded_at": body.consent_recorded_at.isoformat(),
            },
        )
        await client.wait_for_task(handle.taskId)
    except GuardianError as exc:
        raise _mgs_to_http(exc) from exc
    return RegisterResponse(
        username=record.username,
        role=record.role,
        did=record.did,
        consent_recorded_at=body.consent_recorded_at,
    )


@router.get("/did/{username}", summary="Resolve an operator's Hedera DID")
async def get_did(
    username: str,
    client: GuardianClient = Depends(get_guardian_client),
) -> dict[str, str]:
    try:
        did = await client.get_user_did(username)
    except GuardianNotFound as exc:
        raise HTTPException(status_code=404, detail=f"{username} not found") from exc
    except GuardianError as exc:
        raise _mgs_to_http(exc) from exc
    return {"username": username, "did": did}
