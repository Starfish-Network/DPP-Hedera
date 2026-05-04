from fastapi import APIRouter, HTTPException
from app.service.hedera import hedera_contract_check_event, hedera_contract_get_compliance_status
from app.core.config import settings
from app.models.contract import ComplianceEvent
from app.helpers.compliance import fsma_min_rules, sha256_bytes32
from app.service.guardian_forwarder import (
    forward_event_to_guardian,
    maybe_get_guardian_client,
)
from app.service.guardian_policies import FSMA
from hiero_sdk_python.contract.contract_id import ContractId

router = APIRouter(prefix="/compliance", tags=["Compliance"])


@router.post("/check", summary="Validate event, record compliance on-chain, and forward to Guardian")
async def check_and_record(event: ComplianceEvent):
    """
    - Runs lightweight compliance checks (server-side)
    - Hashes the event deterministically
    - Calls ComplianceVerifier.recordEvent(bytes32,string,bool)
    - Forwards compliant events to the FSMA Guardian policy (non-blocking)
    """
    evt_dict = event.model_dump()
    is_compliant = fsma_min_rules(evt_dict)

    event_hash = sha256_bytes32(evt_dict)
    event_hash_hex = "0x" + event_hash.hex()

    contract_id = ContractId.from_string(settings.COMPLIANCE_CONTRACT_ID)

    try:
        tx = hedera_contract_check_event(event_hash, is_compliant, evt_dict["eventType"], contract_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Contract call failed: {e}")

    # Guardian forwarding (non-blocking, FR-004 compliance-only)
    guardian_submission: dict = {"status": "skipped", "reason": "not_configured"}
    if not is_compliant:
        guardian_submission = {"status": "skipped", "reason": "not_compliant"}
    else:
        client = maybe_get_guardian_client(FSMA)
        if client is not None:
            guardian_submission = await forward_event_to_guardian(
                client, FSMA, evt_dict, event_hash_hex
            )

    return {
        "status": "ok",
        "transactionId": tx["transactionId"],
        "receiptStatus": tx["receiptStatus"],
        "eventType": evt_dict["eventType"],
        "eventHash": event_hash_hex,
        "isCompliant": is_compliant,
        "source": "starfish",
        "guardian": guardian_submission,
        # Legacy fields — drop after [test_compliance + status route migrate to
        # `eventHash`/`receiptStatus`]. Kept now to avoid breaking
        # `test_compliance_check_happy_path` and `compliance/status/{hash}`.
        "txStatus": tx["receiptStatus"],
        "contractId": str(contract_id),
        "eventHashHex": event_hash_hex,
    }


@router.get("/status/{event_hash_hex}", summary="Get compliance status for event hash")
def get_compliance_status(event_hash_hex: str):
    """Calls ComplianceVerifier.getComplianceStatus(bytes32)."""
    try:
        contract_id = ContractId.from_string(settings.COMPLIANCE_CONTRACT_ID)
        is_compliant = hedera_contract_get_compliance_status(event_hash_hex, contract_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Contract call failed: {e}")

    return {
        "status": "ok",
        "isCompliant": is_compliant,
        "contractId": str(contract_id),
        "eventHashHex": event_hash_hex,
    }
