import json
import hashlib
from typing import Dict, Any, Iterable

def fsma_min_rules(evt: Dict[str, Any]) -> bool:
    """
    VERY simple sample checks — adapt to your real FSMA/DPP rules.
    """
    et = evt.get("eventType", "").lower()

    # Common required field
    if not evt.get("event_time"):
        return False

    if et == "creating":
        return bool(evt.get("biz_location") and evt.get("quantity_list"))

    if et == "shipping":
        return bool(evt.get("shipFrom") and evt.get("shipTo") and evt.get("items"))

    if et == "receiving":
        # Starfish sometimes uses shippedFrom/receivedAt
        return bool((evt.get("receivedAt") or evt.get("shipTo")) and evt.get("items"))

    if et == "transforming":
        return bool(evt.get("facility") and evt.get("input_items") and evt.get("output_items"))

    if et == "packing":
        return bool(evt.get("facility") and evt.get("container_id") and evt.get("input_items"))

    if et == "unpacking":
        return bool(evt.get("facility") and evt.get("container_id") and evt.get("output_items"))

    return False

def _present(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return v.strip() != ""
    if isinstance(v, dict):
        return len(v) > 0
    if isinstance(v, Iterable):
        return len(v) > 0
    return True

def gdst_min_rules(evt: Dict[str, Any]) -> bool:
    """
    Minimum viability checks for GDST CTE events.
    Returns True if the event meets minimum KDE expectations.
    """

    et = (evt.get("gdst_event_type") or "").lower()

    what = evt.get("what") or {}
    where = evt.get("where") or {}
    when = evt.get("when") or {}
    iuu = evt.get("iuu") or {}

    # ---------- Common required fields ----------
    if not _present(when.get("event_datetime")):
        return False

    if not _present(what.get("species")):
        return False

    if not _present(what.get("quantity")):
        return False

    if not _present(what.get("unit_of_measure")):
        return False

    # ---------- Event-specific KDE checks ----------

    # Fishing
    if et == "fishing":
        vessel = evt.get("vessel") or {}

        return all([
            _present(vessel.get("vessel_id")) or _present(vessel.get("vessel_name")),
            _present(iuu.get("fishing_authorization")),
            _present(where.get("catch_area")) or _present(where.get("event_read_point"))
        ])

    # On-vessel processing
    if et == "onvesselprocessing":
        return _present(when.get("production_date"))

    # Transshipment
    if et == "transshipment":
        trans_vessel = evt.get("transshipment_vessel") or {}

        return all([
            _present(trans_vessel.get("vessel_id")) or _present(trans_vessel.get("vessel_name")),
            _present(iuu.get("transshipment_authorization"))
        ])

    # Landing
    if et == "landing":
        return _present(iuu.get("landing_authorization"))

    # Shipping / Receiving
    if et == "shippingreceiving":
        return any([
            _present(where.get("source_location")),
            _present(where.get("destination_location")),
        ]) and _present(what.get("linking_kde"))

    # Processing
    if et == "processing":
        return _present(when.get("production_date"))

    # Aggregation / Disaggregation
    if et == "aggregationdisaggregation":
        return any([
            _present(evt.get("parent_items")),
            _present(evt.get("child_items"))
        ])

    # Unknown event
    return False


def sha256_bytes32(evt: Dict[str, Any]) -> bytes:
    """
    Deterministic hash of the event content (sorted keys, UTF-8, SHA-256).
    Solidity bytes32 expects 32 raw bytes.
    """
    payload = json.dumps(evt, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).digest()  # 32 bytes