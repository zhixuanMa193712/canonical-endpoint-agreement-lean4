"""Run one immutable Exp51 scientific shard under execution-alignment fix3.

The 576 frozen scientific roots are partitioned by their frozen list index
modulo 16.  A shard has its own worker inputs, generated Lean source, content
store, claims, and theorem rows.  Completed rows are resumable; a claimed root
without a worker row is recorded as an unevaluable orchestration interruption
and is never retried.
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
from typing import Any

from alignment_protocol import *  # noqa: F401,F403


SHARD_COUNT = EXP51_SHARD_COUNT
WORKER = base.PACKAGE_ROOT / "experiment51_live_worker.py"


def amendment_sha(root: Path) -> str:
    return base.file_sha256(root / "frozen/execution_alignment_fix3.json")


def frozen_context(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], str, str]:
    validate_amendment(root)
    cfg, targets, _protocol, _amendment = load_source_bundle(root)
    cfgp = root / "frozen/experiment51_config.json"
    targetsp = root / "frozen/targets.json"
    envp = root / EXP51_ENVIRONMENT_RELATIVE
    preflightp = root / EXP51_PREFLIGHT_RELATIVE
    for path in (cfgp, targetsp, envp, preflightp):
        if not path.is_file():
            raise FileNotFoundError(path)
    cfg_sha = base.file_sha256(cfgp)
    env = base.read_json(envp)
    preflight = base.read_json(preflightp)
    amend_sha = amendment_sha(root)
    if not (
        env.get("environment_gate") is True
        and env.get("source_config_sha256") == cfg_sha
        and env.get("amendment_sha256") == amend_sha
        and env.get("alignment_version") == EXECUTION_ALIGNMENT_VERSION
        and preflight.get("compile_ok") is True
        and preflight.get("source_config_sha256") == cfg_sha
        and preflight.get("amendment_sha256") == amend_sha
        and preflight.get("alignment_version") == EXECUTION_ALIGNMENT_VERSION
        and len(targets) == cfg.get("roots") == 576
        and cfg.get("repository_count") == 12
    ):
        raise ValueError("Exp51 execution prerequisites differ from the fix3 amendment")
    return cfg, targets, cfg_sha, amend_sha


def phase_targets(
    root: Path,
    cfg: dict[str, Any],
    targets: list[dict[str, Any]],
    phase: str,
    shard_index: int,
    amend_sha: str,
) -> list[tuple[int, dict[str, Any]]]:
    if not 0 <= shard_index < SHARD_COUNT:
        raise ValueError(f"shard-index must be in [0, {SHARD_COUNT})")
    if phase == "smoke":
        if shard_index != 0:
            raise ValueError("the frozen four-root smoke is assigned only to shard 0")
        smoke_ids = list(cfg.get("smoke_target_ids", []))
        smoke_set = set(smoke_ids)
        selected = [(index, row) for index, row in enumerate(targets)
                    if row["theorem_id"] in smoke_set]
        if len(smoke_ids) != len(smoke_set) or len(selected) != len(smoke_ids):
            raise ValueError("frozen smoke target identity changed")
        return selected
    smoke = base.read_json(root / "smoke/summary.json")
    if not (
        smoke.get("smoke_gate") is True
        and smoke.get("config_sha256")
        == base.file_sha256(root / "frozen/experiment51_config.json")
        and smoke.get("amendment_sha256") == amend_sha
    ):
        raise ValueError("fix3 smoke did not pass for this amendment")
    selected = [(index, row) for index, row in enumerate(targets)
                if index % SHARD_COUNT == shard_index]
    if len(selected) != 36:
        raise ValueError("scientific shard is not the frozen 36-root partition")
    return selected


def expected_input(
    runtime_root: Path,
    target: dict[str, Any],
    cfg_sha: str,
    phase: str,
    environment_sha: str,
) -> dict[str, Any]:
    candidates = list(target["alternatives"])
    value = {
        "version": 1,
        "protocol_version": base.PROTOCOL_VERSION,
        "mode": phase,
        "config_sha256": cfg_sha,
        "environment_receipt_sha256": environment_sha,
        "artifact_root": str(runtime_root),
        "project": target["checkout"],
        "slug": target["slug"],
        "commit": target["commit"],
        "file_path": target["file_path"],
        "full_name": target["full_name"],
        "theorem_id": target["theorem_id"],
        "source_file_sha256": target["source_file_sha256"],
        "trace_root_state": target["trace_root_state"],
        "trace_root_state_sha256": target["trace_root_state_sha256"],
        "authored_tactic": target["authored_tactic"],
        "target_pos": target["target_pos"],
        "target_end_pos": target["target_end_pos"],
        "ast_sha256": target["ast_sha256"],
        "candidates": candidates,
        "candidates_sha256": base.json_sha256(candidates),
        "candidate_positions_frozen": list(range(len(candidates))),
    }
    value["execution_record_id"] = base.json_sha256({
        "protocol": base.PROTOCOL_VERSION,
        "mode": phase,
        "theorem_id": target["theorem_id"],
        "candidates": candidates,
    })
    return value


def assert_row(
    row: dict[str, Any], target: dict[str, Any], phase: str, cfg_sha: str
) -> None:
    candidates = list(row.get("candidates", []))
    if not (
        row.get("protocol_version") == base.PROTOCOL_VERSION
        and row.get("mode") == phase
        and row.get("config_sha256") == cfg_sha
        and row.get("theorem_id") == target["theorem_id"]
        and row.get("source_file_sha256") == target["source_file_sha256"]
        and row.get("candidate_order") == target["alternatives"]
    ):
        raise ValueError(f"worker row identity mismatch: {target['theorem_id']}")
    expected_record_sha = base.json_sha256({
        key: item for key, item in row.items() if key != "record_sha256"
    })
    if row.get("record_sha256") != expected_record_sha:
        raise ValueError(f"worker record hash mismatch: {target['theorem_id']}")
    if row.get("worker_ok") is True and (
        len(candidates) != base.CANDIDATES_PER_ROOT
        or row.get("complete_candidate_order") is not True
    ):
        raise ValueError(f"evaluable row lacks all 23 candidates: {target['theorem_id']}")


def synthetic_failure(
    target: dict[str, Any], cfg_sha: str, phase: str, error_type: str,
    diagnostic: str,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema": base.WORKER_SCHEMA,
        "version": 1,
        "protocol_version": base.PROTOCOL_VERSION,
        "worker_version": "execution-alignment-fix3-orchestrator-failure-v1",
        "mode": phase,
        "config_sha256": cfg_sha,
        "slug": target["slug"],
        "commit": target["commit"],
        "file_path": target["file_path"],
        "full_name": target["full_name"],
        "theorem_id": target["theorem_id"],
        "source_file_sha256": target["source_file_sha256"],
        "trace_root_state_sha256": target["trace_root_state_sha256"],
        "target_pos": target["target_pos"],
        "target_end_pos": target["target_end_pos"],
        "ast_sha256": target["ast_sha256"],
        "candidate_order": list(target["alternatives"]),
        "candidate_order_sha256": base.json_sha256(target["alternatives"]),
        "worker_ok": False,
        "error_type": error_type,
        "failure_category": "worker_or_protocol_failure",
        "diagnostic_tail": diagnostic[-12000:],
        "candidates": [],
    }
    value["record_sha256"] = base.json_sha256(value)
    return value


def recorded_process_is_live(processp: Path, inputp: Path) -> bool:
    """Conservatively detect an orphaned worker before declaring interruption."""
    candidate_pids: list[int] = []
    if processp.is_file():
        value = base.read_json(processp)
        pid = value.get("pid")
        if type(pid) is not int or pid <= 0:
            raise ValueError(f"invalid worker process receipt: {processp}")
        candidate_pids.append(pid)
    proc_root = Path("/proc")
    if proc_root.is_dir():
        candidate_pids.extend(
            int(path.name) for path in proc_root.iterdir() if path.name.isdigit()
        )
    for pid in set(candidate_pids):
        cmdlinep = Path(f"/proc/{pid}/cmdline")
        if not cmdlinep.is_file():
            continue
        try:
            command = cmdlinep.read_bytes().replace(b"\x00", b" ").decode(
                "utf-8", errors="replace"
            )
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if str(WORKER) in command and str(inputp) in command:
            return True
    return False


def invoke_once(
    *,
    root: Path,
    shard_root: Path,
    runtime_root: Path,
    target: dict[str, Any],
    frozen_index: int,
    phase: str,
    cfg_sha: str,
    amend_sha: str,
    lean_timeout: int,
) -> dict[str, Any]:
    safe = base.safe_slug(target["slug"])
    outp = shard_root / "theorems" / safe / f"{target['rid']}.json"
    inputp = shard_root / "inputs" / safe / f"{target['rid']}.json"
    claimp = shard_root / "claims" / safe / f"{target['rid']}.json"
    receiptp = shard_root / "receipts" / safe / f"{target['rid']}.json"
    processp = shard_root / "processes" / safe / f"{target['rid']}.json"
    environment_sha = base.file_sha256(root / EXP51_ENVIRONMENT_RELATIVE)
    inp = expected_input(runtime_root, target, cfg_sha, phase, environment_sha)
    if inputp.is_file():
        if base.read_json(inputp) != inp:
            raise ValueError(f"existing worker input changed: {target['theorem_id']}")
    else:
        base.atomic_json_dump(inp, inputp)
    if outp.is_file():
        row = base.read_json(outp)
        assert_row(row, target, phase, cfg_sha)
    elif claimp.is_file():
        claim = base.read_json(claimp)
        if not (
            claim.get("amendment_sha256") == amend_sha
            and claim.get("frozen_target_index") == frozen_index
            and claim.get("theorem_id") == target["theorem_id"]
            and claim.get("candidate_execution_attempts_permitted") == 1
        ):
            raise ValueError(f"existing execution claim changed: {target['theorem_id']}")
        if recorded_process_is_live(processp, inputp):
            raise RuntimeError(
                f"claimed worker is still running: {target['theorem_id']}"
            )
        row = synthetic_failure(
            target, cfg_sha, phase,
            "orchestrator_interruption_without_worker_receipt",
            "A prior immutable execution claim exists without a worker row; no retry was run.",
        )
        base.atomic_json_dump(row, outp)
    else:
        base.exclusive_create_json(claimp, {
            "version": 1,
            "amendment_sha256": amend_sha,
            "phase": phase,
            "frozen_target_index": frozen_index,
            "theorem_id": target["theorem_id"],
            "target_identity_sha256": target["target_identity_sha256"],
            "candidate_execution_attempts_permitted": 1,
            "scientific_retry_permitted": False,
        })
        cmd = [
            sys.executable, str(WORKER), "--input", str(inputp),
            "--output", str(outp), "--generated-dir", str(runtime_root / "generated"),
            "--timeout", str(lean_timeout),
        ]
        proc = subprocess.Popen(
            cmd, cwd=base.PACKAGE_ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
        )
        base.exclusive_create_json(processp, {
            "version": 1,
            "amendment_sha256": amend_sha,
            "theorem_id": target["theorem_id"],
            "pid": proc.pid,
            "input": str(inputp),
            "output": str(outp),
        })
        try:
            stdout, stderr = proc.communicate(timeout=lean_timeout + 120)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                stdout, stderr = proc.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                stdout, stderr = proc.communicate()
            row = synthetic_failure(
                target, cfg_sha, phase, "orchestrator_timeout",
                f"stdout={stdout[-4000:]}\nstderr={stderr[-8000:]}",
            )
            base.atomic_json_dump(row, outp)
        if not outp.is_file():
            row = synthetic_failure(
                target, cfg_sha, phase, "worker_process_missing_record",
                f"returncode={proc.returncode}\nstdout={stdout[-4000:]}\nstderr={stderr[-8000:]}",
            )
            base.atomic_json_dump(row, outp)
        row = base.read_json(outp)
        assert_row(row, target, phase, cfg_sha)
    receipt = {
        "version": 1,
        "amendment_sha256": amend_sha,
        "phase": phase,
        "frozen_target_index": frozen_index,
        "theorem_id": target["theorem_id"],
        "target_identity_sha256": target["target_identity_sha256"],
        "worker_row": str(outp),
        "worker_row_sha256": base.file_sha256(outp),
        "worker_ok": row.get("worker_ok") is True,
        "candidate_attempts": len(row.get("candidates", [])),
        "manual_reconciliation_count": 0,
    }
    if receiptp.is_file():
        if base.read_json(receiptp) != receipt:
            raise ValueError(f"existing row receipt changed: {target['theorem_id']}")
    else:
        base.atomic_json_dump(receipt, receiptp)
    return row


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    cfg, targets, cfg_sha, amend_sha = frozen_context(root)
    assigned = phase_targets(root, cfg, targets, args.phase, args.shard_index, amend_sha)
    shard_root = root / args.phase / "shards" / f"shard-{args.shard_index:02d}"
    runtime_root = shard_root / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    lockp = shard_root / "shard.lock"
    lockp.parent.mkdir(parents=True, exist_ok=True)
    with lockp.open("a+", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"shard {args.shard_index} is already running") from exc
        assignment = [{"frozen_target_index": index,
                       "theorem_id": target["theorem_id"]}
                      for index, target in assigned]
        claim = {
            "version": 1,
            "amendment_sha256": amend_sha,
            "phase": args.phase,
            "shard_index": args.shard_index,
            "shard_count": SHARD_COUNT,
            "assignment": assignment,
            "assignment_sha256": base.json_sha256(assignment),
            "scientific_retry_permitted": False,
        }
        claimp = shard_root / "execution_claim.json"
        if claimp.is_file():
            if base.read_json(claimp) != claim:
                raise ValueError("existing shard claim differs from frozen assignment")
        else:
            base.exclusive_create_json(claimp, claim)
        rows = []
        for ordinal, (frozen_index, target) in enumerate(assigned, 1):
            print(
                f"EXP51-{args.phase.upper()}-SHARD {args.shard_index:02d} "
                f"{ordinal}/{len(assigned)} {target['slug']} {target['full_name']}",
                flush=True,
            )
            rows.append(invoke_once(
                root=root, shard_root=shard_root, runtime_root=runtime_root,
                target=target, frozen_index=frozen_index, phase=args.phase,
                cfg_sha=cfg_sha, amend_sha=amend_sha,
                lean_timeout=args.lean_timeout,
            ))
        failures = Counter(
            row.get("error_type", "worker_gate") for row in rows
            if row.get("worker_ok") is not True
        )
        value = {
            "version": 1,
            "protocol_version": base.PROTOCOL_VERSION,
            "amendment_sha256": amend_sha,
            "phase": args.phase,
            "shard_index": args.shard_index,
            "shard_count": SHARD_COUNT,
            "config_sha256": cfg_sha,
            "assignment_sha256": claim["assignment_sha256"],
            "roots_expected": len(assigned),
            "root_receipts": len(rows),
            "evaluable_roots": sum(row.get("worker_ok") is True for row in rows),
            "candidate_attempts_recorded": sum(len(row.get("candidates", [])) for row in rows),
            "all_evaluable_rows_have_23_attempts": all(
                row.get("worker_ok") is not True
                or len(row.get("candidates", [])) == base.CANDIDATES_PER_ROOT
                for row in rows
            ),
            "failure_categories": dict(sorted(failures.items())),
            "manual_reconciliation_count": 0,
        }
        value["shard_gate"] = bool(
            value["root_receipts"] == value["roots_expected"]
            and value["all_evaluable_rows_have_23_attempts"]
        )
        value["next_step"] = (
            "Run remaining frozen shards, then finalize execution."
            if value["shard_gate"] else "STOP; preserve immutable shard evidence."
        )
        summaryp = shard_root / "summary.json"
        if summaryp.is_file() and base.read_json(summaryp) != value:
            raise ValueError("existing shard summary differs from reconstructed summary")
        base.atomic_json_dump(value, summaryp)
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(base.SERVER_ROOT / "artifacts/v51/external_repository_replication_scientific"),
    )
    parser.add_argument("--phase", choices=("smoke", "scientific"), required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--lean-timeout", type=int, default=900)
    return parser.parse_args()


if __name__ == "__main__":
    result = run(parse_args())
    raise SystemExit(0 if result.get("shard_gate") is True else 2)
