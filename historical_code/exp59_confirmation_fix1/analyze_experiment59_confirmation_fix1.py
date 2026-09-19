"""Analyze Exp59 confirmation with locked operational anomalies retained."""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

from experiment59_confirmation_fix1_protocol import *


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return ordered[low]
    return (
        ordered[low] * (high - position)
        + ordered[high] * (position - low)
    )


def bootstrap_ci(rows: list[dict[str, Any]], field: str) -> list[float]:
    pools = {
        dataset: [float(row[field]) for row in rows if row["dataset"] == dataset]
        for dataset in ("minif2f", "putnambench")
    }
    if any(not pool for pool in pools.values()):
        raise ValueError("stratified bootstrap dataset pool is empty")
    rng = random.Random(BOOTSTRAP_SEED + int(json_sha256(field)[:8], 16))
    estimates = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sample = [
            rng.choice(pool)
            for pool in pools.values()
            for _ in range(len(pool))
        ]
        estimates.append(statistics.fmean(sample))
    return [percentile(estimates, 0.025), percentile(estimates, 0.975)]


def analyze(root: Path) -> dict:
    root = Path(root).resolve()
    amendment = validate_fix1_amendment(root)
    corpus = amendment["corpus"]
    execution_path = root / FIX1_RELATIVE / "execution/summary.json"
    execution = read_json(execution_path)
    assert_sealed(execution, "Exp59 confirmation Fix1 execution")
    if not (
        execution.get("fix1_execution_accounting_gate") is True
        and execution.get("amendment_sha256") == amendment["sha256"]
        and execution.get("source_job_ledger_sha256")
        == corpus["job_ledger_sha256"]
        and execution.get("locked_operational_anomaly_cells") == 3
        and execution.get("registered_coverage_execution_gate") is False
    ):
        raise ValueError("Exp59 confirmation Fix1 execution accounting failed")

    design = corpus["design"]
    jobs = corpus["jobs"]
    by_root: dict[str, dict[str, dict[str, Any]]] = {}
    for job in jobs:
        by_root.setdefault(job["target_id"], {})[job["policy"]] = job
    if set(by_root) != set(design["root_order"]):
        raise ValueError("Fix1 confirmation root accounting changed")
    if not all(set(rows) == set(POLICIES) for rows in by_root.values()):
        raise ValueError("Fix1 confirmation policy accounting changed")

    affected = set(corpus["affected_roots"])
    evaluable = [target for target in design["root_order"] if target not in affected]
    paired = []
    for target_id in design["root_order"]:
        policies = by_root[target_id]
        full = policies["full"]
        effect = policies["effect_aware"]
        coverage_evaluable = target_id not in affected
        row: dict[str, Any] = {
            "dataset": full["dataset"],
            "target_id": target_id,
            "efficiency_evaluable": True,
            "coverage_evaluable": coverage_evaluable,
            "operational_anomaly_cell_count": sum(
                policies[policy]["invalid_cells"] for policy in POLICIES
            ),
        }
        for policy in POLICIES:
            job = policies[policy]
            row.update({
                f"{policy}_process_calls": job["process_calls"],
                f"{policy}_downstream_process_calls": job["downstream_process_calls"],
                f"{policy}_solved_receipt_descriptive": job["solved"],
                f"{policy}_unique_endpoint_count_receipt_descriptive": len(
                    job["unique_canonical_endpoints"]
                ),
                f"{policy}_wall_clock_seconds_descriptive":
                    job["wall_clock_seconds_descriptive"],
            })
        row.update({
            "effect_aware_call_saving": (
                full["process_calls"] - effect["process_calls"]
            ),
            "effect_aware_coverage_loss": (
                bool(full["solved"] and not effect["solved"])
                if coverage_evaluable else None
            ),
            "effect_aware_coverage_gain": (
                bool(effect["solved"] and not full["solved"])
                if coverage_evaluable else None
            ),
            "effect_aware_endpoint_set_exact": (
                set(full["unique_canonical_endpoints"])
                == set(effect["unique_canonical_endpoints"])
                if coverage_evaluable else None
            ),
        })
        paired.append(row)

    metrics_path = root / FIX1_RELATIVE / "results/paired_root_metrics.jsonl"
    atomic_jsonl_dump(paired, metrics_path)

    policy_metrics = []
    solved_sets: dict[str, set[str]] = {}
    endpoint_sets: dict[str, set[str]] = {}
    for policy in POLICIES:
        rows = [job for job in jobs if job["policy"] == policy]
        solved = {
            job["target_id"] for job in rows
            if job["target_id"] in evaluable and job["solved"]
        }
        endpoints = {
            endpoint
            for job in rows if job["target_id"] in evaluable
            for endpoint in job["unique_canonical_endpoints"]
        }
        solved_sets[policy] = solved
        endpoint_sets[policy] = endpoints
        policy_metrics.append({
            "policy": policy,
            "efficiency_roots": len(rows),
            "coverage_evaluable_roots": len(evaluable),
            "coverage_unevaluable_roots": len(affected),
            "candidate_process_calls": sum(job["candidate_process_calls"] for job in rows),
            "downstream_process_calls": sum(job["downstream_process_calls"] for job in rows),
            "process_calls": sum(job["process_calls"] for job in rows),
            "expanded_nodes": sum(job["expanded_nodes"] for job in rows),
            "selected_depth2_branches": sum(job["selected_depth2_branches"] for job in rows),
            "solved_evaluable_roots": len(solved),
            "solved_receipt_roots_descriptive": sum(job["solved"] for job in rows),
            "unique_canonical_endpoints_on_evaluable_roots": len(endpoints),
            "wall_clock_seconds_descriptive": sum(
                job["wall_clock_seconds_descriptive"] for job in rows
            ),
            "budget_exhausted_roots": sum(job["budget_exhausted"] is True for job in rows),
            "locked_operational_anomaly_cells": sum(job["invalid_cells"] for job in rows),
        })

    full_metrics = next(row for row in policy_metrics if row["policy"] == "full")
    comparisons = []
    for metrics in policy_metrics:
        policy = metrics["policy"]
        saved = full_metrics["process_calls"] - metrics["process_calls"]
        per_root_endpoint_exact = [
            set(by_root[target][policy]["unique_canonical_endpoints"])
            == set(by_root[target]["full"]["unique_canonical_endpoints"])
            for target in evaluable
        ]
        comparisons.append({
            "policy": policy,
            "efficiency_roots": EXPECTED_ROOTS,
            "coverage_evaluable_roots": len(evaluable),
            "coverage_unevaluable_roots": len(affected),
            "actual_process_calls_saved_vs_full": saved,
            "actual_process_call_reduction_fraction_vs_full": (
                saved / full_metrics["process_calls"]
                if full_metrics["process_calls"] else 0.0
            ),
            "expanded_nodes_saved_vs_full": (
                full_metrics["expanded_nodes"] - metrics["expanded_nodes"]
            ),
            "coverage_loss_evaluable_roots_vs_full": len(
                solved_sets["full"] - solved_sets[policy]
            ),
            "coverage_gain_evaluable_roots_vs_full": len(
                solved_sets[policy] - solved_sets["full"]
            ),
            "solved_root_set_exact_on_evaluable_roots": (
                solved_sets[policy] == solved_sets["full"]
            ),
            "strict_endpoint_union_exact_on_evaluable_roots": (
                endpoint_sets[policy] == endpoint_sets["full"]
            ),
            "per_root_endpoint_set_exact_fraction_on_evaluable_roots": (
                sum(per_root_endpoint_exact) / len(per_root_endpoint_exact)
            ),
            "wall_clock_difference_seconds_descriptive_vs_full": (
                metrics["wall_clock_seconds_descriptive"]
                - full_metrics["wall_clock_seconds_descriptive"]
            ),
        })

    effect_comparison = next(
        row for row in comparisons if row["policy"] == "effect_aware"
    )
    savings = [float(row["effect_aware_call_saving"]) for row in paired]
    mean = statistics.fmean(savings)
    standard_deviation = statistics.stdev(savings)
    lower = mean - ONE_SIDED_Z * standard_deviation / math.sqrt(len(savings))
    efficiency = {
        "unit": "root/problem; policies paired within root",
        "registered_roots": EXPECTED_ROOTS,
        "evaluable_roots": EXPECTED_ROOTS,
        "full_process_calls": full_metrics["process_calls"],
        "effect_aware_process_calls": next(
            row["process_calls"] for row in policy_metrics
            if row["policy"] == "effect_aware"
        ),
        "actual_process_calls_saved": effect_comparison[
            "actual_process_calls_saved_vs_full"
        ],
        "actual_process_call_reduction_fraction": effect_comparison[
            "actual_process_call_reduction_fraction_vs_full"
        ],
        "paired_mean_call_saving": mean,
        "paired_call_saving_sd": standard_deviation,
        "paired_mean_call_saving_stratified_bootstrap_95ci": bootstrap_ci(
            paired, "effect_aware_call_saving"
        ),
        "registered_one_sided_95_lower": lower,
        "registered_efficiency_gate": lower > 0,
        "operational_anomaly_effect": (
            "none on process-call accounting; each launched process remains an actual call"
        ),
    }

    evaluable_rows = [row for row in paired if row["coverage_evaluable"]]
    losses = sum(row["effect_aware_coverage_loss"] is True for row in evaluable_rows)
    gains = sum(row["effect_aware_coverage_gain"] is True for row in evaluable_rows)
    full_solved = len(solved_sets["full"])
    effect_solved = len(solved_sets["effect_aware"])
    sensitivity_upper = wilson_upper(losses, len(evaluable_rows))
    coverage = {
        "unit": "root/problem; full and effect-aware paired within root",
        "registered_roots": EXPECTED_ROOTS,
        "evaluable_roots": len(evaluable_rows),
        "unevaluable_roots": len(affected),
        "unevaluable_root_ids": sorted(affected),
        "unevaluable_reason": (
            "one frozen root contains the same deterministic Lean internal panic "
            "under full, effect-aware, and head-dedup execution"
        ),
        "registered_estimand_status": "inconclusive_due_locked_operational_anomaly",
        "registered_one_sided_95_upper": None,
        "registered_noninferiority_margin": COVERAGE_NONINFERIORITY_MARGIN,
        "registered_coverage_gate": False,
        "full_solved_evaluable_roots": full_solved,
        "effect_aware_solved_evaluable_roots": effect_solved,
        "paired_coverage_loss_evaluable_roots": losses,
        "paired_coverage_gain_evaluable_roots": gains,
        "paired_coverage_loss_fraction_evaluable_roots": (
            losses / len(evaluable_rows)
        ),
        "nonregistered_complete_case_one_sided_95_upper": sensitivity_upper,
        "nonregistered_complete_case_noninferiority_descriptive": (
            sensitivity_upper <= COVERAGE_NONINFERIORITY_MARGIN
        ),
        "solve_coverage_information_gate_on_evaluable_roots": full_solved > 0,
        "strict_endpoint_union_exact_on_evaluable_roots": effect_comparison[
            "strict_endpoint_union_exact_on_evaluable_roots"
        ],
        "per_root_endpoint_set_exact_fraction_on_evaluable_roots": effect_comparison[
            "per_root_endpoint_set_exact_fraction_on_evaluable_roots"
        ],
        "missing_root_imputed": False,
        "panic_counted_as_tactic_failure": False,
    }

    integrity = {
        "fix1_execution_accounting_gate": execution[
            "fix1_execution_accounting_gate"
        ] is True,
        "all_256_jobs_accounted": len(jobs) == EXPECTED_JOBS,
        "all_64_roots_have_four_policies": all(
            set(rows) == set(POLICIES) for rows in by_root.values()
        ),
        "exactly_three_locked_operational_anomaly_cells": (
            sum(job["invalid_cells"] for job in jobs) == 3
        ),
        "exactly_one_coverage_unevaluable_root": len(affected) == 1,
        "all_candidate_stages_exact": all(
            job["candidate_stage_exact"] is True for job in jobs
        ),
        "all_cells_fresh_processes": all(
            job["all_fresh_lean_processes"] is True for job in jobs
        ),
        "all_attempt_ordinals_one": all(
            job["all_attempt_ordinals_one"] is True for job in jobs
        ),
        "zero_scientific_retries": all(
            job["scientific_retry_count"] == 0 for job in jobs
        ),
        "zero_manual_reconciliation": all(
            job["manual_reconciliation_count"] == 0 for job in jobs
        ),
        "original_receipts_unmodified": amendment[
            "original_receipts_rewritten"
        ] is False,
    }
    analysis_gate = all(integrity.values())
    registered_joint_gate = False
    if not analysis_gate:
        decision = "confirmation_invalid"
    elif efficiency["registered_efficiency_gate"]:
        decision = (
            "actual_call_efficiency_confirmed_coverage_inconclusive_due_"
            "locked_operational_anomaly"
        )
    else:
        decision = (
            "actual_call_efficiency_not_confirmed_coverage_inconclusive_due_"
            "locked_operational_anomaly"
        )

    policy_path = root / FIX1_RELATIVE / "analysis/policy_metrics.csv"
    comparisons_path = root / FIX1_RELATIVE / "analysis/comparisons_vs_full.csv"
    atomic_csv_dump(policy_metrics, policy_path)
    atomic_csv_dump(comparisons, comparisons_path)
    value = seal({
        "version": FIX1_VERSION,
        "fix1_protocol_version": FIX1_PROTOCOL_VERSION,
        "mechanical_fix_id": FIX1_MECHANICAL_ID,
        "source_confirmation_protocol_version": CONFIRMATION_PROTOCOL_VERSION,
        "analysis_type": (
            "prospectively frozen disjoint confirmation with a post-execution "
            "locked operational-anomaly amendment"
        ),
        "amendment_sha256": amendment["sha256"],
        "execution_summary_sha256": file_sha256(execution_path),
        "roots": EXPECTED_ROOTS,
        "roots_per_dataset": ROOTS_PER_DATASET,
        "jobs": len(jobs),
        "locked_operational_anomaly_cells": 3,
        "coverage_unevaluable_roots": len(affected),
        "efficiency_estimand": efficiency,
        "coverage_estimand": coverage,
        "efficiency_and_coverage_are_separate_estimands": True,
        "registered_joint_gate": registered_joint_gate,
        "policy_metrics": policy_metrics,
        "comparisons_vs_full": comparisons,
        "paired_root_metrics": str(metrics_path),
        "paired_root_metrics_sha256": file_sha256(metrics_path),
        "policy_metrics_csv": str(policy_path),
        "policy_metrics_csv_sha256": file_sha256(policy_path),
        "comparisons_csv": str(comparisons_path),
        "comparisons_csv_sha256": file_sha256(comparisons_path),
        "integrity_checks": integrity,
        "analysis_gate": analysis_gate,
        "decision_label": decision,
        "claim_boundary": [
            "actual process-call efficiency is evaluated on all 64 frozen roots",
            "coverage and strict-endpoint comparisons are complete-case sensitivity results on 63 roots",
            "the registered 64-root coverage noninferiority estimand is inconclusive",
            "three identical Lean internal-panic cells on one root are retained as operational anomalies",
            "no panic is recoded as a tactic failure and no missing outcome is imputed",
            "no root, cell, or receipt was deleted, rewritten, retried, or manually reconciled",
            "no global tactic interchangeability or general prover-improvement claim",
        ],
        "lean_executed_by_fix1": False,
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
        "next_step": (
            "Run independent Fix1 reconstruction audit."
            if analysis_gate else "STOP; preserve failed Fix1 analysis."
        ),
    })
    atomic_json_dump(value, root / FIX1_RELATIVE / "analysis/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(analyze(Path(parse_args().artifact_root)), indent=2))
