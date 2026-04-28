# Feature Specification: Guardian Integration — GDST & FSMA 204 Compliance Policies

**Feature Branch**: `001-guardian-integration`
**Created**: 2026-04-20
**Status**: Draft
**Input**: Adapted from [docs/guardian-integration/](../../docs/guardian-integration/) — `README.md`, `01-setup.md`, `02-schemas-and-policies.md`, `03-gps-submission.md`.

## Summary

Deliver two Hedera Guardian policies — **GDST 1.2 Seafood Traceability** and **FSMA 204 Food Safety** — as importable `.policy` files with versioned JSON-LD schemas, integrate them with our FastAPI event-ingestion flows via the Managed Guardian Service (MGS), and submit both to the Guardian Methodology Library under the Guardian Policy Standards (GPS) process. Policy exports are the primary product; FastAPI integration is how we use them internally.

## Clarifications

### Session 2026-04-20

- Q: On duplicate submission of the same `eventHash`, how many VCs exist? → A: Idempotent — one VC per `eventHash`; duplicate submit returns the existing VC unchanged, no new Guardian call.
- Q: How are events skipped by the open circuit breaker reconciled? → A: Log-only for v1. No automatic retry, no backlog table, no admin endpoint. Operators can manually replay via the idempotent `/events` endpoint; automatic reconciliation is deferred to v2.
- Q: How are wrongly-issued VCs corrected? Revocation model? → A: Append-only. VCs are immutable; a correction is a new VC with `credentialSubject.complianceStatus = "superseded"` and `credentialSubject.supersedes` pointing at the prior VC's `eventHash`. No revocation registry, no StatusList2021, no HCS revocation topic in v1.
- Q: What goes inside `credentialSubject`? Pseudonymous, minimal, or full payload? → A: Full payload — every field from the submitted event is embedded verbatim in the VC. Simplifies auditor flows and downstream trust-chains, at the cost of exposing all event fields (including operator identifiers, vessel details, and geolocation) to any party receiving the VC. PII minimization is deferred to v2.
- Q: Quantify "reasonable timeout" for pending-VC retrieval? → A: 30 s pending threshold, 5 min hard ceiling before the event is flagged `manual_review`. **Note (post-clarification)**: the `202 Accepted` / `503 VC_MANUAL_REVIEW` HTTP responses for `pending` / `manual_review` are **deferred to v2** (see §Edge Cases and §Assumptions). v1 surfaces the same state via `GuardianClient.get_vc_retrieval_status()`; the HTTP endpoint returns `200` with the VC when present and `404` otherwise.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — GDST-Compliant Supply-Chain Event Issues A VC (Priority: P1)

A Starfish operator submits a GDST Critical Tracking Event (e.g., a Fishing event) through our existing `/events` API. The event is validated, recorded on HCS, and forwarded to the GDST Guardian policy. If the event satisfies the policy's compliance rules, Guardian issues a `GDSTComplianceCredential` VC whose `credentialSubject.eventHash` matches the on-chain event hash. An auditor can later retrieve the VC via `/guardian/gdst/vc/{event_hash}`.

**Why this priority**: This is the core product loop. Without it, there is no compliance evidence to show auditors, and the `.policy` export has nothing to validate against.

**Independent Test**: With a published GDST policy on MGS and one operator pre-provisioned in the MGS portal (see deployment runbook), submit each of the 7 CTE samples under `samples/gdst/` and confirm each produces a VC whose `eventHash` matches the HCS event hash and whose `complianceStatus` is `compliant`.

**Acceptance Scenarios**:

