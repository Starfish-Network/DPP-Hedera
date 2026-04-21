# Tasks: Guardian Integration — GDST & FSMA 204 Compliance Policies

**Input**: Design documents from `/specs/001-guardian-integration/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/)

**Tests**: Tests are REQUIRED by Constitution §V. Test scaffolds already exist under `api/app/tests/integration/guardian/` and currently SKIP because `respx` and `guardian_client` are absent. Each implementation task lands with the matching test flipped from SKIP → FAIL → PASS in lockstep.

**Organization**: Grouped by user story from [spec.md](spec.md). US1–US3 are P1 (MVP); US4–US5 are P2 (Methodology Library / composability).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 (GDST), US2 (FSMA), US3 (Breaker), US4 (Composability), US5 (GPS packet). Omitted on Setup / Foundational / Polish.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies, directory skeletons, config keys.

- [X] T001 Add `httpx`, `respx`, `tenacity`, and `pyld` (JSON-LD) to [api/requirements.txt](api/requirements.txt) (repo uses requirements.txt, not pyproject.toml). `httpx` already present; added `respx==0.21.1`, `tenacity==8.5.0`, `pyld==2.0.4`.
- [X] T002 [P] Create top-level artifact directories [schemas/gdst/](schemas/gdst/), [schemas/fsma/](schemas/fsma/), [schemas/policies/](schemas/policies/), [samples/gdst/](samples/gdst/), [samples/fsma/](samples/fsma/) with a README.md in each explaining "this is a GPS deliverable — do not rename or flatten."
- [X] T003 [P] Symlink [api/app/tests/fixtures/guardian/gdst](api/app/tests/fixtures/guardian/gdst) → `../../../../../samples/gdst` and `api/app/tests/fixtures/guardian/fsma` → `../../../../../samples/fsma` (5-up, not 4-up — guardian/ is one level deeper than initially planned). Single source of truth per Constitution §Development Workflow #3.
- [X] T004 [P] Add Guardian config keys to [api/app/core/config.py](api/app/core/config.py): `GUARDIAN_NETWORK`, `GUARDIAN_API_URL`, `GUARDIAN_SR_USERNAME`, `GUARDIAN_SR_PASSWORD`, `GUARDIAN_GDST_POLICY_ID`, `GUARDIAN_FSMA_POLICY_ID`, `GUARDIAN_GDST_INTAKE_BLOCK_TAG`, `GUARDIAN_FSMA_INTAKE_BLOCK_TAG`, `GUARDIAN_VC_PENDING_THRESHOLD_S=30`, `GUARDIAN_VC_MANUAL_REVIEW_CEILING_S=300`, `GUARDIAN_BREAKER_FAIL_COUNT=3`, `GUARDIAN_BREAKER_OPEN_DURATION_S=60`. Pydantic-settings validator rejects mixed testnet/mainnet DIDs (research.md §1).
- [X] T005 [P] Create empty module skeletons: [api/app/service/guardian_client.py](api/app/service/guardian_client.py), [api/app/service/schema_mapper.py](api/app/service/schema_mapper.py) (module docstring only).
- [X] T006 [P] Create route package skeleton: [api/app/routes/guardian/__init__.py](api/app/routes/guardian/__init__.py), [api/app/routes/guardian/identity.py](api/app/routes/guardian/identity.py), [api/app/routes/guardian/policy.py](api/app/routes/guardian/policy.py) (empty FastAPI `APIRouter` in each; __init__.py aggregates, mirroring the gdst.py/epcis.py pattern).
- [X] T007 Register the `/guardian` router in [api/app/main.py](api/app/main.py) after the existing routers.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core Guardian-client primitives, identity endpoints, test fixtures. All user stories depend on this phase.

**⚠️ CRITICAL**: No user-story work begins until this phase is complete.

- [X] T008 [P] Implement the exception hierarchy per [contracts/guardian-client.md §Error taxonomy](specs/001-guardian-integration/contracts/guardian-client.md) in [api/app/service/guardian_client.py](api/app/service/guardian_client.py): `GuardianAuthError`, `GuardianToSRequired`, `GuardianNotFound`, `GuardianConflict`, `GuardianClientError`, `GuardianUnavailable`, `GuardianBreakerOpen`, `GuardianTaskTimeout`, `GuardianVCPending`, `GuardianVCManualReview`.
- [X] T009 [P] Implement `CircuitBreaker` state machine (closed / open / half_open / tos_required) in [api/app/service/guardian_client.py](api/app/service/guardian_client.py) per research.md §3: 3-strikes counter, 60 s window, single-probe half-open, `clock` injection for tests. `record_success()` / `record_failure(error_class)` / `should_allow_call()` public API.
- [X] T010 Implement `GuardianClient.__init__`, `login()`, `get_health()`, `circuit_status()` in [api/app/service/guardian_client.py](api/app/service/guardian_client.py). Login caches the JWT; 401 triggers re-login; 451 sets breaker to `tos_required` (no counter increment).
- [X] T011 Implement identity methods `register_user()` (409-idempotent per FR-008), `set_user_credentials()`, `get_user_did()` in [api/app/service/guardian_client.py](api/app/service/guardian_client.py). Depends on T010.
- [X] T012 Implement `wait_for_task(task_id, timeout=120.0)` with `tenacity` exponential backoff (500 ms init, factor 2, cap 8 s) in [api/app/service/guardian_client.py](api/app/service/guardian_client.py). Depends on T010.
- [X] T013 [P] Add `respx` MGS-mock fixture `mgs_mock` and `frozen_clock` fixture to [api/app/tests/integration/guardian/conftest.py](api/app/tests/integration/guardian/conftest.py) (fixture scoped to the guardian test package — path narrower than the plan's earlier `tests/conftest.py` target).
- [X] T014 [P] Removed the import-level skip guard at the top of [api/app/tests/integration/guardian/conftest.py](api/app/tests/integration/guardian/conftest.py); the 6 foundational contract tests written in T018 now PASS, and the remaining 39 test-body stubs (for Phases 3–5) still skip via their own `pytest.skip(...)` placeholders.
- [X] T015 Implement `GET /guardian/health` in [api/app/routes/guardian/identity.py](api/app/routes/guardian/identity.py) returning `{status: ok | tos_required | breaker_open | unavailable, breaker: <state>, last_failure_at: ...}` per FR-009. Depends on T010.
- [X] T016 Implement `POST /guardian/register` (FR-008 idempotent) and `GET /guardian/did/{username}` in [api/app/routes/guardian/identity.py](api/app/routes/guardian/identity.py). Depends on T011.
- [X] T017 Add explicit operator-consent capture on `POST /guardian/register` (FR-015): request body requires `acknowledged_vc_disclosure: bool = True` + `consent_recorded_at` timestamp; reject with 400 if absent. After successful registration, push consent to the Guardian profile via `client.set_user_credentials(username, {"acknowledged_vc_disclosure": "true", "consent_recorded_at": ...})` and `wait_for_task` on the returned handle. No Starfish-side persistence.
- [X] T018 Updated [api/app/tests/integration/guardian/test_guardian_client_contract.py](api/app/tests/integration/guardian/test_guardian_client_contract.py) with the 6 foundational invariants (login/401-refresh, 451→`tos_required`, 409→idempotent register, task-polling timeout, breaker state transitions under an injected clock, /guardian/health discriminates all four statuses). 9 tests pass (health is parametrized × 4 statuses).

**Checkpoint**: Guardian identity and client primitives work end-to-end; breaker + task polling proven; MGS mock fixture in place. User-story work can now begin in parallel.

---

## Phase 3: User Story 1 — GDST-Compliant Event Issues A VC (Priority: P1) 🎯 MVP

**Goal**: An operator submits a GDST CTE through `/events/gdst`; the event is validated, HCS-recorded, and forwarded to the GDST Guardian policy; a `GDSTComplianceCredential` is issued and retrievable by `event_hash`.

**Independent Test**: With a published GDST policy on MGS and one registered operator, submit each of the 7 CTE samples under `samples/gdst/` via `POST /events/gdst` and confirm each produces a VC whose `credentialSubject.eventHash` matches the on-chain event hash. Spec §SC-001 acceptance criteria A1–A4.

### Tests for User Story 1 ⚠️ (write/fail before implementation)

- [ ] T019 [P] [US1] Fill in the 15 GDST rule-id acceptance tests in [api/app/tests/integration/guardian/test_gdst_acceptance.py](api/app/tests/integration/guardian/test_gdst_acceptance.py) — one function per rule from [data-model.md §2](specs/001-guardian-integration/data-model.md) (`GDST_COMMON_001`–`004`, `GDST_FISHING_001`–`003`, `GDST_ONVESSEL_001`, `GDST_TRANSSHIP_001`–`002`, `GDST_LANDING_001`, `GDST_SHIPPING_001`–`002`, `GDST_PROCESSING_001`, `GDST_AGGREGATION_001`). Each test submits a valid/invalid variant and asserts the FastAPI code in spec.md §Acceptance Scenarios (e.g. `GDST_MISSING_FISHING_AUTHORIZATION`).
- [ ] T020 [P] [US1] Add `test_gdst_idempotent_submission` to [api/app/tests/integration/guardian/test_guardian_client_contract.py](api/app/tests/integration/guardian/test_guardian_client_contract.py): submitting the same event twice returns the same `eventHash` and triggers exactly one MGS call (FR-004).
- [ ] T021 [P] [US1] Add `test_gdst_vc_retrieval_history` in the same file: after a `superseded` VC is issued, `GET /guardian/gdst/vc/{h}` returns the latest; `GET /guardian/gdst/vc/{h}?history=true` returns `[oldest, …, latest]` (FR-007, FR-014).

### Implementation for User Story 1

- [ ] T022 [P] [US1] Write [schemas/gdst/fishing.json](schemas/gdst/fishing.json) JSON-LD schema with IRI `#GDSTFishingEvent&1.0.0`, matching `api/app/models/gdst/fishing.py::FishingEvent` fields and the `GDST_FISHING_*` rules.
- [ ] T023 [P] [US1] Write [schemas/gdst/landing.json](schemas/gdst/landing.json) (IRI `#GDSTLandingEvent&1.0.0`, `GDST_LANDING_*`).
- [ ] T024 [P] [US1] Write [schemas/gdst/transshipment.json](schemas/gdst/transshipment.json) (IRI `#GDSTTransshipmentEvent&1.0.0`, `GDST_TRANSSHIP_*`).
- [ ] T025 [P] [US1] Write [schemas/gdst/on_vessel.json](schemas/gdst/on_vessel.json) (IRI `#GDSTOnVesselProcessingEvent&1.0.0`, `GDST_ONVESSEL_*`).
- [ ] T026 [P] [US1] Write [schemas/gdst/processing.json](schemas/gdst/processing.json) (IRI `#GDSTProcessingEvent&1.0.0`, `GDST_PROCESSING_*`).
- [ ] T027 [P] [US1] Write [schemas/gdst/shipping.json](schemas/gdst/shipping.json) (IRI `#GDSTShippingEvent&1.0.0`, `GDST_SHIPPING_*`).
- [ ] T028 [P] [US1] Write [schemas/gdst/aggregation.json](schemas/gdst/aggregation.json) (IRI `#GDSTAggregationEvent&1.0.0`, `GDST_AGGREGATION_001`).
- [ ] T029 [P] [US1] Create 7 canonical sample events: [samples/gdst/fishing.json](samples/gdst/fishing.json), `landing.json`, `transshipment.json`, `on_vessel.json`, `processing.json`, `shipping.json`, `aggregation.json`. Each passes `gdst_min_rules()` and matches its JSON-LD schema.
- [ ] T030 [US1] Implement `to_credential_subject_gdst(event: GDSTEvent, policy_version: str, supersedes: str | None) -> dict` in [api/app/service/schema_mapper.py](api/app/service/schema_mapper.py) — full event payload verbatim + `GuaranteedMetadata` fields (FR-015). Validates output against [contracts/vc-output.schema.json](specs/001-guardian-integration/contracts/vc-output.schema.json).
- [ ] T031 [US1] Implement `GuardianClient.submit_document(policy_id, block_tag, document)` in [api/app/service/guardian_client.py](api/app/service/guardian_client.py): consults `CircuitBreaker.should_allow_call()` and raises `GuardianBreakerOpen` when open; increments breaker on 5xx/429/network, not on 4xx other than 429 (research.md §3); never retries inline. Depends on T009, T010.
- [ ] T032 [US1] Implement `GuardianClient.get_vc_by_event_hash(policy_id, event_hash, history=False) -> VCDocument | list[VCDocument] | None` in the same module with in-memory pagination filter (hard cap 1000). Depends on T010.
- [ ] T033 [US1] Implement `GuardianClient.get_vc_retrieval_status(policy_id, event_hash, submitted_at) -> VCRetrievalStatus` with the 30 s / 300 s thresholds from config (T004). Depends on T032.
- [ ] T034 [US1] Add a local idempotency cache (process-memory dict keyed on `event_hash`, TTL 1 h) in [api/app/service/guardian_client.py](api/app/service/guardian_client.py); wrap `submit_document` so callers short-circuit on cache hit and return the cached VC without an MGS call (FR-004).
- [ ] T035 [US1] Wire [api/app/routes/gdst/events.py](api/app/routes/gdst/events.py) to call `schema_mapper.to_credential_subject_gdst` + `guardian_client.submit_document` AFTER the existing HCS + `ComplianceVerifier.recordEvent()` block. Catch `GuardianBreakerOpen` and continue (US3 log comes in T054). Depends on T030–T034.
- [ ] T036 [US1] Implement `GET /guardian/gdst/vc/{event_hash}` with `?history=true` support in [api/app/routes/guardian/policy.py](api/app/routes/guardian/policy.py); responses follow FR-007 / SC-007 (200 / 202 pending / 404 / 503 `vc_manual_review`). Depends on T032, T033.
- [ ] T037 [US1] Author the GDST Guardian policy as a build script at [scripts/build_gdst_policy.py](scripts/build_gdst_policy.py) that: creates the policy (POST /policies), attaches the 7 schemas (T022–T028), adds one compliance block per rule in [data-model.md](specs/001-guardian-integration/data-model.md), wires `externalDataBlock` → `createVcDocumentBlock` → `trustChainBlock`, publishes, and exports to [schemas/policies/gdst-seafood-traceability.policy](schemas/policies/gdst-seafood-traceability.policy). Runs against testnet MGS.
- [ ] T038 [US1] Run `pytest api/app/tests/integration/guardian/test_gdst_acceptance.py` and confirm all 15 rule tests + T020 + T021 pass.

