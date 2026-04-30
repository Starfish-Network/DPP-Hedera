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

- [ ] T001 Create new directories under [ui/trace-ui/src/](ui/trace-ui/src/): `views/`, `pages/`, `lib/`. (Existing `components/`, `hooks/`, `types/`, `utils/` stay.)
- [ ] T002 [P] Add `GUARDIAN_DEMO_ROUTES_ENABLED: str = "0"` setting to [api/app/core/config.py](api/app/core/config.py) (Pydantic-settings; default disabled). Used in T024 to gate the dev-only `_demo` router mount.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Top-nav shell, shared types, API client, hooks, and shared components consumed by every subsequent user-story page.

**⚠️ CRITICAL**: No user-story work begins until this phase is complete.

- [ ] T003 [P] Create [ui/trace-ui/src/types/GuardianHealth.ts](ui/trace-ui/src/types/GuardianHealth.ts) — `{ status: "ok" | "tos_required" | "breaker_open" | "unavailable"; breaker: "closed" | "open" | "half_open" | "tos_required"; last_failure_at: number | null }`.
- [ ] T004 [P] Create [ui/trace-ui/src/types/VerifiableCredential.ts](ui/trace-ui/src/types/VerifiableCredential.ts) — W3C VC envelope `{ "@context", type, issuer, issuanceDate, credentialSubject, proof }` with `credentialSubject: Record<string, unknown> | Record<string, unknown>[]` to allow both shapes Guardian emits.
- [ ] T005 [P] Extend [ui/trace-ui/src/types/ComplianceCheckResponse.ts](ui/trace-ui/src/types/ComplianceCheckResponse.ts) — add optional `transactionId`, `receiptStatus`, `eventType`, `eventHash`, `source`, plus a `guardian: GuardianSubmissionStatus` discriminated-union field per [contracts/ui-flows.md §lib/api.ts](specs/002-demo-ui/contracts/ui-flows.md). Keep existing fields untouched (additive).
- [ ] T006 [P] Create [ui/trace-ui/src/lib/samples.ts](ui/trace-ui/src/lib/samples.ts) — exports `gdstSamples` and `fsmaSamples` populated via `import.meta.glob('../../../samples/{gdst,fsma}/*.json', { eager: true })`. Filename stem (e.g., `"fishing"`) is the key.
- [ ] T007 Create [ui/trace-ui/src/lib/api.ts](ui/trace-ui/src/lib/api.ts) — typed fetch wrappers for `submitGdstEvent`, `submitFsmaEvent`, `getVc(slug, hash, {history})`, `getHealth`, `injectBreakerFailure`, `clearBreaker`, `getBreakerSimulatorStatus`. All paths relative (Vite proxy forwards). Depends on T003-T005.
- [ ] T008 [P] Create [ui/trace-ui/src/hooks/usePollForVc.ts](ui/trace-ui/src/hooks/usePollForVc.ts) — `useEffect` + `setInterval` + `AbortController` cleanup; defaults `intervalMs=5000`, `timeoutMs=300_000`; returns `{ status: "polling" | "ready" | "manual_review", vc?, elapsedMs }`. Depends on T007.
- [ ] T009 [P] Create [ui/trace-ui/src/hooks/useHealthPoll.ts](ui/trace-ui/src/hooks/useHealthPoll.ts) — same pattern; returns `{ health, apiOnline }` with `apiOnline` flipping false on network error. Depends on T007.
- [ ] T010 [P] Create [ui/trace-ui/src/components/SamplePicker.tsx](ui/trace-ui/src/components/SamplePicker.tsx) — generic `<select>` over a `Record<string, T>` with sample-JSON `<details>` preview below. Depends on T006.
- [ ] T011 [P] Create [ui/trace-ui/src/components/ComplianceBadge.tsx](ui/trace-ui/src/components/ComplianceBadge.tsx) — colour-coded label per [data-model.md §Per-page derived data](specs/002-demo-ui/data-model.md): green compliant, amber non-compliant, grey Guardian-unavailable, red recording-failed.
- [ ] T012 [P] Create [ui/trace-ui/src/components/GuaranteedFieldsCard.tsx](ui/trace-ui/src/components/GuaranteedFieldsCard.tsx) — renders the seven Guaranteed fields per [schemas/gdst/README.md](schemas/gdst/README.md) and [schemas/fsma/README.md](schemas/fsma/README.md) with a raw-JSON `<details>` expander for the rest of `credentialSubject`. Depends on T004.
- [ ] T013 Lift the existing [ui/trace-ui/src/App.tsx](ui/trace-ui/src/App.tsx) body into [ui/trace-ui/src/views/TraceExplorer.tsx](ui/trace-ui/src/views/TraceExplorer.tsx) as a default-exported component. Pure rename/move — no behaviour change. Existing imports follow.
- [ ] T014 Rewrite [ui/trace-ui/src/App.tsx](ui/trace-ui/src/App.tsx) as a thin shell: top-nav with `useState<"trace" | "demo">("trace")`, global header showing `<HealthBadge />` driven by `useHealthPoll()`, renders `<TraceExplorer />` or `<GuardianDemo />`. Depends on T009, T013.
- [ ] T015 Create [ui/trace-ui/src/views/GuardianDemo.tsx](ui/trace-ui/src/views/GuardianDemo.tsx) — sub-nav with 5 placeholders (Submit GDST / Submit FSMA / Health & Resilience / Retrieve VC / About) using `useState<"submit_gdst" | "submit_fsma" | "health" | "retrieve" | "about">`. Renders an empty `<section>` per active tab; pages land in subsequent stories. Depends on T014.