1. **Given** a published GDST policy and an operator DID, **When** the operator submits a Fishing event with `vessel.vessel_id`, `iuu.fishing_authorization`, and `where.catch_area = "FAO71"`, **Then** the system records the event on HCS and Guardian issues a `GDSTComplianceCredential` retrievable by `event_hash`.
2. **Given** the same setup, **When** the operator submits a Fishing event missing `iuu.fishing_authorization`, **Then** FastAPI rejects with `422` (Pydantic validation error referencing `iuu.fishing_authorization`), no VC is issued, and the Guardian circuit-breaker counter does not increment (rejection is local, before any MGS call).
3. **Given** a Landing event with `iuu.landing_authorization` present, **When** submitted, **Then** a `GDSTComplianceCredential` is issued with `credentialSubject.complianceStatus = "compliant"`.
4. **Given** an Aggregation event with empty `parent_items` and empty `child_items` (passes Pydantic but fails `gdst_min_rules`), **When** submitted, **Then** the event is recorded on HCS with `isCompliant: false`, the response carries `guardian: {status: "skipped", reason: "not_compliant"}`, and no VC is issued.

### User Story 2 — FSMA-Compliant Supply-Chain Event Issues A VC (Priority: P1)

The same loop for FSMA 204: an operator submits a Creating/Shipping/Receiving/Transforming/Packing/Unpacking event, FastAPI validates, HCS records, the FSMA policy on MGS issues an `FSMA204ComplianceCredential` on pass.

**Why this priority**: FSMA covers the domestic-US traceability use case; it is needed at launch alongside GDST, not after.

**Independent Test**: With a published FSMA policy and one operator pre-provisioned in the MGS portal (see deployment runbook), submit each of the 6 FSMA samples under `samples/fsma/` and confirm each produces a VC whose `credentialSubject.eventHash` matches the HCS event hash.

**Acceptance Scenarios**:

1. **Given** a Creating event with non-empty `quantity_list` and a `biz_location`, **When** submitted, **Then** an `FSMA204ComplianceCredential` is issued.
2. **Given** a Shipping event without `ship_to`, **When** submitted, **Then** FastAPI rejects with `422` (Pydantic validation error referencing `ship_to`), no VC is issued, and the Guardian breaker counter does not increment.
3. **Given** a Transforming event with empty `output_items`, **When** submitted, **Then** FastAPI rejects with `422` (Pydantic `min_length=1` violation on `output_items`), no VC is issued.

### User Story 3 — Guardian Unavailability Does Not Block Event Recording (Priority: P1)

MGS is unreachable (network error, 5xx, or ToS not accepted → `451`). Operators continue submitting events; HCS and the on-chain `ComplianceVerifier.recordEvent()` calls complete normally. The Guardian client skips calls for 60 seconds after 3 consecutive failures. Skipped events are logged (structured log line including `event_hash`, `operator_did`, `mgs_error_class`, `breaker_opened_at`) and surfaced via `/guardian/health`; **v1 ships log-only, with no automatic reconciliation worker or backlog store.** Operators may replay a specific event manually by re-submitting to the idempotent `/events` endpoint (see FR-004). Automatic reconciliation is explicitly deferred to v2.

**Why this priority**: Constitution Principle IV is non-negotiable. Breaking this scenario means Guardian availability becomes a hard dependency of our core product — unacceptable.

**Independent Test**: Inject failing MGS responses (via test mock) for 3 consecutive event submissions; verify that (a) each event still records on HCS, (b) the 4th submission within 60 s does not attempt an MGS call, and (c) after 60 s, the client probes MGS again.

**Acceptance Scenarios**:

1. **Given** MGS returns `503` for three consecutive calls, **When** a fourth event is submitted within 60 s, **Then** `guardian_client` records a "skipped — breaker open" log entry, does NOT call MGS, and the HCS flow completes.
2. **Given** the breaker is open, **When** 60 s elapse and a new event arrives, **Then** the next MGS call is attempted; success closes the breaker, another failure resets the 60 s window.

### User Story 4 — Downstream Guardian Projects Chain Our VCs (Priority: P2)

A third-party Guardian project (e.g., carbon-credit, tax-credit) imports `gdst-seafood-traceability.policy` and uses its `GDSTComplianceCredential` VC as input via `trustChainBlock`, filtering by VC type and SR DID without calling any Starfish API.

**Why this priority**: Composability is the product's reach multiplier but is not required for our own compliance loop.

