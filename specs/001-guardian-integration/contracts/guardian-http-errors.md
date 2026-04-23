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

Per spec.md Edge Cases (post-F3 amendment) and SC-007: the `pending` (<30 s post-submission) and `manual_review` (≥300 s) states are **not** exposed over HTTP in v1. They are surfaced through the Python `GuardianClient.get_vc_retrieval_status()` direct-caller contract (see [guardian-client.md](guardian-client.md)). HTTP `202 Accepted` / `503 VC_MANUAL_REVIEW` responses are deferred to v2.

---

## Body-level Error Codes (not HTTP status)

Acceptance-scenario error codes such as `GDST_MISSING_FISHING_AUTHORIZATION`, `FSMA_MISSING_SHIP_TO` are **FastAPI response-body error codes** emitted by `/events` endpoints on pre-check failure, not by this `/guardian/*` surface. Each maps 1:1 to a rule ID in [data-model.md §2 Rule Source Table](../data-model.md). The concrete HTTP-code ↔ rule-ID mapping lives next to `api/app/helpers/compliance.py` and is produced during `/speckit-implement` (spec.md §"Error-code convention").

---

## Stability

- Path shape (`/guardian/{slug}/vc/{h}`) is stable for v1. v2 may add a pending-state HTTP surface; existing `200 / 404 / 503` behaviour will not break.
- HTTP status codes above are the canonical list; additions in v1 require a spec amendment referencing this file.
