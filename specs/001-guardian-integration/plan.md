# Implementation Plan: Guardian Integration — GDST & FSMA 204 Compliance Policies

**Branch**: `001-guardian-integration` | **Date**: 2026-04-20 | **Spec**: [spec.md](spec.md)
**Input**: [spec.md](spec.md) + legacy tutorial docs in [docs/guardian-integration/](../../docs/guardian-integration/)

## Summary

Integrate two new Guardian policies (GDST 1.2, FSMA 204) with the existing FastAPI event flow via the Managed Guardian Service (MGS). Ship the policies as importable `.policy` exports. Preserve HCS + smart-contract authoritative recording; add Guardian as a non-blocking compliance-VC layer protected by a circuit breaker. Submit both policies to the Guardian Methodology Library under GPS.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI, Pydantic v2, httpx (async HTTP client for MGS), a circuit-breaker library or hand-rolled breaker (decision in `research.md`), respx or httpx_mock for test fixtures.
**Storage**: N/A for Guardian integration itself (Guardian stores policy documents on its side); event hashes already persisted via `ComplianceVerifier` contract and HCS topic.
**Testing**: pytest, reusing [api/app/tests/conftest.py](../../api/app/tests/conftest.py). New suite under `api/app/tests/integration/guardian/`. Shared fixtures under `api/app/tests/fixtures/guardian/` which are the same files as `samples/gdst/` and `samples/fsma/` referenced by GPS submission.
**Target Platform**: Linux server (FastAPI backend); `.policy` exports target any Guardian 2.x-compatible runtime including self-hosted.
**Project Type**: Web-service extension (new service module + new routes on existing FastAPI app; no frontend changes).
**Performance Goals**: `/events` p95 latency must not regress by more than 5% with Guardian enabled (SC-003). `GET /guardian/*/vc/{event_hash}` returns `200` within 30 s of submission for 95% of events; the hard ceiling is 5 min before the event is flagged `manual_review` (SC-007). Guardian submit is async/fire-and-forget on the hot path; VC retrieval is on-demand.
**Constraints**: Guardian calls must never block HCS recording (Constitution §IV). `.policy` exports must be self-contained (Constitution §II). VCs are immutable once issued — corrections are append-only superseding credentials, never mutations (spec §FR-014). `credentialSubject` embeds the full event payload verbatim (FR-015); there is no v1 PII-minimization layer. Operator onboarding — including consent capture for FR-015 — is **out of scope for v1** and is handled out-of-band by the deployer via the MGS portal and a local signed consent record (see deployment runbook).
**Scale/Scope**: Single MGS tenant initially. Two policies. 13 schemas total. 3 new API endpoints under `/guardian/*` (`/health`, `/gdst/vc/{event_hash}`, `/fsma/vc/{event_hash}`), plus the optional `?history=true` query on the VC-retrieval endpoints (FR-007). Operator onboarding endpoints are deferred to v2. New service module (`guardian_client.py`), schema mapper (`schema_mapper.py`), config additions. No reconciler worker and no backlog table in v1 — breaker-skipped events are log-only (FR-006).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|-----------|-------|--------|
| I. Policies are the product | `.policy` exports + JSON-LD schemas are first-class deliverables, tracked alongside code in FR-001/FR-002. | Pass |
| II. Composable by design | Semver'd schema IRIs (FR-012); documented VC "Guaranteed" fields in `data-model.md`; SR DID as stable trust anchor. | Pass |
| III. Dual compliance logic | Rule Source Table in `data-model.md` is the single source both the Pydantic rules and the Guardian policy reference. Workflow rule in Constitution §Development Workflow #4 enforces lockstep PRs. | Pass |
| IV. Core flows never block | FR-005, FR-006, Story 3; circuit breaker specified; `/guardian/health` exposes breaker state. | Pass |
| V. Test-First | FR-013; scaffold tests land with this plan under `api/app/tests/integration/guardian/`; rule-per-test coverage is SC-002. | Pass |
| VI. Authoritative contracts | OpenAPI subset for MGS boundary under `contracts/mgs-boundary.openapi.yaml`; typed Python interface in `contracts/guardian-client.md`; JSON schemas under `schemas/` at repo root. | Pass |

No violations. Complexity Tracking table remains empty.

### Post-design re-check (2026-04-20, after `/speckit-clarify`)