**Checkpoint**: All 7 GDST CTE samples produce compliant VCs retrievable by `event_hash`; duplicate submissions are idempotent; history retrieval works. Spec §SC-001 (GDST half) verified.

---

## Phase 4: User Story 2 — FSMA-Compliant Event Issues A VC (Priority: P1)

**Goal**: Same loop for FSMA 204 — Creating / Shipping / Receiving / Transforming / Packing / Unpacking events produce `FSMA204ComplianceCredential` VCs.

**Independent Test**: With a published FSMA policy on MGS and one registered operator, submit each of the 6 FSMA samples under `samples/fsma/` via `POST /events/epcis/compliance` and confirm each produces a VC whose `credentialSubject.eventHash` matches the on-chain event hash. Spec §SC-001 acceptance criteria B1–B3.

### Tests for User Story 2 ⚠️

- [ ] T039 [P] [US2] Fill in the 17 FSMA rule-id acceptance tests in [api/app/tests/integration/guardian/test_fsma_acceptance.py](api/app/tests/integration/guardian/test_fsma_acceptance.py) — one function per rule from [data-model.md §2](specs/001-guardian-integration/data-model.md) (`FSMA_COMMON_001`, `FSMA_CREATING_001`–`002`, `FSMA_SHIPPING_001`–`003`, `FSMA_RECEIVING_001`–`002`, `FSMA_TRANSFORMING_001`–`003`, `FSMA_PACKING_001`–`003`, `FSMA_UNPACKING_001`–`003`).

