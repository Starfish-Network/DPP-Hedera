# 🐟 Hedera Integration Service

## Overview

This service provides an immutable, secure traceability gateway between the Starfish platform and the Hedera ledger.

It receives supply-chain EPCIS-style events (creating, shipping, receiving, transforming, packing, unpacking), encrypts them using AES-256-GCM + envelope encryption, and immutably records them on the Hedera network.

The service is stateless — no local database is used.
All persisted data lives on Hedera; reads are served via the Mirror Node.

## 🧱 Infrastructure Overview

<img width="1018" height="766" alt="image" src="https://github.com/user-attachments/assets/6cec0046-6b00-44be-88e8-53c07541bfdb" />


### IPFS Integration

The infrastructure includes IPFS (InterPlanetary File System) for decentralized file storage. When files are attached to events, they are encrypted server-side and uploaded to IPFS. The resulting content identifier (CID) is stored on-chain via a smart contract, enabling secure and verifiable file retrieval. Download requests fetch the encrypted file from IPFS and decrypt it using the key managed by the smart contract.

**IPFS is used for:**
- Storing encrypted event-related files
- Retrieving files by CID for authorized users
- Ensuring files are decentralized and tamper-evident

The API endpoints `/events/{event_hash}/attach`, `/events/{event_hash}/files`, and `/events/{event_hash}/files/{cid}/download` handle the integration with IPFS.


``` pgsql
+--------------------------------------------------------------------------------+
|                             🌐 Starfish Platform                              |
|--------------------------------------------------------------------------------|
| Publishes EPCIS-like events via HTTPS to FastAPI endpoints                     |
+--------------------------------------------------------------------------------+
                |
                | (Secure HTTPS, JWT auth)
                v
+--------------------------------------------------------------------------------+
|                          ☁️ Project Infrastructure                             |
|--------------------------------------------------------------------------------|
|                                                                                |
|  +--------------------+        +---------------------------+                   |
|  |  Cloud Run / GKE   |        |  Secret Manager           |                   |
|  |  FastAPI Service   |        |  Environment vars & keys  |                   |
|  |--------------------|        +---------------------------+                   |
|  | Routes: /events, /trace, /health, /compliance |                             |
|  | Performs encryption & writes to Hedera/IPFS |                               |
|  +----------------------------------------+                                   |
|            |                                                                  |
|            | (Envelope Encryption w/ AES-GCM)                                 |
|            v                                                                  |
|  +--------------------------------------+                                    |
|  | 🔐 Cloud KMS (Symmetric Key)         |                                    |
|  | Wrap/unwrap data encryption keys     |                                    |
|  +--------------------------------------+                                    |
|            |                                                                  |
|            | (Encrypted file upload/download)                                 |
|            v                                                                  |
|  +--------------------------------------+                                    |
|  | 🗄️ IPFS (Decentralized Storage)      |                                    |
|  | Stores encrypted event files         |                                    |
|  +--------------------------------------+                                    |
|                                                                                |
|            |                                                                  |
|            | (Signed, encrypted payload)                                      |
|            v                                                                  |
|  +--------------------------------------+                                    |
|  | 🌐 Hedera Consensus Service (HCS)    |                                    |
|  | Topic: 0.0.xxxxx                     |                                    |
|  | Immutable event record               |                                    |
|  +--------------------------------------+                                    |
|            |                                                                  |
|            | (Public ledger replication)                                     |
|            v                                                                  |
|  +--------------------------------------+                                    |
|  | 📡 Hedera Mirror Node (Testnet)      |                                    |
|  | Provides REST API for topic queries  |                                    |
|  +--------------------------------------+                                    |
|                                                                              |
|                                                                              |
+--------------------------------------------------------------------------------+
                |
                | (Mirror Node query or REST)
                v
+--------------------------------------------------------------------------------+
|         🧾 Demo App / Compliance UI                                            |
|--------------------------------------------------------------------------------|
| Fetches event trace from API or Mirror Node, shows product lifecycle          |
+--------------------------------------------------------------------------------+
```

