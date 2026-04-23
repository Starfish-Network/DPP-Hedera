"""
Acceptance tests for GDST compliance rules.

Every rule in specs/001-guardian-integration/data-model.md §Rule Source Table
(GDST section) has a test here. Test names match the "Acceptance test" column.

Strategy: load each canonical sample from samples/gdst/, then for each rule
exercise a valid variant (sample passes Pydantic + gdst_min_rules + mapper) and
an invalid variant (missing / malformed → Pydantic ValidationError or
gdst_min_rules() False). Rules enforced at the Pydantic validator layer surface
as ValidationError; rules enforced by the shared rule predicate surface as
`gdst_min_rules() is False`.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.helpers.compliance import gdst_min_rules
from app.models.gdst.aggregation import AggregationEvent
from app.models.gdst.fishing import FishingEvent
from app.models.gdst.landing import LandingEvent
from app.models.gdst.on_vessel import OnVesselProcessingEvent
from app.models.gdst.processing import ProcessingEvent
from app.models.gdst.shipping import ShippingReceivingEvent
from app.models.gdst.transshipment import TransshipmentEvent
from app.service.schema_mapper import to_credential_subject_gdst

SAMPLES_DIR = Path(__file__).resolve().parents[5] / "samples" / "gdst"


def _load(name: str) -> dict:
    with (SAMPLES_DIR / f"{name}.json").open() as f:
        return json.load(f)


def _assert_valid(model_cls, sample: dict) -> None:
    """Round-trip a sample through Pydantic + gdst_min_rules + the mapper."""
    evt = model_cls(**sample)
    as_dict = evt.model_dump(mode="json")
    assert gdst_min_rules(as_dict) is True
    subject = to_credential_subject_gdst(evt, policy_version="1.0.0")
    assert subject["eventHash"].startswith("0x")
    assert subject["complianceStatus"] == "compliant"
    assert subject["policyVersion"] == "1.0.0"
    assert "gdstEventType" in subject
    assert subject["species"] == as_dict["what"]["species"]


# --- Common rules (apply to all CTE types) -------------------------------------

def test_common_event_datetime_required(mgs_mock):
    """GDST_COMMON_001: when.event_datetime must be present."""
    sample = _load("fishing")
    _assert_valid(FishingEvent, sample)

    bad = copy.deepcopy(sample)
    bad["when"].pop("event_datetime")
    with pytest.raises(ValidationError):
        FishingEvent(**bad)


def test_common_species_format(mgs_mock):
    """GDST_COMMON_002: what.species must match ^[A-Z]{3}$."""
    sample = _load("fishing")
    _assert_valid(FishingEvent, sample)

    bad = copy.deepcopy(sample)
    bad["what"]["species"] = "tuna"  # lower-case, wrong length
    with pytest.raises(ValidationError):
        FishingEvent(**bad)


def test_common_quantity_positive(mgs_mock):
    """GDST_COMMON_003: what.quantity must be > 0."""
    sample = _load("fishing")
    _assert_valid(FishingEvent, sample)

    bad = copy.deepcopy(sample)
    bad["what"]["quantity"] = 0
    with pytest.raises(ValidationError):
        FishingEvent(**bad)


def test_common_uom_enum(mgs_mock):
    """GDST_COMMON_004: what.unit_of_measure must be in {KGM, TNE, LBR, EA}."""
    sample = _load("fishing")
    _assert_valid(FishingEvent, sample)

    bad = copy.deepcopy(sample)
    bad["what"]["unit_of_measure"] = "kg"
    with pytest.raises(ValidationError):
        FishingEvent(**bad)


# --- Fishing -------------------------------------------------------------------

def test_fishing_vessel_identification(mgs_mock):
    """GDST_FISHING_001: Fishing event must carry vessel.vessel_id or vessel.vessel_name."""
    sample = _load("fishing")
    _assert_valid(FishingEvent, sample)

    # Vessel present in Pydantic but both identifiers blank -> rule predicate fails.
    bad = copy.deepcopy(sample)
    bad["vessel"] = {"vessel_registration": "REG-ONLY"}
    evt = FishingEvent(**bad)
    assert gdst_min_rules(evt.model_dump(mode="json")) is False


def test_fishing_authorization_required(mgs_mock):
    """GDST_FISHING_002: Fishing event must carry iuu.fishing_authorization."""
    sample = _load("fishing")
    _assert_valid(FishingEvent, sample)

    bad = copy.deepcopy(sample)
    bad["iuu"].pop("fishing_authorization")
    with pytest.raises(ValidationError):
        FishingEvent(**bad)


def test_fishing_location_required(mgs_mock):
    """GDST_FISHING_003: Fishing event must carry where.catch_area or where.event_read_point."""
    sample = _load("fishing")
    _assert_valid(FishingEvent, sample)

    bad = copy.deepcopy(sample)
    bad["where"] = {"product_origin": "PG"}
    with pytest.raises(ValidationError):
        FishingEvent(**bad)


# --- On-vessel / processing ---------------------------------------------------

def test_on_vessel_production_date_required(mgs_mock):
    """GDST_ONVESSEL_001: OnVesselProcessing requires when.production_date."""
    sample = _load("on_vessel")
    _assert_valid(OnVesselProcessingEvent, sample)

    bad = copy.deepcopy(sample)
    bad["when"].pop("production_date")
    evt = OnVesselProcessingEvent(**bad)
    assert gdst_min_rules(evt.model_dump(mode="json")) is False


def test_processing_production_date_required(mgs_mock):
    """GDST_PROCESSING_001: Processing requires when.production_date."""
    sample = _load("processing")
    _assert_valid(ProcessingEvent, sample)

    bad = copy.deepcopy(sample)
    bad["when"].pop("production_date")
    evt = ProcessingEvent(**bad)
    assert gdst_min_rules(evt.model_dump(mode="json")) is False


# --- Transshipment ------------------------------------------------------------

def test_transshipment_vessel_identification(mgs_mock):
    """GDST_TRANSSHIP_001: Transshipment requires transshipment_vessel.vessel_id or .vessel_name."""
    sample = _load("transshipment")
    _assert_valid(TransshipmentEvent, sample)

    bad = copy.deepcopy(sample)
    bad["transshipment_vessel"] = {"vessel_registration": "REG-ONLY"}
    evt = TransshipmentEvent(**bad)
    assert gdst_min_rules(evt.model_dump(mode="json")) is False


def test_transshipment_authorization_required(mgs_mock):
    """GDST_TRANSSHIP_002: Transshipment requires iuu.transshipment_authorization."""
    sample = _load("transshipment")
    _assert_valid(TransshipmentEvent, sample)

    bad = copy.deepcopy(sample)
    bad["iuu"].pop("transshipment_authorization")
    with pytest.raises(ValidationError):
        TransshipmentEvent(**bad)


# --- Landing ------------------------------------------------------------------

def test_landing_authorization_required(mgs_mock):
    """GDST_LANDING_001: Landing requires iuu.landing_authorization."""
    sample = _load("landing")
    _assert_valid(LandingEvent, sample)

    bad = copy.deepcopy(sample)
    bad["iuu"].pop("landing_authorization")
    with pytest.raises(ValidationError):
        LandingEvent(**bad)


# --- Shipping -----------------------------------------------------------------

def test_shipping_endpoints_required(mgs_mock):
    """GDST_SHIPPING_001: Shipping requires a source OR destination location."""
    sample = _load("shipping")
    _assert_valid(ShippingReceivingEvent, sample)

    bad = copy.deepcopy(sample)
    bad["where"] = {}
    evt = ShippingReceivingEvent(**bad)
    assert gdst_min_rules(evt.model_dump(mode="json")) is False


def test_shipping_linking_kde_required(mgs_mock):
    """GDST_SHIPPING_002: Shipping requires what.linking_kde."""
    sample = _load("shipping")
    _assert_valid(ShippingReceivingEvent, sample)

    bad = copy.deepcopy(sample)
    bad["what"].pop("linking_kde")
    evt = ShippingReceivingEvent(**bad)
    assert gdst_min_rules(evt.model_dump(mode="json")) is False


# --- Aggregation --------------------------------------------------------------

def test_aggregation_non_empty(mgs_mock):
    """GDST_AGGREGATION_001: Aggregation requires parent_items or child_items non-empty."""
    sample = _load("aggregation")
    _assert_valid(AggregationEvent, sample)

    bad = copy.deepcopy(sample)
    bad["parent_items"] = []
    bad["child_items"] = []
    evt = AggregationEvent(**bad)
    assert gdst_min_rules(evt.model_dump(mode="json")) is False
