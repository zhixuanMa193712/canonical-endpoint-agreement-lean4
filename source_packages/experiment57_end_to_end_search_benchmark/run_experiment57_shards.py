"""Run one frozen root shard (all four policies) without retries."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from experiment57_protocol import *


WORKER = PACKAGE_ROOT / "experiment57_live_worker.py"


def run(root: Path, shard_index: int) -> dict:
    design = load_design(root)
    jobs = read_jsonl(design["jobs_path"])
    root_ids = sorted({row["root_id"] for row in jobs})
    if not 0 <= shard_index < len(root_ids):
        raise ValueError("shard index outside frozen root range")
    root_id = root_ids[shard_index]
    target_meta = next(row for row in design["targets"] if row["root_id"] == root_id)
    target = read_json(target_meta["path"])
    if file_sha256(target_meta["path"]) != target_meta["sha256"]:
        raise ValueError("target record changed")
    job_summaries = []
    for job in [row for row in jobs if row["root_id"] == root_id]:
        output = root / "execution/jobs" / f"{job['job_id']}.json"
        if output.exists():
            raise FileExistsError("Exp57 shard rerun prohibited")
        started = time.monotonic()
        cell_rows = []
        solved = False
        first_proof_seconds = None
        budget_exhausted = False
        candidate_rows = []

        # Fixed front end: every policy independently executes the same 23
        # candidates in the same order before selecting its depth-two frontier.
        for candidate in job["candidate_panel"]:
            remaining = job["time_budget_seconds"] - (time.monotonic() - started)
            if remaining <= 0:
                budget_exhausted = True
                break
            cell_id = json_sha256([
                job["job_id"], "candidate_only", candidate["branch_id"]
            ])[:24]
            inp = {
                "version": VERSION, "protocol_version": PROTOCOL_VERSION,
                "artifact_root": str(root), "job_id": job["job_id"],
                "cell_id": cell_id, "root_id": root_id, "slug": job["slug"],
                "policy": job["policy"], "mode": "candidate_only", "target": target,
                "candidate": candidate, "probe": "skip",
                "timeout_seconds": max(1, min(CELL_TIMEOUT_SECONDS, int(remaining))),
            }
            inp["input_identity_sha256"] = json_sha256(inp)
            input_path = root / "execution/inputs" / f"{cell_id}.json"
            row_path = root / "execution/cells" / f"{cell_id}.json"
            atomic_json_dump(inp, input_path)
            proc = subprocess.run(
                [sys.executable, str(WORKER), "--input", str(input_path), "--output", str(row_path)],
                cwd=PACKAGE_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=inp["timeout_seconds"] + 120,
            )
            if not row_path.is_file():
                raise RuntimeError(f"Exp57 candidate worker lacked receipt: {proc.stderr[-6000:]}")
            row = read_json(row_path); assert_sealed(row, f"cell {cell_id}")
            cell_rows.append(row); candidate_rows.append(row)
            if row.get("terminal_success") is True and first_proof_seconds is None:
                first_proof_seconds = time.monotonic() - started
                solved = True
            print(
                f"EXP57 {shard_index:02d} {job['policy']} candidate "
                f"{len(candidate_rows)}/{CANDIDATES_PER_ROOT} status={row['status']}", flush=True,
            )

        observed_executable_ids = [
            row["branch_id"] for row in candidate_rows
            if row.get("valid_reconstruction") is True and row.get("candidate_executable") is True
        ]
        candidate_stage_exact = (
            len(candidate_rows) == CANDIDATES_PER_ROOT
            and all(row.get("valid_reconstruction") is True for row in candidate_rows)
            and observed_executable_ids == job["executable_candidate_order"]
        )
        downstream_rows = []
        for branch in ([] if solved or not candidate_stage_exact else job["selected_branches"]):
            for probe in job["probe_order"]:
                remaining = job["time_budget_seconds"] - (time.monotonic() - started)
                if remaining <= 0:
                    budget_exhausted = True
                    break
                cell_id = json_sha256([
                    job["job_id"], "candidate_probe", branch["branch_id"], probe
                ])[:24]
                inp = {
                    "version": VERSION, "protocol_version": PROTOCOL_VERSION,
                    "artifact_root": str(root), "job_id": job["job_id"],
                    "cell_id": cell_id, "root_id": root_id, "slug": job["slug"],
                    "policy": job["policy"], "mode": "candidate_probe", "target": target,
                    "candidate": branch,
                    "probe": probe, "timeout_seconds": max(1, min(CELL_TIMEOUT_SECONDS, int(remaining))),
                }
                inp["input_identity_sha256"] = json_sha256(inp)
                input_path = root / "execution/inputs" / f"{cell_id}.json"
                row_path = root / "execution/cells" / f"{cell_id}.json"
                atomic_json_dump(inp, input_path)
                proc = subprocess.run(
                    [sys.executable, str(WORKER), "--input", str(input_path), "--output", str(row_path)],
                    cwd=PACKAGE_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=inp["timeout_seconds"] + 120,
                )
                if not row_path.is_file():
                    raise RuntimeError(f"Exp57 worker failed without receipt: {proc.stderr[-6000:]}")
                row = read_json(row_path)
                assert_sealed(row, f"cell {cell_id}")
                cell_rows.append(row); downstream_rows.append(row)
                print(
                    f"EXP57 {shard_index:02d} {job['policy']} depth2 "
                    f"{len(downstream_rows)}/{len(job['selected_branches']) * len(job['probe_order'])} "
                    f"status={row['status']}", flush=True,
                )
                if row.get("terminal_success") is True:
                    solved = True
                    first_proof_seconds = time.monotonic() - started
                    break
            if solved or budget_exhausted:
                break
        candidate_endpoint_set = sorted({
            row["candidate_endpoint_sha256"] for row in candidate_rows
            if row.get("candidate_endpoint_sha256")
        })
        downstream_endpoint_set = sorted({
            row["probe_endpoint_sha256"] for row in downstream_rows
            if row.get("probe_endpoint_sha256")
        })
        endpoint_set = sorted(set(candidate_endpoint_set) | set(downstream_endpoint_set))
        value = seal({
            "schema": JOB_SCHEMA, "version": VERSION, "protocol_version": PROTOCOL_VERSION,
            "job": job, "job_id": job["job_id"], "root_id": root_id,
            "slug": job["slug"], "policy": job["policy"],
            "candidate_process_calls": len(candidate_rows),
            "downstream_process_calls": len(downstream_rows),
            "process_calls": len(cell_rows),
            "expanded_candidate_nodes": len(candidate_rows),
            "expanded_depth2_nodes": len(downstream_rows),
            "expanded_nodes": len(cell_rows),
            "selected_depth2_branches": len(job["selected_branches"]),
            "candidate_stage_exact": candidate_stage_exact,
            "candidate_canonical_endpoints": candidate_endpoint_set,
            "candidate_canonical_endpoint_count": len(candidate_endpoint_set),
            "downstream_canonical_endpoints": downstream_endpoint_set,
            "downstream_canonical_endpoint_count": len(downstream_endpoint_set),
            "unique_canonical_endpoints": endpoint_set,
            "unique_canonical_endpoint_count": len(endpoint_set),
            "solved": solved, "time_to_first_proof_seconds": first_proof_seconds,
            "wall_clock_seconds": time.monotonic() - started,
            "budget_exhausted": budget_exhausted,
            "valid_reconstruction_cells": sum(row.get("valid_reconstruction") is True for row in cell_rows),
            "invalid_cells": sum(row.get("valid_reconstruction") is not True for row in cell_rows),
            "cell_ids": [row["cell_id"] for row in cell_rows],
            "cell_receipts": [
                {
                    "cell_id": row["cell_id"],
                    "path": str(root / "execution/cells" / f"{row['cell_id']}.json"),
                    "sha256": file_sha256(
                        root / "execution/cells" / f"{row['cell_id']}.json"
                    ),
                }
                for row in cell_rows
            ],
            "fresh_lean_process_cells": sum(
                row.get("process", {}).get("fresh_lean_process") is True for row in cell_rows
            ),
            "all_fresh_lean_processes": all(
                row.get("process", {}).get("fresh_lean_process") is True for row in cell_rows
            ),
            "scientific_retry_count": 0, "manual_reconciliation_count": 0,
        })
        atomic_json_dump(value, output)
        job_summaries.append(value)
    summary = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "shard_index": shard_index, "root_id": root_id,
        "jobs_completed": len(job_summaries),
        "all_four_policies_completed": len(job_summaries) == EXPECTED_POLICIES,
        "job_ids": [row["job_id"] for row in job_summaries],
        "scientific_retry_count": 0, "manual_reconciliation_count": 0,
    })
    atomic_json_dump(summary, root / "execution/shards" / f"shard-{shard_index:02d}.json")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--shard-index", type=int, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run(Path(args.artifact_root).resolve(), args.shard_index), indent=2))
