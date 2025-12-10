import requests
from io import BytesIO
from app.crypto.encryption import file_envelope_decrypt
from app.core.config import settings

def upload_to_ipfs(data: bytes, filename: str = "file.bin") -> str:
    files = {
        "file": (filename, BytesIO(data)),
    }
    headers = {
        "pinata_api_key": settings.PINATA_API_KEY,
        "pinata_secret_api_key": settings.PINATA_API_SECRET,
    }
    resp = requests.post(
        "https://api.pinata.cloud/pinning/pinFileToIPFS",
        files=files,
        headers=headers
    )
    resp.raise_for_status()
    json_resp = resp.json()
    cid = json_resp.get("IpfsHash")
    if not cid:
        raise RuntimeError("Unable to determine CID from Pinata response")
    return cid

def download_from_ipfs(cid: str) -> bytes:
    resp = requests.get(f"https://ipfs.io/ipfs/{cid}")
    resp.raise_for_status()
    return resp.content
