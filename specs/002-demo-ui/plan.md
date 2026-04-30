# Implementation Plan: Demo UI for GDST + FSMA Guardian Integration

**Branch**: `002-demo-ui` (working on `dev` per repo convention) | **Date**: 2026-04-29 | **Spec**: [spec.md](spec.md)
**Input**: [spec.md](spec.md) + the shipped 001-guardian-integration FastAPI surface + the existing [ui/trace-ui/](../../ui/trace-ui/) React app.

## Summary

**Extend** the existing `ui/trace-ui/` React app with a Guardian Demo shell — a top-nav switcher between the existing Trace Explorer and a new five-section demo (Submit GDST / Submit FSMA / Retrieve VC / Health & Resilience / About). The demo calls the live `/api/v1/*` endpoints through Vite's existing dev proxy. No new framework, no new build pipeline, no new top-level directory; the demo lands as added components, hooks, and types under `ui/trace-ui/src/`.

## Technical Context

**Language/Version**: TypeScript 5.9 (matches `ui/trace-ui/tsconfig.json`).
**Primary Dependencies**: existing — React 19, Vite 7, Tailwind 4, ReactFlow, Recharts. Zero new deps for the basic demo flow.
**Storage**: None. React `useState` / `useReducer` for in-tab event history. No persistence.
**Testing**: Light. Helpers (`pollForVc`, the API client wrappers, sample-loaders) get unit tests via Vitest if it lands cleanly, otherwise pure manual validation against the running FastAPI backend. The existing `ui/trace-ui/` doesn't have a test runner today; not adding one is acceptable for a demo surface.
**Target Platform**: Localhost browser, single user. Not a deployable production app.
**Project Type**: Frontend extension. The existing `ui/trace-ui/` already targets a localhost FastAPI; this work fits inside that envelope.
**Performance Goals**: Submit→VC-render under 90s on healthy testnet (SC-001). UI itself sub-50ms per interaction (Vite/React HMR is fast).
**Constraints**: Constitution §IV — UI MUST NOT introduce a Guardian dependency on the HCS path. Implementation: UI calls the existing FastAPI route which already enforces this. No parallel HCS path, no client-side breaker logic.
**Scale/Scope**: Single concurrent user during a demo. No load expectations.

## Constitution Check

The constitution targets the Guardian backend; mapping each principle to the frontend extension:

| Principle | Applied to demo UI | Status |
|-----------|---------------------|--------|
| I. Policies are the product | UI doesn't issue or store policies; About tab links viewers to the published `.policy` exports + `schemas/{gdst,fsma}/README.md`. | Pass (out of scope; respected) |
| II. Composable by design | UI consumes Guaranteed VC fields only — same surface a downstream Guardian project would use. The UI is itself a "downstream consumer reference." | Pass |
| III. Dual compliance logic | UI submits raw events; rule enforcement remains entirely at the FastAPI layer. UI does not pre-validate. | Pass |
| IV. Core flows never block | UI's submit flow goes through the existing route, which already gates Guardian under `is_compliant` + breaker. UI surfaces the route's response shape — does not introduce a parallel path. | Pass |
| V. Test-First | Light interpretation: helper-function unit tests where Vitest is trivial to add. UI is not a service-to-service contract boundary. | Pass (light) |
| VI. Authoritative contracts | UI consumes existing JSON shapes (which ARE the contract). One small additive type — `GuardianSubmissionStatus` — formalises the route's `guardian:` envelope already returned by T048's code. | Pass |

No violations. Complexity Tracking remains empty.

## Phase 0 — Research

Recorded in [research.md](research.md). Resolves:

1. **UI framework choice** — extend existing trace-ui (revised from Streamlit greenfield after surveying the repo).
2. **MGS-outage simulation mechanism** — dev-only feature-flagged FastAPI route at `POST /api/v1/_demo/breaker/{inject,clear}`.
3. **VC-polling cadence and React integration** — 5s poll / 5-min ceiling via a custom `usePollForVc` hook with AbortController cleanup.

## Phase 1 — Design

Produced in this plan, [data-model.md](data-model.md), [contracts/ui-flows.md](contracts/ui-flows.md), and [quickstart.md](quickstart.md).

### Page structure (additions to `ui/trace-ui/src/`)

```text
ui/trace-ui/src/
├── App.tsx                                  # MODIFIED — top-nav switcher (Trace | Guardian Demo)
├── views/                                   # NEW — top-level views the App renders
│   ├── TraceExplorer.tsx                    # NEW — wraps existing App body for the Trace tab
│   └── GuardianDemo.tsx                     # NEW — sub-nav for the 5 demo sections
├── pages/                                   # NEW — each section of the Guardian Demo
│   ├── SubmitGdst.tsx
│   ├── SubmitFsma.tsx
│   ├── RetrieveVc.tsx
│   ├── HealthAndResilience.tsx
│   └── About.tsx
├── components/
│   ├── EventFiles.tsx                       # existing (unchanged)
│   ├── GraphLegend.tsx                      # existing (unchanged)
│   ├── NodeModal.tsx                        # existing (unchanged)
│   ├── SamplePicker.tsx                     # NEW — dropdown over samples/{gdst,fsma}/*.json
│   ├── GuaranteedFieldsCard.tsx             # NEW — renders the VC's Guaranteed-fields contract
│   ├── ComplianceBadge.tsx                  # NEW — colour-coded outcome label
│   └── VcTimeline.tsx                       # NEW — supersedes-chain renderer
├── hooks/
│   ├── useEventFiles.ts                     # existing (unchanged)
│   ├── usePollForVc.ts                      # NEW — 5s poll / 5-min ceiling
│   └── useHealthPoll.ts                     # NEW — 5s auto-refresh of /guardian/health
├── lib/
│   ├── api.ts                               # NEW — typed wrapper around /api/v1/* fetches
│   └── samples.ts                           # NEW — vite glob-import of sample JSONs
└── types/
    ├── GDSTEvent.ts                         # existing
    ├── StarfishEvents.ts                    # existing
    ├── ComplianceCheckResponse.ts           # MODIFIED — add `guardian` envelope, `isCompliant`
    ├── TraceResponse.ts                     # existing (unchanged)
    ├── EdgeNode.ts                          # existing (unchanged)
    ├── GuardianHealth.ts                    # NEW — { status, breaker, last_failure_at }
    └── VerifiableCredential.ts              # NEW — { issuer, type, credentialSubject, proof }
```

