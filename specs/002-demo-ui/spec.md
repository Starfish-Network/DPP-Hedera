# Feature Specification: Demo UI for GDST + FSMA Guardian Integration

**Feature Branch**: `002-demo-ui` (working on `dev`)
**Created**: 2026-04-29
**Status**: Draft
**Input**: User request — "I want to plan a demo UI to showcase this" (referring to the shipped 001-guardian-integration backend).

## Summary

A small, self-contained UI that walks a viewer (GPS reviewer, prospective customer, internal stakeholder) through the **end-to-end Guardian compliance loop** running on top of the existing FastAPI backend: submit a GDST or FSMA event, watch it record on Hedera, see Guardian issue a Verifiable Credential, retrieve the VC by `eventHash`, and exercise the resilience surface (breaker open / 451 / superseding correction). The UI is a thin presentation layer over the live `api/v1/*` endpoints — no new business logic, no parallel data store. Deployable as a single page that someone can open during a 5-minute demo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Reviewer Sees a GDST Event Become a VC (Priority: P1)

A GPS reviewer or prospective customer opens the demo UI. They pick a sample GDST event (Fishing) from a dropdown, hit "Submit", and watch the UI report each stage: Pydantic validation passed, HCS transaction id, Guardian acceptance, then (after polling) the issued `GDSTComplianceCredential` with its Guaranteed fields displayed.

**Why this priority**: This is the core narrative the demo exists to tell. Without it there's nothing to showcase.

**Independent Test**: Start the FastAPI backend with `GUARDIAN_GDST_POLICY_ID` populated (current state). Open the UI. Pick `samples/gdst/fishing.json` from the dropdown. Click submit. Confirm the response section fills in HCS transactionId, Guardian status `submitted`, and (within ~60s) the retrieved VC's `credentialSubject` panel shows `eventHash`, `gdstEventType: "Fishing"`, `complianceStatus: "compliant"`, `species`.

**Acceptance Scenarios**:

1. **Given** the backend is running and Guardian is configured, **When** the user submits a valid Fishing sample, **Then** the UI displays HCS receipt, Guardian-submission ack, and the issued VC's Guaranteed fields within 60 seconds.
2. **Given** the same setup, **When** the user submits a Fishing event missing `iuu.fishing_authorization`, **Then** the UI displays the `422` Pydantic validation error with the offending field name highlighted, no HCS transaction is shown, and Guardian section is greyed out.
3. **Given** the same setup, **When** the user submits an Aggregation event with empty `parent_items` AND empty `child_items`, **Then** the UI shows HCS receipt with `isCompliant: false` and Guardian section reads "Skipped — not_compliant" (the G1 gate from the recent /speckit-analyze remediation).

### User Story 2 — Reviewer Sees the FSMA Path (Priority: P1)

Same loop but for the FSMA 204 policy. Demonstrates that the registry pattern handles a second policy generically (Constitution §II composability).

**Why this priority**: The GPS submission packet covers BOTH policies. A reviewer needs to see both work to grant approval.

**Independent Test**: Pick a Creating sample → see `FSMA204ComplianceCredential` issued with `fsma204EventType: "creating"`. Repeat for at least one Shipping sample.

**Acceptance Scenarios**:

1. **Given** `GUARDIAN_FSMA_POLICY_ID` is populated, **When** the user submits a Creating sample, **Then** the UI shows the issued `FSMA204ComplianceCredential` with `fsma204EventType: "creating"` and `complianceStatus: "compliant"`.
2. **Given** the same setup, **When** the user submits a Shipping event missing `ship_to`, **Then** UI displays the Pydantic 422 error referencing `ship_to`.

### User Story 3 — Reviewer Sees Resilience (Priority: P2 — **DEFERRED to v1.1**)

> **Out of MVP scope.** The header health badge (always visible, top-right) covers the resilience signal at low cost; on-demand simulator + dedicated tab adds clarity for technical audiences but not for the core compliance narrative. Add back when an engineering reviewer asks. Implementation scaffolding (`GUARDIAN_DEMO_ROUTES_ENABLED` env-var gate) is already in place from T002, so resuming this story is purely additive.