## ⚙️ Core Features
Capability | Description
--- | ---
Immutable recording | Writes encrypted traceability events to Hedera
EPCIS schema support | Handles creating, shipping, receiving, transforming, packing, and unpacking events
AES-256-GCM encryption | Authenticated symmetric encryption per event
Envelope encryption (v2) | Random 256-bit data key wrapped by KMS
Deterministic hashing | Canonical JSON + normalized structure ensures verifiable hashes

## 🔐 Encryption Design (v2)
Layer | Method | Purpose
--- | --- | ---
Payload | AES-256-GCM | Confidentiality + integrity
Data key | Random per event | Ephemeral encryption key
Key wrap | AWS KMS (Envelope) | Protect data key
AAD | Event fields (eventType, event_time, facility, etc.) | Tamper detection
Hash | SHA-256 (Base64) | Ledger verification
Version | "ver": 2 | Identifies schema generation

## 🧩 Event Types (from Starfish)
Event Type | Key Fields
--- | ---
Creating | biz_location, event_time, quantity_list
Shipping | ship_from, ship_to, items
Receiving | shipped_from, received_at, items
Transforming | facility, input_items, output_items, transformation_id
Packing | facility, container_id, input_items
Unpacking | facility, container_id, output_items

Each payload follows the EPCIS data model, validated via Pydantic.

## 🚀 Endpoints

`POST /api/events`

Receives Starfish events, encrypts them, and writes to Hedera.

**Headers**

Authorization: Bearer
Content-Type: application/json

**Example (Shipping Event)**

``` json
{
  "eventType": "shipping",
  "ship_from": "9506001112229",
  "ship_to": "9506001112229",
  "event_time": "2025-10-03T12:08:00.000Z",
  "event_timezone_offset": "+01:00",
  "items": [
    {
      "epc": "urn:epc:class:lgtin:9506000.1233.a",
      "quantity": 12.0,
      "unit_of_measurement": "kg"
    }
  ]
}
```


**Response**

``` json
{
  "status": "ok",
  "transactionId": "0.0.12345@1698831600.123456789",
  "receiptStatus": "SUCCESS",
  "eventType": "shipping",
  "source": "starfish"
}
```

`GET /api/trace/{epc}`

Fetches the full trace graph for a given EPC.

**Response**

``` json
{
  "epc": "urn:epc:class:lgtin:9506000.1233.a",
  "trace": {
    "nodes": [ ... ],
    "edges": [ ... ]
  }
}
```

`POST /api/compliance/check`

Submits an event for compliance verification via smart contract.

**Request**

``` json
{
        "eventType": "shipping",
        "event_time": "2025-10-03T12:08:00.000Z",
        "shipFrom": "9506001112229",
        "shipTo": "9506001112230",
        "items": [{"epc": "urn:epc:class:lgtin:9506000.1233.a", "quantity": 12.0, "unit_of_measurement": "kg"}]
}
```

**Response**

``` json
{
        "status": "ok",
        "isCompliant": "true",
        "txStatus": "SUCCESS",
        "contractId": "0.0.54321",
        "eventHashHex": "0xa1b2c3d4e5f6..."
}
```

`GET /api/compliance/status/{event_hash}`

Fetches compliance status for a given event hash.

**Response**

``` json
{
        "eventHashHex": "0xa1b2c3d4e5f6...",
        "isCompliant": "true",
        "eventHashHex": "a1b2c3d4e5f6...",
        "contractId": "0.0.54321"
}
```

`GET /api/events/{event_hash}/files` 

Returns all IPFS CIDs attached to an event.

**Response:**
```json
{
  "eventHash": "...",
  "fileCids": ["Qm...", "Qm..."]
}
```

`GET /api/events/{event_hash}/files/{cid}/download`

Downloads and decrypts the file for the event.

---

## 🌊 GDST Endpoints

`POST /api/gdst/events`

Receives GDST events, encrypts them, and writes to Hedera.

**Example Request**

