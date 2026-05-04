"""
Guardian / Managed Guardian Service (MGS) REST client.

Implements the contract declared in
specs/001-guardian-integration/contracts/guardian-client.md.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
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


@dataclass
class SubmitAck:
    """Return of submit_document — MGS accepted the intake, issuance is async."""
    event_hash: str
    submitted_at: datetime
    cached: bool = False  # True when the idempotency cache short-circuited


# Duck-typed: any dict that looks like a VC works. Kept as `dict` for simplicity.
VCDocument = dict[str, Any]


@dataclass
class VCRetrievalStatus:
    """SC-007 retrieval state. Exactly one of `vc` or a status tag is set."""
    state: Literal["ready", "pending", "manual_review", "unknown"]
    vc: VCDocument | None = None


# Hard cap on in-memory pagination (contract: guardian-client.md §105).
_VC_PAGINATION_CAP = 1000
# Idempotency cache TTL (wall seconds). FR-004 — duplicate submits short-circuit.
_IDEMPOTENCY_TTL_S = 3600.0


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
        self._refresh_token: str | None = None
        # Idempotency cache: event_hash -> (VCDocument-ish ack, wall_timestamp).
        # Entries expire after _IDEMPOTENCY_TTL_S wall seconds (FR-004).
        self._idempotency_cache: dict[str, tuple[VCDocument, float]] = {}
        # Submission-time ledger: event_hash -> submitted_at (monotonic seconds).
        # Drives SC-007 pending/manual_review thresholds.
        self._submission_times: dict[str, float] = {}

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._jwt}"} if self._jwt else {}

    def _classify(self, r: httpx.Response) -> GuardianError | None:
        code = r.status_code
        if code < 400:
            return None
        if code == 451:
            # MGS uses 451 for both ToS-not-accepted AND tenant quota errors
            # ({"code": "S02", "details": {"message": "Limit exceeded", "limit": ...}}).
            # Distinguish so the breaker doesn't lock into `tos_required` for a
            # transient quota issue that the operator can clear by deleting an
            # unused policy in the portal.
            body: object = None
            try:
                body = r.json()
            except Exception:
                pass
            details = body.get("details") if isinstance(body, dict) else None
            if isinstance(details, dict) and details.get("limit"):
                return GuardianClientError(
                    f"MGS quota exceeded: {details}. Free a slot in the MGS portal then retry."
                )
            msg = (
                details.get("message")
                if isinstance(details, dict) and details.get("message")
                else "MGS requires TOS acceptance in the portal"
            )
            return GuardianToSRequired(f"{msg} (body={r.text[:300]})")
        if code in (401, 403):
            return GuardianAuthError(f"MGS auth failed: {code} — body={r.text[:200]!r}")
        if code == 404:
            return GuardianNotFound(r.text)
        if code == 409:
            return GuardianConflict(r.text)
        if code == 429 or 500 <= code < 600:
            return GuardianUnavailable(f"MGS {code}: {r.text}")
        return GuardianClientError(f"MGS {code}: {r.text}")

    async def _raw_call(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        merged = dict(self._auth_headers())
        if headers:
            merged.update(headers)
        try:
            return await self._http.request(method, path, headers=merged, **kwargs)
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
        # MGS (`guardianservice.app`) authenticates regular users (incl. SRs)
        # through /accounts/loginByEmail, which returns the MGS-shaped
        # {success, posibleUsers, login: {...}} session DTO. /accounts/login
        # only works for tenant-admin accounts where username == email.
        r = await self._raw_call(
            "POST",
            "/accounts/loginByEmail",
            json={
                "email": self._sr_username,
                "password": self._sr_password,
            },
        )
        err = self._classify(r)
        if err is not None:
            if isinstance(err, (GuardianToSRequired, GuardianUnavailable)):
                self._breaker.record_failure(err)
            raise err

        body = r.json()
        # MGS tenants wrap the session under `login` and gate it behind
        # `success` (multi-user disambiguation). Stock Guardian returns the
        # session flat. Support both.
        if isinstance(body, dict) and "success" in body and not body.get("login"):
            possible = body.get("posibleUsers") or []
            raise GuardianClientError(
                f"MGS login requires userId disambiguation; posibleUsers={possible!r}"
            )
        session = body.get("login") if isinstance(body.get("login"), dict) else body
        if not isinstance(session, dict):
            raise GuardianClientError(f"login response not an object: {body!r}")

        # MGS returns only a refreshToken from /accounts/login — exchange it at
        # /accounts/access-token for the bearer. Stock Guardian returns an
        # accessToken directly, in which case we skip the second hop.
        token = session.get("accessToken")
        refresh = session.get("refreshToken")
        if refresh:
            self._refresh_token = refresh
        if not token:
            if not refresh:
                preview = str(body)[:200]
                raise GuardianClientError(
                    f"login response missing both accessToken and refreshToken "
                    f"(body={preview})"
                )
            token = await self._exchange_refresh_token(refresh)
        self._jwt = token
        return token

    async def _exchange_refresh_token(self, refresh_token: str) -> str:
        """POST /accounts/access-token with the refresh token — returns the bearer."""
        r = await self._raw_call(
            "POST",
            "/accounts/access-token",
            json={"refreshToken": refresh_token},
        )
        err = self._classify(r)
        if err is not None:
            if isinstance(err, (GuardianToSRequired, GuardianUnavailable)):
                self._breaker.record_failure(err)
            raise err
        body = r.json()
        token = (
            body.get("accessToken")
            if isinstance(body, dict)
            else None
        )
        if not token:
            preview = str(body)[:200]
            raise GuardianClientError(
                f"/accounts/access-token response missing accessToken (body={preview})"
            )
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
            tid = data.get("taskId", task_id)
            res = data.get("result")

            def _make(status: str, error: Any = None) -> TaskResult:
                return TaskResult(taskId=tid, status=status, result=res, error=error)

            # MGS wraps completion under info.{completed,failed} and surfaces
            # errors as a top-level {code,message}; stock Guardian returns a
            # flat {status}. Check both so polls fail fast on MGS errors.
            info = data.get("info") or {}
            top_error = data.get("error")
            if top_error or info.get("failed"):
                err_msg = (
                    top_error.get("message") or str(top_error)
                    if isinstance(top_error, dict)
                    else top_error
                )
                return _make("FAILED", err_msg)
            if info.get("completed"):
                return _make("COMPLETED")
            # MGS testnet bug: top-level info.completed stays false even after
            # every step.completed flips true. Treat "all steps done" as done.
            steps = info.get("steps") or []
            if steps and all(s.get("completed") and not s.get("failed") for s in steps):
                return _make("COMPLETED")
            flat_status = data.get("status")
            if flat_status in ("COMPLETED", "FAILED"):
                return _make(flat_status)
            raise _TaskNotReady()

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

    # --- Event submission + VC retrieval (hot path) ---

    def _purge_idempotency_cache(self) -> None:
        now = self._clock()
        stale = [k for k, (_, t) in self._idempotency_cache.items()
                 if now - t > _IDEMPOTENCY_TTL_S]
        for k in stale:
            self._idempotency_cache.pop(k, None)

    async def submit_document(
        self,
        policy_id: str,
        block_tag: str,
        document: dict[str, Any],
    ) -> SubmitAck:
        """
        POST /external/{policyId}/{blockTag}. Fire-and-acknowledge (contract §72).

        - Short-circuits on idempotency cache hit (FR-004) — no MGS call.
        - Raises GuardianBreakerOpen immediately if the breaker is open.
        - Increments the breaker on network/5xx/429. 451 -> tos_required,
          no counter increment. Other 4xx -> GuardianClientError, no increment.
        """
        event_hash = document.get("eventHash")
        if not isinstance(event_hash, str):
            raise ValueError("document missing 'eventHash' — mapper must stamp it")

        self._purge_idempotency_cache()
        cached = self._idempotency_cache.get(event_hash)
        if cached is not None:
            vc, _ = cached
            return SubmitAck(
                event_hash=event_hash,
                submitted_at=datetime.now(timezone.utc),
                cached=True,
            )

        if not self._breaker.should_allow_call():
            raise GuardianBreakerOpen(f"breaker state: {self._breaker.state}")

        if self._jwt is None:
            await self.login()

        path = f"/external/{policy_id}/{block_tag}"
        r = await self._call_with_refresh("POST", path, json=document)
        err = self._classify(r)
        if err is not None:
            if isinstance(err, (GuardianUnavailable, GuardianToSRequired)):
                self._breaker.record_failure(err)
            raise err

        self._breaker.record_success()
        now_mono = self._clock()
        self._idempotency_cache[event_hash] = (document, now_mono)
        self._submission_times[event_hash] = now_mono
        return SubmitAck(
            event_hash=event_hash,
            submitted_at=datetime.now(timezone.utc),
            cached=False,
        )

    @staticmethod
    def _unwrap_list_body(body: Any) -> list[dict[str, Any]]:
        """MGS returns either a bare list or {items|data: [...]} — handle both."""
        if isinstance(body, list):
            return body
        if isinstance(body, dict):
            return body.get("items") or body.get("data") or []
        return []

    async def list_policies(self, *, page_size: int = 200) -> list[dict[str, Any]]:
        """GET /policies — single page. Tenants realistically hold <200 policies."""
        r = await self._authed_call(
            "GET", "/policies", params={"pageSize": page_size}
        )
        return self._unwrap_list_body(r.json())

    async def list_schemas(
        self, topic_id: str, *, page_size: int = 200
    ) -> list[dict[str, Any]]:
        """GET /schemas/{topicId} — single page."""
        r = await self._authed_call(
            "GET", f"/schemas/{topic_id}", params={"pageSize": page_size}
        )
        return self._unwrap_list_body(r.json())

    async def _list_vcs_for_policy(self, policy_id: str) -> list[VCDocument]:
        """GET /policies/{id}/documents?type=VC with in-memory pagination."""
        results: list[VCDocument] = []
        page = 1
        page_size = 100
        while len(results) < _VC_PAGINATION_CAP:
            r = await self._call_with_refresh(
                "GET",
                f"/policies/{policy_id}/documents",
                params={"type": "VC", "page": page, "pageSize": page_size},
            )
            err = self._classify(r)
            if err is not None:
                raise err
            items = self._unwrap_list_body(r.json())
            if not items:
                break
            results.extend(items)
            if len(items) < page_size:
                break
            page += 1
        if len(results) >= _VC_PAGINATION_CAP:
            raise GuardianUnavailable(
                f"VC pagination hit cap {_VC_PAGINATION_CAP} — reconciliation is behind"
            )
        return results

    async def get_policy_vc(self, policy_id: str) -> dict[str, Any] | None:
        """Fetch the policy's own self-describing VC (the `type: POLICY` doc
        published when the policy was registered on Hedera). MGS exposes this
        via /search-documents — the regular /documents?type=VC filter excludes
        it. Returns None if the search returns no POLICY-type entry.
        """
        if self._jwt is None:
            await self.login()
        r = await self._call_with_refresh(
            "GET",
            f"/policies/{policy_id}/search-documents",
            params={"pageSize": 100},
        )
        err = self._classify(r)
        if err is not None:
            raise err
        items = self._unwrap_list_body(r.json()) if r.text else []
        for d in items:
            if d.get("type") == "POLICY":
                return d
        return None

    @staticmethod
    def _credential_subject(vc: VCDocument) -> dict[str, Any]:
        cs = vc.get("credentialSubject") or {}
        if isinstance(cs, list):
            return cs[0] if cs else {}
        return cs

    async def get_vc_by_event_hash(
        self,
        policy_id: str,
        event_hash: str,
        *,
        history: bool = False,
    ) -> VCDocument | list[VCDocument] | None:
        """
        Retrieve a VC (or its full superseding chain) by eventHash.

        - history=False: returns the latest VC (the one whose complianceStatus
          != 'superseded', falling back to the most recently issued).
        - history=True: returns the ordered chain [oldest, ..., latest].
        """
        if self._jwt is None:
            await self.login()

        all_vcs = await self._list_vcs_for_policy(policy_id)
        matches = [
            vc for vc in all_vcs
            if self._credential_subject(vc).get("eventHash") == event_hash
        ]

        def _issued_at(vc: VCDocument) -> str:
            return (
                self._credential_subject(vc).get("issuedAt")
                or vc.get("issuanceDate")
                or ""
            )

        matches.sort(key=_issued_at)

        if history:
            return matches
        if not matches:
            return None

        non_superseded = [
            vc for vc in matches
            if self._credential_subject(vc).get("complianceStatus") != "superseded"
        ]
        return non_superseded[-1] if non_superseded else matches[-1]

    async def get_vc_retrieval_status(
        self,
        policy_id: str,
        event_hash: str,
        *,
        submitted_at: datetime,
    ) -> VCRetrievalStatus:
        """
        Drives SC-007's pending/manual_review state machine.

        - ready(vc) when a VC exists.
        - pending when no VC yet and elapsed < VC_PENDING_THRESHOLD_S.
        - manual_review when no VC yet and elapsed >= VC_MANUAL_REVIEW_CEILING_S.
        - unknown when nothing found and we have no submission record.
        """
        vc = await self.get_vc_by_event_hash(policy_id, event_hash, history=False)
        if vc is not None and not isinstance(vc, list):
            return VCRetrievalStatus(state="ready", vc=vc)

        # No VC yet — compare elapsed wall time against the two thresholds.
        now_wall = datetime.now(timezone.utc)
        elapsed_s = (now_wall - submitted_at).total_seconds()

        if event_hash not in self._submission_times and elapsed_s < 0:
            return VCRetrievalStatus(state="unknown")

        if elapsed_s >= VC_MANUAL_REVIEW_CEILING_S:
            return VCRetrievalStatus(state="manual_review")
        if elapsed_s >= VC_PENDING_THRESHOLD_S:
            # Between 30s and 300s: still pending from the retrieval contract's
            # perspective — tests parametrise the thresholds via module constants.
            return VCRetrievalStatus(state="pending")
        return VCRetrievalStatus(state="pending")

    # --- Schema & policy lifecycle (bootstrap path, used by build scripts) ---

    async def _authed_call(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Shared helper: ensure login, dispatch, classify, record breaker."""
        if self._jwt is None:
            await self.login()
        r = await self._call_with_refresh(method, path, **kwargs)
        err = self._classify(r)
        if err is not None:
            if isinstance(err, (GuardianUnavailable, GuardianToSRequired)):
                self._breaker.record_failure(err)
            raise err
        self._breaker.record_success()
        return r

    async def create_schema(
        self, topic_id: str, schema: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        POST /schemas/{topicId} — sync. MGS responds with the SR's full schema
        list (including the new record). Callers pick their record by matching
        `name` or `uuid`.
        """
        r = await self._authed_call("POST", f"/schemas/{topic_id}", json=schema)
        return r.json()

    async def publish_schema(
        self, schema_id: str, *, version: str = "1.0.0"
    ) -> TaskHandle:
        """
        PUT /schemas/push/{schemaId}/publish — async. Returns a TaskHandle; the
        caller polls completion with `wait_for_task`. MGS requires a
        `{version}` body per VersionSchemaDTO.
        """
        r = await self._authed_call(
            "PUT",
            f"/schemas/push/{schema_id}/publish",
            json={"version": version},
        )
        task_id = r.json().get("taskId")
        if not task_id:
            raise GuardianClientError(
                f"missing taskId in /schemas/push/{schema_id}/publish response"
            )
        return TaskHandle(taskId=task_id)

    async def publish_schema_with_bump(
        self,
        schema_id: str,
        *,
        base_version: str,
        timeout_s: float,
        max_attempts: int = 20,
    ) -> str:
        """Publish a DRAFT schema, walking the patch number up if MGS rejects
        with "Version already exists" — happens when a discontinued policy in
        the SR namespace already published this `<name>@<version>` tuple.

        Returns the version that finally succeeded. Raises RuntimeError on
        non-conflict failure or on hitting `max_attempts` consecutive
        conflicts.
        """
        version = base_version
        for _ in range(max_attempts):
            task = await self.publish_schema(schema_id, version=version)
            result = await self.wait_for_task(task.taskId, timeout=timeout_s)
            if result.status == "COMPLETED":
                return version
            if "already exists" not in (result.error or "").lower():
                raise RuntimeError(f"Schema publish failed: {result.error}")
            major, minor, patch = (version.split(".") + ["0", "0"])[:3]
            version = f"{major}.{minor}.{int(patch) + 1}"
        raise RuntimeError(
            f"Schema publish hit {max_attempts} consecutive 'Version already exists' errors"
        )

    async def create_policy(self, policy: dict[str, Any]) -> list[dict[str, Any]]:
        """
        POST /policies — sync. Returns the SR's full policy list (same shape
        convention as `create_schema`).
        """
        r = await self._authed_call("POST", "/policies", json=policy)
        return r.json()

    async def get_policy(self, policy_id: str) -> dict[str, Any]:
        """GET /policies/{policyId} — fetch the current draft/published config."""
        r = await self._authed_call("GET", f"/policies/{policy_id}")
        return r.json()

    async def update_policy(
        self, policy_id: str, policy: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT /policies/{policyId} — replace the draft configuration."""
        r = await self._authed_call("PUT", f"/policies/{policy_id}", json=policy)
        return r.json()

    async def publish_policy(
        self, policy_id: str, *, policy_version: str = "1.0.0"
    ) -> TaskHandle:
        """
        PUT /policies/push/{policyId}/publish — async. The body carries the
        `policyVersion` label MGS records into the Hedera topic.
        """
        r = await self._authed_call(
            "PUT",
            f"/policies/push/{policy_id}/publish",
            json={"policyVersion": policy_version},
        )
        task_id = r.json().get("taskId")
        if not task_id:
            raise GuardianClientError(
                f"missing taskId in /policies/push/{policy_id}/publish response"
            )
        return TaskHandle(taskId=task_id)

    async def export_policy(self, policy_id: str, out_path: Path) -> Path:
        """
        GET /policies/{policyId}/export/file — returns a zip bundle of the
        published policy + schemas. Written verbatim to `out_path`.
        """
        out_path = Path(out_path)
        r = await self._authed_call("GET", f"/policies/{policy_id}/export/file")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(r.content)
        return out_path

    async def import_policy_file(self, zip_bytes: bytes) -> TaskHandle:
        """
        POST /policies/push/import/file — async. Uploads a `.policy` zip so
        MGS re-creates the policy locally; returns a TaskHandle whose result
        contains the imported policy id.
        """
        r = await self._authed_call(
            "POST",
            "/policies/push/import/file",
            content=zip_bytes,
            headers={"Content-Type": "application/octet-stream"},
        )
        task_id = r.json().get("taskId")
        if not task_id:
            raise GuardianClientError(
                "missing taskId in /policies/push/import/file response"
            )
        return TaskHandle(taskId=task_id)
