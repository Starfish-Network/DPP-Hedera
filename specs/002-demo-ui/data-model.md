# Data Model: Demo UI

**Feature**: `002-demo-ui` | **Date**: 2026-04-29

The demo UI introduces **no new entities**. It surfaces existing entities from feature 001-guardian-integration. This file documents which existing entities each page reads, what fields are displayed, and which session-scoped state lives in `streamlit.session_state`.

## Entities consumed (read-only)

All shapes are defined in 001-guardian-integration; this file links rather than restates.

| Entity | Source | Used on page |
|--------|--------|--------------|
| GDST CTE | [api/app/models/gdst/](../../api/app/models/gdst/) + samples in [samples/gdst/](../../samples/gdst/) | Submit GDST |
| FSMA Event | [api/app/models/starfish_events.py](../../api/app/models/starfish_events.py) + samples in [samples/fsma/](../../samples/fsma/) | Submit FSMA |
| HCS Receipt | `{transactionId, receiptStatus}` from existing `/events/*` route response | Submit GDST, Submit FSMA |
| Guardian Submission Status | `{status: submitted|skipped|error, reason?, cached?, submittedAt?}` from existing route response (T048 + G1 fix shape) | Submit GDST, Submit FSMA |
| Verifiable Credential | `GDSTComplianceCredential` / `FSMA204ComplianceCredential` per [contracts/vc-output.schema.json](../001-guardian-integration/contracts/vc-output.schema.json) | Submit pages, Retrieve VC |
| Health | `{status, breaker, last_failure_at}` from `GET /api/v1/guardian/health` | Health & Resilience |

## Component state (React `useState` / `useReducer`)

The UI is intentionally stateless across page refreshes. State lives in component-local React hooks; no global store, no Redux, no Zustand. Three relevant slots:

| Slot | Type | Owner | Purpose |
|------|------|-------|---------|
| `submittedEvents` | `Array<{eventHash, slug, transactionId, vcStatus}>` | `views/GuardianDemo.tsx` (lifted state) | Append-only log of submissions in the current tab — surfaces a "recent submits" sidebar. Wiped on page reload. |
| `simulatorActive` | `boolean` | `pages/HealthAndResilience.tsx` | Mirrors the demo-only `_demo/breaker` flag toggle. Synced from `GET /_demo/breaker/status` on mount; updated by toggle clicks. |
| `health` | `GuardianHealth \| null` | `hooks/useHealthPoll.ts` | Most recent `/guardian/health` payload, refreshed every 5s. Drives the global status banner + the Health & Resilience tab card without an extra request on widget interactions. |

## New TypeScript types (added to `ui/trace-ui/src/types/`)

| Type | File | Shape |
|------|------|-------|
| `GuardianHealth` | `types/GuardianHealth.ts` | `{ status: "ok" \| "tos_required" \| "breaker_open" \| "unavailable"; breaker: "closed" \| "open" \| "half_open" \| "tos_required"; last_failure_at: number \| null }` |
| `VerifiableCredential` | `types/VerifiableCredential.ts` | `{ "@context": string[]; type: string[]; issuer: string; issuanceDate: string; credentialSubject: Record<string, unknown> \| Record<string, unknown>[]; proof: { type: string; [k: string]: unknown } }` |
| `GuardianSubmissionStatus` | `types/ComplianceCheckResponse.ts` (extending) | Discriminated union — see [contracts/ui-flows.md §lib/api.ts](contracts/ui-flows.md). |

## Modified existing type

`ComplianceCheckResponse` (file unchanged location) gains:

```ts
export interface ComplianceCheckResponse {
    contractId?: string;
    isCompliant: boolean;
    status?: string;
    txStatus?: string;
    eventHashHex: string;
    // NEW (additive — existing callers ignore unknown fields):
    transactionId?: string;
    receiptStatus?: string;
    eventType?: string;
    eventHash?: string;
    source?: string;
    guardian?: GuardianSubmissionStatus;
}
```

The original `eventHashHex` field stays for backward-compatibility with existing Trace Explorer callers (`/api/v1/{gdst|epcis}/compliance/status/{event_hash}`); the demo's submit pages prefer the new `eventHash` field returned by `POST /api/v1/{gdst/events|epcis/compliance/check}`.

## Per-page derived data

Three display transforms are computed on the fly and not stored:

1. **Guaranteed-fields panel** — slices the VC's `credentialSubject` to display only the fields documented in [schemas/gdst/README.md](../../schemas/gdst/README.md) and [schemas/fsma/README.md](../../schemas/fsma/README.md) Guaranteed Fields Contract. Per-CTE KDEs go into a separate "Full payload" expander.

2. **Compliance-status badge** — colour-coded label derived from the route response's `isCompliant` + `guardian.status`:
   - HCS+VC issued: green "Compliant ✓"
   - HCS only, Guardian skipped (not_compliant): amber "Recorded — non-compliant"
   - HCS only, Guardian skipped (breaker_open / not_configured): grey "Recorded — Guardian unavailable"
   - HCS failed: red "Recording failed"

3. **Trust-chain summary** — for a retrieved VC, derive `{issuer_did, vc_type, eventHash, complianceStatus, supersedes_chain_length}` for the at-a-glance summary above the raw JSON.

No persistent storage. No new database. No new schema files.
