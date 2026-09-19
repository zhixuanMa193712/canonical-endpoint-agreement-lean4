"""Finalize Exp59 confirmation while retaining three locked Lean panics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiment59_confirmation_fix1_protocol import *


def finalize(root: Path) -> dict:
    root = Path(root).resolve()
    amendment = validate_fix1_amendment(root)
    corpus = amendment["corpus"]
    design = corpus["design"]
    jobs = corpus["jobs"]

    shards = []
    for shard_index, target_id in enumerate(design["root_order"]):
        path = root / f"confirmation/execution/shards/shard-{shard_index:02d}.json"
        row = read_json(path)
        assert_sealed(row, f"Fix1 source shard {shard_index}")
        if not (
            row.get("shard_index") == shard_index
            and row.get("target_id") == target_id
            and row.get("jobs_completed") == len(POLICIES)
            and row.get("all_four_policies_completed") is True
            and row.get("scientific_retry_count") == 0
            and row.get("manual_reconciliation_count") == 0
            and row.get("shard_gate") is True
        ):
            raise ValueError(f"Fix1 source shard failed: {shard_index}")
        shards.append(row)

    index = sorted(
        corpus["index"],
        key=lambda row: (
            design["root_order"].index(row["target_id"]),
            POLICIES.index(row["policy"]),
            row["cell_id"],
        ),
    )
    index_path = root / FIX1_RELATIVE / "execution/row_index.jsonl"
    atomic_jsonl_dump(index, index_path)
    calls = {
        policy: sum(row["process_calls"] for row in jobs if row["policy"] == policy)
        for policy in POLICIES
    }
    invalid = sum(row["invalid_cells"] for row in jobs)
    complete = len(shards) == EXPECTED_ROOTS and len(jobs) == EXPECTED_JOBS
    accounting_gate = bool(
        complete
        and invalid == len(ANOMALY_LOCKS)
        and all(row["candidate_stage_exact"] is True for row in jobs)
        and all(row["all_fresh_lean_processes"] is True for row in jobs)
        and all(row["all_attempt_ordinals_one"] is True for row in jobs)
        and all(row["scientific_retry_count"] == 0 for row in jobs)
        and all(row["manual_reconciliation_count"] == 0 for row in jobs)
    )
    value = seal({
        "version": FIX1_VERSION,
        "fix1_protocol_version": FIX1_PROTOCOL_VERSION,
        "mechanical_fix_id": FIX1_MECHANICAL_ID,
        "source_confirmation_protocol_version": CONFIRMATION_PROTOCOL_VERSION,
        "source_design_record_sha256": design["record_sha256"],
        "amendment_sha256": amendment["sha256"],
        "source_job_ledger_sha256": corpus["job_ledger_sha256"],
        "shards_expected": EXPECTED_ROOTS,
        "shards_completed": len(shards),
        "jobs_expected": EXPECTED_JOBS,
        "jobs_completed": len(jobs),
        "cells_recorded": corpus["cells_count"],
        "candidate_process_calls": sum(row["candidate_process_calls"] for row in jobs),
        "downstream_process_calls": sum(row["downstream_process_calls"] for row in jobs),
        "process_calls": sum(row["process_calls"] for row in jobs),
        "process_calls_by_policy": calls,
        "valid_reconstruction_cells": sum(
            row["valid_reconstruction_cells"] for row in jobs
        ),
        "locked_operational_anomaly_cells": invalid,
        "locked_operational_anomaly_ledger": corpus["anomalies"],
        "affected_roots": corpus["affected_roots"],
        "affected_root_count": len(corpus["affected_roots"]),
        "fresh_lean_process_cells": sum(row["fresh_lean_process_cells"] for row in jobs),
        "all_attempt_ordinals_one": all(row["all_attempt_ordinals_one"] for row in jobs),
        "all_process_call_accounting_exact": accounting_gate,
        "efficiency_evaluable_roots": EXPECTED_ROOTS,
        "coverage_evaluable_roots": EXPECTED_ROOTS - len(corpus["affected_roots"]),
        "efficiency_execution_gate": accounting_gate,
        "registered_coverage_execution_gate": False,
        "registered_coverage_execution_gate_reason": (
            "one registered root has a locked Lean internal panic in three policy cells"
        ),
        "original_receipts_rewritten": False,
        "lean_executed_by_fix1": False,
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
        "row_index": str(index_path),
        "row_index_sha256": file_sha256(index_path),
        "execution_complete": complete,
        "fix1_execution_accounting_gate": accounting_gate,
        "next_step": (
            "Run offline Fix1 analysis with separate efficiency and coverage gates."
            if accounting_gate else "STOP; preserve failed Fix1 accounting."
        ),
    })
    atomic_json_dump(value, root / FIX1_RELATIVE / "execution/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(finalize(Path(parse_args().artifact_root)), indent=2))