### Implementation for User Story 2

- [ ] T040 [P] [US2] Write [schemas/fsma/creating.json](schemas/fsma/creating.json) (IRI `#FSMA204CreatingEvent&1.0.0`, `FSMA_CREATING_*`).
- [ ] T041 [P] [US2] Write [schemas/fsma/shipping.json](schemas/fsma/shipping.json) (IRI `#FSMA204ShippingEvent&1.0.0`, `FSMA_SHIPPING_*`).
- [ ] T042 [P] [US2] Write [schemas/fsma/receiving.json](schemas/fsma/receiving.json) (IRI `#FSMA204ReceivingEvent&1.0.0`, `FSMA_RECEIVING_*`).
- [ ] T043 [P] [US2] Write [schemas/fsma/transforming.json](schemas/fsma/transforming.json) (IRI `#FSMA204TransformingEvent&1.0.0`, `FSMA_TRANSFORMING_*`).
- [ ] T044 [P] [US2] Write [schemas/fsma/packing.json](schemas/fsma/packing.json) (IRI `#FSMA204PackingEvent&1.0.0`, `FSMA_PACKING_*`).
- [ ] T045 [P] [US2] Write [schemas/fsma/unpacking.json](schemas/fsma/unpacking.json) (IRI `#FSMA204UnpackingEvent&1.0.0`, `FSMA_UNPACKING_*`).
- [ ] T046 [P] [US2] Create 6 canonical FSMA sample events: [samples/fsma/creating.json](samples/fsma/creating.json), `shipping.json`, `receiving.json`, `transforming.json`, `packing.json`, `unpacking.json`.
- [ ] T047 [US2] Implement `to_credential_subject_fsma(event, policy_version, supersedes)` in [api/app/service/schema_mapper.py](api/app/service/schema_mapper.py) — full event payload + `GuaranteedMetadata` (FR-015). Emits `fsma204EventType` (NOT `eventType`) as the discriminator, symmetric with GDST. Validates against `FSMA204ComplianceCredential` branch of [contracts/vc-output.schema.json](specs/001-guardian-integration/contracts/vc-output.schema.json).
- [ ] T048 [US2] Wire [api/app/routes/epcis/compliance.py](api/app/routes/epcis/compliance.py) to call `schema_mapper.to_credential_subject_fsma` + `guardian_client.submit_document` AFTER the existing HCS + `ComplianceVerifier.recordEvent()` block, using the FSMA policy ID and intake block tag from config. Reuses the idempotency cache from T034. Depends on T031, T034, T047.
- [ ] T049 [US2] Implement `GET /guardian/fsma/vc/{event_hash}` with `?history=true` in [api/app/routes/guardian/policy.py](api/app/routes/guardian/policy.py) — mirrors T036.
- [ ] T050 [US2] Author the FSMA Guardian policy build script [scripts/build_fsma_policy.py](scripts/build_fsma_policy.py) producing [schemas/policies/fsma-204-food-safety.policy](schemas/policies/fsma-204-food-safety.policy). Mirrors T037.
- [ ] T051 [US2] Run `pytest api/app/tests/integration/guardian/test_fsma_acceptance.py` and confirm all 17 rule tests pass.

