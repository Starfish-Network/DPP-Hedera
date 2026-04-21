import hashlib
import json
import os
import pytest
import requests

pytestmark = pytest.mark.integration

BASE_URL = os.getenv("TEST_URL", "http://hedera-integration-service:8000/api/v1")


def test_compliance_check_happy_path():
    """
    POST /api/v1/epcis/compliance/check
    - Should compute hash
    - Run minimal FSMA rules (this sample passes)
    - Call mocked contract
    - Return ok + txStatus SUCCESS
    """
    # Minimal Shipping event that passes fsma_min_rules
    event = {
        "eventType": "shipping",
        "event_time": "2025-10-03T12:08:00.000Z",
        "shipFrom": "9506001112229",
        "shipTo": "9506001112230",
        "items": [{"epc": "urn:epc:class:lgtin:9506000.1233.a", "quantity": 12.0, "unit_of_measurement": "kg"}],
    }

    resp = requests.post(f"{BASE_URL}/epcis/compliance/check", json=event)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["status"] == "ok"
    # fsma_min_rules should evaluate to True for this payload
    assert data["isCompliant"] is True
    assert data["txStatus"] == "22"
    assert data["contractId"] == os.getenv("COMPLIANCE_CONTRACT_ID")
