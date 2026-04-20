# Schemas and Policies (Core Delivery)

## Overview

This is the primary deliverable: two Guardian policies with versioned JSON-LD schemas encoding GDST 1.2 and FSMA 204 compliance rules. Each policy validates events and issues W3C Verifiable Credentials. Both are exported as `.policy` files for other Guardian projects to import.

---

## 1. Schema Definitions

One JSON-LD schema per event type. Derived from the existing Pydantic models.

### Constraint Mapping

| Pydantic Type (from `constraints.py`) | Guardian Schema |
|----------------------------------------|-----------------|
| `ISO3166Alpha2` — `^[A-Z]{2}$` | `string` with `pattern` |
| `FAOFishingArea` — `^FAO\d{2,3}$` | `string` with `pattern` |
| `FAOASFISCode` — `^[A-Z]{3}$` | `string` with `pattern` |
| `UNECE_UOM` — `^(KGM\|TNE\|LBR\|EA)$` | `string` with `enum` |
| `GTIN` — `^(\d{8}\|\d{12}\|\d{13}\|\d{14})$` | `string` with `pattern` |
| `EventID` — min 6, max 64 | `string` with `minLength`, `maxLength` |

### GDST Schemas (`schemas/gdst/`)

Each maps 1:1 to a model in `api/app/models/gdst/`.

| Schema | Source Model | Key Required Fields |
|--------|-------------|---------------------|
| `fishing.json` | `fishing.py` | vessel (id or name), `iuu.fishing_authorization`, catch_area or geo |
| `landing.json` | `landing.py` | `iuu.landing_authorization` |
| `transshipment.json` | `transshipment.py` | transshipment_vessel (id or name), `iuu.transshipment_authorization` |
| `on_vessel.json` | `on_vessel.py` | `when.production_date` |
| `processing.json` | `processing.py` | `when.production_date` |
| `shipping.json` | `shipping.py` | source/destination location, `what.linking_kde` |
| `aggregation.json` | `aggregation.py` | `parent_items` or `child_items` |

All GDST schemas share the base structure from `GDSTEvent` (`base.py`): `who` (OwnershipInfo), `what` (ProductInfo), `where` (LocationInfo), `when` (EventTiming), `iuu` (IUUInfo).

Example — `fishing.json`:

```json
{
  "name": "GDSTFishingEvent",
  "description": "GDST 1.2 Fishing Critical Tracking Event",
  "entity": "VC",
  "fields": [
    { "name": "gdst_event_type", "title": "Event Type", "type": "string", "required": true },
    { "name": "who", "title": "Ownership", "type": "object", "required": true,
      "fields": [
        { "name": "product_owner", "type": "string" },
        { "name": "information_provider", "type": "string" }
      ]
    },
    { "name": "what", "title": "Product", "type": "object", "required": true,
      "fields": [
        { "name": "species", "type": "string", "pattern": "^[A-Z]{3}$", "required": true },
        { "name": "product_form", "type": "string" },
        { "name": "item_sku_upc_gtin", "type": "string", "pattern": "^(\\d{8}|\\d{12}|\\d{13}|\\d{14})$" },
        { "name": "linking_kde", "type": "string" },
        { "name": "quantity", "type": "number", "minimum": 0, "required": true },
        { "name": "unit_of_measure", "type": "string", "enum": ["KGM", "TNE", "LBR", "EA"], "required": true }
      ]
    },
    { "name": "where", "title": "Location", "type": "object", "required": true,
      "fields": [
        { "name": "catch_area", "type": "string", "pattern": "^FAO\\d{2,3}$" },
        { "name": "event_read_point", "type": "object",
          "fields": [
            { "name": "latitude", "type": "number" },
            { "name": "longitude", "type": "number" }
          ]
        },
        { "name": "product_origin", "type": "string" }
      ]
    },
    { "name": "when", "title": "Timing", "type": "object", "required": true,
      "fields": [
        { "name": "event_id", "type": "string", "required": true },
        { "name": "event_datetime", "type": "string", "format": "date-time", "required": true },
        { "name": "capture_date", "type": "string", "format": "date-time" }
      ]
    },
    { "name": "vessel", "title": "Vessel", "type": "object", "required": true,
      "fields": [
        { "name": "vessel_name", "type": "string" },
        { "name": "vessel_id", "type": "string" },
        { "name": "vessel_registration", "type": "string" },
        { "name": "vessel_flag", "type": "string", "pattern": "^[A-Z]{2}$" }
      ]
    },
    { "name": "iuu", "title": "IUU Compliance", "type": "object",
      "fields": [
        { "name": "fishing_authorization", "type": "string", "required": true },
        { "name": "gear_type", "type": "string" },
        { "name": "production_method", "type": "string" },
        { "name": "harvest_certification", "type": "string" }
      ]
    }
  ]
}
```

