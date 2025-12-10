from hiero_sdk_python import Client, AccountId, PrivateKey, Network
from app.core.config import settings

def get_client() -> Client:
    op_id = AccountId.from_string(settings.OPERATOR_ID)
    op_key = PrivateKey.from_string(settings.OPERATOR_KEY)
    client = Client(Network(network=settings.NETWORK))
    client.set_operator(op_id, op_key)
    return client, op_key