The 5 clarifications recorded in [spec.md §Clarifications](spec.md) introduced FR-014 (append-only superseding), FR-015 (full-payload `credentialSubject`), SC-007 (30 s / 5 min retrieval window), an idempotency rule on FR-004, and a log-only breaker-recovery stance on FR-006. Re-checking against all six principles:

| Principle | Re-check after clarifications | Status |
|-----------|-------------------------------|--------|
| I. Policies are the product | Append-only / `supersedes` is modeled inside `credentialSubject` — no Starfish-specific machinery required to consume the chain. `.policy` exports remain self-contained. | Pass |
| II. Composable by design | `GuaranteedMetadata` (now formalized in `contracts/vc-output.schema.json`) stays stable; downstream trust-chains continue to filter on `issuer` + `complianceStatus == "compliant"` without revocation-list fetches. | Pass |
| III. Dual compliance logic | No rule additions; clarifications touch VC representation and recovery semantics, not compliance rules. Rule Source Table unchanged. | Pass |
| IV. Core flows never block | Log-only recovery keeps the hot path lean. Idempotency short-circuit on duplicate submissions prevents accidental breaker trips. | Pass (stronger) |
| V. Test-First | New SC-007 thresholds and the `?history=true` behavior add ≥4 new contract tests (already listed in `contracts/guardian-client.md` invariants) that must land before implementation. | Pass |
| VI. Authoritative contracts | `contracts/vc-output.schema.json` now encodes `supersedes` + `superseded` + `policyVersion` + `issuedAt` via `GuaranteedMetadata`; `contracts/guardian-client.md` encodes the `history` param and `VCRetrievalStatus`. Prose in `data-model.md` links to both. | Pass |

No principle is in tension. Complexity Tracking table remains empty.

## Phase 0 — Research

Produced in [research.md](research.md). Resolves the four open decisions from Constitution §Open Decisions:

1. **Environment topology** (testnet vs prod tenant strategy)
2. **Identity lifecycle** (DID key rotation)
3. **Resilience** (failure taxonomy for the 60 s breaker)
4. **Versioning** (policy version pinning on the client side)

Also records the choice of circuit-breaker library vs hand-rolled, and the HTTP mocking library (`respx` vs `httpx_mock`).

## Phase 1 — Design

Produced in [data-model.md](data-model.md), [quickstart.md](quickstart.md), and [contracts/](contracts/).

### Data model deliverables

- `data-model.md` §Entities: GDST CTE, FSMA event, VC, SR, Operator, **Policy Registry (`PolicyConfig`)**.
- `data-model.md` §Rule Source Table: per-event-type rules cross-referencing `compliance.py` and Guardian policy blocks.
- `data-model.md` §Schema Map: one row per JSON-LD schema with source Pydantic model.
- **Per-policy config lives in code, not scattered env vars**: `api/app/service/guardian_policies.py` holds a frozen `PolicyConfig` per compliance policy. Drives a single generic `schema_mapper.to_credential_subject(event, policy, ...)` mapper and a single policy-slug-parameterised `GET /guardian/{slug}/vc/{event_hash}` route. Rationale + alternatives in [research.md §8](research.md); invariants in [data-model.md §Policy Registry](data-model.md).

### Contract deliverables

- `contracts/mgs-boundary.openapi.yaml` — subset of MGS endpoints we actually call (auth, accounts, schemas, policies, external intake, tasks, documents). Extracted from the upstream MGS spec at [docs/guardian-integration/api-docs-yaml](../../docs/guardian-integration/api-docs-yaml).
- `contracts/guardian-client.md` — typed Python interface for `guardian_client.py`: method signatures (incl. `history: bool` on `get_vc_by_event_hash` and the new `get_vc_retrieval_status`), error codes (incl. `GuardianVCPending`, `GuardianVCManualReview`), retry/breaker semantics, task-poll contract, idempotency and append-only invariants.
- `contracts/vc-output.schema.json` — JSON Schema for the issued VC types (`GDSTComplianceCredential`, `FSMA204ComplianceCredential`) including the shared `GuaranteedMetadata` object (`eventHash`, `complianceStatus ∈ {compliant, superseded}`, `policyVersion`, `issuedAt`, conditional `supersedes`) plus `credentialSubject: additionalProperties: true` so the full event payload flows through (spec §FR-014 / §FR-015).
- `contracts/gps-submission-checklist.md` — the GPS deliverables checklist as a machine-auditable list (one checkbox per item in [docs/guardian-integration/03-gps-submission.md §4](../../docs/guardian-integration/03-gps-submission.md)).

