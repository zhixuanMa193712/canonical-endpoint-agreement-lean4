"""Finalize the 32-root Exp59 four-policy pilot execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiment59_pilot_protocol import *


def load_and_validate_jobs(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    design = load_design(root)
    planned_jobs = read_jsonl(design["jobs_path"])
    if len(planned_jobs) != EXPECTED_JOBS:
        raise ValueError("frozen pilot job count changed")
    completed: list[dict[str, Any]] = []
    indexed_cells: list[dict[str, Any]] = []
    seen_cells: set[str] = set()
    for planned in planned_jobs:
        path = root / "pilot/execution/jobs" / f"{planned['job_id']}.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        row = read_json(path)
        assert_sealed(row, f"pilot job {planned['job_id']}")
        if not (
            row.get("schema") == JOB_SCHEMA
            and row.get("pilot_protocol_version") == PILOT_PROTOCOL_VERSION
            and row.get("mechanical_fix_id") == MECHANICAL_FIX_ID
            and row.get("job") == planned
            and row.get("job_id") == planned["job_id"]
            and row.get("target_id") == planned["target_id"]
            and row.get("policy") == planned["policy"]
        ):
            raise ValueError(f"pilot job identity changed: {planned['job_id']}")
        cells = []
        for receipt in row.get("cell_receipts", []):
            cell_path = Path(receipt["path"])
            if not cell_path.is_file() or file_sha256(cell_path) != receipt["sha256"]:
                raise ValueError(f"pilot cell file changed: {receipt['cell_id']}")
            cell = read_json(cell_path)
            assert_sealed(cell, f"pilot cell {receipt['cell_id']}")
            if not (
                cell.get("schema") == ROW_SCHEMA
                and cell.get("pilot_protocol_version") == PILOT_PROTOCOL_VERSION
                and cell.get("mechanical_fix_id") == MECHANICAL_FIX_ID
                and cell.get("cell_id") == receipt["cell_id"]
                and cell.get("job_id") == planned["job_id"]
                and cell.get("target_id") == planned["target_id"]
                and cell.get("policy") == planned["policy"]
                and cell.get("scientific_retry_count") == 0
                and cell.get("manual_reconciliation_count") == 0
            ):
                raise ValueError(f"pilot cell identity changed: {receipt['cell_id']}")
            if cell["cell_id"] in seen_cells:
                raise ValueError(f"pilot cell reused across jobs: {cell['cell_id']}")
            seen_cells.add(cell["cell_id"])
            cells.append(cell)
            indexed_cells.append({
                "cell_id": cell["cell_id"], "job_id": planned["job_id"],
                "target_id": planned["target_id"], "dataset": planned["dataset"],
                "policy": planned["policy"], "mode": cell["mode"],
                "path": str(cell_path), "sha256": receipt["sha256"],
                "record_sha256": cell["record_sha256"],
            })
        if not (
            len(cells) == row.get("process_calls") == len(row.get("cell_ids", []))
            and [cell["cell_id"] for cell in cells] == row["cell_ids"]
            and sum(cell["mode"] == "candidate_only" for cell in cells)
                == row.get("candidate_process_calls")
            and sum(cell["mode"] == "candidate_probe" for cell in cells)
                == row.get("downstream_process_calls")
            and sum(cell.get("valid_reconstruction") is True for cell in cells)
                == row.get("valid_reconstruction_cells")
            and sum(cell.get("valid_reconstruction") is not True for cell in cells)
                == row.get("invalid_cells")
            and row.get("candidate_process_calls") == CANDIDATES_PER_ROOT
            and row.get("candidate_stage_exact") is True
            and row.get("all_fresh_lean_processes") is True
            and row.get("all_attempt_ordinals_one") is True
            and row.get("maximum_process_calls_respected") is True
            and row.get("within_common_time_budget") is True
            and row.get("scientific_retry_count") == 0
            and row.get("manual_reconciliation_count") == 0
        ):
            raise ValueError(f"pilot cell-to-job accounting failed: {planned['job_id']}")
        completed.append(row)
    return design, completed, indexed_cells


def finalize(root: Path) -> dict[str, Any]:
    design, jobs, cell_index = load_and_validate_jobs(root)
    shards = []
    for index, target_id in enumerate(design["root_order"]):
        path = root / f"pilot/execution/shards/shard-{index:02d}.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        row = read_json(path)
        assert_sealed(row, f"pilot shard {index:02d}")
        if not (
            row.get("shard_index") == index
            and row.get("target_id") == target_id
            and row.get("jobs_completed") == EXPECTED_POLICIES
            and row.get("all_four_policies_completed") is True
            and row.get("shard_gate") is True
            and row.get("scientific_retry_count") == 0
            and row.get("manual_reconciliation_count") == 0
        ):
            raise ValueError(f"pilot shard accounting failed: {index:02d}")
        shards.append(row)
    cell_index.sort(key=lambda row: (row["target_id"], POLICIES.index(row["policy"]), row["cell_id"]))
    index_path = root / "pilot/execution/row_index.jsonl"
    atomic_jsonl_dump(cell_index, index_path)
    policy_calls = {
        policy: sum(row["process_calls"] for row in jobs if row["policy"] == policy)
        for policy in POLICIES
    }
    gate = bool(
        len(shards) == EXPECTED_PILOT_ROOTS
        and len(jobs) == EXPECTED_JOBS
        and len({row["job_id"] for row in jobs}) == EXPECTED_JOBS
        and all(row["invalid_cells"] == 0 for row in jobs)
        and all(row["candidate_stage_exact"] is True for row in jobs)
        and all(row["all_fresh_lean_processes"] is True for row in jobs)
        and all(row["all_attempt_ordinals_one"] is True for row in jobs)
        and all(row["maximum_process_calls_respected"] is True for row in jobs)
        and all(row["within_common_time_budget"] is True for row in jobs)
    )
    value = seal({
        "version": VERSION,
        "pilot_protocol_version": PILOT_PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "design_record_sha256": design["record_sha256"],
        "shards_expected": EXPECTED_PILOT_ROOTS,
        "shards_completed": len(shards),
        "jobs_expected": EXPECTED_JOBS,
        "jobs_completed": len(jobs),
        "cells_recorded": len(cell_index),
        "candidate_process_calls": sum(row["candidate_process_calls"] for row in jobs),
        "downstream_process_calls": sum(row["downstream_process_calls"] for row in jobs),
        "process_calls": sum(row["process_calls"] for row in jobs),
        "process_calls_by_policy": policy_calls,
        "valid_reconstruction_cells": sum(row["valid_reconstruction_cells"] for row in jobs),
        "invalid_cells": sum(row["invalid_cells"] for row in jobs),
        "fresh_lean_process_cells": sum(row["fresh_lean_process_cells"] for row in jobs),
        "all_attempt_ordinals_one": all(row["all_attempt_ordinals_one"] for row in jobs),
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
        "row_index": str(index_path),
        "row_index_sha256": file_sha256(index_path),
        "execution_complete": len(shards) == EXPECTED_PILOT_ROOTS and len(jobs) == EXPECTED_JOBS,
        "execution_integrity_gate": gate,
        "next_step": "Run frozen offline pilot analysis." if gate else "STOP; preserve invalid pilot execution.",
    })
    atomic_json_dump(value, root / "pilot/execution/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(finalize(Path(parse_args().artifact_root).resolve()), indent=2))
