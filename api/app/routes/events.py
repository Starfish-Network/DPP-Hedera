"""Generic-event route: minimum validation, HCS write, Guardian forward.

For operators that don't follow GDST 1.2 or FSMA 204. Pydantic enforces a
non-empty `event_type`; everything else passes through verbatim. Compliance
is always `True` — generic events have no rule predicate the API can
enforce. Operators that need compliance gating should run their own check
upstream and only post events they consider compliant.
"""
from __future__ import annotations

import base64
import datetime

from fastapi import APIRouter, HTTPException

from app.core.kms import get_kms
from app.crypto.encryption import envelope_encrypt
from app.helpers.compliance import sha256_bytes32
from app.models.generic_event import GenericEvent
from app.service.guardian_forwarder import (
    forward_event_to_guardian,
    maybe_get_guardian_client,
)
from app.service.guardian_policies import GENERIC
from app.service.hedera import hedera_post_transaction

router = APIRouter(prefix="/events", tags=["Events"])


@router.post("", summary="Receive a generic event -> encrypt -> write to Hedera -> submit to Guardian")
async def create_generic_event(evt: GenericEvent):
    event_dict = evt.model_dump(mode="json")
    enc_meta, data_key = envelope_encrypt(event_dict)
    wrapped_dk = get_kms().wrap_data_key(data_key)

    encrypted_payload = {
        "event_type": event_dict["event_type"],
        "ts": int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
        "source": "generic",
        "enc": {
            **enc_meta,
            "encrypted_data_key_b64": base64.b64encode(wrapped_dk).decode(),
        },
    }
    try:
        result = hedera_post_transaction(encrypted_payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hedera write failed: {e}")

    event_hash_hex = "0x" + sha256_bytes32(event_dict).hex()

    guardian_submission: dict = {"status": "skipped", "reason": "not_configured"}
    client = maybe_get_guardian_client(GENERIC)
    if client is not None:
        guardian_submission = await forward_event_to_guardian(
            client, GENERIC, event_dict, event_hash_hex
        )

    return {
        "status": "ok",
        "transactionId": result["transactionId"],
        "receiptStatus": result["receiptStatus"],
        "eventType": event_dict["event_type"],
        "eventHash": event_hash_hex,
        "isCompliant": True,
        "source": "generic",
        "guardian": guardian_submission,
    }
