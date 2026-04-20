# Research: Guardian Integration

**Feature**: `001-guardian-integration` | **Date**: 2026-04-20

Resolves the four open decisions flagged in [the constitution](../../.specify/memory/constitution.md#open-decisions-deferred-to-research) plus two implementation-level library choices.

---

## 1. Environment Topology (testnet vs prod tenant)

**Decision**: Two MGS tenants — one testnet, one mainnet — with identical policy tags but independent SR DIDs. A single env variable `GUARDIAN_NETWORK ∈ {testnet, mainnet}` selects which tenant's base URL, SR credentials, and policy IDs are loaded from settings.

**Alternatives considered**:

- *Single tenant, environment-tagged policies*. Rejected: MGS does not namespace policies by environment in the free tier, and one compromised testnet key would expose production VCs.
- *Self-hosted Guardian for testing, MGS only in prod*. Rejected: it drifts the runtime from production and defeats the purpose of using MGS.

**Consequences**: Operators registered on testnet have distinct DIDs from mainnet. Reconciliation tooling must not cross networks. Config layer enforces this with a single `GUARDIAN_NETWORK` key.

## 2. Identity Lifecycle (DID key rotation)

**Decision**: The SR DID is **not** rotated. Key rotation for operators is supported via `PUT /profiles/{username}` with new Hedera credentials; the operator's DID string remains stable because Hedera DIDs resolve by DID document, not by raw key. VCs issued before rotation remain valid because the VC's `proof` references the SR key at issuance time.

**Alternatives considered**:

- *Rotate the SR key annually*. Rejected for v1: rotating the SR would require either re-issuing every past VC (impractical) or maintaining a key history in the DID document (Guardian's support for this is unproven on MGS). Deferred to v2 when we have production traffic and can evaluate risk.
- *Separate per-policy SRs*. Rejected: increases operational complexity without a clear threat-model benefit.

**Consequences**: SR credentials are treated as long-lived production secrets. They live in the secret manager only (never in `.env`), and access is audited.

## 3. Resilience (circuit-breaker failure taxonomy)

**Decision**: Only these MGS responses count as a "failure" for the 3-strikes counter:

| Condition | Counts? | Reason |
|-----------|---------|--------|
| Network error / timeout | Yes | Transient infra; skip window is appropriate. |
| HTTP `5xx` | Yes | Server-side fault; transient. |
| HTTP `429` | Yes, but with separate backoff | Rate-limit; use `Retry-After` if present, ignore for breaker. |
| HTTP `503` | Yes | Covered by 5xx. |
| HTTP `451` (ToS not accepted) | **No** | Config/onboarding problem; retrying helps nothing. Surfaced as `tos_required` via `/guardian/health` and escalated. |
| HTTP `4xx` other than `429`/`451` (e.g., `400`, `404`, `409`) | **No** | Per-request client-side fault; does not indicate MGS is down. |
| `2xx` | Resets counter | Success. |

Breaker opens after 3 consecutive "Yes" responses; stays open 60 s; next call after 60 s is a probe — success closes the breaker, failure resets the 60 s window (one failure, not another three).

**Alternatives considered**:

- *Exponential backoff instead of a fixed 60 s window*. Rejected for v1: fixed window is simpler and the constitution already specifies 60 s. Revisit if production data shows MGS outages cluster longer.
- *Queue skipped submissions for automatic retry*. **Rejected for v1** (spec.md Clarifications Q2 / FR-006). Skipped events emit a structured WARN log with `{event_hash, operator_did, mgs_error_class, breaker_opened_at}`; re-submission is manual via the idempotent `/events` call. A reconciliation worker remains a possible v2 feature but is not scheduled.

**Consequences**: `guardian_client` exposes `circuit_status()` returning one of `{closed, open, half_open, tos_required}`. `/guardian/health` surfaces this. `tos_required` is a distinct operational state, not a retry problem.

## 4. Versioning (policy version pinning)

**Decision**: The FastAPI client pins to a specific *published* policy version by MGS `policyId`. `GUARDIAN_GDST_POLICY_ID` and `GUARDIAN_FSMA_POLICY_ID` are env-scoped config values. The `blockTag` for the external-data intake block is also pinned via config (`GUARDIAN_GDST_INTAKE_BLOCK_TAG`, `GUARDIAN_FSMA_INTAKE_BLOCK_TAG`) because block tags are stable per published policy version.

Schema IRIs are semver (`#GDSTFishingEvent&1.0.0`); breaking changes bump the major version and get a new policy version. Upgrade path: publish new policy version → update `*_POLICY_ID` + `*_INTAKE_BLOCK_TAG` in config → deploy. No dual-write during cutover for v1.

**Alternatives considered**:

- *Discover the latest policy version at startup*. Rejected: non-deterministic behavior; a silent upstream policy edit would change compliance semantics without code review.
- *Dual-write to old and new during cutover*. Deferred: adds complexity, no production traffic yet.

**Consequences**: Policy upgrades are deployments, not runtime changes. The `quickstart.md` records how to re-pin.

---

## 5. Library Choice — Circuit Breaker

**Decision**: Hand-rolled implementation in `guardian_client.py`. The state machine is trivial (closed/open/half-open + a counter + a timestamp) and our failure taxonomy (§3) doesn't match the default rules of any off-the-shelf library. Implementation lives next to the client so tests can freeze the clock without monkey-patching a third-party module.

**Alternatives considered**:

- `pybreaker`: mature but heavier; its exception-based fail detection doesn't cleanly handle our "which HTTP codes count" rule.
- `tenacity`: retry library, not breaker. Useful for the task-polling loop (§7) but wrong tool for the core breaker.

## 6. Library Choice — HTTP Mocking In Tests

**Decision**: `respx`. Integrates cleanly with `httpx.AsyncClient` (which we'll use for MGS), supports record/replay for the MGS OpenAPI fixtures, and is already the most common choice in the FastAPI ecosystem.

**Alternatives considered**:

- `httpx_mock`: simpler API but weaker matching (no URL-pattern wildcards with path params); would force per-test hand-wiring.
- `responses` + `requests`: would require adopting sync `requests` for the MGS client, contradicting the async FastAPI stack.

## 7. Task Polling (async MGS operations)

**Decision**: `guardian_client.wait_for_task(task_id)` uses `tenacity` with exponential backoff (initial 500 ms, factor 2, cap 8 s) and a global timeout of 120 s per task. This is distinct from the circuit breaker: task polling is a well-defined retry loop for one async operation, not a resilience boundary between subsystems. Timeout exhaustion raises `GuardianTaskTimeout` and surfaces as `503` from the calling FastAPI endpoint.

**Alternatives considered**:

- Hand-rolled sleep loop: rejected; retry libraries handle jitter, capping, and cancellation correctly.

---

## Open items left for `/speckit-tasks`

- Exact test matrix — one acceptance test per rule in `data-model.md` §Rule Source Table.
- Ordering of schema publish, policy publish, and policy export steps in the bootstrap script.
