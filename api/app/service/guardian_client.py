"""
Guardian / Managed Guardian Service (MGS) REST client.

Implements the contract declared in
specs/001-guardian-integration/contracts/guardian-client.md.

Module-level constants exposed here for test stubbing (SC-007):

    VC_PENDING_THRESHOLD_S       — return 202 while within this window
    VC_MANUAL_REVIEW_CEILING_S   — return 503 vc_manual_review past this ceiling
"""
