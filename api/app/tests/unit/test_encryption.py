from app.crypto.encryption import envelope_encrypt, aes_gcm_decrypt
import base64, json

def test_envelope_encrypt_and_decrypt_roundtrip():
    """Ensure that encryption + decryption roundtrip works as expected."""
    event = {
        "eventType": "creating",
        "biz_location": "9506001112229",
        "event_time": "2025-10-03T12:08:00.000Z",
        "event_timezone_offset": "+01:00",
        "quantity_list": [{
            "epc": "urn:epc:class:lgtin:9506000.1233.a",
            "quantity": 12.0,
            "unit_of_measurement": "kg"
        }]
    }

    enc_meta, dk = envelope_encrypt(event)
    assert "ciphertext_b64" in enc_meta
    assert "nonce_b64" in enc_meta

    nonce = base64.b64decode(enc_meta["nonce_b64"])
    ciphertext = base64.b64decode(enc_meta["ciphertext_b64"])
    aad = base64.b64decode(enc_meta["aad_b64"])

    plaintext = aes_gcm_decrypt(ciphertext, dk, nonce, aad)
    decoded = json.loads(plaintext.decode("utf-8"))

    assert decoded["eventType"] == "creating"
    assert decoded["biz_location"] == "9506001112229"
