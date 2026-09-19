"""Independently reconstruct the Exp59 confirmation Fix1 results."""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

from experiment59_confirmation_fix1_protocol import *


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return ordered[low]
    return ordered[low] * (high - position) + ordered[high] * (position - low)


def _bootstrap(rows: list[dict[str, Any]]) -> list[float]:
    field = "effect_aware_call_saving"
    pools = {
        dataset: [float(row[field]) for row in rows if row["dataset"] == dataset]
        for dataset in ("minif2f", "putnambench")
    }
    rng = random.Random(BOOTSTRAP_SEED + int(json_sha256(field)[:8], 16))
    estimates = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sample = [
            rng.choice(pool)
            for pool in pools.values()
            for _ in range(len(pool))
        ]
        estimates.append(statistics.fmean(sample))
    return [_percentile(estimates, 0.025), _percentile(estimates, 0.975)]


def audit(root: Path) -> dict:
    root = Path(root).resolve()
    amendment = validate_fix1_amendment(root)
    corpus = amendment["corpus"]
    execution_path = root / FIX1_RELATIVE / "execution/summary.json"
    analysis_path = root / FIX1_RELATIVE / "analysis/summary.json"
    execution = read_json(execution_path)
    analysis = read_json(analysis_path)
    assert_sealed(execution, "Fix1 audit execution input")
    assert_sealed(analysis, "Fix1 audit analysis input")

    reconstructed = []
    cells_total = 0
    invalid_ids: set[str] = set()
    for job in corpus["jobs"]:
        cells = corpus["cells_by_job"][job["job_id"]]
        cells_total += len(cells)
        invalid_ids.update(
            cell["cell_id"]
            for cell in cells if cell.get("valid_reconstruction") is not True
        )
        candidate_endpoints = {
            cell["candidate_endpoint_sha256"]
            for cell in cells if cell.get("candidate_endpoint_sha256")
        }
        downstream_endpoints = {
            cell["probe_endpoint_sha256"]
            for cell in cells if cell.get("probe_endpoint_sha256")
        }
        reconstructed.append({
            "target_id": job["target_id"],
            "dataset": job["dataset"],
            "policy": job["policy"],
            "process_calls": len(cells),
            "candidate_calls": sum(
                cell["mode"] == "candidate_only" for cell in cells
            ),
            "downstream_calls": sum(
                cell["mode"] == "candidate_probe" for cell in cells
            ),
            "solved": any(cell.get("terminal_success") is True for cell in cells),
            "endpoints": candidate_endpoints | downstream_endpoints,
            "invalid": sum(
                cell.get("valid_reconstruction") is not True for cell in cells
            ),
            "fresh": all(
                cell.get("process", {}).get("fresh_lean_process") is True
                for cell in cells
            ),
            "attempt_one": all(
                cell.get("process", {}).get("attempt_ordinal") == 1
                for cell in cells
            ),
            "receipt_calls": job["process_calls"],
            "receipt_candidate_calls": job["candidate_process_calls"],
            "receipt_downstream_calls": job["downstream_process_calls"],
            "receipt_solved": job["solved"],
            "receipt_endpoints": set(job["unique_canonical_endpoints"]),
            "receipt_invalid": job["invalid_cells"],
        })

    totals = {
        policy: sum(
            row["process_calls"] for row in reconstructed
            if row["policy"] == policy
        )
        for policy in POLICIES
    }
    design = corpus["design"]
    by_root = {
        target: {
            row["policy"]: row
            for row in reconstructed if row["target_id"] == target
        }
        for target in design["root_order"]
    }
    paired = []
    for target in design["root_order"]:
        full = by_root[target]["full"]
        effect = by_root[target]["effect_aware"]
        paired.append({
            "dataset": full["dataset"],
            "target_id": target,
            "effect_aware_call_saving": (
                full["process_calls"] - effect["process_calls"]
            ),
        })
    savings = [float(row["effect_aware_call_saving"]) for row in paired]
    mean = statistics.fmean(savings)
    standard_deviation = statistics.stdev(savings)
    lower = mean - ONE_SIDED_Z * standard_deviation / math.sqrt(len(savings))
    bootstrap = _bootstrap(paired)

    affected = set(corpus["affected_roots"])
    evaluable = [target for target in design["root_order"] if target not in affected]
    losses = sum(
        by_root[target]["full"]["solved"]
        and not by_root[target]["effect_aware"]["solved"]
        for target in evaluable
    )
    gains = sum(
        by_root[target]["effect_aware"]["solved"]
        and not by_root[target]["full"]["solved"]
        for target in evaluable
    )
    full_solved = sum(by_root[target]["full"]["solved"] for target in evaluable)
    effect_solved = sum(
        by_root[target]["effect_aware"]["solved"] for target in evaluable
    )
    full_union = set().union(*(
        by_root[target]["full"]["endpoints"] for target in evaluable
    ))
    effect_union = set().union(*(
        by_root[target]["effect_aware"]["endpoints"] for target in evaluable
    ))
    endpoint_exact_fraction = sum(
        by_root[target]["full"]["endpoints"]
        == by_root[target]["effect_aware"]["endpoints"]
        for target in evaluable
    ) / len(evaluable)
    sensitivity_upper = wilson_upper(losses, len(evaluable))

    metrics_path = Path(analysis["paired_root_metrics"])
    metrics = read_jsonl(metrics_path)
    metric_map = {row["target_id"]: row for row in metrics}
    metrics_exact = len(metrics) == EXPECTED_ROOTS and all(
        metric_map[target]["effect_aware_call_saving"]
        == paired[index]["effect_aware_call_saving"]
        and metric_map[target]["coverage_evaluable"] == (target in evaluable)
        and metric_map[target]["effect_aware_coverage_loss"] == (
            bool(
                by_root[target]["full"]["solved"]
                and not by_root[target]["effect_aware"]["solved"]
            ) if target in evaluable else None
        )
        for index, target in enumerate(design["root_order"])
    )

    expected_decision = (
        "actual_call_efficiency_confirmed_coverage_inconclusive_due_"
        "locked_operational_anomaly"
        if lower > 0 else
        "actual_call_efficiency_not_confirmed_coverage_inconclusive_due_"
        "locked_operational_anomaly"
    )
    efficiency = analysis["efficiency_estimand"]
    coverage = analysis["coverage_estimand"]
    checks = {
        "all_256_jobs_reconstructed": len(reconstructed) == EXPECTED_JOBS,
        "all_cells_reconstructed": cells_total == execution["cells_recorded"],
        "cell_to_job_counts_exact": all(
            row["process_calls"] == row["receipt_calls"] for row in reconstructed
        ),
        "candidate_and_downstream_counts_exact": all(
            row["candidate_calls"] == row["receipt_candidate_calls"]
            and row["downstream_calls"] == row["receipt_downstream_calls"]
            for row in reconstructed
        ),
        "solved_labels_exact": all(
            row["solved"] == row["receipt_solved"] for row in reconstructed
        ),
        "endpoint_sets_exact": all(
            row["endpoints"] == row["receipt_endpoints"] for row in reconstructed
        ),
        "invalid_counts_exact": all(
            row["invalid"] == row["receipt_invalid"] for row in reconstructed
        ),
        "exact_three_locked_panics": invalid_ids == set(ANOMALY_BY_CELL),
        "all_candidate_counts_exact": all(
            row["candidate_calls"] == CANDIDATES_PER_ROOT for row in reconstructed
        ),
        "all_cells_fresh_processes": all(row["fresh"] for row in reconstructed),
        "all_attempt_ordinals_one": all(row["attempt_one"] for row in reconstructed),
        "process_call_totals_exact": totals == execution["process_calls_by_policy"],
        "paired_mean_call_saving_exact": mean == efficiency["paired_mean_call_saving"],
        "paired_call_saving_sd_exact": (
            standard_deviation == efficiency["paired_call_saving_sd"]
        ),
        "registered_efficiency_bound_exact": (
            lower == efficiency["registered_one_sided_95_lower"]
        ),
        "efficiency_bootstrap_exact": (
            bootstrap == efficiency["paired_mean_call_saving_stratified_bootstrap_95ci"]
        ),
        "effect_aware_calls_saved_exact": (
            totals["full"] - totals["effect_aware"]
            == efficiency["actual_process_calls_saved"]
        ),
        "coverage_evaluable_root_count_exact": (
            len(evaluable) == coverage["evaluable_roots"] == 63
        ),
        "coverage_loss_count_exact": (
            losses == coverage["paired_coverage_loss_evaluable_roots"]
        ),
        "coverage_gain_count_exact": (
            gains == coverage["paired_coverage_gain_evaluable_roots"]
        ),
        "coverage_complete_case_upper_exact": (
            sensitivity_upper
            == coverage["nonregistered_complete_case_one_sided_95_upper"]
        ),
        "solved_counts_exact": (
            full_solved == coverage["full_solved_evaluable_roots"]
            and effect_solved == coverage["effect_aware_solved_evaluable_roots"]
        ),
        "endpoint_union_exact": (
            (full_union == effect_union)
            == coverage["strict_endpoint_union_exact_on_evaluable_roots"]
        ),
        "endpoint_fraction_exact": (
            endpoint_exact_fraction
            == coverage["per_root_endpoint_set_exact_fraction_on_evaluable_roots"]
        ),
        "registered_coverage_remains_inconclusive": (
            coverage["registered_estimand_status"]
            == "inconclusive_due_locked_operational_anomaly"
            and coverage["registered_one_sided_95_upper"] is None
            and coverage["registered_coverage_gate"] is False
            and coverage["missing_root_imputed"] is False
            and coverage["panic_counted_as_tactic_failure"] is False
        ),
        "paired_metrics_hash_exact": (
            file_sha256(metrics_path) == analysis["paired_root_metrics_sha256"]
        ),
        "paired_metrics_reconstructed_exact": metrics_exact,
        "policy_metrics_csv_hash_exact": (
            file_sha256(analysis["policy_metrics_csv"])
            == analysis["policy_metrics_csv_sha256"]
        ),
        "comparisons_csv_hash_exact": (
            file_sha256(analysis["comparisons_csv"])
            == analysis["comparisons_csv_sha256"]
        ),
        "decision_label_exact": analysis["decision_label"] == expected_decision,
        "registered_joint_gate_false": analysis["registered_joint_gate"] is False,
        "zero_scientific_retries": execution["scientific_retry_count"] == 0,
        "zero_manual_reconciliation": execution["manual_reconciliation_count"] == 0,
        "original_receipts_unmodified": amendment["original_receipts_rewritten"] is False,
    }
    gate = all(checks.values()) and analysis.get("analysis_gate") is True
    value = seal({
        "version": FIX1_VERSION,
        "fix1_protocol_version": FIX1_PROTOCOL_VERSION,
        "mechanical_fix_id": FIX1_MECHANICAL_ID,
        "amendment_sha256": amendment["sha256"],
        "execution_summary_sha256": file_sha256(execution_path),
        "analysis_sha256": file_sha256(analysis_path),
        "roots_reconstructed": len(by_root),
        "coverage_evaluable_roots_reconstructed": len(evaluable),
        "jobs_reconstructed": len(reconstructed),
        "cells_reconstructed": cells_total,
        "locked_operational_anomaly_cells_reconstructed": len(invalid_ids),
        "affected_roots_reconstructed": sorted(affected),
        "process_calls_by_policy_reconstructed": totals,
        "effect_aware_calls_saved_reconstructed": (
            totals["full"] - totals["effect_aware"]
        ),
        "effect_aware_coverage_losses_on_evaluable_roots_reconstructed": losses,
        "checks": checks,
        "audit_pass": gate,
        "decision_label_preserved": analysis["decision_label"],
        "lean_executed_by_fix1": False,
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
        "next_step": (
            "Export immutable Fix1 confirmation bundle."
            if gate else "STOP; Fix1 audit failed."
        ),
    })
    atomic_json_dump(value, root / FIX1_RELATIVE / "audit/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(audit(Path(parse_args().artifact_root)), indent=2))
