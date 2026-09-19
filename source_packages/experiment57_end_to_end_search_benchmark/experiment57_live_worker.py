"""Run one candidate-plus-probe path in a fresh Lean process."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from experiment57_protocol import *


sys.path.insert(0, str(WORKSPACE_ROOT / "experiment54_effect_aware_depth2_microbenchmark_fix3"))
import experiment54_live_worker as backend  # type: ignore


def run(args: argparse.Namespace) -> dict[str, Any]:
    inp = read_json(args.input)
    expected_identity = json_sha256({k: v for k, v in inp.items() if k != "input_identity_sha256"})
    if inp.get("input_identity_sha256") != expected_identity:
        raise ValueError("Exp57 worker input changed")
    if inp.get("mode") not in {"candidate_only", "candidate_probe"}:
        raise ValueError("Exp57 worker mode is not registered")
    target = inp["target"]
    candidate_record = inp["candidate"]
    project = portable_checkout(target["checkout"])
    source = (project / target["file_path"]).resolve()
    if not source.is_file() or file_sha256(source) != target["source_file_sha256"]:
        raise ValueError("Exp57 source identity changed")
    output = Path(args.output).resolve()
    if output.exists():
        raise FileExistsError("Exp57 forbids scientific retries or output reuse")
    runtime = output.parent / "runtime"
    lean_file = backend.build_lean_source(
        Path(inp["artifact_root"]).resolve() / "generated" / backend.LEAN_FILE_NAME
    )
    expected_dir = runtime / "expected"
    expected_dir.mkdir(parents=True, exist_ok=True)
    raw_expected = expected_dir / f"{inp['cell_id']}.raw.txt"
    struct_expected = expected_dir / f"{inp['cell_id']}.struct.txt"
    expected_endpoint = (
        candidate_record["endpoints"]
        if candidate_record["expected_executable"]
        else target["initial_endpoints"]
    )
    expected_goal_count = (
        int(candidate_record["goal_count"])
        if candidate_record["expected_executable"]
        else int(target["initial_endpoints"]["raw"]["value"]["goal_count"])
    )
    raw_expected.write_text(str(expected_endpoint["raw"]["value"]["state"]), encoding="utf-8")
    struct_expected.write_text(str(expected_endpoint["struct"]["value"]["state"]), encoding="utf-8")
    raw_output = runtime / f"{inp['cell_id']}.lean.json"
    cmd = [
        "lake", "env", "lean", "--run", str(lean_file), str(source),
        str(target["target_pos"]), str(target["target_end_pos"]), str(raw_output),
        str(candidate_record["tactic"]), str(inp["probe"]), str(raw_expected),
        str(struct_expected), str(expected_goal_count),
    ]
    started = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=project, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True)
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        pgid = None
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=int(inp["timeout_seconds"]))
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            stdout, stderr = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
    elapsed = time.monotonic() - started
    process = {
        "lean_pid": proc.pid, "lean_process_group_id": pgid,
        "fresh_lean_process": pgid == proc.pid, "attempt_ordinal": 1,
        "retry_permitted": False, "timeout_seconds": int(inp["timeout_seconds"]),
        "timed_out": timed_out, "returncode": proc.returncode,
        "elapsed_seconds_descriptive": elapsed,
        "command_sha256": json_sha256(cmd),
        "lean_source_sha256": backend.LEAN_SOURCE_SHA256,
        "stdout_tail": (stdout or "")[-2000:], "stderr_tail": (stderr or "")[-6000:],
    }
    value: dict[str, Any] = {
        "schema": ROW_SCHEMA, "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "cell_id": inp["cell_id"], "job_id": inp["job_id"],
        "root_id": inp["root_id"], "slug": inp["slug"], "policy": inp["policy"],
        "mode": inp["mode"], "branch_id": candidate_record["branch_id"],
        "candidate_tactic": candidate_record["tactic"],
        "candidate_head": candidate_record["head"], "probe": inp["probe"],
        "expected_executable": candidate_record["expected_executable"], "process": process,
        "scientific_retry_count": 0, "manual_reconciliation_count": 0,
    }
    if timed_out or proc.returncode != 0 or not raw_output.is_file():
        value.update({"valid_reconstruction": False,
                      "status": "timeout" if timed_out else "worker_failure",
                      "terminal_success": False})
    else:
        raw = read_json(raw_output)
        candidate = raw.get("candidate", {})
        candidate_ready = bool(
            candidate.get("executable") is True
            and isinstance(candidate.get("goalCount"), int)
            and candidate.get("stateAfter") is not None
            and candidate.get("strictStateAfter") is not None
        )
        observed_candidate_endpoint = (
            backend.endpoint_map(
                str(candidate["stateAfter"]), str(candidate["strictStateAfter"]),
                int(candidate["goalCount"]),
            ) if candidate_ready else None
        )
        if candidate_record["expected_executable"]:
            candidate_valid = bool(
                raw.get("targetFound") is True and raw.get("candidateMatched") is True
                and candidate_ready
                and all(
                    observed_candidate_endpoint[kind]["sha256"]
                        == candidate_record["endpoints"][kind]["sha256"]
                    for kind in ("raw", "text48", "struct")
                )
            )
        else:
            candidate_valid = bool(
                raw.get("targetFound") is True and candidate.get("executable") is not True
            )
        value.update({
            "valid_reconstruction": candidate_valid,
            "candidate_executable": candidate_ready,
            "candidate_endpoint_sha256": (
                observed_candidate_endpoint["struct"]["sha256"]
                if observed_candidate_endpoint is not None else None
            ),
            "candidate_goal_count": candidate.get("goalCount") if candidate_ready else None,
        })
        if inp["mode"] == "candidate_only":
            value.update({
                "status": (
                    "candidate_success" if candidate_valid and candidate_ready
                    else "candidate_expected_failure" if candidate_valid
                    else "invalid_reconstruction"
                ),
                "terminal_success": bool(
                    candidate_valid and candidate_ready and int(candidate["goalCount"]) == 0
                ),
            })
        elif candidate_valid and candidate_ready and int(candidate["goalCount"]) == 0:
            value.update({"status": "candidate_terminal_success", "terminal_success": True})
        else:
            probe = raw.get("probe", {})
            probe_valid = bool(candidate_valid and raw.get("probeAttempted") is True)
            value["valid_reconstruction"] = probe_valid
            if probe_valid and probe.get("executable") is True:
                endpoint = backend.endpoint_map(
                    str(probe["stateAfter"]), str(probe["strictStateAfter"]),
                    int(probe["goalCount"]),
                )
                value.update({
                    "status": "probe_success", "terminal_success": int(probe["goalCount"]) == 0,
                    "probe_endpoint_sha256": endpoint["struct"]["sha256"],
                    "probe_goal_count": int(probe["goalCount"]),
                })
            elif probe_valid:
                value.update({"status": "probe_failure", "terminal_success": False})
            else:
                value.update({"status": "invalid_reconstruction", "terminal_success": False})
    seal(value)
    atomic_json_dump(value, output)
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2))
