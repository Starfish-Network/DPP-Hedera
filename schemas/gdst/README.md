# GDST 1.2 JSON-LD Schemas

This directory is a **GPS deliverable** — do not rename or flatten.

Contains the seven JSON-LD schemas backing the GDST Seafood Traceability policy, one per Critical Tracking Event (CTE):

- `fishing.json`
- `landing.json`
- `transshipment.json`
- `on_vessel.json`
- `processing.json`
- `shipping.json`
- `aggregation.json`

Every schema uses a semver IRI of the form `#GDST<EventType>Event&<MAJOR.MINOR.PATCH>` (see spec §FR-012). Breaking changes bump the major version and publish under a new IRI — never in place.

See [../../specs/001-guardian-integration/data-model.md](../../specs/001-guardian-integration/data-model.md) for the canonical field list and rule table. Schemas here MUST stay in lockstep with the Pydantic models in [../../api/app/models/gdst/](../../api/app/models/gdst/) (Constitution §III).

---

## Guaranteed Fields Contract

This section is the **stability promise** to downstream Guardian projects (Constitution §II). A `GDSTComplianceCredential` VC issued by the Starfish SR will carry every field below with the stated semantics, regardless of CTE type. Downstream `trustChainBlock` filters and `customLogicBlock` expressions can rely on these without inspecting the underlying CTE schema.

The fields live on `credentialSubject` unless noted otherwise. The CTE-specific KDEs (vessel info, catch area, IUU authorizations, etc.) also flow through verbatim per spec §FR-015 — but those are CTE-shape-dependent and not part of this guaranteed contract.

### `eventHash`
- **Type**: `string`, pattern `^0x[0-9a-f]{64}$`.
- **Meaning**: SHA-256 of the canonical (sorted-key) JSON of the submitted event. Equals the `bytes32` value emitted by `ComplianceVerifier.recordEvent()` on Hedera, so a downstream verifier can correlate VC ↔ on-chain event in one lookup.
- **Stability**: `1.x.x` — present on every VC. Format never changes within a major; a v2 hash function would be a major bump (new schema IRI).

### `gdstEventType`
- **Type**: `string`, enum.
- **Values**: `Fishing | Landing | Transshipment | OnVesselProcessing | Processing | Shipping | Aggregation`.
- **Meaning**: Discriminator that tells consumers which GDST CTE produced this VC. Lets downstream filters branch by type without reading the full payload.
- **Stability**: `1.x.x` — the seven values are fixed. Adding a new CTE type to GDST is a minor bump; renaming or removing a value is major.

### `complianceStatus`
- **Type**: `string`, enum.
- **Values**: `compliant | superseded`.
- **Meaning**: `compliant` is the default for any VC issued via the policy's normal flow. `superseded` appears on corrective VCs that replace a prior issuance for the same `eventHash` (FR-014 append-only model). The full chain is retrievable via `GET /guardian/gdst/vc/{eventHash}?history=true`.
- **Stability**: `1.x.x` — these two values are the entire enumeration. v1 has no `revoked` or `pending` value; revocation is out of scope.

### `policyVersion`
- **Type**: `string`, semver.
- **Meaning**: The Guardian-policy version that issued this VC. Lets consumers reason about which compliance ruleset was in effect at issuance time.
- **Stability**: `1.x.x` — string format is semver. The current published policy version is `1.0.0`; a major bump on the policy publishes under a new `policyVersion` value, but the field name and shape are stable.

### `issuedAt`
- **Type**: `string`, ISO-8601 date-time.
- **Meaning**: Server timestamp at the moment the FastAPI mapper stamped the credential subject (just before submission to MGS). May lag the on-chain `recordEvent` timestamp by milliseconds; may lead the downstream Guardian-issuance timestamp by seconds-to-minutes per SC-007.
- **Stability**: `1.x.x` — present on every VC.

### `supersedes` (conditional)
- **Type**: `string`, pattern `^0x[0-9a-f]{64}$`.
- **Presence**: only when `complianceStatus == "superseded"`. Absent on initial issuances.
- **Meaning**: The `eventHash` of the prior VC this one replaces. Downstream consumers that want the latest authoritative VC for a given event resolve the chain by walking `supersedes` references.
- **Stability**: `1.x.x` — name, format, and conditional-presence rule are fixed.

### `species` (GDST-specific)
- **Type**: `string`, pattern `^[A-Z]{3}$`.
- **Meaning**: FAO ASFIS three-letter species code (e.g., `TUN` for tuna). Hoisted to the top level of `credentialSubject` from the source event's `what.species` so downstream species-restricted filters don't need to walk into the per-CTE shape.
- **Stability**: `1.x.x` — present on every GDST VC. The FSMA mirror has `fsma204EventType` only; the species field is GDST-only.

---

## Per-CTE KDEs (flow through verbatim)

Beyond the guaranteed fields above, the full submitted event payload flows into `credentialSubject` verbatim per FR-015. Downstream consumers MAY inspect these but MUST NOT depend on a particular field being present across CTE types. Examples:

| Field | Where it appears | Notes |
|-------|-------------------|-------|
| `vessel.vessel_id` | Fishing, Transshipment | Required for those CTEs by `gdst_min_rules` |
| `iuu.fishing_authorization` | Fishing | IUU compliance evidence |
| `iuu.landing_authorization` | Landing | |
| `iuu.transshipment_authorization` | Transshipment | |
| `where.catch_area` | Fishing | FAO area code, e.g. `FAO71` |
| `where.event_read_point.{latitude,longitude}` | Fishing, On-vessel | GPS at capture |
| `when.production_date` | Processing, On-vessel | |
| `what.linking_kde` | Shipping | Connects shipping to the catch chain |
| `parent_items` / `child_items` | Aggregation | One of the two MUST be non-empty |

The complete CTE-by-CTE field list is in [data-model.md §1 Entities](../../specs/001-guardian-integration/data-model.md) and the per-CTE JSON-LD schemas in this directory.

---

## Trust Anchor

VCs are issued by the Starfish Standard Registry DID. For testnet: `did:hedera:testnet:3xGAGt5EkLtUkqZ663wbAWhcSALyZywmx7hrkB7v2Mvg_0.0.8739126` (also documented at [../../docs/guardian-integration/README.md](../../docs/guardian-integration/README.md) §Testnet Integration Facts). Mainnet DID is published when mainnet rolls out.

Downstream `trustChainBlock` and `customLogicBlock` filters anchor on `vc.issuer == <SR DID>` plus `vc.credentialSubject.complianceStatus == "compliant"` — see [../../samples/downstream/carbon-credit-demo.policy.json](../../samples/downstream/carbon-credit-demo.policy.json) for a reference downstream consumer.