The UI surfaces `/guardian/health` live and lets the user **manually trigger** a simulated MGS outage to demonstrate Constitution §IV ("core flows never block"). After a few simulated failures, the breaker opens; subsequent events still record on HCS but show `guardian: skipped — breaker_open`. After 60s the breaker probes again.

**Why this priority**: Demonstrates the resilience story — important for an enterprise audience but not the core compliance narrative.

**Independent Test**: Toggle "Simulate MGS down" → submit 3 events → confirm breaker opens → submit a 4th → see `breaker_open`. Wait 60s → confirm probe.

**Acceptance Scenarios**:

1. **Given** the breaker is closed, **When** the user toggles the outage simulator and submits 3 events, **Then** each event still gets an HCS transactionId, `/guardian/health` transitions through `ok → unavailable`, and after the 3rd failure shows `breaker_open`.
2. **Given** the breaker is open, **When** the user clears the simulator and waits 60s, **Then** the next event submission probes Guardian successfully and the health endpoint returns to `ok`.

### User Story 4 — Auditor Retrieves a VC by Event Hash (Priority: P2)

A separate "Retrieve" tab/page accepts an `eventHash` and shows the latest VC, optionally with `?history=true` to display the full superseding chain.

**Why this priority**: Demonstrates `GET /guardian/{slug}/vc/{event_hash}` (FR-007). Useful for auditor demos.

**Independent Test**: After submitting a Fishing event, copy the `eventHash`, paste into the Retrieve form → see the VC. Toggle "include history" → see the same single entry until a corrective VC has been issued.

**Acceptance Scenarios**:

1. **Given** a VC exists for an `eventHash`, **When** the user enters the hash and clicks Retrieve, **Then** the UI shows the VC's `credentialSubject` and `proof` summary.
2. **Given** a corrective VC has been issued for the same `eventHash` (manual or via a "Submit Correction" UI affordance), **When** the user toggles "include history", **Then** the UI shows the chain `[oldest, …, latest]` with the oldest entry marked `superseded` and the latest `compliant`.

### Edge Cases

- Backend not running: the UI's status indicator (top-right) shows "API offline" instead of crashing on the first action.
- `GUARDIAN_*_POLICY_ID` not set: the UI greys out the matching policy's submit button and explains "policy not configured — run `scripts/build_*_policy.py`".
- VC retrieval polling hits the 5-minute `manual_review` ceiling: UI surfaces this with a clear "manual review required" badge rather than spinning forever.
- Browser tab in background while polling: tab returns to foreground, polling resumes from current state — no duplicate submissions.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The UI MUST present a sample-event picker for both GDST (7 CTEs) and FSMA (6 event types) sourced live from `samples/gdst/*.json` and `samples/fsma/*.json` so the picker stays in sync with what's checked into the repo.
- **FR-002**: The UI MUST submit the picked sample to the existing `POST /api/v1/gdst/events` (GDST) or `POST /api/v1/epcis/compliance/check` (FSMA) endpoints — no new backend route.
- **FR-003**: The UI MUST poll `GET /api/v1/guardian/{slug}/vc/{event_hash}` after submission and surface the VC's Guaranteed fields (`eventHash`, `<slug>EventType`, `complianceStatus`, `policyVersion`, `issuedAt`, optional `supersedes`, GDST-only `species`) plus the full `credentialSubject` JSON.
- **FR-004**: The UI MUST display the response object verbatim alongside a human-readable summary so a reviewer can correlate the underlying API to the rendered story.
- **FR-005**: The UI MUST surface `/api/v1/guardian/health` live (auto-refresh every 5s) with the four states (`ok | tos_required | breaker_open | unavailable`).
- **FR-006**: The UI MUST provide a "simulate MGS outage" toggle that tells the backend to inject failures (mechanism TBD in research.md — likely an env-toggleable test endpoint OR a respx-style request interceptor).
- **FR-007**: The UI MUST allow VC retrieval by arbitrary `eventHash` (not just events submitted within the current session), with `?history=true` toggle to display the supersedes chain in issuance order.
- **FR-008**: The UI MUST treat `isCompliant: false` events as a first-class outcome — show the HCS receipt + the explicit "Guardian skipped: not_compliant" rationale rather than treating it as an error.
- **FR-009**: The UI MUST work offline-of-Guardian — if `GUARDIAN_*_POLICY_ID` is empty or `/guardian/health` reports `breaker_open`, the UI greys the relevant Guardian panels but keeps the HCS-submit half operational (Constitution §IV).
- **FR-010**: The UI MUST extend the existing [ui/trace-ui/](../../ui/trace-ui/) React + Vite + TypeScript + Tailwind app. Launch is `cd ui/trace-ui && npm run dev` alongside the existing FastAPI server — no second frontend, no docker-compose required for a 5-minute showcase. Reuses the Vite proxy at [vite.config.ts](../../ui/trace-ui/vite.config.ts) that already routes `/api/v1` to `http://localhost:8000`.
- **FR-011**: The UI MUST NOT introduce a parallel data store, schema mapper, or compliance predicate. The existing FastAPI is the only backend; this layer is presentation-only. Existing TypeScript types (`GDSTEvent`, `StarfishEvent`, `ComplianceCheckResponse`) are extended additively rather than reimplemented.

