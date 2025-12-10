import os
import sys
import json
import hashlib
from solcx import compile_source, install_solc

from dotenv import load_dotenv

from hiero_sdk_python import AccountId, Client, Network, PrivateKey
from hiero_sdk_python.contract.contract_call_query import ContractCallQuery
from hiero_sdk_python.contract.contract_create_transaction import (
    ContractCreateTransaction,
)
from hiero_sdk_python.contract.contract_execute_transaction import (
    ContractExecuteTransaction,
)
from hiero_sdk_python.contract.contract_function_parameters import (
    ContractFunctionParameters,
)
from hiero_sdk_python.response_code import ResponseCode

load_dotenv()

# Compile -----------------------------------------------------------
install_solc("0.8.20")

with open("compliance.sol", "r") as f:
    source_code = f.read()

compiled = compile_source(
    source_code,
    output_values=["abi", "bin"],
    solc_version="0.8.20"
)

# The dict key looks like "<stdin>:ContractName" or "filename:ContractName"
contract_id, contract_interface = compiled.popitem()

abi = contract_interface["abi"]
hex = contract_interface["bin"]  # this is already hex string (no 0x prefix)
bytecode = bytes.fromhex(hex)               # <- MUST be bytes

# Save ABI if you want
with open("compiled_abi.json", "w") as f:
    json.dump(abi, f, indent=2)

print(f"✅ Compiled {contract_id}")


def setup_client():
    """Initialize and set up the client with operator account"""
    network = Network(os.getenv('NETWORK'))
    client = Client(network)

    operator_id = AccountId.from_string(os.getenv("OPERATOR_ID"))
    operator_key = PrivateKey.from_string(os.getenv("OPERATOR_KEY"))
    client.set_operator(operator_id, operator_key)

    return client


def create_contract(client):
    receipt = (
        ContractCreateTransaction()
        .set_admin_key(client.operator_private_key.public_key())
        .set_bytecode(bytecode)
        .set_gas(2000000)  # 2M gas
        .set_contract_memo("Compliance Contract")
        .execute(client)
    )

    # Check if contract creation was successful
    if receipt.status != ResponseCode.SUCCESS:
        print(
            f"Contract creation failed with status: {ResponseCode(receipt.status).name}"
        )
        sys.exit(1)

    print(f"Contract created with ID: {receipt.contract_id}")

    return receipt.contract_id


def record_event(client, contract_id):
    """Record an event in the compliance contract"""
    event_payload = b"sample event for FSMA compliance"
    event_hash = hashlib.sha256(event_payload).digest()  # 32 bytes

    params = (
        ContractFunctionParameters()
        .add_bytes32(event_hash)   # bytes32
        .add_string("Shipping")    # string
        .add_bool(True)            # bool
    )

    # State-changing call uses ContractExecuteTransaction
    result = (
        ContractExecuteTransaction()
        .set_contract_id(contract_id)
        .set_gas(200_000)
        .set_function("recordEvent", params)
        .execute(client)
    )

    if result.status != ResponseCode.SUCCESS:
        print(
            f"Contract execution failed with status: {ResponseCode(result.status).name}"
        )
        sys.exit(1)

def get_all_events(client, contract_id):
    """Verify data via getAllEvents function"""
    result = (
        ContractCallQuery()
        .set_contract_id(contract_id)
        .set_gas(2000000)
        .set_function("getAllEvents")
        .execute(client)
    )

    return result


def execute_contract():
    """
    Demonstrates executing a contract by:
    1. Setting up client with operator account
    2. Creating a contract using the file with constructor parameters
    3. Executing a contract function to record an event
    4. Querying the contract function to verify that the event was recorded
    """
    client = setup_client()

    contract_id = create_contract(client)

    record_event(client, contract_id)

    # Query the contract function to verify that the message was set
    updated_events = get_all_events(client, contract_id)

    print(f"Retrieved events from contract getAllEvents(): '{updated_events}'")


if __name__ == "__main__":
    execute_contract()
