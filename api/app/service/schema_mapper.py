"""
Pydantic <-> Guardian JSON-LD mapper.

Builds `credentialSubject` objects for the VC types declared in
specs/001-guardian-integration/contracts/vc-output.schema.json — full event
payload verbatim (FR-015) plus `GuaranteedMetadata`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from app.helpers.compliance import sha256_bytes32
from app.service.guardian_policies import PolicyConfig


def _as_dict(event: BaseModel | dict) -> dict:
    if isinstance(event, BaseModel):
        return event.model_dump(mode="json")
    return event


def _lookup_dotted(d: dict, path: str) -> Any:
    cur: Any = d
    for seg in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(seg)
    return cur


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def to_credential_subject(
    event: BaseModel | dict,
    policy: PolicyConfig,
    *,
    supersedes: str | None = None,
    event_hash_hex: str | None = None,
) -> dict[str, Any]:
    """
    `event_hash_hex`: optional precomputed `"0x<64>"` hash of the same event
    dict. The caller in events.py already hashes for HCS; passing it here
    avoids a second `sha256_bytes32` + `json.dumps` on the hot path.
    """
    evt = _as_dict(event)

    raw_type = evt.get(policy.source_type_field)
    if raw_type is None:
        raise ValueError(
            f"event missing {policy.source_type_field!r} for policy {policy.slug!r}"
        )
    mapped_type = policy.type_map.get(raw_type, raw_type) if policy.type_map else raw_type

    subject: dict[str, Any] = dict(evt)
    subject[policy.vc_type_field] = mapped_type

    for key, path in policy.required_hoists.items():
        value = _lookup_dotted(evt, path)
        if not value:
            raise ValueError(
                f"{policy.slug} event missing required field {path!r} "
                f"(must hoist to credentialSubject.{key})"
            )
        subject[key] = value

    subject["eventHash"] = event_hash_hex or ("0x" + sha256_bytes32(evt).hex())
    subject["complianceStatus"] = "superseded" if supersedes else "compliant"
    subject["policyVersion"] = policy.policy_version
    subject["issuedAt"] = _now_iso()
    if supersedes:
        subject["supersedes"] = supersedes
    return subject
