# Data Model: Guardian Integration

**Feature**: `001-guardian-integration` | **Date**: 2026-04-20

Single source of truth for entity definitions, per-event-type compliance rules, and schema provenance. The Pydantic pre-check in `api/app/helpers/compliance.py` and the Guardian policy blocks MUST match the Rule Source Table below (Constitution §III).

---

## 1. Entities

### GDST Critical Tracking Event (CTE)

Seven event types, all sharing `GDSTEvent` base fields.

| Field group | Base model | Fields |
|-------------|-----------|--------|
| `who` | `OwnershipInfo` | `product_owner`, `information_provider` |
| `what` | `ProductInfo` | `species` (`^[A-Z]{3}$`), `product_form`, `item_sku_upc_gtin` (GTIN pattern), `linking_kde`, `quantity` (`> 0`), `unit_of_measure` (`KGM|TNE|LBR|EA`) |
| `where` | `LocationInfo` | `catch_area` (`^FAO\d{2,3}$`), `event_read_point.{latitude,longitude}`, `product_origin` |
| `when` | `EventTiming` | `event_id` (6–64 chars), `event_datetime` (ISO 8601), `capture_date`, `production_date` |
| `iuu` | `IUUInfo` | `fishing_authorization`, `landing_authorization`, `transshipment_authorization`, `gear_type`, `production_method`, `harvest_certification` |
| event-specific | varies | see §3 Schema Map |

Source models: `api/app/models/gdst/{base,fishing,landing,transshipment,on_vessel,processing,shipping,aggregation}.py`.

### FSMA Event

Six event types, all sharing `event_time: datetime`.

Source model: `api/app/models/starfish_events.py`.

### Verifiable Credential (VC)

W3C VC v1 with DPP-Hedera-specific `credentialSubject` fields.

- **Envelope**: `@context: https://www.w3.org/2018/credentials/v1`, `issuer: <SR DID>`, `issuanceDate`, `proof: Ed25519Signature2018`.
- **Type**: `["VerifiableCredential", "GDSTComplianceCredential"]` or `["VerifiableCredential", "FSMA204ComplianceCredential"]`.
- **`credentialSubject` shape**: embeds the **full submitted event payload verbatim** (all KDEs on the source event) plus the Guaranteed metadata fields below (spec §FR-015). The canonical JSON-schema description is [contracts/vc-output.schema.json](contracts/vc-output.schema.json).
- **Guaranteed metadata fields** (downstream-policy contract, Constitution §II — every VC carries these regardless of event type):

| Field | Type | Notes |
|-------|------|-------|
| `eventHash` | `0x` + 64 hex | Equals the `bytes32` emitted by `ComplianceVerifier.recordEvent()` |
| `complianceStatus` | enum `compliant \| superseded` | `superseded` only on corrective VCs (FR-014) |
| `policyVersion` | semver | The Guardian policy version that issued this VC (FR-012) |
| `issuedAt` | ISO 8601 date-time | Guardian-issuance timestamp, may lag `submitted_at` by up to 5 min (SC-007) |
| `supersedes` | `0x` + 64 hex (conditional) | Required iff `complianceStatus == "superseded"`; references the prior VC's `eventHash` |
| `gdstEventType` or `fsma204EventType` | enum | Discriminator — drives the Pydantic/schema match on read |

- **Per-type additional Guaranteed fields**:

| Type | Extra Guaranteed |
|------|------------------|
| `GDSTComplianceCredential` | `species` (`^[A-Z]{3}$`). Additional KDEs (`catchArea`, `fishingAuthorization`, `vesselId`, `landingAuthorization`, `transshipmentAuthorization`, …) flow through as part of the full event payload but are not required on every event type |
| `FSMA204ComplianceCredential` | (none beyond the base); all KDEs (`facility`, `shipFrom`, `shipTo`, quantity lists, …) flow through as part of the full event payload |

- **`eventHash` equivalence**: MUST equal the `bytes32` emitted by `ComplianceVerifier.recordEvent()` for the same event.
- **Immutability (FR-014)**: once issued, a VC is never mutated or deleted. A correction is a **new** VC of the same type carrying `complianceStatus = "superseded"` and `supersedes = <prior eventHash>`. The chain `[oldest, …, latest]` is retrievable via `GET /guardian/*/vc/{event_hash}?history=true` (FR-007).
- **Idempotency (FR-004)**: exactly one "latest" VC exists per `eventHash` at any time. Duplicate `/events` submissions short-circuit to the existing VC without calling MGS.

### Standard Registry (SR)

One SR DID per environment (testnet, mainnet). Owns both policies. Issues all VCs. Key rotation policy: see [research.md §2](research.md).