The existing Trace Explorer body moves wholesale into `views/TraceExplorer.tsx`; `App.tsx` becomes a thin shell that renders one view at a time based on `useState<"trace" | "demo">`.

### Data flow per submit

```text
SamplePicker → load JSON via vite glob (lib/samples.ts)
        ↓
api.ts: POST /api/v1/gdst/events  (or /api/v1/epcis/compliance/check)
        ↓
Display HCS receipt + isCompliant + guardian: {status, reason}
        ↓
usePollForVc(slug, eventHash) → GET /api/v1/guardian/{slug}/vc/{eventHash} every 5s, ceiling 5min
        ↓
GuaranteedFieldsCard renders the VC; raw JSON in a <details> expander
```

### Sample loading

Vite's `import.meta.glob('../../../samples/gdst/*.json', { eager: true })` lets the bundle pull canonical event samples directly from the repo at build time. Read-only — the demo doesn't write samples.

### MGS-outage simulator

Per research.md §2: a small new module at `api/app/routes/_demo/breaker.py` (feature-flagged via `GUARDIAN_DEMO_ROUTES_ENABLED=1`) exposes `POST /api/v1/_demo/breaker/{inject,clear}` and `GET /api/v1/_demo/breaker/status`. The inject endpoint sets a process-local flag that wraps `GuardianClient.submit_document` to raise `GuardianUnavailable` on the next N calls. Drives the real `CircuitBreaker` (T009).

### Contract deliverables

- [contracts/ui-flows.md](contracts/ui-flows.md) — per-page request/response narrative + the TypeScript helper-module signatures (`api.ts`, `samples.ts`, `usePollForVc.ts`, `useHealthPoll.ts`). Functions as the manual test plan.
- One small addition to backend contracts: `_demo/breaker/*` admin routes documented in prose (not added to `mgs-boundary.openapi.yaml` since they're not at the MGS boundary).

### Runbook deliverable

[quickstart.md](quickstart.md) — three-terminal launch (existing trace-ui's `npm run dev` is unchanged; the Guardian Demo just appears as a new tab once code lands).

## Project Structure

### Documentation (this feature)

```text
specs/002-demo-ui/
├── plan.md                 # This file
├── spec.md                 # Five user stories
├── research.md             # Tech choice + simulator design + polling cadence
├── data-model.md           # Light — references existing entities, new TS types
├── quickstart.md           # Two-terminal launch runbook
└── contracts/
    └── ui-flows.md         # Per-page request/response + helper TS signatures
```

### Source code

```text
api/                                     # MODIFIED — small additions only
├── app/
│   └── routes/
│       └── _demo/                       # NEW — feature-flagged dev-only routes
│           ├── __init__.py
│           └── breaker.py               # POST /_demo/breaker/{inject,clear}, GET /status
├── requirements.txt                     # unchanged

ui/trace-ui/                             # MODIFIED — new views/pages/hooks under src/
├── package.json                         # unchanged (zero new deps for v1)
├── src/                                 # see "Page structure" above
└── ...
```

**Structure decision**: Extend `ui/trace-ui/` rather than introduce a new top-level dir. The existing project already has Vite + Tailwind + the API proxy + types — duplicating any of those for a separate demo would be churn. The demo and the trace explorer benefit from sharing a shell: an audience sees both halves of the product in one place.

## Phase 2 — Tasks (deferred to /speckit-tasks)

Expected shape (preview):

- T001-T003: Setup — top-nav shell in App.tsx, lift existing body to `views/TraceExplorer.tsx`, scaffold `views/GuardianDemo.tsx`.
- T004-T005: Backend dev-only `_demo/breaker` route + the GuardianClient demo-failure hook.
- T006: `lib/api.ts` typed fetch wrapper.
- T007: `lib/samples.ts` vite glob loader.
- T008: `usePollForVc` + `useHealthPoll` hooks.
- T009-T013 [P]: Five demo pages (SubmitGdst, SubmitFsma, RetrieveVc, HealthAndResilience, About).
- T014: Shared UI components (`SamplePicker`, `GuaranteedFieldsCard`, `ComplianceBadge`, `VcTimeline`).
- T015: New TypeScript types (`GuardianHealth`, `VerifiableCredential`); extend `ComplianceCheckResponse`.
- T016: README polish in `ui/trace-ui/README.md`.
- T017: Smoke run against live backend.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified.

None.
