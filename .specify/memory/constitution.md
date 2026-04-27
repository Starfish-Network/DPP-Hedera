# DPP-Hedera Constitution

> Governing principles for spec-driven development of the Guardian integration and related compliance work in the DPP-Hedera project. Derived from the existing design notes in [docs/guardian-integration/README.md](../../docs/guardian-integration/README.md) and repo conventions in [README.md](../../README.md).

## Core Principles

### I. Policies Are The Product

The primary deliverable of the Guardian integration is the pair of exportable `.policy` files (`gdst-seafood-traceability.policy`, `fsma-204-food-safety.policy`) together with their versioned JSON-LD schemas. The FastAPI integration is how **we** use them; any Guardian project must be able to import the exports and run the compliance checks without any Starfish-specific code, config, or network dependency. Spec and plan artifacts MUST treat policy/schema exports as first-class, not as a byproduct of backend work.

### II. Composable By Design

Schemas are versioned with IRIs of the form `#<EventType>&<semver>` and are self-contained. VCs carry a semantic type (`GDSTComplianceCredential`, `FSMA204ComplianceCredential`) and enough `credentialSubject` fields for downstream policies to decide without calling our API. The Standard Registry DID is the stable trust anchor. Breaking schema changes require a new version; existing versions remain resolvable. Any proposal that couples our policies to private infrastructure, unversioned schemas, or opaque VC payloads is rejected at plan review.

### III. Dual Compliance Logic Is Intentional

Compliance rules live primarily in `api/app/helpers/compliance.py` for fast rejection at the FastAPI boundary; ideally they are *also* encoded in the Guardian policy as compliance blocks for auditable in-policy enforcement. The Pydantic rules and the rule list in `data-model.md` are the canonical source of truth — any change to either MUST be reflected in the other, verified by the shared test fixture set under `api/app/tests/fixtures/guardian/`. Removing the FastAPI pre-check to "simplify" is a violation.

**v1 exemption (2026-04-27, ratified at v0.2.0)**: the GDST and FSMA Guardian policies built by `scripts/build_*_policy.py` ship with a single envelope-intake schema (`GDSTComplianceIntake` / `FSMA204ComplianceIntake`) and **no per-rule compliance blocks**. Rule enforcement lives in `gdst_min_rules()` / `fsma_min_rules()` only; the Guardian policy is the issuer, not the validator. The trust anchor for a `compliant`-status VC is (a) the SR DID as issuer and (b) the FastAPI pre-check having admitted the event. Re-introducing per-rule Guardian compliance blocks is tracked under v2 and will restore in-policy auditability. This exemption applies to v1 only.

### IV. Core Flows Never Block On Guardian

Hedera Consensus Service (HCS) submission and the `ComplianceVerifier` smart-contract flow are the authoritative chain of custody. Guardian is the compliance-VC layer on top. If Guardian is unreachable, the client opens a circuit breaker for 60 seconds after 3 consecutive failures and event recording continues uninterrupted; the operation is logged for reconciliation but is not retried inline. Plans that introduce synchronous Guardian dependencies on the hot path are rejected. Async retries and backfill for skipped events are acceptable and MUST be specified when the circuit breaker opens.

### V. Test-First For Integration Boundaries (NON-NEGOTIABLE)

Every Guardian-facing module (`guardian_client.py`, `schema_mapper.py`, each `/api/guardian/*` route) lands with contract tests that execute against a recorded or mocked MGS response before the production implementation is merged. Every compliance rule in `data-model.md` has a matching pytest acceptance test named after the rule. The existing unit-test pattern under [api/app/tests/unit/](../../api/app/tests/unit/) is the baseline; Guardian work adds `api/app/tests/integration/guardian/` but does not replace or duplicate the existing suites.

### VI. Authoritative Contracts Over Prose

Behavior that crosses a process boundary MUST be captured in a machine-readable contract: OpenAPI for HTTP, JSON Schema for documents, typed Python signatures for the client. Descriptive tables and prose in existing docs are sources but not contracts; once a behavior is in prose and in an OpenAPI/JSON Schema file, the schema is canonical and the prose links to it. Contracts live under `specs/NNN-*/contracts/`.

