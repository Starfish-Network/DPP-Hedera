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

See [../../specs/001-guardian-integration/data-model.md](../../specs/001-guardian-integration/data-model.md) for the canonical field list and rule table. Schemas here MUST stay in lockstep with the Pydantic models in [../../api/app/models/epcis/](../../api/app/models/epcis/) (Constitution §III).
