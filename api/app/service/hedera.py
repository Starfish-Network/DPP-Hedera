import json
from fastapi import HTTPException
from hiero_sdk_python import ContractCallQuery, TopicId, TopicMessageSubmitTransaction
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

client, op_key = get_client()

def hedera_post_transaction(encrypted_payload: dict) -> dict:
    """Posts an encrypted payload to Hedera and returns transaction details."""
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

def hedera_contract_check_event(event_hash: bytes, is_compliant: bool, event_type: str, contract_id) -> ContractExecuteTransaction:
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

def hedera_contract_get_files(event_hash_hex: str, contract_id) -> list:
    params = (
            ContractFunctionParameters()
            .add_bytes32(bytes.fromhex(event_hash_hex.removeprefix("0x")))
        )
    tx = (
        ContractCallQuery()
        .set_contract_id(contract_id)
        .set_gas(200000)
        .set_function("getFiles", params)
        .execute(client)
    )

    return tx.get_result(["string[]"])[0]

def hedera_contract_attach_file(event_hash_hex: str, cid: str, data_key: bytes, contract_id) -> ContractExecuteTransaction:
    params = (
        ContractFunctionParameters()
        .add_bytes32(bytes.fromhex(event_hash_hex))
        .add_string(cid)
        .add_bytes32(data_key)
    )
        
    tx = (
        ContractExecuteTransaction()
        .set_contract_id(contract_id)
        .set_gas(200000)
        .set_function("attachFile", params)
        .freeze_with(client)
        .sign(op_key)
    )

    return str(tx.transaction_id)

def hedera_contract_get_data_key(cid: str, contract_id) -> bytes:
    params = (
        ContractFunctionParameters()
        .add_string(cid)
    )
    tx = (
        ContractCallQuery()
        .set_contract_id(contract_id)
        .set_gas(200000)
        .set_function("getDataKey", params)
        .execute(client)
    )
    return tx.get_result(["bytes32"])[0]
