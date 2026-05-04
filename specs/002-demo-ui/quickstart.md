# Quickstart: Demo UI

**Feature**: `002-demo-ui` | **Date**: 2026-04-29

Two terminals, two commands, one browser tab. Extends the existing `ui/trace-ui/` — the Trace Explorer view stays available; the Guardian Demo lands as a new tab.

## Prerequisites

- Feature 001-guardian-integration backend functional (`api/.env.dev` has `GUARDIAN_GDST_POLICY_ID` and `GUARDIAN_FSMA_POLICY_ID` populated — current state).
- Python 3.11 venv with `api/requirements.txt` installed.
- Node + npm with `ui/trace-ui/node_modules` installed (`cd ui/trace-ui && npm install` if first time).

## Launch

**Terminal 1 — backend**:

```sh
cd /home/joao/DPP-Hedera
set -a && source api/.env.dev && set +a
GUARDIAN_DEMO_ROUTES_ENABLED=1 \
  uvicorn app.main:app --port 8000 --app-dir api --reload
```

The `GUARDIAN_DEMO_ROUTES_ENABLED=1` flag mounts the `/api/v1/_demo/breaker/*` routes used by the Health & Resilience tab's outage simulator. Omit it for a "no demo affordances" run; the Submit/Retrieve tabs still work (the simulator toggle just shows as disabled).

**Terminal 2 — frontend**:

```sh
cd /home/joao/DPP-Hedera/ui/trace-ui
npm run dev
```

Vite prints a `http://localhost:5173` URL. The `/api/v1/*` requests are proxied to `http://localhost:8000` per [vite.config.ts](../../ui/trace-ui/vite.config.ts) — no CORS dance.

Top nav has two tabs: **Trace Explorer** (the original graph view, unchanged) and **Guardian Demo**. The demo tab has a sub-nav for **Policy VCs** (default — see [spec.md §User Story 5](spec.md)) / Submit GDST / Submit FSMA. The Retrieve VC tab is implementation-complete but hidden while MGS event-VC issuance is broken (see [spec.md §FR-007 status](spec.md)). The header always shows a live Guardian-health badge (red API offline / green ok / amber breaker_open / grey other) — that's the resilience signal in MVP. The dedicated Health & Resilience tab is deferred to v1.1 (see [spec.md §User Story 3](spec.md)).

## Demo script (~3-4 minutes)

1. **Policy VCs** (~60s, default landing tab): both cards render (GDST blue, FSMA 204 green) with policy name, tag, version, issuer DID (the SR), and an IPFS link. Click each IPFS CID → IPFS gateway resolves the policy artefact independently. Establishes that both compliance frameworks are real, signed by the SR, and on-chain. See [spec.md §User Story 5](spec.md).
2. **Submit GDST** (~90s): pick `fishing.json` from the dropdown, click Submit, watch the HCS receipt + Guardian forwarding status appear. *(Note: VC polling is currently disabled while MGS event-VC issuance is being investigated — see FR-003 status. The HCS half of the loop is fully functional.)*
3. **Submit FSMA** (~60s): pick `creating.json`, show the same submit-and-receipt path. Demonstrates two policies via one registry pattern.
4. (Bonus) **Switch to Trace Explorer**: enter a product EPC/lot used in the events you just submitted and show the upstream/downstream graph rendering on top of the HCS-recorded events. Demonstrates that the Policy VCs and the trace graph share one source of truth (HCS).

If a viewer asks about MGS outages, point to the header badge and explain Constitution §IV: HCS keeps writing even when Guardian is unavailable; the breaker auto-opens after 3 failures, probes back after 60s. The on-demand simulator that exercises this on stage ships with v1.1.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Vite dev server says "API offline" or 502 on `/api/v1` calls | FastAPI not running | Check Terminal 1; default expected at `http://localhost:8000` |
| Guardian section greyed out with "policy not configured" | `GUARDIAN_*_POLICY_ID` empty | Re-run `scripts/build_*_policy.py` (or paste a known-good ID into `api/.env.dev`) |
| VC poll spins for 5 minutes | MGS slow or breaker open | Header health badge shows breaker state; query `/api/v1/guardian/health` directly. If `breaker_open`, wait 60s for the half-open probe |
| Outage simulator toggle has no effect or returns 404 | `GUARDIAN_DEMO_ROUTES_ENABLED` not set on the backend | Restart Terminal 1 with the flag |
| `vite: command not found` | `node_modules` not installed | `cd ui/trace-ui && npm install` |
| HMR broken after editing a TS file | Stale Vite cache (rare) | Stop Terminal 2, `rm -rf node_modules/.vite`, restart |
