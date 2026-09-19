"""Launch missing Exp59 confirmation root shards with bounded concurrency."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from experiment59_confirmation_protocol import *

RUNNER = PACKAGE_ROOT / "run_experiment59_confirmation_shards.py"


def run_one(root: Path, index: int) -> dict[str, Any]:
    log = root / f"confirmation/logs/shard-{index:02d}.log"; log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as handle:
        proc = subprocess.run([sys.executable, "-u", str(RUNNER), "--artifact-root", str(root),
                               "--shard-index", str(index)], cwd=PACKAGE_ROOT,
                              stdout=handle, stderr=subprocess.STDOUT)
    return {"shard_index": index, "returncode": proc.returncode, "log": str(log)}


def launch(root: Path, max_workers: int) -> dict[str, Any]:
    design = load_execution_design(root)
    preflight = read_json(root / "confirmation/preflight/worker_compile.json"); assert_sealed(preflight, "confirmation preflight")
    if preflight.get("compile_gate") is not True: raise ValueError("confirmation compile gate failed")
    pid_path = root / "confirmation/logs/launcher.pid"; pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
    pending = [i for i in range(EXPECTED_ROOTS)
               if not (root / f"confirmation/execution/shards/shard-{i:02d}.json").is_file()]
    results = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(run_one, root, index) for index in pending]
            for future in concurrent.futures.as_completed(futures):
                row = future.result(); results.append(row)
                print(f"EXP59-CONFIRM-SHARD {row['shard_index']:02d} returncode={row['returncode']}", flush=True)
    finally:
        if pid_path.is_file() and pid_path.read_text(encoding="utf-8").strip() == str(os.getpid()): pid_path.unlink()
    completed = sum((root / f"confirmation/execution/shards/shard-{i:02d}.json").is_file()
                    for i in range(EXPECTED_ROOTS))
    value = seal({
        "version": VERSION, "confirmation_protocol_version": CONFIRMATION_PROTOCOL_VERSION,
        "design_record_sha256": design["record_sha256"], "max_parallel_root_shards": max_workers,
        "shards_present_before_launch": EXPECTED_ROOTS - len(pending), "shards_launched": len(pending),
        "shards_completed_after_launch": completed,
        "returncode_counts": {str(code): sum(row["returncode"] == code for row in results)
                              for code in sorted({row["returncode"] for row in results})},
        "launch_gate": completed == EXPECTED_ROOTS and all(row["returncode"] == 0 for row in results),
        "scientific_retry_count": 0, "manual_reconciliation_count": 0,
        "next_step": "Finalize confirmation execution." if completed == EXPECTED_ROOTS else
                     "STOP; inspect shard logs and do not retry a launched cell without amendment.",
    })
    atomic_json_dump(value, root / "confirmation/logs/launcher_summary.json"); return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT)); parser.add_argument("--max-workers", type=int, default=16); return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if not 1 <= args.max_workers <= EXPECTED_ROOTS: raise ValueError("max-workers must be between 1 and 64")
    print(json.dumps(launch(Path(args.artifact_root).resolve(), args.max_workers), indent=2))
