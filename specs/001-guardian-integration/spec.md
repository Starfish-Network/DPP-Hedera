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
- Q: Quantify "reasonable timeout" for pending-VC retrieval? → A: Initial `202 Accepted` threshold 30 s, hard ceiling 5 min before the event is flagged `manual_review`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — GDST-Compliant Supply-Chain Event Issues A VC (Priority: P1)

A Starfish operator submits a GDST Critical Tracking Event (e.g., a Fishing event) through our existing `/events` API. The event is validated, recorded on HCS, and forwarded to the GDST Guardian policy. If the event satisfies the policy's compliance rules, Guardian issues a `GDSTComplianceCredential` VC whose `credentialSubject.eventHash` matches the on-chain event hash. An auditor can later retrieve the VC via `/guardian/gdst/vc/{event_hash}`.

**Why this priority**: This is the core product loop. Without it, there is no compliance evidence to show auditors, and the `.policy` export has nothing to validate against.

**Independent Test**: With a published GDST policy on MGS and one operator user registered, submit each of the 7 CTE samples under `samples/gdst/` and confirm each produces a VC whose `eventHash` matches the HCS event hash and whose `complianceStatus` is `compliant`.

**Acceptance Scenarios**:

1. **Given** a published GDST policy and an operator DID, **When** the operator submits a Fishing event with `vessel.vessel_id`, `iuu.fishing_authorization`, and `where.catch_area = "FAO71"`, **Then** the system records the event on HCS and Guardian issues a `GDSTComplianceCredential` retrievable by `event_hash`.
2. **Given** the same setup, **When** the operator submits a Fishing event missing `iuu.fishing_authorization`, **Then** FastAPI rejects with `400` and error code `GDST_MISSING_FISHING_AUTHORIZATION`, no VC is issued, and the Guardian circuit-breaker counter does not increment (rejection is local).
3. **Given** a Landing event with `iuu.landing_authorization` present, **When** submitted, **Then** a `GDSTComplianceCredential` is issued with `credentialSubject.complianceStatus = "compliant"`.
4. **Given** an Aggregation event with empty `parent_items` and empty `child_items`, **When** submitted, **Then** FastAPI rejects with `400` / `GDST_AGGREGATION_EMPTY`.

### User Story 2 — FSMA-Compliant Supply-Chain Event Issues A VC (Priority: P1)

The same loop for FSMA 204: an operator submits a Creating/Shipping/Receiving/Transforming/Packing/Unpacking event, FastAPI validates, HCS records, the FSMA policy on MGS issues an `FSMA204ComplianceCredential` on pass.

**Why this priority**: FSMA covers the domestic-US traceability use case; it is needed at launch alongside GDST, not after.

**Independent Test**: With a published FSMA policy and one registered operator, submit each of the 6 FSMA samples under `samples/fsma/` and confirm each produces a VC whose `credentialSubject.eventHash` matches the HCS event hash.

**Acceptance Scenarios**:

1. **Given** a Creating event with non-empty `quantity_list` and a `biz_location`, **When** submitted, **Then** an `FSMA204ComplianceCredential` is issued.
2. **Given** a Shipping event without `ship_to`, **When** submitted, **Then** FastAPI rejects with `400` / `FSMA_MISSING_SHIP_TO`.
3. **Given** a Transforming event with empty `output_items`, **When** submitted, **Then** FastAPI rejects with `400` / `FSMA_TRANSFORMING_NO_OUTPUTS`.

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

> **Error-code convention.** The error codes used in acceptance scenarios above
> (e.g. `GDST_MISSING_FISHING_AUTHORIZATION`, `FSMA_MISSING_SHIP_TO`) are the
> *FastAPI response* codes. Each maps 1:1 to a rule ID in
> [data-model.md §Rule Source Table](data-model.md) — e.g.
> `GDST_MISSING_FISHING_AUTHORIZATION` is the API code for rule `GDST_FISHING_002`.
> The concrete mapping table is produced as part of `/speckit-implement` and
> kept next to `api/app/helpers/compliance.py`.

### Edge Cases

