"""Independently reconstruct Exp59 pilot accounting from immutable receipts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiment59_pilot_protocol import *


def audit(root: Path) -> dict[str, Any]:
    design = load_design(root)
    analysis_path = root / "pilot/analysis/summary.json"
    execution_path = root / "pilot/execution/summary.json"
    analysis = read_json(analysis_path)
    execution = read_json(execution_path)
    assert_sealed(analysis, "pilot analysis")
    assert_sealed(execution, "pilot execution")
    planned = read_jsonl(design["jobs_path"])
    reconstructed = []
    cells_reconstructed = 0
    for plan in planned:
        path = root / "pilot/execution/jobs" / f"{plan['job_id']}.json"
        row = read_json(path)
        assert_sealed(row, f"pilot audit job {plan['job_id']}")
        if row.get("job") != plan:
            raise ValueError("pilot audit found a changed job plan")
        cells = []
        for item in row["cell_receipts"]:
            cell_path = Path(item["path"])
            if file_sha256(cell_path) != item["sha256"]:
                raise ValueError("pilot audit found a changed cell file")
            cell = read_json(cell_path)
            assert_sealed(cell, f"pilot audit cell {item['cell_id']}")
            if not (
                cell["cell_id"] == item["cell_id"]
                and cell["job_id"] == plan["job_id"]
                and cell["target_id"] == plan["target_id"]
                and cell["policy"] == plan["policy"]
            ):
                raise ValueError("pilot audit found a changed cell identity")
            cells.append(cell)
        cells_reconstructed += len(cells)
        reconstructed.append({
            "target_id": plan["target_id"], "dataset": plan["dataset"],
            "policy": plan["policy"], "process_calls": len(cells),
            "candidate_process_calls": sum(cell["mode"] == "candidate_only" for cell in cells),
            "downstream_process_calls": sum(cell["mode"] == "candidate_probe" for cell in cells),
            "solved": any(cell.get("terminal_success") is True for cell in cells),
            "invalid_cells": sum(cell.get("valid_reconstruction") is not True for cell in cells),
            "all_fresh": all(cell.get("process", {}).get("fresh_lean_process") is True for cell in cells),
            "all_attempt_one": all(cell.get("process", {}).get("attempt_ordinal") == 1 for cell in cells),
            "receipt_process_calls": row["process_calls"],
            "receipt_solved": row["solved"],
        })
    totals = {
        policy: sum(row["process_calls"] for row in reconstructed if row["policy"] == policy)
        for policy in POLICIES
    }
    solved_sets = {
        policy: {row["target_id"] for row in reconstructed if row["policy"] == policy and row["solved"]}
        for policy in POLICIES
    }
    full = totals["full"]
    effect = totals["effect_aware"]
    effect_comparison = next(
        row for row in analysis["comparisons_vs_full"] if row["policy"] == "effect_aware"
    )
    metrics_path = Path(analysis["paired_root_metrics"])
    metrics = read_jsonl(metrics_path)
    metric_by_root = {row["target_id"]: row for row in metrics}
    paired_exact = True
    for target_id in design["root_order"]:
        rows = {row["policy"]: row for row in reconstructed if row["target_id"] == target_id}
        metric = metric_by_root.get(target_id, {})
        paired_exact = paired_exact and bool(
            set(rows) == set(POLICIES)
            and metric.get("full_process_calls") == rows["full"]["process_calls"]
            and metric.get("effect_aware_process_calls") == rows["effect_aware"]["process_calls"]
            and metric.get("effect_aware_call_saving")
                == rows["full"]["process_calls"] - rows["effect_aware"]["process_calls"]
            and metric.get("effect_aware_coverage_loss")
                == (rows["full"]["solved"] and not rows["effect_aware"]["solved"])
        )
    checks = {
        "design_and_analysis_seals_exact": True,
        "all_128_jobs_reconstructed": len(reconstructed) == EXPECTED_JOBS,
        "all_cells_reconstructed": cells_reconstructed == execution["cells_recorded"],
        "cell_to_job_counts_exact": all(
            row["process_calls"] == row["receipt_process_calls"] for row in reconstructed
        ),
        "solved_labels_exact": all(row["solved"] == row["receipt_solved"] for row in reconstructed),
        "all_candidate_counts_exact": all(
            row["candidate_process_calls"] == CANDIDATES_PER_ROOT for row in reconstructed
        ),
        "all_cells_valid": all(row["invalid_cells"] == 0 for row in reconstructed),
        "all_cells_fresh_processes": all(row["all_fresh"] for row in reconstructed),
        "all_attempt_ordinals_one": all(row["all_attempt_one"] for row in reconstructed),
        "process_call_totals_exact": totals == execution["process_calls_by_policy"],
        "effect_aware_actual_call_saving_exact": (
            full - effect == analysis["efficiency_estimand"]["actual_process_calls_saved"]
            == effect_comparison["actual_process_calls_saved_vs_full"]
        ),
        "effect_aware_coverage_loss_exact": (
            len(solved_sets["full"] - solved_sets["effect_aware"])
            == analysis["coverage_estimand"]["paired_coverage_loss_roots"]
        ),
        "paired_root_metrics_hash_exact": file_sha256(metrics_path)
            == analysis["paired_root_metrics_sha256"],
        "paired_root_metrics_reconstructed_exact": paired_exact and len(metrics) == EXPECTED_PILOT_ROOTS,
        "efficiency_and_coverage_kept_separate": analysis.get(
            "efficiency_and_coverage_are_separate_estimands"
        ) is True,
        "zero_scientific_retries": execution.get("scientific_retry_count") == 0,
        "zero_manual_reconciliation": execution.get("manual_reconciliation_count") == 0,
    }
    gate = all(checks.values()) and analysis.get("analysis_gate") is True
    value = seal({
        "version": VERSION,
        "pilot_protocol_version": PILOT_PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "jobs_reconstructed": len(reconstructed),
        "cells_reconstructed": cells_reconstructed,
        "roots_reconstructed": len({row["target_id"] for row in reconstructed}),
        "process_calls_by_policy_reconstructed": totals,
        "effect_aware_calls_saved_reconstructed": full - effect,
        "effect_aware_coverage_losses_reconstructed": len(
            solved_sets["full"] - solved_sets["effect_aware"]
        ),
        "checks": checks,
        "audit_pass": gate,
        "decision_label_preserved": analysis["decision_label"],
        "manual_reconciliation_count": 0,
        "next_step": "Run frozen pilot-based power planning." if gate else "STOP; audit failed.",
    })
    atomic_json_dump(value, root / "pilot/audit/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(audit(Path(parse_args().artifact_root).resolve()), indent=2))
