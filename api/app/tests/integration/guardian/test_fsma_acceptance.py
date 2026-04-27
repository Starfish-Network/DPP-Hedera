"""
Acceptance tests for FSMA 204 compliance rules.

Every rule in specs/001-guardian-integration/data-model.md §Rule Source Table
(FSMA section) has a test here. Test names match the "Acceptance test" column.

Strategy mirrors test_gdst_acceptance.py: load each canonical sample from
samples/fsma/, then for each rule exercise a valid variant (sample passes
Pydantic + fsma_min_rules) and an invalid variant (missing / malformed →
Pydantic ValidationError or fsma_min_rules() False).
"""
from __future__ import annotations

import copy
import functools
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.helpers.compliance import fsma_min_rules
from app.models.starfish_events import (
    CreatingEvent,
    PackingEvent,
    ReceivingEvent,
    ShippingEvent,
    TransformingEvent,
    UnpackingEvent,
)

SAMPLES_DIR = Path(__file__).resolve().parents[5] / "samples" / "fsma"


@functools.lru_cache(maxsize=None)
def _load(name: str) -> dict:
    """Cached read of the canonical sample. Callers `copy.deepcopy` before mutating."""
    with (SAMPLES_DIR / f"{name}.json").open() as f:
        return json.load(f)


def _assert_valid(model_cls, sample: dict) -> None:
    """Round-trip a sample through Pydantic + fsma_min_rules."""
    evt = model_cls(**sample)
    as_dict = evt.model_dump(mode="json")
    assert fsma_min_rules(as_dict) is True


# --- Common rules (apply to every event type) ---------------------------------

def test_common_event_time_required():
    """FSMA_COMMON_001: event_time must be present on every event."""
    sample = _load("creating")
    _assert_valid(CreatingEvent, sample)

    bad = copy.deepcopy(sample)
    bad.pop("event_time")
    with pytest.raises(ValidationError):
        CreatingEvent(**bad)


# --- Creating -----------------------------------------------------------------

def test_creating_biz_location_required():
    """FSMA_CREATING_001: Creating requires biz_location."""
    sample = _load("creating")
    _assert_valid(CreatingEvent, sample)

    bad = copy.deepcopy(sample)
    bad.pop("biz_location")
    with pytest.raises(ValidationError):
        CreatingEvent(**bad)


def test_creating_quantity_list_non_empty():
    """FSMA_CREATING_002: Creating requires quantity_list non-empty."""
    sample = _load("creating")
    _assert_valid(CreatingEvent, sample)

    bad = copy.deepcopy(sample)
    bad["quantity_list"] = []
    with pytest.raises(ValidationError):
        CreatingEvent(**bad)


# --- Shipping -----------------------------------------------------------------

def test_shipping_ship_from_required():
    """FSMA_SHIPPING_001: Shipping requires ship_from."""
    sample = _load("shipping")
    _assert_valid(ShippingEvent, sample)

    bad = copy.deepcopy(sample)
    bad.pop("ship_from")
    with pytest.raises(ValidationError):
        ShippingEvent(**bad)


def test_shipping_ship_to_required():
    """FSMA_SHIPPING_002: Shipping requires ship_to."""
    sample = _load("shipping")
    _assert_valid(ShippingEvent, sample)

    bad = copy.deepcopy(sample)
    bad.pop("ship_to")
    with pytest.raises(ValidationError):
        ShippingEvent(**bad)


def test_shipping_items_non_empty():
    """FSMA_SHIPPING_003: Shipping requires items non-empty."""
    sample = _load("shipping")
    _assert_valid(ShippingEvent, sample)

    bad = copy.deepcopy(sample)
    bad["items"] = []
    with pytest.raises(ValidationError):
        ShippingEvent(**bad)


# --- Receiving ----------------------------------------------------------------

