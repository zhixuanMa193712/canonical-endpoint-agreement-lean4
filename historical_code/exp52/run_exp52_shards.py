"""Run one of 32 immutable Exp52 continuation-probe shards.

Cells are assigned by frozen cell-plan position modulo 32.  A shard is
single-threaded and owns its runtime, generated Lean source, content store,
claims, inputs, rows, and receipts.  Every cell launches a new worker process,
which launches exactly one fresh Lean process.  An existing claim without a
row is never retried and becomes an immutable orchestration-failure record.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from alignment_protocol import *  # noqa: F401,F403
from experiment52_live_worker import (
    INPUT_SCHEMA,
    LEAN_SOURCE_SHA256,
    WORKER_SCHEMA,
)


RUNNER_SCHEMA = "experiment52-safe-sharded-execution-fix4-v1"
WORKER = Path(__file__).resolve().with_name("experiment52_live_worker.py")


def _record_sha(value: Mapping[str, Any]) -> str:
    return json_sha256({
        key: item for key, item in value.items() if key != "record_sha256"
    })


def _proc_cmdline(pid: int) -> list[str] | None:
    """Return the exact Linux ``/proc`` argv, or ``None`` after exit.

    A missing ``/proc`` filesystem is treated conservatively: if the PID is
    still alive, the caller must stop rather than synthesize a row over a
    process whose identity cannot be proved.
    """
    proc_root = Path("/proc")
    if proc_root.is_dir():
        path = proc_root / str(pid) / "cmdline"
        try:
            payload = path.read_bytes()
        except (FileNotFoundError, ProcessLookupError):
            return None
        if not payload:
            return None
        return [os.fsdecode(item) for item in payload.rstrip(b"\0").split(b"\0")]
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return None
    raise RuntimeError(
        "cannot prove worker-process identity without Linux /proc; "
        "refusing to write a synthetic Exp52 row"
    )


def _assert_process_receipt(
    value: Mapping[str, Any], *, inp: Mapping[str, Any], cmd: list[str],
    inputp: Path, outp: Path,
) -> None:
    if not (
        value.get("schema") == PROCESS_LAUNCH_SCHEMA
        and value.get("alignment_version") == EXECUTION_ALIGNMENT_VERSION
        and value.get("mechanical_fix_id") == EXECUTION_FIX_ID
        and value.get("amendment_sha256") == inp["amendment_sha256"]
        and value.get("selection_ledger_sha256")
        == inp["selection_ledger_sha256"]
        and value.get("cell_id") == inp["cell_id"]
        and value.get("cell_index") == inp["cell_index"]
        and value.get("input_identity_sha256") == inp["input_identity_sha256"]
        and value.get("input") == str(inputp)
        and value.get("input_sha256") == file_sha256(inputp)
        and value.get("output") == str(outp)
        and value.get("command") == cmd
        and value.get("command_sha256") == json_sha256(cmd)
        and type(value.get("worker_pid")) is int
        and int(value["worker_pid"]) > 0
        and value.get("fresh_session_requested") is True
        and (
            value.get("worker_process_group_id") is None
            or type(value.get("worker_process_group_id")) is int
        )
        and value.get("fresh_session_observed")
        is (
            value.get("worker_process_group_id") == value.get("worker_pid")
        )
        and value.get("attempt_ordinal") == 1
        and value.get("scientific_retry_permitted") is False
        and value.get("record_sha256") == _record_sha(value)
    ):
        raise ValueError(f"Exp52 worker-process receipt changed: {inp['cell_id']}")


def _worker_still_active(value: Mapping[str, Any]) -> bool:
    current = _proc_cmdline(int(value["worker_pid"]))
    return current is not None and current == list(value["command"])


def _active_worker_pids_for_command(cmd: list[str]) -> list[int]:
    """Close the small claim-to-launch-receipt crash window by exact scan."""
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        raise RuntimeError(
            "cannot scan exact worker argv without Linux /proc; refusing to "
            "synthesize an Exp52 row from a claim lacking a launch receipt"
        )
    active: list[int] = []
    for path in proc_root.iterdir():
        if not path.name.isdigit():
            continue
        current = _proc_cmdline(int(path.name))
        if current == cmd:
            active.append(int(path.name))
    return sorted(active)


def _selection_plan(
    root: Path, source: Mapping[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]], Path, str]:
    summaryp = root / "exp52/selection/summary.json"
    if not summaryp.is_file():
        raise FileNotFoundError(summaryp)
    summary = read_json(summaryp)
    planp = root / str(summary.get(
        "execution_cell_plan", "exp52/selection/execution_cells.jsonl"
    ))
    if not planp.is_file():
        raise FileNotFoundError(planp)
    rows = read_jsonl(planp)
    if not (
        summary.get("selection_version") == fix3.EXP52_SELECTION_VERSION
        and summary.get("alignment_version") == SOURCE_FIX3_ALIGNMENT_VERSION
        and summary.get("mechanical_fix_id") == SOURCE_FIX3_FIX_ID
        and summary.get("amendment_sha256")
        == source["source_fix3_amendment_sha256"]
        and summary.get("exp52_protocol_sha256") == source["protocol_sha256"]
        and summary.get("selection_complete") is True
        and summary.get("execution_cells") == len(rows)
        and file_sha256(planp) == summary.get("execution_cell_plan_sha256")
        and len({row.get("cell_id") for row in rows}) == len(rows)
        and all(
            row.get("record_sha256") == _record_sha(row)
            and row.get("fresh_process_required") is True
            and row.get("scientific_retry_permitted") is False
            and row.get("manual_reconciliation_count") == 0
            for row in rows
        )
    ):
        raise ValueError("Exp52 frozen execution-cell plan changed")
    return summary, rows, planp, file_sha256(planp)


def _preflight_exact(
    root: Path, source: Mapping[str, Any], plan_sha: str
) -> dict[str, Any]:
    path = root / EXP52_PREFLIGHT_RELATIVE
    if not path.is_file():
        raise FileNotFoundError(path)
    value = read_json(path)
    if not (
        value.get("alignment_version") == EXECUTION_ALIGNMENT_VERSION
        and value.get("mechanical_fix_id") == EXECUTION_FIX_ID
        and value.get("amendment_sha256") == source["amendment_sha256"]
        and value.get("execution_cell_plan_sha256") == plan_sha
        and value.get("lean_source_sha256") == LEAN_SOURCE_SHA256
        and value.get("compile_gate") is True
        and value.get("theorem_sources_elaborated") == 0
        and value.get("candidate_tactics_executed") == 0
        and value.get("continuation_probes_executed") == 0
    ):
        raise ValueError("Exp52 compile-only preflight did not pass for this plan")
    return value


def _input_from_plan(
    *,
    root: Path,
    source: Mapping[str, Any],
    plan_sha: str,
    cell_index: int,
    cell: Mapping[str, Any],
) -> dict[str, Any]:
    candidate = cell["candidate"]
    value = {
        "schema": INPUT_SCHEMA,
        "version": 1,
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "mechanical_fix_id": EXECUTION_FIX_ID,
        "scientific_root": str(root),
        "amendment_sha256": source["amendment_sha256"],
        "exp52_protocol_sha256": source["protocol_sha256"],
        "selection_ledger_sha256": plan_sha,
        "selection_record_sha256": cell["selection_record_sha256"],
        "cell_plan_record_sha256": cell["record_sha256"],
        "cell_id": cell["cell_id"],
        "cell_index": cell_index,
        "root_id": cell["root_id"],
        "theorem_id": cell["theorem_id"],
        "rid": cell["rid"],
        "slug": cell["slug"],
        "pair_id": cell["pair_id"],
        "pair_role": cell["pair_role"],
        "side": cell["side"],
        "probe": cell["probe"],
        "probe_index": cell["probe_index"],
        "repeat_kind": cell["repeat_kind"],
        "source_exp51_row": cell["source_exp51_row"],
        "source_exp51_row_sha256": cell["source_exp51_row_sha256"],
        "candidate_tactic": candidate["tactic"],
        "candidate_head": candidate["head"],
        "candidate_position_frozen": candidate["candidate_index"],
        "candidate_record_sha256": candidate["candidate_record_sha256"],
        "expected_candidate_endpoint": candidate["endpoint"],
        "fresh_process_required": True,
        "attempts_permitted": 1,
        "scientific_retry_permitted": False,
        "manual_reconciliation_count": 0,
    }
    value["input_identity_sha256"] = json_sha256(value)
    return value


def _assert_row(
    row: Mapping[str, Any], inp: Mapping[str, Any], plan_sha: str
) -> None:
    if not (
        row.get("schema") == WORKER_SCHEMA
        and row.get("alignment_version") == EXECUTION_ALIGNMENT_VERSION
        and row.get("mechanical_fix_id") == EXECUTION_FIX_ID
        and row.get("cell_id") == inp["cell_id"]
        and row.get("cell_index") == inp["cell_index"]
        and row.get("amendment_sha256") == inp["amendment_sha256"]
        and row.get("selection_ledger_sha256") == plan_sha
        and row.get("source_exp51_row_sha256")
        == inp["source_exp51_row_sha256"]
        and row.get("candidate_record_sha256")
        == inp["candidate_record_sha256"]
        and row.get("expected_candidate_endpoint")
        == inp["expected_candidate_endpoint"]
        and row.get("input_identity_sha256")
        == inp["input_identity_sha256"]
        and row.get("record_complete") is True
        and row.get("scientific_retry_permitted") is False
        and row.get("manual_reconciliation_count") == 0
        and row.get("record_sha256") == _record_sha(row)
    ):
        raise ValueError(f"Exp52 cell row changed: {inp['cell_id']}")


def _synthetic_failure(
    inp: Mapping[str, Any], error_type: str, diagnostic: str
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema": WORKER_SCHEMA,
        "version": 1,
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "mechanical_fix_id": EXECUTION_FIX_ID,
        "worker_version": "experiment52-fix4-orchestrator-failure-v1",
        **{
            key: inp[key] for key in (
                "cell_id", "cell_index", "amendment_sha256",
                "exp52_protocol_sha256", "selection_ledger_sha256",
                "selection_record_sha256", "cell_plan_record_sha256",
                "root_id", "theorem_id", "rid", "slug", "pair_id",
                "pair_role", "side", "probe", "probe_index", "repeat_kind",
                "candidate_tactic", "candidate_head",
                "candidate_position_frozen", "candidate_record_sha256",
                "expected_candidate_endpoint", "input_identity_sha256",
                "source_exp51_row",
                "source_exp51_row_sha256",
            )
        },
        "record_complete": True,
        "worker_ok": False,
        "valid_reconstruction": False,
        "candidate_reconstruction_ok": False,
        "probe_attempted": False,
        "probe_executable": False,
        "probe_status": "not_executed",
        "failure_category": "worker_or_protocol_failure",
        "response_component": "invalid_reconstruction",
        "orchestrator_error_type": error_type,
        "diagnostic_tail": diagnostic[-12000:],
        "process": {
            "fresh_lean_process": False,
            "attempt_ordinal": 1,
            "retry_permitted": False,
            "timeout_seconds": LEAN_TIMEOUT_SECONDS,
        },
        "manual_reconciliation_count": 0,
        "scientific_retry_permitted": False,
    }
    value["record_sha256"] = _record_sha(value)
    return value


def _invoke_once(
    *,
    root: Path,
    shard_root: Path,
    runtime_root: Path,
    source: Mapping[str, Any],
    plan_sha: str,
    cell_index: int,
    cell: Mapping[str, Any],
) -> dict[str, Any]:
    cell_id = str(cell["cell_id"])
    inputp = shard_root / "inputs" / f"{cell_id}.json"
    claimp = shard_root / "claims" / f"{cell_id}.json"
    outp = shard_root / "rows" / f"{cell_id}.json"
    receiptp = shard_root / "receipts" / f"{cell_id}.json"
    processp = shard_root / "worker_processes" / f"{cell_id}.json"
    inp = _input_from_plan(
        root=root, source=source, plan_sha=plan_sha,
        cell_index=cell_index, cell=cell,
    )
    if inputp.is_file():
        if read_json(inputp) != inp:
            raise ValueError(f"existing Exp52 cell input changed: {cell_id}")
    else:
        atomic_json_dump(inp, inputp)
    cmd = [
        sys.executable, str(WORKER),
        "--input", str(inputp), "--output", str(outp),
        "--runtime-root", str(runtime_root),
        "--timeout", str(LEAN_TIMEOUT_SECONDS),
    ]
    if outp.is_file():
        row = read_json(outp)
        _assert_row(row, inp, plan_sha)
    elif claimp.is_file():
        claim = read_json(claimp)
        if not (
            claim.get("cell_id") == cell_id
            and claim.get("cell_index") == cell_index
            and claim.get("amendment_sha256") == source["amendment_sha256"]
            and claim.get("attempts_permitted") == 1
            and claim.get("scientific_retry_permitted") is False
        ):
            raise ValueError(f"existing Exp52 execution claim changed: {cell_id}")
        process_receipt = read_json(processp) if processp.is_file() else None
        if process_receipt is not None:
            _assert_process_receipt(
                process_receipt, inp=inp, cmd=cmd, inputp=inputp, outp=outp,
            )
            if _worker_still_active(process_receipt):
                raise RuntimeError(
                    f"Exp52 worker for {cell_id} is still active with the exact "
                    "recorded /proc cmdline; wait for it instead of retrying or "
                    "writing a synthetic row"
                )
        else:
            active = _active_worker_pids_for_command(cmd)
            if active:
                raise RuntimeError(
                    f"Exp52 worker(s) {active} for {cell_id} are still active "
                    "with the exact expected /proc cmdline; the launch receipt "
                    "was interrupted, so no synthetic row or retry is allowed"
                )
        # The worker may have atomically committed its row between the first
        # existence check and the process-identity check.
        if outp.is_file():
            row = read_json(outp)
            _assert_row(row, inp, plan_sha)
        else:
            error_type = (
                "orchestrator_interruption_after_worker_exit"
                if process_receipt is not None else
                "orchestrator_interruption_before_worker_launch_receipt"
            )
            row = _synthetic_failure(
                inp,
                error_type,
                "An immutable prior claim exists, no exact worker is still "
                "active, and no worker row exists; no retry was run.",
            )
            atomic_json_dump(row, outp)
    else:
        exclusive_create_json(claimp, {
            "version": 1,
            "cell_id": cell_id,
            "cell_index": cell_index,
            "amendment_sha256": source["amendment_sha256"],
            "selection_ledger_sha256": plan_sha,
            "input_identity_sha256": inp["input_identity_sha256"],
            "attempts_permitted": 1,
            "scientific_retry_permitted": False,
        })
        proc = subprocess.Popen(
            cmd,
            cwd=Path(__file__).resolve().parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            worker_process_group_id: int | None = os.getpgid(proc.pid)
        except ProcessLookupError:
            worker_process_group_id = None
        process_receipt = {
            "schema": PROCESS_LAUNCH_SCHEMA,
            "version": 1,
            "alignment_version": EXECUTION_ALIGNMENT_VERSION,
            "mechanical_fix_id": EXECUTION_FIX_ID,
            "amendment_sha256": source["amendment_sha256"],
            "selection_ledger_sha256": plan_sha,
            "cell_id": cell_id,
            "cell_index": cell_index,
            "input": str(inputp),
            "input_sha256": file_sha256(inputp),
            "input_identity_sha256": inp["input_identity_sha256"],
            "output": str(outp),
            "worker_pid": proc.pid,
            "fresh_session_requested": True,
            "worker_process_group_id": worker_process_group_id,
            "fresh_session_observed": worker_process_group_id == proc.pid,
            "command": cmd,
            "command_sha256": json_sha256(cmd),
            "attempt_ordinal": 1,
            "scientific_retry_permitted": False,
        }
        process_receipt["record_sha256"] = _record_sha(process_receipt)
        atomic_json_dump(process_receipt, processp)
        _assert_process_receipt(
            process_receipt, inp=inp, cmd=cmd, inputp=inputp, outp=outp,
        )
        try:
            stdout, stderr = proc.communicate(timeout=LEAN_TIMEOUT_SECONDS + 180)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                stdout, stderr = proc.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                stdout, stderr = proc.communicate()
        if not outp.is_file():
            row = _synthetic_failure(
                inp,
                "worker_process_missing_record",
                f"returncode={proc.returncode}\nstdout={stdout[-4000:]}\nstderr={stderr[-8000:]}",
            )
            atomic_json_dump(row, outp)
        row = read_json(outp)
        _assert_row(row, inp, plan_sha)
    process_receipt_exact = False
    if processp.is_file():
        launch = read_json(processp)
        _assert_process_receipt(
            launch, inp=inp, cmd=cmd, inputp=inputp, outp=outp,
        )
        process_receipt_exact = True
    receipt = {
        "version": 1,
        "cell_index": cell_index,
        "cell_id": cell_id,
        "amendment_sha256": source["amendment_sha256"],
        "selection_ledger_sha256": plan_sha,
        "worker_row": str(outp),
        "worker_row_sha256": file_sha256(outp),
        "worker_process_receipt": str(processp) if processp.is_file() else None,
        "worker_process_receipt_sha256": (
            file_sha256(processp) if processp.is_file() else None
        ),
        "worker_process_receipt_exact": process_receipt_exact,
        "record_complete": row.get("record_complete") is True,
        "fresh_lean_process": row.get("process", {}).get(
            "fresh_lean_process"
        ) is True,
        "attempt_ordinal": row.get("process", {}).get("attempt_ordinal"),
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
    }
    receipt["record_sha256"] = _record_sha(receipt)
    if receiptp.is_file():
        if read_json(receiptp) != receipt:
            raise ValueError(f"existing Exp52 cell receipt changed: {cell_id}")
    else:
        atomic_json_dump(receipt, receiptp)
    return row


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    if not 0 <= args.shard_index < EXP52_SHARD_COUNT:
        raise ValueError(f"shard-index must be in [0, {EXP52_SHARD_COUNT})")
    source = validate_amendment(root)
    selection, cells, planp, plan_sha = _selection_plan(root, source)
    _preflight_exact(root, source, plan_sha)
    assigned = [
        (index, row) for index, row in enumerate(cells)
        if shard_index(index, EXP52_SHARD_COUNT) == args.shard_index
    ]
    shard_root = root / "exp52/execution/shards" / f"shard-{args.shard_index:02d}"
    runtime_root = shard_root / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    lockp = shard_root / "shard.lock"
    lockp.parent.mkdir(parents=True, exist_ok=True)
    with lockp.open("a+", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(
                f"Exp52 shard {args.shard_index} is already running"
            ) from exc
        assignment = [
            {"cell_index": index, "cell_id": row["cell_id"]}
            for index, row in assigned
        ]
        claim = {
            "schema": RUNNER_SCHEMA,
            "version": 1,
            "alignment_version": EXECUTION_ALIGNMENT_VERSION,
            "amendment_sha256": source["amendment_sha256"],
            "selection_ledger_sha256": plan_sha,
            "shard_index": args.shard_index,
            "shard_count": EXP52_SHARD_COUNT,
            "assignment": assignment,
            "assignment_sha256": json_sha256(assignment),
            "scientific_retry_permitted": False,
        }
        claimp = shard_root / "execution_claim.json"
        if claimp.is_file():
            if read_json(claimp) != claim:
                raise ValueError("existing Exp52 shard claim changed")
        else:
            exclusive_create_json(claimp, claim)
        rows = []
        for ordinal, (cell_index, cell) in enumerate(assigned, 1):
            print(
                f"EXP52-SHARD {args.shard_index:02d} {ordinal}/{len(assigned)} "
                f"{cell['slug']} {cell['pair_role']} {cell['side']} "
                f"{cell['repeat_kind']} probe={cell['probe']}",
                flush=True,
            )
            rows.append(_invoke_once(
                root=root,
                shard_root=shard_root,
                runtime_root=runtime_root,
                source=source,
                plan_sha=plan_sha,
                cell_index=cell_index,
                cell=cell,
            ))
        failures = Counter(
            str(row.get("failure_category")) for row in rows
            if row.get("probe_status") != "success"
        )
        value: dict[str, Any] = {
            "schema": RUNNER_SCHEMA,
            "version": 1,
            "alignment_version": EXECUTION_ALIGNMENT_VERSION,
            "mechanical_fix_id": EXECUTION_FIX_ID,
            "amendment_sha256": source["amendment_sha256"],
            "selection_ledger_sha256": plan_sha,
            "shard_index": args.shard_index,
            "shard_count": EXP52_SHARD_COUNT,
            "assignment_sha256": claim["assignment_sha256"],
            "cells_expected": len(assigned),
            "cells_recorded": len(rows),
            "fresh_lean_process_receipts": sum(
                row.get("process", {}).get("fresh_lean_process") is True
                for row in rows
            ),
            "worker_process_launch_receipts": sum(
                (
                    shard_root / "worker_processes" /
                    f"{cell['cell_id']}.json"
                ).is_file()
                for _, cell in assigned
            ),
            "valid_reconstructions": sum(
                row.get("valid_reconstruction") is True for row in rows
            ),
            "probe_successes": sum(
                row.get("probe_status") == "success" for row in rows
            ),
            "probe_failures": sum(
                row.get("probe_status") == "failure" for row in rows
            ),
            "failure_categories": dict(sorted(failures.items())),
            "all_attempt_ordinals_one": all(
                row.get("process", {}).get("attempt_ordinal") == 1
                for row in rows
            ),
            "scientific_retry_count": 0,
            "manual_reconciliation_count": 0,
        }
        value["shard_completion_gate"] = bool(
            value["cells_recorded"] == value["cells_expected"]
            and value["all_attempt_ordinals_one"]
            and all(row.get("record_complete") is True for row in rows)
        )
        value["all_fresh_lean_processes"] = bool(
            value["fresh_lean_process_receipts"] == value["cells_expected"]
        )
        value["all_worker_process_launch_receipts_exact"] = bool(
            value["worker_process_launch_receipts"] == value["cells_expected"]
        )
        # `shard_gate` is deliberately an immutable-accounting gate.  Fresh
        # process integrity remains separate so a no-retry synthetic row can
        # still be finalized and produce an auditable invalid_execution.
        value["shard_gate"] = value["shard_completion_gate"]
        value["shard_execution_integrity_gate"] = bool(
            value["shard_completion_gate"]
            and value["all_fresh_lean_processes"]
            and value["all_worker_process_launch_receipts_exact"]
        )
        value["next_step"] = (
            "Run remaining Exp52 shards, then finalize execution."
            if value["shard_gate"] else
            "STOP; complete immutable Exp52 cell accounting without retry."
        )
        summaryp = shard_root / "summary.json"
        if summaryp.is_file() and read_json(summaryp) != value:
            raise ValueError("existing Exp52 shard summary changed")
        atomic_json_dump(value, summaryp)
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(SCIENTIFIC_ROOT))
    parser.add_argument("--shard-index", type=int, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    result = run(parse_args())
    raise SystemExit(0 if result.get("shard_gate") is True else 2)
