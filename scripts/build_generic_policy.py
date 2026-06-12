#!/usr/bin/env python3
"""
Bootstrap the generic Guardian policy on the configured MGS tenant.

Same flow + invariants as `build_gdst_policy.py` and `build_fsma_policy.py`
(see `scripts/_policy_builder.py`). The schema is minimal: an `eventType`
free-form string + the canonical metadata fields. Use this policy for
operators that don't follow GDST or FSMA conventions.

    python3 scripts/build_generic_policy.py             # full bootstrap + publish + export
    python3 scripts/build_generic_policy.py --resume    # pick up after a mid-run failure
    python3 scripts/build_generic_policy.py --draft-only # stop in DRAFT (for MGS dry-run)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _policy_builder import PolicySpec, REPO_ROOT, run  # noqa: E402

SPEC = PolicySpec(
    slug="generic",
    name="Generic Compliance",
    description=(
        "Generic compliance policy for traceability events that don't follow "
        "GDST 1.2 or FSMA 204 conventions. Issues GenericComplianceCredential "
        "VCs for events submitted via FastAPI."
    ),
    policy_tag="generic-compliance-v1",
    intake_schema_path=REPO_ROOT / "schemas" / "generic" / "compliance-intake.json",
    export_path=REPO_ROOT / "schemas" / "policies" / "generic-compliance.policy",
    schema_name="GenericComplianceIntake",
    entity_type="GenericComplianceIntake",
    env_var_prefix="GUARDIAN_GENERIC_",
)


if __name__ == "__main__":
    run(SPEC, doc=__doc__)