**Independent Test**: On a clean Guardian instance (can be self-hosted for this test), import the exported `.policy`, register an SR, publish, submit a compliant event via the policy's intake block, and retrieve the issued VC. A second policy references the VC by type and passes validation.

**Acceptance Scenarios**:

1. **Given** the exported `gdst-seafood-traceability.policy`, **When** imported into a vanilla Guardian instance and published, **Then** it runs without any Starfish-specific configuration, external service, or code.
2. **Given** a downstream policy that accepts `GDSTComplianceCredential`, **When** it receives a VC whose `credentialSubject` carries the documented Guaranteed fields (`eventHash`, `gdstEventType`, `complianceStatus`, `species`), **Then** it validates successfully without inspecting proprietary payload fields.

### User Story 5 — GPS Submission Artifacts Are Ready For The Methodology Library (Priority: P2)

Both policies have their full GPS proposal packet: description, workflow diagram, user guide, sample data, IPFS-published `.policy` + schemas, compatibility declaration, maintenance commitment.

**Why this priority**: Required for Methodology Library acceptance but not required for the policies to function.

**Independent Test**: Walk the deliverables checklist in [docs/guardian-integration/03-gps-submission.md §4](../../docs/guardian-integration/03-gps-submission.md) — every box checked and every referenced file exists and is valid.

**Acceptance Scenarios**:

1. **Given** the GDST submission packet, **When** cross-referenced against the GPS deliverables checklist, **Then** every required artifact is present and the IPFS CIDs resolve.
2. **Given** the FSMA submission packet, **When** cross-referenced similarly, **Then** every required artifact is present.

> **Rejection layers.** Acceptance scenarios above describe two distinct rejection paths:
>
> 1. **Pydantic 422** — most missing-field / format-violation rules (e.g. `iuu.fishing_authorization` required, `min_length=1` on lists) reject before the route body executes. The error payload references the offending field path; assertions use that field name, not a custom code string.
> 2. **`gdst_min_rules` / `fsma_min_rules` returning `False`** — covers rules Pydantic can't express (e.g. "vessel.vessel_id OR vessel.vessel_name", non-empty parent OR child items). Such events still record on HCS with `isCompliant: false` and skip Guardian forwarding (FR-004 compliance-only).
>
> Mapping each rule ID to its enforcement layer is documented in [data-model.md §Rule Source Table](data-model.md). v2 may add a custom-code surface for clients that want stable error identifiers separate from Pydantic's field paths.

### Edge Cases

