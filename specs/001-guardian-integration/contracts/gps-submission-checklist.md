# Contract: GPS Submission Checklist

**Feature**: `001-guardian-integration` | **Source**: [docs/guardian-integration/03-gps-submission.md §4](../../../docs/guardian-integration/03-gps-submission.md)

Machine-auditable deliverables checklist for each Guardian Policy Standards (GPS) submission. An automated check should validate every item before a submission is sent. One checklist per policy.

---

## GDST Seafood Traceability

- [ ] Policy description with overview (file: `docs/gps/gdst-policy-description.md`)
- [ ] Workflow diagram (file: `docs/gps/gdst-workflow.png` or `.svg`)
- [ ] Explanatory video (URL: TBD)
- [ ] User guide (file: `docs/gps/gdst-policy-user-guide.md`)
- [ ] Sample input data — all 7 CTEs (files under `samples/gdst/`):
  - [ ] `samples/gdst/fishing.json`
  - [ ] `samples/gdst/landing.json`
  - [ ] `samples/gdst/transshipment.json`
  - [ ] `samples/gdst/on_vessel.json`
  - [ ] `samples/gdst/processing.json`
  - [ ] `samples/gdst/shipping.json`
  - [ ] `samples/gdst/aggregation.json`
- [ ] Every sample produces a `GDSTComplianceCredential` (automated: `pytest -m gps_samples -k gdst` passes)
- [ ] `.policy` export (file: `schemas/policies/gdst-seafood-traceability.policy`)
- [ ] `.json` schema files — 7 total (files under `schemas/gdst/`)
- [ ] IPFS CIDs recorded (file: `docs/gps/gdst-ipfs-cids.md`):
  - [ ] Policy `.policy` CID
  - [ ] One CID per of 7 schemas
- [ ] Guardian version compatibility declared (`Compatibility` block in the policy description, targeting latest stable)
- [ ] Hedera network declared (Testnet for dev, Mainnet for production)
- [ ] Dependencies declared (None — self-contained, per Constitution §I)
- [ ] Policy owner declared: `Starfish Network`
- [ ] Contact info declared (in `docs/gps/gdst-policy-description.md`)
- [ ] Update schedule declared (aligned with GDST regulatory updates)
- [ ] Support type declared: `Community support`

## FSMA 204 Food Safety

- [ ] Policy description with overview (file: `docs/gps/fsma-policy-description.md`)
- [ ] Workflow diagram (file: `docs/gps/fsma-workflow.png` or `.svg`)
- [ ] Explanatory video (URL: TBD)
- [ ] User guide (file: `docs/gps/fsma-policy-user-guide.md`)
- [ ] Sample input data — all 6 FSMA events (files under `samples/fsma/`):
  - [ ] `samples/fsma/creating.json`
  - [ ] `samples/fsma/shipping.json`
  - [ ] `samples/fsma/receiving.json`
  - [ ] `samples/fsma/transforming.json`
  - [ ] `samples/fsma/packing.json`
  - [ ] `samples/fsma/unpacking.json`
- [ ] Every sample produces an `FSMA204ComplianceCredential` (automated: `pytest -m gps_samples -k fsma` passes)
- [ ] `.policy` export (file: `schemas/policies/fsma-204-food-safety.policy`)
- [ ] `.json` schema files — 6 total (files under `schemas/fsma/`)
- [ ] IPFS CIDs recorded (file: `docs/gps/fsma-ipfs-cids.md`):
  - [ ] Policy `.policy` CID
  - [ ] One CID per of 6 schemas
- [ ] Guardian version compatibility declared
- [ ] Hedera network declared
- [ ] Dependencies declared (None)
- [ ] Policy owner declared: `Starfish Network`
- [ ] Contact info declared
- [ ] Update schedule declared (aligned with FDA FSMA updates)
- [ ] Support type declared: `Community support`

---

## Automated verification

A simple script (produced by `/speckit-implement` under `scripts/check_gps_submission.py`) MUST:

1. Assert every referenced file exists and is non-empty.
2. Resolve every declared IPFS CID and confirm the fetched bytes hash-match the local file.
3. Run the `gps_samples` pytest selection and require exit code 0.
4. Print one ✅/❌ per checkbox. Non-zero exit on any ❌.

## Maintenance obligations (from §3 of the source doc)

After acceptance:

- Issue response within 1 month.
- Updates on declared schedule, or a published attestation that the policy is still valid.
- Policies lapsing 3+ months without updates/attestation are archived.

Triggers for policy updates:

| Trigger | Required action |
|---------|-----------------|
| GDST 1.3 (or later) released | Update GDST schemas + rules, bump schema IRIs |
| FDA updates FSMA 204 | Update FSMA schemas + rules |
| Guardian breaking release | Test compatibility, update if needed |
| Community-reported bug | Fix within 1 month |