### FSMA Schemas (`schemas/fsma/`)

Each maps 1:1 to a model in `api/app/models/starfish_events.py`.

| Schema | Source Model | Key Required Fields |
|--------|-------------|---------------------|
| `creating.json` | `CreatingEvent` | `event_time`, `biz_location`, `quantity_list` |
| `shipping.json` | `ShippingEvent` | `event_time`, `ship_from`, `ship_to`, `items` |
| `receiving.json` | `ReceivingEvent` | `event_time`, `shipped_from`, `received_at`, `items` |
| `transforming.json` | `TransformingEvent` | `event_time`, `facility`, `input_items`, `output_items` |
| `packing.json` | `PackingEvent` | `event_time`, `facility`, `container_id`, `input_items` |
| `unpacking.json` | `UnpackingEvent` | `event_time`, `facility`, `container_id`, `output_items` |

---

## 2. GDST Seafood Traceability Policy

```
Name:        GDST Seafood Traceability
Description: Cross Party Ruleset Compliance Template for GDST 1.2 Critical Tracking Events.
Policy Tag:  GDST-1.2
```

### Roles (Proposition)

| Role | Allowed Actions |
|------|-----------------|
| Standard Registry | Approve users, manage policy |
| Vessel Operator | Submit Fishing, OnVesselProcessing events |
| Processor | Submit Processing, Aggregation events |
| Shipper | Submit Shipping, Transshipment, Landing events |
| Auditor | View VCs |

### Workflow

```
Event Received → Schema Validation → Compliance Check → Compliant? ─┬─ Yes → Issue VC
                                                                     └─ No  → Reject
```

### Compliance Rules

Mirrors `gdst_min_rules()` from `api/app/helpers/compliance.py`.

**Common (all events):**
- `when.event_datetime` present
- `what.species` present, matches `^[A-Z]{3}$`
- `what.quantity` present, > 0
- `what.unit_of_measure` present, in `[KGM, TNE, LBR, EA]`

**Per event type:**

| Event | Required KDEs |
|-------|---------------|
| Fishing | vessel (id or name), `iuu.fishing_authorization`, catch_area or geo |
| OnVesselProcessing | `when.production_date` |
| Transshipment | transshipment_vessel (id or name), `iuu.transshipment_authorization` |
| Landing | `iuu.landing_authorization` |
| ShippingReceiving | source or destination location, `what.linking_kde` |
| Processing | `when.production_date` |
| AggregationDisaggregation | `parent_items` or `child_items` non-empty |

### VC Output

```json
{
  "@context": ["https://www.w3.org/2018/credentials/v1"],
  "type": ["VerifiableCredential", "GDSTComplianceCredential"],
  "issuer": "did:hedera:testnet:..._0.0.xxxxx",
  "issuanceDate": "2026-04-07T12:00:00Z",
  "credentialSubject": {
    "id": "did:hedera:testnet:..._0.0.yyyyy",
    "eventHash": "0xabc123...",
    "gdstEventType": "Fishing",
    "complianceStatus": "compliant",
    "species": "TUN",
    "catchArea": "FAO71",
    "fishingAuthorization": "AUTH-2026-001"
  },
  "proof": { "type": "Ed25519Signature2018", "..." }
}
```

`credentialSubject.eventHash` matches the `bytes32` stored on-chain via `ComplianceVerifier.recordEvent()`.

---

## 3. FSMA 204 Food Safety Policy

```
Name:        FSMA 204 Food Safety
Description: Cross Party Ruleset Compliance Template for FDA FSMA Section 204 traceability.
Policy Tag:  FSMA-204
```

### Roles (Proposition)

| Role | Allowed Actions |
|------|-----------------|
| Standard Registry | Approve users, manage policy |
| Producer | Submit Creating events |
| Shipper | Submit Shipping events |
| Receiver | Submit Receiving events |
| Transformer | Submit Transforming, Packing, Unpacking events |

### Compliance Rules

Mirrors `fsma_min_rules()` from `api/app/helpers/compliance.py`.

**Common:** `event_time` present.

| Event | Required Fields |
|-------|-----------------|
| Creating | `biz_location`, `quantity_list` non-empty |
| Shipping | `ship_from`, `ship_to`, `items` non-empty |
| Receiving | `received_at` or `ship_to`, `items` non-empty |
| Transforming | `facility`, `input_items` non-empty, `output_items` non-empty |
| Packing | `facility`, `container_id`, `input_items` non-empty |
| Unpacking | `facility`, `container_id`, `output_items` non-empty |

