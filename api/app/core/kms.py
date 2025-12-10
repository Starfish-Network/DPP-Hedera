from typing import Protocol
from app.core.config import settings

class KMSProvider(Protocol):
    def wrap_data_key(self, dk: bytes) -> bytes: ...
    def unwrap_data_key(self, wrapped: bytes) -> bytes: ...

class MockKMS(KMSProvider):
    PREFIX = b"mock_kms_wrap_"
    def wrap_data_key(self, dk: bytes) -> bytes:
        return self.PREFIX + dk
    def unwrap_data_key(self, wrapped: bytes) -> bytes:
        assert wrapped.startswith(self.PREFIX), "Invalid mock KMS blob"
        return wrapped[len(self.PREFIX):]


# ---------------------------------------------------------------------------
# Google Cloud KMS
# ---------------------------------------------------------------------------
class GCPKMS(KMSProvider):
    def __init__(self, project_id: str, location: str, key_ring: str, key_name: str):
        from google.cloud import kms
        self.client = kms.KeyManagementServiceClient()
        self.key_path = self.client.crypto_key_path(project_id, location, key_ring, key_name)

    def wrap_data_key(self, dk: bytes) -> bytes:
        """Encrypt the raw data key using GCP KMS."""
        response = self.client.encrypt(request={"name": self.key_path, "plaintext": dk})
        return response.ciphertext

    def unwrap_data_key(self, wrapped: bytes) -> bytes:
        """Decrypt the wrapped data key using GCP KMS."""
        response = self.client.decrypt(request={"name": self.key_path, "ciphertext": wrapped})
        return response.plaintext


# ---------------------------------------------------------------------------
# Provider selector
# ---------------------------------------------------------------------------
def get_kms() -> KMSProvider:
    if settings.KMS_PROVIDER == "gcp":
        return GCPKMS(
            settings.GCP_PROJECT_ID,
            settings.GCP_LOCATION_ID,
            settings.GCP_KEY_RING,
            settings.GCP_KEY_NAME
        )
    return MockKMS()
