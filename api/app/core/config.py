from pydantic_settings import BaseSettings
from pydantic import model_validator
from typing import Literal
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

    # Guardian / MGS (feature 001-guardian-integration, research.md §1 & §4)
    GUARDIAN_NETWORK: Literal["testnet", "mainnet"] = "testnet"
    GUARDIAN_API_URL: str | None = None
    GUARDIAN_SR_USERNAME: str | None = None
    GUARDIAN_SR_PASSWORD: str | None = None
    GUARDIAN_GDST_POLICY_ID: str | None = None
    GUARDIAN_FSMA_POLICY_ID: str | None = None
    GUARDIAN_GDST_INTAKE_BLOCK_TAG: str | None = None
    GUARDIAN_FSMA_INTAKE_BLOCK_TAG: str | None = None
    GUARDIAN_GENERIC_POLICY_ID: str | None = None
    GUARDIAN_GENERIC_INTAKE_BLOCK_TAG: str | None = None
    # Dry-run sandbox policy (scripts/bootstrap_dryrun_policy.py creates it).
    # Used by POST /guardian/dryrun/submit/{slug} to issue real signed VCs in
    # the dry-run environment when published-policy workers are unavailable.
    GUARDIAN_DRYRUN_POLICY_ID: str | None = None
    GUARDIAN_DRYRUN_INTAKE_BLOCK_TAG: str | None = None
    GUARDIAN_VC_PENDING_THRESHOLD_S: int = 30       # SC-007 pending window
    GUARDIAN_VC_MANUAL_REVIEW_CEILING_S: int = 300  # SC-007 manual-review ceiling
    GUARDIAN_BREAKER_FAIL_COUNT: int = 3            # FR-005 / research.md §3
    GUARDIAN_BREAKER_OPEN_DURATION_S: int = 60      # FR-005 / research.md §3

    # 002-demo-ui: feature-flagged dev-only routes that drive the breaker
    # simulator from the demo UI (research.md §2 of 002-demo-ui). Default
    # disabled; production deployments leave this off so /api/v1/_demo/* is
    # unmounted and unreachable.
    GUARDIAN_DEMO_ROUTES_ENABLED: str = "0"

    @model_validator(mode="after")
    def _guardian_network_matches_hedera_network(self) -> "Settings":
        if self.GUARDIAN_NETWORK != self.NETWORK:
            raise ValueError(
                "GUARDIAN_NETWORK must match NETWORK — mixing testnet Guardian DIDs with "
                "mainnet Hedera identities is forbidden (research.md §1)."
            )
        return self

    class Config:
        env_file = f".env.{os.getenv('ENV', 'dev')}"
        env_file_encoding = "utf-8"

settings = Settings()