### VC Output

```json
{
  "@context": ["https://www.w3.org/2018/credentials/v1"],
  "type": ["VerifiableCredential", "FSMA204ComplianceCredential"],
  "issuer": "did:hedera:testnet:...",
  "credentialSubject": {
    "eventHash": "0xdef456...",
    "eventType": "shipping",
    "complianceStatus": "compliant",
    "shipFrom": "facility-123",
    "shipTo": "facility-456"
  },
  "proof": { "..." }
}
```

---

## 4. Composability

Our policies are designed so other Guardian projects can import them and compose multi-policy workflows.

### Deliverables

```
schemas/
├── gdst/*.json                              # 7 versioned schemas
├── fsma/*.json                              # 6 versioned schemas
└── policies/
    ├── gdst-seafood-traceability.policy     # Importable Guardian policy
    └── fsma-204-food-safety.policy          # Importable Guardian policy
```

### Schema Versioning

Versioned so other policies can reference without duplication:

```
#GDSTFishingEvent&1.0.0
#GDSTLandingEvent&1.0.0
#FSMA204ShippingEvent&1.0.0
```

### VC Output Interface

Downstream policies accept our VCs via Guardian's `trustChainBlock`.

**GDST:**
```
Type: GDSTComplianceCredential
Guaranteed: eventHash, gdstEventType, complianceStatus, species
Optional:   catchArea, fishingAuthorization, vesselId,
            landingAuthorization, transshipmentAuthorization
```

**FSMA:**
```
Type: FSMA204ComplianceCredential
Guaranteed: eventHash, eventType, complianceStatus
Optional:   facility, shipFrom, shipTo
```

### Design Rules

1. **Schemas are self-contained.** Each validates independently.
2. **VCs include enough context** for downstream policies to decide without calling our API.
3. **Stable issuer DID.** The Standard Registry DID is the trust anchor.
4. **Semantic VC types.** Specific types let downstream policies filter without inspecting payloads.
5. **Versioned schemas.** Breaking changes get a new version number.

---

## 5. FastAPI Integration

### Schema Mapper: `api/app/service/schema_mapper.py`

Converts between Pydantic models and Guardian JSON-LD format:

```python
def pydantic_to_guardian_schema(model_class, schema_name, schema_description) -> dict
def event_dict_to_guardian_document(event: dict, schema_iri: str) -> dict
def guardian_vc_to_dict(vc_response: dict) -> dict
```

### Event Route Hooks

After existing HCS submission, submit to MGS via the `/external` endpoint (no auth required for external document submission, but our client always sends JWT):

```python
# In api/app/routes/gdst/events.py
result = hedera_post_transaction(encrypted_payload)  # unchanged

guardian_doc = event_dict_to_guardian_document(event_dict, gdst_schema_iri)
guardian_client.submit_document(gdst_policy_id, gdst_intake_block_tag, guardian_doc)
# → POST /external/{gdst_policy_id}/{gdst_intake_block_tag}
```

`gdst_intake_block_tag` is the tag of the policy's external-data intake block (set when the policy is built). Same pattern in `api/app/routes/epcis/compliance.py` for FSMA events with `fsma_policy_id` + `fsma_intake_block_tag`.

### VC Query Routes: `api/app/routes/guardian/policy.py`

VCs are not retrieved by hash directly. Each route queries `GET /policies/{id}/documents?type=VC` and filters by `credentialSubject.eventHash`:

- `GET /guardian/gdst/vc/{event_hash}` — searches GDST policy documents
- `GET /guardian/fsma/vc/{event_hash}` — searches FSMA policy documents

---

## 6. Schema Deployment

One-time setup script. `create_schema` (`POST /schemas`) is sync; `publish_schema` and `publish_policy` use the async `/push/` variants and require polling `GET /tasks/{taskId}`:

```python
for schema_file in glob("schemas/gdst/*.json") + glob("schemas/fsma/*.json"):
    schema = guardian_client.create_schema(json.load(open(schema_file)))
    task = guardian_client.publish_schema(schema["id"])  # PUT /schemas/push/{id}/publish
    guardian_client.wait_for_task(task["taskId"])

# Same pattern for policies — create, then publish via /push/, then poll
gdst_task = guardian_client.publish_policy(gdst_policy_id)
guardian_client.wait_for_task(gdst_task["taskId"])

guardian_client.export_policy(gdst_policy_id)   # → gdst-seafood-traceability.policy
guardian_client.export_policy(fsma_policy_id)   # → fsma-204-food-safety.policy
```