- Duplicate event submission (same `eventHash`): the client MUST detect the duplicate via a local VC cache (or `GET /guardian/*/vc/{event_hash}`) before calling MGS, return the existing VC, and MUST NOT increment the circuit-breaker counter. No new HCS write, no new Guardian call.
- Correction of a wrongly-issued VC: operator submits a new corrective event through `/events`; the resulting VC carries `complianceStatus = "superseded"` and `supersedes = <prior eventHash>` (FR-014). The superseded VC stays retrievable via `?history=true` but is never overwritten or deleted.
- MGS returns `451` (ToS not accepted): treat as a hard failure, do NOT increment the circuit-breaker counter; expose via `/guardian/health` as a distinct `tos_required` status.
- A compliant event produces no VC within a bounded window because Guardian's task pipeline is backlogged. v1 surfaces the `pending` / `manual_review` state **via the Python `GuardianClient.get_vc_retrieval_status()` direct-caller contract** (see [contracts/guardian-client.md](contracts/guardian-client.md)), not over HTTP: at `< 30 s` post-submission the state is `pending`; at `≥ 300 s` it is `manual_review`. The HTTP endpoint `GET /guardian/{slug}/vc/{event_hash}` returns `200` with the VC when present and `404` otherwise (see [contracts/guardian-http-errors.md](contracts/guardian-http-errors.md)). Exposing `pending` / `manual_review` over HTTP (as `202 Accepted` / `503 VC_MANUAL_REVIEW`) is deferred to v2 so v1 ships a smaller HTTP surface.
- DID key rotation mid-flight: only operator DIDs rotate in v1 (the SR DID is pinned — `research.md` §2). Because Hedera DIDs resolve by DID document, the operator's DID string is stable across rotations and a pre-rotation VC remains verifiable by any W3C-compliant verifier without Starfish participation. No Starfish endpoint or test enforces this — it is delegated to the W3C VC verification semantics.
- Policy upgrade while events are in flight: version pinning in the client (`research.md` section Versioning) dictates whether in-flight submissions target the old or new version.
- MGS task-poll completion flag stuck `false`: on testnet `GET /tasks/{taskId}` returns `info.completed = false` indefinitely on schema/policy publish even after every sub-step transitions to `completed: true` and the underlying resource reaches `PUBLISHED`. `GuardianClient.wait_for_task` treats "all top-level `info.steps` completed and none failed" as task success in addition to the `info.completed` flag, so callers don't spin until the timeout on an already-finished task. Bootstrap scripts should still cap publish-class task waits at ≥10 minutes (Hedera mirror lag).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST export `gdst-seafood-traceability.policy` and `fsma-204-food-safety.policy` that import and publish on any Guardian instance (MGS or self-hosted) without Starfish-specific configuration.
- **FR-002**: System MUST ship 7 versioned GDST JSON-LD schemas (Fishing, Landing, Transshipment, OnVesselProcessing, Processing, Shipping, Aggregation) and 6 FSMA JSON-LD schemas (Creating, Shipping, Receiving, Transforming, Packing, Unpacking) under `schemas/gdst/` and `schemas/fsma/`, each with IRI `#<EventType>&<semver>`, and MUST IPFS-publish them as part of the GPS packet (FR-011, T067). The v1 Guardian policies attach a single envelope-intake schema each (`GDSTComplianceIntake` / `FSMA204ComplianceIntake`); the per-CTE schemas are GPS deliverables, not runtime attachments — see [constitution §III](../../.specify/memory/constitution.md) for the v1 exemption.
- **FR-003**: The compliance rules in `api/app/helpers/compliance.py` (`gdst_min_rules()` / `fsma_min_rules()`) MUST match the rule list in [data-model.md §Rule Source Table](data-model.md). The v1 Guardian policies do not duplicate rule enforcement at the Guardian layer — see [constitution §III](../../.specify/memory/constitution.md) for the v1 exemption and the v2 restoration plan.
- **FR-004**: System MUST issue a W3C Verifiable Credential (`GDSTComplianceCredential` or `FSMA204ComplianceCredential`) for every compliant event; `credentialSubject.eventHash` MUST equal the `bytes32` stored on-chain by `ComplianceVerifier.recordEvent()`. VC issuance MUST be idempotent on `eventHash`: a duplicate submission of a previously-recorded event MUST NOT trigger a new Guardian call and MUST return the existing VC unchanged (HTTP `200` from the `/events` endpoint; the client checks the VC cache before calling MGS). VCs MUST be treated as immutable once issued — no revocation registry, no StatusList2021, no HCS revocation topic in v1; corrections are handled exclusively via the superseding flow in FR-014.
- **FR-014**: To correct a previously-issued VC (e.g., forged IUU authorization surfaced post-hoc), the system MUST issue a **new** VC of the same type whose `credentialSubject` carries `complianceStatus = "superseded"` and `supersedes = <prior eventHash>`. The prior VC remains retrievable and unchanged. The VC-retrieval endpoints (FR-007) return the **latest** VC for a given `eventHash`; historical superseded VCs are retrievable via `GET /guardian/*/vc/{event_hash}?history=true` returning the chain in issuance order.
- **FR-005**: The Guardian client MUST open a circuit breaker for 60 s after 3 consecutive failures. Which MGS error classes count as "failure" is defined in `research.md` §Resilience.
- **FR-006**: Core HCS and `ComplianceVerifier` flows MUST complete unaffected when the Guardian breaker is open. Each skipped submission MUST emit a structured log entry (`event_hash`, `operator_did`, `mgs_error_class`, `breaker_opened_at`) at WARN level; no backlog table or async retry worker is in scope for v1. Manual replay via the idempotent `/events` endpoint (FR-004) is the only reconciliation path for v1.
- **FR-007**: FastAPI MUST expose `GET /guardian/health` and `GET /guardian/{policy_slug}/vc/{event_hash}` (with `policy_slug ∈ {gdst, fsma}`) per the endpoint list and HTTP status-code table in [contracts/guardian-http-errors.md](contracts/guardian-http-errors.md). The VC-retrieval endpoints MUST return exactly the **latest** VC for `event_hash` (single document, 404 if none exists). The optional `?history=true` query parameter returns the ordered chain `[oldest, …, latest]` for the same `event_hash`, so downstream consumers that need the full issuance history can obtain it without a separate endpoint. This is consistent with FR-004 (idempotent issuance) and FR-014 (superseding corrections). Operator onboarding endpoints (user registration, DID resolution) are **deferred to v2** — v1 assumes operators are pre-provisioned in the MGS portal.
- **FR-009**: `GET /guardian/health` MUST distinguish `ok`, `tos_required` (MGS `451`), `breaker_open`, and `unavailable`.
- **FR-010**: Each sample event under `samples/gdst/` and `samples/fsma/` MUST pass both the FastAPI pre-check and the matching Guardian policy, producing a VC. Samples are shared with test fixtures under `api/app/tests/fixtures/guardian/`.
- **FR-011**: The GPS submission packet for each policy MUST include: description, workflow diagram, explanatory video, user guide, sample data, IPFS-published artifacts, compatibility declaration, maintenance commitment. See `specs/001-guardian-integration/contracts/gps-submission-checklist.md`.
- **FR-012**: Schema versioning MUST be semver. Breaking changes publish a new schema with a bumped IRI; Starfish MUST NOT unpublish or delete prior versions. Resolvability of a published IRI is guaranteed by the Guardian runtime (MGS or self-hosted), not by Starfish code — consequently, no Starfish test covers "old IRI still resolves." The `.policy` export pins its schema IRIs by value, so downstream projects are not dependent on Starfish's config to resolve them.
- **FR-013**: Contract tests MUST exist for every `guardian_client` method before its production implementation is merged (Constitution §V).
- **FR-015**: VC `credentialSubject` MUST embed the full submitted event payload verbatim (all GDST KDEs / FSMA KDEs present on the event) plus the Guaranteed metadata fields (`eventHash`, `gdstEventType` or `fsma204EventType`, `complianceStatus`, `policyVersion`, `issuedAt`, `supersedes`). Operator consent for this disclosure posture — acknowledgement that any party receiving a VC can read all event fields, including operator and vessel identifiers and catch geolocation — MUST be captured **out-of-band** by the deployer before provisioning the operator in the MGS portal, and a signed consent record MUST be retained locally (see deployment runbook). v1 does not issue programmatic consent prompts; selective disclosure / redaction is out of scope for v1.

