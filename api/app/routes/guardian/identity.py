"""
Guardian identity endpoints.

    GET  /guardian/health              — MGS reachability + breaker state (FR-009)
    POST /guardian/register            — idempotent operator registration (FR-008, FR-015)
    GET  /guardian/did/{username}      — look up operator DID
"""
from fastapi import APIRouter

router = APIRouter()
