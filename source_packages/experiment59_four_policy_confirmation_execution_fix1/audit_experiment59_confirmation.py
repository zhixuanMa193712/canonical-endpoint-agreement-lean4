"""Independently reconstruct Exp59 confirmation estimands from cell receipts."""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

from experiment59_confirmation_protocol import *


def audit(root: Path) -> dict[str, Any]:
    design = load_execution_design(root)
    execution = read_json(root / "confirmation/execution/summary.json")
    analysis = read_json(root / "confirmation/analysis/summary.json")
    assert_sealed(execution, "confirmation execution"); assert_sealed(analysis, "confirmation analysis")
    reconstructed = []; cells_total = 0
    for plan in read_jsonl(design["jobs_path"]):
        job = read_json(root / "confirmation/execution/jobs" / f"{plan['job_id']}.json")
        assert_sealed(job, f"confirmation audit job {plan['job_id']}")
        if job["job"] != plan: raise ValueError("confirmation audit job plan changed")
        cells = []
        for item in job["cell_receipts"]:
            path = Path(item["path"])
            if file_sha256(path) != item["sha256"]: raise ValueError("confirmation audit cell hash changed")
            cell = read_json(path); assert_sealed(cell, f"confirmation audit cell {item['cell_id']}")
            if not (cell["cell_id"] == item["cell_id"] and cell["job_id"] == plan["job_id"]
                    and cell["target_id"] == plan["target_id"] and cell["policy"] == plan["policy"]):
                raise ValueError("confirmation audit cell identity changed")
            cells.append(cell)
        cells_total += len(cells)
        reconstructed.append({"target_id": plan["target_id"], "dataset": plan["dataset"],
            "policy": plan["policy"], "process_calls": len(cells),
            "candidate_calls": sum(cell["mode"] == "candidate_only" for cell in cells),
            "downstream_calls": sum(cell["mode"] == "candidate_probe" for cell in cells),
            "solved": any(cell.get("terminal_success") is True for cell in cells),
            "endpoints": set(job["unique_canonical_endpoints"]),
            "invalid": sum(cell.get("valid_reconstruction") is not True for cell in cells),
            "fresh": all(cell.get("process", {}).get("fresh_lean_process") is True for cell in cells),
            "attempt_one": all(cell.get("process", {}).get("attempt_ordinal") == 1 for cell in cells),
            "receipt_calls": job["process_calls"], "receipt_solved": job["solved"]})
    totals = {policy: sum(row["process_calls"] for row in reconstructed if row["policy"] == policy) for policy in POLICIES}
    by_root = {target: {row["policy"]: row for row in reconstructed if row["target_id"] == target}
               for target in design["root_order"]}
    savings = [by_root[target]["full"]["process_calls"] - by_root[target]["effect_aware"]["process_calls"]
               for target in design["root_order"]]
    mean = statistics.fmean(savings); sd = statistics.stdev(savings)
    lower = mean - ONE_SIDED_Z * sd / math.sqrt(len(savings))
    losses = sum(by_root[target]["full"]["solved"] and not by_root[target]["effect_aware"]["solved"]
                 for target in design["root_order"])
    full_solved = sum(by_root[target]["full"]["solved"] for target in design["root_order"])
    full_union = set().union(*(by_root[target]["full"]["endpoints"] for target in design["root_order"]))
    effect_union = set().union(*(by_root[target]["effect_aware"]["endpoints"] for target in design["root_order"]))
    metrics_path = Path(analysis["paired_root_metrics"]); metrics = read_jsonl(metrics_path)
    metric_map = {row["target_id"]: row for row in metrics}
    paired_exact = all(
        metric_map[target]["effect_aware_call_saving"] == savings[index]
        and metric_map[target]["effect_aware_coverage_loss"]
            == (by_root[target]["full"]["solved"] and not by_root[target]["effect_aware"]["solved"])
        for index, target in enumerate(design["root_order"])
    )
    checks = {"all_256_jobs_reconstructed": len(reconstructed) == EXPECTED_JOBS,
        "all_cells_reconstructed": cells_total == execution["cells_recorded"],
        "cell_to_job_counts_exact": all(row["process_calls"] == row["receipt_calls"] for row in reconstructed),
        "solved_labels_exact": all(row["solved"] == row["receipt_solved"] for row in reconstructed),
        "all_candidate_counts_exact": all(row["candidate_calls"] == CANDIDATES_PER_ROOT for row in reconstructed),
        "all_cells_valid": all(row["invalid"] == 0 for row in reconstructed),
        "all_cells_fresh_processes": all(row["fresh"] for row in reconstructed),
        "all_attempt_ordinals_one": all(row["attempt_one"] for row in reconstructed),
        "process_call_totals_exact": totals == execution["process_calls_by_policy"],
        "paired_mean_call_saving_exact": mean == analysis["efficiency_estimand"]["paired_mean_call_saving"],
        "registered_efficiency_bound_exact": lower == analysis["efficiency_estimand"]["registered_one_sided_95_lower"],
        "coverage_loss_count_exact": losses == analysis["coverage_estimand"]["paired_coverage_loss_roots"],
        "coverage_upper_bound_exact": wilson_upper(losses, EXPECTED_ROOTS) == analysis["coverage_estimand"]["registered_one_sided_95_upper"],
        "solve_information_gate_exact": (full_solved > 0) == analysis["coverage_estimand"]["solve_coverage_information_gate"],
        "strict_endpoint_union_exact": (full_union == effect_union) == analysis["coverage_estimand"]["strict_endpoint_union_exact"],
        "paired_metrics_hash_exact": file_sha256(metrics_path) == analysis["paired_root_metrics_sha256"],
        "paired_metrics_reconstructed_exact": len(metrics) == EXPECTED_ROOTS and paired_exact,
        "zero_scientific_retries": execution["scientific_retry_count"] == 0,
        "zero_manual_reconciliation": execution["manual_reconciliation_count"] == 0}
    gate = all(checks.values()) and analysis.get("analysis_gate") is True
    value = seal({"version": VERSION, "confirmation_protocol_version": CONFIRMATION_PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID, "roots_reconstructed": len(by_root),
        "jobs_reconstructed": len(reconstructed), "cells_reconstructed": cells_total,
        "process_calls_by_policy_reconstructed": totals,
        "effect_aware_calls_saved_reconstructed": totals["full"] - totals["effect_aware"],
        "effect_aware_coverage_losses_reconstructed": losses,
        "full_solved_roots_reconstructed": full_solved, "checks": checks,
        "audit_pass": gate, "decision_label_preserved": analysis["decision_label"],
        "manual_reconciliation_count": 0,
        "next_step": "Export immutable confirmation bundle." if gate else "STOP; audit failed."})
    atomic_json_dump(value, root / "confirmation/audit/summary.json"); return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT)); return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(audit(Path(parse_args().artifact_root).resolve()), indent=2))
