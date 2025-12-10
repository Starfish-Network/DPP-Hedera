import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app

@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_external_services():
    """
    Automatically mock external dependencies:
    - Hedera client and transaction
    - Google Cloud KMS or MockKMS
    """
    with patch("app.core.kms.get_kms") as mock_kms, \
         patch("app.routes.events.get_client") as mock_client, \
         patch("app.routes.events.TopicMessageSubmitTransaction") as mock_tx:

        # Mock KMS key wrapping
        mock_kms_instance = MagicMock()
        mock_kms_instance.wrap_data_key.side_effect = lambda dk: b"wrapped_" + dk
        mock_kms_instance.unwrap_data_key.side_effect = lambda w: w.replace(b"wrapped_", b"")
        mock_kms.return_value = mock_kms_instance

        # Mock Hedera client/transaction
        mock_client_instance = MagicMock()
        op_key = MagicMock()
        mock_client.return_value = (mock_client_instance, op_key)

        # Mock transaction methods
        mock_tx_instance = MagicMock()
        mock_tx_instance.freeze_with.return_value = mock_tx_instance
        mock_tx_instance.sign.return_value = mock_tx_instance
        mock_tx_instance.execute.return_value = MagicMock(transaction_id="0.0.12345@1698831600.123456789", get_receipt=lambda client: MagicMock(status="SUCCESS"))
        mock_tx.return_value = mock_tx_instance

        yield  # run the test