**Checkpoint**: All 6 FSMA event samples produce compliant VCs. Spec §SC-001 (FSMA half) and SC-002 (100% rule↔test coverage for both schemas combined = 32 tests) verified.

---

## Phase 5: User Story 3 — Guardian Unavailability Does Not Block Event Recording (Priority: P1)

**Goal**: When MGS is unreachable, HCS + `ComplianceVerifier.recordEvent()` complete unaffected. After 3 consecutive failures the breaker opens for 60 s, skipped submissions emit a structured WARN log, and `/guardian/health` surfaces the state. No backlog table, no automatic retry (FR-006 log-only).

**Independent Test**: Inject `503` responses for 3 consecutive `POST /events/gdst` calls via `respx`; verify (a) each event recorded on HCS, (b) 4th submission within 60 s does NOT call MGS, (c) after 60 s the next call is a probe, (d) 451 does NOT increment the counter. Spec §SC-006 acceptance.

### Tests for User Story 3 ⚠️

- [ ] T052 [P] [US3] Fill in the 7 breaker tests in [api/app/tests/integration/guardian/test_circuit_breaker.py](api/app/tests/integration/guardian/test_circuit_breaker.py): 3-failures-opens, stays-open-60s, probe-success-closes, probe-failure-restarts-60s-window, 451-no-increment, 4xx-no-increment, breaker-open-never-blocks-HCS.
- [ ] T053 [P] [US3] Add `test_skipped_event_emits_warn_log` in [api/app/tests/integration/guardian/test_circuit_breaker.py](api/app/tests/integration/guardian/test_circuit_breaker.py) — asserts a structured log record with fields `{event_hash, operator_did, mgs_error_class, breaker_opened_at}` is emitted when `GuardianBreakerOpen` is raised on the hot path.

