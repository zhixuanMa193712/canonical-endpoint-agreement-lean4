"""Static tests for Exp53; no Lean or theorem source is executed."""
from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path

from exp53_protocol import *


def main() -> dict[str, Any]:
    python_files = sorted(PACKAGE_ROOT.glob("*.py")) + sorted(
        (PACKAGE_ROOT / "vendor").glob("*.py")
    )
    for path in python_files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    subset, receipt = validate_frozen()
    counts = Counter(row["slug"] for row in subset["targets"])
    selected = [row["slug"] for row in subset["repositories"]]
    references = read_json(PACKAGE_ROOT / "frozen/reference_index.json")
    theorem_ids = [row["theorem_id"] for row in subset["targets"]]
    assertions = {
        "python_syntax_valid": True,
        "repository_count_exact": len(selected) == REPOSITORIES,
        "root_count_exact": len(subset["targets"]) == ROOTS,
        "roots_per_repository_exact": all(
            counts[slug] == ROOTS_PER_REPOSITORY for slug in selected
        ),
        "candidate_budget_exact": all(
            len(row["alternatives"]) == CANDIDATES_PER_ROOT
            and json_sha256(row["alternatives"]) == row["alternatives_sha256"]
            for row in subset["targets"]
        ),
        "reference_rows_exact": len(references) == ROOTS,
        "root_identities_unique": len(set(theorem_ids)) == ROOTS,
        "reference_identities_exact": {
            row["theorem_id"] for row in references
        } == set(theorem_ids),
        "outcome_blind_selection_declared": subset["selection_rule"][
            "candidate_outcomes_used"
        ] is False,
        "source_bundle_locked": receipt["source_exp51_bundle_sha256"]
        == SOURCE_EXP51_SHA256,
        "zero_execution_during_freeze": receipt["scientific_candidate_tactics_executed"]
        == 0 and receipt["theorem_sources_elaborated"] == 0,
        "prior_aborted_launch_disclosed": receipt["prior_aborted_scientific_launch"]
        is True and receipt["prior_aborted_rows_persisted"] == 14
        and receipt["prior_aborted_candidate_attempts_in_persisted_rows"] == 322
        and receipt["prior_aborted_comparison_analysis_executed"] is False,
    }
    value = {
        "version": 1,
        "package": "experiment53-cross-machine-subset-reexecution-v1",
        "tests": assertions,
        "all_static_tests_passed": all(assertions.values()),
        "lean_executed": False,
        "theorem_sources_elaborated": 0,
        "candidate_tactics_executed": 0,
    }
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


if __name__ == "__main__":
    result = main()
    raise SystemExit(0 if result["all_static_tests_passed"] else 2)
