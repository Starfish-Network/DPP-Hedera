import json
import hashlib
from typing import Dict, Any

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


def sha256_bytes32(evt: Dict[str, Any]) -> bytes:
    """
    Deterministic hash of the event content (sorted keys, UTF-8, SHA-256).
    Solidity bytes32 expects 32 raw bytes.
    """
    payload = json.dumps(evt, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).digest()  # 32 bytes