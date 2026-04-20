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
