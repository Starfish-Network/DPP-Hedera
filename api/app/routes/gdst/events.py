import base64
import datetime
from fastapi import APIRouter, HTTPException
from app.helpers.compliance import sha256_bytes32
from app.service.hedera import hedera_post_transaction
from app.core.kms import get_kms
from app.crypto.encryption import envelope_encrypt
from app.models.gdst.base import GDSTEvent

router = APIRouter(prefix="/events", tags=["Events"])

@router.post("", summary="Receive GDST event → encrypt → write to Hedera")
def create_gdst_event(evt: GDSTEvent):
    """Accepts any GDST event and writes it immutably to Hedera, following the same logic as EPCIS events."""
    source = "starfish"
    event_dict = evt.model_dump(mode="json")
    enc_meta, data_key = envelope_encrypt(event_dict)
    kms = get_kms()
    wrapped_dk = kms.wrap_data_key(data_key)

    encrypted_payload = {
        "eventType": event_dict["gdst_event_type"],
        "ts": int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
        "source": source,
        "enc": {
            **enc_meta,
            "encrypted_data_key_b64": base64.b64encode(wrapped_dk).decode(),
        },
    }

    try:
        result = hedera_post_transaction(encrypted_payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hedera write failed: {e}")
    
    event_hash = sha256_bytes32(event_dict)

    return {
        "status": "ok",
        "transactionId": result["transactionId"],
        "receiptStatus": result["receiptStatus"],
        "eventType": event_dict["gdst_event_type"],
        "eventHash": event_hash.hex(),
        "source": source,
    }