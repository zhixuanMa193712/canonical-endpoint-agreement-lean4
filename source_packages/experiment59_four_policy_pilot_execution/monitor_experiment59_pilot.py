"""Print a compact progress snapshot for the Exp59 pilot."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from experiment59_pilot_protocol import *


def running(pid_path: Path) -> tuple[int | None, bool]:
    if not pid_path.is_file():
        return None, False
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        return pid, True
    except (ValueError, ProcessLookupError, PermissionError):
        return None, False


def snapshot(root: Path) -> dict:
    pid, active = running(root / "pilot/logs/launcher.pid")
    shards = list((root / "pilot/execution/shards").glob("shard-*.json"))
    jobs = list((root / "pilot/execution/jobs").glob("*.json"))
    cells = list((root / "pilot/execution/cells").glob("*.json"))
    policy_jobs = {policy: 0 for policy in POLICIES}
    process_calls = {policy: 0 for policy in POLICIES}
    for path in jobs:
        try:
            row = read_json(path)
            policy = row.get("policy")
            if policy in policy_jobs:
                policy_jobs[policy] += 1
                process_calls[policy] += int(row.get("process_calls", 0))
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "launcher_pid": pid,
        "launcher_running": active,
        "shards_completed": len(shards),
        "shards_expected": EXPECTED_PILOT_ROOTS,
        "jobs_completed": len(jobs),
        "jobs_expected": EXPECTED_JOBS,
        "jobs_completed_by_policy": policy_jobs,
        "cells_recorded": len(cells),
        "process_calls_in_completed_jobs": process_calls,
        "progress_percent_by_jobs": round(100 * len(jobs) / EXPECTED_JOBS, 2),
        "execution_summary_exists": (root / "pilot/execution/summary.json").is_file(),
        "analysis_exists": (root / "pilot/analysis/summary.json").is_file(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(snapshot(Path(parse_args().artifact_root).resolve()), indent=2))
