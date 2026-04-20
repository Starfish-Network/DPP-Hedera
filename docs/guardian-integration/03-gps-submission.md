# GPS Submission (Methodology Library)

## Overview

Guardian Policy Standards (GPS) govern how policies are accepted into the official Guardian Methodology Library. Submitting our policies there gives them visibility, credibility, and makes them discoverable by other Guardian projects that want to compose multi-policy workflows.

Reference: https://guardian.hedera.com/guardian/community-standards/guardian-policy-standards-gps

---

## 1. Proposal Lifecycle

Each policy (GDST, FSMA) goes through 6 stages:

```
Idea → Draft → Review → Accepted → Development → Final (merged into Methodology Library)
```

| Stage | What Happens | Who |
|-------|-------------|-----|
| Idea | Conceive policy concept | Starfish |
| Draft | Submit formal proposal with required docs | Starfish |
| Review | Community feedback; proposer addresses concerns | Starfish + Community |
| Accepted | Approved for development | Community |
| Development | Build policy, produce all required artifacts | Starfish |
| Final | Merged into Methodology Library, policy owner assigned | Community + Starfish |

We submit **two proposals** — one for GDST Seafood Traceability, one for FSMA 204 Food Safety.

---

## 2. Required Artifacts

Each proposal must include all of the following:

### 2.1 Policy Description

- Overview of what the policy does
- Workflow diagram showing the validation and VC issuance flow
- Explanatory video covering workflow and execution

**GDST workflow diagram:**

```
Event Submitted → Schema Validation → Compliance Check ─┬─ Pass → Issue GDSTComplianceCredential (VC)
                                                         └─ Fail → Reject
```

**FSMA workflow diagram:**

```
Event Submitted → Schema Validation → Compliance Check ─┬─ Pass → Issue FSMA204ComplianceCredential (VC)
                                                         └─ Fail → Reject
```

Detailed compliance rules for each event type are in [02-schemas-and-policies.md](02-schemas-and-policies.md).

### 2.2 User Guide

Implementation instructions for importing and using the policies:

1. How to import the `.policy` file into a Guardian instance
2. How to configure the Standard Registry
3. How to register users under each role
4. How to submit events through the policy
5. How to retrieve issued VCs
6. How to chain our VCs into downstream policies via `trustChainBlock`

### 2.3 Automated Workflow (Sample Data)

Valid sample input data that enables end-to-end policy execution without manual setup.

**GDST sample events** (one per CTE):

| Event Type | Sample File | Key Fields |
|-----------|-------------|------------|
| Fishing | `samples/gdst/fishing.json` | vessel, species: `TUN`, catch_area: `FAO71`, fishing_authorization |
| Landing | `samples/gdst/landing.json` | landing_authorization |
| Transshipment | `samples/gdst/transshipment.json` | transshipment_vessel, transshipment_authorization |
| OnVesselProcessing | `samples/gdst/on_vessel.json` | production_date |
| Processing | `samples/gdst/processing.json` | production_date |
| Shipping | `samples/gdst/shipping.json` | source/destination location, linking_kde |
| Aggregation | `samples/gdst/aggregation.json` | parent_items, child_items |

**FSMA sample events** (one per event type):

| Event Type | Sample File | Key Fields |
|-----------|-------------|------------|
| Creating | `samples/fsma/creating.json` | biz_location, quantity_list |
| Shipping | `samples/fsma/shipping.json` | ship_from, ship_to, items |
| Receiving | `samples/fsma/receiving.json` | received_at, items |
| Transforming | `samples/fsma/transforming.json` | facility, input_items, output_items |
| Packing | `samples/fsma/packing.json` | facility, container_id, input_items |
| Unpacking | `samples/fsma/unpacking.json` | facility, container_id, output_items |

Each sample must pass the corresponding policy's compliance checks and result in a VC being issued.

### 2.4 IPFS Documentation

All policy files published to IPFS with timestamps:

| Artifact | Format | IPFS |
|----------|--------|------|
| GDST policy | `.policy` | CID recorded at publish time |
| FSMA policy | `.policy` | CID recorded at publish time |
| GDST schemas (7) | `.json` | CID per schema |
| FSMA schemas (6) | `.json` | CID per schema |

Each policy version gets its own IPFS CID. Version history is maintained so previous versions remain accessible.

### 2.5 Compatibility

| Field | Value |
|-------|-------|
| Guardian version | Specify at development time (target: latest stable) |
| Hedera network | Testnet (development), Mainnet (production) |
| Dependencies | None — policies are self-contained |

Developed and tested against Managed Guardian Service (MGS). `.policy` exports remain compatible with self-hosted Guardian instances.

### 2.6 Maintenance Details

| Field | Value |
|-------|-------|
| Policy owner | Starfish Network |
| Contact | TBD |
| Update schedule | Aligned with GDST and FSMA regulatory updates |
| Support type | Community support |

---

## 3. Maintenance Obligations

Once accepted into the Methodology Library:

- **Issue response:** Address reported issues within 1 month
- **Update schedule:** Follow the declared schedule, or provide attestation that the policy is still valid
- **Archival risk:** Policies lapsing 3+ months past their update schedule without updates or attestation are archived

### Triggers for Policy Updates

| Trigger | Action |
|---------|--------|
| GDST releases a new version (e.g., 1.3) | Update GDST schemas and compliance rules, bump schema IRIs |
| FDA updates FSMA 204 requirements | Update FSMA schemas and compliance rules |
| Guardian releases a breaking version | Test compatibility, update if needed |
| Community reports a bug | Fix within 1 month |

Version updates require release notes detailing differences from the prior version.

---

## 4. Deliverables Checklist

Per-policy checklist for GPS submission:

- [ ] Policy description with overview
- [ ] Workflow diagram
- [ ] Explanatory video
- [ ] User guide (import, configure, use, chain)
- [ ] Sample input data (one per event type, all passing)
- [ ] `.policy` export file
- [ ] `.json` schema files
- [ ] All artifacts published to IPFS with CIDs recorded
- [ ] Guardian version compatibility declared
- [ ] Policy owner and contact info
- [ ] Update schedule declared
- [ ] Support type declared (community/commercial)

---

## 5. File Structure

```
samples/
├── gdst/
│   ├── fishing.json
│   ├── landing.json
│   ├── transshipment.json
│   ├── on_vessel.json
│   ├── processing.json
│   ├── shipping.json
│   └── aggregation.json
└── fsma/
    ├── creating.json
    ├── shipping.json
    ├── receiving.json
    ├── transforming.json
    ├── packing.json
    └── unpacking.json

docs/
├── gdst-policy-user-guide.md
└── fsma-policy-user-guide.md
```
