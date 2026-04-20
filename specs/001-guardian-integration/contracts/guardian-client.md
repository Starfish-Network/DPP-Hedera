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

```python
async def register_user(self, username: str, role: Literal["User", "STANDARD_REGISTRY"] = "User") -> UserRecord
```

- **MGS**: `POST /accounts/register`.
- **409 handling**: MUST NOT raise. Resolves existing DID via `GET /profiles/{username}` and returns the `UserRecord` unchanged — idempotent by design (FR-008).

```python
async def set_user_credentials(self, username: str, credentials: HederaCredentials) -> TaskHandle
```

- **MGS**: `PUT /profiles/push/{username}` (async).
- **Returns**: `TaskHandle`; caller awaits `wait_for_task`.

```python
async def get_user_did(self, username: str) -> str
```

- **MGS**: `GET /profiles/{username}` → `profile.did`.
- **Errors**: `GuardianNotFound` on `404`.

---

## Schemas & policies (SR-only)

```python
async def create_schema(self, schema: dict) -> SchemaRecord                          # POST /schemas (sync)
async def publish_schema(self, schema_id: str) -> TaskHandle                         # PUT /schemas/push/{id}/publish
async def create_policy(self, policy: dict) -> PolicyRecord                          # POST /policies (sync)
async def publish_policy(self, policy_id: str) -> TaskHandle                         # PUT /policies/push/{id}/publish
async def export_policy(self, policy_id: str, out_path: Path) -> Path                # GET /policies/{id}/export/file → .policy zip
```

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
) -> VCDocument | None
```

- **MGS**: `GET /policies/{id}/documents?type=VC` with client-side filter on `credentialSubject.eventHash`. (MGS does not index `eventHash`; we filter in memory.)
- **Returns**: the matching VC or `None`. Pagination handled internally (hard cap: 1000 records; raise `GuardianUnavailable` if the cap is hit — indicates reconciliation is behind).
- **Used by**: `/guardian/gdst/vc/{event_hash}` and `/guardian/fsma/vc/{event_hash}`.

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
| `GuardianConflict` | MGS `409` (other than register_user idempotent case) | `409` |
| `GuardianClientError` | MGS `4xx` not covered above | `400` with upstream detail |
| `GuardianUnavailable` | Network, 5xx, 429 | `503` |
| `GuardianBreakerOpen` | Breaker open at call time | `503` with `detail: "breaker_open"` — DOES NOT retry |
| `GuardianTaskTimeout` | Task poll exceeded 120 s | `503` |

## Invariants (tested)

- Breaker opens after exactly 3 consecutive "counting" failures.
- Breaker stays open for 60 s from the last failure.
- After 60 s, next call is a probe: success → closed, failure → 60 s window restarts (ONE failure, not another three).
- `register_user` on an existing username returns the existing DID and does not raise.
- `submit_document` does not retry inline; retries are the reconciliation job's responsibility (out of scope for v1).
- `wait_for_task` never races: if the task completes between polls, the next poll observes it.

Each invariant has a matching test under `api/app/tests/integration/guardian/test_circuit_breaker.py` or `test_guardian_client_contract.py`.
