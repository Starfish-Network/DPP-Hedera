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
- [X] T011 **Deferred to v2** — operator onboarding is out of scope for v1 (spec §FR-007 / Assumptions). The `register_user()`, `set_user_credentials()`, `get_user_did()` methods currently present in `guardian_client.py` are scheduled for removal in the follow-up implementation pass; v1 retains only `login()` / `get_health()` on the identity surface.
- [X] T012 Implement `wait_for_task(task_id, timeout=120.0)` with `tenacity` exponential backoff (500 ms init, factor 2, cap 8 s) in [api/app/service/guardian_client.py](api/app/service/guardian_client.py). Depends on T010.
- [X] T013 [P] Add `respx` MGS-mock fixture `mgs_mock` and `frozen_clock` fixture to [api/app/tests/integration/guardian/conftest.py](api/app/tests/integration/guardian/conftest.py) (fixture scoped to the guardian test package — path narrower than the plan's earlier `tests/conftest.py` target).
- [X] T014 [P] Removed the import-level skip guard at the top of [api/app/tests/integration/guardian/conftest.py](api/app/tests/integration/guardian/conftest.py); the 5 foundational contract tests written in T018 now PASS (the 409→idempotent-register invariant was dropped with the onboarding deferral), and the remaining test-body stubs (for Phases 3–5) still skip via their own `pytest.skip(...)` placeholders.
- [X] T015 Implement `GET /guardian/health` in [api/app/routes/guardian/identity.py](api/app/routes/guardian/identity.py) returning `{status: ok | tos_required | breaker_open | unavailable, breaker: <state>, last_failure_at: ...}` per FR-009. Depends on T010.
- [X] T016 **Deferred to v2** — `POST /guardian/register` and `GET /guardian/did/{username}` are removed from v1 (spec §FR-007). Operators are pre-provisioned in the MGS portal; the corresponding route handlers currently present in `identity.py` are scheduled for removal in the follow-up implementation pass.
- [X] T017 **Deferred to v2** — programmatic consent capture is removed from v1. FR-015 consent is obtained out-of-band by the deployer and persisted in the deployment-runbook operator registry (see quickstart §5). v1 ships no consent endpoint.
- [X] T018 Updated [api/app/tests/integration/guardian/test_guardian_client_contract.py](api/app/tests/integration/guardian/test_guardian_client_contract.py) with 5 foundational invariants for v1 (login/401-refresh, 451→`tos_required`, task-polling timeout, breaker state transitions under an injected clock, /guardian/health discriminates all four statuses). The 409→idempotent-register invariant was dropped with the T011/T016 deferral. Health is parametrized × 4 statuses.

**Checkpoint**: Guardian identity and client primitives work end-to-end; breaker + task polling proven; MGS mock fixture in place. User-story work can now begin in parallel.

---

## Phase 3: User Story 1 — GDST-Compliant Event Issues A VC (Priority: P1) 🎯 MVP

**Goal**: An operator submits a GDST CTE through `/events/gdst`; the event is validated, HCS-recorded, and forwarded to the GDST Guardian policy; a `GDSTComplianceCredential` is issued and retrievable by `event_hash`.

**Independent Test**: With a published GDST policy on MGS and one registered operator, submit each of the 7 CTE samples under `samples/gdst/` via `POST /events/gdst` and confirm each produces a VC whose `credentialSubject.eventHash` matches the on-chain event hash. Spec §SC-001 acceptance criteria A1–A4.

### Tests for User Story 1 ⚠️ (write/fail before implementation)

- [X] T019 [P] [US1] Fill in the 15 GDST rule-id acceptance tests in [api/app/tests/integration/guardian/test_gdst_acceptance.py](api/app/tests/integration/guardian/test_gdst_acceptance.py) — one function per rule from [data-model.md §2](specs/001-guardian-integration/data-model.md) (`GDST_COMMON_001`–`004`, `GDST_FISHING_001`–`003`, `GDST_ONVESSEL_001`, `GDST_TRANSSHIP_001`–`002`, `GDST_LANDING_001`, `GDST_SHIPPING_001`–`002`, `GDST_PROCESSING_001`, `GDST_AGGREGATION_001`). Each test submits a valid/invalid variant and asserts the FastAPI code in spec.md §Acceptance Scenarios (e.g. `GDST_MISSING_FISHING_AUTHORIZATION`).
- [X] T020 [P] [US1] Add `test_gdst_idempotent_submission` to [api/app/tests/integration/guardian/test_guardian_client_contract.py](api/app/tests/integration/guardian/test_guardian_client_contract.py): submitting the same event twice returns the same `eventHash` and triggers exactly one MGS call (FR-004).
- [X] T021 [P] [US1] Add `test_gdst_vc_retrieval_history` in the same file: after a `superseded` VC is issued, `GET /guardian/gdst/vc/{h}` returns the latest; `GET /guardian/gdst/vc/{h}?history=true` returns `[oldest, …, latest]` (FR-007, FR-014).

### Implementation for User Story 1

- [X] T022 [P] [US1] Write [schemas/gdst/fishing.json](schemas/gdst/fishing.json) JSON-LD schema with IRI `#GDSTFishingEvent&1.0.0`, matching `api/app/models/gdst/fishing.py::FishingEvent` fields and the `GDST_FISHING_*` rules.
- [X] T023 [P] [US1] Write [schemas/gdst/landing.json](schemas/gdst/landing.json) (IRI `#GDSTLandingEvent&1.0.0`, `GDST_LANDING_*`).
- [X] T024 [P] [US1] Write [schemas/gdst/transshipment.json](schemas/gdst/transshipment.json) (IRI `#GDSTTransshipmentEvent&1.0.0`, `GDST_TRANSSHIP_*`).
- [X] T025 [P] [US1] Write [schemas/gdst/on_vessel.json](schemas/gdst/on_vessel.json) (IRI `#GDSTOnVesselProcessingEvent&1.0.0`, `GDST_ONVESSEL_*`).
- [X] T026 [P] [US1] Write [schemas/gdst/processing.json](schemas/gdst/processing.json) (IRI `#GDSTProcessingEvent&1.0.0`, `GDST_PROCESSING_*`).
- [X] T027 [P] [US1] Write [schemas/gdst/shipping.json](schemas/gdst/shipping.json) (IRI `#GDSTShippingEvent&1.0.0`, `GDST_SHIPPING_*`). Source model is `ShippingReceivingEvent`; the schema accepts both `"Shipping"` and `"ShippingReceiving"` in `gdst_event_type` and the mapper normalises to `"Shipping"` at the VC boundary.
- [X] T028 [P] [US1] Write [schemas/gdst/aggregation.json](schemas/gdst/aggregation.json) (IRI `#GDSTAggregationEvent&1.0.0`, `GDST_AGGREGATION_001`). Schema accepts both `"Aggregation"` and `"AggregationDisaggregation"`; mapper normalises to `"Aggregation"`.
- [X] T029 [P] [US1] Create 7 canonical sample events: [samples/gdst/fishing.json](samples/gdst/fishing.json), `landing.json`, `transshipment.json`, `on_vessel.json`, `processing.json`, `shipping.json`, `aggregation.json`. Each passes `gdst_min_rules()` and matches its JSON-LD schema.
- [X] T030 [US1] Implement `to_credential_subject_gdst(event: GDSTEvent, policy_version: str, supersedes: str | None) -> dict` in [api/app/service/schema_mapper.py](api/app/service/schema_mapper.py) — full event payload verbatim + `GuaranteedMetadata` fields (FR-015). Validates output against [contracts/vc-output.schema.json](specs/001-guardian-integration/contracts/vc-output.schema.json).
- [X] T031 [US1] Implement `GuardianClient.submit_document(policy_id, block_tag, document)` in [api/app/service/guardian_client.py](api/app/service/guardian_client.py): consults `CircuitBreaker.should_allow_call()` and raises `GuardianBreakerOpen` when open; increments breaker on 5xx/429/network, not on 4xx other than 429 (research.md §3); never retries inline. Depends on T009, T010.
- [X] T032 [US1] Implement `GuardianClient.get_vc_by_event_hash(policy_id, event_hash, history=False) -> VCDocument | list[VCDocument] | None` in the same module with in-memory pagination filter (hard cap 1000). Depends on T010.
- [X] T033 [US1] Implement `GuardianClient.get_vc_retrieval_status(policy_id, event_hash, submitted_at) -> VCRetrievalStatus` with the 30 s / 300 s thresholds from config (T004). Depends on T032.
- [X] T034 [US1] Add a local idempotency cache (process-memory dict keyed on `event_hash`, TTL 1 h) in [api/app/service/guardian_client.py](api/app/service/guardian_client.py); wrap `submit_document` so callers short-circuit on cache hit and return the cached VC without an MGS call (FR-004).
- [X] T035 [US1] Wire [api/app/routes/gdst/events.py](api/app/routes/gdst/events.py) to call `schema_mapper.to_credential_subject_gdst` + `guardian_client.submit_document` AFTER the existing HCS + `ComplianceVerifier.recordEvent()` block. Catch `GuardianBreakerOpen` and continue (US3 log comes in T054). Depends on T030–T034.
- [X] T036 [US1] Implement `GET /guardian/gdst/vc/{event_hash}` with `?history=true` support in [api/app/routes/guardian/policy.py](api/app/routes/guardian/policy.py) per [contracts/guardian-http-errors.md](specs/001-guardian-integration/contracts/guardian-http-errors.md). Depends on T032, T033.
- [X] T036a [US1/US2] Introduce the `PolicyConfig` registry per [data-model.md §Policy Registry](specs/001-guardian-integration/data-model.md) and [research.md §8](specs/001-guardian-integration/research.md). Concrete changes:
  1. New module [api/app/service/guardian_policies.py](api/app/service/guardian_policies.py) exporting `PolicyConfig` (frozen dataclass), `POLICIES: dict[str, PolicyConfig]` with `GDST` and `FSMA` entries populated from settings at import time, and `get_policy(slug)`. Assert at import that no two policies share `source_type_field` or `vc_type_field`.
  2. Rewrite [api/app/service/schema_mapper.py](api/app/service/schema_mapper.py) to expose a single `to_credential_subject(event, policy: PolicyConfig, *, supersedes=None) -> dict`. It consumes `source_type_field`, `vc_type_field`, `type_map`, and `required_hoists` from the config. Delete `to_credential_subject_gdst` in the same commit — callers migrate in (3) and (5). Supersedes T030's public signature; mapping logic preserved.
  3. Rewire [api/app/routes/gdst/events.py](api/app/routes/gdst/events.py) to call `to_credential_subject(event_dict, GDST)` and use `GDST.policy_id` / `GDST.intake_block_tag` / `GDST.policy_version`. Drop the module-level `_GDST_POLICY_VERSION` constant.
  4. Collapse [api/app/routes/guardian/policy.py](api/app/routes/guardian/policy.py) to a single `GET /{policy_slug}/vc/{event_hash}` handler that resolves the policy via `get_policy(slug)` (404 on unknown slug, 503 on `not enabled`). URL contract `/guardian/gdst/vc/{h}` stays byte-identical; this makes T049 a no-op.
  5. Update call sites in [api/app/tests/integration/guardian/test_gdst_acceptance.py](api/app/tests/integration/guardian/test_gdst_acceptance.py) and [api/app/tests/integration/guardian/test_guardian_client_contract.py](api/app/tests/integration/guardian/test_guardian_client_contract.py) to pass `PolicyConfig` where they previously passed `policy_version`.

  No wire-format change (FR-004 / FR-007 / FR-012 / FR-015 unaffected; `contracts/vc-output.schema.json` unchanged). No MGS-boundary change. Depends on T030–T036. Unblocks T047/T048 to land as config entries rather than parallel code.
- [X] T037 [US1] Author the GDST Guardian policy build script at [scripts/build_gdst_policy.py](scripts/build_gdst_policy.py) and run it against testnet MGS. Shipped topology is simpler than the original task text: **one `GDSTComplianceIntake` envelope schema** (not 7 per-CTE schemas) and **`externalDataBlock` → `sendToGuardianBlock`** (not the three-block `createVcDocumentBlock` + `trustChainBlock` pipeline). Rule enforcement lives in `gdst_min_rules()` server-side per Constitution §III (Pydantic + JSON-LD schemas + pytest); Guardian is the issuer, not the validator. The 7 per-CTE JSON-LD schemas under [schemas/gdst/](schemas/gdst/) remain GPS deliverables. Script supports `--dry-run` and `--resume` (the latter recovers from mid-run failures where the schema publish task outlives the client's wait window). Published on testnet as `policyTag=GDST-1-2-seafood-v2`, `policyId=69eb781e6c734e54853b3cb5`, intake block tag `gdst_intake`; exported to [schemas/policies/gdst-seafood-traceability.policy](schemas/policies/gdst-seafood-traceability.policy).
- [X] T038 [US1] Run `pytest api/app/tests/integration/guardian/test_gdst_acceptance.py` and confirm all 15 rule tests + T020 + T021 pass. — 25 passed, 24 skipped (scaffolds for later phases).

**Checkpoint**: All 7 GDST CTE samples produce compliant VCs retrievable by `event_hash`; duplicate submissions are idempotent; history retrieval works. Spec §SC-001 (GDST half) verified.

---

## Phase 4: User Story 2 — FSMA-Compliant Event Issues A VC (Priority: P1)

**Goal**: Same loop for FSMA 204 — Creating / Shipping / Receiving / Transforming / Packing / Unpacking events produce `FSMA204ComplianceCredential` VCs.

**Independent Test**: With a published FSMA policy on MGS and one registered operator, submit each of the 6 FSMA samples under `samples/fsma/` via `POST /events/epcis/compliance` and confirm each produces a VC whose `credentialSubject.eventHash` matches the on-chain event hash. Spec §SC-001 acceptance criteria B1–B3.

### Tests for User Story 2 ⚠️

- [X] T039 [P] [US2] Filled in the 17 FSMA rule-id acceptance tests in [api/app/tests/integration/guardian/test_fsma_acceptance.py](api/app/tests/integration/guardian/test_fsma_acceptance.py) — one function per rule from [data-model.md §2](specs/001-guardian-integration/data-model.md). Pulled in T046 (samples) as a hard prerequisite. Also fixed two latent bugs blocking the suite: (a) `fsma_min_rules()` was checking camelCase keys (`shipFrom`, `shipTo`, `receivedAt`) while the Pydantic model uses snake_case — silent rule failure, never caught because `test_compliance.py` requires an external docker service; (b) [api/app/models/starfish_events.py](api/app/models/starfish_events.py) used the invalid Pydantic-v2 syntax `Field(..., Literal=True)` and had no `min_length` constraints on List fields, so 7 of the 17 "non-empty list" rules weren't enforceable at the Pydantic boundary as the rule table claims. Models now use proper `Literal["…"]` typing and `Field(..., min_length=1)` on every list mentioned by the FSMA rules. 17 tests pass (`55 passed, 7 skipped` across the integration/guardian + unit suites; the 7 skips are scaffolds for later phases). The `eventType` (camelCase) vs. `fsma204_event_type` (snake_case, per `PolicyConfig.source_type_field`) naming mismatch is left for T047 — Pydantic dispatch and registry dispatch use different keys and reconciliation is out of T039 scope.

### Implementation for User Story 2

- [X] T040 [P] [US2] Wrote [schemas/fsma/creating.json](schemas/fsma/creating.json) — IRI `#FSMA204CreatingEvent&1.0.0`. Enforces FSMA_COMMON_001 (event_time required), FSMA_CREATING_001 (biz_location required), FSMA_CREATING_002 (quantity_list `minItems: 1`). Discriminator field is `eventType` (camelCase) to match the existing `starfish_events.py::CreatingEvent` model — the snake_case rename to `fsma204_event_type` for registry-side consistency is still tracked under T047. Validated against [samples/fsma/creating.json](samples/fsma/creating.json): valid sample passes, empty `quantity_list` / missing `biz_location` / wrong `eventType` all rejected.
- [X] T041 [P] [US2] Wrote [schemas/fsma/shipping.json](schemas/fsma/shipping.json) — IRI `#FSMA204ShippingEvent&1.0.0`. Enforces FSMA_COMMON_001, FSMA_SHIPPING_001 (ship_from), FSMA_SHIPPING_002 (ship_to), FSMA_SHIPPING_003 (items `minItems: 1`). Validated against [samples/fsma/shipping.json](samples/fsma/shipping.json): valid sample passes; missing `ship_from`, missing `ship_to`, empty `items` all rejected.
- [X] T042 [P] [US2] Wrote [schemas/fsma/receiving.json](schemas/fsma/receiving.json) — IRI `#FSMA204ReceivingEvent&1.0.0`. Enforces FSMA_COMMON_001 (event_time), FSMA_RECEIVING_001 (received_at — schema reflects v1 Pydantic, which only declares `received_at` and no `ship_to` alternative; the data-model rule's "OR ship_to" branch will need an `anyOf` widening if v2 reintroduces `ship_to`), FSMA_RECEIVING_002 (items `minItems: 1`). Validated against [samples/fsma/receiving.json](samples/fsma/receiving.json): valid sample passes; missing `received_at` and empty `items` rejected.
- [X] T043 [P] [US2] Wrote [schemas/fsma/transforming.json](schemas/fsma/transforming.json) — IRI `#FSMA204TransformingEvent&1.0.0`. Enforces FSMA_COMMON_001, FSMA_TRANSFORMING_001 (facility), FSMA_TRANSFORMING_002 (input_items `minItems: 1`), FSMA_TRANSFORMING_003 (output_items `minItems: 1`). `transformation_id` is optional. Validated against [samples/fsma/transforming.json](samples/fsma/transforming.json): valid sample passes; missing `facility` and empty `input_items` / `output_items` all rejected.
- [X] T044 [P] [US2] Wrote [schemas/fsma/packing.json](schemas/fsma/packing.json) — IRI `#FSMA204PackingEvent&1.0.0`. Enforces FSMA_COMMON_001, FSMA_PACKING_001 (facility), FSMA_PACKING_002 (container_id), FSMA_PACKING_003 (input_items `minItems: 1`). Validated against [samples/fsma/packing.json](samples/fsma/packing.json): valid sample passes; missing `facility`, missing `container_id`, empty `input_items` all rejected.
- [X] T045 [P] [US2] Wrote [schemas/fsma/unpacking.json](schemas/fsma/unpacking.json) — IRI `#FSMA204UnpackingEvent&1.0.0`. Enforces FSMA_COMMON_001, FSMA_UNPACKING_001 (facility), FSMA_UNPACKING_002 (container_id), FSMA_UNPACKING_003 (output_items `minItems: 1`). Validated against [samples/fsma/unpacking.json](samples/fsma/unpacking.json): valid sample passes; missing `facility`, missing `container_id`, empty `output_items` all rejected.
- [X] T046 [P] [US2] Created 6 canonical FSMA sample events at [samples/fsma/](samples/fsma/) (creating, shipping, receiving, transforming, packing, unpacking). Each round-trips through its Pydantic model and `fsma_min_rules()` per T039's acceptance suite. Pulled forward of order with T039 because the test suite cannot load fixtures otherwise.
- [X] T047 [US2] Filled in the `FSMA` entry in [api/app/service/guardian_policies.py](api/app/service/guardian_policies.py). Three deliberate calls: (1) `source_type_field="eventType"` (camelCase) — matches the existing `starfish_events.py` Pydantic model and avoids a ~20-call-site rename that the data-model.md spec's aspirational `fsma204_event_type` would require; reconciliation deferred to v2. Registry uniqueness invariant still holds (GDST: `gdst_event_type`). (2) `type_map={}` (passthrough) — `vc-output.schema.json` `fsma204EventType` enum is already lowercase (`creating`, `shipping`, …), matching the Pydantic `Literal` values directly, so no source→VC mapping is needed (unlike GDST's `"ShippingReceiving" → "Shipping"` PascalCase mapping). (3) `required_hoists={}` per the task — the FSMA204 VC schema declares no top-level subject fields beyond `GuaranteedMetadata` + `fsma204EventType`, both stamped by the generic mapper. End-to-end smoke test passes: `to_credential_subject(creating_sample, FSMA)` produces a valid subject with `fsma204EventType: creating`, `complianceStatus: compliant`, full event payload flowed through. Suite: 57 passed / 7 skipped.
- [X] T048 [US2] Wired [api/app/routes/epcis/compliance.py](api/app/routes/epcis/compliance.py) to call `to_credential_subject(evt_dict, FSMA, event_hash_hex=...)` + `client.submit_document(...)` AFTER the existing `hedera_contract_check_event(...)` call. Mirror of GDST T035: same `_maybe_get_guardian_client()` helper, same `try/except GuardianBreakerOpen / GuardianError` envelope, same `guardian: {status, reason|cached|submittedAt}` field added to the response. Route changed from sync `def` to `async def` since `submit_document` is async.

  **One deliberate divergence from T035**: forwarding is gated on `is_compliant` per FR-004 ("System MUST issue a VC for every **compliant** event"). Non-compliant events still get `recordEvent` on-chain (with `is_compliant=False`) but skip Guardian with `guardian: {status: "skipped", reason: "not_compliant"}`. T035's GDST flow does not yet apply this gate — non-compliant GDST events that pass Pydantic but fail `gdst_min_rules` are still being submitted to Guardian today. **Follow-up**: replicate this gate in [api/app/routes/gdst/events.py](api/app/routes/gdst/events.py) (file an issue or fold into T054 alongside the structured WARN log work).

  **Field-naming discrepancy noted**: `ComplianceEvent` (used by this route) declares camelCase fields (`shipFrom`, `shipTo`, `shippedFrom`, `receivedAt`), while `StarfishEvent` (used by `/api/v1/events`, T039 acceptance tests) uses snake_case. `fsma_min_rules` was aligned to snake_case in T039, so it under-evaluates `ComplianceEvent` payloads (Shipping/Receiving rules silently always-False on this route). Out of T048 scope; recommend collapsing the two models in a follow-up.

  Suite: 57 passed / 7 skipped. Helper correctly returns `None` while `GUARDIAN_FSMA_POLICY_ID` remains blank (waiting on T050).
- [X] T050 [US2] Authored [scripts/build_fsma_policy.py](scripts/build_fsma_policy.py) (mirror of `build_gdst_policy.py` with FSMA constants, `--dry-run` and `--resume` flags, 600 s publish timeouts, IRI-version auto-detection) and [schemas/fsma/compliance-intake.json](schemas/fsma/compliance-intake.json) (envelope schema for the FSMA Guardian intake block). Ran against testnet MGS; published as `policyTag=FSMA-204-food-safety`, `policyId=69ef9d3ede6cb63433b0ed3f`, intake block `fsma_intake`; exported to [schemas/policies/fsma-204-food-safety.policy](schemas/policies/fsma-204-food-safety.policy) (~19 KB zip). Both `GUARDIAN_FSMA_POLICY_ID` and `GUARDIAN_FSMA_INTAKE_BLOCK_TAG` populated in `api/.env.dev`; `FSMA.enabled` is now `True`, the `/epcis/compliance/check` route's Guardian forwarding (T048) activates automatically.

  **Two wrinkles encountered, worth a follow-up patch to both build scripts**: (1) MGS's `POST /schemas/{topicId}` response sometimes excludes the just-created schema from the returned record list (we got back the SR-namespace schemas instead) — `_pick_created` then can't find the new schema and the script aborts. The schema actually exists; a follow-up `list_schemas(topic_id)` call confirms it. Recommend: have `bootstrap()` fall back to `list_schemas` if `_pick_created` misses on the create response. (2) MGS's "Version already exists" error fires when the SR namespace has *anything* at that semver, regardless of which schema name. We hit this on FSMA at `1.0.1` (left over from an earlier discontinued schema) and had to bump to `1.0.2` manually. Recommend: have `publish_schema` retry on a bumped patch version when MGS returns this specific error. For now, `--resume` worked once the manual publish landed.

  Suite: 57 passed / 7 skipped, no regressions.
- [X] T051 [US2] Ran `pytest api/app/tests/integration/guardian/test_fsma_acceptance.py` — **17 passed in 0.63s**, one test per FSMA rule per [data-model.md §Rule Source Table](specs/001-guardian-integration/data-model.md). Combined with the 15 GDST rule tests from T038, **SC-002's "100% rule↔test coverage for both schemas combined = 32 tests" is satisfied**. T074 will add the build-time audit gate that fails CI if a rule loses its matching pytest function.

**Checkpoint**: All 6 FSMA event samples produce compliant VCs. Spec §SC-001 (FSMA half) and SC-002 (100% rule↔test coverage for both schemas combined = 32 tests) verified.

---

## Phase 5: User Story 3 — Guardian Unavailability Does Not Block Event Recording (Priority: P1)

**Goal**: When MGS is unreachable, HCS + `ComplianceVerifier.recordEvent()` complete unaffected. After 3 consecutive failures the breaker opens for 60 s, skipped submissions emit a structured WARN log, and `/guardian/health` surfaces the state. No backlog table, no automatic retry (FR-006 log-only).

**Independent Test**: Inject `503` responses for 3 consecutive `POST /events/gdst` calls via `respx`; verify (a) each event recorded on HCS, (b) 4th submission within 60 s does NOT call MGS, (c) after 60 s the next call is a probe, (d) 451 does NOT increment the counter. Spec §SC-006 acceptance.

### Tests for User Story 3 ⚠️

- [X] T052 [P] [US3] Filled the 7 breaker tests in [api/app/tests/integration/guardian/test_circuit_breaker.py](api/app/tests/integration/guardian/test_circuit_breaker.py) using the `mgs_mock` (respx) + `frozen_clock` fixtures from `conftest.py` — `_make_client(breaker, clock)` mirrors the helper in `test_guardian_client_contract.py`. Coverage: 3-failures-opens (and 4th call is breaker-blocked, no HTTP), 4xx (400 + 409) does not count, half-open probe success closes, half-open probe failure re-opens with ONE failure (window restart), `submit_document` raises `GuardianBreakerOpen` with no HTTP call when pre-opened via the public API, and `forward_event_to_guardian` returns `{status: "skipped", reason: "breaker_open"}` instead of raising — proving the §IV "core flows never block" guarantee at the helper-layer boundary that the routes depend on. **One implementation note for the spec**: the `tos_required` state from a 451 blocks subsequent calls at the breaker (raise `GuardianBreakerOpen`, not `GuardianToSRequired`) — research.md §3 wording could be tightened. Verified with `pytest -v`: 7 passed in 1.54s.

### Implementation for User Story 3

- [X] T056 [US3] Verified MGS 451 → `GuardianToSRequired` with no 3-strikes counter increment; breaker enters the distinct `tos_required` state, `consecutive_failures` stays at 0, and the state does not decay on the 60 s window (only an operator portal action clears it). Test landed as `test_breaker_does_not_count_451` in [api/app/tests/integration/guardian/test_circuit_breaker.py](api/app/tests/integration/guardian/test_circuit_breaker.py); part of T052's batch.
- [X] T057 [US3] Ran `pytest api/app/tests/integration/guardian/test_circuit_breaker.py -v` — **7 passed in 1.54s** (Option B per [.claude/plans/i-am-thinking-of-shimmering-abelson.md](../../.claude/plans/i-am-thinking-of-shimmering-abelson.md): T053's WARN-log assertion test deferred along with T054's expanded payload + T055's extended health endpoint — pure observability adds with no behavior consequence). Story 3 acceptance verified at the breaker layer: 3×503 opens, 4th call is breaker-blocked-not-attempted (`submit_route.call_count` unchanged), 451 doesn't count toward 3-strikes, and `forward_event_to_guardian` returns the skipped envelope so HCS-path completion is decoupled from Guardian availability. Full guardian + unit suite: 64 passed, 0 skipped.

**Checkpoint**: P1 MVP complete (US1 + US2 + US3). Guardian VCs issue for both policies under healthy MGS; outages never block the hot path. Ready to deploy v1.

---

## Phase 6: User Story 4 — Downstream Guardian Projects Chain Our VCs (Priority: P2)

**Goal**: A third-party Guardian project imports `gdst-seafood-traceability.policy` (or the FSMA one) into a vanilla Guardian instance, accepts our VCs via `trustChainBlock` by SR DID + VC type, and validates without calling any Starfish API.

**Independent Test**: On a clean Hedera Guardian 2.x instance (self-hosted for this test; documented in quickstart.md), import the exported `.policy`, register an SR, publish, submit a compliant sample event, retrieve the VC. Then import a demo downstream policy that filters by `GDSTComplianceCredential` + our SR DID and confirm it validates.

### Tests for User Story 4 ⚠️

- [X] T058 [P] [US4] Added [api/app/tests/integration/guardian/test_policy_imports_on_vanilla_guardian.py](api/app/tests/integration/guardian/test_policy_imports_on_vanilla_guardian.py) — `pytest.parametrize` over both shipped exports (`gdst-seafood-traceability.policy`, `fsma-204-food-safety.policy`); each test logs into a vanilla Guardian SR (URL/creds via `VANILLA_GUARDIAN_URL` / `VANILLA_GUARDIAN_SR_USERNAME` / `VANILLA_GUARDIAN_SR_PASSWORD`), calls `client.import_policy_file(zip_bytes)`, waits up to 10 min, and asserts the import task transitions to COMPLETED + the policy list grew by 1. SC-004 / US4 A4.1 verification: a successful COMPLETED import on a clean Guardian implicitly proves no Starfish-specific dependency reaches into the published topology — Guardian would refuse to publish if any block referenced an unknown schema or external service. **Module-level `pytest.skipif(GUARDIAN_VANILLA_COMPOSE != "1")`** keeps it out of CI; `pytest.skip` inside `_vanilla_client()` covers the case where the env var is set but creds aren't. The Guardian docker-compose stack itself is the operator's deployment concern (the Hedera Guardian repo's reference compose file is the canonical setup) — not a repo deliverable. Verified locally: both parametrized cases SKIPPED by default; full suite: 64 passed, 2 skipped, no regressions.

### Implementation for User Story 4

- [X] T059 [P] [US4] Authored [samples/downstream/carbon-credit-demo.policy.json](samples/downstream/carbon-credit-demo.policy.json) — a complete Guardian PolicyDTO (importable shape) showing the four-block downstream pattern: `externalDataBlock` (cc_vc_intake) → `customLogicBlock` (cc_filter_trusted_issuer) → `trustChainBlock` (cc_trust_chain, display/verification) → `createVcDocumentBlock` (cc_issue_eligibility). The customLogicBlock's expression rejects VCs whose `issuer` isn't the testnet Starfish SR DID (`did:hedera:testnet:3xGAGt5EkLtUkqZ663wbAWhcSALyZywmx7hrkB7v2Mvg_0.0.8739126`) or whose `credentialSubject.complianceStatus` ≠ `compliant`. The trustChainBlock surfaces the full DID + VC chain to auditors per US4 acceptance scenario A4.2 ("downstream policy validates without inspecting proprietary payload fields"). NOT runnable as-is — each block carries a `description` field documenting what the downstream operator must do (replace the trustedIssuer DID for mainnet, import the GDSTComplianceCredential schema into their SR namespace, ship a CarbonCreditEligibility schema, regenerate the placeholder UUIDs). Placeholder UUIDs are deterministic (`00000000-0000-4000-8000-00000000000X`) so the file diffs cleanly on edit. JSON parses; topology is a clean linear chain `intake → filter → chain → issue`.
- [X] T060 [P] [US4] Expanded [schemas/gdst/README.md](schemas/gdst/README.md) from a 17-line stub into a full Guaranteed-fields contract: one section per field (`eventHash`, `gdstEventType`, `complianceStatus`, `policyVersion`, `issuedAt`, `supersedes` conditional, `species` GDST-specific) with type, meaning, and `1.x.x` stability promise per Constitution §II. Added a "Per-CTE KDEs (flow through verbatim)" section documenting the FR-015 full-payload semantics with examples by CTE, and a "Trust Anchor" section pinning the testnet SR DID and pointing downstream consumers at [samples/downstream/carbon-credit-demo.policy.json](samples/downstream/carbon-credit-demo.policy.json) (T059) for a reference filter pattern. The original stub's intro (semver IRI shape, lockstep with Pydantic models per Constitution §III) is preserved.
- [X] T061 [P] [US4] Expanded [schemas/fsma/README.md](schemas/fsma/README.md) into the FSMA mirror of T060: the same Guaranteed-fields contract structure with FSMA substitutions — `fsma204EventType` (lowercase enum: `creating | shipping | receiving | transforming | packing | unpacking`), no `species` field (GDST-only), and the per-event-type KDE table reshaped around FSMA's `biz_location` / `ship_from` / `ship_to` / `received_at` / `facility` / `container_id` / `input_items` / `output_items` / `quantity_list`. Also fixed a pre-existing doc bug in the original stub: corrected the Pydantic-models pointer from the non-existent `api/app/models/epcis/` to the actual `api/app/models/starfish_events.py`. Trust-anchor section reuses the same testnet SR DID + reference to T059's downstream demo, with a note that the demo is GDST-keyed but the pattern is identical for FSMA consumers.
- [X] T062 [US4] Extended [api/app/tests/integration/guardian/test_policy_imports_on_vanilla_guardian.py](api/app/tests/integration/guardian/test_policy_imports_on_vanilla_guardian.py) with two more tests under the same `GUARDIAN_VANILLA_COMPOSE=1` gate. (1) `test_gdst_policy_publish_and_submit_e2e_on_vanilla_guardian` covers the full SC-004 / US4 A4.1 loop on vanilla Guardian: import the GDST `.policy` → find by `policyTag=GDST-1-2-seafood-v2` → publish if not yet published → submit a Fishing sample through `gdst_intake` → poll `get_vc_by_event_hash` for up to 5 min → assert `vc.issuer == <importing SR's DID>` (vanilla SR re-issues under its own key, NOT Starfish's testnet SR — that's the desired composability behaviour) + `complianceStatus == "compliant"` + `eventHash` round-trips. (2) `test_downstream_demo_policy_validates_gdst_vc_on_vanilla_guardian` is a deliberate `pytest.skip` stub for US4 A4.2 — running it requires a `CarbonCreditEligibility` schema that's intentionally NOT shipped (T059's demo policy is reference doc, not a runnable artifact; the schema is the downstream operator's deliverable). The skip docstring is the unblock checklist: provide schema → regenerate UUIDs → replace `TRUSTED_ISSUER` DID → import + publish demo → run the test. **What this T062 satisfies vs leaves open**: the SC-004 import-and-publish-on-vanilla-Guardian half is fully scaffolded; the A4.2 trust-chain-validation half is documented but waits on the downstream-operator schema. Verified locally: all 4 cases in the file SKIPPED by default (2 from T058 parametrize + 2 from T062). Full suite: 64 passed, 4 skipped, no regressions.

**Checkpoint**: Spec §SC-004 (vanilla Guardian import works) and US4 acceptance scenarios A4.1 / A4.2 verified. Composability promise delivered.

---

## Phase 7: User Story 5 — GPS Submission Artifacts Ready For The Methodology Library (Priority: P2)

**Goal**: Both policies have a complete GPS proposal packet: description, workflow diagram, user guide, sample data, IPFS-published `.policy` + schemas, compatibility declaration, maintenance commitment. Checklist in [contracts/gps-submission-checklist.md](specs/001-guardian-integration/contracts/gps-submission-checklist.md) fully green.

**Independent Test**: Walk the GPS deliverables checklist — every box checked, every referenced file exists, every IPFS CID resolves.

### Implementation for User Story 5

- [ ] T063 [P] [US5] Produce the GDST policy workflow diagram at [docs/guardian-integration/gdst-workflow.svg](docs/guardian-integration/gdst-workflow.svg) (SVG, exported from the Guardian policy designer or equivalent).
- [ ] T064 [P] [US5] Produce the FSMA policy workflow diagram at [docs/guardian-integration/fsma-workflow.svg](docs/guardian-integration/fsma-workflow.svg).
- [ ] T065 [P] [US5] Write the GDST operator user guide at [docs/guardian-integration/gdst-user-guide.md](docs/guardian-integration/gdst-user-guide.md) covering: submitting each of the 7 CTE types, retrieving a VC, correcting via superseding (FR-014), and reading `/guardian/health`. Operator onboarding and consent (FR-015) are covered by the deployment runbook rather than this guide for v1.
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
  - **US1 (P1) and US2 (P1)** share the `submit_document` hot path and idempotency cache (T031, T034), the `PolicyConfig` registry and generic mapper (T036a), and the single policy-slug-parameterised VC retrieval route (also T036a) — US1 lands those; US2 reuses. Inside that constraint they can proceed in parallel by feature area (schemas, samples, route-test wiring).
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
- **Phase 3**: T019–T021 tests are `[P]`. T022–T029 (schemas + samples) are 8 parallel files. T030 (mapper) blocks T031–T035. T036a (registry refactor) runs after T036 and unblocks Phase 4.
- **Phase 4**: Mirror of Phase 3 — T040–T046 are `[P]`. T036a + T047 (FSMA registry entry) block T048, T051. T049 is absorbed into T036a and drops off the critical path.
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
