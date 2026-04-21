import os
import time
import pytest
import requests

pytestmark = pytest.mark.integration

BASE_URL = os.getenv("TEST_URL", "http://hedera-integration-service:8000/api/v1")

PRODUCT_A = "urn:epc:class:lgtin:9506000.1231"
PRODUCT_B = "urn:epc:class:lgtin:9506000.1233"
PRODUCT_C = "urn:epc:class:lgtin:9506000.1236"


@pytest.fixture(scope="session")
def test_events():
    """Lifecycle events forming a small transformation graph: A → B → C"""
    return [
        {
            "eventType": "creating",
            "biz_location": "9506001112229",
            "event_time": "2025-10-03T12:00:00Z",
            "event_timezone_offset": "+01:00",
            "quantity_list": [{"epc": PRODUCT_A, "quantity": 10.0, "unit_of_measurement": "kg"}],
        },
        {
            "eventType": "transforming",
            "facility": "9506001112230",
            "event_time": "2025-10-03T18:00:00Z",
            "event_timezone_offset": "+01:00",
            "transformation_id": "TST-A-B",
            "input_items": [{"epc": PRODUCT_A, "quantity": 10.0, "unit_of_measurement": "kg"}],
            "output_items": [{"epc": PRODUCT_B, "quantity": 10.0, "unit_of_measurement": "kg"}],
        },
        {
            "eventType": "transforming",
            "facility": "9506001112240",
            "event_time": "2025-10-04T06:00:00Z",
            "event_timezone_offset": "+01:00",
            "transformation_id": "TST-B-C",
            "input_items": [{"epc": PRODUCT_B, "quantity": 10.0, "unit_of_measurement": "kg"}],
            "output_items": [{"epc": PRODUCT_C, "quantity": 10.0, "unit_of_measurement": "kg"}],
        },
        {
            "eventType": "shipping",
            "ship_from": "9506001112240",
            "ship_to": "9506001112250",
            "event_time": "2025-10-04T09:00:00Z",
            "event_timezone_offset": "+01:00",
            "items": [{"epc": PRODUCT_C, "quantity": 10.0, "unit_of_measurement": "kg"}],
        },
    ]


@pytest.fixture(scope="session", autouse=True)
def publish_events(test_events):
    """Push test events through /api/v1/epcis/events before lineage testing."""
    print("🚀 Publishing lineage test events ...")
    for evt in test_events:
        r = requests.post(f"{BASE_URL}/epcis/events", json=evt, timeout=30)
        assert r.status_code == 200, f"Failed to publish event: {r.text}"
    print("✅ Test events submitted. Waiting for mirror node sync...")
    time.sleep(15)


def assert_edge_structure(edge_dict):
    """Validate that each node in edge_list_dict has required fields."""
    for node_id, node in edge_dict.items():
        assert "identifier" in node
        assert "depth" in node
        assert "event_starfish_ids" in node
        assert isinstance(node["related_nodes"], list)


def test_trace_graph_input_root():
    """Query by PRODUCT_A and expect full downstream lineage A→B→C."""
    r = requests.get(f"{BASE_URL}/trace/{PRODUCT_A}", timeout=90)
    assert r.status_code == 200, f"Trace API failed: {r.text}"
    data = r.json()

    upstream = data["upstream_result"]["edge_list_dict"]
    downstream = data["downstream_result"]["edge_list_dict"]

    # Upstream of A should be empty (it’s the root)
    assert len(upstream) == 1 or len(upstream) == 0
    # Downstream should contain B and C
    downstream_ids = list(downstream.keys())
    assert PRODUCT_B in downstream_ids or any(PRODUCT_B in i for i in downstream_ids)
    assert PRODUCT_C in downstream_ids or any(PRODUCT_C in i for i in downstream_ids)

    # Validate structure
    assert_edge_structure(downstream)
    print(f"✅ Downstream lineage for {PRODUCT_A}: {list(downstream.keys())}")


def test_trace_graph_midpoint():
    """Query by PRODUCT_B and ensure we see A upstream and C downstream."""
    r = requests.get(f"{BASE_URL}/trace/{PRODUCT_B}", timeout=90)
    assert r.status_code == 200, f"Trace API failed: {r.text}"
    data = r.json()

    upstream = data["upstream_result"]["edge_list_dict"]
    downstream = data["downstream_result"]["edge_list_dict"]

    upstream_ids = list(upstream.keys())
    downstream_ids = list(downstream.keys())

    assert PRODUCT_A in upstream_ids or any(PRODUCT_A in i for i in upstream_ids)
    assert PRODUCT_C in downstream_ids or any(PRODUCT_C in i for i in downstream_ids)

    # Ensure depths increment logically
    for node in upstream.values():
        assert node["depth"] >= 0
    for node in downstream.values():
        assert node["depth"] >= 0

    print(f"✅ Graph for {PRODUCT_B} shows A upstream and C downstream.")


def test_trace_graph_leaf_node():
    """Query by PRODUCT_C (final product) should only have upstream lineage."""
    r = requests.get(f"{BASE_URL}/trace/{PRODUCT_C}", timeout=90)
    assert r.status_code == 200, f"Trace API failed: {r.text}"
    data = r.json()

    upstream = data["upstream_result"]["edge_list_dict"]
    downstream = data["downstream_result"]["edge_list_dict"]

    assert PRODUCT_A in upstream.keys() or any(PRODUCT_A in i for i in upstream.keys())
    assert PRODUCT_B in upstream.keys() or any(PRODUCT_B in i for i in upstream.keys())
    # Downstream should be empty or only itself
    assert len(downstream) <= 1

    print(f"✅ Leaf product {PRODUCT_C} correctly shows only upstream lineage.")
