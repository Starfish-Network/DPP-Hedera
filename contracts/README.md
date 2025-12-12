# How to deploy the contract

To deploy the contract, follow these steps:

```bash
docker build -t contract-deployer .
docker run contract-deployer
```

This will build the Docker image and run the deployment script contained within it. Make sure you have Docker installed and running on your machine before executing these commands.

The deployment script will handle all necessary steps to deploy the contract to the specified blockchain network. Ensure you have the required environment variables set for authentication and network configuration before running the Docker container.

Copy the contract id from the logs once the deployment is complete for future use.

---

# ComplianceVerifier Smart Contract Overview

This contract manages compliance records for supply chain events and supports secure file attachments using IPFS CIDs and data keys.

## Key Features

- Record compliance status for events (event type, compliance, timestamp, verifier)
- Attach encrypted files (by IPFS CID) to events
- Store and retrieve data keys for each file
- Query compliance status and attached files for any event

## Main Functions

- `recordEvent(bytes32 eventHash, string eventType, bool isCompliant)`
	- Records a new compliance event. Only one record per event hash is allowed.

- `getComplianceStatus(bytes32 eventHash)`
	- Returns event type, compliance status, timestamp, and verifier address for a given event hash.

- `getAllEvents()`
	- Returns all recorded event hashes.

- `attachFile(bytes32 eventHash, string cid, bytes32 dataKey)`
	- Attaches an IPFS file (by CID) and its data key to an event.

- `getFiles(bytes32 eventHash)`
	- Returns all file CIDs attached to an event.

- `getDataKey(string cid)`
	- Returns the data key for a given file CID.

## Usage Notes

- Each event is uniquely identified by its hash (`bytes32`).
- Files are encrypted before upload; only the data key is stored on-chain.
- The contract is designed to be called by an API or backend service that manages encryption and IPFS interactions.

## Example Workflow

1. Record a compliance event using `recordEvent`.
2. Attach one or more files to the event using `attachFile` (store the encrypted file in IPFS, then call this function with the CID and data key).
3. Retrieve compliance status or attached files using `getComplianceStatus` and `getFiles`.
4. To decrypt a file, fetch its data key with `getDataKey` and retrieve the file from IPFS using its CID.

---

For more details, see the contract source: `compliance.sol`.