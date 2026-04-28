# FSMA 204 JSON-LD Schemas

This directory is a **GPS deliverable** — do not rename or flatten.

Contains the six JSON-LD schemas backing the FSMA 204 Food Safety policy, one per event type on the Food Traceability List:

- `creating.json`
- `shipping.json`
- `receiving.json`
- `transforming.json`
- `packing.json`
- `unpacking.json`

Every schema uses a semver IRI of the form `#FSMA204<EventType>Event&<MAJOR.MINOR.PATCH>` (see spec §FR-012). Breaking changes bump the major version and publish under a new IRI — never in place.

See [../../specs/001-guardian-integration/data-model.md](../../specs/001-guardian-integration/data-model.md) for the canonical field list and rule table. Schemas here MUST stay in lockstep with the Pydantic models in [../../api/app/models/starfish_events.py](../../api/app/models/starfish_events.py) (Constitution §III).

---

## Guaranteed Fields Contract

This section is the **stability promise** to downstream Guardian projects (Constitution §II). An `FSMA204ComplianceCredential` VC issued by the Starfish SR will carry every field below with the stated semantics, regardless of event type. Downstream `trustChainBlock` filters and `customLogicBlock` expressions can rely on these without inspecting the underlying event-type schema.

The fields live on `credentialSubject` unless noted otherwise. The event-type-specific KDEs (`biz_location`, `ship_from` / `ship_to`, `facility`, `container_id`, `input_items` / `output_items`, etc.) also flow through verbatim per spec §FR-015 — but those are event-shape-dependent and not part of this guaranteed contract.

### `eventHash`
- **Type**: `string`, pattern `^0x[0-9a-f]{64}$`.
- **Meaning**: SHA-256 of the canonical (sorted-key) JSON of the submitted event. Equals the `bytes32` value emitted by `ComplianceVerifier.recordEvent()` on Hedera, so a downstream verifier can correlate VC ↔ on-chain event in one lookup.
- **Stability**: `1.x.x` — present on every VC. Format never changes within a major; a v2 hash function would be a major bump (new schema IRI).

### `fsma204EventType`
- **Type**: `string`, enum.
- **Values**: `creating | shipping | receiving | transforming | packing | unpacking` (all lowercase — matches the `eventType` discriminator on the source FSMA event Pydantic model).
- **Meaning**: Discriminator that tells consumers which FSMA 204 Critical Tracking Event produced this VC. Lets downstream filters branch by type without reading the full payload.
- **Stability**: `1.x.x` — the six values are fixed. Adding a new FSMA event type to the Food Traceability List is a minor bump; renaming or removing a value is major.

### `complianceStatus`
- **Type**: `string`, enum.
- **Values**: `compliant | superseded`.
- **Meaning**: `compliant` is the default for any VC issued via the policy's normal flow. `superseded` appears on corrective VCs that replace a prior issuance for the same `eventHash` (FR-014 append-only model). The full chain is retrievable via `GET /guardian/fsma/vc/{eventHash}?history=true`.
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

> Note: FSMA VCs do not carry a `species` field — that's a GDST-only Guaranteed extension. The FSMA branch's only type-specific Guaranteed addition over `GuaranteedMetadata` is `fsma204EventType` itself.

---

## Per-event-type KDEs (flow through verbatim)

Beyond the guaranteed fields above, the full submitted event payload flows into `credentialSubject` verbatim per FR-015. Downstream consumers MAY inspect these but MUST NOT depend on a particular field being present across event types. Examples:

| Field | Where it appears | Notes |
|-------|-------------------|-------|
| `biz_location` | Creating | GLN of the production location |
| `quantity_list` | Creating | `[{epc, quantity, unit_of_measurement}]`, non-empty |
| `ship_from` / `ship_to` | Shipping | GLNs of origin / destination |
| `items` | Shipping, Receiving | Lot-level quantity items |
| `shipped_from` | Receiving | Counterparty origin GLN |
| `received_at` | Receiving | Receiving location GLN |
| `facility` | Transforming, Packing, Unpacking | GLN of the transformation / packing facility |
| `transformation_id` | Transforming | Optional traceability identifier |
| `input_items` | Transforming, Packing | Materials going in |
| `output_items` | Transforming, Unpacking | Products coming out |
| `container_id` | Packing, Unpacking | Container the lot is packed into / out of |
| `event_time`, `event_timezone_offset` | All | Common timestamp fields |

The complete event-by-event field list is in [data-model.md §1 Entities](../../specs/001-guardian-integration/data-model.md) and the per-event JSON-LD schemas in this directory.

---

## Trust Anchor

VCs are issued by the Starfish Standard Registry DID. For testnet: `did:hedera:testnet:3xGAGt5EkLtUkqZ663wbAWhcSALyZywmx7hrkB7v2Mvg_0.0.8739126` (also documented at [../../docs/guardian-integration/README.md](../../docs/guardian-integration/README.md) §Testnet Integration Facts). Mainnet DID is published when mainnet rolls out.

Downstream `trustChainBlock` and `customLogicBlock` filters anchor on `vc.issuer == <SR DID>` plus `vc.credentialSubject.complianceStatus == "compliant"` — see [../../samples/downstream/carbon-credit-demo.policy.json](../../samples/downstream/carbon-credit-demo.policy.json) for a reference downstream consumer (the demo is GDST-keyed but the pattern is identical for FSMA: replace the schema reference and the `fsma204EventType` filter as needed).
