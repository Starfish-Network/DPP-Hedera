# Contract: `guardian_client.py`

**Feature**: `001-guardian-integration` | **Module**: `api/app/service/guardian_client.py`

Typed interface for the MGS REST client. This contract is authoritative — the implementation under `api/app/service/guardian_client.py` and the MGS subset in [mgs-boundary.openapi.yaml](mgs-boundary.openapi.yaml) MUST match. Any change to this file is a change to the implementation, and vice versa.

---

## Class

```python
class GuardianClient:
    def __init__(
        self,
        base_url: str,
        sr_username: str,
        sr_password: str,
        *,
        http: httpx.AsyncClient | None = None,
        breaker: CircuitBreaker | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None: ...
```

The `clock` injection is required for deterministic breaker tests.

---

## Authentication

```python
async def login(self) -> str
```

- **MGS**: `POST /accounts/login` → `{ accessToken, refreshToken }`.
- **Returns**: the bearer token. Cached for the life of the client; refreshed on `401`.
- **Errors**: `GuardianAuthError` on `401/403`; `GuardianUnavailable` on network/5xx (counts toward breaker, see `research.md §3`).

```python
async def get_health(self) -> HealthStatus
```

- **MGS**: `GET /accounts/session` with the cached JWT.
- **Returns**: `HealthStatus` — one of `ok`, `tos_required`, `breaker_open`, `unavailable`.
- `tos_required` is surfaced specifically on MGS `451` and does NOT count toward the breaker.

---

## Identity

Operator onboarding (user registration, credential activation, DID resolution) is **out of scope for v1** (spec §FR-007 / Assumptions). Operators are pre-provisioned directly in the MGS portal before any event is submitted, so the client exposes no onboarding methods in v1. `login()` / `get_health()` above are the only identity-adjacent calls and operate on the SR credentials.

v2 will reintroduce `register_user`, `set_user_credentials`, and `get_user_did` backed by `POST /accounts/register`, `PUT /profiles/push/{username}`, and `GET /profiles/{username}` respectively. These paths are intentionally absent from [mgs-boundary.openapi.yaml](mgs-boundary.openapi.yaml) for v1.

---

## Schemas & policies (SR-only)

```python
async def create_schema(self, schema: dict) -> SchemaRecord                          # POST /schemas (sync)
async def publish_schema(self, schema_id: str) -> TaskHandle                         # PUT /schemas/push/{id}/publish
async def list_schemas(self, topic_id: str) -> list[dict]                            # GET /schemas/{topicId}
async def create_policy(self, policy: dict) -> PolicyRecord                          # POST /policies (sync)
async def list_policies(self) -> list[dict]                                          # GET /policies
async def publish_policy(self, policy_id: str) -> TaskHandle                         # PUT /policies/push/{id}/publish
async def export_policy(self, policy_id: str, out_path: Path) -> Path                # GET /policies/{id}/export/file → .policy zip
```

`list_policies` and `list_schemas` return a single page (pageSize=200); used by bootstrap scripts for tag/schema lookup after partial runs.

`TaskHandle` is `{ task_id: str, submitted_at: datetime }`. `wait_for_task` (below) drives the polling loop.

---

## Event submission (hot path)

```python
async def submit_document(
    self,
    policy_id: str,
    block_tag: str,
    document: dict,
) -> SubmitAck
```

- **MGS**: `POST /external/{policyId}/{blockTag}`.
- **Semantics**: fire-and-acknowledge. The VC is issued asynchronously by the Guardian pipeline; this call returns as soon as MGS accepts the document. Does NOT block on VC creation.
- **Breaker**: protected by the circuit breaker — if open, raises `GuardianBreakerOpen` immediately without making a call.
- **Failure → breaker**: network error, 5xx, 429 increment the breaker counter. 451 returns `GuardianToSRequired` and does NOT increment. Other 4xx raise `GuardianClientError` and do NOT increment.
- **Call site**: invoked after the HCS and `ComplianceVerifier.recordEvent()` calls; MUST NOT block the `/events/*` response (Constitution §IV).

---

## VC retrieval

```python
async def get_vc_by_event_hash(
    self,
    policy_id: str,
    event_hash: str,
    *,
    history: bool = False,
) -> VCDocument | list[VCDocument] | None
```

- **MGS**: `GET /policies/{id}/documents?type=VC` with client-side filter on `credentialSubject.eventHash`. (MGS does not index `eventHash`; we filter in memory.)
- **`history=False` (default)**: returns the **latest** VC for `event_hash` (i.e. the one whose `credentialSubject.complianceStatus != "superseded"`, or the most recently issued if no superseding exists). Returns `None` if nothing found.
- **`history=True`**: returns the full ordered superseding chain `[oldest, …, latest]` so callers can audit corrections (spec §FR-007, §FR-014). Returns `[]` if nothing found.
- Pagination handled internally (hard cap: 1000 records; raise `GuardianUnavailable` if the cap is hit — indicates reconciliation is behind).
- **Used by**: `/guardian/gdst/vc/{event_hash}` and `/guardian/fsma/vc/{event_hash}` — routes forward the `?history=true` query parameter 1:1.

