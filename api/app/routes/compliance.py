from fastapi import APIRouter, HTTPException
from typing import Literal
from app.core.client import get_client
from app.core.config import settings
from app.models.contract import ComplianceEvent
from app.helpers.compliance import fsma_min_rules, sha256_bytes32

from hiero_sdk_python import (
    ContractFunctionParameters,
    ResponseCode
)

from hiero_sdk_python.contract.contract_execute_transaction import (
    ContractExecuteTransaction
)

from hiero_sdk_python.contract.contract_id import ContractId

from hiero_sdk_python.contract.contract_call_query import ContractCallQuery

router = APIRouter(prefix="/compliance", tags=["Compliance"])

EventType = Literal[
    "creating", "shipping", "receiving", "transforming", "packing", "unpacking"
]

@router.post("/check", summary="Validate event and record compliance on-chain")
def check_and_record(event: ComplianceEvent):
    """
    - Runs lightweight compliance checks (server-side)
    - Hashes the event deterministically
    - Calls ComplianceVerifier.recordEvent(bytes32,string,bool)
    """
    evt_dict = event.model_dump()
    is_compliant = fsma_min_rules(evt_dict)

    # Hash as bytes32 for Solidity
    event_hash = sha256_bytes32(evt_dict)

    try:
        client, _op_key = get_client()
        contract_id = ContractId.from_string(settings.COMPLIANCE_CONTRACT_ID)

        params = (
            ContractFunctionParameters()
            .add_bytes32(event_hash)   
            .add_string(evt_dict["eventType"])    
            .add_bool(is_compliant)            
        )

        # State-changing call uses ContractExecuteTransaction
        tx = (
            ContractExecuteTransaction()
            .set_contract_id(contract_id)
            .set_gas(200_000)
            .set_function("recordEvent", params)
            .execute(client)
        )
    
        if tx.status != ResponseCode.SUCCESS:
            raise HTTPException(status_code=500, detail=f"Contract execution failed with status: {ResponseCode(tx.status).name}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Contract call failed: {e}")

    return {
        "status": "ok",
        "isCompliant": is_compliant,
        "txStatus": str(getattr(tx, "status", "UNKNOWN")),
        "contractId": str(contract_id),
        "eventHashHex": "0x" + event_hash.hex(),
    }

@router.get("/status/{event_hash_hex}", summary="Get compliance status for event hash")
def get_compliance_status(event_hash_hex: str):
    """
    Calls ComplianceVerifier.getComplianceStatus(bytes32)
    """
    try:
        client, _op_key = get_client()
        contract_id = ContractId.from_string(settings.COMPLIANCE_CONTRACT_ID)

        event_hash_bytes = bytes.fromhex(event_hash_hex.removeprefix("0x"))

        params = (
            ContractFunctionParameters()
            .add_bytes32(event_hash_bytes)       
        )

        tx = (
            ContractCallQuery()
            .set_contract_id(contract_id)
            .set_gas(2000000)
            .set_function("getComplianceStatus", params)
            .execute(client)
        )

        event_type = tx.get_string(0)

        if event_type == "":
            is_compliant = None  # Event hash not found
        else:
            is_compliant = tx.get_bool(1)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Contract call failed: {e}")

    return {
        "status": "ok",
        "isCompliant": is_compliant,
        "contractId": str(contract_id),
        "eventHashHex": event_hash_hex,
    }
