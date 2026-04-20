# Cross Party Ruleset Compliance Templates

## What We're Building

Two composable Hedera Guardian policies — **GDST 1.2 Seafood Traceability** and **FSMA 204 Food Safety** — exported as importable `.policy` files with versioned JSON-LD schemas. Any Guardian project can import them and either run the compliance checks as-is, or chain the VCs into downstream policies (carbon footprint, tax credit, etc.).

### Deliverables

```
schemas/
├── gdst/                                    # 7 JSON-LD schemas (one per CTE)
├── fsma/                                    # 6 JSON-LD schemas (one per event type)
└── policies/
    ├── gdst-seafood-traceability.policy     # Importable Guardian policy
    └── fsma-204-food-safety.policy          # Importable Guardian policy
```

### Runtime

We use **Managed Guardian Service (MGS)** — a Hedera-managed multi-tenant Guardian instance. Our FastAPI backend authenticates via JWT against the MGS REST API and submits events alongside the existing HCS + smart contract flows.

The OpenAPI spec for MGS is checked in at [api-docs-yaml](api-docs-yaml).

## Spec Documents

> **Canonical spec lives in [`spec/`](spec/)** (symlink → `specs/001-guardian-integration/`).
> The numbered docs below are the original tutorial-style notes that seeded the
> spec; keep them for background until their content is fully represented in the
> spec, then replace each with a stub pointing at the spec. See
> [.specify/memory/constitution.md](../../.specify/memory/constitution.md)
> §Development Workflow #5.

| Doc | Role |
|-----|------|
| [spec/spec.md](spec/spec.md) | **Canonical:** user stories, requirements, acceptance criteria |
| [spec/plan.md](spec/plan.md) | **Canonical:** technical plan, file layout |
| [spec/data-model.md](spec/data-model.md) | **Canonical:** Rule Source Table, schema map |
| [spec/contracts/](spec/contracts/) | **Canonical:** MGS OpenAPI subset, client interface, VC schema, GPS checklist |
| [spec/research.md](spec/research.md) | **Canonical:** resolved open decisions |
| [spec/quickstart.md](spec/quickstart.md) | **Canonical:** local-dev runbook |
| [01-setup.md](01-setup.md) | Tutorial — superseded by `spec/plan.md` and `spec/quickstart.md` |
| [02-schemas-and-policies.md](02-schemas-and-policies.md) | Tutorial — superseded by `spec/spec.md` and `spec/data-model.md` |
| [03-gps-submission.md](03-gps-submission.md) | Tutorial — superseded by `spec/contracts/gps-submission-checklist.md` |

## Design Decisions

1. **Policies are the product.** The `.policy` exports and schemas are the primary deliverable. The FastAPI integration is how we use them internally.
2. **Composable by design.** Versioned schema IRIs, semantic VC types, and documented output interfaces so other Guardian projects can chain them via `trustChainBlock`.
3. **Dual compliance logic is intentional.** FastAPI rules provide fast rejection; Guardian policies duplicate them to produce auditable VCs. Both stay in sync.
4. **Circuit breaker for resilience.** If Guardian is temporarily down, the circuit breaker skips Guardian calls for 60 seconds so event recording isn't blocked.

---

## Glossary

| Term | Definition |
|------|------------|
| **CID** | IPFS content-addressed hash (`QmXyz...` or `bafy...`). Guardian uses IPFS internally for document storage. |
| **CTE** | Critical Tracking Event — a key supply chain event (Fishing, Landing, Processing, etc.) that must be recorded. |
| **DID** | Decentralized Identifier — W3C standard for self-owned identities, anchored on Hedera. Format: `did:hedera:testnet:z6Mk..._0.0.12345`. |
| **dMRV** | Digital Measurement, Reporting, and Verification. Guardian is a dMRV platform. |
| **EPC** | Electronic Product Code — unique product/batch identifier. Format: `urn:epc:class:lgtin:9506000.1233.a`. |
| **EPCIS** | Electronic Product Code Information Services — GS1 standard for supply chain events. |
| **FSMA 204** | FDA regulation requiring food traceability recordkeeping for high-risk foods. |
| **GDST** | Global Dialogue on Seafood Traceability — standard (v1.2) defining CTEs and KDEs for seafood traceability. |
| **HCS** | Hedera Consensus Service — topic-based messaging for immutable event recording. |
| **IRI** | Internationalized Resource Identifier — globally unique schema ID (e.g., `#GDSTFishingEvent&1.0.0`). |
| **IUU** | Illegal, Unreported, and Unregulated fishing. IUU fields in GDST events prove legal sourcing. |
| **KDE** | Key Data Element — required data fields within a CTE (e.g., vessel ID, catch area). |
| **Policy** | Guardian workflow definition encoding compliance rules, schema validation, and VC issuance. |
| **Policy Export** | Guardian's `.policy` format for importing/exporting complete policy definitions. The primary deliverable. |
| **Standard Registry (SR)** | Guardian's root authority role. Owns policies, approves users. Maps to `admin`. |
| **Trust Chain** | Sequence of VCs where each policy accepts VCs from a previous policy as input. |
| **VC** | Verifiable Credential — W3C tamper-proof digital certificate issued on compliance. |
| **VP** | Verifiable Presentation — bundle of VCs packaged for an auditor. |
