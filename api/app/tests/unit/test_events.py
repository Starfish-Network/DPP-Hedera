def test_post_shipping_event(client):
    """Test Starfish shipping event encryption + ledger write flow (mocked Hedera)."""

    payload = {
        "eventType": "shipping",
        "ship_from": "9506001112229",
        "ship_to": "9506001112229",
        "event_time": "2025-10-03T12:08:00.000Z",
        "event_timezone_offset": "+01:00",
        "items": [{
            "epc": "urn:epc:class:lgtin:9506000.1233.a",
            "quantity": 12.0,
            "unit_of_measurement": "kg"
        }]
    }

    response = client.post("/api/v1/epcis/events", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["eventType"] == "shipping"
    assert data["source"] == "starfish"
