## Supplemental Methodology: DPP Evidence & Documentation Layer

### 1. Purpose and Scope

This supplemental methodology defines how **external files and documents/artifacts** are securely associated with Digital Product Passport (DPP) lifecycle events using **IPFS for decentralized storage** and **Hedera smart contracts for immutable association and access control**.

The methodology enables the attachment, retrieval, and verification of event-specific files (e.g., certificates, lab results, images, bills of lading, compliance documents) while preserving confidentiality, integrity, and auditability.

This methodology supplements the primary FSMA 204 & DPP Traceability Methodology and applies to all events recorded on-chain that require supporting documentation.
  
----------

### 2. Architectural Overview

The system introduces IPFS as a decentralized content layer, coordinated by a Hedera smart contract that acts as the **authoritative registry** for file–event associations.

**High-level flow:**

1.  A supply-chain event is validated and anchored on Hedera
    
2.  One or more files are encrypted and uploaded to IPFS
    
3.  The resulting IPFS Content Identifier (CID) is recorded on-chain
    
4.  The smart contract stores the encrypted data key associated with the CID
    
5.  Authorized users retrieve files by resolving:
    
    -   event hash → CID(s) → encrypted file → decryption key
        

All on-chain references are immutable and independently verifiable via Hedera Mirror Nodes .

----------

### 3. Event–File Association Model

Each file attachment is bound to a **single immutable event**, identified by its deterministic `eventHash`.

-   `eventHash`  
    A SHA-256 hash of the canonical event representation
    
-   `cid`  
    The IPFS Content Identifier of the encrypted file
    
-   `dataKey`  
    The encrypted symmetric key required to decrypt the file
    

This model ensures:

-   Files cannot exist independently of an event
    
-   Events can have zero, one, or many attached files
    
-   File integrity is guaranteed by IPFS content addressing
    
-   Event integrity is guaranteed by Hedera consensus
    

----------

### 4. Encryption and Confidentiality Model

All files are encrypted **before** being uploaded to IPFS.

**Encryption process:**

Layer

Mechanism

Purpose

File payload

AES-256-GCM

Confidentiality + integrity

Data key

Random per file

Limits blast radius

Key storage

On-chain (encrypted)

Controlled access

Ledger record

CID only

No plaintext exposure

Only encrypted data keys are stored on-chain. The ledger never contains plaintext files or plaintext encryption keys .

----------

### 5. Smart Contract Responsibilities

The ComplianceVerifier smart contract serves as the authoritative control plane for file attachments.

**Core responsibilities:**

-   Enforce one-to-one binding between event hash and compliance record
    
-   Register IPFS CIDs against an event
    
-   Store encrypted data keys per CID
    
-   Provide read-only retrieval of:
    
    -   compliance status
        
    -   attached file identifiers
        
    -   encrypted keys for authorized decryption
        

**Relevant functions include:**

-   `recordEvent`
    
-   `attachFile`
    
-   `getFiles`
    
-   `getDataKey`
    
-   `getComplianceStatus`
    

The contract does not perform encryption or file handling directly; it enforces **immutability, referential integrity, and auditability**.

----------

### 6. File Attachment Workflow

**Step-by-step process:**

1.  **Event anchoring**  
    A supply-chain event is validated and recorded on Hedera.
    
2.  **File encryption**  
    The backend encrypts the file using a per-file AES-256-GCM data key.
    
3.  **IPFS upload**  
    The encrypted file is uploaded to IPFS, producing a CID.
    
4.  **On-chain registration**  
    The backend calls `attachFile(eventHash, cid, dataKey)` on the smart contract.
    
5.  **Verification**  
    The association between event hash and CID becomes immutable and publicly verifiable.
    

----------

### 7. File Retrieval Workflow

**Authorized retrieval process:**

1.  Query the smart contract for files associated with an event hash
    
2.  Select a CID to retrieve
    
3.  Fetch the encrypted file from IPFS
    
4.  Retrieve the encrypted data key from the smart contract
    
5.  Decrypt the file off-chain
    
6.  Present the file in the DPP or compliance UI
    

This workflow ensures that:

-   IPFS alone is insufficient to access file contents
    
-   Hedera alone does not expose file contents
    
-   Both layers are required for meaningful access
    

----------

### 8. Auditability and Evidence Guarantees

This methodology provides the following guarantees:

-   **Immutability**  
    Event–file associations cannot be altered once recorded.
    
-   **Integrity**  
    Any modification to a file changes its CID and invalidates the linkage.
    
-   **Temporal ordering**  
    File attachments are chronologically anchored relative to the underlying event.
    
-   **Independent verification**  
    Third parties can verify:
    
    -   event existence
        
    -   attachment existence
        
    -   CID integrity  
        via Mirror Nodes and IPFS.
        

----------

### 9. Digital Product Passport and Industry Alignment

This supplemental methodology strengthens DPP implementations by enabling:

-   Persistent linkage of supporting evidence to lifecycle events
-   Decentralized, vendor-neutral document storage
-   Cryptographically verifiable claims
 
-   Selective disclosure of sensitive materials
    
-   Long-term retrievability beyond platform lifetimes
    

The result is a **DPP-compatible evidence layer** that complements event-level traceability with durable, verifiable documentation.

This evidence attachment methodology is designed to integrate seamlessly with existing industry certification, inspection, and audit workflows, including organic certifications, Good Agricultural Practices (GAP), sustainability standards, and third-party inspections. Certification documents, inspection reports, laboratory results, and attestations are produced today as discrete files by accredited bodies and reviewed during audits or recalls. By encrypting these files, storing them in decentralized storage, and immutably associating them with specific supply-chain events, the system preserves existing workflows while adding cryptographic integrity, temporal anchoring, and verifiable linkage to product lifecycle data. This approach does not replace established certification processes or authorities; rather, it enhances them by ensuring that supporting documentation remains tamper-evident, persistently retrievable, and directly attributable to the relevant production, transformation, or shipment events. As a result, regulators, auditors, and trading partners can verify the presence, timing, and integrity of certifications and inspections without requiring changes to how those documents are created, issued, or governed today.
