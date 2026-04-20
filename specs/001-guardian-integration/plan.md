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
**Performance Goals**: `/events` p95 latency must not regress by more than 5% with Guardian enabled (SC-003). Guardian submit is async/fire-and-forget on the hot path; VC retrieval is on-demand.
**Constraints**: Guardian calls must never block HCS recording (Constitution §IV). `.policy` exports must be self-contained (Constitution §II).
**Scale/Scope**: Single MGS tenant initially. Two policies. 13 schemas total. ~5 new API endpoints under `/guardian/*`. New service module (`guardian_client.py`), schema mapper (`schema_mapper.py`), config additions.

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

- `data-model.md` §Entities: GDST CTE, FSMA event, VC, SR, Operator.
- `data-model.md` §Rule Source Table: per-event-type rules cross-referencing `compliance.py` and Guardian policy blocks.
- `data-model.md` §Schema Map: one row per JSON-LD schema with source Pydantic model.

### Contract deliverables

- `contracts/mgs-boundary.openapi.yaml` — subset of MGS endpoints we actually call (auth, accounts, schemas, policies, external intake, tasks, documents). Extracted from the upstream MGS spec at [docs/guardian-integration/api-docs-yaml](../../docs/guardian-integration/api-docs-yaml).
- `contracts/guardian-client.md` — typed Python interface for `guardian_client.py`: method signatures, error codes, retry/breaker semantics, task-poll contract.
- `contracts/vc-output.schema.json` — JSON Schema for the issued VC types (`GDSTComplianceCredential`, `FSMA204ComplianceCredential`) including the Guaranteed-fields contract that downstream policies rely on.
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
│   │   └── schema_mapper.py                     # NEW — Pydantic ↔ Guardian JSON-LD
│   ├── routes/
│   │   ├── guardian/
│   │   │   ├── __init__.py                      # NEW
│   │   │   ├── identity.py                      # NEW — /register, /did, /health
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
