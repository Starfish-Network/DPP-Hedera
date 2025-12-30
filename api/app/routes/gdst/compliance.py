from typing import Union
from fastapi import APIRouter, HTTPException
from app.service.hedera import hedera_contract_check_event
from app.core.client import get_client
from app.helpers.compliance import gdst_min_rules, sha256_bytes32
from app.models.gdst.aggregation import AggregationEvent
from app.models.gdst.fishing import FishingEvent
from app.models.gdst.landing import LandingEvent
from app.models.gdst.on_vessel import OnVesselProcessingEvent
from app.models.gdst.processing import ProcessingEvent
from app.models.gdst.transshipment import TransshipmentEvent
from app.models.starfish_events import ShippingEvent
from hiero_sdk_python.contract.contract_id import ContractId
from app.core.config import settings

router = APIRouter(prefix="/compliance", tags=["Compliance"])

@router.post("/check", summary="Validate event and record compliance on-chain")
def check_and_record(event: Union[AggregationEvent, FishingEvent, LandingEvent, OnVesselProcessingEvent, TransshipmentEvent, ProcessingEvent, ShippingEvent]):
    """
    - Runs lightweight compliance checks (server-side)
    - Hashes the event deterministically
    - Calls ComplianceVerifier.recordEvent(bytes32,string,bool)
    """
    evt_dict = event.model_dump(mode="json")
    is_compliant = gdst_min_rules(evt_dict)

    # Hash as bytes32 for Solidity
    event_hash = sha256_bytes32(evt_dict)

    client, _op_key = get_client()
    contract_id = ContractId.from_string(settings.GDST_CONTRACT_ID)

    try:
        tx = hedera_contract_check_event(event_hash, is_compliant, evt_dict["gdst_event_type"], client, contract_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Contract call failed: {e}")

    return {
        "status": "ok",
        "isCompliant": is_compliant,
        "txStatus": str(getattr(tx, "status", "UNKNOWN")),
        "contractId": str(contract_id),
        "eventHashHex": "0x" + event_hash.hex(),
    }