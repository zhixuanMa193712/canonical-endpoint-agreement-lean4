"""Finalize and validate all Exp59 confirmation receipts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiment59_confirmation_protocol import *


def load_jobs(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    design = load_execution_design(root); planned = read_jsonl(design["jobs_path"])
    if len(planned) != EXPECTED_JOBS: raise ValueError("frozen confirmation job count changed")
    jobs = []; index = []; seen = set()
    for plan in planned:
        path = root / "confirmation/execution/jobs" / f"{plan['job_id']}.json"
        row = read_json(path); assert_sealed(row, f"confirmation job {plan['job_id']}")
        if not (row.get("schema") == JOB_SCHEMA and row.get("job") == plan
                and row.get("job_id") == plan["job_id"] and row.get("policy") == plan["policy"]):
            raise ValueError("confirmation job identity changed")
        cells = []
        for receipt in row["cell_receipts"]:
            cell_path = Path(receipt["path"])
            if not cell_path.is_file() or file_sha256(cell_path) != receipt["sha256"]: raise ValueError("confirmation cell file changed")
            cell = read_json(cell_path); assert_sealed(cell, f"confirmation cell {receipt['cell_id']}")
            if not (cell.get("schema") == ROW_SCHEMA and cell["cell_id"] == receipt["cell_id"]
                    and cell["job_id"] == plan["job_id"] and cell["target_id"] == plan["target_id"]
                    and cell["policy"] == plan["policy"] and cell["cell_id"] not in seen):
                raise ValueError("confirmation cell identity or uniqueness changed")
            seen.add(cell["cell_id"]); cells.append(cell)
            index.append({"cell_id": cell["cell_id"], "job_id": plan["job_id"],
                          "target_id": plan["target_id"], "dataset": plan["dataset"],
                          "policy": plan["policy"], "mode": cell["mode"],
                          "path": str(cell_path), "sha256": receipt["sha256"],
                          "record_sha256": cell["record_sha256"]})
        if not (
            len(cells) == row["process_calls"] == len(row["cell_ids"])
            and [cell["cell_id"] for cell in cells] == row["cell_ids"]
            and sum(cell["mode"] == "candidate_only" for cell in cells) == row["candidate_process_calls"] == CANDIDATES_PER_ROOT
            and sum(cell["mode"] == "candidate_probe" for cell in cells) == row["downstream_process_calls"]
            and sum(cell.get("valid_reconstruction") is True for cell in cells) == row["valid_reconstruction_cells"]
            and row["invalid_cells"] == 0 and row["candidate_stage_exact"] is True
            and row["all_fresh_lean_processes"] is True and row["all_attempt_ordinals_one"] is True
            and row["maximum_process_calls_respected"] is True and row["within_common_time_budget"] is True
            and row["scientific_retry_count"] == 0 and row["manual_reconciliation_count"] == 0
        ): raise ValueError(f"confirmation accounting failed: {plan['job_id']}")
        jobs.append(row)
    return design, jobs, index


def finalize(root: Path) -> dict[str, Any]:
    design, jobs, index = load_jobs(root); shards = []
    for i, target_id in enumerate(design["root_order"]):
        row = read_json(root / f"confirmation/execution/shards/shard-{i:02d}.json"); assert_sealed(row, f"confirmation shard {i}")
        if not (row["shard_index"] == i and row["target_id"] == target_id
                and row["jobs_completed"] == len(POLICIES) and row["shard_gate"] is True): raise ValueError("confirmation shard failed")
        shards.append(row)
    index.sort(key=lambda row: (row["target_id"], POLICIES.index(row["policy"]), row["cell_id"]))
    index_path = root / "confirmation/execution/row_index.jsonl"; atomic_jsonl_dump(index, index_path)
    policy_calls = {policy: sum(row["process_calls"] for row in jobs if row["policy"] == policy) for policy in POLICIES}
    gate = len(shards) == EXPECTED_ROOTS and len(jobs) == EXPECTED_JOBS and all(row["invalid_cells"] == 0 for row in jobs)
    value = seal({
        "version": VERSION, "confirmation_protocol_version": CONFIRMATION_PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID, "design_record_sha256": design["record_sha256"],
        "shards_expected": EXPECTED_ROOTS, "shards_completed": len(shards),
        "jobs_expected": EXPECTED_JOBS, "jobs_completed": len(jobs), "cells_recorded": len(index),
        "candidate_process_calls": sum(row["candidate_process_calls"] for row in jobs),
        "downstream_process_calls": sum(row["downstream_process_calls"] for row in jobs),
        "process_calls": sum(row["process_calls"] for row in jobs), "process_calls_by_policy": policy_calls,
        "valid_reconstruction_cells": sum(row["valid_reconstruction_cells"] for row in jobs),
        "invalid_cells": sum(row["invalid_cells"] for row in jobs),
        "fresh_lean_process_cells": sum(row["fresh_lean_process_cells"] for row in jobs),
        "all_attempt_ordinals_one": all(row["all_attempt_ordinals_one"] for row in jobs),
        "scientific_retry_count": 0, "manual_reconciliation_count": 0,
        "row_index": str(index_path), "row_index_sha256": file_sha256(index_path),
        "execution_complete": len(shards) == EXPECTED_ROOTS and len(jobs) == EXPECTED_JOBS,
        "execution_integrity_gate": gate,
        "next_step": "Run registered offline confirmation analysis." if gate else "STOP; preserve invalid execution.",
    })
    atomic_json_dump(value, root / "confirmation/execution/summary.json"); return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT)); return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(finalize(Path(parse_args().artifact_root).resolve()), indent=2))
