# GDST Sample Events

This directory is a **GPS deliverable** — do not rename or flatten.

Canonical, known-good GDST Critical Tracking Event payloads, one per CTE defined in the GDST 1.2 standard:

- `fishing.json`
- `landing.json`
- `transshipment.json`
- `on_vessel.json`
- `processing.json`
- `shipping.json`
- `aggregation.json`

Each sample is self-contained, validates against the matching JSON-LD schema in [../../schemas/gdst/](../../schemas/gdst/), and passes every `GDST_*` rule in [../../specs/001-guardian-integration/data-model.md](../../specs/001-guardian-integration/data-model.md) §Rule Source Table.

The test suite consumes these files via the symlink [../../api/app/tests/fixtures/guardian/gdst](../../api/app/tests/fixtures/guardian/gdst) — they are the single source of truth for both the GPS packet and the integration tests (Constitution §Development Workflow #3).