## Technology Baseline

- **Language:** Python 3.11 (repo standard; matches `api/` runtime).
- **Framework:** FastAPI + Pydantic v2 for all HTTP and data-modeling work.
- **Tests:** pytest with the existing `conftest.py` fixtures in [api/app/tests/conftest.py](../../api/app/tests/conftest.py). Mock HTTP with `respx` or `httpx_mock` (pick one per feature and record the choice in `research.md`).
- **Guardian runtime:** Managed Guardian Service (MGS) — a Hedera-managed multi-tenant Guardian instance. No self-hosted Guardian, MongoDB, IPFS, or Hedera operator to manage on our side. `.policy` exports MUST still run on self-hosted Guardian.
- **Hedera network:** Testnet for development, Mainnet for production. Test and mainnet DIDs are distinct; a single env MUST NOT mix them.
- **VC format:** W3C Verifiable Credentials Data Model v1 (`https://www.w3.org/2018/credentials/v1`), signed with the SR's Hedera DID as issuer.

## Development Workflow

1. **Specify → Plan → Tasks → Implement.** Features follow the spec-kit flow. No code before `spec.md` is approved and `tasks.md` exists. `/speckit-analyze` must pass before `/speckit-implement` runs.
2. **Constitution check at plan time.** Every `plan.md` includes a Constitution Check gate before Phase 0 research and again after Phase 1 design; violations must be justified in `Complexity Tracking` or the plan is rewritten.
3. **Fixtures are shared.** Sample events under `samples/gdst/` and `samples/fsma/` (referenced by [docs/guardian-integration/03-gps-submission.md](../../docs/guardian-integration/03-gps-submission.md)) and integration fixtures under `api/app/tests/fixtures/guardian/` are the same files — one source of truth.
4. **Compliance rules change in lockstep.** A PR that touches `gdst_min_rules()` or `fsma_min_rules()` in `api/app/helpers/compliance.py` must also update the matching policy's compliance-check block and the rule table in `data-model.md`. Reviewer rejects any PR that touches only one side.
5. **Docs decay into specs.** The numbered tutorial files in [docs/guardian-integration/](../../docs/guardian-integration/) are kept until their content is represented in `specs/001-guardian-integration/`, then replaced with short stubs that link to the spec. Do not maintain two copies.

## Open Decisions (Deferred To Research)

These are called out so they are not quietly assumed during planning. Each MUST be resolved in `research.md` before `tasks.md` is generated.

- **Testnet vs prod tenant strategy.** Separate MGS tenants? Same tenant with environment-tagged policies? Recorded in `research.md` section "Environment Topology."
- **DID key rotation.** How the SR and operator DIDs are rotated without invalidating previously issued VCs. Recorded in `research.md` section "Identity Lifecycle."
- **Circuit-breaker failure taxonomy.** Which MGS error classes count as "failure" for the 3-strikes rule (5xx? 429? network timeout? 451 ToS?) and which are fatal. Recorded in `research.md` section "Resilience."
- **Policy version pinning.** How the FastAPI client pins to a specific published policy version and how it upgrades. Recorded in `research.md` section "Versioning."

## Governance

This constitution supersedes ad-hoc preferences. Amendments require: (a) a PR editing this file, (b) a one-sentence rationale in the PR description, (c) bumping the version below. Breaking amendments (removing or weakening a core principle) require a migration note in the PR describing how in-flight specs should adapt.

**Version**: 0.2.0 | **Ratified**: 2026-04-20 | **Last Amended**: 2026-04-27

**Amendment log**:

- **0.2.0 (2026-04-27)** — Weakening of §III: documented v1 exemption acknowledging that the shipped GDST policy (and the FSMA policy built by the same `scripts/build_*_policy.py` flow) issue VCs against an envelope-intake schema with no per-rule Guardian compliance blocks. Migration: in-flight spec `001-guardian-integration` updated FR-002 and FR-003 to reflect the simplified topology; T037 task text already documents the deviation. v2 will restore in-policy enforcement.
