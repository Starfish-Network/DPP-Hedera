"""
Registry of Guardian compliance policies.

Rationale and alternatives in specs/001-guardian-integration/research.md §8;
invariants (enforced at module import below) in data-model.md §Policy Registry.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import settings


@dataclass(frozen=True)
class PolicyConfig:
    slug: str
    policy_id: str | None
    intake_block_tag: str | None
    policy_version: str
    source_type_field: str
    vc_type_field: str
    type_map: dict[str, str] = field(default_factory=dict)
    required_hoists: dict[str, str] = field(default_factory=dict)

    @property
    def enabled(self) -> bool:
        return bool(self.policy_id and self.intake_block_tag)


GDST = PolicyConfig(
    slug="gdst",
    policy_id=settings.GUARDIAN_GDST_POLICY_ID,
    intake_block_tag=settings.GUARDIAN_GDST_INTAKE_BLOCK_TAG,
    policy_version="1.0.0",
    source_type_field="gdst_event_type",
    vc_type_field="gdstEventType",
    type_map={
        "Fishing": "Fishing",
        "Landing": "Landing",
        "Transshipment": "Transshipment",
        "OnVesselProcessing": "OnVesselProcessing",
        "Processing": "Processing",
        "Shipping": "Shipping",
        "ShippingReceiving": "Shipping",
        "Aggregation": "Aggregation",
        "AggregationDisaggregation": "Aggregation",
    },
    required_hoists={"species": "what.species"},
)

# `source_type_field="eventType"` matches the existing Pydantic model
# (api/app/models/starfish_events.py uses camelCase `eventType`). The
# data-model.md spec lists `fsma204_event_type` as the conventional name
# for symmetry with GDST's `gdst_event_type`; reconciling that requires
# renaming `eventType` across ~20 call sites and is deferred to v2.
# Registry invariant (uniqueness across policies) still holds: GDST uses
# `gdst_event_type`, FSMA uses `eventType`.
#
# `type_map={}` is intentional — the VC schema's `fsma204EventType` enum
# is lowercase (creating, shipping, …) matching the Pydantic Literal
# values directly, so no source→VC label mapping is needed.
#
# `required_hoists={}` — `vc-output.schema.json`'s
# `FSMA204ComplianceCredential` branch declares no required top-level
# subject fields beyond `GuaranteedMetadata` + `fsma204EventType`, both
# stamped by the generic mapper.
FSMA = PolicyConfig(
    slug="fsma",
    policy_id=settings.GUARDIAN_FSMA_POLICY_ID,
    intake_block_tag=settings.GUARDIAN_FSMA_INTAKE_BLOCK_TAG,
    policy_version="1.0.0",
    source_type_field="eventType",
    vc_type_field="fsma204EventType",
    type_map={},
    required_hoists={},
)


POLICIES: dict[str, PolicyConfig] = {p.slug: p for p in (GDST, FSMA)}


def _assert_registry_invariants() -> None:
    source_fields: dict[str, str] = {}
    vc_fields: dict[str, str] = {}
    for p in POLICIES.values():
        if p.source_type_field in source_fields:
            raise RuntimeError(
                f"PolicyConfig dispatch collision: {p.slug!r} and "
                f"{source_fields[p.source_type_field]!r} both use "
                f"source_type_field={p.source_type_field!r}"
            )
        if p.vc_type_field in vc_fields:
            raise RuntimeError(
                f"PolicyConfig VC-discriminator collision: {p.slug!r} and "
                f"{vc_fields[p.vc_type_field]!r} both use "
                f"vc_type_field={p.vc_type_field!r}"
            )
        source_fields[p.source_type_field] = p.slug
        vc_fields[p.vc_type_field] = p.slug


_assert_registry_invariants()


def get_policy(slug: str) -> PolicyConfig | None:
    return POLICIES.get(slug)


def get_policy_for_event(event: dict) -> PolicyConfig | None:
    for p in POLICIES.values():
        if p.source_type_field in event:
            return p
    return None
