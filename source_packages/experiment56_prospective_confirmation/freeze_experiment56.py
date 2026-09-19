"""Freeze the prospective confirmation before recruitment or Lean execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiment56_protocol import *
from simulate_repository_power import run as run_power


def freeze(root: Path) -> dict:
    power_path = root / "design/power_simulation.json"
    if power_path.is_file():
        power = read_json(power_path)
        assert_sealed(power, "power simulation")
    else:
        power = run_power(root / "design")
    registered = power["registered_design"]
    if not (
        registered["repositories"] == REPOSITORIES_REQUIRED
        and registered["roots_per_repository"] == ROOTS_PER_REPOSITORY
        and registered["planning_gate_probability"] >= 0.90
    ):
        raise ValueError("registered design lacks the frozen planning operating characteristic")
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "design_schema": DESIGN_SCHEMA,
        "purpose": "prospective confirmation independent of the historical 96-root selection",
        "source_locks": validate_locks(),
        "implementation_locks": [
            {"path": path.name, "sha256": file_sha256(path), "bytes": path.stat().st_size}
            for path in sorted(PACKAGE_ROOT.glob("*.py"), key=lambda item: item.name)
        ],
        "candidate_snapshot_queries": list(FROZEN_GITHUB_QUERIES),
        "historical_scientific_exclusions": sorted(
            HISTORICAL_SCIENTIFIC_REPOSITORIES, key=str.lower
        ),
        "power_simulation_sha256": file_sha256(power_path),
        "eligible_repository_contract": {
            "public_candidate_snapshot_before_screening": True,
            "excluded_historical_scientific_repositories": True,
            "public_all_eligible_and_excluded_repositories": True,
            "lean_toolchain": TARGET_TOOLCHAIN,
            "unmodified_build_required": True,
            "trace_required": True,
            "authored_replay_required": True,
            "minimum_eligible_roots": MIN_ELIGIBLE_ROOTS,
            "source_overlap_threshold": SOURCE_OVERLAP_THRESHOLD,
        },
        "repository_sampling": {
            "seed": MASTER_REPOSITORY_SEED,
            "key": "sha256(seed || repository_slug || commit)",
            "take": REPOSITORIES_REQUIRED,
            "selection_unit": "lineage representative repository",
        },
        "root_sampling": {
            "seed": MASTER_ROOT_SEED,
            "key": "sha256(seed || slug || commit || source_sha256 || theorem_name || positions)",
            "take_per_repository": ROOTS_PER_REPOSITORY,
        },
        "measurement": {
            "candidate_panel": "the frozen 23-candidate L0 panel from the locked backend",
            "primary_root_outcome": "at least one state-conditioned strict-endpoint witness",
            "roots": TOTAL_ROOTS,
            "candidates_per_root": CANDIDATES_PER_ROOT,
        },
        "registered_analysis": {
            "unit": "repository",
            "macro_estimand": "unweighted mean of repository witness fractions",
            "bootstrap": "two-level repository-then-root bootstrap",
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "confirmation_gate": {
                "lower_95_ci_gt": PRIMARY_THRESHOLD,
                "ci_halfwidth_lte": MAX_CI_HALFWIDTH,
                "nonzero_repository_fraction_gte": MIN_NONZERO_REPOSITORY_FRACTION,
            },
        },
        "historical_claim_policy": {
            "does_not_overwrite_exp48": True,
            "new_result_reported_separately": True,
            "failure_or_shortfall_retained": True,
        },
        "scientific_candidate_execution_before_freeze": False,
        "scientific_candidate_tactics_executed": 0,
        "next_step": "Snapshot and hash the complete candidate frame, then run zero-candidate qualification.",
    })
    atomic_json_dump(value, root / "frozen/protocol.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(freeze(Path(parse_args().artifact_root).resolve()), indent=2))
