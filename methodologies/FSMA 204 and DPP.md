
## Methodology for FSMA 204 & Digital Product Passport Traceability

**Sections**

1. Purpose & Scope
2. Regulatory Alignment (FSMA 204 + DPP)
3. System Architecture
4. Event & Data Model
5. Validation Controls
6. Encryption & Confidentiality
7. Ledger Anchoring
8. Trace Reconstruction

### 1. Purpose and Scope

The FSMA 204 Compliance Traceability Solution is a cryptographically secure, distributed ledger-based system designed to capture and immutably record Critical Tracking Events (CTEs) throughout the food supply chain.

This methodology defines how the Starfish captures, validates, encrypts, and immutably anchors supply-chain Critical Tracking Events (CTEs) and associated Key Data Elements (KDEs) in compliance with **FSMA 204** requirements and **Digital Product Passport (DPP)** principles.

The methodology applies to product creation, transformation, packing, shipping, receiving, and unpacking events across regulated food supply chains.

### Regulatory Context

Developed to meet the stringent requirements of the Food Safety Modernization Act (FSMA) Section 204, this solution provides a robust framework for:

-   Capturing Key Data Elements and associated Critical Tracking Events across supply chain events
-   Ensuring data immutability and tamper-evidence
-   Facilitating rapid trace-back and trace-forward capabilities

---

### 2. Architectural Overview

The system is composed of:

* An **off-chain traceability application** responsible for:

  * Event validation
  * KDE enforcement
  * Encryption
  * Compliance evaluation
* An **on-chain integrity layer** implemented using the **Hedera Consensus Service (HCS)**

Supply-chain events are validated and encrypted prior to submission to the Hedera Consensus Service Topic.  The service provides immutable ordering, timestamps, and cryptographic integrity without exposing confidential business data. Events are queryable via the Hedera Mirror Node.

---

### 3. Event Model and CTE Coverage

The platform implements structured event types aligned with FSMA 204 Critical Tracking Events:

| Event Type   | CTE Classification |
| ------------ | ------------------ |
| Creating     | Creation / Harvest |
| Transforming | Transformation     |
| Packing      | Packing            |
| Shipping     | Shipping           |
| Receiving    | Receiving          |
| Unpacking    | Disaggregation     |

Each event type enforces mandatory KDEs.

### Key Data Elements (KDEs)

-   Event Timestamp
-   Location Identifiers
-   Product Identifiers (EPC)
-   Quantity and Unit of Measurement
-   Transaction Participants

---

### 4. Validation and Compliance Controls

All events undergo **pre-ledger validation** using deterministic schema enforcement and business rules prior to acceptance.

Controls include:

* Mandatory KDE presence
* Event-type specific field requirements
* EPC / lot identifier validation
* Quantity and unit normalization
* Temporal validation (UTC timestamps + offsets)

Events failing validation are rejected and **will not be written to the ledger**.

Once the events are recorded to the Hedera service, they provide an immutable audit trail and cryptographic verification of event authenticity.

---

### 5. Confidentiality and Encryption Model

To protect sensitive commercial and operational data:

* Event payloads are encrypted using **AES-GCM**
* Encryption keys are managed via a secure Key Management Service (KMS)
* Only authorized systems can decrypt and interpret event contents

The encrypted payload is submitted to a Hedera topic as the authoritative record.

Plaintext EPCIS data is never exposed on-chain.

---

### 6. Ledger Anchoring and Immutability

Each validated event is written to the Hedera Consensus Service, which provides:

* Network-agreed consensus timestamps
* Immutable sequencing
* Cryptographic running hashes
* Independent verification via Mirror Nodes

Once submitted, events cannot be altered, deleted, or reordered.

---

### 7. Event Hashing and Evidence Binding

For each event:

* A deterministic `event_hash` is computed from the canonical event representation
* The hash is included in the decrypted compliance view
* The hash binds:

  * Off-chain EPCIS data
  * On-chain encrypted payload
  * Ledger timestamp and sequence

This enables third-party auditors to verify integrity without accessing confidential payload contents.

---

### 8. Trace Reconstruction and Auditability

Authorized systems reconstruct product lineage by:

1. Querying Hedera Mirror Nodes for all topic messages
2. Decrypting authorized payloads
3. Rebuilding upstream and downstream relationships
4. Evaluating compliance status per event

The resulting trace provides:

* Full product lineage
* Time-ordered event history
* Compliance determination per CTE
* Cryptographic proof of integrity

---

### 9. Digital Product Passport and FSMA 204 Initiatives Alignment

This methodology supports Digital Product Passport requirements by ensuring:

* Persistent product identity (EPC / lot level)
* Verifiable lifecycle events
* Controlled data disclosure
* Machine-readable compliance evidence
* Cryptographically anchored provenance

By directly aligning with FSMA 204 requirements, the system provides a comprehensive digital approach to tracking food products from origin to destination. The implementation leverages the EPCIS 2.0 event standard, ensuring seamless interoperability across diverse supply chain platforms and technologies. Furthermore, the architecture supports emerging digital product passport initiatives, which aim to provide transparent, verifiable information about a product's entire journey. This approach goes beyond mere regulatory compliance, creating a framework that enables granular traceability, enhances food safety protocols, and provides stakeholders with unprecedented visibility into supply chain processes. By combining rigorous regulatory adherence with flexible, standards-based design, the solution offers a forward-looking approach to food traceability that can adapt to evolving regulatory landscapes and technological advancements.
