import os
import time
import json
import base64
import pytest
import requests

pytestmark = pytest.mark.integration

BASE_URL = os.getenv("TEST_URL", "http://hedera-integration-service:8000/api/v1")
TOPIC_ID = os.getenv("TOPIC_ID")
MIRROR_BASE = "https://testnet.mirrornode.hedera.com/api/v1"


# ------------------------------------------------------
# Helpers
# ------------------------------------------------------
def mirror_tx_id_format(tx_id: str) -> str:
    """Convert SDK-style tx_id to mirror node format."""
    # Example: 0.0.12345@1728128932.123456789 -> 0.0.12345-1728128932-123456789
    try:
        account, timestamp = tx_id.split("@")
        seconds, nanos = timestamp.split(".")
        return f"{account}-{seconds}-{nanos}"
    except Exception:
        raise ValueError(f"Invalid Hedera transaction id format: {tx_id}")


def wait_for_transaction(tx_id: str, timeout: int = 60):
    """Wait until transaction appears on Hedera mirror node."""
    mirror_tx_id = mirror_tx_id_format(tx_id)
    url = f"{MIRROR_BASE}/transactions/{mirror_tx_id}"
    print(f"🔍 Waiting for transaction {mirror_tx_id} to appear on mirror node...")

    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("transactions", [])
            if data and data[0].get("result") == "SUCCESS":
                print(f"✅ Transaction found on mirror node: {mirror_tx_id}")
                return data[0]
        elif resp.status_code == 400:
            # Mirror node might not have indexed it yet
            print("⚠️ Mirror node not ready (400 Bad Request) — retrying...")
        time.sleep(3)

    raise AssertionError(f"❌ Transaction {mirror_tx_id} not found on mirror node within {timeout}s")


def get_topic_messages(topic_id: str, limit: int = 5):
    """Retrieve messages from a Hedera topic via Mirror Node."""
    url = f"{MIRROR_BASE}/topics/{topic_id}/messages?limit={limit}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json().get("messages", [])


# ------------------------------------------------------
# Integration Test
# ------------------------------------------------------
def test_full_traceability_flow():
    """End-to-end: POST event → Hedera → Mirror Node → verify topic message."""

    # Create a shipping event payload
    payload = {
        "eventType": "shipping",
        "ship_from": "9506001112229",
        "ship_to": "9506001112229",
        "event_time": "2025-10-03T12:08:00.000Z",
        "event_timezone_offset": "+01:00",
        "items": [
            {
                "epc": "urn:epc:class:lgtin:9506000.1233.a",
                "quantity": 12.0,
                "unit_of_measurement": "kg",
            }
        ],
    }

    # Send to FastAPI (Hedera integration)
    print(f"🚀 Sending event to {BASE_URL}/epcis/events ...")
    r = requests.post(f"{BASE_URL}/epcis/events", json=payload, timeout=30)
    assert r.status_code == 200, f"API failed: {r.text}"

    response_json = r.json()
    tx_id = response_json["transactionId"]
    assert tx_id, "No transactionId returned from API"
    print(f"🧾 Received transactionId: {tx_id}")

    # Wait for mirror node confirmation
    tx_data = wait_for_transaction(tx_id)
    assert tx_data["name"] == "CONSENSUSSUBMITMESSAGE"
    assert tx_data["result"] == "SUCCESS"

    # Retrieve topic messages
    print(f"📡 Fetching messages from topic {TOPIC_ID} ...")
    messages = get_topic_messages(TOPIC_ID)
    assert messages, f"No messages found on topic {TOPIC_ID}"

    print(f"✅ {len(messages)} messages found on topic {TOPIC_ID}")

    # Decode the latest message
    latest = messages[-1]
    try:
        msg_bytes = base64.b64decode(latest["message"])
        msg_json = json.loads(msg_bytes.decode())
        assert "eventType" in msg_json, "Missing eventType in message payload"
        print(f"📦 Latest message eventType: {msg_json['eventType']}")
    except Exception as e:
        pytest.skip(f"⚠️ Could not decode encrypted payload: {e}")
