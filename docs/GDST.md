# GDST – Field Definitions and Validation Rules

This document describes the **GDST Critical Tracking Event (CTE) Python models**, including:

* Field definitions
* Data standards applied
* Validation rules and business constraints

These models are designed to align with **GDST Event-Based Traceability**, **GS1 EPCIS**, and **IUU compliance expectations**.

---

## 1. Design Principles

* One **Python model per GDST CTE** (e.g. Fishing, Landing, Transshipment)
* Shared sub-models for **Who / What / Where / When / IUU**
* Validation is based on:

  * GDST developer guidance
  * ISO, FAO, UNECE, GS1 standards
  * Regulatory/IUU expectations

The goal is to prevent invalid or non-compliant traceability events at ingestion time.

---

## 2. Common Field Groups

### 2.1 WHO – Ownership & Vessel Information

#### OwnershipInfo

| Field                | Description                         | Type   | Validation |
| -------------------- | ----------------------------------- | ------ | ---------- |
| product_owner        | Legal owner of the product          | string | Optional   |
| information_provider | Party responsible for data accuracy | string | Optional   |

#### VesselInfo

| Field               | Description                      | Type         | Validation                               |
| ------------------- | -------------------------------- | ------------ | ---------------------------------------- |
| vessel_name         | Name of the vessel               | string       | Optional                                 |
| vessel_registration | National vessel registration     | string       | Optional                                 |
| vessel_id           | IMO number or national vessel ID | string       | Optional                                 |
| public_registry_url | Link to public vessel registry   | string (URL) | Optional                                 |
| vessel_flag         | Flag state of the vessel         | string       | **ISO 3166-1 alpha-2** (e.g. `NO`, `US`) |

---

### 2.2 WHAT – Product Information

#### ProductInfo

| Field             | Description                  | Type   | Validation                               |
| ----------------- | ---------------------------- | ------ | ---------------------------------------- |
| species           | Species code                 | string | **FAO ASFIS 3-letter code** (e.g. `COD`) |
| product_form      | Physical form of product     | string | Optional                                 |
| item_sku_upc_gtin | Trade identifier             | string | **GTIN-8/12/13/14 numeric**              |
| linking_kde       | Batch, lot, or serial number | string | Optional                                 |
| quantity          | Quantity of product          | number | **Must be > 0**                          |
| unit_of_measure   | Unit of measure              | string | **UNECE codes** (e.g. `KGM`, `TNE`)      |

---

### 2.3 WHERE – Location Information

#### GeoLocation

| Field     | Description | Type   | Validation             |
| --------- | ----------- | ------ | ---------------------- |
| latitude  | Latitude    | number | **-90 ≤ value ≤ 90**   |
| longitude | Longitude   | number | **-180 ≤ value ≤ 180** |

#### LocationInfo

| Field                | Description             | Type        | Validation                       |
| -------------------- | ----------------------- | ----------- | -------------------------------- |
| event_read_point     | Physical event location | GeoLocation | Optional                         |
| source_location      | Shipping origin         | string      | Optional                         |
| destination_location | Shipping destination    | string      | Optional                         |
| catch_area           | Fishing area            | string      | **FAO area code** (e.g. `FAO27`) |
| product_origin       | Origin country/location | string      | Optional                         |

---

### 2.4 WHEN – Event Timing

#### EventTiming

| Field           | Description             | Type     | Validation                        |
| --------------- | ----------------------- | -------- | --------------------------------- |
| event_id        | Unique event identifier | string   | 6–64 characters                   |
| event_datetime  | Date/time of event      | datetime | ISO 8601                          |
| timezone        | Time zone identifier    | string   | Optional                          |
| capture_date    | Date of capture         | datetime | Optional                          |
| landing_date    | Date of landing         | datetime | Optional                          |
| production_date | Date of production      | datetime | Optional                          |
| expiration_date | Expiration date         | datetime | **Must be after production_date** |

---

### 2.5 IUU – Compliance & Ethical Data

#### IUUInfo

| Field                          | Description                    | Type    | Validation                    |
| ------------------------------ | ------------------------------ | ------- | ----------------------------- |
| chain_of_custody_certification | Chain of custody reference     | string  | Optional                      |
| fishing_authorization          | Fishing authorization ID       | string  | Required for Fishing          |
| landing_authorization          | Landing authorization ID       | string  | Required for Landing          |
| transshipment_authorization    | Transshipment authorization ID | string  | Required for Transshipment    |
| harvest_certification          | Harvest certification          | string  | Optional                      |
| production_method              | Production method              | string  | Optional                      |
| gear_type                      | Fishing gear used              | string  | Optional                      |
| human_welfare_policy_exists    | Welfare policy exists          | boolean | Optional                      |
| human_welfare_policy_standards | Welfare standards              | string  | Requires policy_exists = true |

---

## 3. Base GDST Event Model

All GDST events inherit from a common base structure.

| Field           | Description                           |
| --------------- | ------------------------------------- |
| gdst_event_type | GDST CTE name (controlled vocabulary) |
| who             | Ownership information                 |
| what            | Product information                   |
| where           | Location information                  |
| when            | Timing information                    |
| iuu             | IUU compliance information            |

### Allowed GDST Event Types

* Fishing
* OnVesselProcessing
* Transshipment
* Landing
* AggregationDisaggregation
* ShippingReceiving
* Processing

Invalid event types are rejected.

---

## 4. Event-Specific Validation Rules

### 4.1 Fishing Event

**Additional Requirements:**

* Must include either:

  * `catch_area`, or
  * `event_read_point` (geo coordinates)
* `fishing_authorization` is required

---

### 4.2 Transshipment Event

**Additional Requirements:**

* `transshipment_authorization` is required
* Transshipment vessel must be provided

---

### 4.3 Landing Event

**Additional Requirements:**

* `landing_authorization` is required

---

### 4.4 Aggregation / Disaggregation Event

**Additional Requirements:**

* At least one parent or child item reference should exist
* Used to represent packaging or unpacking events

---

### 4.5 Shipping / Receiving Event

**Additional Requirements:**

* Source and/or destination location should be present

---

### 4.6 Processing Event

**Additional Requirements:**

* `product_origin` or processing location should be present

---

## 5. Standards Referenced

* GDST Event-Based Traceability
* GDST Developer Portal
* GS1 EPCIS 2.0
* ISO 3166-1 (Country Codes)
* FAO ASFIS (Species Codes)
* FAO Fishing Areas
* UNECE Units of Measure
