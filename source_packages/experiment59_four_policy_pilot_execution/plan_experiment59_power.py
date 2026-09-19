"""Estimate a balanced confirmation sample size from the disjoint Exp59 pilot."""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

from experiment59_pilot_protocol import *


def wilson_upper(failures: int, n: int, z: float = ONE_SIDED_Z) -> float:
    if n <= 0:
        return 1.0
    p = failures / n
    denominator = 1 + z * z / n
    center = p + z * z / (2 * n)
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (center + radius) / denominator


def simulate_once(rng: random.Random, pools: dict[str, list[dict[str, Any]]],
                  total_n: int) -> tuple[bool, bool]:
    per_dataset = total_n // 2
    sample = [
        rng.choice(pools[dataset])
        for dataset in ("minif2f", "putnambench")
        for _ in range(per_dataset)
    ]
    savings = [float(row["effect_aware_call_saving"]) for row in sample]
    mean = statistics.fmean(savings)
    standard_deviation = statistics.stdev(savings) if len(savings) > 1 else 0.0
    lower = mean - ONE_SIDED_Z * standard_deviation / math.sqrt(len(savings))
    losses = sum(row["effect_aware_coverage_loss"] is True for row in sample)
    return lower > 0, wilson_upper(losses, len(sample)) <= COVERAGE_NONINFERIORITY_MARGIN


def run(root: Path) -> dict[str, Any]:
    design = load_design(root)
    analysis = read_json(root / "pilot/analysis/summary.json")
    audit = read_json(root / "pilot/audit/summary.json")
    assert_sealed(analysis, "pilot analysis")
    assert_sealed(audit, "pilot audit")
    if analysis.get("analysis_gate") is not True or audit.get("audit_pass") is not True:
        raise ValueError("pilot analysis or audit gate failed")
    metrics_path = Path(analysis["paired_root_metrics"])
    if file_sha256(metrics_path) != analysis["paired_root_metrics_sha256"]:
        raise ValueError("pilot paired-root metrics changed")
    rows = read_jsonl(metrics_path)
    required = {
        "dataset", "target_id", "full_process_calls", "effect_aware_process_calls",
        "effect_aware_call_saving", "effect_aware_coverage_loss", "execution_integrity_gate",
    }
    if not (
        len(rows) == EXPECTED_PILOT_ROOTS
        and {row["target_id"] for row in rows} == set(design["root_order"])
        and all(required.issubset(row) and row["execution_integrity_gate"] is True for row in rows)
    ):
        raise ValueError("pilot paired-root metrics are incomplete")
    pools = {
        dataset: [row for row in rows if row["dataset"] == dataset]
        for dataset in ("minif2f", "putnambench")
    }
    if any(len(pool) != 16 for pool in pools.values()):
        raise ValueError("pilot power planning is not balanced by dataset")
    grid = []
    for total_n in CONFIRMATION_TOTAL_N_GRID:
        efficiency = coverage = joint = 0
        rng = random.Random(POWER_SEED + total_n)
        for _ in range(POWER_REPLICATES):
            efficiency_gate, coverage_gate = simulate_once(rng, pools, total_n)
            efficiency += int(efficiency_gate)
            coverage += int(coverage_gate)
            joint += int(efficiency_gate and coverage_gate)
        grid.append({
            "total_roots": total_n,
            "roots_per_dataset": total_n // 2,
            "replicates": POWER_REPLICATES,
            "efficiency_power": efficiency / POWER_REPLICATES,
            "coverage_noninferiority_power": coverage / POWER_REPLICATES,
            "joint_gate_probability": joint / POWER_REPLICATES,
        })
    registered = next(
        (row for row in grid if row["joint_gate_probability"] >= POWER_TARGET), None
    )
    grid_path = root / "pilot/power/power_grid.csv"
    atomic_csv_dump(grid, grid_path)
    value = seal({
        "version": VERSION,
        "pilot_protocol_version": PILOT_PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "analysis_type": "pilot-based planning simulation; not confirmation evidence",
        "pilot_analysis_sha256": file_sha256(root / "pilot/analysis/summary.json"),
        "pilot_audit_sha256": file_sha256(root / "pilot/audit/summary.json"),
        "pilot_metrics": str(metrics_path),
        "pilot_metrics_sha256": file_sha256(metrics_path),
        "independent_unit": "root/problem",
        "paired_structure": "policies paired within root",
        "balanced_by_dataset": True,
        "seed": POWER_SEED,
        "replicates_per_n": POWER_REPLICATES,
        "target_joint_gate_probability": POWER_TARGET,
        "efficiency_rule": "one-sided normal lower bound for paired mean actual call saving is greater than zero",
        "coverage_rule": f"one-sided Wilson upper bound for paired coverage loss is at most {COVERAGE_NONINFERIORITY_MARGIN}",
        "efficiency_and_coverage_are_separate_estimands": True,
        "grid": grid,
        "power_grid": str(grid_path),
        "power_grid_sha256": file_sha256(grid_path),
        "registered_design": registered,
        "power_gate": registered is not None,
        "confirmation_continuation_probes_executed": 0,
        "manual_reconciliation_count": 0,
        "next_step": (
            "Freeze balanced disjoint confirmation roots."
            if registered else
            "STOP: no registered n up to 128 reached 90% joint planning probability; amend prospectively."
        ),
    })
    atomic_json_dump(value, root / "pilot/power/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(Path(parse_args().artifact_root).resolve()), indent=2))