**Checkpoint**: `npm run dev` produces a working Trace-tab (existing behaviour unchanged) + a Demo-tab with 5 empty sub-pages. Health badge auto-refreshes in the header. User-story work can now proceed in parallel.

---

## Phase 3: User Story 1 — Submit GDST event → see VC issued (Priority: P1) 🎯 MVP

**Goal**: Pick a GDST CTE sample, click Submit, watch the UI report each stage (Pydantic → HCS receipt → Guardian ack → polling → issued `GDSTComplianceCredential` with Guaranteed fields).

**Independent Test**: With a healthy backend (`GUARDIAN_GDST_POLICY_ID` populated — current state), open the Demo tab → Submit GDST sub-page → pick `fishing.json` → click Submit → observe HCS receipt within ~1s, then within ~60s see the VC card filled with `eventHash`, `gdstEventType: "Fishing"`, `complianceStatus: "compliant"`, `species`. Confirm spec §Acceptance Scenarios US1 #1.

### Implementation for User Story 1

- [ ] T016 [US1] Implement [ui/trace-ui/src/pages/SubmitGdst.tsx](ui/trace-ui/src/pages/SubmitGdst.tsx) — uses `<SamplePicker items={gdstSamples} />`, `submitGdstEvent` from `lib/api.ts`, `<ComplianceBadge>` for the result, `usePollForVc("gdst", eventHash)` for the VC poll, `<GuaranteedFieldsCard>` for the rendered VC. Handles all six failure modes from [contracts/ui-flows.md §Page 1](specs/002-demo-ui/contracts/ui-flows.md): API offline, 422, 5xx, `not_configured`, `not_compliant`, `breaker_open`.
- [ ] T017 [US1] Wire `<SubmitGdst />` into [ui/trace-ui/src/views/GuardianDemo.tsx](ui/trace-ui/src/views/GuardianDemo.tsx) — replace the placeholder section for the `submit_gdst` tab.
- [ ] T018 [US1] Manual smoke test against live backend: submit each of the 7 GDST samples, confirm 7 VCs appear with correct `gdstEventType` discriminator. Submit a malformed event (mutate fishing.json client-side via DevTools) → confirm 422 path. Submit an Aggregation with empty `parent_items`+`child_items` → confirm `is_compliant: false` + amber `not_compliant` badge (G1 gating).

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
