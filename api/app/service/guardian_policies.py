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

# Registration-only stub until T047 fills type_map + required_hoists and
# T048 wires POST /events/epcis/compliance through it. Kept here so the
# registry invariants exercise both policies.
FSMA = PolicyConfig(
    slug="fsma",
    policy_id=settings.GUARDIAN_FSMA_POLICY_ID,
    intake_block_tag=settings.GUARDIAN_FSMA_INTAKE_BLOCK_TAG,
    policy_version="1.0.0",
    source_type_field="fsma204_event_type",
    vc_type_field="fsma204EventType",
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
