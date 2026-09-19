"""Run one immutable Exp54 shard with one fresh worker and Lean process per cell."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from experiment54_protocol import *


WORKER = Path(__file__).resolve().parent / "experiment54_live_worker.py"


def validate_row(row: Mapping[str, Any], cell: Mapping[str, Any]) -> None:
    if not (
        row.get("schema") == ROW_SCHEMA
        and row.get("cell_id") == cell["cell_id"]
        and row.get("cell") == cell
        and row.get("execution_version") == EXECUTION_VERSION
        and row.get("mechanical_fix_id") == MECHANICAL_FIX_ID
        and row.get("record_sha256") == record_sha(row)
        and row.get("scientific_retry_count") == 0
        and row.get("manual_reconciliation_count") == 0
    ):
        raise ValueError(f"changed Exp54 row: {cell['cell_id']}")


def synthetic_failure(cell: Mapping[str, Any], inp: Mapping[str, Any], message: str) -> dict[str, Any]:
    return seal({
        "schema": ROW_SCHEMA,
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "execution_version": EXECUTION_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "worker_version": "orchestrator-fail-closed-v1",
        "cell": dict(cell),
        "cell_id": cell["cell_id"],
        "policy": cell["policy"],
        "pair_role": cell["pair_role"],
        "pair_id": cell["pair_id"],
        "root_id": cell["root_id"],
        "slug": cell["slug"],
        "side": cell["side"],
        "probe": cell["probe"],
        "input_identity_sha256": inp["input_identity_sha256"],
        "record_complete": True,
        "valid_reconstruction": False,
        "probe_status": "worker_failure",
        "failure_category": "worker_or_protocol_failure",
        "error_tail": message[-2000:],
        "process": {
            "fresh_lean_process": False,
            "attempt_ordinal": 1,
            "retry_permitted": False,
        },
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
    })


def invoke(
    *, root: Path, frozen: Mapping[str, Any], shard_root: Path,
    cell: Mapping[str, Any],
) -> dict[str, Any]:
    cell_id = cell["cell_id"]
    input_path = shard_root / "inputs" / f"{cell_id}.json"
    claim_path = shard_root / "claims" / f"{cell_id}.json"
    process_path = shard_root / "worker_processes" / f"{cell_id}.json"
    output_path = shard_root / "rows" / f"{cell_id}.json"
    inp = {
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "execution_version": EXECUTION_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "artifact_root": str(root),
        "design_record_sha256": frozen["record_sha256"],
        "cell": dict(cell),
        "cell_id": cell_id,
    }
    inp["input_identity_sha256"] = json_sha256(inp)
    if input_path.is_file():
        if read_json(input_path) != inp:
            raise ValueError(f"changed Exp54 cell input: {cell_id}")
    else:
        atomic_json_dump(inp, input_path)
    if output_path.is_file():
        row = read_json(output_path)
        validate_row(row, cell)
        return row
    if claim_path.is_file():
        raise RuntimeError(
            f"Exp54 cell {cell_id} has an immutable claim but no row. "
            "Do not relaunch it: preserve the incomplete first attempt for audit."
        )
    claim = {
        "version": VERSION,
        "execution_version": EXECUTION_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "cell_id": cell_id,
        "cell_index": cell["cell_index"],
        "input_identity_sha256": inp["input_identity_sha256"],
        "attempts_permitted": 1,
        "scientific_retry_permitted": False,
    }
    exclusive_json_dump(claim, claim_path)
    cmd = [
        sys.executable, str(WORKER),
        "--input", str(input_path), "--output", str(output_path),
    ]
    proc = subprocess.Popen(
        cmd, cwd=WORKER.parent, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        pgid: int | None = os.getpgid(proc.pid)
    except ProcessLookupError:
        pgid = None
    process_receipt = seal({
        "version": VERSION,
        "cell_id": cell_id,
        "worker_pid": proc.pid,
        "worker_process_group_id": pgid,
        "fresh_session_observed": pgid == proc.pid,
        "command": cmd,
        "command_sha256": json_sha256(cmd),
        "input_sha256": file_sha256(input_path),
        "attempt_ordinal": 1,
        "retry_permitted": False,
    })
    atomic_json_dump(process_receipt, process_path)
    stdout, stderr = proc.communicate()
    if not output_path.is_file():
        row = synthetic_failure(
            cell, inp,
            f"returncode={proc.returncode}\nstdout={stdout[-1000:]}\nstderr={stderr[-4000:]}",
        )
        atomic_json_dump(row, output_path)
    row = read_json(output_path)
    validate_row(row, cell)
    return row


def run(args: argparse.Namespace) -> dict[str, Any]:
    if not 0 <= args.shard_index < SHARD_COUNT:
        raise ValueError("shard index outside frozen range")
    root = Path(args.artifact_root).resolve()
    frozen = load_freeze(root)
    preflight = read_json(root / "preflight/worker_compile.json")
    if preflight.get("compile_gate") is not True:
        raise ValueError("Exp54 requires passing compile-only preflight")
    cells = [
        cell for cell in read_jsonl(frozen["cells_path"])
        if cell["shard_index"] == args.shard_index
    ]
    shard_root = root / f"execution/shards/shard-{args.shard_index:02d}"
    summary_path = shard_root / "summary.json"
    if summary_path.is_file():
        value = read_json(summary_path)
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value
    rows = []
    for position, cell in enumerate(cells, start=1):
        print(
            f"EXP54-SHARD {args.shard_index:02d} {position}/{len(cells)} "
            f"{cell['policy']} {cell['pair_role']} {cell['slug']} "
            f"{cell['side']} probe={cell['probe']}",
            flush=True,
        )
        rows.append(invoke(
            root=root, frozen=frozen, shard_root=shard_root, cell=cell
        ))
    statuses = Counter(row.get("probe_status") for row in rows)
    gate = bool(
        len(rows) == len(cells)
        and all(row.get("record_complete") is True for row in rows)
    )
    value = {
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "execution_version": EXECUTION_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "shard_index": args.shard_index,
        "shard_count": SHARD_COUNT,
        "cells_expected": len(cells),
        "cells_recorded": len(rows),
        "valid_reconstruction_cells": sum(
            row.get("valid_reconstruction") is True for row in rows
        ),
        "probe_status_counts": dict(statuses),
        "fresh_lean_process_cells": sum(
            row.get("process", {}).get("fresh_lean_process") is True
            for row in rows
        ),
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
        "shard_gate": gate,
    }
    atomic_json_dump(value, summary_path)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--artifact-root", default=str(artifact_root()))
    p.add_argument("--shard-index", type=int, required=True)
    return p.parse_args()


if __name__ == "__main__":
    run(parse_args())
