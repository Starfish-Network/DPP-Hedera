from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    ENV: str = "dev"
    OPERATOR_ID: str
    OPERATOR_KEY: str
    KEY_TYPE: str = "der"
    COMPLIANCE_CONTRACT_ID: str | None = None
    GDST_CONTRACT_ID: str | None = None
    TOPIC_ID: str
    NETWORK: str = "testnet"
    MIRROR_BASE: str = "https://testnet.mirrornode.hedera.com/api/v1"

    # GCP KMS
    KMS_PROVIDER: str = "mock"  # "mock" or "gcp"
    GCP_PROJECT_ID: str | None = None
    GCP_LOCATION_ID: str | None = None
    GCP_KEY_RING: str | None = None
    GCP_KEY_NAME: str | None = None

    # JWT
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # PINATA
    PINATA_API_URL: str = "https://testnet.pinata.cloud"
    PINATA_API_KEY: str | None = None
    PINATA_API_SECRET: str | None = None

    class Config:
        env_file = f".env.{os.getenv('ENV', 'dev')}"
        env_file_encoding = "utf-8"

settings = Settings()
