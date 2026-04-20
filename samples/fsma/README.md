# FSMA 204 Sample Events

This directory is a **GPS deliverable** — do not rename or flatten.

Canonical, known-good FSMA 204 Food Traceability List event payloads, one per event type:

- `creating.json`
- `shipping.json`
- `receiving.json`
- `transforming.json`
- `packing.json`
- `unpacking.json`

Each sample is self-contained, validates against the matching JSON-LD schema in [../../schemas/fsma/](../../schemas/fsma/), and passes every `FSMA_*` rule in [../../specs/001-guardian-integration/data-model.md](../../specs/001-guardian-integration/data-model.md) §Rule Source Table.

The test suite consumes these files via the symlink [../../api/app/tests/fixtures/guardian/fsma](../../api/app/tests/fixtures/guardian/fsma) — they are the single source of truth for both the GPS packet and the integration tests (Constitution §Development Workflow #3).
