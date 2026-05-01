# Contract: UI Flows

**Feature**: `002-demo-ui` | **Module**: `ui/trace-ui/src/pages/*`

The Guardian Demo extends the existing trace-ui app with a top-nav switcher and five demo pages. There is no new wire-level contract — the existing 001-guardian-integration contracts remain authoritative. This file is a **per-page narrative contract** describing what each page does in terms of HTTP calls + display transforms. Use as the manual integration-test plan when touching this code.

The existing **Trace Explorer** view (`views/TraceExplorer.tsx`, lifted from the current `App.tsx`) is unchanged — it stays available at the "Trace" tab.

---

## Page 1: Submit GDST (`pages/SubmitGdst.tsx`)

**Actions**:

1. On mount: `lib/samples.ts` glob-imports `samples/gdst/*.json` (excluding README.md). Render a `<select>` of CTE names + a `<details>` showing the picked sample's JSON.
2. On "Submit" click:
   - `api.ts::submitGdstEvent(sample)` → `POST /api/v1/gdst/events`.
   - Render response: `{transactionId, receiptStatus, eventType, eventHash, isCompliant, source, guardian}` using `<ComplianceBadge>` + an HCS receipt card.
   - If `isCompliant === true` AND `guardian.status` ∈ {`submitted`, `cached`}: trigger `usePollForVc("gdst", eventHash)`. Render the polling status pill above an empty `<GuaranteedFieldsCard>`.
   - When the hook returns a VC: fill the card with `eventHash`, `gdstEventType`, `complianceStatus`, `policyVersion`, `issuedAt`, `species`, optional `supersedes` + a `<details>` raw-JSON expander.
   - When the hook hits its 300s ceiling: render the `manual_review` badge, link to the Health & Resilience tab.

**Failure modes**:

| Outcome | Display |
|---------|---------|
| Network error / 502 | Top-of-shell status banner: "API offline". Submit button disabled until reachable (re-checked by `useHealthPoll`). |
| `422` Pydantic validation error | Field-by-field error panel; no HCS section, no Guardian section. |
| `5xx` from backend | Show error JSON verbatim. |
| `guardian.status: skipped, reason: not_configured` | Greyed Guardian section linking to `scripts/build_gdst_policy.py`. |
| `guardian.status: skipped, reason: not_compliant` | Amber `<ComplianceBadge>`; Guardian section explains "rule predicate failed". Don't poll. |
| `guardian.status: skipped, reason: breaker_open` | Grey Guardian section linking to Health & Resilience tab. Don't poll. |

---

## Page 2: Submit FSMA (`pages/SubmitFsma.tsx`)

Mirror of Page 1 with substitutions:

- Sample source: `samples/fsma/*.json`.
- Submit endpoint: `POST /api/v1/epcis/compliance/check`.
- Poller slug: `"fsma"`.
- Guaranteed fields display: drop `species`, use `fsma204EventType` instead of `gdstEventType`.

The route response shape is identical (T048 normalised this), so `<ComplianceBadge>`, `<GuaranteedFieldsCard>`, and `usePollForVc` compose without per-policy branches.

---

## Page 3: Retrieve VC (`pages/RetrieveVc.tsx`)

**Actions**:

1. Render two inputs: `eventHashHex` text + a "policy" radio (`gdst` | `fsma`).
2. On "Retrieve" click:
   - `api.ts::getVc(slug, eventHashHex)` → `GET /api/v1/guardian/{slug}/vc/{eventHashHex}`.
   - 200: render via `<GuaranteedFieldsCard>` + raw-JSON `<details>`.
   - 404: explanatory empty state ("no VC for that event hash; check that you submitted it first").
   - 5xx: error JSON verbatim.

Read-only; no state mutation outside the page's local `useState`. **MVP scope cut**: the "Include history" checkbox + `<VcTimeline>` chain renderer are deferred to v1.1 — see [spec.md §User Story 4](../spec.md). The `lib/api.ts::getVc` helper still accepts `{ history }` so re-introducing the toggle is purely additive.

---

## Page 4: Health & Resilience (`pages/HealthAndResilience.tsx`)

**Actions**:

