# 🧭 Hedera Supply Chain Traceability DApp

This project implements a food traceability and compliance solution that integrates the Starfish traceability platform with the Hedera Distributed Ledger.
It immutably records supply chain events (e.g., creating, transforming, packing, shipping, receiving) and provides a web UI to explore full product lineage and event proofs on-chain.

## 🌍 Overview

The goal of this project is to enhance supply chain transparency by immutably storing EPCIS-like event data from the Starfish platform on the Hedera ledger, ensuring:

- Data integrity and immutability via distributed ledger
- Full traceability across transformations and shipments
- Compliance verification (e.g., FSMA digital product passports)
- Interoperability with existing Starfish APIs and applications

## 🧱 Infrastructure Overview

<img width="1018" height="766" alt="image" src="https://github.com/user-attachments/assets/6cec0046-6b00-44be-88e8-53c07541bfdb" />

## ⚙️ Architecture
``` text
 ┌──────────────────────┐
 │  Starfish Platform   │
 │ (EPCIS & GDST Events)│
 └──────────┬───────────┘
            │ POST /api/events
            ▼
 ┌───────────────────────────────┐
 │  FastAPI Integration Service  │
 │   • Encrypts payloads (KMS)   │
 │   • Writes to Hedera Topic    │
 │   • Exposes /api/trace/{id}   │
 └──────────┬────────────────────┘
            │
            ▼
 ┌───────────────────────────────┐
 │      Hedera Network           │
 │   (HCS Topic + Mirror Node)   │
 └──────────┬────────────────────┘
            │
            ▼
 ┌───────────────────────────────┐
 │   React Trace Explorer UI     │
 │   • Calls /api/trace/{id}     │
 │   • Visualizes lineage graph  │
 │   • Links to HashScan proofs  │
 └───────────────────────────────┘
```

## 🧱 Components
Component | Tech Stack | Purpose
--- | --- | ---
Integration API | FastAPI (Python) | Accepts EPCIS events, encrypts, writes to Hedera
Encryption Layer | AES-GCM + GCP KMS | Ensures secure storage of sensitive data
Ledger Integration | Hiero SDK / Hedera Topic | Immutable record of events
Trace Service | FastAPI + Mirror Node | Rebuilds full lineage graph
UI Frontend | React + Tailwind + vis-network | Interactive lineage visualization
Tests | pytest | Unit + integration verification

## 🔐 Data Flow

1. Starfish sends traceability events to /api/events

2. Service encrypts the payload using AES-GCM (data key managed by GCP KMS)

3. Encrypted payload is written to a Hedera Consensus Topic

4. Mirror Node makes these messages queryable

5. /api/trace/{productId} fetches and decrypts all messages, reconstructing upstream/downstream relationships

6. UI displays a graph and timeline of the product’s full supply chain journey

## 🧩 API Endpoints

Endpoint | Method | Description
--- | --- | ---
/api/events | POST | Receives EPCIS-like trace events (creating, shipping, receiving, etc.) and writes them to Hedera
/api/trace/{productId} | GET | Retrieves a product’s full lineage (upstream/downstream graph) from Hedera’s Mirror Node
/api/gdst/events | POST | Receives GDST events, encrypts, and writes to Hedera
/api/gdst/compliance/check | POST | Validates a GDST event and records compliance on-chain
/api/gdst/compliance/status/{event_hash} | GET | Fetches compliance status for a GDST event hash
/api/gdst/events/{event_hash}/files | GET | Returns all IPFS CIDs attached to a GDST event
/api/gdst/events/{event_hash}/attach | POST | Attaches a file to a GDST event (stores CID on-chain)
/api/gdst/events/{event_hash}/files/{cid}/download | GET | Downloads and decrypts a file for a GDST event

## 🔧 Backend Setup
**Prerequisites**

- Python 3.12+

- Docker + Docker Compose

- Hedera Testnet account + Topic ID

- AWS/GCP credentials (for KMS key management)

- For `/guardian/*` endpoints: a reachable Managed Guardian Service (MGS) + SR credentials

**Environment Variables**

