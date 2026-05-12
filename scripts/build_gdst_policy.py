#!/usr/bin/env python3
"""
Bootstrap the GDST Guardian policy on the configured MGS tenant.

Flow + invariants are documented in `scripts/_policy_builder.py`. This file
is just the GDST spec; it shells out to `_policy_builder.run` for the
actual work.

    python3 scripts/build_gdst_policy.py             # full bootstrap + publish + export
    python3 scripts/build_gdst_policy.py --resume    # pick up after a mid-run failure
    python3 scripts/build_gdst_policy.py --draft-only # stop in DRAFT (for MGS dry-run)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _policy_builder import PolicySpec, REPO_ROOT, run  # noqa: E402

SPEC = PolicySpec(
    slug="gdst",
    name="GDST Seafood Traceability",
    description=(
        "Cross-party ruleset compliance for GDST 1.2 critical tracking events. "
        "Issues GDSTComplianceCredential VCs for events submitted via FastAPI."
    ),
    policy_tag="GDST-1-2-seafood-v9",
    intake_schema_path=REPO_ROOT / "schemas" / "gdst" / "compliance-intake.json",
    export_path=REPO_ROOT / "schemas" / "policies" / "gdst-seafood-traceability.policy",
    schema_name="GDSTComplianceIntake",
    entity_type="GDSTComplianceIntake",
    env_var_prefix="GUARDIAN_GDST_",
)


if __name__ == "__main__":
    run(SPEC, doc=__doc__)
