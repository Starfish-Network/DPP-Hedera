"""
Pydantic <-> Guardian JSON-LD mapper.

Builds `credentialSubject` objects for the two VC types declared in
specs/001-guardian-integration/contracts/vc-output.schema.json:

    to_credential_subject_gdst(event, policy_version, supersedes=None) -> dict
    to_credential_subject_fsma(event, policy_version, supersedes=None) -> dict

Both mappers embed the full event payload verbatim (FR-015) plus the
`GuaranteedMetadata` fields (eventHash, complianceStatus, policyVersion,
issuedAt, optional supersedes) and the type-specific discriminator
(`gdstEventType` / `fsma204EventType`).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from app.helpers.compliance import sha256_bytes32

# Pydantic `gdst_event_type` -> VC schema `gdstEventType` (vc-output.schema.json
# enum uses short names "Shipping"/"Aggregation"; the API accepts the longer
# "ShippingReceiving"/"AggregationDisaggregation" labels used in the Starfish
# event model).
_GDST_TYPE_MAP = {
    "Fishing": "Fishing",
    "Landing": "Landing",
    "Transshipment": "Transshipment",
    "OnVesselProcessing": "OnVesselProcessing",
    "Processing": "Processing",
    "Shipping": "Shipping",
    "ShippingReceiving": "Shipping",
    "Aggregation": "Aggregation",
    "AggregationDisaggregation": "Aggregation",
}


def _as_dict(event: BaseModel | dict) -> dict:
    if isinstance(event, BaseModel):
        return event.model_dump(mode="json")
    return dict(event)


def _event_hash_hex(event_dict: dict) -> str:
    return "0x" + sha256_bytes32(event_dict).hex()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def to_credential_subject_gdst(
    event: BaseModel | dict,
    policy_version: str,
    supersedes: str | None = None,
) -> dict[str, Any]:
    """
    Build the credentialSubject for a GDSTComplianceCredential.

    Embeds the full event payload verbatim (FR-015) plus GuaranteedMetadata.
    `species` is hoisted to the top level to satisfy the VC schema's
    ``required: ["gdstEventType", "species"]`` (vc-output.schema.json).
    """
    evt = _as_dict(event)

    raw_type = evt.get("gdst_event_type")
    if raw_type not in _GDST_TYPE_MAP:
        raise ValueError(f"Unknown gdst_event_type: {raw_type!r}")
    gdst_type = _GDST_TYPE_MAP[raw_type]

    what = evt.get("what") or {}
    species = what.get("species")
    if not species:
        raise ValueError("GDST event is missing what.species — required by VC schema")

    subject: dict[str, Any] = dict(evt)
    subject["gdstEventType"] = gdst_type
    subject["species"] = species
    subject["eventHash"] = _event_hash_hex(evt)
    subject["complianceStatus"] = "superseded" if supersedes else "compliant"
    subject["policyVersion"] = policy_version
    subject["issuedAt"] = _now_iso()
    if supersedes:
        subject["supersedes"] = supersedes
    return subject
