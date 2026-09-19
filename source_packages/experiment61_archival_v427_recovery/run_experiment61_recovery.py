"""Run disk-aware zero-candidate build/trace recovery for Exp61."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import shutil
import sys
import threading
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from experiment61_protocol import *


sys.path.insert(0, str(WORKSPACE_ROOT_61 / "experiment51_external_repository_replication"))
import screen_experiment51_repositories as backend  # type: ignore


def configure_backend(root: Path) -> None:
    backend.SERVER_ROOT = WORKSPACE_ROOT_61
    backend.SCREEN_CHECKOUT_ROOT = CHECKOUT_ROOT_61
    backend.ARTIFACT_ROOT = root
    backend.ROOTS_PER_REPOSITORY = MIN_ELIGIBLE_ROOTS


def load_inputs(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    protocol = read_json(root / "frozen/protocol.json")
    assert_sealed(protocol, "Exp61 protocol")
    if protocol.get("protocol_version") != PROTOCOL_VERSION_61:
        raise ValueError("wrong Exp61 protocol")
    validate_implementation_locks_61(protocol)
    candidates = read_jsonl(root / "frozen/candidate_frame.jsonl")
    recovery = read_jsonl(root / "frozen/recovery_frame.jsonl")
    if len(candidates) != 1089 or len(recovery) != 70:
        raise ValueError("Exp61 frozen frame changed")
    return protocol, candidates, recovery


def build_state(root: Path, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    active = [row for row in candidates if not row.get("prequalification_exclusion")]
    passed, failed, unresolved = [], [], []
    failure_counts: Counter[str] = Counter()
    for candidate in active:
        path = root / "screening/build_trace" / f"{safe_slug_61(candidate['slug'])}.json"
        if not path.is_file():
            unresolved.append(candidate["slug"])
            continue
        receipt = read_json(path)
        if receipt.get("candidate") != backend_candidate_61(candidate):
            raise ValueError(f"candidate identity changed: {candidate['slug']}")
        if receipt.get("scientific_candidate_tactics_executed") != 0:
            raise ValueError(f"nonzero scientific tactic count: {candidate['slug']}")
        if receipt.get("build_trace_gate") is True:
            if receipt.get("first_failed_gate") is not None:
                raise ValueError(f"passing receipt has a failure gate: {candidate['slug']}")
            passed.append(candidate["slug"])
            continue
        gate = receipt.get("first_failed_gate")
        if gate == "checkout":
            raise ValueError(f"operational checkout receipt was not quarantined: {candidate['slug']}")
        if not isinstance(gate, str) or not gate:
            raise ValueError(f"failed receipt lacks a definitive gate: {candidate['slug']}")
        failed.append(candidate["slug"])
        failure_counts[gate] += 1
    upper_bound = len(passed) + len(unresolved)
    return {
        "active": len(active), "passed": passed, "failed": failed,
        "unresolved": unresolved, "failure_counts": dict(sorted(failure_counts.items())),
        "conservative_upper_bound": upper_bound,
        "repository_target": REPOSITORIES_REQUIRED,
        "futility_reached": upper_bound < REPOSITORIES_REQUIRED,
    }


def checkout_path(candidate: dict[str, Any]) -> Path:
    return CHECKOUT_ROOT_61 / safe_slug_61(candidate["slug"])


def clean_checkout(candidate: dict[str, Any]) -> dict[str, Any]:
    root = CHECKOUT_ROOT_61.resolve()
    path = checkout_path(candidate)
    if path.is_symlink():
        raise ValueError(f"refusing checkout symlink cleanup: {path}")
    resolved = path.resolve(strict=False)
    if not resolved.is_relative_to(root) or resolved == root:
        raise ValueError(f"checkout cleanup escaped recovery root: {resolved}")
    existed = path.exists()
    if existed:
        shutil.rmtree(path)
    return {"path": str(path), "existed": existed, "removed": not path.exists()}


def next_attempt_path(root: Path, candidate: dict[str, Any]) -> Path:
    directory = root / "recovery/operational_attempts" / safe_slug_61(candidate["slug"])
    existing = sorted(directory.glob("attempt-*.json")) if directory.is_dir() else []
    return directory / f"attempt-{len(existing) + 1:03d}.json"


def record_operational_attempt(root: Path, candidate: dict[str, Any],
                               receipt: dict[str, Any] | None,
                               error: BaseException | None = None) -> Path:
    source_path = root / "screening/build_trace" / f"{safe_slug_61(candidate['slug'])}.json"
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION_61,
        "candidate": candidate,
        "classification": "operationally_unresolved_not_a_qualification_failure",
        "backend_receipt": receipt,
        "backend_receipt_sha256": file_sha256(source_path) if source_path.is_file() else None,
        "runner_exception": None if error is None else {
            "type": type(error).__name__, "message": str(error)[-12000:],
        },
        "checkout_cleanup": clean_checkout(candidate),
        "scientific_candidate_tactics_executed": 0,
    })
    destination = next_attempt_path(root, candidate)
    atomic_json_dump(value, destination)
    source_path.unlink(missing_ok=True)
    source_path.with_name(source_path.name + ".tmp").unlink(missing_ok=True)
    return destination


def operational_attempt_exists(root: Path, candidate: dict[str, Any]) -> bool:
    directory = root / "recovery/operational_attempts" / safe_slug_61(candidate["slug"])
    return directory.is_dir() and any(directory.glob("attempt-*.json"))


def write_progress(root: Path, candidates: list[dict[str, Any]],
                   stopping_reason: str | None = None) -> dict[str, Any]:
    state = build_state(root, candidates)
    operational_attempts = list((root / "recovery/operational_attempts").rglob("attempt-*.json"))
    free = shutil.disk_usage(WORKSPACE_ROOT_61).free
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION_61,
        "active_candidates": state["active"],
        "definitive_build_trace_passes": len(state["passed"]),
        "definitive_build_trace_failures": len(state["failed"]),
        "operationally_unresolved_candidates": len(state["unresolved"]),
        "operational_attempt_receipts": len(operational_attempts),
        "failure_counts": state["failure_counts"],
        "conservative_upper_bound": state["conservative_upper_bound"],
        "repository_target": state["repository_target"],
        "futility_reached": state["futility_reached"],
        "disk_free_bytes": free, "disk_floor_bytes": FREE_DISK_FLOOR_BYTES,
        "disk_floor_satisfied": free >= FREE_DISK_FLOOR_BYTES,
        "stopping_reason": stopping_reason,
        "scientific_candidate_tactics_executed": 0,
    })
    atomic_json_dump(value, root / "recovery/progress.json")
    return value


def run(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    _, candidates, recovery = load_inputs(root)
    configure_backend(root)
    if args.status_only:
        return write_progress(root, candidates, "status_only")
    if shutil.disk_usage(WORKSPACE_ROOT_61).free < FREE_DISK_FLOOR_BYTES:
        return write_progress(root, candidates, "disk_floor_not_satisfied_before_start")

    old_args = SimpleNamespace(
        git_timeout=args.git_timeout, build_timeout=args.build_timeout,
        trace_timeout=args.trace_timeout, enumeration_timeout=args.enumeration_timeout,
        threads=args.threads,
    )
    build_slots = threading.Semaphore(args.build_slots)
    trace_slots = threading.Semaphore(args.trace_slots)
    enumeration_slots = threading.Semaphore(args.enumeration_slots)
    pending = []
    for candidate in recovery:
        out = root / "screening/build_trace" / f"{safe_slug_61(candidate['slug'])}.json"
        if out.is_file():
            continue
        if operational_attempt_exists(root, candidate) and not args.retry_operational:
            continue
        pending.append(candidate)
    batches_run = 0
    for start in range(0, len(pending), args.batch_size):
        state = build_state(root, candidates)
        if state["futility_reached"]:
            return write_progress(root, candidates, "deterministic_recruitment_futility")
        if shutil.disk_usage(WORKSPACE_ROOT_61).free < FREE_DISK_FLOOR_BYTES:
            return write_progress(root, candidates, "disk_floor_reached")
        if args.max_batches and batches_run >= args.max_batches:
            return write_progress(root, candidates, "max_batches_reached")
        batch = pending[start:start + args.batch_size]
        print(f"EXP61-BATCH {batches_run + 1} size={len(batch)}", flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.repository_workers) as executor:
            futures = {
                executor.submit(
                    backend.build_trace_one, backend_candidate_61(candidate), old_args, root,
                    build_slots, trace_slots, enumeration_slots,
                ): candidate for candidate in batch
            }
            for future in concurrent.futures.as_completed(futures):
                candidate = futures[future]
                try:
                    receipt = future.result()
                except BaseException as exc:
                    path = record_operational_attempt(root, candidate, None, exc)
                    print(f"EXP61-OPERATIONAL {candidate['slug']} receipt={path}", flush=True)
                    continue
                gate = receipt.get("first_failed_gate")
                if receipt.get("build_trace_gate") is not True and gate == "checkout":
                    path = record_operational_attempt(root, candidate, receipt)
                    print(f"EXP61-OPERATIONAL {candidate['slug']} gate=checkout receipt={path}", flush=True)
                elif receipt.get("build_trace_gate") is True:
                    print(f"EXP61-PASS {candidate['slug']} checkout-retained=1", flush=True)
                else:
                    cleanup = clean_checkout(candidate)
                    print(f"EXP61-FAIL {candidate['slug']} gate={gate} cleanup={int(cleanup['removed'])}", flush=True)
        batches_run += 1
        progress = write_progress(root, candidates)
        print(
            f"EXP61-PROGRESS passes={progress['definitive_build_trace_passes']} "
            f"failures={progress['definitive_build_trace_failures']} "
            f"unresolved={progress['operationally_unresolved_candidates']} "
            f"upper={progress['conservative_upper_bound']}", flush=True,
        )
    final = build_state(root, candidates)
    reason = "deterministic_recruitment_futility" if final["futility_reached"] else "recovery_frame_exhausted"
    return write_progress(root, candidates, reason)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT_61))
    parser.add_argument("--status-only", action="store_true")
    parser.add_argument("--retry-operational", action="store_true")
    parser.add_argument("--batch-size", type=int, default=RECOVERY_BATCH_SIZE)
    parser.add_argument("--max-batches", type=int, default=0)
    parser.add_argument("--repository-workers", type=int, default=RECOVERY_REPOSITORY_WORKERS)
    parser.add_argument("--build-slots", type=int, default=RECOVERY_BUILD_SLOTS)
    parser.add_argument("--trace-slots", type=int, default=RECOVERY_TRACE_SLOTS)
    parser.add_argument("--enumeration-slots", type=int, default=RECOVERY_ENUMERATION_SLOTS)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--git-timeout", type=int, default=1800)
    parser.add_argument("--build-timeout", type=int, default=7200)
    parser.add_argument("--trace-timeout", type=int, default=14400)
    parser.add_argument("--enumeration-timeout", type=int, default=7200)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run(Path(args.artifact_root).resolve(), args), indent=2, sort_keys=True))
