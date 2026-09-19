"""Run the frozen Exp62 live solvability qualification frame without retries."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from experiment62_protocol import *


WORKER = PACKAGE_ROOT / "experiment62_qualification_worker.py"


def unresolved_receipt(target: dict[str, Any], marker: Path, output: Path) -> dict[str, Any]:
    value = seal({
        "schema": QUALIFICATION_SCHEMA,
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "target_id": target["target_id"],
        "role": target["role"],
        "stratum": target["stratum"],
        "theorem_id": target["theorem_id"],
        "target_record_sha256": target["record_sha256"],
        "attempt_ordinal": 1,
        "retry_permitted": False,
        "qualification_gate": False,
        "operational_failure": True,
        "first_failed_gate": "prior_attempt_interrupted_without_receipt",
        "attempt_marker_sha256": file_sha256(marker),
        "four_scientific_policies_executed": 0,
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
    })
    atomic_json_dump(value, output)
    return value


def run_one(root: Path, target: dict[str, Any]) -> dict[str, Any]:
    target_id = target["target_id"]
    output = root / "qualification/receipts" / f"{target_id}.json"
    marker = root / "qualification/attempts" / f"{target_id}.json"
    target_path = root / "qualification/targets" / f"{target_id}.json"
    if output.is_file():
        value = read_json(output)
        assert_sealed(value, f"qualification {target_id}")
        return value
    if marker.is_file():
        return unresolved_receipt(target, marker, output)
    atomic_json_dump(target, target_path)
    atomic_json_dump(seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "target_id": target_id,
        "target_record_sha256": target["record_sha256"],
        "attempt_ordinal": 1,
        "retry_permitted": False,
    }), marker)
    command = [
        sys.executable, str(WORKER), "--target", str(target_path), "--output", str(output)
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
        stdout, stderr = process.communicate(timeout=QUALIFICATION_TIMEOUT_SECONDS)
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
    proc = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if not output.is_file():
        value = seal({
            "schema": QUALIFICATION_SCHEMA,
            "version": VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "target_id": target_id,
            "role": target["role"],
            "stratum": target["stratum"],
            "theorem_id": target["theorem_id"],
            "target_record_sha256": target["record_sha256"],
            "attempt_ordinal": 1,
            "retry_permitted": False,
            "qualification_gate": False,
            "operational_failure": True,
            "first_failed_gate": "worker_failed_without_receipt",
            "worker_returncode": proc.returncode,
            "worker_stdout_tail": proc.stdout[-2000:],
            "worker_stderr_tail": proc.stderr[-4000:],
            "four_scientific_policies_executed": 0,
            "scientific_retry_count": 0,
            "manual_reconciliation_count": 0,
        })
        atomic_json_dump(value, output)
    value = read_json(output)
    assert_sealed(value, f"qualification {target_id}")
    return value


def summary(root: Path, frame: list[dict[str, Any]]) -> dict[str, Any]:
    receipts = []
    for target in frame:
        path = root / "qualification/receipts" / f"{target['target_id']}.json"
        if path.is_file():
            row = read_json(path)
            assert_sealed(row, f"qualification {target['target_id']}")
            receipts.append(row)
    counts = {
        role: {
            stratum: sum(
                row.get("qualification_gate") is True
                and row["role"] == role and row["stratum"] == stratum
                for row in receipts
            )
            for stratum in STRATA
        }
        for role in ("pilot", "confirmation")
    }
    complete = len(receipts) == len(frame)
    gate = bool(
        complete
        and all(counts["pilot"][stratum] >= PILOT_ROOTS_PER_STRATUM for stratum in STRATA)
        and all(counts["confirmation"][stratum] >= CONFIRMATION_ROOTS_PER_STRATUM for stratum in STRATA)
    )
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "candidate_frame_rows": len(frame),
        "completed_receipts": len(receipts),
        "qualification_passes": sum(row.get("qualification_gate") is True for row in receipts),
        "qualification_failures": sum(row.get("qualification_gate") is not True for row in receipts),
        "operational_failures": sum(row.get("operational_failure") is True for row in receipts),
        "passes_by_role_stratum": counts,
        "qualification_complete": complete,
        "qualification_gate": gate,
        "four_scientific_policies_executed": 0,
        "next_step": "Freeze and run pilot." if gate else "STOP: solvable frame recruitment no-go.",
    })
    atomic_json_dump(value, root / "qualification/summary.json")
    return value


def run(root: Path, workers: int) -> dict[str, Any]:
    if not 1 <= workers <= 4:
        raise ValueError("qualification workers must be between 1 and 4")
    load_installed_protocol(root)
    preflight = read_json(root / "preflight/summary.json")
    assert_sealed(preflight, "Exp62 preflight")
    if preflight.get("preflight_gate") is not True:
        raise ValueError("Exp62 preflight did not pass")
    frame = read_jsonl(root / "frozen/candidate_frame.jsonl")
    if len(frame) != EXPECTED_FRAME_ROWS:
        raise ValueError("Exp62 candidate frame row count changed")
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(run_one, root, target): target for target in frame}
        done = 0
        for future in concurrent.futures.as_completed(futures):
            target = futures[future]
            row = future.result()
            done += 1
            print(
                f"EXP62-QUALIFY {done}/{len(frame)} {target['role']} {target['stratum']} "
                f"{target['full_name']} gate={int(row.get('qualification_gate') is True)} "
                f"failed={row.get('first_failed_gate')}",
                flush=True,
            )
            summary(root, frame)
    return summary(root, frame)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--workers", type=int, default=2)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run(Path(args.artifact_root).resolve(), args.workers), indent=2))
