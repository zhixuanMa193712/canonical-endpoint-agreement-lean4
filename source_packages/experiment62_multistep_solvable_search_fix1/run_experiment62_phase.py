"""Run frozen Exp62 pilot or confirmation roots sequentially without retries."""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from experiment62_protocol import *


WORKER = PACKAGE_ROOT / "experiment62_policy_worker.py"


def load_design(root: Path, phase: str) -> dict[str, Any]:
    design = read_json(root / phase / "frozen/design.json")
    assert_sealed(design, f"Exp62 {phase} design")
    if design.get("phase") != phase:
        raise ValueError("Exp62 phase design mismatch")
    if file_sha256(design["targets_path"]) != design["targets_sha256"]:
        raise ValueError("Exp62 phase target ledger changed")
    if file_sha256(design["jobs_path"]) != design["jobs_sha256"]:
        raise ValueError("Exp62 phase job ledger changed")
    return design


def failure_receipt(
    job: dict[str, Any], target: dict[str, Any], reason: str,
    output: Path, marker: Path, proc: subprocess.CompletedProcess[str] | None = None,
) -> dict[str, Any]:
    value = seal({
        "schema": JOB_SCHEMA,
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "phase": job["phase"],
        "job": job,
        "job_id": job["job_id"],
        "target_id": target["target_id"],
        "theorem_id": target["theorem_id"],
        "stratum": target["stratum"],
        "policy": job["policy"],
        "attempt_ordinal": 1,
        "retry_permitted": False,
        "solved": False,
        "proof": None,
        "proof_length": None,
        "multi_step_solved": False,
        "tactic_invocations": 0,
        "expanded_nodes": 0,
        "operational_failure": True,
        "coverage_evaluable": False,
        "efficiency_evaluable": False,
        "stop_reason": reason,
        "attempt_marker_sha256": file_sha256(marker),
        "worker_returncode": proc.returncode if proc is not None else None,
        "worker_stdout_tail": proc.stdout[-2000:] if proc is not None else None,
        "worker_stderr_tail": proc.stderr[-4000:] if proc is not None else None,
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
    })
    atomic_json_dump(value, output)
    return value


def run_job(root: Path, phase: str, design: dict[str, Any], job: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    output = root / phase / "execution/jobs" / f"{job['job_id']}.json"
    marker = root / phase / "execution/attempts" / f"{job['job_id']}.json"
    input_path = root / phase / "execution/inputs" / f"{job['job_id']}.json"
    if output.is_file():
        row = read_json(output)
        assert_sealed(row, f"Exp62 job {job['job_id']}")
        if row.get("job") != job:
            raise ValueError("existing Exp62 job differs from frozen job")
        return row
    if marker.is_file():
        return failure_receipt(
            job, target, "prior_attempt_interrupted_without_receipt", output, marker
        )
    inp = {
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "artifact_root": str(root),
        "phase_design_record_sha256": design["record_sha256"],
        "job": job,
        "target": target,
    }
    inp["input_identity_sha256"] = json_sha256(inp)
    atomic_json_dump(inp, input_path)
    atomic_json_dump(seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "phase": phase,
        "job_id": job["job_id"],
        "input_identity_sha256": inp["input_identity_sha256"],
        "attempt_ordinal": 1,
        "retry_permitted": False,
    }), marker)
    command = [
        sys.executable, str(WORKER), "--input", str(input_path), "--output", str(output)
    ]
    process = subprocess.Popen(
            command,
            cwd=PACKAGE_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(
            timeout=POLICY_WORKER_OUTER_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
        stderr = (
            (stderr or "")
            + f"\nouter worker timeout after {POLICY_WORKER_OUTER_TIMEOUT_SECONDS}s"
        )
    proc = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if not output.is_file():
        return failure_receipt(job, target, "worker_failed_without_receipt", output, marker, proc)
    row = read_json(output)
    assert_sealed(row, f"Exp62 job {job['job_id']}")
    return row


def progress(root: Path, phase: str, design: dict[str, Any], jobs: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for job in jobs:
        path = root / phase / "execution/jobs" / f"{job['job_id']}.json"
        if path.is_file():
            row = read_json(path)
            assert_sealed(row, f"Exp62 job {job['job_id']}")
            rows.append(row)
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "phase": phase,
        "roots": design["roots"],
        "planned_jobs": len(jobs),
        "completed_jobs": len(rows),
        "operational_failures": sum(row.get("operational_failure") is True for row in rows),
        "solved_jobs": sum(row.get("solved") is True for row in rows),
        "multistep_solved_jobs": sum(row.get("multi_step_solved") is True for row in rows),
        "tactic_invocations": sum(int(row.get("tactic_invocations", 0)) for row in rows),
        "complete": len(rows) == len(jobs),
        "next_step": f"Analyze Exp62 {phase}." if len(rows) == len(jobs) else "Continue frozen root order.",
    })
    atomic_json_dump(value, root / phase / "execution/progress.json")
    return value


def run(root: Path, phase: str, start_index: int, end_index: int | None) -> dict[str, Any]:
    load_installed_protocol(root)
    design = load_design(root, phase)
    targets = {row["target_id"]: row for row in read_jsonl(design["targets_path"])}
    jobs = read_jsonl(design["jobs_path"])
    selected_roots = design["root_order"][start_index:end_index]
    for root_position, target_id in enumerate(selected_roots, start=start_index):
        target = targets[target_id]
        root_jobs = [job for job in jobs if job["target_id"] == target_id]
        if [job["policy"] for job in root_jobs] != policy_order(target_id):
            raise ValueError("Exp62 frozen policy order changed")
        for job in root_jobs:
            row = run_job(root, phase, design, job, target)
            print(
                f"EXP62-{phase.upper()} root={root_position + 1}/{design['roots']} "
                f"policy={job['policy']} solved={int(row.get('solved') is True)} "
                f"depth={row.get('proof_length')} calls={row.get('tactic_invocations')} "
                f"stop={row.get('stop_reason')}",
                flush=True,
            )
            progress(root, phase, design, jobs)
    return progress(root, phase, design, jobs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--phase", required=True, choices=("pilot", "confirmation"))
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--end-index", type=int)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run(
        Path(args.artifact_root).resolve(), args.phase, args.start_index, args.end_index
    ), indent=2))