def test_receiving_location_required():
    """FSMA_RECEIVING_001: Receiving requires received_at (data-model.md says `received_at` OR `ship_to`).

    The Pydantic model only declares `received_at` (and `shipped_from`) — there is no
    `ship_to` alternative on ReceivingEvent. So the OR-rule collapses to a stricter
    "received_at required" at the FastAPI boundary. If `ship_to` is reintroduced as an
    Optional[str] later, expand this test to cover the OR semantics.
    """
    sample = _load("receiving")
    _assert_valid(ReceivingEvent, sample)

    bad = copy.deepcopy(sample)
    bad.pop("received_at")
    with pytest.raises(ValidationError):
        ReceivingEvent(**bad)


def test_receiving_items_non_empty():
    """FSMA_RECEIVING_002: Receiving requires items non-empty."""
    sample = _load("receiving")
    _assert_valid(ReceivingEvent, sample)

    bad = copy.deepcopy(sample)
    bad["items"] = []
    with pytest.raises(ValidationError):
        ReceivingEvent(**bad)


# --- Transforming -------------------------------------------------------------

def test_transforming_facility_required():
    """FSMA_TRANSFORMING_001: Transforming requires facility."""
    sample = _load("transforming")
    _assert_valid(TransformingEvent, sample)

    bad = copy.deepcopy(sample)
    bad.pop("facility")
    with pytest.raises(ValidationError):
        TransformingEvent(**bad)


def test_transforming_inputs_non_empty():
    """FSMA_TRANSFORMING_002: Transforming requires input_items non-empty."""
    sample = _load("transforming")
    _assert_valid(TransformingEvent, sample)

    bad = copy.deepcopy(sample)
    bad["input_items"] = []
    with pytest.raises(ValidationError):
        TransformingEvent(**bad)


def test_transforming_outputs_non_empty():
    """FSMA_TRANSFORMING_003: Transforming requires output_items non-empty."""
    sample = _load("transforming")
    _assert_valid(TransformingEvent, sample)

    bad = copy.deepcopy(sample)
    bad["output_items"] = []
    with pytest.raises(ValidationError):
        TransformingEvent(**bad)


# --- Packing ------------------------------------------------------------------

def test_packing_facility_required():
    """FSMA_PACKING_001: Packing requires facility."""
    sample = _load("packing")
    _assert_valid(PackingEvent, sample)

    bad = copy.deepcopy(sample)
    bad.pop("facility")
    with pytest.raises(ValidationError):
        PackingEvent(**bad)


def test_packing_container_id_required():
    """FSMA_PACKING_002: Packing requires container_id."""
    sample = _load("packing")
    _assert_valid(PackingEvent, sample)

    bad = copy.deepcopy(sample)
    bad.pop("container_id")
    with pytest.raises(ValidationError):
        PackingEvent(**bad)


def test_packing_inputs_non_empty():
    """FSMA_PACKING_003: Packing requires input_items non-empty."""
    sample = _load("packing")
    _assert_valid(PackingEvent, sample)

    bad = copy.deepcopy(sample)
    bad["input_items"] = []
    with pytest.raises(ValidationError):
        PackingEvent(**bad)


# --- Unpacking ----------------------------------------------------------------

def test_unpacking_facility_required():
    """FSMA_UNPACKING_001: Unpacking requires facility."""
    sample = _load("unpacking")
    _assert_valid(UnpackingEvent, sample)

    bad = copy.deepcopy(sample)
    bad.pop("facility")
    with pytest.raises(ValidationError):
        UnpackingEvent(**bad)


def test_unpacking_container_id_required():
    """FSMA_UNPACKING_002: Unpacking requires container_id."""
    sample = _load("unpacking")
    _assert_valid(UnpackingEvent, sample)

    bad = copy.deepcopy(sample)
    bad.pop("container_id")
    with pytest.raises(ValidationError):
        UnpackingEvent(**bad)


def test_unpacking_outputs_non_empty():
    """FSMA_UNPACKING_003: Unpacking requires output_items non-empty."""
    sample = _load("unpacking")
    _assert_valid(UnpackingEvent, sample)

    bad = copy.deepcopy(sample)
    bad["output_items"] = []
    with pytest.raises(ValidationError):
        UnpackingEvent(**bad)
