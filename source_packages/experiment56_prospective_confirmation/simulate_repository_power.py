"""Repository-level operating-characteristic simulation for Experiment 56."""
from __future__ import annotations

import argparse
import json
import math
import zipfile
from pathlib import Path

import numpy as np

from experiment56_protocol import *


def source_rates() -> tuple[list[float], str]:
    archive = (WORKSPACE_ROOT / SOURCE_EXP51["path"]).resolve()
    if file_sha256(archive) != SOURCE_EXP51["sha256"]:
        raise ValueError("Exp51 source archive SHA changed")
    with zipfile.ZipFile(archive) as handle:
        name = "artifacts/analysis/summary.json"
        raw = handle.read(name)
        summary = json.loads(raw)
    rates = [float(row["rates"]["Y_L0"]) for row in summary["repositories_detail"]]
    if len(rates) != 12:
        raise ValueError("Exp51 repository-rate source changed")
    return rates, hashlib.sha256(raw).hexdigest()


def beta_moments(values: list[float]) -> tuple[float, float, float]:
    mean = float(np.mean(values))
    variance = float(np.var(values, ddof=1))
    common = mean * (1 - mean) / variance - 1
    if common <= 0:
        raise ValueError("method-of-moments beta fit is undefined")
    alpha = mean * common
    beta = (1 - mean) * common
    return alpha, beta, 1 / (alpha + beta + 1)


def simulate(alpha: float, beta: float, repositories: int, roots: int,
             replicates: int, seed: int) -> dict[str, float | int]:
    rng = np.random.default_rng(seed)
    batch = 5_000
    passed = 0
    lower_ok = 0
    width_ok = 0
    nonzero_ok = 0
    for start in range(0, replicates, batch):
        size = min(batch, replicates - start)
        p = rng.beta(alpha, beta, size=(size, repositories))
        successes = rng.binomial(roots, p)
        rates = successes / roots
        macro = rates.mean(axis=1)
        standard_error = rates.std(axis=1, ddof=1) / math.sqrt(repositories)
        lower = macro - 1.96 * standard_error
        halfwidth = 1.96 * standard_error
        nonzero = (successes > 0).mean(axis=1)
        a = lower > PRIMARY_THRESHOLD
        b = halfwidth <= MAX_CI_HALFWIDTH
        c = nonzero >= MIN_NONZERO_REPOSITORY_FRACTION
        lower_ok += int(a.sum())
        width_ok += int(b.sum())
        nonzero_ok += int(c.sum())
        passed += int((a & b & c).sum())
    return {
        "repositories": repositories,
        "roots_per_repository": roots,
        "total_roots": repositories * roots,
        "replicates": replicates,
        "planning_gate_probability": passed / replicates,
        "lower_bound_gate_probability": lower_ok / replicates,
        "precision_gate_probability": width_ok / replicates,
        "nonzero_repository_gate_probability": nonzero_ok / replicates,
    }


def run(output_root: Path) -> dict:
    locks = validate_locks()
    rates, source_analysis_sha = source_rates()
    alpha, beta, icc = beta_moments(rates)
    grid = []
    grid_id = 0
    for roots in (16, 24, 32, 48):
        for repositories in range(12, 49, 2):
            grid_id += 1
            grid.append(simulate(
                alpha, beta, repositories, roots, POWER_REPLICATES,
                POWER_SEED + grid_id,
            ))
    registered = next(
        row for row in grid
        if row["repositories"] == REPOSITORIES_REQUIRED
        and row["roots_per_repository"] == ROOTS_PER_REPOSITORY
    )
    result = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "analysis_type": "planning simulation, not experimental evidence",
        "source_locks": locks,
        "source_exp51_analysis_sha256": source_analysis_sha,
        "source_repository_rates": rates,
        "beta_binomial_method_of_moments": {
            "alpha": alpha, "beta": beta, "intraclass_correlation": icc,
        },
        "simulation_seed": POWER_SEED,
        "replicates_per_cell": POWER_REPLICATES,
        "decision_rule_approximation": {
            "repository_macro_lower_95_gt": PRIMARY_THRESHOLD,
            "normal_approximation_ci_halfwidth_lte": MAX_CI_HALFWIDTH,
            "nonzero_repository_fraction_gte": MIN_NONZERO_REPOSITORY_FRACTION,
        },
        "registered_design": registered,
        "selection_rationale": (
            "Choose the smallest tested roots-per-repository design with at least "
            "0.90 planning-gate probability while prioritizing independent repositories."
        ),
        "scientific_candidate_tactics_executed": 0,
    })
    atomic_csv_dump(grid, output_root / "power_grid.csv")
    atomic_json_dump(result, output_root / "power_simulation.json")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT / "design"))
    return parser.parse_args()


if __name__ == "__main__":
    value = run(Path(parse_args().artifact_root).resolve())
    print(json.dumps(value, indent=2))

