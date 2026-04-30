import io
import json
import os
from pathlib import Path

import pytest
import requests

pytestmark = pytest.mark.integration

BASE_URL = os.getenv("TEST_URL", "http://hedera-integration-service:8000/api/v1")

# Use the canonical Landing sample. The previous inline FSMA-shaped fixture
# (`event_time` + `facility` + `input_items` + `gdst_event_type`) failed
# Pydantic 422 against the current GDSTEvent base — `who`/`what`/`where`/`when`
# are required. Loading the same JSON the tests/integration/guardian/ suite
# uses keeps the two test layers in lockstep.
_REPO_ROOT = Path(__file__).resolve().parents[4]
with (_REPO_ROOT / "samples" / "gdst" / "landing.json").open() as _f:
    LANDING_EVENT = json.load(_f)


def _post_event() -> dict:
    """Submit a Landing event through /gdst/events. Returns the response JSON
    (used to seed event-hash-based tests below)."""
    resp = requests.post(f"{BASE_URL}/gdst/events", json=LANDING_EVENT)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_gdst_event_happy_path():
    """POST /gdst/events with a valid Landing event → HCS write + ok response."""
    data = _post_event()
    assert data["status"] == "ok"
    assert data["eventType"] == "Landing"
    assert "transactionId" in data
    assert "eventHash" in data
    # G1 fix from /speckit-analyze: response now carries isCompliant + guardian envelope.
    assert "isCompliant" in data
    assert "guardian" in data


def test_gdst_compliance_check():
    """POST /gdst/compliance/check → validates + records compliance on-chain."""
    resp = requests.post(f"{BASE_URL}/gdst/compliance/check", json=LANDING_EVENT)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ok"
    assert "isCompliant" in data
    assert "txStatus" in data
    assert "contractId" in data
    assert "eventHashHex" in data


def test_gdst_compliance_status():
    """GET /gdst/compliance/status/{event_hash} → fetches compliance status."""
    check_resp = requests.post(f"{BASE_URL}/gdst/compliance/check", json=LANDING_EVENT)
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
    """Attach a file, list CIDs, download + decrypt round-trip."""
    check_resp = requests.post(f"{BASE_URL}/gdst/compliance/check", json=LANDING_EVENT)
    assert check_resp.status_code == 200, check_resp.text
    event_hash = check_resp.json()["eventHashHex"].replace("0x", "")

    file_content = b"test file content"
    files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
    attach_resp = requests.post(
        f"{BASE_URL}/gdst/events/{event_hash}/attach", files=files
    )
    assert attach_resp.status_code == 200, attach_resp.text
    attach_data = attach_resp.json()
    assert attach_data["status"] == "ok"
    assert "fileCid" in attach_data
    file_cid = attach_data["fileCid"]

    files_resp = requests.get(f"{BASE_URL}/gdst/events/{event_hash}/files")
    assert files_resp.status_code == 200, files_resp.text
    files_data = files_resp.json()
    assert file_cid in files_data["fileCids"]

    download_resp = requests.get(
        f"{BASE_URL}/gdst/events/{event_hash}/files/{file_cid}/download"
    )
    assert download_resp.status_code == 200, download_resp.text
    assert download_resp.content == file_content
