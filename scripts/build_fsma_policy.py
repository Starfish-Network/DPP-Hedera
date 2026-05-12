#!/usr/bin/env python3
"""
Bootstrap the FSMA 204 Guardian policy on the configured MGS tenant.

Flow + invariants are documented in `scripts/_policy_builder.py`. This file
is just the FSMA spec; it shells out to `_policy_builder.run` for the
actual work.

    python3 scripts/build_fsma_policy.py             # full bootstrap + publish + export
    python3 scripts/build_fsma_policy.py --resume    # pick up after a mid-run failure
    python3 scripts/build_fsma_policy.py --draft-only # stop in DRAFT (for MGS dry-run)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _policy_builder import PolicySpec, REPO_ROOT, run  # noqa: E402

SPEC = PolicySpec(
    slug="fsma",
    name="FSMA 204 Food Safety",
    description=(
        "FSMA 204 (Food Safety Modernization Act, Final Traceability Rule) "
        "compliance for Critical Tracking Events. Issues "
        "FSMA204ComplianceCredential VCs for events submitted via FastAPI."
    ),
    policy_tag="FSMA-204-food-safety-v4",
    intake_schema_path=REPO_ROOT / "schemas" / "fsma" / "compliance-intake.json",
    export_path=REPO_ROOT / "schemas" / "policies" / "fsma-204-food-safety.policy",
    schema_name="FSMA204ComplianceIntake",
    entity_type="FSMA204ComplianceIntake",
    env_var_prefix="GUARDIAN_FSMA_",
)


if __name__ == "__main__":
    run(SPEC, doc=__doc__)
