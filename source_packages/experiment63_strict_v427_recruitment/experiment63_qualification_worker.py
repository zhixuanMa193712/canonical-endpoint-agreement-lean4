"""Run one serial, disk-bounded build/trace/authored-replay qualification."""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from experiment63_protocol import *

sys.path.insert(0, str(MZX_ROOT / "experiment51_external_repository_replication"))
import screen_experiment51_repositories as backend  # type: ignore


class ResourceBudgetExceeded(RuntimeError):
    pass


class DiskTracker:
    def __init__(self, checkout: Path) -> None:
        self.checkout = checkout
        self.free_before = shutil.disk_usage(MZX_ROOT).free
        self.minimum_free = self.free_before
        self.termination_reason: str | None = None

    def poll(self) -> None:
        free = shutil.disk_usage(MZX_ROOT).free
        self.minimum_free = min(self.minimum_free, free)
        delta = max(0, self.free_before - free)
        if free < GLOBAL_FREE_DISK_FLOOR_BYTES:
            self.termination_reason = "global_disk_floor"
            raise ResourceBudgetExceeded("global disk floor reached")
        if delta > PER_REPOSITORY_DISK_LIMIT_BYTES:
            self.termination_reason = "per_repository_disk_budget"
            raise ResourceBudgetExceeded("per-repository physical disk budget exceeded")

    def record(self) -> dict[str, Any]:
        free_after = shutil.disk_usage(MZX_ROOT).free
        self.minimum_free = min(self.minimum_free, free_after)
        return {
            "free_bytes_before": self.free_before,
            "minimum_free_bytes_observed": self.minimum_free,
            "free_bytes_after_before_cleanup": free_after,
            "maximum_observed_physical_growth_bytes": max(0, self.free_before - self.minimum_free),
            "per_repository_disk_limit_bytes": PER_REPOSITORY_DISK_LIMIT_BYTES,
            "global_free_disk_floor_bytes": GLOBAL_FREE_DISK_FLOOR_BYTES,
            "termination_reason": self.termination_reason,
        }


TRACKER: DiskTracker | None = None


def monitored(cmd: list[str], cwd: Path, timeout: int, check: bool = False) -> subprocess.CompletedProcess[str]:
    if TRACKER is None:
        raise RuntimeError("disk tracker not configured")
    proc = subprocess.Popen(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True)
    started, reason = time.monotonic(), None
    while proc.poll() is None:
        try:
            TRACKER.poll()
        except ResourceBudgetExceeded as exc:
            reason = str(exc)
        if time.monotonic() - started > timeout:
            reason = f"command timeout after {timeout}s"
        if reason:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(30)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
            break
        time.sleep(2)
    stdout, stderr = proc.communicate()
    if reason:
        raise ResourceBudgetExceeded(reason)
    TRACKER.poll()
    result = subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
    if check and result.returncode != 0:
        raise RuntimeError(f"command failed {cmd}:\n{stderr[-12000:]}")
    return result


