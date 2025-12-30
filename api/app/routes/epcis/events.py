from app.helpers.compliance import sha256_bytes32
from app.models.gdst.base import GDSTEvent
from app.service.hedera import hedera_post_transaction
from app.service.ipfs import download_from_ipfs, upload_to_ipfs
from fastapi import APIRouter, HTTPException, File, UploadFile
from fastapi.responses import StreamingResponse
from app.core.client import get_client
from app.core.kms import get_kms
from app.crypto.encryption import envelope_encrypt, file_envelope_decrypt, file_envelope_encrypt
from app.core.config import settings
from app.models.starfish_events import StarfishEvent
from hiero_sdk_python.contract.contract_id import ContractId
from hiero_sdk_python.contract.contract_call_query import ContractCallQuery
from hiero_sdk_python.contract.contract_execute_transaction import (
    ContractExecuteTransaction
)
from hiero_sdk_python import (
    ContractFunctionParameters
)
import base64, json, datetime

router = APIRouter(prefix="/events", tags=["Events"])

@router.post("", summary="Receive Starfish event → encrypt → write to Hedera")
def create_event(
    evt: StarfishEvent,
):
    """Accepts any Starfish EPCIS-like event and writes it immutably to Hedera."""
    source = "starfish"
    event_dict = evt.model_dump()
    enc_meta, data_key = envelope_encrypt(event_dict)
    kms = get_kms()
    wrapped_dk = kms.wrap_data_key(data_key)

    encrypted_payload = {
        "eventType": event_dict["eventType"],
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

    return {
        "status": "ok",
        "transactionId": result["transactionId"],
        "receiptStatus": result["receiptStatus"],
        "eventType": event_dict["eventType"],
        "source": source,
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

        # 1️⃣ Envelope-encrypt using your AES-GCM
        envelope, data_key = file_envelope_encrypt(raw, metadata)
        envelope_json = json.dumps(envelope).encode("utf-8")

        # 2️⃣ Upload ciphertext to IPFS
        cid = upload_to_ipfs(envelope_json, filename=file.filename)

        # Store CID on smart contract
        client, op_key = get_client()
        contract_id = ContractId.from_string(settings.COMPLIANCE_CONTRACT_ID)
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
        receipt = tx.execute(client)
        tx_id = str(tx.transaction_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hedera write failed: {e}")

    return {
        "status": "ok",
        "transactionId": tx_id,
        "receiptStatus": str(receipt.status),
        "eventHash": event_hash_hex,
        "fileCid": cid,
    }

@router.get("/{event_hash_hex}/files", summary="Get file CIDs attached to an event")
def get_files_for_event(event_hash_hex: str):
    """
    Fetches the list of file CIDs attached to an event from the smart contract.
    """
    try:
        client, _op_key = get_client()
        contract_id = ContractId.from_string(settings.COMPLIANCE_CONTRACT_ID)
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

        file_cids = tx.get_result(["string[]"])[0]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Contract call failed: {e}")

    return {
        "eventHash": event_hash_hex,
        "fileCids": file_cids,
    }

@router.get("/{event_hash_hex}/files/{cid}/download", summary="Download and decrypt file for event")
def download_decrypted_file(event_hash_hex: str, cid: str):
    # 1. Download encrypted file from IPFS using CID
    envelope_json = download_from_ipfs(cid)
    envelope = json.loads(envelope_json)

    # 2. Retrieve wrapped data key from smart contract using CID
    client, _op_key = get_client()
    contract_id = ContractId.from_string(settings.COMPLIANCE_CONTRACT_ID)
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
    data_key = tx.get_result(["bytes32"])[0]

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