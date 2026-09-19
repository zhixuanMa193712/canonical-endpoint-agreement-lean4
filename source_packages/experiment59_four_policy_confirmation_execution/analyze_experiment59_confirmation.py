"""Run registered Exp59 confirmation analysis with explicit information checks."""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

from experiment59_confirmation_protocol import *
from finalize_experiment59_confirmation import load_jobs


def percentile(values: list[float], p: float) -> float:
    values = sorted(values); position = (len(values) - 1) * p
    low = int(math.floor(position)); high = int(math.ceil(position))
    return values[low] if low == high else values[low] * (high - position) + values[high] * (position - low)


def bootstrap_ci(rows: list[dict[str, Any]], field: str) -> list[float]:
    pools = {dataset: [float(row[field]) for row in rows if row["dataset"] == dataset]
             for dataset in ("minif2f", "putnambench")}
    rng = random.Random(BOOTSTRAP_SEED + int(json_sha256(field)[:8], 16)); estimates = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sample = [rng.choice(pool) for pool in pools.values() for _ in range(len(pool))]
        estimates.append(statistics.fmean(sample))
    return [percentile(estimates, 0.025), percentile(estimates, 0.975)]


def analyze(root: Path) -> dict[str, Any]:
    execution = read_json(root / "confirmation/execution/summary.json"); assert_sealed(execution, "confirmation execution")
    if execution.get("execution_integrity_gate") is not True: raise ValueError("confirmation execution failed")
    design, jobs, _ = load_jobs(root); by_root: dict[str, dict[str, dict[str, Any]]] = {}
    for row in jobs: by_root.setdefault(row["target_id"], {})[row["policy"]] = row
    if set(by_root) != set(design["root_order"]): raise ValueError("confirmation root accounting changed")
    paired = []
    for target_id in design["root_order"]:
        policies = by_root[target_id]
        if set(policies) != set(POLICIES): raise ValueError("confirmation policies incomplete")
        full = policies["full"]; effect = policies["effect_aware"]
        row: dict[str, Any] = {"dataset": full["dataset"], "target_id": target_id, "execution_integrity_gate": True}
        for policy in POLICIES:
            job = policies[policy]
            row.update({f"{policy}_process_calls": job["process_calls"],
                        f"{policy}_downstream_process_calls": job["downstream_process_calls"],
                        f"{policy}_solved": job["solved"],
                        f"{policy}_unique_endpoint_count": len(job["unique_canonical_endpoints"]),
                        f"{policy}_wall_clock_seconds_descriptive": job["wall_clock_seconds_descriptive"]})
        row.update({
            "effect_aware_call_saving": full["process_calls"] - effect["process_calls"],
            "effect_aware_coverage_loss": bool(full["solved"] and not effect["solved"]),
            "effect_aware_coverage_gain": bool(effect["solved"] and not full["solved"]),
            "effect_aware_endpoint_set_exact": set(full["unique_canonical_endpoints"]) == set(effect["unique_canonical_endpoints"]),
        }); paired.append(row)
    metrics_path = root / "confirmation/results/paired_root_metrics.jsonl"; atomic_jsonl_dump(paired, metrics_path)
    policy_metrics = []; solved_sets = {}; endpoint_sets = {}
    for policy in POLICIES:
        rows = [row for row in jobs if row["policy"] == policy]
        solved = {row["target_id"] for row in rows if row["solved"]}
        endpoints = {endpoint for row in rows for endpoint in row["unique_canonical_endpoints"]}
        solved_sets[policy] = solved; endpoint_sets[policy] = endpoints
        policy_metrics.append({"policy": policy, "roots": len(rows),
            "candidate_process_calls": sum(row["candidate_process_calls"] for row in rows),
            "downstream_process_calls": sum(row["downstream_process_calls"] for row in rows),
            "process_calls": sum(row["process_calls"] for row in rows),
            "expanded_nodes": sum(row["expanded_nodes"] for row in rows),
            "selected_depth2_branches": sum(row["selected_depth2_branches"] for row in rows),
            "solved_roots": len(solved), "unique_canonical_endpoints": len(endpoints),
            "wall_clock_seconds_descriptive": sum(row["wall_clock_seconds_descriptive"] for row in rows),
            "budget_exhausted_roots": sum(row["budget_exhausted"] is True for row in rows)})
    full_metrics = policy_metrics[0]; comparisons = []
    for metrics in policy_metrics:
        policy = metrics["policy"]; saved = full_metrics["process_calls"] - metrics["process_calls"]
        comparisons.append({"policy": policy, "actual_process_calls_saved_vs_full": saved,
            "actual_process_call_reduction_fraction_vs_full": saved / full_metrics["process_calls"] if full_metrics["process_calls"] else 0.0,
            "expanded_nodes_saved_vs_full": full_metrics["expanded_nodes"] - metrics["expanded_nodes"],
            "coverage_loss_roots_vs_full": len(solved_sets["full"] - solved_sets[policy]),
            "coverage_gain_roots_vs_full": len(solved_sets[policy] - solved_sets["full"]),
            "solved_root_set_exact": solved_sets[policy] == solved_sets["full"],
            "strict_endpoint_union_exact": endpoint_sets[policy] == endpoint_sets["full"],
            "per_root_endpoint_set_exact_fraction": sum(
                set(by_root[target][policy]["unique_canonical_endpoints"])
                == set(by_root[target]["full"]["unique_canonical_endpoints"])
                for target in design["root_order"]) / EXPECTED_ROOTS,
            "wall_clock_difference_seconds_descriptive_vs_full": metrics["wall_clock_seconds_descriptive"] - full_metrics["wall_clock_seconds_descriptive"]})
    effect_comparison = next(row for row in comparisons if row["policy"] == "effect_aware")
    savings = [float(row["effect_aware_call_saving"]) for row in paired]
    mean = statistics.fmean(savings); sd = statistics.stdev(savings); lower = mean - ONE_SIDED_Z * sd / math.sqrt(len(savings))
    losses = int(effect_comparison["coverage_loss_roots_vs_full"]); coverage_upper = wilson_upper(losses, EXPECTED_ROOTS)
    efficiency = {"unit": "root/problem; policies paired within root",
        "full_process_calls": full_metrics["process_calls"],
        "effect_aware_process_calls": next(row["process_calls"] for row in policy_metrics if row["policy"] == "effect_aware"),
        "actual_process_calls_saved": effect_comparison["actual_process_calls_saved_vs_full"],
        "actual_process_call_reduction_fraction": effect_comparison["actual_process_call_reduction_fraction_vs_full"],
        "paired_mean_call_saving": mean, "paired_call_saving_sd": sd,
        "paired_mean_call_saving_stratified_bootstrap_95ci": bootstrap_ci(paired, "effect_aware_call_saving"),
        "registered_one_sided_95_lower": lower, "registered_efficiency_gate": lower > 0}
    full_solved = full_metrics["solved_roots"]
    coverage = {"unit": "root/problem; policies paired within root",
        "full_solved_roots": full_solved,
        "effect_aware_solved_roots": next(row["solved_roots"] for row in policy_metrics if row["policy"] == "effect_aware"),
        "paired_coverage_loss_roots": losses, "paired_coverage_loss_fraction": losses / EXPECTED_ROOTS,
        "registered_one_sided_95_upper": coverage_upper,
        "registered_noninferiority_margin": COVERAGE_NONINFERIORITY_MARGIN,
        "registered_coverage_gate": coverage_upper <= COVERAGE_NONINFERIORITY_MARGIN,
        "solve_coverage_information_gate": full_solved > 0,
        "strict_endpoint_union_exact": effect_comparison["strict_endpoint_union_exact"],
        "per_root_endpoint_set_exact_fraction": effect_comparison["per_root_endpoint_set_exact_fraction"]}
    integrity = {"execution_integrity_gate": execution["execution_integrity_gate"] is True,
        "all_256_jobs_accounted": len(jobs) == EXPECTED_JOBS,
        "all_64_roots_have_four_policies": all(set(rows) == set(POLICIES) for rows in by_root.values()),
        "all_cells_valid": all(row["invalid_cells"] == 0 for row in jobs),
        "all_candidate_stages_exact": all(row["candidate_stage_exact"] is True for row in jobs),
        "all_cells_fresh_processes": all(row["all_fresh_lean_processes"] is True for row in jobs),
        "all_attempt_ordinals_one": all(row["all_attempt_ordinals_one"] is True for row in jobs),
        "zero_scientific_retries": all(row["scientific_retry_count"] == 0 for row in jobs),
        "zero_manual_reconciliation": all(row["manual_reconciliation_count"] == 0 for row in jobs)}
    analysis_gate = all(integrity.values()); registered_joint = efficiency["registered_efficiency_gate"] and coverage["registered_coverage_gate"]
    if not analysis_gate: decision = "confirmation_invalid"
    elif not efficiency["registered_efficiency_gate"]: decision = "actual_call_efficiency_not_confirmed"
    elif not coverage["registered_coverage_gate"]: decision = "call_efficiency_confirmed_but_coverage_noninferiority_failed"
    elif not coverage["solve_coverage_information_gate"]:
        decision = "call_efficiency_confirmed_with_endpoint_preservation_but_solve_coverage_uninformative"
    elif coverage["strict_endpoint_union_exact"]:
        decision = "call_efficiency_and_coverage_noninferiority_confirmed_with_endpoint_preservation"
    else: decision = "call_efficiency_and_solved_coverage_noninferiority_confirmed_with_endpoint_loss"
    value = seal({"version": VERSION, "confirmation_protocol_version": CONFIRMATION_PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID, "analysis_type": "prospectively frozen disjoint confirmation",
        "roots": EXPECTED_ROOTS, "roots_per_dataset": ROOTS_PER_DATASET, "jobs": len(jobs),
        "efficiency_estimand": efficiency, "coverage_estimand": coverage,
        "efficiency_and_coverage_are_separate_estimands": True,
        "registered_joint_gate": registered_joint, "policy_metrics": policy_metrics,
        "comparisons_vs_full": comparisons, "paired_root_metrics": str(metrics_path),
        "paired_root_metrics_sha256": file_sha256(metrics_path), "integrity_checks": integrity,
        "analysis_gate": analysis_gate, "decision_label": decision,
        "claim_boundary": ["64 prospectively selected roots disjoint from the 32-root pilot",
            "two external benchmark datasets balanced 32 plus 32",
            "fresh Lean process calls are the primary efficiency outcome",
            "a zero full-policy solve count makes solve-coverage preservation practically uninformative",
            "strict canonical endpoint preservation is reported separately",
            "no global tactic interchangeability or general prover-improvement claim"],
        "scientific_retry_count": 0, "manual_reconciliation_count": 0,
        "next_step": "Run independent confirmation reconstruction audit." if analysis_gate else "STOP; preserve invalid confirmation."})
    atomic_csv_dump(policy_metrics, root / "confirmation/analysis/policy_metrics.csv")
    atomic_csv_dump(comparisons, root / "confirmation/analysis/comparisons_vs_full.csv")
    atomic_json_dump(value, root / "confirmation/analysis/summary.json"); return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT)); return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(analyze(Path(parse_args().artifact_root).resolve()), indent=2))
