"""Guardian identity endpoints.

Operator onboarding (registration, DID resolution, consent capture) is out of
scope for v1 — operators are pre-provisioned directly in the MGS portal and
consent is captured out-of-band (spec §FR-007 / Assumptions, quickstart §5).
Only the SR-level health probe lives here in v1.
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.service.guardian_client import (
    BreakerState,
    GuardianClient,
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


class HealthResponse(BaseModel):
    status: HealthStatus
    breaker: BreakerState
    last_failure_at: float | None


@router.get("/health", response_model=HealthResponse, summary="Guardian health & breaker state")
async def health(client: GuardianClient = Depends(get_guardian_client)) -> HealthResponse:
    return HealthResponse(
        status=await client.get_health(),
        breaker=client.circuit_status(),
        last_failure_at=client.last_failure_at,
    )