### Implementation for User Story 3

- [ ] T054 [US3] On `GuardianBreakerOpen` catch in [api/app/routes/gdst/events.py](api/app/routes/gdst/events.py) and [api/app/routes/epcis/compliance.py](api/app/routes/epcis/compliance.py), emit a structured WARN log record `logger.warning("guardian.skipped", extra={…})` with the four fields required by FR-006 and spec §Edge Cases. Do NOT re-raise — HCS path already wrote.
- [ ] T055 [US3] Extend `GET /guardian/health` in [api/app/routes/guardian/identity.py](api/app/routes/guardian/identity.py) to include `{breaker_state, last_failure_at, consecutive_failures}` and a monotonic counter of breaker-skipped events since process start (FR-009 + Edge Cases transparency).
- [ ] T056 [US3] Confirm `GuardianClient.submit_document` correctly maps MGS 451 → `GuardianToSRequired` (no breaker increment; /guardian/health shows `tos_required`). This is a verification task against T010/T031; add unit test if missing.
- [ ] T057 [US3] Run `pytest api/app/tests/integration/guardian/test_circuit_breaker.py` and confirm all 8 tests pass. Verify Story 3 acceptance end-to-end: inject 3×503 via respx, assert 4th call is skipped-not-attempted, 451 does not count.

