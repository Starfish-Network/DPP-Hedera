import json
from fastapi import HTTPException
from hiero_sdk_python import TopicId, TopicMessageSubmitTransaction
from api.app.core.client import get_client
from app.core.config import settings

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