### Runbook deliverable

- `quickstart.md` — local-dev tenant provisioning, SR setup, publishing schemas and policies, running the contract tests. Adapted from [01-setup.md §1-2](../../docs/guardian-integration/01-setup.md) and [03-gps-submission.md §1](../../docs/guardian-integration/03-gps-submission.md).

## Project Structure

### Documentation (this feature)

```text
specs/001-guardian-integration/
├── plan.md                 # This file
├── spec.md                 # User-facing requirements
├── research.md             # Phase 0 decisions
├── data-model.md           # Entities + Rule Source Table + Schema Map
├── quickstart.md           # Local-dev runbook
├── contracts/
│   ├── mgs-boundary.openapi.yaml
│   ├── guardian-client.md
│   ├── vc-output.schema.json
│   └── gps-submission-checklist.md
└── tasks.md                # Produced by /speckit-tasks (not in this plan)
```

Additionally, symlinked from [docs/guardian-integration/spec](../../docs/guardian-integration/spec) so the Guardian docs folder stays the single human-facing entry point.

### Source code (repository root)

```text
api/
├── app/
│   ├── core/
│   │   ├── config.py                            # MODIFIED — GUARDIAN_API_URL, SR credentials
│   │   └── auth.py                              # MODIFIED — include `did` claim in JWT
│   ├── service/
│   │   ├── guardian_client.py                   # NEW — MGS REST client + circuit breaker
│   │   ├── guardian_policies.py                 # NEW — PolicyConfig registry (see data-model §Policy Registry)
│   │   └── schema_mapper.py                     # NEW — Pydantic ↔ Guardian JSON-LD (single generic mapper)
│   ├── routes/
│   │   ├── guardian/
│   │   │   ├── __init__.py                      # NEW
│   │   │   ├── identity.py                      # NEW — /health (operator onboarding deferred to v2)
│   │   │   └── policy.py                        # NEW — /gdst/vc, /fsma/vc
│   │   ├── gdst/events.py                       # MODIFIED — submit to MGS after HCS
│   │   └── epcis/compliance.py                  # MODIFIED — submit to MGS after HCS
│   ├── helpers/
│   │   └── compliance.py                        # Unchanged; remains authoritative for the Pydantic pre-check
│   ├── main.py                                  # MODIFIED — register guardian router
│   └── tests/
│       ├── conftest.py                          # MODIFIED — add MGS mock fixture
│       ├── fixtures/
│       │   └── guardian/                        # NEW — shared with samples/ via symlink
│       └── integration/
│           └── guardian/
│               ├── test_guardian_client_contract.py   # NEW
│               ├── test_schema_mapper.py              # NEW
│               ├── test_gdst_acceptance.py            # NEW — one test per rule
│               ├── test_fsma_acceptance.py            # NEW — one test per rule
│               └── test_circuit_breaker.py           # NEW
└── pytest.ini                                   # Unchanged

schemas/
├── gdst/                                        # NEW — 7 JSON-LD schemas
│   ├── fishing.json
│   ├── landing.json
│   ├── transshipment.json
│   ├── on_vessel.json
│   ├── processing.json
│   ├── shipping.json
│   └── aggregation.json
├── fsma/                                        # NEW — 6 JSON-LD schemas
│   ├── creating.json
│   ├── shipping.json
│   ├── receiving.json
│   ├── transforming.json
│   ├── packing.json
│   └── unpacking.json
└── policies/                                    # NEW — produced by publish step
    ├── gdst-seafood-traceability.policy
    └── fsma-204-food-safety.policy

samples/
├── gdst/*.json                                  # NEW — 7 valid sample events
└── fsma/*.json                                  # NEW — 6 valid sample events
```

**Structure Decision**: Single FastAPI project (the existing `api/` tree) plus two new top-level artifact folders (`schemas/`, `samples/`) that are also the GPS submission deliverables. No new services or processes. `api/app/tests/fixtures/guardian/` symlinks the `samples/` files to avoid duplication (Constitution §Development Workflow #3).

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified.

None. All principles pass without exception.