**Checkpoint**: P1 MVP complete (US1 + US2 + US3). Guardian VCs issue for both policies under healthy MGS; outages never block the hot path. Ready to deploy v1.

---

## Phase 6: User Story 4 — Downstream Guardian Projects Chain Our VCs (Priority: P2)

**Goal**: A third-party Guardian project imports `gdst-seafood-traceability.policy` (or the FSMA one) into a vanilla Guardian instance, accepts our VCs via `trustChainBlock` by SR DID + VC type, and validates without calling any Starfish API.

**Independent Test**: On a clean Hedera Guardian 2.x instance (self-hosted for this test; documented in quickstart.md), import the exported `.policy`, register an SR, publish, submit a compliant sample event, retrieve the VC. Then import a demo downstream policy that filters by `GDSTComplianceCredential` + our SR DID and confirm it validates.

### Tests for User Story 4 ⚠️

- [ ] T058 [P] [US4] Add `test_policy_imports_on_vanilla_guardian.py` in [api/app/tests/integration/guardian/](api/app/tests/integration/guardian/) that shells out to a Docker-compose Guardian fixture, imports both `.policy` files, and asserts no Starfish-specific dependencies error. Skipped in CI unless `GUARDIAN_VANILLA_COMPOSE=1`.

### Implementation for User Story 4

- [ ] T059 [P] [US4] Author a minimal downstream demo policy [samples/downstream/carbon-credit-demo.policy.json](samples/downstream/carbon-credit-demo.policy.json) that accepts `GDSTComplianceCredential` via `trustChainBlock` filtered by `issuer == <SR DID>` and `credentialSubject.complianceStatus == "compliant"`.
- [ ] T060 [P] [US4] Write [schemas/gdst/README.md](schemas/gdst/README.md) documenting the Guaranteed-fields contract from [data-model.md §VC entity](specs/001-guardian-integration/data-model.md) — one section per field with semver stability promise (Constitution §II).
- [ ] T061 [P] [US4] Write [schemas/fsma/README.md](schemas/fsma/README.md) with the same structure for FSMA.
- [ ] T062 [US4] Run `pytest api/app/tests/integration/guardian/test_policy_imports_on_vanilla_guardian.py` end-to-end and verify the downstream demo policy issues a VC whose trust chain validates back to our SR DID.

**Checkpoint**: Spec §SC-004 (vanilla Guardian import works) and US4 acceptance scenarios A4.1 / A4.2 verified. Composability promise delivered.

---

## Phase 7: User Story 5 — GPS Submission Artifacts Ready For The Methodology Library (Priority: P2)

**Goal**: Both policies have a complete GPS proposal packet: description, workflow diagram, user guide, sample data, IPFS-published `.policy` + schemas, compatibility declaration, maintenance commitment. Checklist in [contracts/gps-submission-checklist.md](specs/001-guardian-integration/contracts/gps-submission-checklist.md) fully green.

**Independent Test**: Walk the GPS deliverables checklist — every box checked, every referenced file exists, every IPFS CID resolves.

### Implementation for User Story 5

