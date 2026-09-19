"""Run one frozen Exp59 confirmation cell in one fresh Lean process."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from experiment59_confirmation_protocol import *


def run(args: argparse.Namespace) -> dict[str, Any]:
    inp = read_json(args.input); design = load_execution_design(Path(inp["artifact_root"]).resolve())
    identity = json_sha256({k: v for k, v in inp.items() if k != "input_identity_sha256"})
    if not (
        inp.get("input_identity_sha256") == identity
        and inp.get("confirmation_protocol_version") == CONFIRMATION_PROTOCOL_VERSION
        and inp.get("design_record_sha256") == design["record_sha256"]
        and inp.get("mode") in {"candidate_only", "candidate_probe"}
    ):
        raise ValueError("confirmation worker input changed")
    output = Path(args.output).resolve()
    if output.exists():
        raise FileExistsError("confirmation forbids cell overwrite and scientific retry")
    target = inp["target"]; candidate = inp["candidate"]
    pilot = load_pilot(); source_module = pilot.load_source()[0]
    exp58 = source_module.load_exp58_modules()[0]
    project = source_module.project_path(target["dataset"], CHECKOUT_ROOT, exp58)
    source = Path(target["measurement_source"]).resolve()
    if not source.is_file() or file_sha256(source) != target["measurement_source_sha256"]:
        raise ValueError("confirmation measurement source changed")
    staged = (project / ".lake/exp59_confirmation_sources" / target["dataset"] / f"{target['target_id']}.lean").resolve()
    staged.parent.mkdir(parents=True, exist_ok=True)
    if staged.is_file() and file_sha256(staged) != target["measurement_source_sha256"]:
        raise ValueError("staged confirmation source changed")
    if not staged.is_file():
        staged.write_bytes(source.read_bytes())
    backend = pilot.load_backend()
    lean_path = backend.build_lean_source(Path(inp["artifact_root"]) / "confirmation/generated/Experiment59ConfirmationDepth2Worker.lean")
    runtime = output.parent.parent / "runtime"; expected_dir = runtime / "expected"
    expected_dir.mkdir(parents=True, exist_ok=True)
    expected_endpoint = candidate["endpoints"] if candidate["expected_executable"] else target["initial_endpoints"]
    expected_goal_count = int(candidate["goal_count"]) if candidate["expected_executable"] else int(
        target["initial_endpoints"]["raw"]["value"]["goal_count"]
    )
    raw_expected = expected_dir / f"{inp['cell_id']}.raw.txt"
    struct_expected = expected_dir / f"{inp['cell_id']}.struct.txt"
    raw_expected.write_text(str(expected_endpoint["raw"]["value"]["state"]), encoding="utf-8")
    struct_expected.write_text(str(expected_endpoint["struct"]["value"]["state"]), encoding="utf-8")
    raw_output = runtime / "lean_raw" / f"{inp['cell_id']}.json"; raw_output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "lake", "env", "lean", "--run", str(lean_path), str(staged),
        str(target["target_pos"]), str(target["target_end_pos"]), str(raw_output),
        candidate["tactic"], inp["probe"], str(raw_expected), str(struct_expected), str(expected_goal_count),
    ]
    started = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=project, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True)
    try: pgid = os.getpgid(proc.pid)
    except ProcessLookupError: pgid = None
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=int(inp["timeout_seconds"]))
    except subprocess.TimeoutExpired:
        timed_out = True
        try: os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError: pass
        try: stdout, stderr = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            stdout, stderr = proc.communicate()
    process = {
        "lean_pid": proc.pid, "lean_process_group_id": pgid, "fresh_lean_process": pgid == proc.pid,
        "attempt_ordinal": 1, "retry_permitted": False,
        "timeout_seconds": int(inp["timeout_seconds"]), "timed_out": timed_out,
        "returncode": proc.returncode, "elapsed_seconds_descriptive": time.monotonic() - started,
        "command_sha256": json_sha256(cmd), "lean_source_sha256": backend.LEAN_SOURCE_SHA256,
        "stdout_tail": (stdout or "")[-2000:], "stderr_tail": (stderr or "")[-6000:],
    }
    value: dict[str, Any] = {
        "schema": ROW_SCHEMA, "version": VERSION,
        "confirmation_protocol_version": CONFIRMATION_PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID, "cell_id": inp["cell_id"],
        "job_id": inp["job_id"], "target_id": target["target_id"], "dataset": target["dataset"],
        "policy": inp["policy"], "mode": inp["mode"], "branch_id": candidate["branch_id"],
        "candidate_tactic": candidate["tactic"], "candidate_head": candidate["head"],
        "probe": inp["probe"], "input_identity_sha256": inp["input_identity_sha256"],
        "expected_executable": candidate["expected_executable"], "process": process,
        "scientific_retry_count": 0, "manual_reconciliation_count": 0,
    }
    if timed_out or proc.returncode != 0 or not raw_output.is_file():
        value.update({"valid_reconstruction": False,
                      "status": "timeout" if timed_out else "worker_failure",
                      "failure_category": "timeout" if timed_out else "worker_or_protocol_failure",
                      "terminal_success": False})
    else:
        raw = read_json(raw_output); pre_goal_count = raw.get("preGoalCount")
        initial_ready = isinstance(pre_goal_count, int) and raw.get("stateBefore") is not None and raw.get("strictStateBefore") is not None
        initial = None
        if initial_ready:
            values = {
                "raw": {"state": str(raw["stateBefore"]), "goal_count": int(pre_goal_count)},
                "text48": {"state": source_module.normalize_goal_text(raw["stateBefore"]), "goal_count": int(pre_goal_count)},
                "struct": {"state": str(raw["strictStateBefore"]), "goal_count": int(pre_goal_count)},
            }
            initial = {kind: {"value": item, "sha256": json_sha256(item)} for kind, item in values.items()}
        initial_exact = bool(initial is not None and pre_goal_count == 1 and all(
            initial[kind]["sha256"] == target["initial_endpoints"][kind]["sha256"]
            for kind in ("raw", "text48", "struct")
        ))
        candidate_raw = raw.get("candidate", {})
        candidate_ready = bool(candidate_raw.get("executable") is True
            and isinstance(candidate_raw.get("goalCount"), int)
            and candidate_raw.get("stateAfter") is not None
            and candidate_raw.get("strictStateAfter") is not None)
        observed = backend.endpoint_map(str(candidate_raw["stateAfter"]), str(candidate_raw["strictStateAfter"]),
                                        int(candidate_raw["goalCount"])) if candidate_ready else None
        if candidate["expected_executable"]:
            candidate_valid = bool(raw.get("targetFound") is True and initial_exact
                and raw.get("candidateMatched") is True and candidate_ready and all(
                    observed[kind]["sha256"] == candidate["endpoints"][kind]["sha256"]
                    for kind in ("raw", "text48", "struct")))
        else:
            candidate_valid = bool(raw.get("targetFound") is True and initial_exact
                                   and candidate_raw.get("executable") is not True)
        value.update({"valid_reconstruction": candidate_valid, "initial_endpoint_exact": initial_exact,
                      "candidate_executable": candidate_ready,
                      "candidate_endpoint_sha256": observed["struct"]["sha256"] if observed else None,
                      "candidate_goal_count": candidate_raw.get("goalCount") if candidate_ready else None})
        if inp["mode"] == "candidate_only":
            value.update({"status": "candidate_success" if candidate_valid and candidate_ready else
                          "candidate_expected_failure" if candidate_valid else "invalid_reconstruction",
                          "terminal_success": bool(candidate_valid and candidate_ready and candidate_raw["goalCount"] == 0)})
        elif not candidate_valid or not candidate_ready or candidate_raw["goalCount"] == 0:
            value.update({"valid_reconstruction": False, "status": "invalid_reconstruction",
                          "failure_category": "candidate_checkpoint_mismatch", "terminal_success": False})
        else:
            probe = raw.get("probe", {}); probe_valid = raw.get("probeAttempted") is True
            value["valid_reconstruction"] = probe_valid
            if probe_valid and probe.get("executable") is True:
                endpoint = backend.endpoint_map(str(probe["stateAfter"]), str(probe["strictStateAfter"]), int(probe["goalCount"]))
                value.update({"status": "probe_success", "terminal_success": int(probe["goalCount"]) == 0,
                              "probe_endpoint_sha256": endpoint["struct"]["sha256"],
                              "probe_goal_count": int(probe["goalCount"])})
            elif probe_valid:
                message = str(probe.get("error") or "tactic failure")
                value.update({"status": "probe_failure", "failure_category": "tactic_failure",
                              "error_sha256": hashlib.sha256(message.encode()).hexdigest(),
                              "terminal_success": False})
            else:
                value.update({"status": "invalid_reconstruction", "failure_category": "probe_not_attempted",
                              "terminal_success": False})
    atomic_json_dump(seal(value), output); return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--input", required=True); parser.add_argument("--output", required=True); return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2))