The API loads its env from [`api/.env.dev`](api/.env.dev) (already present in the repo). See [`api/.env.example`](api/.env.example) for the full list. Minimum keys:

```env
OPERATOR_ID=0.0.xxxxx
OPERATOR_KEY=302e02...
TOPIC_ID=0.0.xxxxx
NETWORK=testnet
CONTRACT_ID=0.0.xxxxx

KMS_PROVIDER=aws
KMS_KEY_ID=arn:aws:kms:...
AWS_REGION=eu-west-1

JWT_SECRET=supersecretdevkey
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# Guardian (optional — /guardian/* returns 503 if unset; see below)
GUARDIAN_NETWORK=testnet
GUARDIAN_API_URL=
GUARDIAN_SR_USERNAME=
GUARDIAN_SR_PASSWORD=
GUARDIAN_GDST_POLICY_ID=
GUARDIAN_FSMA_POLICY_ID=
GUARDIAN_GDST_INTAKE_BLOCK_TAG=
GUARDIAN_FSMA_INTAKE_BLOCK_TAG=
```

### 🛡️ Configuring Guardian (MGS)

Guardian (Managed Guardian Service) is used to issue Verifiable Credentials for each compliance event. It's optional — the core `/epcis/*`, `/gdst/*`, and `/trace/*` endpoints work without it — but `/api/v1/guardian/*` will return `503` until these are set.

Canonical runbook: [specs/001-guardian-integration/quickstart.md](specs/001-guardian-integration/quickstart.md).

TL;DR of what the keys mean:

| Key | Source |
|-----|--------|
| `GUARDIAN_NETWORK` | Must match `NETWORK` (`testnet` or `mainnet`). Enforced by [`api/app/core/config.py`](api/app/core/config.py). |
| `GUARDIAN_API_URL` | Your MGS tenant's REST base, e.g. `https://<tenant>.hedera.com/api/v1`. |
| `GUARDIAN_SR_USERNAME` / `_SR_PASSWORD` | Standard Registry credentials created via `POST /accounts/register` with `role: STANDARD_REGISTRY`. |
| `GUARDIAN_GDST_POLICY_ID` / `GUARDIAN_FSMA_POLICY_ID` | Returned after you publish the bundled policies (quickstart §4). |
| `GUARDIAN_GDST_INTAKE_BLOCK_TAG` / `GUARDIAN_FSMA_INTAKE_BLOCK_TAG` | Intake block tag from each published policy. |

High-level provisioning flow (full steps in the quickstart):