### Key Entities

The UI surfaces existing entities — does not introduce new ones:

- **Event** (GDST CTE | FSMA Event) — picked from the on-disk samples.
- **HCS Receipt** — `transactionId`, `receiptStatus` from the existing `/events` response.
- **Guardian Submission Status** — the route's existing `guardian: {status, reason|cached|submittedAt}` envelope.
- **Verifiable Credential** — `GDSTComplianceCredential` or `FSMA204ComplianceCredential`, surfaced via `GET /guardian/{slug}/vc/{event_hash}`.
- **Health** — `{status, breaker, last_failure_at}` from `/guardian/health`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time viewer can submit a GDST sample and see the issued VC appear in the UI within **90 seconds** without any documentation lookup. Measured by walking three new colleagues through an unguided demo.
- **SC-002**: The Guardian Demo extension adds **zero net new external dependencies** to the existing `ui/trace-ui/package.json` for the basic submit/retrieve/health flows. (One small dev-only backend dep may land for the simulator, gated behind `GUARDIAN_DEMO_ROUTES_ENABLED`.) No new build pipeline.
- **SC-003**: The UI starts up and renders the three MVP user-story flows (US1, US2, US4) correctly with **`pip install -r api/requirements.txt`** for the backend and **`cd ui/trace-ui && npm install` (already done) + `npm run dev`** for the frontend. Measured by reproducing on a clean checkout. (US3 is deferred to v1.1 — see note above.)
- **SC-004**: The Guardian-integration spec's claims (FR-004 idempotency, FR-007 retrieval, FR-014 superseding) are each **directly demonstrable** via a button or toggle in the UI — one-click reproduction of the corresponding acceptance scenarios. **FR-006 (breaker) is partially demonstrated** via the always-visible header health badge; the on-demand simulator that exercises the open→half-open→closed cycle moves to v1.1 with US3.
- **SC-005**: The UI degrades gracefully when Guardian is unconfigured / unavailable: a viewer sees an explanatory empty state, not a stack trace. Tested by running with `GUARDIAN_FSMA_POLICY_ID=` (empty) and `GUARDIAN_API_URL=http://invalid:9999`.

## Assumptions

- The existing 001-guardian-integration FastAPI is **already running** and reachable when the UI is launched. The UI is not a deployable web app on its own — it's a demo client.
- The user submitting events through the UI has the SR credentials in `api/.env.dev` already (current state).
- Mainnet / production rollout of the demo UI is **out of scope** for v1. This feature targets local-dev demos and stakeholder previews.
- The "simulate MGS outage" feature (FR-006) requires a backend hook — exact mechanism is a research item. Acceptable trade-offs include a dev-only `/api/v1/_test/breaker/{open|close}` admin endpoint or wrapping the GuardianClient in a test-mode interceptor.
- No authentication/authorization on the UI itself — it inherits whatever the FastAPI backend enforces. v1 ships without a login gate.
- No persistence of user actions — refreshing the page wipes the session-scoped event history. v2 may add a "demo timeline" if useful.
