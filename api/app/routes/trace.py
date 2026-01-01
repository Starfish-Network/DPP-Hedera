from app.models.contract import ComplianceEvent
from app.models.gdst.base import GDSTEvent
from app.helpers.compliance import sha256_bytes32
from fastapi import APIRouter, HTTPException
from app.core.config import settings
from app.core.kms import get_kms
from app.crypto.encryption import aes_gcm_decrypt
import base64
import json
import requests
from collections import defaultdict
from app.helpers.trace import build_edge_list, normalize_epc, traverse

router = APIRouter(prefix="/trace", tags=["Traceability"])

@router.get("/{product_id}", summary="Retrieve full upstream/downstream trace graph for a product")
def get_trace_graph(product_id: str):
    """
    Retrieves the full traceability graph for a product (upstream + downstream).
    Builds a directed graph of EPC transformations from decrypted Hedera events.
    Output format mirrors Starfish trace structure.
    """
    topic_id = settings.TOPIC_ID
    url = f"{settings.MIRROR_BASE}/topics/{topic_id}/messages?limit=1000&order=asc"

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mirror node fetch failed: {e}")

    messages = resp.json().get("messages", [])
    if not messages:
        raise HTTPException(status_code=404, detail="No messages found on this topic")

    kms = get_kms()

    # Graph structure
    graph = defaultdict(lambda: {"inputs": set(), "outputs": set(), "events": []})

    # Decrypt and parse all events (Compliance and GDST)
    for msg in messages:
        try:
            enc_payload = json.loads(base64.b64decode(msg["message"]).decode())
            enc_block = enc_payload.get("enc", {})
            if not enc_block:
                continue

            wrapped_dk = base64.b64decode(enc_block["encrypted_data_key_b64"])
            data_key = kms.unwrap_data_key(wrapped_dk)

            nonce = base64.b64decode(enc_block["nonce_b64"])
            aad = base64.b64decode(enc_block["aad_b64"])
            ciphertext = base64.b64decode(enc_block["ciphertext_b64"])
            plaintext = aes_gcm_decrypt(ciphertext, data_key, nonce, aad)
            evt = json.loads(plaintext)

            event_type = evt.get("eventType") or evt.get("gdst_event_type")
            if event_type:
                try:
                    if "gdst_event_type" in evt:
                        evt_model = GDSTEvent.parse_obj(evt)
                        event_hash = sha256_bytes32(evt_model.model_dump(mode="json"))
                        evt["event_hash"] = event_hash.hex()
                        evt["consensus_timestamp"] = msg["consensus_timestamp"]

                        # For GDST AggregationDisaggregation, build parent-child relationships like transforming
                        if evt.get("gdst_event_type") == "AggregationDisaggregation":
                            parent_items = evt.get("parent_items", [])
                            child_items = evt.get("child_items", [])
                            for parent in parent_items or []:
                                for child in child_items or []:
                                    parent_norm = normalize_epc(parent)
                                    child_norm = normalize_epc(child)
                                    graph[parent_norm]["outputs"].add(child_norm)
                                    graph[child_norm]["inputs"].add(parent_norm)
                                    graph[parent_norm]["events"].append(evt)
                                    graph[child_norm]["events"].append(evt)
                        else:
                            # For other GDST events, just link EPC to event
                            epc = evt.get("what", {}).get("linking_kde")
                            if epc:
                                epc = normalize_epc(epc)
                                graph[epc]["events"].append(evt)
                    else:
                        evt_model = ComplianceEvent.parse_obj(evt)
                        event_hash = sha256_bytes32(evt_model.model_dump())
                        evt["event_hash"] = event_hash.hex()
                        evt["consensus_timestamp"] = msg["consensus_timestamp"]

                        # Build relationships for transforming events
                        if evt.get("eventType") == "transforming":
                            inputs = [i["epc"] for i in evt.get("input_items", []) if i.get("epc")]
                            outputs = [output_epc["epc"] for output_epc in evt.get("output_items", []) if output_epc.get("epc")]
                            for i in inputs:
                                for output_epc in outputs:
                                    graph[i]["outputs"].add(output_epc)
                                    graph[output_epc]["inputs"].add(i)
                                    graph[i]["events"].append(evt)
                                    graph[output_epc]["events"].append(evt)
                        else:
                            # For non-transform events, link EPCs to their events
                            for item in (
                                evt.get("items", [])
                                or evt.get("input_items", [])
                                or evt.get("output_items", [])
                                or evt.get("quantity_list", [])
                                or []
                            ):
                                epc = normalize_epc(item.get("epc"))
                                if epc:
                                    graph[epc]["events"].append(evt)
                except Exception as e:
                    print(f"Error parsing event: {e}")
                    continue
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # Log the error for debugging purposes
            print(f"Error processing message: {e}")
            continue

    upstream_nodes = traverse(graph, product_id, "upstream")
    downstream_nodes = traverse(graph, product_id, "downstream")

    response = {
        "total_count": None,
        "next_page_encoded": None,
        "upstream_result": {
            "edge_list_dict": build_edge_list(graph, upstream_nodes),
            "root_node_ids": [product_id],
        },
        "downstream_result": {
            "edge_list_dict": build_edge_list(graph, downstream_nodes),
            "root_node_ids": [product_id],
        },
        "events": graph[product_id]["events"],
    }

    return response
