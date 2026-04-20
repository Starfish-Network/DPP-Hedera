# Guardian Policy Exports

This directory is a **GPS deliverable** — do not rename or flatten.

Contains the self-contained `.policy` exports produced by the build scripts under [../../scripts/](../../scripts/):

- `gdst-seafood-traceability.policy` — produced by `build_gdst_policy.py`
- `fsma-204-food-safety.policy` — produced by `build_fsma_policy.py`

These exports are the artifact-of-record for Guardian Proposal Schema (GPS) submission. They MUST be importable into any vanilla Hedera Guardian 2.x runtime without reference to Starfish infrastructure (Constitution §II).

Do not hand-edit. Regenerate via the build scripts and re-publish IPFS CIDs in [../../specs/001-guardian-integration/contracts/gps-submission-checklist.md](../../specs/001-guardian-integration/contracts/gps-submission-checklist.md).
