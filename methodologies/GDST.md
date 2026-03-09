# Methodology for GDST 1.2 Seafood Traceability

**Key Data Elements, Critical Tracking Events & Schema Definitions**
*Starfish Platform | Hedera Integration Service*

---

## Sections

1. [Purpose and Scope](#1-purpose-and-scope)
2. [Architectural Overview](#2-architectural-overview)
3. [Master Data Schema Definitions](#3-master-data-schema-definitions)
4. [CTE Coverage and Event Model](#4-cte-coverage-and-event-model)
5. [KDE Specifications by CTE](#5-kde-specifications-by-cte)
6. [Validation and Compliance Controls](#6-validation-and-compliance-controls)
7. [Confidentiality and Encryption Model](#7-confidentiality-and-encryption-model)
8. [Ledger Anchoring and File Attestation](#8-ledger-anchoring-and-file-attestation)
9. [Trace Reconstruction and Auditability](#9-trace-reconstruction-and-auditability)
10. [GDST Standard Alignment Summary](#10-gdst-standard-alignment-summary)
11. [Glossary](#glossary)

---

## 1. Purpose and Scope

This methodology defines how the Starfish platform captures, validates, encrypts, and immutably records Global Dialogue on Seafood Traceability (GDST) Critical Tracking Events (CTEs) and associated Key Data Elements (KDEs) in compliance with the **GDST Core Normative Standard 1.2**.

The GDST 1.2 standard establishes internationally agreed minimum data elements and technical formats for interoperable digital seafood traceability, covering both wild-caught and aquaculture supply chains. Built on GS1 EPCIS 2.0 with JSON-LD as the data format, GDST provides a common language for sharing KDEs between participating traceability systems.

This document covers:

- Master Data schema definitions for vessels, facilities, products, and parties
- Event-level KDE and CTE specifications for wild-caught and aquaculture supply chains
- Validation and compliance controls applied prior to ledger submission
- Encryption, ledger anchoring, and auditability mechanisms
- Integration with the Hedera Consensus Service (HCS) and IPFS for immutable, verifiable evidence

### Regulatory and Standards Context

The GDST 1.2 standard is the current authoritative release, having evolved from version 1.0 (2020) through 1.1 (2022) and 1.2 (2023).

| Dimension | Description |
|---|---|
| Data Format | JSON-LD (EPCIS 2.0 aligned), replacing earlier XML-based formats |
| Communication Protocol | GS1 Digital Link, mandated as the single interoperability protocol in v1.1+ |
| Identification Standard | GS1 EPCIS / CBV with GDST extensions (`gdst:` and `cbvmda:` namespaces) |
| Supply Chain Scope | Wild-caught seafood and aquaculture (feed traceability to feed mill level) |
| Compliance Model | Conditional: a CTE/KDE is required only when the event occurs or the information exists |

---

## 2. Architectural Overview

The Starfish GDST integration follows a stateless, two-layer architecture. GDST events are submitted via dedicated API endpoints, validated and encrypted off-chain, and then committed to the Hedera Consensus Service. File attachments (e.g., catch certificates, fishing authorisations) are stored on IPFS with CIDs registered on-chain via the `ComplianceVerifier` smart contract.

### Processing Pipeline

| Step | Component | Action |
|---|---|---|
| 1. Receive | FastAPI (`/api/gdst/events`) | Validates event JSON against GDST Pydantic schema |
| 2. Validate | Off-chain validation layer | Enforces mandatory KDEs, EPC format, temporal and spatial rules |
| 3. Encrypt | AES-256-GCM + KMS | Encrypts payload; data key wrapped by Cloud KMS |
| 4. Anchor | Hedera Consensus Service | Encrypted payload committed to HCS topic with consensus timestamp |
| 5. Comply | ComplianceVerifier contract | Compliance status recorded on-chain via `/api/gdst/compliance/check` |
| 6. Attach | IPFS + Smart Contract | Supporting files encrypted, uploaded to IPFS; CID registered on-chain |
| 7. Query | Mirror Node + `/api/trace/{epc}` | Full lineage graph reconstructed from decrypted event history |

---

## 3. Master Data Schema Definitions

Master data represents attributes that are static or slowly-changing relative to event-level data. Per GDST guidance, master data is communicated using GS1 Web Vocab JSON-LD and should be maintained in a master data header rather than repeated in individual events.

### 3.1 Vessel Master Data (Wild-Caught)

Vessel master data captures static attributes about harvesting and transshipment vessels. The vessel's IMO Number is mandatory where assigned. Vessel data is linked to fishing, transshipment, and landing events via the vessel's GLN or `sgln` identifier.

| KDE | JSON-LD Attribute | Format / Constraint | Required |
|---|---|---|---|
| Vessel Name | `cbvmda:vesselName` | String; must correspond to IMO registry name | Required |
| Vessel ID | `cbvmda:vesselID` | String; vessel registration number | Required |
| IMO Number | `cbvmda:imoNumber` | 7-digit numeric string per IMO standard | Required if assigned |
| Vessel Flag State | `cbvmda:vesselFlagState` | ISO 3166-1 alpha-2 country code | Required |
| Vessel Type | `cbvmda:vesselType` | Controlled vocabulary (e.g., fishing, transshipment) | Conditional |
| Satellite Tracking Authority | `gdst:satelliteTrackingAuthority` | URI of VMS/AIS authority | Conditional |
| Home Port | `cbvmda:homePort` | Port name / UN/LOCODE | Recommended |
| Public Vessel Registry | `gdst:publicVesselRegistryHyperlink` | URL to official registry listing | Recommended |
| Information Provider | `cbvmda:informationProvider` | PGLN of party recording the data | Required |

### 3.2 Facility / Location Master Data

Facilities include landing ports, processing plants, cold stores, and distribution centres. Each location is assigned a GLN and expressed as a `sgln` identifier within EPCIS event `bizLocation` and `readPoint` fields.

| KDE | JSON-LD Attribute | Format / Constraint | Required |
|---|---|---|---|
| Location Name | `gs1:organizationName` | String | Required |
| GLN / SGLN | `@id` (sgln URN) | `urn:epc:id:sgln:<GS1Prefix>.<LocationRef>.<Extension>` | Required |
| Country Code | `gs1:countryCode` | ISO 3166-1 alpha-2 | Required |
| Address | `gs1:streetAddress`, `gs1:city`, `gs1:postalCode` | String fields per GS1 Web Vocab | Recommended |
| Geo-coordinates | `geo:<lat>,<lng>` | WGS 84 decimal degrees | Recommended |
| Chain-of-Custody Certification | `gdst:certificationList` | Certificate type + value URN | Conditional |
| Information Provider | `cbvmda:informationProvider` | PGLN of party recording the data | Required |

### 3.3 Product / Trade Item Master Data

Product master data captures species-level and trade item-level attributes referenced by EPC identifiers (LGTIN or SGTIN) in event payloads. Scientific name and product form are essential for regulatory alignment with SIMP and other government programmes.

| KDE | JSON-LD Attribute | Format / Constraint | Required |
|---|---|---|---|
| GTIN | `@id` (lgtin / sgtin URN) | `urn:epc:class:lgtin:<GS1Prefix>.<ItemRef>.<Lot>` | Required |
| Species (Common Name) | `cbvmda:speciesForFisheryStatisticsPurposesName` | ASFIS common name | Required |
| Species (Scientific Name / Code) | `cbvmda:speciesForFisheryStatisticsPurposesCode` | FAO ASFIS 3-alpha code | Required |
| Product Form / Processing State | `cbvmda:tradeItemConditionCode` | GS1 CBV controlled vocabulary | Required |
| Country of Origin | `cbvmda:countryOfOrigin` | ISO 3166-1 alpha-2 code | Required |
| Production Method | `cbvmda:productionMethodForFishAndSeafoodCode` | `WILD_CAUGHT` or `AQUACULTURE` | Required |
| Product Net Weight (UOM) | `gs1:netWeight` + `gs1:unitCode` | Numeric + UN/CEFACT unit code | Recommended |
| Expiry / Production Date | `gs1:itemExpirationDate` | ISO 8601 date | Conditional |

---

## 4. CTE Coverage and Event Model

GDST defines CTEs as the minimum set of supply chain events at which KDEs must be captured. The platform implements all GDST-defined CTEs for both wild-caught and aquaculture supply chains. Events are structured as EPCIS 2.0 JSON-LD documents, validated against Pydantic schemas, and submitted via the `/api/gdst/events` endpoint.

### 4.1 Wild-Caught Supply Chain CTEs

| CTE | GDST Business Step URN | EPCIS Event Type | Platform Event Type |
|---|---|---|---|
| Fishing (Harvest) | `urn:gdst:bizstep:fishing` | ObjectEvent (ADD) | `Fishing` |
| On-Vessel Processing | `urn:epcglobal:cbv:bizstep:commissioning` | TransformationEvent | `OnVesselProcessing` |
| Transshipment | `urn:gdst:bizstep:transshipment` | ObjectEvent (OBSERVE) | `Transshipment` |
| Landing / Offload | `urn:gdst:bizstep:landing` | ObjectEvent (OBSERVE) | `Landing` |
| Processing (Ashore) | `urn:epcglobal:cbv:bizstep:commissioning` | TransformationEvent | `Processing` |
| Aggregation | `urn:epcglobal:cbv:bizstep:packing` | AggregationEvent (ADD) | `Packing` |
| Disaggregation | `urn:epcglobal:cbv:bizstep:unpacking` | AggregationEvent (DELETE) | `Unpacking` |
| Shipping | `urn:epcglobal:cbv:bizstep:shipping` | ObjectEvent (OBSERVE) | `Shipping` |
| Receiving | `urn:epcglobal:cbv:bizstep:receiving` | ObjectEvent (OBSERVE) | `Receiving` |

### 4.2 Aquaculture Supply Chain CTEs

| CTE | GDST Business Step URN | EPCIS Event Type | Platform Event Type |
|---|---|---|---|
| Farm Harvest | `urn:gdst:bizstep:farmHarvest` | ObjectEvent (ADD) | `FarmHarvest` |
| On-Farm Processing | `urn:epcglobal:cbv:bizstep:commissioning` | TransformationEvent | `OnFarmProcessing` |
| Processing (Post-Farm) | `urn:epcglobal:cbv:bizstep:commissioning` | TransformationEvent | `Processing` |
| Aggregation | `urn:epcglobal:cbv:bizstep:packing` | AggregationEvent (ADD) | `Packing` |
| Disaggregation | `urn:epcglobal:cbv:bizstep:unpacking` | AggregationEvent (DELETE) | `Unpacking` |
| Shipping | `urn:epcglobal:cbv:bizstep:shipping` | ObjectEvent (OBSERVE) | `Shipping` |
| Receiving | `urn:epcglobal:cbv:bizstep:receiving` | ObjectEvent (OBSERVE) | `Receiving` |

---

## 5. KDE Specifications by CTE

All KDEs use GDST-defined namespaces (`gdst:`, `cbvmda:`) within EPCIS 2.0 JSON-LD. Fields marked **Required** must be present for an event to pass pre-ledger validation. **Conditional** fields are required when the underlying data exists or the situation applies, per the GDST conditionality rule.

### 5.1 Fishing Event KDEs

The Fishing Event records the harvest of seafood from the wild. It is an `ObjectEvent` with `action: ADD`. Each unique harvesting session (vessel, gear, date, catch area) should generate a distinct Fishing Event.

| KDE | JSON-LD / EPCIS Field | Format | Required |
|---|---|---|---|
| Event Time | `eventTime` | ISO 8601 UTC with offset | Required |
| Event Timezone Offset | `eventTimeZoneOffset` | `+HH:MM` or `-HH:MM` | Required |
| EPC / Product Identifier | `quantityList[].epcClass` | LGTIN URN | Required |
| Quantity + UOM | `quantityList[].quantity` + `uom` | Numeric + UN/CEFACT code (e.g., `KGM`) | Required |
| Vessel Location (Read Point) | `readPoint.id` | `geo:<lat>,<lng>` or sgln URN | Required |
| Fishing Vessel (Biz Location) | `bizLocation.id` | sgln URN referencing vessel master data | Required |
| Catch Area (FAO Zone) | `ilmd.cbvmda:catchArea` | FAO major fishing area code (e.g., `FAO.71`) | Required |
| Fishing Gear Type | `ilmd.cbvmda:fishingGearTypeCode` | FAO ISSCFG gear code | Required |
| Species Code (ASFIS) | `ilmd.cbvmda:speciesForFisheryStatisticsPurposesCode` | FAO 3-alpha code | Required |
| Fishing Authorization | `ilmd.gdst:fishingAuthorization` | Authorization document reference | Required |
| Vessel Catch Information | `ilmd.cbvmda:vesselCatchInformationList` | Nested catch object | Required |
| Product Owner | `gdst:productOwner` | PGLN URN of owning party | Required |
| Information Provider | `cbvmda:informationProvider` | PGLN URN of recording party | Required |
| Human Welfare Policy | `gdst:certificationList` (type: `urn:gdst:certType:humanPolicy`) | Certificate URN | Required |
| Economic Zone (EEZ) | `ilmd.cbvmda:economicZone` | ISO EEZ code or FAO area | Conditional |
| Sub-National Fishing Area | `ilmd.cbvmda:subnationalPermitArea` | String | Conditional |
| Chain-of-Custody Certificate | `gdst:certificationList` (CoC cert) | Certificate type URN + value | Conditional |

### 5.2 Transshipment Event KDEs

Transshipment records the transfer of product from one vessel to another at sea before landing. It is an `ObjectEvent` with `action: OBSERVE`. Transshipment events are conditional — only required when transshipment actually occurs.

| KDE | JSON-LD / EPCIS Field | Format | Required |
|---|---|---|---|
| Event Time | `eventTime` | ISO 8601 UTC with offset | Required |
| EPC / Product Identifier | `epcList` or `quantityList` | LGTIN or SGTIN URN | Required |
| Quantity + UOM | `quantityList[].quantity` + `uom` | Numeric + UN/CEFACT code | Required |
| Transshipment Location (Read Point) | `readPoint.id` | `geo:<lat>,<lng>` | Required |
| Transshipment Vessel (Biz Location) | `bizLocation.id` | sgln URN of transshipment vessel | Required |
| Source Fishing Vessel | `sourceList` (owning_party) | PGLN URN of origin vessel owner | Required |
| Destination (Receiving Party) | `destinationList` | PGLN or sgln URN | Required |
| Transshipment Authorization | `ilmd.gdst:transshipmentAuthorization` | Document reference | Required |
| Vessel Flag State | `cbvmda:vesselFlagState` (from master data) | ISO alpha-2 country code | Required |
| Product Owner | `gdst:productOwner` | PGLN URN | Required |
| Information Provider | `cbvmda:informationProvider` | PGLN URN | Required |

### 5.3 Landing Event KDEs

The Landing Event represents the first time wild-harvested products reach land. It is mandatory for all wild-caught product and uses `bizStep: urn:gdst:bizstep:landing`.

| KDE | JSON-LD / EPCIS Field | Format | Required |
|---|---|---|---|
| Event Time | `eventTime` | ISO 8601 UTC with offset | Required |
| EPC / Product Identifier | `epcList` or `quantityList` | LGTIN or SGTIN URN | Required |
| Quantity + UOM | `quantityList[].quantity` + `uom` | Numeric + UN/CEFACT code | Required |
| Port of Landing (Biz Location) | `bizLocation.id` | sgln URN for port facility | Required |
| Source Vessel | `sourceList` (location) | sgln URN of fishing / transshipment vessel | Required |
| Landing Authorization | `ilmd.gdst:landingAuthorization` | Authorization authority + document number | Required |
| Link to Fishing Event (EPC) | `epcList` (matching LGTIN) | LGTIN URN from corresponding Fishing Event | Required |
| Product Owner | `gdst:productOwner` | PGLN URN (seller at time of landing) | Required |
| Information Provider | `cbvmda:informationProvider` | PGLN URN | Required |
| IMO Number (Vessel) | `cbvmda:imoNumber` (from master data) | 7-digit string | Conditional |

### 5.4 Processing Event KDEs

Processing events are `TransformationEvent`s that record the conversion of input products (e.g., whole fish) into output products (e.g., fillets). Input and output EPCs are different identifiers, capturing the transformation of traceable identity.

| KDE | JSON-LD / EPCIS Field | Format | Required |
|---|---|---|---|
| Event Time | `eventTime` | ISO 8601 UTC with offset | Required |
| Input Products | `inputQuantityList[].epcClass` + `quantity` + `uom` | LGTIN URNs of inputs | Required |
| Output Products | `outputQuantityList[].epcClass` + `quantity` + `uom` | LGTIN URNs of outputs | Required |
| Processing Facility (Biz Location) | `bizLocation.id` | sgln URN | Required |
| Transformation ID | `transformationID` | UUID or business-assigned string | Required |
| Processing Type / Form | `ilmd.cbvmda:tradeItemConditionCode` | GS1 CBV processing description | Required |
| Species Code | Derived from input EPC master data | FAO 3-alpha code | Required |
| Product Owner | `gdst:productOwner` | PGLN URN | Required |
| Information Provider | `cbvmda:informationProvider` | PGLN URN | Required |
| Chain-of-Custody Certificate | `gdst:certificationList` | Certificate type URN + value | Conditional |

### 5.5 Shipping and Receiving Event KDEs

Shipping and Receiving are paired `ObjectEvent`s that record the transfer of custody between supply chain parties. They are required at each point where product changes hands between organisations.

| KDE | JSON-LD / EPCIS Field | Shipping | Receiving |
|---|---|---|---|
| Event Time | `eventTime` | Required | Required |
| EPC / Product Identifiers | `epcList` or `quantityList` | Required | Required |
| Quantity + UOM | `quantityList[].quantity` + `uom` | Required | Required |
| Ship-From Location | `bizLocation.id` / `sourceList` | Required | Derived |
| Ship-To Location | `destinationList` | Required | Required (as `bizLocation`) |
| Bill of Lading / Reference | `bizTransactionList` (bol) | Recommended | Recommended |
| Chain-of-Custody Certificate | `gdst:certificationList` | Conditional | Conditional |
| Product Owner | `gdst:productOwner` | Required | Required |
| Information Provider | `cbvmda:informationProvider` | Required | Required |

---

## 6. Validation and Compliance Controls

All GDST events undergo deterministic pre-ledger validation before being submitted to Hedera. Events that fail validation are rejected and never written to the ledger.

| Control Layer | Description |
|---|---|
| Schema Validation | Pydantic models enforce the mandatory field structure for each GDST event type. Missing required KDEs cause immediate rejection. |
| EPC Format Validation | All EPC and PGLN identifiers are validated against GS1 URN patterns. |
| Temporal Validation | `eventTime` must be a valid ISO 8601 UTC timestamp. Timezone offsets must be syntactically valid. |
| Species Code Validation | FAO ASFIS 3-alpha species codes are validated against the authoritative code list. |
| Catch Area Validation | FAO fishing area codes (e.g., `FAO.71`) are validated against the FAO Major Fishing Areas registry. |
| Quantity Normalisation | Quantity values must be positive numeric; UOM codes must be valid UN/CEFACT codes. |
| CTE Conditionality | Conditional CTEs (e.g., Transshipment, On-Vessel Processing) are only required when the underlying event occurred. The validator enforces this per-event-type rule. |
| Certification Validation | Where certificates are provided, the `certType` URN must match a recognised GDST certificate type vocabulary. |
| Compliance Check (On-Chain) | After submission, a compliance determination is recorded on-chain via `/api/gdst/compliance/check`, calling `recordEvent()` on the `ComplianceVerifier` smart contract. |

---

## 7. Confidentiality and Encryption Model

GDST events frequently contain commercially sensitive data (catch volumes, vessel routes, counterparty identities). All event payloads are encrypted prior to submission to Hedera, ensuring no plaintext business data is ever exposed on-chain.

| Layer | Method | Purpose |
|---|---|---|
| Payload Encryption | AES-256-GCM | Authenticated symmetric encryption of the full JSON-LD event payload |
| Data Key | Random 256-bit per event | Ephemeral key ensures each event is independently encrypted |
| Key Wrapping | Cloud KMS (AWS KMS or GCP KMS) | Data encryption key is envelope-encrypted; plaintext key never stored |
| Additional Authenticated Data (AAD) | Event type, event time, facility, bizStep | Binds ciphertext to event context; prevents ciphertext substitution attacks |
| Content Hash | SHA-256 (Base64) | Deterministic hash of canonical event for ledger verification |
| Schema Version | `ver: 2` envelope field | Identifies the current encryption schema generation |

Plaintext GDST event data is never exposed on-chain. Authorised systems decrypt event payloads using the KMS-managed data key when reconstructing lineage or producing compliance reports.

---

## 8. Ledger Anchoring and File Attestation

### 8.1 Hedera Consensus Service Anchoring

Each validated GDST event is committed to the designated HCS topic. Hedera provides:

- Network-agreed consensus timestamps (tamper-evident ordering)
- Immutable sequencing — events cannot be altered, deleted, or reordered after submission
- Cryptographic running hashes over the topic message sequence
- Independent verification via the Hedera Mirror Node REST API

The `event_hash` (SHA-256 of the canonical event) is included in the compliance view and serves as the binding identifier between the off-chain GDST/EPCIS data, the on-chain encrypted payload, and the on-chain compliance record.

### 8.2 IPFS File Attestation

Supporting documents such as catch certificates, fishing authorisations, landing authorisations, and chain-of-custody certificates may be attached to GDST events.

| Step | Action |
|---|---|
| 1. Encrypt File | File is encrypted server-side using the event's data key before upload |
| 2. Upload to IPFS | Encrypted file uploaded to IPFS; a content identifier (CID) is returned |
| 3. Register On-Chain | `attachFile(eventHash, cid, encryptedDataKey)` called on `ComplianceVerifier` |
| 4. Retrieve | Authorised parties call `getFiles(eventHash)` to list CIDs, then download and decrypt via `/api/gdst/events/{hash}/files/{cid}/download` |

---

## 9. Trace Reconstruction and Auditability

Authorised systems reconstruct the full product lineage for any EPC by querying `/api/trace/{epc}` or `/api/gdst/events`. The reconstruction process:

1. Queries the Hedera Mirror Node for all messages in the relevant HCS topic
2. Filters and decrypts event payloads referencing the target EPC or its upstream/downstream linked EPCs
3. Rebuilds the directed acyclic graph (DAG) of upstream inputs and downstream outputs across all CTEs
4. Evaluates compliance status per event using on-chain `ComplianceVerifier` records
5. Returns a trace graph with nodes (product lots, vessels, facilities) and edges (event relationships) for UI visualisation and audit export

The resulting trace provides:

- Full wild-caught or aquaculture lineage from harvest to consumer
- Time-ordered event history with Hedera-attested consensus timestamps
- Per-CTE compliance determination with on-chain proof
- Cryptographic proof of integrity via `event_hash` binding
- Direct links to Hedera HashScan transaction receipts for independent verification

---

## 10. GDST Standard Alignment Summary

| Capability | GDST / GS1 Alignment |
|---|---|
| JSON-LD event format | EPCIS 2.0 JSON-LD; GDST 1.2 mandatory data format |
| EPC / LGTIN identifiers | GS1 URN format; `gdst:` and `cbvmda:` namespace extensions |
| Wild-caught CTE coverage | All 9 GDST wild-caught CTEs (Fishing through Receiving) |
| Aquaculture CTE coverage | All 7 GDST aquaculture CTEs (Farm Harvest through Receiving) |
| Master data schema | GS1 Web Vocab JSON-LD; `cbvmda:` vessel, facility, and product attributes |
| Communication protocol | GS1 Digital Link (GDST 1.1+ mandatory protocol) |
| Conditional KDE enforcement | CTE/KDE required only when event occurs or data exists (GDST conditionality rule) |
| Species codes | FAO ASFIS 3-alpha codes via `cbvmda:speciesForFisheryStatisticsPurposesCode` |
| Fishing area codes | FAO Major Fishing Area codes via `cbvmda:catchArea` |
| Certification records | `gdst:certificationList` with typed URN certificate references |
| Immutable ledger anchoring | Hedera Consensus Service |
| Encrypted storage | AES-256-GCM; no plaintext KDEs stored on-chain |
| File attestation | IPFS + on-chain CID registry via `ComplianceVerifier` |
| SIMP compatibility | Fishing, Transshipment, and Landing KDEs aligned with SIMP PGA record fields |

---

## Glossary

| Term | Definition |
|---|---|
| AAD | Additional Authenticated Data — metadata bound to an AES-GCM ciphertext to prevent substitution attacks |
| ASFIS | Aquatic Sciences and Fisheries Information System — FAO species code standard |
| CBV | GS1 Core Business Vocabulary — standard vocabulary for EPCIS business steps and transaction types |
| CID | Content Identifier — IPFS unique address derived from the hash of file content |
| CTE | Critical Tracking Event — a defined supply chain event at which KDEs must be captured |
| DAG | Directed Acyclic Graph — data structure representing product lineage relationships |
| EPC | Electronic Product Code — GS1 identifier for a traceable unit (instance or class level) |
| EPCIS | Electronic Product Code Information Services — GS1 standard for sharing supply chain event data |
| FAO | Food and Agriculture Organization of the United Nations |
| GDST | Global Dialogue on Seafood Traceability — international standard for digital seafood traceability |
| GLN | Global Location Number — GS1 identifier for a physical or logical location |
| HCS | Hedera Consensus Service — distributed ledger service providing immutable event ordering and timestamps |
| IMO | International Maritime Organization — issues unique 7-digit vessel identification numbers |
| IPFS | InterPlanetary File System — decentralised content-addressed file storage network |
| KDE | Key Data Element — a specific data field required to be captured at a CTE |
| KMS | Key Management Service — cloud service for managing and protecting cryptographic keys |
| LGTIN | Lot-based GTIN — GS1 EPC class identifier for a product class and lot combination |
| PGLN | Party GLN — GLN used to identify a legal entity or supply chain party |
| SGLN | Serialised GLN — GLN with an extension component identifying a specific sub-location |
| SIMP | Seafood Import Monitoring Program — US NOAA import traceability and reporting requirement |
| UOM | Unit of Measurement — UN/CEFACT unit code (e.g., `KGM` for kilogram) |
| VMS | Vessel Monitoring System — satellite-based system for tracking and recording vessel positions |
