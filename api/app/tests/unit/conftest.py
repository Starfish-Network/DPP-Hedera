import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.core.kms import MockKMS
from app.main import app


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_external_services():
    """
    Stub external dependencies so unit tests don't hit the network:
    - KMS (production MockKMS — covers wrap/unwrap including the prefix assertion)
    - The Hedera ledger write (`hedera_post_transaction` in the EPCIS events route)
    """
    with patch("app.core.kms.get_kms", return_value=MockKMS()), \
         patch(
             "app.routes.epcis.events.hedera_post_transaction",
             return_value={
                 "transactionId": "0.0.12345@1698831600.123456789",
                 "receiptStatus": "SUCCESS",
             },
         ):
        yield
