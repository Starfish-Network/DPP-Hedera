"""
Guardian / Managed Guardian Service (MGS) REST client.

Implements the contract declared in
specs/001-guardian-integration/contracts/guardian-client.md.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_exponential,
)

from app.core.config import settings

# Exposed at module scope so SC-007 tests can monkey-patch the thresholds
# without reaching into client state (contract: guardian-client.md §141).
VC_PENDING_THRESHOLD_S: float = 30.0
VC_MANUAL_REVIEW_CEILING_S: float = 300.0


class GuardianError(Exception):
    """Base class for all Guardian-client errors."""


class GuardianAuthError(GuardianError):
    """MGS rejected credentials (401/403)."""


class GuardianToSRequired(GuardianError):
    """MGS 451 — Terms of Service must be accepted in the MGS portal."""


class GuardianNotFound(GuardianError):
    """MGS 404 — identity/profile/document not found."""


class GuardianConflict(GuardianError):
    """MGS 409."""


class GuardianClientError(GuardianError):
    """MGS 4xx not covered by a more specific class."""


class GuardianUnavailable(GuardianError):
    """Network / 5xx / 429 — counts toward the circuit breaker."""


class GuardianBreakerOpen(GuardianError):
    """Breaker is open at call time — no HTTP call was made."""


class GuardianTaskTimeout(GuardianError):
    """wait_for_task exceeded its configured timeout."""


class GuardianVCPending(GuardianError):
    """VC retrieval: still within the 30 s pending window."""


class GuardianVCManualReview(GuardianError):
    """VC retrieval: past the 300 s ceiling — escalate to manual review."""


class _TaskNotReady(Exception):
    """Internal: signals tenacity to keep polling."""


BreakerState = Literal["closed", "open", "half_open", "tos_required"]


class CircuitBreaker:

    def __init__(
        self,
        *,
        fail_threshold: int = 3,
        open_duration_s: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fail_threshold = fail_threshold
        self._open_duration_s = open_duration_s
        self._clock = clock
        self._state: BreakerState = "closed"
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._last_failure_at: float | None = None

    @property
    def state(self) -> BreakerState:
        if self._state == "open" and self._opened_at is not None:
            if self._clock() - self._opened_at >= self._open_duration_s:
                self._state = "half_open"
        return self._state

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    @property
    def last_failure_at(self) -> float | None:
        return self._last_failure_at

    def should_allow_call(self) -> bool:
        state = self.state
        return state in ("closed", "half_open")

    def record_success(self) -> None:
        # tos_required clears only via operator action in the MGS portal.
        if self._state == "tos_required":
            return
        self._state = "closed"
        self._consecutive_failures = 0
        self._opened_at = None

    def record_failure(self, error: Exception) -> None:
        now = self._clock()
        if isinstance(error, GuardianToSRequired):
            self._state = "tos_required"
            self._last_failure_at = now
            return
        if not isinstance(error, GuardianUnavailable):
            return
        self._last_failure_at = now
        if self._state == "half_open":
            # probe failure — one failure re-opens the window, not another three
            self._state = "open"
            self._opened_at = now
            return
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._fail_threshold:
            self._state = "open"
            self._opened_at = now


HealthStatus = Literal["ok", "tos_required", "breaker_open", "unavailable"]


@dataclass
class TaskHandle:
    taskId: str
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TaskResult:
    taskId: str
    status: Literal["PENDING", "PROCESSING", "COMPLETED", "FAILED"]
    result: Any = None
    error: str | None = None


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
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._sr_username = sr_username
        self._sr_password = sr_password
        self._http = http or httpx.AsyncClient(base_url=self._base_url, timeout=30.0)
        self._breaker = breaker or CircuitBreaker(
            fail_threshold=settings.GUARDIAN_BREAKER_FAIL_COUNT,
            open_duration_s=settings.GUARDIAN_BREAKER_OPEN_DURATION_S,
            clock=clock,
        )
        self._clock = clock
        self._jwt: str | None = None

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._jwt}"} if self._jwt else {}

    def _classify(self, r: httpx.Response) -> GuardianError | None:
        code = r.status_code
        if code < 400:
            return None
        if code == 451:
            return GuardianToSRequired("MGS requires TOS acceptance in the portal")
        if code in (401, 403):
            return GuardianAuthError(f"MGS auth failed: {code}")
        if code == 404:
            return GuardianNotFound(r.text)
        if code == 409:
            return GuardianConflict(r.text)
        if code == 429 or 500 <= code < 600:
            return GuardianUnavailable(f"MGS {code}: {r.text}")
        return GuardianClientError(f"MGS {code}: {r.text}")

    async def _raw_call(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return await self._http.request(
                method, path, headers=self._auth_headers(), **kwargs
            )
        except httpx.HTTPError as e:
            raise GuardianUnavailable(f"network: {e}") from e

    async def _call_with_refresh(
        self, method: str, path: str, **kwargs: Any
    ) -> httpx.Response:
        r = await self._raw_call(method, path, **kwargs)
        if r.status_code == 401 and self._jwt is not None:
            self._jwt = None
            await self.login()
            r = await self._raw_call(method, path, **kwargs)
        return r

    async def login(self) -> str:
        r = await self._raw_call(
            "POST",
            "/accounts/login",
            json={"username": self._sr_username, "password": self._sr_password},
        )
        err = self._classify(r)
        if err is not None:
            if isinstance(err, (GuardianToSRequired, GuardianUnavailable)):
                self._breaker.record_failure(err)
            raise err
        token = r.json().get("accessToken")
        if not token:
            raise GuardianClientError("MGS login response missing accessToken")
        self._jwt = token
        return token

    async def get_health(self) -> HealthStatus:
        breaker_state = self._breaker.state
        if breaker_state == "tos_required":
            return "tos_required"
        if breaker_state == "open":
            return "breaker_open"
        if self._jwt is None:
            try:
                await self.login()
            except GuardianToSRequired:
                return "tos_required"
            except (GuardianUnavailable, GuardianAuthError):
                return "unavailable"
        r = await self._call_with_refresh("GET", "/accounts/session")
        err = self._classify(r)
        if err is None:
            self._breaker.record_success()
            return "ok"
        if isinstance(err, GuardianToSRequired):
            self._breaker.record_failure(err)
            return "tos_required"
        if isinstance(err, GuardianUnavailable):
            self._breaker.record_failure(err)
            return "unavailable"
        return "unavailable"

    def circuit_status(self) -> BreakerState:
        return self._breaker.state

    @property
    def last_failure_at(self) -> float | None:
        return self._breaker.last_failure_at

    @property
    def breaker(self) -> CircuitBreaker:
        # Exposed for tests that assert breaker-internal state. Production
        # callers should prefer `circuit_status()` / `last_failure_at`.
        return self._breaker

    # --- Task polling ---

    async def wait_for_task(
        self, task_id: str, *, timeout: float = 120.0
    ) -> TaskResult:
        async def _poll_once() -> TaskResult:
            r = await self._call_with_refresh("GET", f"/tasks/{task_id}")
            err = self._classify(r)
            if err is not None:
                raise err
            data = r.json()
            result = TaskResult(
                taskId=data.get("taskId", task_id),
                status=data.get("status"),
                result=data.get("result"),
                error=data.get("error"),
            )
            if result.status not in ("COMPLETED", "FAILED"):
                raise _TaskNotReady()
            return result

        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(_TaskNotReady),
                stop=stop_after_delay(timeout),
                wait=wait_exponential(multiplier=0.5, max=8.0),
                reraise=True,
            ):
                with attempt:
                    return await _poll_once()
        except _TaskNotReady as e:
            raise GuardianTaskTimeout(
                f"task {task_id} did not complete in {timeout}s"
            ) from e
        raise GuardianTaskTimeout(f"task {task_id} did not complete in {timeout}s")