- [ ] T063 [P] [US5] Produce the GDST policy workflow diagram at [docs/guardian-integration/gdst-workflow.svg](docs/guardian-integration/gdst-workflow.svg) (SVG, exported from the Guardian policy designer or equivalent).
- [ ] T064 [P] [US5] Produce the FSMA policy workflow diagram at [docs/guardian-integration/fsma-workflow.svg](docs/guardian-integration/fsma-workflow.svg).
- [ ] T065 [P] [US5] Write the GDST operator user guide at [docs/guardian-integration/gdst-user-guide.md](docs/guardian-integration/gdst-user-guide.md) covering: onboarding + consent (FR-015), submitting each of the 7 CTE types, retrieving a VC, correcting via superseding (FR-014), and reading `/guardian/health`.
- [ ] T066 [P] [US5] Write the FSMA operator user guide at [docs/guardian-integration/fsma-user-guide.md](docs/guardian-integration/fsma-user-guide.md) with the same structure for the 6 FSMA event types.
- [ ] T067 [US5] Publish both `.policy` files and the 13 JSON-LD schemas to IPFS; record CIDs in [specs/001-guardian-integration/contracts/gps-submission-checklist.md](specs/001-guardian-integration/contracts/gps-submission-checklist.md) under the "IPFS-published artifacts" section.
- [ ] T068 [US5] Write the compatibility declaration + maintenance commitment at [docs/guardian-integration/gps-submission.md](docs/guardian-integration/gps-submission.md) stating the Guardian version range, semver promise (FR-012), and the Starfish team's quarterly-review commitment.
- [ ] T069 [US5] Tick every box in [specs/001-guardian-integration/contracts/gps-submission-checklist.md](specs/001-guardian-integration/contracts/gps-submission-checklist.md) and cross-reference each item to its artifact. Verify every referenced file exists; verify every IPFS CID resolves via `ipfs cat <cid> | head`.

**Checkpoint**: Spec §SC-005 (GPS deliverables checklist green on first submission) verified. Ready to submit to the Methodology Library.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Performance verification, docs cleanup, append-only superseding validation, operational hardening.

- [ ] T070 [P] Add [api/app/tests/integration/guardian/test_superseding_vc.py](api/app/tests/integration/guardian/test_superseding_vc.py) covering FR-014: submit corrective event with `supersedes=<prior eventHash>` → new VC has `complianceStatus=superseded`, prior VC unchanged, `?history=true` returns both in issuance order, `?history=false` returns latest only.
- [ ] T071 [P] Benchmark `/events` p95 latency with Guardian enabled vs. disabled in [api/benchmarks/guardian_latency.py](api/benchmarks/guardian_latency.py); confirm SC-003 (≤5% regression under healthy MGS and ≤0% regression when breaker is open).
- [ ] T072 [P] Benchmark `GET /guardian/*/vc/{event_hash}` retrieval timing in the same benchmark module; confirm SC-007 (95% < 30 s under healthy MGS; no event lingers past 5 min).
- [ ] T073 Run [specs/001-guardian-integration/quickstart.md](specs/001-guardian-integration/quickstart.md) end-to-end against a real testnet MGS tenant (provisioning, SR bootstrap, schema publish, policy publish, policy export, sample event submission for both GDST and FSMA). Fix any step drift.
- [ ] T074 [P] Coverage audit: confirm 100% of the 32 rule IDs in [data-model.md §2](specs/001-guardian-integration/data-model.md) have a matching pytest function (SC-002). Fail the build if a rule lacks a test.
- [ ] T075 Replace the tutorial-style numbered docs in [docs/guardian-integration/](docs/guardian-integration/) (`01-setup.md`, `02-schemas-and-policies.md`, `03-gps-submission.md`) with one-paragraph stubs linking to the corresponding spec artifact, per Constitution §Development Workflow #5.
- [ ] T076 Security hardening: confirm `GUARDIAN_SR_PASSWORD` is never logged, never surfaced in `/guardian/health`, and is loaded only from the environment (not committed). Add `.gitignore` entries as needed and a unit test `test_sr_credentials_not_logged` in [api/app/tests/unit/](api/app/tests/unit/).
- [ ] T077 [P] Add minimal CI workflow at [.github/workflows/ci.yml](.github/workflows/ci.yml) running `pytest api/app/tests` and a JSON-schema lint over `schemas/` + `contracts/vc-output.schema.json`. Block PRs on failure.
- [ ] T078 Run `/speckit-analyze` one final time; resolve any drift before marking the feature complete.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **BLOCKS all user stories.**
- **User Stories (Phases 3–7)**: All depend on Foundational.
  - **US1 (P1) and US2 (P1)** share the `submit_document` hot path and idempotency cache (T031, T034) — US1 lands those; US2 reuses. Inside that constraint they can proceed in parallel by feature area (schemas, mappers, routes).
  - **US3 (P1)** depends on US1 (`submit_document` exists before US3 can verify breaker-skipped logging on the hot path); ideally run after US1's T035.
  - **US4 (P2)** depends on US1 + US2 `.policy` exports (T037, T050).
  - **US5 (P2)** depends on everything — it packages the artifacts.
