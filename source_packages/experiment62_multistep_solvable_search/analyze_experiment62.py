"""Analyze Exp62 pilot or confirmation at the independent theorem-root level."""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

from experiment62_protocol import *


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return ordered[low]
    return ordered[low] * (high - position) + ordered[high] * (position - low)


def wilson_interval(successes: int, n: int, z: float = 1.959963984540054) -> list[float]:
    if n <= 0:
        return [0.0, 1.0]
    p = successes / n
    denominator = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return [max(0.0, center - radius), min(1.0, center + radius)]


def bootstrap_saving(rows: list[dict[str, Any]]) -> list[float] | None:
    pools = {
        stratum: [float(row["effect_aware_call_saving"]) for row in rows
                  if row["stratum"] == stratum and row["efficiency_complete"]]
        for stratum in STRATA
    }
    if any(not pool for pool in pools.values()):
        return None
    rng = random.Random(BOOTSTRAP_SEED)
    estimates = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sample = [rng.choice(pool) for pool in pools.values() for _ in range(len(pool))]
        estimates.append(statistics.fmean(sample))
    return [percentile(estimates, 0.025), percentile(estimates, 0.975)]


def analyze(root: Path, phase: str) -> dict[str, Any]:
    design_path = root / phase / "frozen/design.json"
    design = read_json(design_path)
    assert_sealed(design, f"Exp62 {phase} design")
    jobs = read_jsonl(design["jobs_path"])
    by_root: dict[str, dict[str, dict[str, Any]]] = {}
    for job in jobs:
        path = root / phase / "execution/jobs" / f"{job['job_id']}.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        row = read_json(path)
        assert_sealed(row, f"Exp62 job {job['job_id']}")
        if row.get("job") != job:
            raise ValueError("Exp62 job receipt differs from frozen plan")
        by_root.setdefault(job["target_id"], {})[job["policy"]] = row
    if set(by_root) != set(design["root_order"]):
        raise ValueError("Exp62 root accounting changed")
    if not all(set(rows) == set(POLICIES) for rows in by_root.values()):
        raise ValueError("Exp62 policy accounting changed")

    paired = []
    for target_id in design["root_order"]:
        policies = by_root[target_id]
        full = policies["full"]
        effect = policies["effect_aware"]
        coverage_complete = bool(
            full.get("coverage_evaluable") is True
            and effect.get("coverage_evaluable") is True
        )
        efficiency_complete = bool(
            full.get("efficiency_evaluable") is True
            and effect.get("efficiency_evaluable") is True
        )
        missing_worst_case_loss = not coverage_complete
        row = {
            "target_id": target_id,
            "theorem_id": full["theorem_id"],
            "stratum": full["stratum"],
            "coverage_complete": coverage_complete,
            "efficiency_complete": efficiency_complete,
            "full_solved": full.get("solved") is True,
            "effect_aware_solved": effect.get("solved") is True,
            "full_multistep_solved": full.get("multi_step_solved") is True,
            "effect_aware_multistep_solved": effect.get("multi_step_solved") is True,
            "registered_coverage_loss": (
                True if missing_worst_case_loss
                else full.get("solved") is True and effect.get("solved") is not True
            ),
            "registered_missing_worst_case_loss": missing_worst_case_loss,
            "coverage_gain": (
                coverage_complete
                and effect.get("solved") is True and full.get("solved") is not True
            ),
            "full_tactic_invocations": int(full.get("tactic_invocations", 0)),
            "effect_aware_tactic_invocations": int(effect.get("tactic_invocations", 0)),
            "effect_aware_call_saving": (
                int(full.get("tactic_invocations", 0)) - int(effect.get("tactic_invocations", 0))
                if efficiency_complete else None
            ),
            "effect_aware_endpoint_set_exact": (
                set(full.get("unique_observed_endpoint_keys", []))
                == set(effect.get("unique_observed_endpoint_keys", []))
                if coverage_complete else False
            ),
        }
        for policy in POLICIES:
            job = policies[policy]
            row.update({
                f"{policy}_solved": job.get("solved") is True,
                f"{policy}_proof_length": job.get("proof_length"),
                f"{policy}_tactic_invocations": int(job.get("tactic_invocations", 0)),
                f"{policy}_expanded_nodes": int(job.get("expanded_nodes", 0)),
                f"{policy}_wall_clock_seconds": float(job.get("wall_clock_seconds_descriptive", 0.0)),
                f"{policy}_operational_failure": job.get("operational_failure") is True,
            })
        paired.append(row)
    paired_path = root / phase / "analysis/paired_root_metrics.jsonl"
    atomic_jsonl_dump(paired, paired_path)

    policy_metrics = []
    for policy in POLICIES:
        rows = [by_root[target_id][policy] for target_id in design["root_order"]]
        solved = sum(row.get("solved") is True for row in rows)
        multistep = sum(row.get("multi_step_solved") is True for row in rows)
        policy_metrics.append({
            "policy": policy,
            "roots": len(rows),
            "evaluable_roots": sum(row.get("coverage_evaluable") is True for row in rows),
            "operational_failure_roots": sum(row.get("operational_failure") is True for row in rows),
            "solved_roots_missing_as_unsolved": solved,
            "solve_rate_missing_as_unsolved": solved / len(rows),
            "solve_rate_wilson_95ci": json.dumps(wilson_interval(solved, len(rows))),
            "multistep_solved_roots_missing_as_unsolved": multistep,
            "multistep_solve_rate_missing_as_unsolved": multistep / len(rows),
            "tactic_invocations": sum(int(row.get("tactic_invocations", 0)) for row in rows),
            "expanded_nodes": sum(int(row.get("expanded_nodes", 0)) for row in rows),
            "fresh_policy_worker_processes": len(rows),
            "fresh_lean_session_processes_observed": sum(
                row.get("fresh_lean_session_process") is True for row in rows
            ),
            "wall_clock_seconds_descriptive": sum(
                float(row.get("wall_clock_seconds_descriptive", 0.0)) for row in rows
            ),
            "median_time_to_first_proof_seconds": (
                statistics.median([
                    float(row["time_to_first_proof_seconds_descriptive"])
                    for row in rows if row.get("solved") is True
                ]) if solved else None
            ),
            "unique_observed_endpoint_union": len({
                endpoint for row in rows
                for endpoint in row.get("unique_observed_endpoint_keys", [])
            }),
        })

    losses = sum(row["registered_coverage_loss"] for row in paired)
    gains = sum(row["coverage_gain"] for row in paired)
    full_multistep = sum(row["full_multistep_solved"] for row in paired)
    coverage_upper = wilson_upper(losses, len(paired))
    coverage = {
        "unit": "independent theorem root; policies paired within root",
        "registered_roots": len(paired),
        "complete_pairs": sum(row["coverage_complete"] for row in paired),
        "operationally_incomplete_pairs": sum(not row["coverage_complete"] for row in paired),
        "missing_outcome_rule": "every operationally incomplete pair is one coverage loss",
        "full_multistep_solved_roots_missing_as_unsolved": full_multistep,
        "minimum_full_multistep_solves_information_gate": (
            12 if phase == "pilot" else MIN_CONFIRMATION_FULL_MULTISTEP_SOLVES
        ),
        "solve_information_gate": full_multistep >= (
            12 if phase == "pilot" else MIN_CONFIRMATION_FULL_MULTISTEP_SOLVES
        ),
        "effect_aware_coverage_losses_including_missing_worst_case": losses,
        "effect_aware_coverage_gains": gains,
        "effect_aware_coverage_loss_fraction": losses / len(paired),
        "registered_one_sided_95_upper": coverage_upper,
        "registered_noninferiority_margin": COVERAGE_NONINFERIORITY_MARGIN,
        "registered_coverage_noninferiority_gate": coverage_upper <= COVERAGE_NONINFERIORITY_MARGIN,
        "effect_aware_per_root_endpoint_set_exact_fraction": sum(
            row["effect_aware_endpoint_set_exact"] for row in paired
        ) / len(paired),
    }

    efficiency_rows = [row for row in paired if row["efficiency_complete"]]
    savings = [float(row["effect_aware_call_saving"]) for row in efficiency_rows]
    mean_saving = statistics.fmean(savings) if savings else None
    sd_saving = statistics.stdev(savings) if len(savings) >= 2 else None
    lower = (
        mean_saving - ONE_SIDED_Z * sd_saving / math.sqrt(len(savings))
        if mean_saving is not None and sd_saving is not None else None
    )
    required_pairs = len(paired) if phase == "pilot" else MIN_EFFICIENCY_COMPLETE_PAIRS
    efficiency = {
        "unit": "independent theorem root; policies paired within root",
        "complete_pairs": len(efficiency_rows),
        "minimum_complete_pairs": required_pairs,
        "paired_mean_full_minus_effect_aware_tactic_invocations": mean_saving,
        "paired_saving_standard_deviation": sd_saving,
        "paired_saving_stratified_bootstrap_95ci": bootstrap_saving(paired),
        "registered_one_sided_95_lower": lower,
        "registered_efficiency_gate": (
            len(efficiency_rows) >= required_pairs and lower is not None and lower > 0
        ),
        "actual_tactic_invocations_not_planned_calls": True,
        "os_process_launches_reported_separately": True,
    }

    integrity = {
        "all_frozen_jobs_have_receipts": len(jobs) == design["roots"] * len(POLICIES),
        "all_roots_have_four_policies": all(set(rows) == set(POLICIES) for rows in by_root.values()),
        "all_attempt_ordinals_one": all(
            row.get("attempt_ordinal") == 1 for policies in by_root.values() for row in policies.values()
        ),
        "zero_scientific_retries": all(
            row.get("scientific_retry_count") == 0 for policies in by_root.values() for row in policies.values()
        ),
        "zero_manual_reconciliation": all(
            row.get("manual_reconciliation_count") == 0 for policies in by_root.values() for row in policies.values()
        ),
    }
    analysis_gate = all(integrity.values())
    if phase == "pilot":
        all_four_policy_evaluable = all(
            row.get("coverage_evaluable") is True
            for policies in by_root.values() for row in policies.values()
        )
        pilot_go = bool(
            analysis_gate
            and all_four_policy_evaluable
            and coverage["solve_information_gate"]
        )
        decision = "pilot_go" if pilot_go else "pilot_no_go"
    else:
        pilot_go = None
        if not analysis_gate:
            decision = "confirmation_invalid"
        elif not coverage["solve_information_gate"]:
            decision = "insufficient_multistep_solve_information"
        elif not coverage["registered_coverage_noninferiority_gate"]:
            decision = "effect_aware_multistep_coverage_noninferiority_failed"
        elif efficiency["registered_efficiency_gate"]:
            decision = "multistep_solve_coverage_and_tactic_call_efficiency_confirmed"
        else:
            decision = "multistep_solve_coverage_confirmed_efficiency_not_confirmed"

    atomic_csv_dump(policy_metrics, root / phase / "analysis/policy_metrics.csv")
    result = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "phase": phase,
        "analysis_type": "prospectively frozen paired theorem-root evaluation",
        "roots": len(paired),
        "jobs": len(jobs),
        "policy_metrics": policy_metrics,
        "coverage_estimand": coverage,
        "efficiency_estimand": efficiency,
        "integrity_checks": integrity,
        "analysis_gate": analysis_gate,
        "all_four_policy_evaluable": (
            all(
                row.get("coverage_evaluable") is True
                for policies in by_root.values() for row in policies.values()
            )
            if phase == "pilot" else None
        ),
        "pilot_go": pilot_go,
        "decision_label": decision,
        "paired_root_metrics": str(paired_path),
        "paired_root_metrics_sha256": file_sha256(paired_path),
        "claim_boundary": [
            "real multi-step LeanDojo proof search with at least two external tactic invocations",
            "candidate acquisition is intentionally neutralized by a disclosed authored-witness action set",
            "the result evaluates branch-selection policies, not autonomous proof generation",
            "text48 endpoint agreement is not proof-term or semantic identity",
            "wall-clock and time-to-first-proof are secondary because policy order, not machine load, is randomized",
            "operational missing coverage outcomes are conservatively counted as losses",
        ],
        "next_step": (
            "Freeze untouched confirmation roots." if phase == "pilot" and pilot_go
            else "Run independent audit and export." if phase == "confirmation"
            else "STOP and retain the registered result."
        ),
    })
    atomic_json_dump(result, root / phase / "analysis/summary.json")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--phase", required=True, choices=("pilot", "confirmation"))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(analyze(Path(args.artifact_root).resolve(), args.phase), indent=2))
