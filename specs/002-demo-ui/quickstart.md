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

Top nav has two tabs: **Trace Explorer** (the original graph view, unchanged) and **Guardian Demo**. The demo tab has a sub-nav for Submit GDST / Submit FSMA / Retrieve VC / Health & Resilience / About.

## Five-minute demo script

1. **Open About** (~30s): explain the architecture — HCS for authoritative record + Guardian for VC issuance + breaker for resilience.
2. **Submit GDST** (~90s): pick `fishing.json` from the dropdown, click Submit, watch the HCS receipt appear, then the polling indicator, then the issued VC's Guaranteed fields. Copy the `eventHash`.
3. **Retrieve VC** (~30s): paste the `eventHash` into the Retrieve form, show the VC. Toggle "include history" — for a fresh submit it's a one-entry chain.
4. **Submit FSMA** (~60s): pick `creating.json`, show the same loop produces an `FSMA204ComplianceCredential` with `fsma204EventType: "creating"`. Demonstrates two policies via one registry pattern.
5. **Health & Resilience** (~90s): toggle "Simulate MGS down", submit 3 events, watch `/guardian/health` go `ok → unavailable → breaker_open`. Submit a 4th — see HCS still records, Guardian shows "skipped: breaker_open". Clear the simulator, wait 60s, submit a 5th — breaker probes, returns to `ok`.
6. (Bonus) **Switch to Trace Explorer**: enter a product EPC/lot used in the events you just submitted and show the upstream/downstream graph rendering on top of the HCS-recorded events. Demonstrates that the Guardian VCs and the trace graph share one source of truth (HCS).

Total: ~5–6 minutes. Each step references a Constitution principle the listener can verify on screen.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Vite dev server says "API offline" or 502 on `/api/v1` calls | FastAPI not running | Check Terminal 1; default expected at `http://localhost:8000` |
| Guardian section greyed out with "policy not configured" | `GUARDIAN_*_POLICY_ID` empty | Re-run `scripts/build_*_policy.py` (or paste a known-good ID into `api/.env.dev`) |
| VC poll spins for 5 minutes | MGS slow or breaker open | Health & Resilience tab shows `/guardian/health` state; if `breaker_open`, wait 60s |
| Outage simulator toggle has no effect or returns 404 | `GUARDIAN_DEMO_ROUTES_ENABLED` not set on the backend | Restart Terminal 1 with the flag |
| `vite: command not found` | `node_modules` not installed | `cd ui/trace-ui && npm install` |
| HMR broken after editing a TS file | Stale Vite cache (rare) | Stop Terminal 2, `rm -rf node_modules/.vite`, restart |