- Duplicate event submission (same `eventHash`): the client MUST detect the duplicate via a local VC cache (or `GET /guardian/*/vc/{event_hash}`) before calling MGS, return the existing VC, and MUST NOT increment the circuit-breaker counter. No new HCS write, no new Guardian call.
- Correction of a wrongly-issued VC: operator submits a new corrective event through `/events`; the resulting VC carries `complianceStatus = "superseded"` and `supersedes = <prior eventHash>` (FR-014). The superseded VC stays retrievable via `?history=true` but is never overwritten or deleted.
- MGS returns `451` (ToS not accepted): treat as a hard failure, do NOT increment the circuit-breaker counter; expose via `/guardian/health` as a distinct `tos_required` status.
- MGS returns `409` on user registration (username exists): the client resolves the existing DID and reuses it rather than erroring.
- A compliant event produces no VC within a bounded window because Guardian's task pipeline is backlogged: if the VC is not visible within **30 s** of submission, `GET /guardian/*/vc/{event_hash}` returns `202 Accepted` with `{ "status": "pending", "submitted_at": ... }`. A retrieval-side polling loop re-queries `GET /policies/{id}/documents?type=VC` by `credentialSubject.eventHash`; if no VC is produced within the hard ceiling of **5 min** from submission, the event is marked `manual_review` and subsequent retrievals return `503 VC_MANUAL_REVIEW` until an operator re-submits or escalates.
- DID key rotation mid-flight: events recorded before rotation MUST still validate against their VCs after rotation; resolution procedure is pinned in `research.md`.
- Policy upgrade while events are in flight: version pinning in the client (`research.md` section Versioning) dictates whether in-flight submissions target the old or new version.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST export `gdst-seafood-traceability.policy` and `fsma-204-food-safety.policy` that import and publish on any Guardian instance (MGS or self-hosted) without Starfish-specific configuration.
- **FR-002**: System MUST publish 7 versioned GDST JSON-LD schemas (Fishing, Landing, Transshipment, OnVesselProcessing, Processing, Shipping, Aggregation) and 6 FSMA JSON-LD schemas (Creating, Shipping, Receiving, Transforming, Packing, Unpacking), each with IRI `#<EventType>&<semver>`.
- **FR-003**: For every event type, the Guardian policy's compliance rules MUST match the corresponding rules in `api/app/helpers/compliance.py` (`gdst_min_rules()` / `fsma_min_rules()`). See `data-model.md` §"Rule Source Table."
- **FR-004**: System MUST issue a W3C Verifiable Credential (`GDSTComplianceCredential` or `FSMA204ComplianceCredential`) for every compliant event; `credentialSubject.eventHash` MUST equal the `bytes32` stored on-chain by `ComplianceVerifier.recordEvent()`. VC issuance MUST be idempotent on `eventHash`: a duplicate submission of a previously-recorded event MUST NOT trigger a new Guardian call and MUST return the existing VC unchanged (HTTP `200` from the `/events` endpoint; the client checks the VC cache before calling MGS). VCs MUST be treated as immutable once issued — no revocation registry, no StatusList2021, no HCS revocation topic in v1; corrections are handled exclusively via the superseding flow in FR-014.
- **FR-014**: To correct a previously-issued VC (e.g., forged IUU authorization surfaced post-hoc), the system MUST issue a **new** VC of the same type whose `credentialSubject` carries `complianceStatus = "superseded"` and `supersedes = <prior eventHash>`. The prior VC remains retrievable and unchanged. The VC-retrieval endpoints (FR-007) return the **latest** VC for a given `eventHash`; historical superseded VCs are retrievable via `GET /guardian/*/vc/{event_hash}?history=true` returning the chain in issuance order.
- **FR-005**: The Guardian client MUST open a circuit breaker for 60 s after 3 consecutive failures. Which MGS error classes count as "failure" is defined in `research.md` §Resilience.
- **FR-006**: Core HCS and `ComplianceVerifier` flows MUST complete unaffected when the Guardian breaker is open. Each skipped submission MUST emit a structured log entry (`event_hash`, `operator_did`, `mgs_error_class`, `breaker_opened_at`) at WARN level; no backlog table or async retry worker is in scope for v1. Manual replay via the idempotent `/events` endpoint (FR-004) is the only reconciliation path for v1.
- **FR-007**: FastAPI MUST expose `GET /guardian/health`, `POST /guardian/register`, `GET /guardian/did/{username}`, `GET /guardian/gdst/vc/{event_hash}`, `GET /guardian/fsma/vc/{event_hash}` with the error codes listed in [docs/guardian-integration/01-setup.md §5](../../docs/guardian-integration/01-setup.md). The VC-retrieval endpoints MUST return exactly the **latest** VC for `event_hash` (single document, 404 if none exists). The optional `?history=true` query parameter returns the ordered chain `[oldest, …, latest]` for the same `event_hash`, so downstream consumers that need the full issuance history can obtain it without a separate endpoint. This is consistent with FR-004 (idempotent issuance) and FR-014 (superseding corrections).
- **FR-008**: User registration MUST handle `409` (username exists) by resolving and reusing the existing DID rather than erroring.
- **FR-009**: `GET /guardian/health` MUST distinguish `ok`, `tos_required` (MGS `451`), `breaker_open`, and `unavailable`.
- **FR-010**: Each sample event under `samples/gdst/` and `samples/fsma/` MUST pass both the FastAPI pre-check and the matching Guardian policy, producing a VC. Samples are shared with test fixtures under `api/app/tests/fixtures/guardian/`.
- **FR-011**: The GPS submission packet for each policy MUST include: description, workflow diagram, explanatory video, user guide, sample data, IPFS-published artifacts, compatibility declaration, maintenance commitment. See `specs/001-guardian-integration/contracts/gps-submission-checklist.md`.
- **FR-012**: Schema versioning MUST be semver. Breaking changes get a new version; old versions remain resolvable via their IRI.
- **FR-013**: Contract tests MUST exist for every `guardian_client` method before its production implementation is merged (Constitution §V).
- **FR-015**: VC `credentialSubject` MUST embed the full submitted event payload verbatim (all GDST KDEs / FSMA KDEs present on the event) plus the Guaranteed metadata fields (`eventHash`, `gdstEventType` or `fsmaEventType`, `complianceStatus`, `policyVersion`, `issuedAt`, `supersedes`). Operators MUST be informed at onboarding that any party receiving a VC can read all event fields, including operator and vessel identifiers and catch geolocation. Selective disclosure / redaction is out of scope for v1.

