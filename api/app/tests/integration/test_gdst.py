import os
import pytest
import requests

pytestmark = pytest.mark.integration

BASE_URL = os.getenv("TEST_URL", "http://hedera-integration-service:8000/api/v1")


def test_gdst_event_happy_path():
    """
    POST /api/gdst/events
    - Should accept a GDST event, encrypt, and write to Hedera
    - Return ok + tx info
    """
    event = {
        "gdst_event_type": "Landing",
        "event_time": "2025-10-03T12:08:00.000Z",
        "facility": "Port of Vigo",
        "input_items": [
            {"epc": "urn:epc:id:sgtin:9506000.1233.400"}
        ]
    }
    resp = requests.post(f"{BASE_URL}/gdst/events", json=event)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ok"
    assert data["eventType"] == "Landing"
    assert "transactionId" in data
    assert "eventHash" in data


def test_gdst_compliance_check():
    """
    POST /api/gdst/compliance/check
    - Should validate and record compliance for a GDST event
    """
    event = {
        "gdst_event_type": "Landing",
        "event_time": "2025-10-03T12:08:00.000Z",
        "facility": "Port of Vigo",
        "input_items": [
            {"epc": "urn:epc:id:sgtin:9506000.1233.400"}
        ]
    }
    resp = requests.post(f"{BASE_URL}/gdst/compliance/check", json=event)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ok"
    assert "isCompliant" in data
    assert "txStatus" in data
    assert "contractId" in data
    assert "eventHashHex" in data


def test_gdst_compliance_status():
    """
    GET /api/gdst/compliance/status/{event_hash}
    - Should fetch compliance status for a GDST event hash
    """
    # First, create and check compliance to get a hash
    event = {
        "gdst_event_type": "Landing",
        "event_time": "2025-10-03T12:08:00.000Z",
        "facility": "Port of Vigo",
        "input_items": [
            {"epc": "urn:epc:id:sgtin:9506000.1233.400"}
        ]
    }
    check_resp = requests.post(f"{BASE_URL}/gdst/compliance/check", json=event)
    assert check_resp.status_code == 200, check_resp.text
    event_hash = check_resp.json()["eventHashHex"].replace("0x", "")
    resp = requests.get(f"{BASE_URL}/gdst/compliance/status/{event_hash}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ok"
    assert "isCompliant" in data
    assert "contractId" in data
    assert "eventHashHex" in data


def test_gdst_event_files_lifecycle():
    """
    POST /api/gdst/events/{event_hash}/attach
    GET /api/gdst/events/{event_hash}/files
    GET /api/gdst/events/{event_hash}/files/{cid}/download
    - Should attach a file, list CIDs, and download/decrypt
    """
    import io
    # Create event and get hash
    event = {
        "gdst_event_type": "Landing",
        "event_time": "2025-10-03T12:08:00.000Z",
        "facility": "Port of Vigo",
        "input_items": [
            {"epc": "urn:epc:id:sgtin:9506000.1233.400"}
        ]
    }
    check_resp = requests.post(f"{BASE_URL}/gdst/compliance/check", json=event)
    assert check_resp.status_code == 200, check_resp.text
    event_hash = check_resp.json()["eventHashHex"].replace("0x", "")
    # Attach file
    file_content = b"test file content"
    files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
    attach_resp = requests.post(f"{BASE_URL}/gdst/events/{event_hash}/attach", files=files)
    assert attach_resp.status_code == 200, attach_resp.text
    attach_data = attach_resp.json()
    assert attach_data["status"] == "ok"
    assert "fileCid" in attach_data
    file_cid = attach_data["fileCid"]
    # List files
    files_resp = requests.get(f"{BASE_URL}/gdst/events/{event_hash}/files")
    assert files_resp.status_code == 200, files_resp.text
    files_data = files_resp.json()
    assert file_cid in files_data["fileCids"]
    # Download file
    download_resp = requests.get(f"{BASE_URL}/gdst/events/{event_hash}/files/{file_cid}/download")
    assert download_resp.status_code == 200, download_resp.text
    assert download_resp.content == file_content
