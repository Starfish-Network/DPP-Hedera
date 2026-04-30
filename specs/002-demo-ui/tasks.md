# Tasks: Demo UI for GDST + FSMA Guardian Integration

**Input**: Design documents from `/specs/002-demo-ui/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/ui-flows.md](contracts/ui-flows.md)

**Tests**: Light. Manual smoke validation per story checkpoint is the primary signal; opt-in Vitest unit tests for helpers land in Phase 8 if the trace-ui repo gains a test runner cleanly. Per spec.md: "manual validation against the running FastAPI."

**Organization**: Grouped by user story from [spec.md](spec.md). US1 + US2 are P1 (MVP); US3, US4, US5 are P2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 (Submit GDST), US2 (Submit FSMA), US3 (Resilience), US4 (Retrieve VC), US5 (About). Omitted on Setup / Foundational / Polish.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: New directories under `ui/trace-ui/src/`, backend config knob for the dev-only demo routes.

- [X] T001 Created `views/`, `pages/`, `lib/` under [ui/trace-ui/src/](ui/trace-ui/src/) (alongside existing `components/`, `hooks/`, `types/`, `utils/`). Empty for now — Phase 2 tasks populate them.
- [X] T002 [P] Added `GUARDIAN_DEMO_ROUTES_ENABLED: str = "0"` to the Guardian section of [api/app/core/config.py](api/app/core/config.py) with a comment pointing at 002-demo-ui research.md §2. Default disabled; verified the env-var override flips it to `"1"` on reload.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Top-nav shell, shared types, API client, hooks, and shared components consumed by every subsequent user-story page.

**⚠️ CRITICAL**: No user-story work begins until this phase is complete.

- [X] T003 [P] Created [ui/trace-ui/src/types/GuardianHealth.ts](ui/trace-ui/src/types/GuardianHealth.ts) — exports `HealthStatus`, `BreakerState`, `GuardianHealth`.
- [X] T004 [P] Created [ui/trace-ui/src/types/VerifiableCredential.ts](ui/trace-ui/src/types/VerifiableCredential.ts) — W3C VC envelope, `credentialSubject` accepts both single-object and array shapes.
- [X] T005 [P] Extended [ui/trace-ui/src/types/ComplianceCheckResponse.ts](ui/trace-ui/src/types/ComplianceCheckResponse.ts) — added `GuardianSubmissionStatus` discriminated union + 6 optional fields (`transactionId`, `receiptStatus`, `eventType`, `eventHash`, `source`, `guardian`). Existing fields untouched (additive — existing Trace Explorer callers continue to work).
- [X] T006 [P] Created [ui/trace-ui/src/lib/samples.ts](ui/trace-ui/src/lib/samples.ts) — Vite eager-glob with 4-up path (`../../../../samples/{gdst,fsma}/*.json`); 500-module Vite production build confirms the glob resolves outside the project root.
- [X] T007 Created [ui/trace-ui/src/lib/api.ts](ui/trace-ui/src/lib/api.ts) — typed wrappers for all 8 endpoints (submit GDST/FSMA, getVc with `?history` toggle, getHealth, breaker simulator inject/clear/status). Internal `request<T>` helper + `ApiError` class encapsulating the `{status, body}` payload from non-2xx responses. `getVc` swallows 404 → returns null (FR-007 not-yet-issued semantics).
- [X] T008 [P] Created [ui/trace-ui/src/hooks/usePollForVc.ts](ui/trace-ui/src/hooks/usePollForVc.ts) — `useEffect` + `setInterval` + `cancelled` flag; treats ApiError(404) as "keep polling"; defaults intervalMs=5000, timeoutMs=300_000; transitions through `polling → ready | manual_review`. Cleanup clears the interval.
- [X] T009 [P] Created [ui/trace-ui/src/hooks/useHealthPoll.ts](ui/trace-ui/src/hooks/useHealthPoll.ts) — same pattern; preserves last-known `health` on transient network errors so the badge doesn't blank out on a single failed poll. `apiOnline` flips back to true on the next successful response.
- [X] T010 [P] Created [ui/trace-ui/src/components/SamplePicker.tsx](ui/trace-ui/src/components/SamplePicker.tsx) — controlled component (parent owns `selected` state); renders `<select>` + JSON preview `<details>`; gracefully handles empty samples Record.
- [X] T011 [P] Created [ui/trace-ui/src/components/ComplianceBadge.tsx](ui/trace-ui/src/components/ComplianceBadge.tsx) — `deriveStyle()` lookup table over `{isCompliant, guardian}` produces 4 outcomes (green compliant / amber non-compliant / grey Guardian-unavailable / red Guardian-error) per [data-model.md §Per-page derived data](specs/002-demo-ui/data-model.md).
- [X] T012 [P] Created [ui/trace-ui/src/components/GuaranteedFieldsCard.tsx](ui/trace-ui/src/components/GuaranteedFieldsCard.tsx) — `FIELDS` lookup table per slug (GDST has 6 entries with `species`, FSMA has 5 without). Renders Issuer + Event Hash always, then iterates the slug's field list skipping undefined. Raw `credentialSubject` in a `<details>` expander.
- [X] T013 Lifted the existing [ui/trace-ui/src/App.tsx](ui/trace-ui/src/App.tsx) body verbatim into [ui/trace-ui/src/views/TraceExplorer.tsx](ui/trace-ui/src/views/TraceExplorer.tsx) — relative imports shifted one level up (`./components/*` → `../components/*`, etc.). Default → named export `TraceExplorer`. Outer wrapper `<div className="min-h-screen bg-gray-50 p-6">` removed since the App shell now provides the page chrome; inner header h1 demoted to h2 to match the new hierarchy.
- [X] T014 Rewrote [ui/trace-ui/src/App.tsx](ui/trace-ui/src/App.tsx) as a thin nav shell — top-nav with `useState<"trace" | "demo">`, global header `<span>` health badge driven by `useHealthPoll()` with 4 colour states (red API offline / green ok / amber breaker_open / grey other). `<TabButton>` typed with `Readonly<>` props (S6759).
- [X] T015 Created [ui/trace-ui/src/views/GuardianDemo.tsx](ui/trace-ui/src/views/GuardianDemo.tsx) — sub-nav grid (12rem aside + main panel) with 5 tabs; each renders a `<Placeholder>` until the corresponding story phase lands. **Build verified**: `npm run build` produces `dist/` with 500 modules transformed (samples successfully inlined); `npm run lint` clean.

**Checkpoint**: `npm run dev` produces a working Trace-tab (existing behaviour unchanged) + a Demo-tab with 5 empty sub-pages. Health badge auto-refreshes in the header. User-story work can now proceed in parallel.

---

## Phase 3: User Story 1 — Submit GDST event → see VC issued (Priority: P1) 🎯 MVP

**Goal**: Pick a GDST CTE sample, click Submit, watch the UI report each stage (Pydantic → HCS receipt → Guardian ack → polling → issued `GDSTComplianceCredential` with Guaranteed fields).

**Independent Test**: With a healthy backend (`GUARDIAN_GDST_POLICY_ID` populated — current state), open the Demo tab → Submit GDST sub-page → pick `fishing.json` → click Submit → observe HCS receipt within ~1s, then within ~60s see the VC card filled with `eventHash`, `gdstEventType: "Fishing"`, `complianceStatus: "compliant"`, `species`. Confirm spec §Acceptance Scenarios US1 #1.

### Implementation for User Story 1

- [X] T016 [US1] Implemented [ui/trace-ui/src/pages/SubmitGdst.tsx](ui/trace-ui/src/pages/SubmitGdst.tsx) — composes `<SamplePicker>`, `<ComplianceBadge>`, `<GuaranteedFieldsCard>`, and the `usePollForVc` hook into the full submit flow. Polling is gated on `result.isCompliant && result.guardian.status === "submitted"` so non-compliant or breaker-skipped events don't spin a poller pointlessly. Five inline helper components (`ErrorPanel`, `ResultPanel`, `GuardianStatusInline`, `PollingPill`, `ManualReviewPanel`) cover the six failure modes from [contracts/ui-flows.md §Page 1](specs/002-demo-ui/contracts/ui-flows.md): network error (delegated to global header badge via `useHealthPoll`), 422 with field-by-field Pydantic detail, 5xx with raw JSON, `not_configured` (links to build script), `not_compliant` (amber badge, no poll), `breaker_open` (links to Health tab, no poll). Inline helpers will move to `components/` if duplicated by T019's FSMA mirror — defer until /simplify catches the dupe.
- [X] T017 [US1] Wired `<SubmitGdst />` into [ui/trace-ui/src/views/GuardianDemo.tsx](ui/trace-ui/src/views/GuardianDemo.tsx) — `tab === "submit_gdst"` renders `<SubmitGdst />`, the other 4 tabs still render `<Placeholder>` until their phase lands. **Build verified**: 520 modules transformed (+19 vs Phase 2), lint clean.
- [ ] T018 [US1] Manual smoke test against live backend (user to perform): start backend (`set -a && source api/.env.dev && set +a && uvicorn app.main:app --port 8000 --app-dir api --reload`), start UI (`cd ui/trace-ui && npm run dev`), open the Guardian Demo tab → Submit GDST sub-page. Validate:
  - Submit each of the 7 GDST samples (`fishing`, `landing`, `transshipment`, `on_vessel`, `processing`, `shipping`, `aggregation`); confirm each yields HCS receipt → polling pill → green "Compliant ✓" badge → `<GuaranteedFieldsCard>` with correct `gdstEventType` discriminator.
  - In DevTools, mutate the picked sample to drop `iuu.fishing_authorization` before clicking Submit (or temporarily edit `samples/gdst/fishing.json` then revert). Confirm 422 panel renders with field path `iuu.fishing_authorization`, no HCS section, no Guardian section.
  - Open `samples/gdst/aggregation.json`, blank both `parent_items` and `child_items`, submit. Confirm HCS receipt appears with `isCompliant: false`, amber "Recorded — non-compliant" badge, and the Guardian inline note reads "rule predicate failed (gdst_min_rules returned False) — no VC will be issued". G1 gating from the recent /speckit-analyze remediation.

  Mark this task `[X]` after the three checks pass.

**Checkpoint**: User Story 1 fully functional. MVP shippable as-is for a "GDST-only" demo.

---

## Phase 4: User Story 2 — Submit FSMA event → see VC issued (Priority: P1)

**Goal**: Same loop as US1 for FSMA 204. Demonstrates the registry pattern handles a second policy generically.

**Independent Test**: With `GUARDIAN_FSMA_POLICY_ID` populated (current state), Submit FSMA sub-page → pick `creating.json` → confirm `FSMA204ComplianceCredential` issued with `fsma204EventType: "creating"`, no `species` field. Confirm spec §Acceptance Scenarios US2 #1.

### Implementation for User Story 2

- [ ] T019 [US2] Implement [ui/trace-ui/src/pages/SubmitFsma.tsx](ui/trace-ui/src/pages/SubmitFsma.tsx) — mirror of SubmitGdst with: `items={fsmaSamples}`, `submitFsmaEvent`, slug `"fsma"`, drop `species` from the Guaranteed-fields card (FSMA doesn't carry it). Reuses every component from Phase 2.
- [ ] T020 [US2] Wire `<SubmitFsma />` into [ui/trace-ui/src/views/GuardianDemo.tsx](ui/trace-ui/src/views/GuardianDemo.tsx) — replace the `submit_fsma` placeholder.
- [ ] T021 [US2] Manual smoke test: submit each of the 6 FSMA samples, confirm 6 VCs with correct `fsma204EventType`. Submit a Shipping event missing `ship_to` → confirm 422 referencing `ship_to`.

**Checkpoint**: P1 MVP complete (US1 + US2). Both compliance loops demonstrable. Ready to deploy as a "compliance-loop showcase" if Phase 5+ slips.

---

## Phase 5: User Story 3 — Resilience: Guardian outage doesn't block HCS (Priority: P2)

**Goal**: Toggle a "Simulate MGS down" switch → submit 3 events → watch breaker open + HCS keeps writing. Demonstrates Constitution §IV.

**Independent Test**: With `GUARDIAN_DEMO_ROUTES_ENABLED=1` on backend startup, Health & Resilience sub-page → toggle simulator on → submit 3 events from the Submit GDST tab → watch `/guardian/health` transition `ok → unavailable → breaker_open`; 4th submission shows grey `breaker_open` badge with no MGS call attempted; clear simulator + wait 60s + 5th submission → breaker probes back to `ok`. Confirm spec §Acceptance Scenarios US3 #1 + #2.

### Implementation for User Story 3

- [ ] T022 [P] [US3] Create [api/app/routes/_demo/__init__.py](api/app/routes/_demo/__init__.py) (empty package marker) and [api/app/routes/_demo/breaker.py](api/app/routes/_demo/breaker.py) exposing `POST /api/v1/_demo/breaker/inject` (body: `{count?: int = 5}`, returns `{active: true}`), `POST /api/v1/_demo/breaker/clear` (returns `{active: false}`), `GET /api/v1/_demo/breaker/status` (returns `{active: bool}`). Uses a process-local module variable `_DEMO_FAILURE_COUNT` for state.
- [ ] T023 [P] [US3] Add `set_demo_failure_mode(active: bool, count: int = 5)` and an internal counter check at the top of `GuardianClient.submit_document` in [api/app/service/guardian_client.py](api/app/service/guardian_client.py) — when active, decrement counter and raise `GuardianUnavailable("demo: simulated MGS outage")` instead of making the HTTP call. The breaker's `record_failure` then runs as normal (research.md §2 — drives the real CircuitBreaker, not a mock). Tag the hook with a `# v1: demo only` comment.
- [ ] T024 [US3] Mount the `_demo` router in [api/app/main.py](api/app/main.py) inside `if settings.GUARDIAN_DEMO_ROUTES_ENABLED == "1":` — keeps it out of production. Depends on T002, T022.
- [ ] T025 [US3] Implement [ui/trace-ui/src/pages/HealthAndResilience.tsx](ui/trace-ui/src/pages/HealthAndResilience.tsx) — uses `useHealthPoll()` for the live status card; calls `injectBreakerFailure` / `clearBreaker` / `getBreakerSimulatorStatus` from `lib/api.ts` for the toggle. Greys the toggle with an explanatory tooltip if the `_demo` route returns 404 (ie, `GUARDIAN_DEMO_ROUTES_ENABLED` not set on backend). Renders the "What this demonstrates" caption per [contracts/ui-flows.md §Page 4](specs/002-demo-ui/contracts/ui-flows.md).
- [ ] T026 [US3] Wire `<HealthAndResilience />` into [ui/trace-ui/src/views/GuardianDemo.tsx](ui/trace-ui/src/views/GuardianDemo.tsx).
- [ ] T027 [US3] Manual smoke test: full simulator scenario — verify breaker opens after exactly 3 submissions (matching the 3-strikes from research.md §3); 4th submission has `guardian.status == "skipped", reason == "breaker_open"`; clear + wait 60s + 5th submission probes back to `ok`. Confirms FR-005 + FR-006 end-to-end visually.

**Checkpoint**: Resilience story demonstrable. Constitution §IV verified live in front of an audience.

---

## Phase 6: User Story 4 — Auditor retrieves VC by event hash (Priority: P2)

**Goal**: Standalone retrieve form — paste any `eventHash`, see the latest VC, optionally see the supersedes chain.

**Independent Test**: After submitting a Fishing event in Phase 3, copy the `eventHash` from the result card → open Retrieve VC sub-page → paste hash + select `gdst` → click Retrieve → see the VC. Toggle "include history" → for a fresh event, see a single-entry timeline. Confirm spec §Acceptance Scenarios US4 #1.

### Implementation for User Story 4

- [ ] T028 [P] [US4] Create [ui/trace-ui/src/components/VcTimeline.tsx](ui/trace-ui/src/components/VcTimeline.tsx) — vertical-timeline renderer for `[oldest, …, latest]` chains. Each entry uses `<GuaranteedFieldsCard>` + `<ComplianceBadge>`. Oldest entries with `complianceStatus: "superseded"` render dimmer; latest with `complianceStatus: "compliant"` is highlighted.
- [ ] T029 [US4] Implement [ui/trace-ui/src/pages/RetrieveVc.tsx](ui/trace-ui/src/pages/RetrieveVc.tsx) — text input for hash, radio for slug (`gdst | fsma`), checkbox for `?history=true`, "Retrieve" button. Uses `getVc` from `lib/api.ts`. On success, renders `<GuaranteedFieldsCard>` (single VC) or `<VcTimeline>` (history). On 404, explanatory empty state. Depends on T028.
- [ ] T030 [US4] Wire `<RetrieveVc />` into [ui/trace-ui/src/views/GuardianDemo.tsx](ui/trace-ui/src/views/GuardianDemo.tsx).
- [ ] T031 [US4] Manual smoke test: retrieve a fresh VC (single entry); then submit a corrective event with `supersedes=<prior eventHash>` (via the API directly, since the UI doesn't have a "submit correction" affordance in v1) and confirm the timeline renders both entries with correct ordering and badges.

**Checkpoint**: Retrieval story demonstrable. FR-007 + FR-014 visible.

---

## Phase 7: User Story 5 — About / onboarding page (Priority: P2)

**Goal**: A first-time visitor leaves with the right mental model: HCS for record + Guardian for VC + breaker for resilience.

**Independent Test**: Open the Demo tab → About sub-page. Confirm the architecture summary fits one screen, every link resolves, and a colleague who's never seen the project can answer "what is being submitted" + "where is the VC stored" in under 30 seconds without opening other tabs.

### Implementation for User Story 5

- [ ] T032 [P] [US5] Implement [ui/trace-ui/src/pages/About.tsx](ui/trace-ui/src/pages/About.tsx) — pure-static markdown content per [contracts/ui-flows.md §Page 5](specs/002-demo-ui/contracts/ui-flows.md): two-paragraph architecture summary + links to docs/guardian-integration/README.md, schemas/{gdst,fsma}/README.md, samples/downstream/carbon-credit-demo.policy.json, specs/002-demo-ui/spec.md. Use Tailwind prose classes; no markdown library needed (small content).
- [ ] T033 [US5] Wire `<About />` into [ui/trace-ui/src/views/GuardianDemo.tsx](ui/trace-ui/src/views/GuardianDemo.tsx).

**Checkpoint**: All five user stories demonstrable. Spec §SC-004 test ready (each FR/§ from 001-guardian-integration is reachable via a button or toggle).

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, optional unit tests, end-to-end run.

- [ ] T034 [P] Update [ui/trace-ui/README.md](ui/trace-ui/README.md) — replace the Vite-template boilerplate with: project intent (Trace Explorer + Guardian Demo), prerequisites (FastAPI backend running, `npm install` done), `npm run dev` instruction, link to [specs/002-demo-ui/quickstart.md](specs/002-demo-ui/quickstart.md) for the 5-min demo script.
- [ ] T035 [P] *(optional)* Add Vitest config + a small test file at [ui/trace-ui/src/lib/__tests__/api.test.ts](ui/trace-ui/src/lib/__tests__/api.test.ts) covering happy + 404 paths of each `lib/api.ts` wrapper using `msw` for HTTP mocks. Add `vitest`, `@testing-library/react`, `msw` to devDependencies. Skip this task if introducing a test runner conflicts with team velocity — manual validation via T018/T021/T027/T031 is the primary signal.
- [ ] T036 Run [specs/002-demo-ui/quickstart.md](specs/002-demo-ui/quickstart.md) end-to-end against a live backend — execute the 5-minute demo script verbatim, fix any drift between the runbook and the actual UI behaviour.
- [ ] T037 Tidy: confirm zero `any` types in new TS files (use `unknown` for VC raw JSON, narrow at boundaries), zero browser console warnings during a clean session, no dead imports flagged by ESLint. Run `npm run lint` and fix any issues introduced by the demo work.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **BLOCKS all user stories.**
- **User Stories (Phases 3–7)**: All depend on Foundational.
  - **US1 (P1) and US2 (P1)** share every Phase-2 component — they proceed in parallel by file (different `pages/Submit*.tsx` files; both modify `views/GuardianDemo.tsx` for nav wiring, so T017 and T020 are sequential).
  - **US3 (P2)** is independent of US1/US2 once Phase 2 is done; backend additions (T022-T024) can run in parallel with frontend (T025).
  - **US4 (P2)** is independent.
  - **US5 (P2)** is independent — pure static content.
- **Polish (Phase 8)**: Depends on all desired user stories being complete.

### Within Each User Story

- Page implementation before nav wiring (the wiring task imports the page).
- Smoke test last.

### Parallel Opportunities

- **Phase 1**: T002 [P] (backend config) parallel with T001 (frontend dirs).
- **Phase 2**: T003-T006 [P] (4 type/lib files), T008+T009 [P] (after T007 lands), T010-T012 [P] (after T006 + T004 land).
- **Phase 3**: Only T016 marked [P]; T017 + T018 are sequential single-file ops.
- **Phase 5**: T022 + T023 [P] (different files — backend route vs guardian_client.py).
- **Phases 6 + 7**: T028, T032 [P] within their phases.
- **Phase 8**: T034, T035 [P].

### Cross-story parallelism (with multiple developers)

After Phase 2 ships, three developers could split:
- Dev A: US1 (T016-T018) + US2 (T019-T021)
- Dev B: US3 frontend (T025-T027) + US3 backend (T022-T024) (or Dev C splits backend off)
- Dev C: US4 (T028-T031) + US5 (T032-T033)

The only cross-story serialisation is `views/GuardianDemo.tsx` — every "Wire \<Page /\> into nav" task touches it. Devs coordinate via merges, not lock-step ordering.

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1 (Setup) — ~10 min.
2. Complete Phase 2 (Foundational) — the bulk of the work; ~half the total tasks. **Blocks everything.**
3. Complete Phase 3 (US1) — deliver the GDST half of the demo. **STOP and VALIDATE** with T018.
4. Complete Phase 4 (US2) — deliver the FSMA half. **STOP and VALIDATE** with T021.
5. **MVP complete** — both P1 stories deployable. The demo can open with US1 + US2 + the existing Trace Explorer; resilience/retrieval/about ship in the next iteration.

### Incremental Delivery

Each phase ends with a checkpoint that's independently demoable. After Phase 4 (MVP), Phase 5/6/7 can ship in any order — they don't depend on each other.

### Parallel Team Strategy

With two developers post-Phase-2:
- Dev A: US1 → US3 (frontend) → US4
- Dev B: US2 → US3 (backend) → US5

Phase 8 polish (~4 tasks) is whoever finishes their stack first.

---

## Notes

- `[P]` = different files, no dependencies on incomplete tasks.
- `[Story]` label maps user-story tasks to US1–US5 for traceability.
- Each user story is independently completable and testable; the only inter-story coupling is `views/GuardianDemo.tsx` (nav wiring) which serialises one line per story.
- Manual smoke tests (T018, T021, T027, T031) are the primary validation signal per spec.md ("manual validation against the running FastAPI"). Vitest/automated testing is opt-in (T035) and not the default.
- Commit after each task or logical group.
- Avoid: importing 001-guardian-integration backend modules into the trace-ui (they're Python, the UI is TypeScript — types are duplicated by hand in `types/`, intentionally).
