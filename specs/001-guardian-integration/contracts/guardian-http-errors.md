# Guardian HTTP Surface — Endpoints & Error Codes

**Feature**: `001-guardian-integration` | **Scope**: inbound `/guardian/*` routes exposed by `api/app/routes/guardian/`. Canonical per FR-007; Constitution §VI (authoritative contracts).

This file is the authoritative list for the HTTP surface our FastAPI app exposes to clients (auditors, internal tooling). The outbound boundary to MGS is covered by [mgs-boundary.openapi.yaml](mgs-boundary.openapi.yaml); the typed Python client contract is in [guardian-client.md](guardian-client.md).

---

## Endpoints

All paths are mounted under the FastAPI root. JWT authentication is enforced by the existing middleware; no Guardian-specific auth layer.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/guardian/health` | Health check. Returns `{status, breaker, last_failure_at, consecutive_failures}` per FR-009 + T055. |
| `GET` | `/guardian/{policy_slug}/vc/{event_hash}` | Retrieve the latest VC for `event_hash`. `policy_slug ∈ {gdst, fsma}` (registry lookup per data-model.md §Policy Registry). |
| `GET` | `/guardian/{policy_slug}/vc/{event_hash}?history=true` | Retrieve the ordered superseding chain `[oldest, …, latest]` for `event_hash`. See FR-014. |

The single slug-parameterised VC route replaces the prior GDST-only / FSMA-only handler pair (tasks.md T036a); the URL strings `/guardian/gdst/vc/{h}` and `/guardian/fsma/vc/{h}` remain byte-identical to the pre-refactor contract.

---

## HTTP Response Codes

### `GET /guardian/{policy_slug}/vc/{event_hash}`

| Status | Condition | Response body |
|--------|-----------|---------------|
| `200` | VC exists | Single VC document (shape per [vc-output.schema.json](vc-output.schema.json)). With `?history=true`: `{eventHash, history: [VC, …]}`. |
| `404` | `policy_slug` not registered, or no VC found for `event_hash` | `{detail: "unknown policy: <slug>"}` or `{detail: "VC not found for eventHash"}` |
| `503` | MGS unavailable (network error / 5xx / breaker open / auth failure) | `{detail: "guardian_unavailable"}` |
| `503` | MGS Terms of Service not accepted (mapped from MGS 451) | `{detail: "tos_required"}` |
| `503` | Policy configured in registry but env vars missing (`enabled == False`) | `{detail: "Guardian <SLUG> policy is not configured"}` |
| `400` | Other MGS client error propagated (e.g., malformed `event_hash`) | `{detail: "<error text>"}` |

Exception → HTTP mapping is authoritative in [guardian-client.md §Error taxonomy](guardian-client.md). The table above is the inverse view.

### `GET /guardian/health`

| Status | Condition | Response body `status` |
|--------|-----------|---------|
| `200` | Breaker closed, MGS session valid | `ok` |
| `200` | Breaker open | `breaker_open` |
| `200` | MGS returned 451 on the last probe | `tos_required` |
| `200` | Network/5xx/auth error on probe | `unavailable` |

Note: `/guardian/health` returns `200` for **all** status values — the body discriminates. This keeps platform health-checks (Kubernetes, load balancers) simple and localises Guardian-availability parsing to consumers that care.

---

## Pending / Manual-Review State (v1 scope)

v2 deferral per [spec.md §Edge Cases + §Assumptions](../spec.md). Thresholds and state semantics owned by [guardian-client.md §VC retrieval](guardian-client.md).

---

## Body-level Error Codes (not HTTP status)

Acceptance-scenario codes (`GDST_MISSING_FISHING_AUTHORIZATION`, `FSMA_MISSING_SHIP_TO`, …) are emitted by `/events` endpoints on pre-check failure, not by this `/guardian/*` surface. See [spec.md §"Error-code convention"](../spec.md).

---

## Stability

- Path shape (`/guardian/{slug}/vc/{h}`) is stable for v1. v2 may add a pending-state HTTP surface; existing `200 / 404 / 503` behaviour will not break.
- HTTP status codes above are the canonical list; additions in v1 require a spec amendment referencing this file.
