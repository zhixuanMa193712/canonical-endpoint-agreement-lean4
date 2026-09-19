"""Offline analysis of the four-policy root-job receipts."""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from experiment57_protocol import *


def analyze(root: Path) -> dict:
    design = load_design(root)
    jobs = []
    for planned in read_jsonl(design["jobs_path"]):
        path = root / "execution/jobs" / f"{planned['job_id']}.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        row = read_json(path)
        assert_sealed(row, f"job {planned['job_id']}")
        if row["job"] != planned:
            raise ValueError("job receipt differs from frozen plan")
        cells = []
        for receipt in row["cell_receipts"]:
            cell_path = Path(receipt["path"])
            if not cell_path.is_file() or file_sha256(cell_path) != receipt["sha256"]:
                raise ValueError(f"cell receipt changed: {receipt['cell_id']}")
            cell = read_json(cell_path); assert_sealed(cell, f"cell {receipt['cell_id']}")
            if not (
                cell["cell_id"] == receipt["cell_id"]
                and cell["job_id"] == planned["job_id"]
                and cell["root_id"] == planned["root_id"]
                and cell["policy"] == planned["policy"]
            ):
                raise ValueError(f"cell identity changed: {receipt['cell_id']}")
            cells.append(cell)
        if not (
            len(cells) == row["process_calls"] == len(row["cell_ids"])
            and [cell["cell_id"] for cell in cells] == row["cell_ids"]
            and sum(cell["valid_reconstruction"] is True for cell in cells)
                == row["valid_reconstruction_cells"]
            and sum(cell["valid_reconstruction"] is not True for cell in cells)
                == row["invalid_cells"]
            and sum(cell["mode"] == "candidate_only" for cell in cells)
                == row["candidate_process_calls"]
            and sum(cell["mode"] == "candidate_probe" for cell in cells)
                == row["downstream_process_calls"]
        ):
            raise ValueError(f"cell-to-job accounting changed: {planned['job_id']}")
        jobs.append(row)
    policy_rows = []
    solved_sets = {}
    endpoint_sets = {}
    downstream_endpoint_sets = {}
    full = [row for row in jobs if row["policy"] == "full"]
    full_by_root = {row["root_id"]: row for row in full}
    for policy in POLICIES:
        rows = [row for row in jobs if row["policy"] == policy]
        solved = {row["root_id"] for row in rows if row["solved"]}
        endpoints = {endpoint for row in rows for endpoint in row["unique_canonical_endpoints"]}
        downstream_endpoints = {
            endpoint for row in rows for endpoint in row["downstream_canonical_endpoints"]
        }
        solved_times = [float(row["time_to_first_proof_seconds"]) for row in rows if row["solved"]]
        solved_sets[policy] = solved
        endpoint_sets[policy] = endpoints
        downstream_endpoint_sets[policy] = downstream_endpoints
        policy_rows.append({
            "policy": policy, "roots": len(rows),
            "candidate_process_calls": sum(row["candidate_process_calls"] for row in rows),
            "downstream_process_calls": sum(row["downstream_process_calls"] for row in rows),
            "process_calls": sum(row["process_calls"] for row in rows),
            "expanded_candidate_nodes": sum(row["expanded_candidate_nodes"] for row in rows),
            "expanded_depth2_nodes": sum(row["expanded_depth2_nodes"] for row in rows),
            "expanded_nodes": sum(row["expanded_nodes"] for row in rows),
            "selected_depth2_branches": sum(row["selected_depth2_branches"] for row in rows),
            "wall_clock_seconds": sum(float(row["wall_clock_seconds"]) for row in rows),
            "solved_roots": len(solved),
            "unique_canonical_endpoints": len(endpoints),
            "unique_downstream_canonical_endpoints": len(downstream_endpoints),
            "median_time_to_first_proof_seconds": statistics.median(solved_times) if solved_times else None,
            "coverage_loss_roots_vs_full": len(solved_sets["full"] - solved) if policy != "full" else 0,
            "coverage_gain_roots_vs_full": len(solved - solved_sets["full"]) if policy != "full" else 0,
            "valid_reconstruction_cells": sum(row["valid_reconstruction_cells"] for row in rows),
            "invalid_cells": sum(row["invalid_cells"] for row in rows),
            "fresh_lean_process_cells": sum(row["fresh_lean_process_cells"] for row in rows),
            "budget_exhausted_roots": sum(row["budget_exhausted"] for row in rows),
        })
    full_metrics = next(row for row in policy_rows if row["policy"] == "full")
    comparisons = []
    for row in policy_rows:
        comparisons.append({
            "policy": row["policy"],
            "process_call_reduction_vs_full": full_metrics["process_calls"] - row["process_calls"],
            "process_call_reduction_fraction_vs_full": (
                (full_metrics["process_calls"] - row["process_calls"]) / full_metrics["process_calls"]
                if full_metrics["process_calls"] else 0.0
            ),
            "expanded_node_reduction_vs_full": full_metrics["expanded_nodes"] - row["expanded_nodes"],
            "wall_clock_reduction_seconds_vs_full": full_metrics["wall_clock_seconds"] - row["wall_clock_seconds"],
            "solved_root_difference_vs_full": row["solved_roots"] - full_metrics["solved_roots"],
            "solved_root_set_exact": solved_sets[row["policy"]] == solved_sets["full"],
            "endpoint_union_exact": endpoint_sets[row["policy"]] == endpoint_sets["full"],
            "downstream_endpoint_union_exact": (
                downstream_endpoint_sets[row["policy"]] == downstream_endpoint_sets["full"]
            ),
        })
    integrity = {
        "all_64_jobs_accounted": len(jobs) == EXPECTED_JOBS,
        "all_cells_valid": all(row["invalid_cells"] == 0 for row in jobs),
        "all_candidate_stages_exact": all(row["candidate_stage_exact"] is True for row in jobs),
        "all_policies_execute_23_candidates_per_root": all(
            row["candidate_process_calls"] == CANDIDATES_PER_ROOT for row in jobs
        ),
        "all_no_retry": all(row["scientific_retry_count"] == 0 for row in jobs),
        "all_cells_used_fresh_lean_processes": all(
            row["all_fresh_lean_processes"] is True for row in jobs
        ),
        "all_within_common_time_budget": all(
            row["wall_clock_seconds"] <= ROOT_POLICY_TIME_BUDGET_SECONDS + 120 for row in jobs
        ),
        "all_max_call_limits_respected": all(
            row["process_calls"] <= row["job"]["max_process_calls"] for row in jobs
        ),
        "zero_manual_reconciliation": all(row["manual_reconciliation_count"] == 0 for row in jobs),
    }
    effect = next(row for row in comparisons if row["policy"] == "effect_aware")
    result = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "estimands": {
            "search_efficiency": {
                "primary": "Lean process-call and expanded-node reduction",
                "secondary": "wall-clock and time-to-first-proof",
                "effect_aware_process_call_reduction_fraction": effect["process_call_reduction_fraction_vs_full"],
            },
            "coverage_preservation": {
                "primary": "solved-root set relative to full expansion",
                "secondary": "all-state and downstream successful strict-endpoint unions",
                "effect_aware_solved_root_set_exact": effect["solved_root_set_exact"],
                "effect_aware_endpoint_union_exact": effect["endpoint_union_exact"],
                "effect_aware_downstream_endpoint_union_exact": effect[
                    "downstream_endpoint_union_exact"
                ],
            },
        },
        "policy_metrics": policy_rows, "comparisons_vs_full": comparisons,
        "integrity_checks": integrity,
        "analysis_gate": all(integrity.values()),
        "decision_label": (
            "end_to_end_benchmark_invalid"
            if not all(integrity.values())
            else "effect_aware_efficiency_with_preserved_root_and_endpoint_coverage"
            if (
                effect["process_call_reduction_fraction_vs_full"] > 0
                and effect["solved_root_set_exact"]
                and effect["downstream_endpoint_union_exact"]
            )
            else "effect_aware_efficiency_with_preserved_solved_root_coverage_only"
            if (
                effect["process_call_reduction_fraction_vs_full"] > 0
                and effect["solved_root_set_exact"]
            )
            else "end_to_end_coverage_loss_detected"
            if not effect["solved_root_set_exact"]
            else "end_to_end_benchmark_inconclusive"
        ),
        "claim_boundary": [
            "sixteen frozen roots from four Lean 4.27 repositories",
            "depth-two search with one frozen eight-probe panel",
            "wall-clock is descriptive and not a general system-speed claim",
            "no global tactic interchangeability or general prover-improvement claim",
        ],
        "scientific_retry_count": 0, "manual_reconciliation_count": 0,
    })
    atomic_csv_dump(policy_rows, root / "analysis/policy_metrics.csv")
    atomic_csv_dump(comparisons, root / "analysis/comparisons_vs_full.csv")
    atomic_json_dump(result, root / "analysis/summary.json")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(analyze(Path(parse_args().artifact_root).resolve()), indent=2))
