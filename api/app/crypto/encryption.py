import os, json, base64, hashlib
from typing import Tuple, Dict, Any, List, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# ---------------------------------------------------------------------------
# 1. Normalization helpers
# ---------------------------------------------------------------------------

def normalize_event(event: dict) -> dict:
    """
    Normalize Starfish event dict to ensure deterministic structure before hashing/encryption.
    - Sorts top-level keys.
    - Sorts any list of dicts by 'epc' key if present.
    - Converts datetimes to strings if they are not already.
    """
    def normalize_value(value):
        if isinstance(value, dict):
            return normalize_event(value)
        elif isinstance(value, list):
            if all(isinstance(i, dict) and "epc" in i for i in value):
                return sorted([normalize_event(i) for i in value], key=lambda x: x["epc"])
            else:
                return [normalize_event(i) if isinstance(i, dict) else i for i in value]
        return value

    normalized = {k: normalize_value(v) for k, v in sorted(event.items())}
    return normalized


# ---------------------------------------------------------------------------
# 2. JSON + hashing helpers
# ---------------------------------------------------------------------------

def canonical_json(data: dict) -> bytes:
    """
    Convert dict to canonical JSON (UTF-8, sorted keys, no whitespace).
    Ensures deterministic serialization for hash and encryption.
    """
    return json.dumps(data, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")


def sha256_b64(data: bytes) -> str:
    """Compute base64-encoded SHA-256 hash of data."""
    return base64.b64encode(hashlib.sha256(data).digest()).decode()


# ---------------------------------------------------------------------------
# 3. AES-GCM encryption/decryption
# ---------------------------------------------------------------------------

def aes_gcm_encrypt(plaintext: bytes, data_key: bytes, aad: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    """Encrypts plaintext with AES-256-GCM. Returns (ciphertext, nonce)."""
    nonce = os.urandom(12)  # 96-bit nonce
    aesgcm = AESGCM(data_key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, aad)
    return ciphertext, nonce


def aes_gcm_decrypt(ciphertext: bytes, data_key: bytes, nonce: bytes, aad: Optional[bytes] = None) -> bytes:
    """Decrypts AES-256-GCM ciphertext."""
    aesgcm = AESGCM(data_key)
    return aesgcm.decrypt(nonce, ciphertext, aad)

# ---------------------------------------------------------------------------
# 4. Envelope encryption (with AAD and deterministic hash)
# ---------------------------------------------------------------------------

def envelope_encrypt(
    event: Dict[str, Any],
    aad_fields: Optional[List[str]] = None
) -> Tuple[Dict[str, Any], bytes]:
    """
    Encrypts an event with AES-256-GCM, wrapping the key separately (via KMS outside this function).

    Returns:
        (metadata dict, raw data_key bytes)
    """

    # 1️⃣ Normalize event for deterministic hash
    event = normalize_event(event)
    plaintext = canonical_json(event)

    # 2️⃣ Generate random data key (32 bytes = 256 bits)
    data_key = os.urandom(32)

    # 3️⃣ Compute AAD: non-confidential fields to protect
    if aad_fields is None:
        aad_fields = [
            "eventType",
            "event_time",
            "event_timezone_offset",
            "biz_location",
            "facility",
            "ship_from",
            "ship_to",
            "received_at",
            "container_id"
        ]
    aad_values = [str(event.get(f, "")) for f in aad_fields if f in event]
    aad = "|".join(aad_values).encode("utf-8") if aad_values else None

    # 4️⃣ Encrypt
    ciphertext, nonce = aes_gcm_encrypt(plaintext, data_key, aad)

    # 5️⃣ Compute hash of plaintext (for verification / integrity)
    digest_b64 = sha256_b64(plaintext)

    # 6️⃣ Package envelope metadata
    return {
        "ciphertext_b64": base64.b64encode(ciphertext).decode(),
        "nonce_b64": base64.b64encode(nonce).decode(),
        "aad_b64": base64.b64encode(aad or b"").decode(),
        "sha256_b64": digest_b64,
        "alg": "AES-256-GCM",
        "ver": 2
    }, data_key

def file_envelope_encrypt(
    file_bytes: bytes,
    metadata: Dict[str, Any],
    aad_fields: Optional[list[str]] = None,
) -> Tuple[Dict[str, Any], bytes]:
    """
    Encrypt file_bytes with AES-256-GCM using a fresh data_key.
    Returns (envelope_metadata, raw data_key).
    `metadata` should contain non-sensitive info used for AAD (e.g. filename, owner_id).
    """

    # 1️⃣ Generate random data key (32 bytes = 256 bits)
    data_key = os.urandom(32)

    # 2️⃣ Build AAD from selected metadata fields
    if aad_fields is None:
        aad_fields = ["filename", "mime_type"]
    aad_values = [str(metadata.get(f, "")) for f in aad_fields if f in metadata]
    aad = "|".join(aad_values).encode("utf-8") if aad_values else None

    # 3️⃣ Encrypt file bytes
    ciphertext, nonce = aes_gcm_encrypt(file_bytes, data_key, aad)

    # 4️⃣ Hash plaintext (optional but very nice to have)
    digest_b64 = sha256_b64(file_bytes)

    # 5️⃣ Envelope metadata (no plaintext, no data_key)
    envelope = {
        "ciphertext_b64": base64.b64encode(ciphertext).decode(),
        "nonce_b64": base64.b64encode(nonce).decode(),
        "aad_b64": base64.b64encode(aad or b"").decode(),
        "sha256_b64": digest_b64,
        "alg": "AES-256-GCM",
        "ver": 1,
        # can also store selected metadata fields here if useful
        "meta": {
            "filename": metadata.get("filename"),
            "mime_type": metadata.get("mime_type"),
        },
    }

    return envelope, data_key


def file_envelope_decrypt(
    envelope: Dict[str, Any],
    data_key: bytes,
) -> bytes:
    """
    Decrypts an envelope produced by file_envelope_encrypt.
    """
    ciphertext = base64.b64decode(envelope["ciphertext_b64"])
    nonce = base64.b64decode(envelope["nonce_b64"])
    aad_raw = base64.b64decode(envelope.get("aad_b64", "") or b"")
    aad = aad_raw if aad_raw else None

    plaintext = aes_gcm_decrypt(ciphertext, data_key, nonce, aad)

    # Optional: verify hash
    expected_hash = envelope.get("sha256_b64")
    if expected_hash:
        actual_hash = sha256_b64(plaintext)
        if actual_hash != expected_hash:
            raise ValueError("File integrity check failed (SHA-256 mismatch)")

    return plaintext
