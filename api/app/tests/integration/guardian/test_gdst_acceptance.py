"""
Acceptance tests for GDST compliance rules.

Every rule in specs/001-guardian-integration/data-model.md §Rule Source Table
(GDST section) MUST have a test here. Test names match the "Acceptance test"
column in that table.

Implementation lands under /speckit-implement; tests are skipped until then.
"""
import pytest


# --- Common rules (apply to all CTE types) -------------------------------------

def test_common_event_datetime_required(mgs_mock):
    """GDST_COMMON_001: when.event_datetime must be present."""
    pytest.skip("awaiting /speckit-implement")


def test_common_species_format(mgs_mock):
    """GDST_COMMON_002: what.species must match ^[A-Z]{3}$."""
    pytest.skip("awaiting /speckit-implement")


def test_common_quantity_positive(mgs_mock):
    """GDST_COMMON_003: what.quantity must be > 0."""
    pytest.skip("awaiting /speckit-implement")


def test_common_uom_enum(mgs_mock):
    """GDST_COMMON_004: what.unit_of_measure must be in {KGM, TNE, LBR, EA}."""
    pytest.skip("awaiting /speckit-implement")


# --- Fishing -------------------------------------------------------------------

def test_fishing_vessel_identification(mgs_mock):
    """GDST_FISHING_001: Fishing event must carry vessel.vessel_id or vessel.vessel_name."""
    pytest.skip("awaiting /speckit-implement")


def test_fishing_authorization_required(mgs_mock):
    """GDST_FISHING_002: Fishing event must carry iuu.fishing_authorization."""
    pytest.skip("awaiting /speckit-implement")


def test_fishing_location_required(mgs_mock):
    """GDST_FISHING_003: Fishing event must carry where.catch_area or where.event_read_point."""
    pytest.skip("awaiting /speckit-implement")


# --- On-vessel / processing ---------------------------------------------------

def test_on_vessel_production_date_required(mgs_mock):
    """GDST_ONVESSEL_001: OnVesselProcessing requires when.production_date."""
    pytest.skip("awaiting /speckit-implement")


def test_processing_production_date_required(mgs_mock):
    """GDST_PROCESSING_001: Processing requires when.production_date."""
    pytest.skip("awaiting /speckit-implement")


# --- Transshipment ------------------------------------------------------------

def test_transshipment_vessel_identification(mgs_mock):
    """GDST_TRANSSHIP_001: Transshipment requires transshipment_vessel.vessel_id or .vessel_name."""
    pytest.skip("awaiting /speckit-implement")


def test_transshipment_authorization_required(mgs_mock):
    """GDST_TRANSSHIP_002: Transshipment requires iuu.transshipment_authorization."""
    pytest.skip("awaiting /speckit-implement")


# --- Landing ------------------------------------------------------------------

def test_landing_authorization_required(mgs_mock):
    """GDST_LANDING_001: Landing requires iuu.landing_authorization."""
    pytest.skip("awaiting /speckit-implement")


# --- Shipping -----------------------------------------------------------------

def test_shipping_endpoints_required(mgs_mock):
    """GDST_SHIPPING_001: Shipping requires a source OR destination location."""
    pytest.skip("awaiting /speckit-implement")


def test_shipping_linking_kde_required(mgs_mock):
    """GDST_SHIPPING_002: Shipping requires what.linking_kde."""
    pytest.skip("awaiting /speckit-implement")


# --- Aggregation --------------------------------------------------------------

def test_aggregation_non_empty(mgs_mock):
    """GDST_AGGREGATION_001: Aggregation requires parent_items or child_items non-empty."""
    pytest.skip("awaiting /speckit-implement")