- **Polish (Phase 8)**: Depends on all desired user stories being complete.

### Within Each User Story

- Tests (T019–T021, T039, T052–T053) are written and FAIL before the implementation tasks in that story (Constitution §V).
- Schemas before mapper; mapper before routes; policy build script last.
- Commit after each task or logical group.

### Parallel Opportunities

- **Phase 1**: T002–T006 all `[P]` — run in parallel.
- **Phase 2**: T008, T009, T013 all `[P]`. T014 can run alongside T015/T016 if in separate files.
- **Phase 3**: T019–T021 tests are `[P]`. T022–T029 (schemas + samples) are 8 parallel files. T030 (mapper) blocks T031–T035.
- **Phase 4**: Mirror of Phase 3 — T040–T046 are `[P]`. T047 blocks T048–T051.
- **Phase 5**: T052–T053 tests are `[P]`; implementation is two route files in sequence.
- **Phases 6–7**: Most docs/sample tasks are `[P]`.
- **Phase 8**: T070–T072, T074, T077 all `[P]`.

---

## Parallel Example: User Story 1

```bash
# Write the GDST schemas and samples in parallel (8 files, no interdependencies):
Task: "Write schemas/gdst/fishing.json per data-model.md"
Task: "Write schemas/gdst/landing.json per data-model.md"
Task: "Write schemas/gdst/transshipment.json per data-model.md"
Task: "Write schemas/gdst/on_vessel.json per data-model.md"
Task: "Write schemas/gdst/processing.json per data-model.md"
Task: "Write schemas/gdst/shipping.json per data-model.md"
Task: "Write schemas/gdst/aggregation.json per data-model.md"
Task: "Create samples/gdst/*.json canonical events"

# Write the US1 tests in parallel BEFORE implementation (Constitution §V):
Task: "Fill test_gdst_acceptance.py (15 rule tests)"
Task: "Add test_gdst_idempotent_submission to test_guardian_client_contract.py"
Task: "Add test_gdst_vc_retrieval_history to test_guardian_client_contract.py"
```

---

## Implementation Strategy

### MVP First (US1 only, then US2, then US3)

1. Complete Phase 1 (Setup).
2. Complete Phase 2 (Foundational) — **blocks everything**.
3. Complete Phase 3 (US1 — GDST VC issuance). **STOP and VALIDATE** with the 7 CTE samples.
4. Complete Phase 4 (US2 — FSMA VC issuance). **STOP and VALIDATE** with the 6 event samples.
5. Complete Phase 5 (US3 — resilience). **STOP and VALIDATE** by injecting MGS failures.
6. **MVP complete** — all P1 stories deployable.
7. Then Phases 6–7 for composability + GPS packet (P2), and Phase 8 polish.

### Parallel Team Strategy

- Dev A owns US1 (GDST schemas + policy + route).
- Dev B owns US2 (FSMA schemas + policy + route) — waits for US1 T031 (`submit_document`) then proceeds in parallel.
- Dev C owns US3 (breaker integration + health + logs) — waits for US1 to land the hot-path submission.
- Docs + GPS packet (Phases 6–7) can start as soon as US1 schemas exist.

---

## Notes

- `[P]` = different files, no dependencies on incomplete tasks.
- `[Story]` label maps every user-story task to US1–US5 for traceability (omitted on Setup / Foundational / Polish).
- Each user story is independently completable and testable; US3 has a hard ordering dependency on US1 (needs `submit_document` to exist) but tests a distinct behavior.
- Verify tests FAIL before implementing (Constitution §V). The 45 pre-scaffolded tests under [api/app/tests/integration/guardian/](api/app/tests/integration/guardian/) currently SKIP; T014 flips them to FAIL.
- Commit after each task or logical group.
- Stop at any Checkpoint to validate the story independently.
- Avoid: vague tasks, same-file conflicts between `[P]` tasks, cross-story dependencies that break independence.