1. Create an MGS account and accept the Terms of Service (before acceptance, every call returns `451`).
2. `PUT /tenants/user` to provision the tenant.
3. `POST /accounts/register` with `role: STANDARD_REGISTRY`, then `PUT /profiles/{sr-username}` to activate the SR DID.
4. Publish the GDST and FSMA schemas, then create + publish the policies. Capture the policy IDs and intake block tags.
5. Fill the env keys above, restart the API, and verify with:

   ```bash
   curl http://localhost:8000/api/v1/guardian/health
   ```

   Healthy: `{ "status": "ok", "breaker": "closed", ... }`.
   Other states: `tos_required`, `breaker_open`, `unavailable` — see the [troubleshooting table](specs/001-guardian-integration/quickstart.md#troubleshooting).

### Run with Docker (recommended)

```bash
cd api
docker-compose up --build
```

The API boots at **http://localhost:8000**, mounted at `/api/v1` (hot-reload enabled via volume mount).

- Swagger: http://localhost:8000/api/v1/swagger
- ReDoc:   http://localhost:8000/api/v1/redoc
- Health:  http://localhost:8000/api/v1/health

### Run locally (without Docker)

```bash
cd api
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

env $(grep -v '^#' .env.dev | xargs) \
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Calling the API from Postman

A ready-to-use collection lives at [`docs/postman/DPP-Hedera.postman_collection.json`](docs/postman/DPP-Hedera.postman_collection.json).

1. Import it into Postman.
2. `baseUrl` defaults to `http://localhost:8000/api/v1`.
3. Run **Root → Login** first — its test script stashes the JWT into the `token` collection variable, which every other request uses as a Bearer token.
4. Set the `event_hash_hex`, `cid`, and `product_id` collection variables for path-parameterised requests.

## 🧪 Testing
**Unit + contract tests (local)**
```bash
cd api && pytest -v
```

**Integration suite (API + Hedera + Mirror Node, in Docker)**
```bash
cd api
docker-compose up --build --exit-code-from integration-tests
```


These tests:

- Publish test events to /api/events

- Query /api/trace/{productId}

- Validate upstream/downstream lineage

## 💻 Frontend UI
**Setup**
```bash
cd ui/trace-ui
npm install
npm run dev
```


The UI runs on → http://localhost:5173

**Features**

🔍 Enter any EPC / Lot to fetch its trace

🌐 Graph view showing upstream (blue) and downstream (green) nodes

🕓 Event timeline of all linked products

🔗 Direct links to Hedera transaction proofs on HashScan

🧾 Click a node → see details in modal (identifier, depth, tx IDs)

## 🧬 Example Trace Flow
```
Creating Event → Transforming Event → Packing Event → Shipping Event → Receiving Event
(A10001)            (A→B)                (B in pallet)       (B→C)           (C received)
```

**Sample EPC**
urn:epc:class:lgtin:9506000.1233.a

**Example Trace Graph (simplified)**
``` text
A (Created)
│
▼
B (Transformed)
│
▼
C (Packed & Shipped)
```

## 🧾 Folder Structure
``` text
/api/app
 ├── core/               # Config, KMS, Hedera client setup
 ├── crypto/             # Encryption utilities (AES-GCM, envelope)
 ├── models/             # Pydantic event schemas
 ├── routes/             # FastAPI routes (events, trace)
 ├── tests/              # Unit + integration tests
 └── main.py             # App entrypoint

/ui/trace-ui
 ├── src/
 │   ├── App.tsx         # Trace Explorer UI
 │   ├── components/     # UI components
 │   ├── hooks/          # Data fetching logic
 │   └── index.css       # Tailwind setup
 ├── vite.config.ts
 └── package.json

/contracts
 ├── compliance.sol    # smart contract for compliance verification
 ├── deploy_compliance_contract.py # deployment script
 ├── .env              # contract env vars
```

## 📝 GDST Smart Contract: ComplianceVerifier

The `ComplianceVerifier` smart contract is deployed on Hedera and underpins GDST event compliance and file attachment. It provides:

- **Immutable compliance records** for each event (by hash)
- **On-chain file attachment** (IPFS CIDs + encrypted keys)
- **Compliance status queries** for any event

**Key Functions:**

- `recordEvent(bytes32 eventHash, string eventType, bool isCompliant)`: Records compliance for a GDST event (called by API on /gdst/compliance/check)
- `getComplianceStatus(bytes32 eventHash)`: Returns compliance status, event type, timestamp, and verifier address
- `attachFile(bytes32 eventHash, string cid, bytes32 dataKey)`: Attaches an IPFS file (CID + encrypted key) to an event
- `getFiles(bytes32 eventHash)`: Returns all CIDs attached to an event
- `getDataKey(string cid)`: Returns the encrypted data key for a file CID

**Deployment & Usage:**

- The contract is deployed to the Hedera testnet (see `CONTRACT_ID` in .env)
- All compliance and file operations for GDST events are routed through this contract
- See `/contracts/gdst.sol` for full Solidity source

**Example:**

1. API hashes a GDST event and calls `recordEvent` to store compliance
2. Files are encrypted, uploaded to IPFS, and `attachFile` is called to link the CID and key
3. Downstream, `getComplianceStatus` and `getFiles`/`getDataKey` are used to verify and retrieve event data

This ensures all compliance and file proofs are cryptographically verifiable and auditable on-chain.

## 🧠 Key Design Principles

- Immutable Storage: every event written to Hedera is cryptographically permanent

- Data Encryption: all data encrypted client-side before leaving the platform

- Graph Lineage Reconstruction: full upstream/downstream DAG

- Open Interoperability: JSON-based EPCIS-compatible schema

- Auditable Proofs: mirror node provides transaction receipts and hashes