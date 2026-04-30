# Research: Demo UI

**Feature**: `002-demo-ui` | **Date**: 2026-04-29

Three open decisions resolved before [tasks.md](tasks.md) is generated.

## 1. UI framework

**Decision (revised 2026-04-29 after surveying the repo)**: **Extend the existing [ui/trace-ui/](../../ui/trace-ui/) React + Vite + TypeScript + Tailwind app.** No new framework, no new build pipeline, no new top-level directory. The Guardian demo lands as additional pages/components inside `ui/trace-ui/src/`.

**Rationale**:
- The repo already ships a working frontend: React 19 + Vite 7 + TypeScript + Tailwind 4 + ReactFlow + Recharts. Original surface is a Trace Explorer (graph view of HCS-recorded supply chains).
- A Vite proxy at [vite.config.ts](../../ui/trace-ui/vite.config.ts) already forwards `/api/v1` to `http://localhost:8000` — relative-URL fetches in App.tsx already work against the existing FastAPI. Zero infra to add.
- TypeScript types for `GDSTEvent`, `StarfishEvent`, `ComplianceCheckResponse`, `TraceResponse` already live under `ui/trace-ui/src/types/` — the demo extends these rather than redefines.
- A Trace Explorer + a Guardian Demo under one shell *tells a richer story* than either alone: the audience sees event submission → VC issuance → and how the resulting events later appear on the trace graph.
- Zero new dependencies for the basic flow (fetch, useState, Tailwind). If a chart is needed, recharts is already installed.

**Alternatives considered (and rejected after the survey)**:

- *Streamlit greenfield* — what the prior plan revision recommended. Rejected: the user already has a React app set up. Adding Streamlit means two frontend stacks for stakeholders to maintain and a worse demo (jumping between two UIs vs one shell).
- *Reflex / Gradio / HTMX* — same blocker.
- *Add a separate React app at `demo_ui/`* — duplicates Vite config, Tailwind config, types, fetch helpers, the proxy. No upside.

**Consequences**:
- New work lands in `ui/trace-ui/src/` — a top-level nav switcher (Trace Explorer | Guardian Demo) wraps the existing App content + the new demo pages. The existing graph experience is unchanged when the user picks the Trace tab.
- View-switching uses local `useState` (or a tiny tab component) — no need for `react-router-dom` for a 2-tab shell. Add it later if a third top-level page lands.
- Existing `ComplianceCheckResponse` type extends to add the `guardian: {status, reason|cached|submittedAt}` envelope from T048's route response — additive, no breaking change to existing callers.

## 2. MGS-outage simulator

**Decision**: A pair of **dev-only feature-flagged FastAPI routes** at `POST /api/v1/_demo/breaker/inject` and `POST /api/v1/_demo/breaker/clear`. The inject route flips a process-local flag in the `GuardianClient` (or wraps it via dependency-override) so the next 3+ `submit_document` calls raise `GuardianUnavailable` regardless of MGS state. The clear route resets the flag.

**Rationale**:
- Drives the real `CircuitBreaker.record_failure(...)` state machine from Phase 5 / T009 — the demo exercises the same code path production would. No mock breaker, no parallel state.
- Single-process: no need to coordinate the UI with a separate test container. Both backend and UI run on localhost.
- Scoped via env flag (`GUARDIAN_DEMO_ROUTES_ENABLED=1`). The `_demo` router is mounted only when the flag is on, so production deployments can't accidentally expose it. The flag is not in `api/.env.dev` by default.
- Reversible: clearing the flag drops back to live MGS behavior; the breaker's 60s window decays naturally if the demoer wants to show the probe-success closes path.

**Alternatives considered**:

- *Wrap GuardianClient in a debug interceptor at import time*. Rejected: requires Python test-shim plumbing to swap clients for the duration of the demo and back, easy to forget.
- *Disconnect the network for real* (e.g. block guardianservice.app via local firewall). Rejected: viewer-hostile; needs sudo; doesn't reset cleanly.
- *Add a `_demo_force_failure` field to GuardianClient itself*. Rejected: pollutes a production class with a debug-only knob. Better to keep the hook out-of-band in the `_demo` route module.

**Consequences**:
- One small new module under `api/app/routes/_demo/breaker.py` — gated behind `settings.GUARDIAN_DEMO_ROUTES_ENABLED`.
- `GuardianClient` gains a single internal hook (`set_demo_failure_mode(active: bool)`) with a `# v1: demo only` comment. This is acceptable scope creep on the production class because the entire mechanism is feature-flagged at route-mount time.
- Documented in [contracts/ui-flows.md](contracts/ui-flows.md) as a v1-only surface with v2 plans to remove (or replace with a proper test-mode interceptor).

## 3. VC-polling cadence and React integration

**Decision**: Poll `GET /api/v1/guardian/{slug}/vc/{event_hash}` **every 5 seconds with a 5-minute ceiling**, implemented as a custom React hook `usePollForVc(slug, eventHash, { intervalMs: 5000, timeoutMs: 300_000 })` returning `{ vc, status: "polling" | "ready" | "manual_review", elapsedMs }`.

**Rationale**:
- The 30s-pending / 5-min-manual-review thresholds in spec §SC-007 are the natural ceilings; aligning the UI poll keeps the displayed status consistent with the Python `GuardianClient.get_vc_retrieval_status()` semantics already implemented.
- `useEffect` + `setInterval` is the standard React pattern. AbortController on unmount prevents leaks if the user switches tabs or navigates away mid-poll.
- 5 seconds is fast enough to feel live without hammering MGS (Hedera testnet's mirror node has rate limits; 60 polls in 5 minutes is well below).

**Alternatives considered**:

- *Server-Sent Events (SSE) push from FastAPI*. Rejected: requires a new endpoint and a server-side notification when MGS issues a VC (we don't have one). Polling is the right shape.
- *Faster poll cadence (1s or 2s)*. Rejected: hammers the testnet mirror; 5s feels live enough for a human watching a screen.
- *Tanstack Query / SWR*. Considered. Either would handle the polling lifecycle cleanly. Skipped to avoid adding a dependency for one hook — the custom hook is ~30 lines and the codebase doesn't use a fetcher library yet. If a third polling surface lands, revisit.

**Consequences**:
- New file `ui/trace-ui/src/hooks/usePollForVc.ts` exports the hook plus a small `pollForVc` core function (testable without React).
- Submit pages render the hook output into a status pill above the VC card: "Polling for VC… (Xs)" → "VC issued" → fields panel.
- If the timeout hits, the pill flips to a `manual_review` badge linking to the Health & Resilience tab.