def monitored_isolated(cmd: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return monitored(cmd, cwd, timeout, False)


def hardlink_tree(source: Path, destination: Path) -> dict[str, Any]:
    if destination.is_symlink():
        raise ValueError(f"refusing symlink destination: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    linked, copied, symlinks = 0, 0, 0
    for base, directories, files in os.walk(source):
        rel = Path(base).relative_to(source)
        target_base = destination / rel
        target_base.mkdir(parents=True, exist_ok=True)
        for directory in directories:
            src = Path(base) / directory
            dst = target_base / directory
            if src.is_symlink():
                dst.unlink(missing_ok=True)
                dst.symlink_to(os.readlink(src)); symlinks += 1
        for filename in files:
            src, dst = Path(base) / filename, target_base / filename
            dst.unlink(missing_ok=True)
            if src.is_symlink():
                dst.symlink_to(os.readlink(src)); symlinks += 1
                continue
            try:
                os.link(src, dst); linked += 1
            except OSError:
                shutil.copy2(src, dst); copied += 1
        if TRACKER is not None:
            TRACKER.poll()
    return {"hardlinked_files": linked, "copied_files": copied, "symlinks": symlinks}


def trace_project(project: Path, timeout: int, threads: int,
                  preparation_slots: threading.Semaphore) -> dict[str, Any]:
    prefix_proc = monitored(["lake", "env", "lean", "--print-prefix"], project, 300, True)
    lean_prefix = Path(prefix_proc.stdout.strip()).resolve()
    if not (lean_prefix / "src").is_dir() or not (lean_prefix / "lib").is_dir():
        raise FileNotFoundError(f"invalid Lean prefix: {lean_prefix}")
    with preparation_slots:
        cleanup = backend.clear_repository_trace_artifacts(project)
        lean_package = project / ".lake/packages/lean4"
        materialization = hardlink_tree(lean_prefix, lean_package)
        local = project / "ExtractData.lean"
        stale = backend.remove_verified_stale_extractor(local)
        runtime = backend.write_extractor(local)
    try:
        proc = monitored_isolated(
            ["lake", "env", "lean", "--threads", str(threads), "--run", local.name, "noDeps"],
            project, timeout,
        )
    finally:
        local.unlink(missing_ok=True)
    asts = list(project.glob(".lake/build/ir/**/*.ast.json")) + list(project.glob("build/ir/**/*.ast.json"))
    return {
        "returncode": proc.returncode, "stdout_tail": proc.stdout[-8000:],
        "stderr_tail": proc.stderr[-12000:], "ast_files": len(asts),
        "trace_ok": proc.returncode == 0 and bool(asts), "trace_runtime": runtime,
        "fresh_trace_cleanup": cleanup, "stale_extractor_recovery": stale,
        "extractor_sha256": runtime["v427_extractor_sha256"],
        "lean_prefix": str(lean_prefix), "lean_prefix_materialized_to": str(lean_package),
        "lean_prefix_materialization": materialization,
    }


def candidate_for_backend(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": row["slug"], "url": row["url"], "ref": row["commit"],
        "commit": row["commit"], "domain": row.get("domain", "unclassified"),
        "subdir": ".", "snapshot_source": row["snapshot_source"],
        "snapshot_record_sha256": row["snapshot_record_sha256"],
    }


def checkout_path(candidate: dict[str, Any]) -> Path:
    return CHECKOUT_ROOT / safe_slug(candidate["slug"])


def cleanup_checkout(candidate: dict[str, Any]) -> dict[str, Any]:
    path = ensure_scoped_path(checkout_path(candidate), CHECKOUT_ROOT)
    if path.is_symlink():
        raise ValueError(f"refusing checkout symlink cleanup: {path}")
    before = allocated_bytes(path)
    if path.exists():
        shutil.rmtree(path)
    return {"path": str(path), "allocated_bytes_before": before, "removed": not path.exists()}


def deterministic_roots(frame: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(frame, key=lambda row: selection_key(REPLAY_ROOT_SEED, row["theorem_id"]))[:MAX_AUTHORED_REPLAY_ROOTS]


def replay(candidate: dict[str, Any], root: Path, timeout: int) -> dict[str, Any]:
    safe = safe_slug(candidate["slug"])
    frame = read_jsonl(root / "screening/frames" / f"{safe}.jsonl")
    chosen = deterministic_roots(frame)
    eligible, failure_counts = [], {}
    for index, target in enumerate(chosen, 1):
        inputp = root / "qualification/authored_inputs" / safe / f"{target['rid']}.json"
        outputp = root / "qualification/authored_rows" / safe / f"{target['rid']}.json"
        payload = backend.worker_input(root, target, "exp63-zero-candidate-screening", [], "exp63_authored_only")
        atomic_json_dump(payload, inputp)
        proc = monitored(
            [sys.executable, str(backend.WORKER), "--input", str(inputp), "--output", str(outputp),
             "--generated-dir", str(root / "generated"), "--timeout", str(timeout)],
            backend.PACKAGE_ROOT, timeout + 120,
        )
        if proc.returncode != 0 or not outputp.is_file():
            raise RuntimeError(f"authored worker failed without valid receipt: {proc.stderr[-8000:]}")
        row = read_json(outputp)
        ok = bool(row.get("worker_ok") is True and row.get("authored_replay_ok") is True
                  and len(row.get("candidates", [])) == 0)
        if ok:
            eligible.append(target)
        else:
            reason = str(row.get("error_type") or "authored_replay_gate")
            failure_counts[reason] = failure_counts.get(reason, 0) + 1
        print(f"EXP63-REPLAY {candidate['slug']} {index}/{len(chosen)} ok={int(ok)}", flush=True)
    eligiblep = root / "qualification/eligible_frames" / f"{safe}.jsonl"
    atomic_jsonl_dump(eligible, eligiblep)
    return {
        "roots_available": len(frame), "roots_replayed": len(chosen),
        "eligible_roots": len(eligible), "failure_counts": dict(sorted(failure_counts.items())),
        "eligible_frame_sha256": file_sha256(eligiblep),
        "authored_replay_gate": len(eligible) >= MIN_TRACE_ROOTS,
    }


def run(root: Path, candidate: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    global TRACKER
    protocol = read_json(root / "frozen/protocol.json")
    frame_receipt = read_json(root / "frozen/candidate_frame_receipt.json")
    assert_sealed(protocol, "Exp63 protocol"); assert_sealed(frame_receipt, "Exp63 frame")
    validate_locks(protocol)
    if candidate not in read_jsonl(root / "frozen/candidate_frame.jsonl"):
        raise ValueError("worker candidate is not in frozen frame")
    safe = safe_slug(candidate["slug"])
    outp = root / "qualification/repositories" / f"{safe}.json"
    if outp.is_file():
        return read_json(outp)
    backend.SERVER_ROOT = MZX_ROOT
    backend.SCREEN_CHECKOUT_ROOT = CHECKOUT_ROOT
    backend.ARTIFACT_ROOT = root
    backend.ROOTS_PER_REPOSITORY = MIN_TRACE_ROOTS
    backend.run_cmd = monitored
    backend.run_cmd_isolated = monitored_isolated
    backend.trace_project = trace_project
    CHECKOUT_ROOT.mkdir(parents=True, exist_ok=True)
    cleanup_checkout(candidate)
    # A worker interruption after build/trace but before its sealed qualification
    # receipt must restart from the exact commit; stale absolute checkout paths are
    # never reused after the scoped cleanup above.
    for stale in (
        root / "screening/build_trace" / f"{safe}.json",
        root / "screening/frames" / f"{safe}.jsonl",
        root / "screening/source_inventories" / f"{safe}.jsonl",
        root / "screening/enumeration_inputs" / f"{safe}.json",
        root / "screening/enumeration_receipts" / f"{safe}.json",
    ):
        stale.unlink(missing_ok=True)
    TRACKER = DiskTracker(checkout_path(candidate))
    value: dict[str, Any] = {
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "candidate": candidate, "qualification_gate": False,
        "classification": "operationally_unresolved", "first_failed_gate": "build_trace",
        "scientific_candidate_tactics_executed": 0,
    }
    try:
        old_args = SimpleNamespace(
            git_timeout=args.git_timeout, build_timeout=args.build_timeout,
            trace_timeout=args.trace_timeout, enumeration_timeout=args.enumeration_timeout,
            threads=args.threads,
        )
        build = backend.build_trace_one(
            candidate_for_backend(candidate), old_args, root,
            threading.Semaphore(1), threading.Semaphore(1), threading.Semaphore(1),
        )
        value["build_trace_receipt_sha256"] = file_sha256(root / "screening/build_trace" / f"{safe}.json")
        value["build_trace_gate"] = build.get("build_trace_gate") is True
        if build.get("build_trace_gate") is not True:
            status, reason = classify_build_trace_receipt(build)
            value.update({"classification": status, "first_failed_gate": reason,
                          "backend_first_failed_gate": build.get("first_failed_gate")})
        else:
            replay_result = replay(candidate, root, args.replay_timeout)
            value["authored_replay"] = replay_result
            if replay_result["authored_replay_gate"]:
                value.update({"qualification_gate": True, "classification": "qualified",
                              "first_failed_gate": None})
            else:
                value.update({"classification": "definitive_ineligible",
                              "first_failed_gate": "minimum_authored_replay_roots"})
    except ResourceBudgetExceeded as exc:
        value["error"] = {"type": type(exc).__name__, "message": str(exc)}
        value["first_failed_gate"] = TRACKER.termination_reason or "resource_budget"
    except Exception as exc:
        value["error"] = {"type": type(exc).__name__, "message": str(exc)[-12000:]}
        value["first_failed_gate"] = "operational_worker_exception"
    finally:
        value["disk"] = TRACKER.record()
        value["checkout_cleanup"] = cleanup_checkout(candidate)
        value["disk"]["free_bytes_after_cleanup"] = shutil.disk_usage(MZX_ROOT).free
        TRACKER = None
    value = seal(value)
    atomic_json_dump(value, outp)
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--candidate", required=True, help="Frozen-candidate JSON file")
    parser.add_argument("--git-timeout", type=int, default=1800)
    parser.add_argument("--build-timeout", type=int, default=14400)
    parser.add_argument("--trace-timeout", type=int, default=14400)
    parser.add_argument("--enumeration-timeout", type=int, default=7200)
    parser.add_argument("--replay-timeout", type=int, default=1200)
    parser.add_argument("--threads", type=int, default=2)
    return parser.parse_args()


if __name__ == "__main__":
    parsed = parse_args()
    candidate = read_json(parsed.candidate)
    print(json.dumps(run(Path(parsed.artifact_root).resolve(), candidate, parsed), indent=2))
