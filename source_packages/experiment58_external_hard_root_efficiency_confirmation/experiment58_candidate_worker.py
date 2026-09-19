"""Execute exactly the frozen candidate panel at one proof hole; never run a continuation."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from experiment58_protocol import *


def load_vendor() -> Any:
    protocol_path, worker_path = vendor_paths()
    if str(protocol_path.parent) not in sys.path:
        sys.path.insert(0, str(protocol_path.parent))
    spec = importlib.util.spec_from_file_location("experiment58_vendor_exp49_worker", worker_path)
    if spec is None or spec.loader is None:
        raise ImportError(worker_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if hashlib.sha256(module.LEAN_SOURCE.encode("utf-8")).hexdigest() != module.LEAN_SOURCE_SHA256:
        raise ValueError("vendor Lean worker source hash is internally inconsistent")
    return module


def run(args: argparse.Namespace) -> dict[str, Any]:
    vendor = load_vendor()
    inp = read_json(args.input)
    expected_identity = json_sha256({key: value for key, value in inp.items() if key != "input_identity_sha256"})
    if inp.get("input_identity_sha256") != expected_identity:
        raise ValueError("Exp58 worker input changed")
    if tuple(inp.get("candidate_panel", [])) != CANDIDATE_PANEL or inp.get("continuation_probe_count") != 0:
        raise ValueError("Exp58 candidate-only contract changed")
    target = inp["target"]
    source = Path(target["measurement_source"]).resolve()
    if not source.is_file() or file_sha256(source) != target["measurement_source_sha256"]:
        raise ValueError("Exp58 generated measurement source changed")
    project = project_path(target["dataset"], Path(inp["checkout_root"]).resolve())
    # Lean 4.27 rejects frontend input files outside the active Lake project
    # root.  Stage the already frozen, hash-checked measurement bytes under
    # .lake; this changes only the execution path, never the source content.
    staged_source = (
        project / ".lake/exp58_measurement_sources"
        / target["dataset"] / f"{target['target_id']}.lean"
    ).resolve()
    staged_source.parent.mkdir(parents=True, exist_ok=True)
    if staged_source.is_file() and file_sha256(staged_source) != target["measurement_source_sha256"]:
        raise ValueError("staged Exp58 measurement source changed")
    if not staged_source.is_file():
        staged_source.write_bytes(source.read_bytes())
    if file_sha256(staged_source) != target["measurement_source_sha256"]:
        raise ValueError("staged Exp58 measurement source hash mismatch")
    output = Path(args.output).resolve()
    if output.exists():
        raise FileExistsError("Exp58 candidate-only screening forbids retries and output reuse")
    generated = Path(inp["artifact_root"]).resolve() / "generated/Experiment58CandidateOnlyWorker.lean"
    generated.parent.mkdir(parents=True, exist_ok=True)
    if generated.is_file() and file_sha256(generated) != vendor.LEAN_SOURCE_SHA256:
        raise ValueError("generated candidate-only Lean worker changed")
    if not generated.is_file():
        generated.write_text(vendor.LEAN_SOURCE, encoding="utf-8")
    raw_output = output.with_suffix(".lean.json")
    cmd = [
        "lake", "env", "lean", "--run", str(generated), str(staged_source),
        str(target["target_pos"]), str(target["target_end_pos"]), str(raw_output),
        *CANDIDATE_PANEL,
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
        stdout, stderr = proc.communicate(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            stdout, stderr = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
    process = {
        "lean_pid": proc.pid, "lean_process_group_id": pgid,
        "fresh_lean_process": pgid == proc.pid, "attempt_ordinal": 1,
        "retry_permitted": False, "timeout_seconds": args.timeout,
        "timed_out": timed_out, "returncode": proc.returncode,
        "elapsed_seconds_descriptive": time.monotonic() - started,
        "command_sha256": json_sha256(cmd), "lean_source_sha256": vendor.LEAN_SOURCE_SHA256,
        "stdout_tail": (stdout or "")[-2000:], "stderr_tail": (stderr or "")[-6000:],
    }
    value: dict[str, Any] = {
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "target_id": target["target_id"], "dataset": target["dataset"],
        "role": target["role"], "theorem_name": target["theorem_name"],
        "target_identity": target, "candidate_panel": list(CANDIDATE_PANEL),
        "candidate_panel_sha256": json_sha256(CANDIDATE_PANEL), "process": process,
        "measurement_source": str(source),
        "staged_measurement_source": str(staged_source),
        "staged_measurement_source_sha256": file_sha256(staged_source),
        "staged_source_content_exact": file_sha256(staged_source) == target["measurement_source_sha256"],
        "candidate_only_tactics_executed": 0, "continuation_probes_executed": 0,
        "scientific_retry_count": 0, "manual_reconciliation_count": 0,
    }
    if timed_out or proc.returncode != 0 or not raw_output.is_file():
        value.update({"worker_ok": False, "failure_category": "timeout" if timed_out else "worker_failure",
                      "candidate_accounting_exact": False, "eligibility_gate": False,
                      "first_failed_gate": "timeout" if timed_out else "worker"})
    else:
        raw = read_json(raw_output)
        alternatives = list(raw.get("alternatives") or [])
        rows = []
        initial_goal_count = raw.get("preGoalCount")
        initial_struct = raw.get("strictStateBefore")
        initial = {
            "raw": {"state": raw.get("stateBefore"), "goal_count": initial_goal_count},
            "text48": {"state": normalize_goal_text(raw.get("stateBefore")), "goal_count": initial_goal_count},
            "struct": {"state": initial_struct, "goal_count": initial_goal_count},
        }
        initial_endpoints = {kind: {"value": endpoint, "sha256": json_sha256(endpoint)}
                             for kind, endpoint in initial.items()}
        for position, (tactic, branch) in enumerate(zip(CANDIDATE_PANEL, alternatives)):
            executable = branch.get("executable") is True
            row = {
                "candidate_position_frozen": position, "tactic": tactic,
                "head": tactic_head(tactic), "executable": executable,
            }
            if executable:
                endpoints = vendor._endpoint_map(branch)
                row.update({"goal_count": branch.get("goalCount"),
                            "terminal": branch.get("goalCount") == 0, "endpoints": endpoints})
            else:
                message = str(branch.get("error") or "tactic failure")
                row.update({"terminal": False, "failure_category": "tactic_failure",
                            "error_sha256": hashlib.sha256(message.encode()).hexdigest()})
            rows.append(row)
        accounting = len(alternatives) == CANDIDATES_PER_ROOT and len(rows) == CANDIDATES_PER_ROOT
        same_pre = all(
            normalize_goal_text(branch.get("preState")) == initial["text48"]["state"]
            and branch.get("strictPreState") == initial_struct
            for branch in alternatives
        ) if accounting else False
        executable_nonterminal = [row for row in rows if row["executable"] and not row["terminal"]]
        classes: dict[str, list[int]] = {}
        for row in executable_nonterminal:
            classes.setdefault(row["endpoints"]["struct"]["sha256"], []).append(row["candidate_position_frozen"])
        terminal_count = sum(row["terminal"] for row in rows)
        max_class = max((len(items) for items in classes.values()), default=0)
        worker_ok = bool(raw.get("targetFound") is True and initial_goal_count == 1 and accounting and same_pre)
        eligible = bool(worker_ok and terminal_count == 0
                        and len(executable_nonterminal) >= MIN_EXECUTABLE_NONTERMINAL
                        and max_class >= MIN_EFFECT_CLASS_SIZE)
        value.update({
            "worker_ok": worker_ok, "target_found": raw.get("targetFound") is True,
            "pre_goal_count": initial_goal_count, "initial_endpoints": initial_endpoints,
            "candidate_rows": rows, "candidate_accounting_exact": accounting,
            "same_pre_state_all_branches": same_pre,
            "candidate_only_tactics_executed": len(rows),
            "executable_nonterminal_candidates": len(executable_nonterminal),
            "terminal_candidate_count": terminal_count,
            "strict_endpoint_class_count": len(classes), "maximum_strict_endpoint_class_size": max_class,
            "strict_endpoint_classes": classes, "eligibility_gate": eligible,
            "first_failed_gate": None if eligible else (
                "worker" if not worker_ok else "terminal_candidate" if terminal_count else
                "minimum_executable_nonterminal" if len(executable_nonterminal) < MIN_EXECUTABLE_NONTERMINAL
                else "minimum_effect_class_size"
            ),
        })
    seal(value)
    atomic_json_dump(value, output)
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2))
