"""Analyze the Exp59 pilot with efficiency and coverage kept separate."""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

from experiment59_pilot_protocol import *
from finalize_experiment59_pilot import load_and_validate_jobs


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("empty percentile")
    position = (len(ordered) - 1) * probability
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return ordered[low]
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def stratified_bootstrap_ci(rows: list[dict[str, Any]], field: str) -> list[float]:
    pools = {
        dataset: [float(row[field]) for row in rows if row["dataset"] == dataset]
        for dataset in ("minif2f", "putnambench")
    }
    rng = random.Random(ANALYSIS_BOOTSTRAP_SEED + int(json_sha256(field)[:8], 16))
    estimates = []
    for _ in range(POWER_REPLICATES):
        sample = [rng.choice(pool) for pool in pools.values() for _ in range(len(pool))]
        estimates.append(statistics.fmean(sample))
    return [percentile(estimates, 0.025), percentile(estimates, 0.975)]


def wilson_upper(failures: int, n: int, z: float = ONE_SIDED_Z) -> float:
    if n <= 0:
        return 1.0
    p = failures / n
    denominator = 1 + z * z / n
    center = p + z * z / (2 * n)
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (center + radius) / denominator


def analyze(root: Path) -> dict[str, Any]:
    execution_path = root / "pilot/execution/summary.json"
    execution = read_json(execution_path)
    assert_sealed(execution, "pilot execution summary")
    if execution.get("execution_integrity_gate") is not True:
        raise ValueError("pilot execution integrity gate failed")
    design, jobs, _ = load_and_validate_jobs(root)
    by_root: dict[str, dict[str, dict[str, Any]]] = {}
    for row in jobs:
        by_root.setdefault(row["target_id"], {})[row["policy"]] = row
    if set(by_root) != set(design["root_order"]):
        raise ValueError("pilot root accounting changed")
    paired = []
    for target_id in design["root_order"]:
        policies = by_root[target_id]
        if tuple(policies) != POLICIES:
            raise ValueError(f"pilot policies incomplete: {target_id}")
        full = policies["full"]
        effect = policies["effect_aware"]
        row: dict[str, Any] = {
            "dataset": full["dataset"], "target_id": target_id,
            "execution_integrity_gate": True,
        }
        for policy in POLICIES:
            job = policies[policy]
            prefix = policy
            row.update({
                f"{prefix}_process_calls": job["process_calls"],
                f"{prefix}_candidate_process_calls": job["candidate_process_calls"],
                f"{prefix}_downstream_process_calls": job["downstream_process_calls"],
                f"{prefix}_expanded_nodes": job["expanded_nodes"],
                f"{prefix}_solved": job["solved"],
                f"{prefix}_wall_clock_seconds_descriptive": job["wall_clock_seconds_descriptive"],
                f"{prefix}_time_to_first_proof_seconds": job["time_to_first_proof_seconds"],
                f"{prefix}_unique_endpoint_count": len(job["unique_canonical_endpoints"]),
            })
        row.update({
            "effect_aware_call_saving": full["process_calls"] - effect["process_calls"],
            "effect_aware_call_saving_fraction": (
                (full["process_calls"] - effect["process_calls"]) / full["process_calls"]
                if full["process_calls"] else 0.0
            ),
            "effect_aware_expanded_node_saving": full["expanded_nodes"] - effect["expanded_nodes"],
            "effect_aware_coverage_loss": bool(full["solved"] and not effect["solved"]),
            "effect_aware_coverage_gain": bool(effect["solved"] and not full["solved"]),
            "effect_aware_solved_exact": bool(full["solved"] == effect["solved"]),
        })
        paired.append(row)
    paired_path = root / "pilot/results/paired_root_metrics.jsonl"
    atomic_jsonl_dump(paired, paired_path)

    policy_metrics = []
    solved_sets: dict[str, set[str]] = {}
    endpoint_sets: dict[str, set[str]] = {}
    for policy in POLICIES:
        rows = [row for row in jobs if row["policy"] == policy]
        solved = {row["target_id"] for row in rows if row["solved"]}
        endpoints = {value for row in rows for value in row["unique_canonical_endpoints"]}
        solved_sets[policy] = solved
        endpoint_sets[policy] = endpoints
        times = [row["time_to_first_proof_seconds"] for row in rows if row["solved"]]
        policy_metrics.append({
            "policy": policy, "roots": len(rows),
            "candidate_process_calls": sum(row["candidate_process_calls"] for row in rows),
            "downstream_process_calls": sum(row["downstream_process_calls"] for row in rows),
            "process_calls": sum(row["process_calls"] for row in rows),
            "expanded_nodes": sum(row["expanded_nodes"] for row in rows),
            "selected_depth2_branches": sum(row["selected_depth2_branches"] for row in rows),
            "solved_roots": len(solved),
            "unique_canonical_endpoints": len(endpoints),
            "wall_clock_seconds_descriptive": sum(row["wall_clock_seconds_descriptive"] for row in rows),
            "median_time_to_first_proof_seconds": statistics.median(times) if times else None,
            "budget_exhausted_roots": sum(row["budget_exhausted"] is True for row in rows),
        })
    full_metrics = policy_metrics[0]
    comparisons = []
    for metrics in policy_metrics:
        policy = metrics["policy"]
        comparisons.append({
            "policy": policy,
            "actual_process_calls_saved_vs_full": full_metrics["process_calls"] - metrics["process_calls"],
            "actual_process_call_reduction_fraction_vs_full": (
                (full_metrics["process_calls"] - metrics["process_calls"]) / full_metrics["process_calls"]
                if full_metrics["process_calls"] else 0.0
            ),
            "expanded_nodes_saved_vs_full": full_metrics["expanded_nodes"] - metrics["expanded_nodes"],
            "solved_root_difference_vs_full": metrics["solved_roots"] - full_metrics["solved_roots"],
            "coverage_loss_roots_vs_full": len(solved_sets["full"] - solved_sets[policy]),
            "coverage_gain_roots_vs_full": len(solved_sets[policy] - solved_sets["full"]),
            "solved_root_set_exact": solved_sets[policy] == solved_sets["full"],
            "strict_endpoint_union_exact": endpoint_sets[policy] == endpoint_sets["full"],
            "wall_clock_difference_seconds_descriptive_vs_full": (
                metrics["wall_clock_seconds_descriptive"] - full_metrics["wall_clock_seconds_descriptive"]
            ),
        })
    effect = next(row for row in comparisons if row["policy"] == "effect_aware")
    effect_losses = int(effect["coverage_loss_roots_vs_full"])
    integrity = {
        "execution_summary_integrity_gate": execution["execution_integrity_gate"] is True,
        "all_128_jobs_accounted": len(jobs) == EXPECTED_JOBS,
        "all_32_roots_have_four_policies": all(set(rows) == set(POLICIES) for rows in by_root.values()),
        "all_candidate_stages_exact": all(row["candidate_stage_exact"] is True for row in jobs),
        "all_cells_valid": all(row["invalid_cells"] == 0 for row in jobs),
        "all_cells_fresh_processes": all(row["all_fresh_lean_processes"] is True for row in jobs),
        "all_attempt_ordinals_one": all(row["all_attempt_ordinals_one"] is True for row in jobs),
        "zero_scientific_retries": all(row["scientific_retry_count"] == 0 for row in jobs),
        "zero_manual_reconciliation": all(row["manual_reconciliation_count"] == 0 for row in jobs),
    }
    efficiency_estimand = {
        "unit": "root/problem; policies paired within root",
        "full_process_calls": full_metrics["process_calls"],
        "effect_aware_process_calls": next(
            row["process_calls"] for row in policy_metrics if row["policy"] == "effect_aware"
        ),
        "actual_process_calls_saved": effect["actual_process_calls_saved_vs_full"],
        "actual_process_call_reduction_fraction": effect[
            "actual_process_call_reduction_fraction_vs_full"
        ],
        "paired_mean_call_saving": statistics.fmean(
            row["effect_aware_call_saving"] for row in paired
        ),
        "paired_mean_call_saving_stratified_bootstrap_95ci": stratified_bootstrap_ci(
            paired, "effect_aware_call_saving"
        ),
    }
    coverage_estimand = {
        "unit": "root/problem; full and effect-aware paired within root",
        "full_solved_roots": full_metrics["solved_roots"],
        "effect_aware_solved_roots": next(
            row["solved_roots"] for row in policy_metrics if row["policy"] == "effect_aware"
        ),
        "paired_coverage_loss_roots": effect_losses,
        "paired_coverage_loss_fraction": effect_losses / EXPECTED_PILOT_ROOTS,
        "paired_coverage_loss_one_sided_95_upper": wilson_upper(effect_losses, EXPECTED_PILOT_ROOTS),
        "registered_noninferiority_margin": COVERAGE_NONINFERIORITY_MARGIN,
        "pilot_noninferiority_descriptive_only": wilson_upper(effect_losses, EXPECTED_PILOT_ROOTS)
            <= COVERAGE_NONINFERIORITY_MARGIN,
        "strict_endpoint_union_exact": effect["strict_endpoint_union_exact"],
    }
    gate = all(integrity.values())
    if not gate:
        label = "pilot_invalid"
    elif efficiency_estimand["actual_process_calls_saved"] <= 0:
        label = "pilot_no_actual_call_saving_detected"
    elif coverage_estimand["paired_coverage_loss_one_sided_95_upper"] <= COVERAGE_NONINFERIORITY_MARGIN:
        label = "pilot_actual_call_saving_with_descriptive_coverage_noninferiority"
    else:
        label = "pilot_actual_call_saving_with_unresolved_or_excess_coverage_loss"
    value = seal({
        "version": VERSION,
        "pilot_protocol_version": PILOT_PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "analysis_type": "prospectively frozen pilot; planning evidence, not confirmation",
        "roots": EXPECTED_PILOT_ROOTS,
        "roots_by_dataset": design["roots_by_dataset"],
        "jobs": len(jobs),
        "efficiency_estimand": efficiency_estimand,
        "coverage_estimand": coverage_estimand,
        "efficiency_and_coverage_are_separate_estimands": True,
        "policy_metrics": policy_metrics,
        "comparisons_vs_full": comparisons,
        "paired_root_metrics": str(paired_path),
        "paired_root_metrics_sha256": file_sha256(paired_path),
        "integrity_checks": integrity,
        "analysis_gate": gate,
        "decision_label": label,
        "claim_boundary": [
            "32 prospectively selected expansion-only roots balanced across miniF2F and PutnamBench",
            "four frozen policies, one frozen 21-candidate panel, and one frozen eight-probe depth-two search",
            "actual fresh Lean process calls are the primary efficiency outcome",
            "wall-clock is descriptive because policies execute in separate processes",
            "pilot outcomes determine only the prospectively frozen confirmation sample size",
            "no global tactic interchangeability or general prover-improvement claim",
        ],
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
        "next_step": "Run independent offline pilot audit." if gate else "STOP; preserve invalid pilot.",
    })
    atomic_csv_dump(policy_metrics, root / "pilot/analysis/policy_metrics.csv")
    atomic_csv_dump(comparisons, root / "pilot/analysis/comparisons_vs_full.csv")
    atomic_json_dump(value, root / "pilot/analysis/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(analyze(Path(parse_args().artifact_root).resolve()), indent=2))
