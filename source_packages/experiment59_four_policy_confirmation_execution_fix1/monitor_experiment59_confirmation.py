"""Print compact Exp59 confirmation progress."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from experiment59_confirmation_protocol import *


def snapshot(root: Path) -> dict:
    pid_path = root / "confirmation/logs/launcher.pid"; pid = None; running = False
    if pid_path.is_file():
        try: pid = int(pid_path.read_text().strip()); os.kill(pid, 0); running = True
        except (ValueError, ProcessLookupError, PermissionError): pid = None
    jobs = list((root / "confirmation/execution/jobs").glob("*.json"))
    counts = {policy: 0 for policy in POLICIES}; calls = {policy: 0 for policy in POLICIES}
    for path in jobs:
        try:
            row = read_json(path); policy = row.get("policy")
            if policy in counts: counts[policy] += 1; calls[policy] += int(row.get("process_calls", 0))
        except (OSError, json.JSONDecodeError): pass
    shards = list((root / "confirmation/execution/shards").glob("shard-*.json"))
    cells = list((root / "confirmation/execution/cells").glob("*.json"))
    return {"launcher_pid": pid, "launcher_running": running,
            "shards_completed": len(shards), "shards_expected": EXPECTED_ROOTS,
            "jobs_completed": len(jobs), "jobs_expected": EXPECTED_JOBS,
            "jobs_completed_by_policy": counts, "cells_recorded": len(cells),
            "process_calls_in_completed_jobs": calls,
            "progress_percent_by_jobs": round(100 * len(jobs) / EXPECTED_JOBS, 2),
            "execution_summary_exists": (root / "confirmation/execution/summary.json").is_file(),
            "analysis_exists": (root / "confirmation/analysis/summary.json").is_file()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT)); return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(snapshot(Path(parse_args().artifact_root).resolve()), indent=2))
