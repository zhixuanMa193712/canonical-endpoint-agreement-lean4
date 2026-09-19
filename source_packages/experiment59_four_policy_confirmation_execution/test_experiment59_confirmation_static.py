"""Zero-Lean static checks for the Exp59 confirmation package."""
from __future__ import annotations

import ast
import json

from experiment59_confirmation_protocol import *


REQUIRED = {"experiment59_confirmation_protocol.py", "freeze_experiment59_confirmation_execution.py",
    "preflight_experiment59_confirmation.py", "experiment59_confirmation_live_worker.py",
    "run_experiment59_confirmation_shards.py", "launch_experiment59_confirmation.py",
    "monitor_experiment59_confirmation.py", "finalize_experiment59_confirmation.py",
    "analyze_experiment59_confirmation.py", "audit_experiment59_confirmation.py",
    "export_experiment59_confirmation.py", "test_experiment59_confirmation_static.py",
    "build_experiment59_confirmation_package.py", "README_SERVER.md", "EXP59_CONFIRMATION_AMENDMENT.md"}


def check(value: bool, message: str) -> None:
    if not value: raise AssertionError(message)


def run() -> dict:
    count = 0; names = {path.name for path in PACKAGE_ROOT.iterdir() if path.is_file()}
    check(REQUIRED <= names, "confirmation package incomplete"); count += 1
    for path in PACKAGE_ROOT.glob("*.py"): ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    count += 1
    check(EXPECTED_SELECTION_DESIGN_RECORD_SHA256 == "70043de8a1c6db3abf94687d5166f25468ae95c8fba3495079c77cbd8668a114", "selection lock changed"); count += 1
    check(EXPECTED_SELECTED_ROOTS_SHA256.startswith("cbfc4569"), "selected roots lock changed"); count += 1
    check(EXPECTED_SELECTION_AUDIT_SHA256.startswith("2c341eee"), "selection audit lock changed"); count += 1
    check(EXPECTED_ROOTS == 64 and ROOTS_PER_DATASET == 32 and EXPECTED_JOBS == 256, "confirmation counts changed"); count += 1
    check(POLICIES == ("full", "effect_aware", "head_dedup", "fixed_budget_random"), "policies changed"); count += 1
    check(len(PROBE_PANEL) == 8, "probe panel changed"); count += 1
    freeze = (PACKAGE_ROOT / "freeze_experiment59_confirmation_execution.py").read_text()
    check("confirmation_continuation_probes_executed_before_execution_freeze\": 0" in freeze, "pre-execution gate missing"); count += 1
    worker = (PACKAGE_ROOT / "experiment59_confirmation_live_worker.py").read_text()
    check("initial_ready" in worker and "normalize_goal_text" in worker, "compact initial adapter missing"); count += 1
    runner = (PACKAGE_ROOT / "run_experiment59_confirmation_shards.py").read_text()
    check("retry forbidden" in runner and "candidate_only" in runner, "fail-closed execution missing"); count += 1
    analysis = (PACKAGE_ROOT / "analyze_experiment59_confirmation.py").read_text()
    check("registered_one_sided_95_lower" in analysis and "registered_one_sided_95_upper" in analysis, "registered tests missing"); count += 1
    check("solve_coverage_information_gate" in analysis, "coverage information check missing"); count += 1
    check("efficiency_and_coverage_are_separate_estimands" in analysis, "estimands not separated"); count += 1
    audit = (PACKAGE_ROOT / "audit_experiment59_confirmation.py").read_text()
    check("cells_reconstructed" in audit and "paired_metrics_reconstructed_exact" in audit, "independent audit incomplete"); count += 1
    check(not any("pilot/execution" in path.read_text(errors="ignore") for path in PACKAGE_ROOT.glob("run_*.py")), "confirmation runner points at pilot execution"); count += 1
    return {"version": VERSION, "package": "experiment59-four-policy-confirmation-execution",
            "static_checks": count, "all_static_checks_passed": True, "lean_executed": False,
            "theorem_sources_elaborated": 0, "confirmation_cells_executed": 0,
            "continuation_probes_executed": 0}


if __name__ == "__main__": print(json.dumps(run(), indent=2))