```python
async def get_vc_retrieval_status(
    self,
    policy_id: str,
    event_hash: str,
    *,
    submitted_at: datetime,
) -> VCRetrievalStatus
```

- Used by `/guardian/*/vc/{event_hash}` to drive SC-007's pending-window behavior.
- Returns one of:
  - `ready(vc)` — a VC exists.
  - `pending` — no VC yet; `now - submitted_at < 30 s`. Route returns `202 Accepted`.
  - `manual_review` — no VC yet; `now - submitted_at >= 5 min`. Route returns `503 VC_MANUAL_REVIEW` (new error). Event is flagged on `/guardian/health`.
  - `unknown` — no submission record for `event_hash`. Route returns `404`.
- The 30 s and 5 min constants are module-level (`VC_PENDING_THRESHOLD_S = 30`, `VC_MANUAL_REVIEW_CEILING_S = 300`) so they can be stubbed under test.

---

## Task polling

```python
async def wait_for_task(self, task_id: str, *, timeout: float = 120.0) -> TaskResult
```

- **MGS**: repeated `GET /tasks/{taskId}`.
- **Backoff**: `tenacity` — initial 500 ms, factor 2, cap 8 s. Global `timeout` default 120 s (see `research.md §7`).
- **Errors**: `GuardianTaskTimeout` on timeout; FastAPI maps this to `503`.

---

## Circuit-breaker observability

```python
def circuit_status(self) -> Literal["closed", "open", "half_open", "tos_required"]
```

- Pure local read, never makes an HTTP call.
- Used by `/guardian/health`.

---

## Error taxonomy

| Exception | When | HTTP mapping in `/guardian/*` routes |
|-----------|------|--------------------------------------|
| `GuardianAuthError` | MGS rejects credentials | `503` (treated as MGS config problem) |
| `GuardianToSRequired` | MGS `451` | `503` with `detail: "tos_required"` |
| `GuardianNotFound` | MGS `404` on identity/profile | `404` |
| `GuardianConflict` | MGS `409` | `409` |
| `GuardianClientError` | MGS `4xx` not covered above | `400` with upstream detail |
| `GuardianUnavailable` | Network, 5xx, 429 | `503` |
| `GuardianBreakerOpen` | Breaker open at call time | `503` with `detail: "breaker_open"` — DOES NOT retry |
| `GuardianTaskTimeout` | Task poll exceeded 120 s | `503` |
| `GuardianVCPending` | `get_vc_retrieval_status` returns `pending` (within 30 s window) | `202 Accepted` with `{ "status": "pending", "submitted_at": ... }` |
| `GuardianVCManualReview` | `get_vc_retrieval_status` returns `manual_review` (past 5 min ceiling, SC-007) | `503` with `detail: "vc_manual_review"` |

## Invariants (tested)

- Breaker opens after exactly 3 consecutive "counting" failures.
- Breaker stays open for 60 s from the last failure.
- After 60 s, next call is a probe: success → closed, failure → 60 s window restarts (ONE failure, not another three).
- `submit_document` does not retry inline — there is no v1 reconciliation worker (spec §FR-006). Breaker-skipped submissions emit a structured WARN log (`event_hash`, `operator_did`, `mgs_error_class`, `breaker_opened_at`) and are replayable only by manual operator re-submission of the idempotent `/events` call.
- **Idempotency (FR-004)**: callers of `submit_document` MUST first consult `get_vc_by_event_hash` (or a local cache keyed on `event_hash`) and short-circuit if a VC already exists. A duplicate submission does not call MGS and does not increment the breaker counter.
- **Immutable VCs (FR-014)**: `submit_document` never mutates a prior VC. A correction is a fresh `submit_document` whose payload carries `{"complianceStatus": "superseded", "supersedes": "<prior eventHash>"}`; the resulting chain is retrievable via `get_vc_by_event_hash(..., history=True)`.
- **Full-payload VCs (FR-015)**: `schema_mapper.to_credential_subject(event)` returns the complete event body (all KDEs) plus `{eventHash, gdstEventType | fsma204EventType, complianceStatus, policyVersion, issuedAt}` and optionally `supersedes`. There is no v1 redaction pass.
- **SC-007 retrieval window**: `get_vc_retrieval_status` uses the injected `clock` so tests can advance virtual time across the 30 s / 300 s thresholds.
- `wait_for_task` never races: if the task completes between polls, the next poll observes it.

Each invariant has a matching test under `api/app/tests/integration/guardian/test_circuit_breaker.py` or `test_guardian_client_contract.py`.