```json
{
  "gdst_event_type": "Landing",
  "event_time": "2025-10-03T12:08:00.000Z",
  "facility": "Port of Vigo",
  "input_items": [
    {"epc": "urn:epc:id:sgtin:9506000.1233.400"}
  ]
}
```

**Example Response**

```json
{
  "status": "ok",
  "transactionId": "0.0.12345@1698831600.123456789",
  "receiptStatus": "SUCCESS",
  "eventType": "Landing",
  "eventHash": "a1b2c3d4e5f6...",
  "source": "starfish"
}
```

`POST /api/gdst/compliance/check`

Validates a GDST event and records compliance on-chain.

**Example Request**

```json
{
  "gdst_event_type": "Landing",
  "event_time": "2025-10-03T12:08:00.000Z",
  "facility": "Port of Vigo",
  "input_items": [
    {"epc": "urn:epc:id:sgtin:9506000.1233.400"}
  ]
}
```

**Example Response**

```json
{
  "status": "ok",
  "isCompliant": true,
  "txStatus": "SUCCESS",
  "contractId": "0.0.54321",
  "eventHashHex": "0xa1b2c3d4e5f6..."
}
```

`GET /api/gdst/compliance/status/{event_hash}`

Fetches compliance status for a GDST event hash.

**Example Response**

```json
{
  "status": "ok",
  "isCompliant": true,
  "contractId": "0.0.54321",
  "eventHashHex": "0xa1b2c3d4e5f6..."
}
```

`GET /api/gdst/events/{event_hash}/files`

Returns all IPFS CIDs attached to a GDST event.

**Example Response**

```json
{
  "eventHash": "a1b2c3d4e5f6...",
  "fileCids": ["Qm123...", "Qm456..."]
}
```

`POST /api/gdst/events/{event_hash}/attach`

Attaches a file to a GDST event (stores CID on-chain).

**Example Request**

Form-data: file (binary)

**Example Response**

```json
{
  "status": "ok",
  "transactionId": "0.0.12345@1698831600.123456789",
  "eventHash": "a1b2c3d4e5f6...",
  "fileCid": "Qm123..."
}
```

`GET /api/gdst/events/{event_hash}/files/{cid}/download`

Downloads and decrypts a file for a GDST event.

**Example Response**

Binary file stream (decrypted contents)

## 🔧 Configuration (.env.dev example)
``` env
OPERATOR_ID=0.0.12345
OPERATOR_KEY=302e020100300506032b657004220420xxxxxxxxxxxxxx
TOPIC_ID=0.0.45678
NETWORK=testnet
CONTRACT_ID=0.0.54321

KMS_PROVIDER=aws
KMS_KEY_ID=arn:aws:kms:eu-west-1:123456789012:key/abcd-...-1234
AWS_REGION=eu-west-1

JWT_SECRET=supersecretdevkey
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

```

## 🐳 Docker Usage
``` bash
docker-compose build
docker-compose up
```

App will start on http://localhost:8000.

Health check:

curl http://localhost:8000/api/health

## 🧪 Integration Testing

Run the integration suite (FastAPI + Hedera + Mirror Node)
``` bash
docker-compose up --build --exit-code-from integration-tests
```

Or locally:

``` bash
pytest -m integration -v
```

**Test steps**

1. Send sample shipping event → /api/events

2. Wait for Hedera transaction confirmation via Mirror Node

3. Fetch topic messages and decode

4. Verify eventType and message integrity

## 📜 Data Lifecycle

Step | Description
--- | ---
1️⃣ Receive | Starfish POSTs event → FastAPI validates
2️⃣ Encrypt | AES-256-GCM encrypts payload; KMS wraps key
3️⃣ Write | Encrypted event committed to Hedera Topic
4️⃣ Query | Mirror Node serves immutable history

## 🧠 Notes

All data stored on Hedera is encrypted and integrity-protected.

The API is stateless — ledger and Mirror Node are sources of truth.

The system can be extended to support partial (public/private) encryption later.

Each message envelope includes ver: 2 to distinguish the new encryption schema.
