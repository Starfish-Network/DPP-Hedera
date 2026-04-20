"""
Guardian policy / VC retrieval endpoints.

    GET /guardian/gdst/vc/{event_hash}   — latest VC (200) or chain with ?history=true
    GET /guardian/fsma/vc/{event_hash}   — same for FSMA 204

Per SC-007: pending submissions within 30 s return 202; past 5 min return 503
with detail "vc_manual_review".
"""
from fastapi import APIRouter

router = APIRouter()
