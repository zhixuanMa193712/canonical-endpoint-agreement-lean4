"""Run one frozen Exp59 confirmation root shard containing all four policies."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from experiment59_confirmation_protocol import *


WORKER = PACKAGE_ROOT / "experiment59_confirmation_live_worker.py"


def elapsed(rows: list[dict[str, Any]]) -> float:
    return sum(float(row.get("process", {}).get("elapsed_seconds_descriptive", 0.0)) for row in rows)


def execute_cell(root: Path, design: dict[str, Any], job: dict[str, Any], target: dict[str, Any],
                 candidate: dict[str, Any], mode: str, probe: str, remaining: float) -> dict[str, Any]:
    cell_id = json_sha256([job["job_id"], mode, candidate["branch_id"], probe])[:24]
    row_path = root / "confirmation/execution/cells" / f"{cell_id}.json"
    inp = {
        "version": VERSION, "confirmation_protocol_version": CONFIRMATION_PROTOCOL_VERSION,
        "design_record_sha256": design["record_sha256"], "artifact_root": str(root),
        "cell_id": cell_id, "job_id": job["job_id"], "policy": job["policy"],
        "mode": mode, "target": target, "candidate": candidate, "probe": probe,
        "timeout_seconds": max(1, min(CELL_TIMEOUT_SECONDS, int(remaining))),
    }
    inp["input_identity_sha256"] = json_sha256(inp)
    input_path = root / "confirmation/execution/inputs" / f"{cell_id}.json"
    if row_path.is_file():
        row = read_json(row_path); assert_sealed(row, f"existing confirmation cell {cell_id}")
        if not (
            row.get("cell_id") == cell_id and row.get("job_id") == job["job_id"]
            and row.get("target_id") == target["target_id"] and row.get("policy") == job["policy"]
            and row.get("mode") == mode and row.get("branch_id") == candidate["branch_id"]
            and row.get("probe") == probe and row.get("input_identity_sha256") == inp["input_identity_sha256"]
        ):
            raise ValueError(f"existing confirmation cell identity changed: {cell_id}")
        return row
    if input_path.is_file():
        raise RuntimeError(f"confirmation cell has prior input but no final receipt; retry forbidden: {cell_id}")
    atomic_json_dump(inp, input_path)
    proc = subprocess.run(
        [sys.executable, str(WORKER), "--input", str(input_path), "--output", str(row_path)],
        cwd=PACKAGE_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=inp["timeout_seconds"] + 120,
    )
    if proc.returncode != 0 or not row_path.is_file():
        raise RuntimeError(f"confirmation cell lacked final receipt: {cell_id}: {proc.stderr[-6000:]}")
    row = read_json(row_path); assert_sealed(row, f"confirmation cell {cell_id}"); return row


def run(root: Path, shard_index: int) -> dict[str, Any]:
    design = load_execution_design(root)
    preflight = read_json(root / "confirmation/preflight/worker_compile.json"); assert_sealed(preflight, "confirmation preflight")
    if preflight.get("compile_gate") is not True:
        raise ValueError("confirmation compile preflight failed")
    if not 0 <= shard_index < EXPECTED_ROOTS:
        raise ValueError("confirmation shard index outside frozen root order")
    target_id = design["root_order"][shard_index]
    target = {row["target_id"]: row for row in read_jsonl(design["targets_path"])}[target_id]
    jobs = [row for row in read_jsonl(design["jobs_path"]) if row["target_id"] == target_id]
    if [row["policy"] for row in jobs] != list(POLICIES):
        raise ValueError("confirmation shard policy order changed")
    branches = {row["branch_id"]: row for row in target["candidate_panel"]}; completed = []
    for job in jobs:
        output = root / "confirmation/execution/jobs" / f"{job['job_id']}.json"
        if output.is_file():
            existing = read_json(output); assert_sealed(existing, f"existing confirmation job {job['job_id']}")
            if existing.get("job") != job: raise ValueError("existing confirmation job changed")
            completed.append(existing); continue
        cells: list[dict[str, Any]] = []; candidate_rows = []; downstream_rows = []
        budget_exhausted = False
        for branch_id in job["candidate_order"]:
            remaining = job["time_budget_seconds"] - elapsed(cells)
            if remaining <= 0: budget_exhausted = True; break
            row = execute_cell(root, design, job, target, branches[branch_id], "candidate_only", "skip", remaining)
            cells.append(row); candidate_rows.append(row)
            print(f"EXP59-CONFIRM {shard_index:02d} {job['policy']} candidate {len(candidate_rows)}/{CANDIDATES_PER_ROOT} status={row['status']}", flush=True)
        observed = [row["branch_id"] for row in candidate_rows
                    if row.get("valid_reconstruction") is True and row.get("candidate_executable") is True]
        candidate_exact = bool(
            len(candidate_rows) == CANDIDATES_PER_ROOT
            and all(row.get("valid_reconstruction") is True for row in candidate_rows)
            and observed == job["executable_candidate_order"]
            and not any(row.get("terminal_success") is True for row in candidate_rows)
        )
        solved = False; first_proof = None
        if candidate_exact:
            for branch in job["selected_branches"]:
                for probe in job["probe_order"]:
                    remaining = job["time_budget_seconds"] - elapsed(cells)
                    if remaining <= 0: budget_exhausted = True; break
                    row = execute_cell(root, design, job, target, branch, "candidate_probe", probe, remaining)
                    cells.append(row); downstream_rows.append(row)
                    print(f"EXP59-CONFIRM {shard_index:02d} {job['policy']} depth2 {len(downstream_rows)}/{len(job['selected_branches']) * len(job['probe_order'])} status={row['status']}", flush=True)
                    if row.get("terminal_success") is True:
                        solved = True; first_proof = elapsed(cells); break
                if solved or budget_exhausted: break
        candidate_endpoints = sorted({row["candidate_endpoint_sha256"] for row in candidate_rows if row.get("candidate_endpoint_sha256")})
        downstream_endpoints = sorted({row["probe_endpoint_sha256"] for row in downstream_rows if row.get("probe_endpoint_sha256")})
        value = seal({
            "schema": JOB_SCHEMA, "version": VERSION,
            "confirmation_protocol_version": CONFIRMATION_PROTOCOL_VERSION,
            "mechanical_fix_id": MECHANICAL_FIX_ID, "job": job, "job_id": job["job_id"],
            "target_id": target_id, "dataset": target["dataset"], "policy": job["policy"],
            "candidate_process_calls": len(candidate_rows), "downstream_process_calls": len(downstream_rows),
            "process_calls": len(cells), "expanded_candidate_nodes": len(candidate_rows),
            "expanded_depth2_nodes": len(downstream_rows), "expanded_nodes": len(cells),
            "selected_depth2_branches": len(job["selected_branches"]), "candidate_stage_exact": candidate_exact,
            "candidate_canonical_endpoints": candidate_endpoints,
            "downstream_canonical_endpoints": downstream_endpoints,
            "unique_canonical_endpoints": sorted(set(candidate_endpoints) | set(downstream_endpoints)),
            "solved": solved, "time_to_first_proof_seconds": first_proof,
            "wall_clock_seconds_descriptive": elapsed(cells), "budget_exhausted": budget_exhausted,
            "valid_reconstruction_cells": sum(row.get("valid_reconstruction") is True for row in cells),
            "invalid_cells": sum(row.get("valid_reconstruction") is not True for row in cells),
            "cell_ids": [row["cell_id"] for row in cells],
            "cell_receipts": [{"cell_id": row["cell_id"],
                "path": str(root / "confirmation/execution/cells" / f"{row['cell_id']}.json"),
                "sha256": file_sha256(root / "confirmation/execution/cells" / f"{row['cell_id']}.json")}
                for row in cells],
            "fresh_lean_process_cells": sum(row.get("process", {}).get("fresh_lean_process") is True for row in cells),
            "all_fresh_lean_processes": all(row.get("process", {}).get("fresh_lean_process") is True for row in cells),
            "all_attempt_ordinals_one": all(row.get("process", {}).get("attempt_ordinal") == 1 for row in cells),
            "maximum_process_calls_respected": len(cells) <= job["maximum_process_calls"],
            "within_common_time_budget": elapsed(cells) <= job["time_budget_seconds"] + 1.0,
            "scientific_retry_count": 0, "manual_reconciliation_count": 0,
        })
        atomic_json_dump(value, output); completed.append(value)
    summary = seal({
        "version": VERSION, "confirmation_protocol_version": CONFIRMATION_PROTOCOL_VERSION,
        "shard_index": shard_index, "target_id": target_id, "dataset": target["dataset"],
        "jobs_completed": len(completed), "all_four_policies_completed": len(completed) == len(POLICIES),
        "job_ids": [row["job_id"] for row in completed],
        "process_calls": sum(row["process_calls"] for row in completed),
        "scientific_retry_count": 0, "manual_reconciliation_count": 0,
        "shard_gate": len(completed) == len(POLICIES),
    })
    atomic_json_dump(summary, root / f"confirmation/execution/shards/shard-{shard_index:02d}.json"); return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT)); parser.add_argument("--shard-index", type=int, required=True); return parser.parse_args()


if __name__ == "__main__":
    args = parse_args(); print(json.dumps(run(Path(args.artifact_root).resolve(), args.shard_index), indent=2))
