import base64
import datetime
import json
import logging
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from app.service.ipfs import download_from_ipfs, upload_to_ipfs
from app.core.client import get_client
from app.helpers.compliance import sha256_bytes32
from app.service.hedera import hedera_contract_attach_file, hedera_contract_get_data_key, hedera_contract_get_files, hedera_post_transaction
from app.core.kms import get_kms
from app.crypto.encryption import envelope_encrypt, file_envelope_decrypt, file_envelope_encrypt
from app.models.gdst.base import GDSTEvent
from app.core.config import settings
from app.routes.guardian.identity import get_guardian_client
from app.service.guardian_client import (
    GuardianBreakerOpen,
    GuardianClient,
    GuardianError,
)
from app.service.guardian_policies import GDST
from app.service.schema_mapper import to_credential_subject
from hiero_sdk_python.contract.contract_id import ContractId

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["Events"])


def _maybe_get_guardian_client() -> GuardianClient | None:
    """Return the client if Guardian is configured, else None.

    Keeps the /events hot path working when Guardian is disabled or partially
    configured — events still land on HCS (Constitution §IV).
    """
    if not (
        settings.GUARDIAN_API_URL
        and settings.GUARDIAN_SR_USERNAME
        and settings.GUARDIAN_SR_PASSWORD
        and GDST.enabled
    ):
        return None
    try:
        return get_guardian_client()
    except HTTPException:
        return None


@router.post("", summary="Receive GDST event -> encrypt -> write to Hedera -> submit to Guardian")
async def create_gdst_event(evt: GDSTEvent):
    """Accepts any GDST event, writes it immutably to Hedera (HCS), then
    forwards the compliance payload to Guardian (non-blocking).
    """
    source = "starfish"
    event_dict = evt.model_dump(mode="json")
    enc_meta, data_key = envelope_encrypt(event_dict)
    kms = get_kms()
    wrapped_dk = kms.wrap_data_key(data_key)

    encrypted_payload = {
        "gdst_event_type": event_dict["gdst_event_type"],
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
    event_hash_hex = "0x" + event_hash.hex()

    # --- Guardian forwarding (non-blocking on hot path, Constitution §IV) ---
    guardian_submission: dict = {"status": "skipped", "reason": "not_configured"}
    client = _maybe_get_guardian_client()
    if client is not None:
        try:
            subject = to_credential_subject(
                event_dict, GDST, event_hash_hex=event_hash_hex
            )
            ack = await client.submit_document(
                policy_id=GDST.policy_id,
                block_tag=GDST.intake_block_tag,
                document=subject,
            )
            guardian_submission = {
                "status": "submitted",
                "cached": ack.cached,
                "submittedAt": ack.submitted_at.isoformat(),
            }
        except GuardianBreakerOpen:
            # T054 (US3) will expand this into a structured WARN with the
            # full {event_hash, operator_did, mgs_error_class, breaker_opened_at}
            # payload. For now keep the HCS path unblocked.
            logger.warning(
                "guardian.skipped", extra={"event_hash": event_hash_hex, "reason": "breaker_open"}
            )
            guardian_submission = {"status": "skipped", "reason": "breaker_open"}
        except GuardianError as e:
            logger.warning(
                "guardian.error",
                extra={"event_hash": event_hash_hex, "error": e.__class__.__name__},
            )
            guardian_submission = {"status": "error", "reason": e.__class__.__name__}

    return {
        "status": "ok",
        "transactionId": result["transactionId"],
        "receiptStatus": result["receiptStatus"],
        "eventType": event_dict["gdst_event_type"],
        "eventHash": event_hash_hex,
        "source": source,
        "guardian": guardian_submission,
    }

@router.get("/{event_hash_hex}/files", summary="Get file CIDs attached to an event")
def get_files_for_event(event_hash_hex: str):
    """
    Fetches the list of file CIDs attached to an event from the smart contract.
    """
    try:
        contract_id = ContractId.from_string(settings.GDST_CONTRACT_ID)
        file_cids = hedera_contract_get_files(event_hash_hex, contract_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Contract call failed: {e}")

    return {
        "eventHash": event_hash_hex,
        "fileCids": file_cids,
    }

@router.post("/{event_hash_hex}/attach", summary="Attach file to existing event on Hedera")
async def attach_file_to_event(
    event_hash_hex: str,
    file: UploadFile = File(...),
):
    """Creates a file CID (using IPFS/Pinata) and attaches it to an existing event on Hedera."""

    try:
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Empty file")

        metadata = {
            "filename": file.filename,
            "mime_type": file.content_type,
        }

        # 1. Envelope-encrypt using your AES-GCM
        envelope, data_key = file_envelope_encrypt(raw, metadata)
        envelope_json = json.dumps(envelope).encode("utf-8")

        # 2. Upload ciphertext to IPFS
        cid = upload_to_ipfs(envelope_json, filename=file.filename)

        # Store CID on smart contract
        contract_id = ContractId.from_string(settings.GDST_CONTRACT_ID)
        tx_id = hedera_contract_attach_file(event_hash_hex, cid, data_key, contract_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hedera write failed: {e}")

    return {
        "status": "ok",
        "transactionId": tx_id,
        "eventHash": event_hash_hex,
        "fileCid": cid,
    }

@router.get("/{event_hash_hex}/files/{cid}/download", summary="Download and decrypt file for event")
def download_decrypted_file(event_hash_hex: str, cid: str):
    # 1. Download encrypted file from IPFS using CID
    envelope_json = download_from_ipfs(cid)
    envelope = json.loads(envelope_json)

    # 2. Retrieve wrapped data key from smart contract using CID
    contract_id = ContractId.from_string(settings.GDST_CONTRACT_ID)
    data_key = hedera_contract_get_data_key(cid, contract_id)

    # 3. Decrypt the file
    decrypted_bytes = file_envelope_decrypt(
        envelope,
        data_key
    )

    # 4. Return the decrypted file
    metadata = envelope.get("meta", {})
    filename = metadata.get("filename", "decrypted_file.bin")
    mime_type = metadata.get("mime_type", "application/octet-stream")
    return StreamingResponse(
        iter([decrypted_bytes]),
        media_type=mime_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