### Key Entities

- **GDST Critical Tracking Event (CTE)**: Fishing | Landing | Transshipment | OnVesselProcessing | Processing | Shipping | Aggregation. Shared fields: `who`, `what`, `where`, `when`, `iuu`.
- **FSMA Event**: Creating | Shipping | Receiving | Transforming | Packing | Unpacking. Shared field: `event_time`.
- **Verifiable Credential (VC)**: W3C v1 VC signed by the SR DID with semantic type `GDSTComplianceCredential` or `FSMA204ComplianceCredential`. `credentialSubject` embeds the **full submitted event payload verbatim** (all GDST KDEs / FSMA KDEs for the event type) alongside the Guaranteed metadata fields (`eventHash`, `gdstEventType` or `fsmaEventType`, `complianceStatus`, `policyVersion`, `issuedAt`, `supersedes`). The canonical field list per event type is in `data-model.md` and is mirrored by `contracts/vc-output.schema.json`. VCs are **immutable** once issued (no revocation); corrections are represented as a newer VC with `complianceStatus = "superseded"` and `supersedes = <prior eventHash>` (FR-014). Downstream trust-chains can trust a VC on the sole basis of (a) SR DID as issuer, (b) signature validity, (c) `complianceStatus = "compliant"`, with no external revocation-state fetch.
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

- MGS tenant for the project will be provisioned; placeholder `<mgs-tenant>` in config is replaced once available. (Tracked in [docs/guardian-integration/01-setup.md §1](../../docs/guardian-integration/01-setup.md).)
- The existing Pydantic event models in `api/app/models/gdst/` and `api/app/models/starfish_events.py` are the source of truth for field names and types; Guardian schemas are derived from them.
- `ComplianceVerifier.recordEvent()` already emits a `bytes32` event hash we can reuse as `credentialSubject.eventHash` without re-hashing.
- All target Guardian runtimes (MGS at time of development, self-hosted Guardian for `.policy` imports) support the Guardian block types used (`externalDataBlock`, `createVcDocumentBlock`, `trustChainBlock`).
- Testnet is used for all non-production work; Mainnet rollout is a separate deployment step out of scope for v1.
- Automatic reconciliation of events skipped by the open breaker is **out of scope for v1**. v2 may add a backlog table and reconciler worker; the v1 spec must not assume they exist.
- PII in VC payloads is accepted as a tradeoff: VCs embed the full event verbatim (FR-015). Selective disclosure, BBS+ signatures, and redaction are deferred to v2. Consent for this posture MUST be captured at operator onboarding before any VC is issued.
- Explanatory videos for GPS submission are produced by a team member outside the scope of code; the spec only requires the URL/CID to be recorded.