### Key Entities

- **GDST Critical Tracking Event (CTE)**: Fishing | Landing | Transshipment | OnVesselProcessing | Processing | Shipping | Aggregation. Shared fields: `who`, `what`, `where`, `when`, `iuu`.
- **FSMA Event**: Creating | Shipping | Receiving | Transforming | Packing | Unpacking. Shared field: `event_time`.
- **Verifiable Credential (VC)**: W3C v1 VC signed by the SR DID with semantic type `GDSTComplianceCredential` or `FSMA204ComplianceCredential`. `credentialSubject` embeds the **full submitted event payload verbatim** (all GDST KDEs / FSMA KDEs for the event type) alongside the Guaranteed metadata fields (`eventHash`, `gdstEventType` or `fsma204EventType`, `complianceStatus`, `policyVersion`, `issuedAt`, `supersedes`). The canonical field list per event type is in `data-model.md` and is mirrored by `contracts/vc-output.schema.json`. VCs are **immutable** once issued (no revocation); corrections are represented as a newer VC with `complianceStatus = "superseded"` and `supersedes = <prior eventHash>` (FR-014). Downstream trust-chains can trust a VC on the sole basis of (a) SR DID as issuer, (b) signature validity, (c) `complianceStatus = "compliant"`, with no external revocation-state fetch.
- **Standard Registry (SR)**: Single Guardian role that owns both policies; its Hedera DID is the trust anchor for all issued VCs.
- **Operator**: Guardian `User` role mapping to the existing Starfish `operator`. Has a Hedera DID, submits events, receives VCs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the 13 sample events (7 GDST + 6 FSMA) under `samples/` produce a compliant VC in an end-to-end test against MGS.
- **SC-002**: 100% of compliance rules in `gdst_min_rules()` and `fsma_min_rules()` have a matching pytest acceptance test and a matching rule in the Guardian policy.
- **SC-003**: With MGS injected as failing, event-recording throughput (HCS writes/min) is unchanged from baseline; p95 latency of `/events` increases by no more than 5%.
- **SC-007**: Under healthy MGS, `GET /guardian/*/vc/{event_hash}` returns `200` with the VC within 30 s of submission for 95% of events. No event stays `pending` beyond the 5 min hard ceiling; any event that does is flagged `manual_review` and surfaced via `/guardian/health`.
- **SC-004**: `.policy` exports import and publish on a vanilla Guardian instance with zero manual code changes.
- **SC-005**: Both GPS submissions pass the GPS deliverables checklist review on first submission.
- **SC-006**: Zero Guardian-related incidents cause HCS write failures in the first 30 days after rollout.

