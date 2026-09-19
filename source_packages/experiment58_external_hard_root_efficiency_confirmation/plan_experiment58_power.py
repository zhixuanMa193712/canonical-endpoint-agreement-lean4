"""Estimate balanced confirmation n from the frozen disjoint pilot root metrics."""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

from experiment58_protocol import *


def wilson_upper(failures: int, n: int, z: float = EFFICIENCY_ONE_SIDED_Z) -> float:
    if n <= 0:
        return 1.0
    p = failures / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (center + radius) / denom


def one_simulation(rng: random.Random, by_dataset: dict[str, list[dict[str, Any]]], n_total: int) -> tuple[bool, bool]:
    sampled = []
    per_dataset = n_total // len(DATASETS)
    for dataset in sorted(DATASETS):
        pool = by_dataset[dataset]
        sampled.extend(rng.choice(pool) for _ in range(per_dataset))
    deltas = [float(row["full_process_calls"]) - float(row["effect_aware_process_calls"]) for row in sampled]
    mean = statistics.fmean(deltas)
    sd = statistics.stdev(deltas) if len(deltas) > 1 else 0.0
    lower = mean - EFFICIENCY_ONE_SIDED_Z * sd / math.sqrt(len(deltas))
    losses = sum(bool(row["full_solved"]) and not bool(row["effect_aware_solved"]) for row in sampled)
    return lower > 0, wilson_upper(losses, len(sampled)) <= COVERAGE_NONINFERIORITY_MARGIN


def run(root: Path) -> dict[str, Any]:
    pilot_design = read_json(root / "pilot/frozen/design.json")
    assert_sealed(pilot_design, "pilot design")
    metrics_path = root / "pilot/results/paired_root_metrics.jsonl"
    if not metrics_path.is_file():
        raise FileNotFoundError(
            f"{metrics_path} is absent: pilot continuation has not been executed; final confirmation n must not be invented"
        )
    rows = read_jsonl(metrics_path)
    expected = {(row["dataset"], row["target_id"]) for row in read_jsonl(
        read_json(root / "screening/summary.json")["pilot_roots_path"]
    )}
    observed = {(row["dataset"], row["target_id"]) for row in rows}
    required = {"dataset", "target_id", "full_process_calls", "effect_aware_process_calls",
                "full_solved", "effect_aware_solved", "execution_integrity_gate"}
    if observed != expected or any(not required.issubset(row) or row["execution_integrity_gate"] is not True for row in rows):
        raise ValueError("pilot paired-root metrics are incomplete or differ from the frozen pilot")
    by_dataset = {dataset: [row for row in rows if row["dataset"] == dataset] for dataset in DATASETS}
    grid = []
    for n_total in CONFIRMATION_TOTAL_N_GRID:
        efficiency = coverage = combined = 0
        rng = random.Random(POWER_SEED + n_total)
        for _ in range(POWER_REPLICATES):
            eff, cov = one_simulation(rng, by_dataset, n_total)
            efficiency += int(eff)
            coverage += int(cov)
            combined += int(eff and cov)
        grid.append({
            "total_roots": n_total, "roots_per_dataset": n_total // len(DATASETS),
            "replicates": POWER_REPLICATES, "efficiency_power": efficiency / POWER_REPLICATES,
            "coverage_noninferiority_power": coverage / POWER_REPLICATES,
            "joint_gate_probability": combined / POWER_REPLICATES,
        })
    registered = next((row for row in grid
                       if row["efficiency_power"] >= POWER_TARGET
                       and row["coverage_noninferiority_power"] >= POWER_TARGET), None)
    grid_path = root / "pilot/power/power_grid.csv"
    atomic_csv_dump(grid, grid_path)
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "analysis_type": "pilot-based planning simulation; not confirmation evidence",
        "pilot_metrics": str(metrics_path), "pilot_metrics_sha256": file_sha256(metrics_path),
        "independent_unit": "root/problem", "paired_structure": "policies paired within root",
        "balanced_by_dataset": True, "seed": POWER_SEED, "replicates_per_n": POWER_REPLICATES,
        "efficiency_rule": "one-sided normal lower bound for paired mean call saving is greater than zero",
        "coverage_rule": f"one-sided Wilson upper bound for paired coverage loss is at most {COVERAGE_NONINFERIORITY_MARGIN}",
        "grid": grid, "registered_design": registered,
        "power_gate": registered is not None,
        "confirmation_continuation_probes_executed": 0,
        "next_step": "Freeze the balanced confirmation roots." if registered else
        "STOP: no registered n up to 128 achieved both planning targets; amend prospectively before confirmation.",
    })
    atomic_json_dump(value, root / "pilot/power/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(Path(parse_args().artifact_root).resolve()), indent=2))
