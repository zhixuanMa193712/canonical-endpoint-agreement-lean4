"""Static, zero-Lean checks for the Exp59 pilot execution package."""
from __future__ import annotations

import ast
import json
from pathlib import Path

from experiment59_pilot_protocol import *


REQUIRED = {
    "experiment59_pilot_protocol.py", "freeze_experiment59_pilot.py",
    "preflight_experiment59_pilot.py", "experiment59_pilot_live_worker.py",
    "run_experiment59_pilot_shards.py", "launch_experiment59_pilot.py",
    "monitor_experiment59_pilot.py", "finalize_experiment59_pilot.py",
    "analyze_experiment59_pilot.py", "audit_experiment59_pilot.py",
    "plan_experiment59_power.py", "freeze_experiment59_confirmation.py",
    "test_experiment59_pilot_static.py", "build_experiment59_pilot_package.py",
    "README_SERVER.md", "EXP59_PILOT_AMENDMENT.md",
}


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run() -> dict:
    checks = 0
    names = {path.name for path in PACKAGE_ROOT.iterdir() if path.is_file()}
    check(REQUIRED <= names, "package file set is incomplete"); checks += 1
    for path in PACKAGE_ROOT.glob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    checks += 1
    check(
        EXPECTED_SCREENING_SUMMARY_RECORD_SHA256
        == "96ef54df49716b1037d84ae383b790d6fde86800fb4fc3325a371a61cec80331",
        "screening summary lock changed",
    ); checks += 1
    check(EXPECTED_ELIGIBILITY_LEDGER_SHA256.startswith("5751d162"), "ledger lock changed"); checks += 1
    check(EXPECTED_PILOT_ROOTS_SHA256.startswith("a83631e3"), "pilot lock changed"); checks += 1
    check(POLICIES == ("full", "effect_aware", "head_dedup", "fixed_budget_random"),
          "policy panel changed"); checks += 1
    check(len(PROBE_PANEL) == 8 and len(set(PROBE_PANEL)) == 8, "probe panel changed"); checks += 1
    branches = [
        {"branch_id": "a", "head": "simp", "endpoints": {"struct": {"sha256": "x"}}},
        {"branch_id": "b", "head": "ring", "endpoints": {"struct": {"sha256": "x"}}},
        {"branch_id": "c", "head": "ring", "endpoints": {"struct": {"sha256": "y"}}},
        {"branch_id": "d", "head": "aesop", "endpoints": {"struct": {"sha256": "z"}}},
    ]
    check(len(choose("full", branches, "root")) == 4, "full policy changed"); checks += 1
    check([row["branch_id"] for row in choose("effect_aware", branches, "root")] == ["a", "c", "d"],
          "effect policy changed"); checks += 1
    check([row["branch_id"] for row in choose("head_dedup", branches, "root")] == ["a", "b", "d"],
          "head policy changed"); checks += 1
    check(
        choose("fixed_budget_random", branches, "root")
        == choose("fixed_budget_random", branches, "root"),
        "random policy is not deterministic",
    ); checks += 1
    validate_backend(); checks += 1
    freeze_text = (PACKAGE_ROOT / "freeze_experiment59_pilot.py").read_text(encoding="utf-8")
    check("continuation_probes_executed_before_freeze\": 0" in freeze_text,
          "pilot pre-probe gate missing"); checks += 1
    runner_text = (PACKAGE_ROOT / "run_experiment59_pilot_shards.py").read_text(encoding="utf-8")
    check("each policy independently" not in runner_text or "candidate_only" in runner_text,
          "candidate execution path missing"); checks += 1
    check("retry is forbidden" in runner_text, "fail-closed retry rule missing"); checks += 1
    worker_text = (PACKAGE_ROOT / "experiment59_pilot_live_worker.py").read_text(encoding="utf-8")
    check("initial_values" in worker_text and "source_module.normalize_goal_text" in worker_text,
          "Exp59 compact initial-state adapter missing"); checks += 1
    analysis_text = (PACKAGE_ROOT / "analyze_experiment59_pilot.py").read_text(encoding="utf-8")
    check("efficiency_and_coverage_are_separate_estimands" in analysis_text,
          "separate estimands missing"); checks += 1
    power_text = (PACKAGE_ROOT / "plan_experiment59_power.py").read_text(encoding="utf-8")
    check("joint_gate_probability" in power_text and "POWER_TARGET" in power_text,
          "joint power gate missing"); checks += 1
    confirmation_text = (PACKAGE_ROOT / "freeze_experiment59_confirmation.py").read_text(encoding="utf-8")
    check("pilot_and_confirmation_disjoint" in confirmation_text,
          "pilot-confirmation disjointness missing"); checks += 1
    check(not any(path.name.startswith("run_experiment59_confirmation") for path in PACKAGE_ROOT.iterdir()),
          "confirmation execution was bundled before confirmation freeze"); checks += 1
    value = {
        "version": VERSION,
        "package": "experiment59-four-policy-pilot-execution",
        "static_checks": checks,
        "all_static_checks_passed": True,
        "lean_executed": False,
        "theorem_sources_elaborated": 0,
        "candidate_only_tactics_executed": 0,
        "continuation_probes_executed": 0,
    }
    return value


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