### Operator

Guardian `User` role mapped from Starfish `operator` role. Has its own Hedera DID. In **v1**, operators are pre-provisioned directly in the MGS portal by the deployer before any event is submitted — there are no Starfish API calls for onboarding (spec §FR-007 / Assumptions). The operator's DID, once activated in the portal, is what Starfish references when submitting events on their behalf. v2 will add self-service endpoints.

**Consent record (v1, out-of-band)**: The FR-015 disclosure acknowledgement is captured **outside the Starfish API** by the deployer before the operator is provisioned in the MGS portal. Concretely, the deployer retains a signed local record (e.g., a counter-signed PDF or an entry in a secured consent log keyed on the operator's DID) containing the acknowledgement text and an ISO-8601 timestamp. Starfish runs no consent API, stores no consent field, and makes no programmatic assertion that consent was captured — this is a deployment-runbook obligation. If consent capture needs to become programmatic, it will be added in v2 alongside the operator-onboarding endpoints.

### Policy Registry (`PolicyConfig`)

In-process registry of the compliance policies Starfish forwards events to. Populated at import time in `api/app/service/guardian_policies.py`; keyed by `slug`. Rationale and alternatives are recorded in [research.md §8](research.md).

| Field | Type | Notes |
|-------|------|-------|
| `slug` | `str` | URL segment for `/guardian/{slug}/vc/{event_hash}`; also the directory name under `schemas/` and `samples/`. Stable. |
| `policy_id` | `str \| None` | MGS `policyId` of the published policy. Sourced from `settings.GUARDIAN_<SLUG>_POLICY_ID`. `None` ⇒ policy is not configured in this deployment. |
| `intake_block_tag` | `str \| None` | External-data intake block tag for `POST /external/{policyId}/{blockTag}`. Sourced from `settings.GUARDIAN_<SLUG>_INTAKE_BLOCK_TAG`. |
| `policy_version` | semver `str` | Guardian-policy semver mirrored into `credentialSubject.policyVersion` (FR-012). Bumped in lockstep with policy-publish events. |
| `source_type_field` | `str` | Field name on the submitted event dict used for per-policy dispatch. Pairs of policies MUST NOT share this value. **Current v1 values**: GDST → `gdst_event_type` (snake_case, matches `models/gdst/*::GDSTEvent`); FSMA → `eventType` (camelCase, matches `models/starfish_events.py::*Event` — historical convention from the pre-Guardian compliance route). The naming asymmetry is documented; v2 plans to rename the FSMA model field to `fsma204_event_type` for symmetry once a model migration window is scheduled. |
| `vc_type_field` | `str` | Field name the mapper writes into `credentialSubject` as the VC-side discriminator (`gdstEventType`, `fsma204EventType`). Pairs of policies MUST NOT share this value. |
| `type_map` | `dict[str, str]` | Normalises source labels to VC labels (e.g. `"ShippingReceiving" → "Shipping"`). Empty dict ⇒ passthrough. |
| `required_hoists` | `tuple[(str, str), ...]` | Subject-key → dotted-source-path pairs that must be hoisted to the top level of `credentialSubject` to satisfy the VC schema's `required` list (e.g. GDST: `("species", "what.species")`). |
| `enabled` (property) | `bool` | Shorthand for `policy_id is not None and intake_block_tag is not None`. The `/events` hot path skips Guardian forwarding (not an error) when `False`. |

**Invariants** (Constitution §II — composability):

- Dispatch is unambiguous: for any two registered policies, `source_type_field` values differ. Enforced at registry-construction time.
- Downstream trust-chain filters on `vc_type_field`, so that field is likewise unique across the registry.
- `policy_version` matches the semver recorded on the most recent policy-publish event in MGS. Verified by the build script (`scripts/build_<slug>_policy.py`).

**Lifecycle**:

- Read from settings at import (process lifetime). Rotating `GUARDIAN_<SLUG>_POLICY_ID` requires a process restart — matches the pre-registry behaviour.
- Adding a new policy: (1) add a `PolicyConfig` entry to `POLICIES`; (2) add the matching env keys to `config.py`; (3) land schemas under `schemas/<slug>/`. No edits to `schema_mapper.py`, `policy.py`, or `events.py` beyond the existing generic paths.

---

## 2. Rule Source Table

Canonical list of compliance rules. Each row is enforced in THREE places: Pydantic pre-check, Guardian policy block, and a pytest acceptance test. The three MUST match.

### GDST — common (applies to all CTE types)

| Rule ID | Rule | Pydantic source | Policy block | Acceptance test |
|---------|------|-----------------|--------------|-----------------|
| `GDST_COMMON_001` | `when.event_datetime` present | `gdst_min_rules()` | schema `required` + compliance block | `test_gdst_acceptance.py::test_common_event_datetime_required` |
| `GDST_COMMON_002` | `what.species` matches `^[A-Z]{3}$` | `constraints.FAOASFISCode` | schema `pattern` | `test_gdst_acceptance.py::test_common_species_format` |
| `GDST_COMMON_003` | `what.quantity > 0` | `gdst_min_rules()` | schema `minimum` | `test_gdst_acceptance.py::test_common_quantity_positive` |
| `GDST_COMMON_004` | `what.unit_of_measure ∈ {KGM, TNE, LBR, EA}` | `constraints.UNECE_UOM` | schema `enum` | `test_gdst_acceptance.py::test_common_uom_enum` |

### GDST — per-event-type

| Rule ID | Event | Rule | Pydantic source | Policy block | Acceptance test |
|---------|-------|------|-----------------|--------------|-----------------|
| `GDST_FISHING_001` | Fishing | `vessel.vessel_id` OR `vessel.vessel_name` present | `gdst_min_rules()` | schema anyOf + block | `test_fishing_vessel_identification` |
| `GDST_FISHING_002` | Fishing | `iuu.fishing_authorization` present | `gdst_min_rules()` | schema `required` | `test_fishing_authorization_required` |
| `GDST_FISHING_003` | Fishing | `where.catch_area` OR `where.event_read_point` present | `gdst_min_rules()` | block anyOf | `test_fishing_location_required` |
| `GDST_ONVESSEL_001` | OnVesselProcessing | `when.production_date` present | `gdst_min_rules()` | schema `required` | `test_on_vessel_production_date_required` |
| `GDST_TRANSSHIP_001` | Transshipment | `transshipment_vessel.{vessel_id\|vessel_name}` | `gdst_min_rules()` | schema anyOf | `test_transshipment_vessel_identification` |
| `GDST_TRANSSHIP_002` | Transshipment | `iuu.transshipment_authorization` | `gdst_min_rules()` | schema `required` | `test_transshipment_authorization_required` |
| `GDST_LANDING_001` | Landing | `iuu.landing_authorization` | `gdst_min_rules()` | schema `required` | `test_landing_authorization_required` |
| `GDST_SHIPPING_001` | Shipping | `where.{source\|destination}` present | `gdst_min_rules()` | block anyOf | `test_shipping_endpoints_required` |
| `GDST_SHIPPING_002` | Shipping | `what.linking_kde` present | `gdst_min_rules()` | schema `required` | `test_shipping_linking_kde_required` |
| `GDST_PROCESSING_001` | Processing | `when.production_date` present | `gdst_min_rules()` | schema `required` | `test_processing_production_date_required` |
| `GDST_AGGREGATION_001` | Aggregation | `parent_items` OR `child_items` non-empty | `gdst_min_rules()` | block anyOf | `test_aggregation_non_empty` |

### FSMA — common

| Rule ID | Rule | Pydantic source | Policy block | Acceptance test |
|---------|------|-----------------|--------------|-----------------|
| `FSMA_COMMON_001` | `event_time` present | `fsma_min_rules()` | schema `required` | `test_fsma_acceptance.py::test_common_event_time_required` |

### FSMA — per-event-type

| Rule ID | Event | Rule | Pydantic source | Policy block | Acceptance test |
|---------|-------|------|-----------------|--------------|-----------------|
| `FSMA_CREATING_001` | Creating | `biz_location` present | `fsma_min_rules()` | schema `required` | `test_creating_biz_location_required` |
| `FSMA_CREATING_002` | Creating | `quantity_list` non-empty | `fsma_min_rules()` | schema `minItems: 1` | `test_creating_quantity_list_non_empty` |
| `FSMA_SHIPPING_001` | Shipping | `ship_from` present | `fsma_min_rules()` | schema `required` | `test_shipping_ship_from_required` |
| `FSMA_SHIPPING_002` | Shipping | `ship_to` present | `fsma_min_rules()` | schema `required` | `test_shipping_ship_to_required` |
| `FSMA_SHIPPING_003` | Shipping | `items` non-empty | `fsma_min_rules()` | schema `minItems: 1` | `test_shipping_items_non_empty` |
| `FSMA_RECEIVING_001` | Receiving | `received_at` OR `ship_to` present | `fsma_min_rules()` | block anyOf | `test_receiving_location_required` |
| `FSMA_RECEIVING_002` | Receiving | `items` non-empty | `fsma_min_rules()` | schema `minItems: 1` | `test_receiving_items_non_empty` |
| `FSMA_TRANSFORMING_001` | Transforming | `facility` present | `fsma_min_rules()` | schema `required` | `test_transforming_facility_required` |
| `FSMA_TRANSFORMING_002` | Transforming | `input_items` non-empty | `fsma_min_rules()` | schema `minItems: 1` | `test_transforming_inputs_non_empty` |
| `FSMA_TRANSFORMING_003` | Transforming | `output_items` non-empty | `fsma_min_rules()` | schema `minItems: 1` | `test_transforming_outputs_non_empty` |
| `FSMA_PACKING_001` | Packing | `facility` present | `fsma_min_rules()` | schema `required` | `test_packing_facility_required` |
| `FSMA_PACKING_002` | Packing | `container_id` present | `fsma_min_rules()` | schema `required` | `test_packing_container_id_required` |
| `FSMA_PACKING_003` | Packing | `input_items` non-empty | `fsma_min_rules()` | schema `minItems: 1` | `test_packing_inputs_non_empty` |
| `FSMA_UNPACKING_001` | Unpacking | `facility` present | `fsma_min_rules()` | schema `required` | `test_unpacking_facility_required` |
| `FSMA_UNPACKING_002` | Unpacking | `container_id` present | `fsma_min_rules()` | schema `required` | `test_unpacking_container_id_required` |
| `FSMA_UNPACKING_003` | Unpacking | `output_items` non-empty | `fsma_min_rules()` | schema `minItems: 1` | `test_unpacking_outputs_non_empty` |

---

## 3. Schema Map

| Schema file | Source Pydantic model | Schema IRI (initial) |
|-------------|----------------------|----------------------|
| `schemas/gdst/fishing.json` | `api/app/models/gdst/fishing.py::FishingEvent` | `#GDSTFishingEvent&1.0.0` |
| `schemas/gdst/landing.json` | `api/app/models/gdst/landing.py::LandingEvent` | `#GDSTLandingEvent&1.0.0` |
| `schemas/gdst/transshipment.json` | `api/app/models/gdst/transshipment.py::TransshipmentEvent` | `#GDSTTransshipmentEvent&1.0.0` |
| `schemas/gdst/on_vessel.json` | `api/app/models/gdst/on_vessel.py::OnVesselProcessingEvent` | `#GDSTOnVesselProcessingEvent&1.0.0` |
| `schemas/gdst/processing.json` | `api/app/models/gdst/processing.py::ProcessingEvent` | `#GDSTProcessingEvent&1.0.0` |
| `schemas/gdst/shipping.json` | `api/app/models/gdst/shipping.py::ShippingEvent` | `#GDSTShippingEvent&1.0.0` |
| `schemas/gdst/aggregation.json` | `api/app/models/gdst/aggregation.py::AggregationEvent` | `#GDSTAggregationEvent&1.0.0` |
| `schemas/fsma/creating.json` | `api/app/models/starfish_events.py::CreatingEvent` | `#FSMA204CreatingEvent&1.0.0` |
| `schemas/fsma/shipping.json` | `api/app/models/starfish_events.py::ShippingEvent` | `#FSMA204ShippingEvent&1.0.0` |
| `schemas/fsma/receiving.json` | `api/app/models/starfish_events.py::ReceivingEvent` | `#FSMA204ReceivingEvent&1.0.0` |
| `schemas/fsma/transforming.json` | `api/app/models/starfish_events.py::TransformingEvent` | `#FSMA204TransformingEvent&1.0.0` |
| `schemas/fsma/packing.json` | `api/app/models/starfish_events.py::PackingEvent` | `#FSMA204PackingEvent&1.0.0` |
| `schemas/fsma/unpacking.json` | `api/app/models/starfish_events.py::UnpackingEvent` | `#FSMA204UnpackingEvent&1.0.0` |

## 4. Constraint Mapping (Pydantic → JSON-LD)

| Pydantic type (`constraints.py`) | Guardian JSON-LD |
|----------------------------------|------------------|
| `ISO3166Alpha2` — `^[A-Z]{2}$` | `string` + `pattern` |
| `FAOFishingArea` — `^FAO\d{2,3}$` | `string` + `pattern` |
| `FAOASFISCode` — `^[A-Z]{3}$` | `string` + `pattern` |
| `UNECE_UOM` — `^(KGM\|TNE\|LBR\|EA)$` | `string` + `enum` |
| `GTIN` — `^(\d{8}\|\d{12}\|\d{13}\|\d{14})$` | `string` + `pattern` |
| `EventID` — 6–64 chars | `string` + `minLength` + `maxLength` |
