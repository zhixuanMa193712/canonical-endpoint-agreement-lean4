"""Frozen offline analysis for the Exp54 full-versus-dedup microbenchmark."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Mapping

from experiment54_protocol import *


def load_rows(root: Path) -> list[dict[str, Any]]:
    index = read_jsonl(root / "execution/row_index.jsonl")
    rows = []
    for item in index:
        path = Path(item["path"])
        if file_sha256(path) != item["sha256"]:
            raise ValueError("Exp54 execution row hash changed")
        row = read_json(path)
        assert_sealed(row, "analysis row")
        rows.append(row)
    return rows


def key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return str(row["pair_id"]), str(row["side"]), str(row["probe"])


def pair_probe_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row["pair_id"]), str(row["probe"])


def endpoint_set(rows: list[Mapping[str, Any]]) -> set[str]:
    return {
        str(row["probe_endpoint"]["struct"]["sha256"])
        for row in rows if row.get("probe_status") == "success"
    }


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.artifact_root).resolve()
    frozen = load_freeze(root)
    execution = read_json(root / "execution/summary.json")
    if execution.get("execution_integrity_gate") is not True:
        raise ValueError("Exp54 analysis requires complete valid execution")
    rows = load_rows(root)
    full = [row for row in rows if row["policy"] == "full"]
    dedup = [row for row in rows if row["policy"] == "dedup"]
    full_by = {key(row): row for row in full}
    dedup_by = {key(row): row for row in dedup}
    overlap_keys = sorted(set(full_by) & set(dedup_by))
    overlap_mismatches = [
        {
            "pair_id": item[0], "side": item[1], "probe": item[2],
            "full": outcome_signature(full_by[item]),
            "dedup": outcome_signature(dedup_by[item]),
        }
        for item in overlap_keys
        if outcome_signature(full_by[item]) != outcome_signature(dedup_by[item])
    ]
    pair_meta = {pair["pair_id"]: pair for pair in read_jsonl(frozen["pairs_path"])}
    full_pair_probe: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    dedup_pair_probe: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in full:
        full_pair_probe[pair_probe_key(row)].append(row)
    for row in dedup:
        dedup_pair_probe[pair_probe_key(row)].append(row)
    coverage_mismatches = []
    witness_probe_mismatches = []
    pair_any_mismatch: dict[str, bool] = {
        pair_id: False for pair_id, pair in pair_meta.items()
        if pair["role"] == "witness"
    }
    for item, full_rows in sorted(full_pair_probe.items()):
        pair_id, probe = item
        dedup_rows = dedup_pair_probe[item]
        full_signatures = {
            json.dumps(outcome_signature(row), sort_keys=True)
            for row in full_rows
        }
        dedup_signatures = {
            json.dumps(outcome_signature(row), sort_keys=True)
            for row in dedup_rows
        }
        if full_signatures != dedup_signatures:
            coverage_mismatches.append({
                "pair_id": pair_id,
                "role": pair_meta[pair_id]["role"],
                "probe": probe,
                "full_signatures": sorted(full_signatures),
                "dedup_signatures": sorted(dedup_signatures),
            })
        if pair_meta[pair_id]["role"] == "witness":
            by_side = {row["side"]: outcome_signature(row) for row in full_rows}
            if by_side.get("left") != by_side.get("right"):
                witness_probe_mismatches.append({
                    "pair_id": pair_id,
                    "slug": pair_meta[pair_id]["slug"],
                    "probe": probe,
                    "left": by_side.get("left"),
                    "right": by_side.get("right"),
                })
                pair_any_mismatch[pair_id] = True
    witness_pairs = [
        pair for pair in pair_meta.values() if pair["role"] == "witness"
    ]
    pair_mismatch_count = sum(pair_any_mismatch.values())
    repositories_with_zero_mismatch = len({
        pair["slug"] for pair in witness_pairs
        if not any(
            row["slug"] == pair["slug"]
            for row in witness_probe_mismatches
        )
    })
    full_calls = len(full)
    dedup_calls = len(dedup)
    saved_calls = full_calls - dedup_calls
    full_strict_endpoints = endpoint_set(full)
    dedup_strict_endpoints = endpoint_set(dedup)
    full_terminal_successes = sum(
        row.get("probe_status") == "success"
        and row["probe_endpoint"]["struct"]["terminal"] is True
        for row in full
    )
    dedup_terminal_successes = sum(
        row.get("probe_status") == "success"
        and row["probe_endpoint"]["struct"]["terminal"] is True
        for row in dedup
    )
    full_terminal_pair_probes = {
        pair_probe_key(row) for row in full
        if row.get("probe_status") == "success"
        and row["probe_endpoint"]["struct"]["terminal"] is True
    }
    dedup_terminal_pair_probes = {
        pair_probe_key(row) for row in dedup
        if row.get("probe_status") == "success"
        and row["probe_endpoint"]["struct"]["terminal"] is True
    }
    elapsed = {
        policy: [
            float(row["process"]["elapsed_seconds_descriptive"])
            for row in rows if row["policy"] == policy
        ]
        for policy in ("full", "dedup")
    }
    integrity_checks = {
        "execution_integrity_gate": execution["execution_integrity_gate"] is True,
        "all_896_cells_accounted": len(rows) == EXPECTED_CELLS,
        "all_overlap_cells_exactly_reproduced": len(overlap_mismatches) == 0,
        "all_attempt_ordinals_one": execution["all_attempt_ordinals_one"] is True,
        "zero_scientific_retries": execution["scientific_retry_count"] == 0,
        "zero_manual_reconciliation": execution["manual_reconciliation_count"] == 0,
    }
    preservation_checks = {
        "zero_witness_probe_outcome_mismatches": len(witness_probe_mismatches) == 0,
        "full_and_dedup_pair_probe_coverage_exact": len(coverage_mismatches) == 0,
        "successful_strict_endpoint_union_preserved": (
            full_strict_endpoints == dedup_strict_endpoints
        ),
        "terminal_success_pair_probe_set_preserved": (
            full_terminal_pair_probes == dedup_terminal_pair_probes
        ),
    }
    efficiency_checks = {
        "full_calls_exact": full_calls == EXPECTED_FULL_CELLS,
        "dedup_calls_exact": dedup_calls == EXPECTED_DEDUP_CELLS,
        "positive_call_reduction": saved_calls > 0,
        "planned_25_percent_reduction_realized": (
            saved_calls == 128 and saved_calls / full_calls == 0.25
        ),
    }
    supported = bool(
        all(integrity_checks.values())
        and all(preservation_checks.values())
        and all(efficiency_checks.values())
    )
    if supported:
        decision = "effect_aware_depth2_supported"
    elif all(integrity_checks.values()) and all(efficiency_checks.values()):
        decision = "coverage_loss_detected"
    else:
        decision = "effect_aware_depth2_inconclusive"
    summary = {
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "execution_version": EXECUTION_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "independent_unit": "frozen within-root candidate pair",
        "repeated_measure": "eight probes per pair",
        "repository_block": "four confirmation repositories",
        "roots": EXPECTED_ROOTS,
        "witness_pairs": len(witness_pairs),
        "control_pairs": sum(p["role"] == "control" for p in pair_meta.values()),
        "probes_per_pair": len(PROBES),
        "search_efficiency": {
            "full_downstream_calls": full_calls,
            "dedup_downstream_calls": dedup_calls,
            "calls_saved": saved_calls,
            "call_reduction_fraction": saved_calls / full_calls,
            "witness_only_call_reduction_fraction": 0.5,
            "depth1_candidate_execution_reduction": 0,
        },
        "coverage": {
            "witness_probe_comparisons": len(witness_pairs) * len(PROBES),
            "witness_probe_mismatches": len(witness_probe_mismatches),
            "witness_pairs_with_any_mismatch": pair_mismatch_count,
            "witness_pair_mismatch_fraction": pair_mismatch_count / len(witness_pairs),
            "one_sided_exact_95_upper_if_zero_pair_mismatches": (
                exact_binomial_zero_upper(len(witness_pairs))
                if pair_mismatch_count == 0 else None
            ),
            "repositories_with_zero_witness_mismatch": repositories_with_zero_mismatch,
            "coverage_mismatches": len(coverage_mismatches),
            "full_successful_strict_endpoint_count": len(full_strict_endpoints),
            "dedup_successful_strict_endpoint_count": len(dedup_strict_endpoints),
            "successful_strict_endpoint_union_exact": (
                full_strict_endpoints == dedup_strict_endpoints
            ),
            "full_terminal_success_cells": full_terminal_successes,
            "dedup_terminal_success_cells": dedup_terminal_successes,
            "full_terminal_success_pair_probes": len(full_terminal_pair_probes),
            "dedup_terminal_success_pair_probes": len(dedup_terminal_pair_probes),
            "terminal_success_pair_probe_set_exact": (
                full_terminal_pair_probes == dedup_terminal_pair_probes
            ),
        },
        "outcome_diversity": {
            "full_unique_successful_strict_endpoints_per_100_calls": (
                100 * len(full_strict_endpoints) / full_calls
            ),
            "dedup_unique_successful_strict_endpoints_per_100_calls": (
                100 * len(dedup_strict_endpoints) / dedup_calls
            ),
            "interpretation": (
                "descriptive yield per executed depth-2 branch; not a claim about "
                "global tactic diversity"
            ),
        },
        "descriptive_process_time": {
            "full_sum_seconds": sum(elapsed["full"]),
            "dedup_sum_seconds": sum(elapsed["dedup"]),
            "full_median_cell_seconds": median(elapsed["full"]),
            "dedup_median_cell_seconds": median(elapsed["dedup"]),
            "not_primary_because": (
                "wall-clock scheduling and cache effects were not controlled as an estimand"
            ),
        },
        "probe_status_counts": {
            policy: dict(Counter(
                row["probe_status"] for row in rows if row["policy"] == policy
            )) for policy in ("full", "dedup")
        },
        "integrity_checks": integrity_checks,
        "preservation_checks": preservation_checks,
        "efficiency_checks": efficiency_checks,
        "overlap_mismatch_count": len(overlap_mismatches),
        "manual_reconciliation_count": 0,
        "decision_label": decision,
        "claim_boundary": [
            "frozen one-step candidates followed by one frozen probe only",
            "effect-aware pruning is evaluated only on registered strict-endpoint witnesses",
            "no global tactic interchangeability, arbitrary continuation, learning, or general prover-improvement claim",
        ],
        "next_step": "Run independent reconstruction audit.",
    }
    outdir = root / "analysis"
    atomic_json_dump(summary, outdir / "summary.json")
    atomic_jsonl_dump(witness_probe_mismatches, outdir / "witness_probe_mismatches.jsonl")
    atomic_jsonl_dump(coverage_mismatches, outdir / "coverage_mismatches.jsonl")
    atomic_jsonl_dump(overlap_mismatches, outdir / "overlap_mismatches.jsonl")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--artifact-root", default=str(artifact_root()))
    return p.parse_args()


if __name__ == "__main__":
    analyze(parse_args())