## Assumptions

- MGS tenant provisioned at <https://guardianservice.app> (REST base: `https://guardianservice.app/api/v1`). Tenant ID is held per-environment in `GUARDIAN_*` secrets, not in the repo. (Tracked in [docs/guardian-integration/01-setup.md §1](../../docs/guardian-integration/01-setup.md).)
- The existing Pydantic event models in `api/app/models/gdst/` and `api/app/models/starfish_events.py` are the source of truth for field names and types; Guardian schemas are derived from them.
- `ComplianceVerifier.recordEvent()` already emits a `bytes32` event hash we can reuse as `credentialSubject.eventHash` without re-hashing.
- All target Guardian runtimes (MGS at time of development, self-hosted Guardian for `.policy` imports) support the Guardian block types used (`externalDataBlock`, `createVcDocumentBlock`, `trustChainBlock`).
- Testnet is used for all non-production work; Mainnet rollout is a separate deployment step out of scope for v1.
- Automatic reconciliation of events skipped by the open breaker is **out of scope for v1**. v2 may add a backlog table and reconciler worker; the v1 spec must not assume they exist.
- PII in VC payloads is accepted as a tradeoff: VCs embed the full event verbatim (FR-015). Selective disclosure, BBS+ signatures, and redaction are deferred to v2. Consent for this posture is captured out-of-band by the deployer (see FR-015) — v1 does not ship an in-product consent prompt.
- Operator onboarding is **out of scope for v1**. Operators (Guardian `User` accounts and their Hedera DIDs) are pre-provisioned in the MGS portal by the deployer before any event is submitted; the `GUARDIAN_SR_*` credentials in the env file belong to the Standard Registry, not to operators. v2 may add FastAPI endpoints for operator self-service registration and DID resolution; the v1 spec must not assume they exist.
- Explanatory videos for GPS submission are produced by a team member outside the scope of code; the spec only requires the URL/CID to be recorded.
- The HTTP `202 Accepted` / `503 VC_MANUAL_REVIEW` responses for pending / manual-review retrieval are **deferred to v2**; v1 exposes the same state only through the Python client's `GuardianClient.get_vc_retrieval_status()` contract. SC-007's 30 s / 5 min thresholds remain in effect, measured via that contract and the T072 benchmark.
