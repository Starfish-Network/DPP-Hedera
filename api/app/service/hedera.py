import json
from fastapi import HTTPException
from hiero_sdk_python import TopicId, TopicMessageSubmitTransaction
from app.core.client import get_client
from app.core.config import settings
from hiero_sdk_python.contract.contract_execute_transaction import (
    ContractExecuteTransaction
)
from hiero_sdk_python.contract.contract_id import ContractId
from hiero_sdk_python import (
    ContractFunctionParameters,
    ResponseCode
)

def hedera_post_transaction(encrypted_payload: dict) -> dict:
    """Posts an encrypted payload to Hedera and returns transaction details."""
    client, op_key = get_client()
    tx = (
        TopicMessageSubmitTransaction(topic_id=TopicId.from_string(settings.TOPIC_ID), message=json.dumps(encrypted_payload, separators=(",", ":"), sort_keys=True))
        .freeze_with(client)
        .sign(op_key)
    )
    receipt = tx.execute(client)
    tx_id = str(tx.transaction_id)
    
    return {
        "transactionId": tx_id,
        "receiptStatus": str(receipt.status),
    }

def hedera_contract_check_event(event_hash: bytes, is_compliant: bool, event_type: str, client, contract_id) -> ContractExecuteTransaction:
    params = (
        ContractFunctionParameters()
        .add_bytes32(event_hash)   
        .add_string(event_type)    
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
    
    return tx