1. On mount: `useHealthPoll()` triggers `GET /api/v1/guardian/health` every 5s.
2. Render the response into a status card: status badge (color per state), breaker state, `last_failure_at` (relative timestamp), `consecutive_failures` (when T055 lands), skipped-event counter (same).
3. Outage simulator panel:
   - Toggle: "Simulate MGS down". On flip:
     - On → `api.ts::injectBreakerFailure()` → `POST /api/v1/_demo/breaker/inject`.
     - Off → `api.ts::clearBreaker()` → `POST /api/v1/_demo/breaker/clear`.
   - Display: current toggle state synced from `GET /api/v1/_demo/breaker/status` on mount.
   - Disabled with explanatory tooltip if the `_demo` routes return 404 (i.e., `GUARDIAN_DEMO_ROUTES_ENABLED` isn't set).
4. Render a "What this demonstrates" caption explaining the breaker invariants from research.md §3 — 3-strikes / 60s window / half-open probe / 451-no-counter-increment — so the viewer can map what they see on-screen to the spec.

---

## Helper-module contracts (`ui/trace-ui/src/lib` + `src/hooks`)

### `lib/api.ts`

```ts
// All paths relative; Vite proxy forwards /api/v1 to localhost:8000.
export type GuardianSubmissionStatus =
  | { status: "submitted"; cached: boolean; submittedAt: string }
  | { status: "skipped"; reason: "not_configured" | "not_compliant" | "breaker_open" }
  | { status: "error"; reason: string };

export type SubmitResponse = {
  status: "ok";
  transactionId: string;
  receiptStatus: string;
  eventType: string;
  eventHash: string;
  isCompliant: boolean;
  source: string;
  guardian: GuardianSubmissionStatus;
};

export async function submitGdstEvent(event: GDSTEvent): Promise<SubmitResponse>;
export async function submitFsmaEvent(event: StarfishEvent): Promise<SubmitResponse>;
export async function getVc(
  slug: "gdst" | "fsma",
  eventHash: string,
  opts?: { history?: boolean }
): Promise<VerifiableCredential | VerifiableCredential[] | null>;
export async function getHealth(): Promise<GuardianHealth>;
export async function injectBreakerFailure(): Promise<void>;     // /_demo/breaker/inject
export async function clearBreaker(): Promise<void>;             // /_demo/breaker/clear
export async function getBreakerSimulatorStatus(): Promise<{ active: boolean }>;
```

### `lib/samples.ts`

```ts
// Vite glob-import — bundle reads samples/{gdst,fsma}/*.json at build time.
export const gdstSamples: Record<string /* filename stem */, GDSTEvent>;
export const fsmaSamples: Record<string /* filename stem */, StarfishEvent>;
```

### `hooks/usePollForVc.ts`

```ts
type PollState =
  | { status: "polling"; elapsedMs: number }
  | { status: "ready"; vc: VerifiableCredential; elapsedMs: number }
  | { status: "manual_review"; elapsedMs: number };

export function usePollForVc(
  slug: "gdst" | "fsma" | null,        // null pauses the hook
  eventHash: string | null,
  opts?: { intervalMs?: number; timeoutMs?: number }
): PollState;
```

Implementation notes: `useEffect` with `setInterval` + `AbortController` cleanup on unmount. Defaults `intervalMs=5000`, `timeoutMs=300_000`.

### `hooks/useHealthPoll.ts`

```ts
export function useHealthPoll(intervalMs?: number): {
  health: GuardianHealth | null;
  apiOnline: boolean;
};
```

Implementation: same pattern as `usePollForVc`. `apiOnline` flips `false` on network error, `true` on successful response.

---

## New backend route: `_demo/breaker`

A small dev-only module — feature-flagged via `GUARDIAN_DEMO_ROUTES_ENABLED=1` in the FastAPI startup env. Documented here in prose rather than added to `mgs-boundary.openapi.yaml` (which is the MGS *boundary*, not our internal routes).

| Method | Path | Body | Response | Purpose |
|--------|------|------|----------|---------|
| `POST` | `/api/v1/_demo/breaker/inject` | `{ count?: number = 5 }` | `{ active: true }` | Make the next `count` `submit_document` calls raise `GuardianUnavailable`. |
| `POST` | `/api/v1/_demo/breaker/clear` | `{}` | `{ active: false }` | Reset the demo failure flag. |
| `GET` | `/api/v1/_demo/breaker/status` | — | `{ active: boolean }` | Read-only state echo. |

Mounted only when `settings.GUARDIAN_DEMO_ROUTES_ENABLED == "1"`. The flag is not present in `api/.env.dev` by default.

---

## Why no new OpenAPI / JSON Schema

The frontend doesn't introduce a wire-level contract — it consumes the existing one. The `_demo/breaker/*` admin routes are dev-only and feature-flagged; they're documented here in prose. If a v2 makes the demo a deployable product, those routes graduate to `contracts/guardian-http-errors.md` (the prose+table contract for the inbound `/guardian/*` HTTP surface, exempted from OpenAPI per 001-guardian-integration plan.md §Post-refactor re-check).
