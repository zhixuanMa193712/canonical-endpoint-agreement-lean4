"""Execute the frozen Exp64 frame serially with bounded, scoped disk use."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from experiment64_protocol import *

EXP63_PACKAGE = MZX_ROOT / "experiment63_strict_v427_recruitment"
EXP51_PACKAGE = MZX_ROOT / "experiment51_external_repository_replication"
sys.path.insert(0, str(EXP63_PACKAGE))
sys.path.insert(0, str(EXP51_PACKAGE))
import experiment63_qualification_worker as exp63worker  # type: ignore
import experiment51_protocol as exp51  # type: ignore

backend = exp63worker.backend
LIVE_WORKER = EXP51_PACKAGE / "experiment51_live_worker.py"


def configure_backend(root: Path) -> None:
    exp63worker.MZX_ROOT = MZX_ROOT
    exp63worker.CHECKOUT_ROOT = CHECKOUT_ROOT
    exp63worker.GLOBAL_FREE_DISK_FLOOR_BYTES = GLOBAL_FREE_DISK_FLOOR_BYTES
    exp63worker.PER_REPOSITORY_DISK_LIMIT_BYTES = PER_REPOSITORY_DISK_LIMIT_BYTES
    backend.SERVER_ROOT = MZX_ROOT
    backend.SCREEN_CHECKOUT_ROOT = CHECKOUT_ROOT
    backend.ARTIFACT_ROOT = root
    backend.ROOTS_PER_REPOSITORY = ROOTS_PER_REPOSITORY
    backend.run_cmd = exp63worker.monitored
    backend.run_cmd_isolated = exp63worker.monitored_isolated
    backend.trace_project = exp63worker.trace_project


def checkout_path(repository: dict[str, Any]) -> Path:
    return CHECKOUT_ROOT / safe_slug(repository["slug"])


def cleanup_checkout(repository: dict[str, Any]) -> dict[str, Any]:
    path = ensure_scoped_path(checkout_path(repository), CHECKOUT_ROOT)
    before = exp63worker.allocated_bytes(path)
    if path.is_symlink():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)
    return {"path": str(path), "allocated_bytes_before": before, "removed": not path.exists()}


def exact_cache_paths(repository: dict[str, Any]) -> list[Path]:
    owner, name = repository["slug"].split("/", 1)
    commit = repository["commit"]
    names = {
        f"gitpython-{owner}__{name}-{commit}",
        f"gitpython-{name}-{commit}",
    }
    legacy = f"{owner}-{name}-{commit}"
    paths = [LEAN_DOJO_CACHE_ROOT / "repos" / value for value in sorted(names)]
    paths.append(LEAN_DOJO_CACHE_ROOT / legacy)
    return paths


def cache_ownership(root: Path, repository: dict[str, Any]) -> dict[str, Any]:
    path = root / "execution/cache_ownership" / f"{safe_slug(repository['slug'])}.json"
    if path.is_file():
        value = read_json(path)
        assert_sealed(value, f"cache ownership {repository['slug']}")
        return value
    candidates = exact_cache_paths(repository)
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "slug": repository["slug"],
        "commit": repository["commit"],
        "exact_candidate_paths": [str(item) for item in candidates],
        "preexisting_paths": [str(item) for item in candidates if item.exists()],
    })
    atomic_json_dump(value, path)
    return value


def cleanup_new_exact_caches(ownership: dict[str, Any]) -> dict[str, Any]:
    preexisting = set(ownership["preexisting_paths"])
    removed: list[dict[str, Any]] = []
    retained: list[str] = []
    allowed_roots = [(LEAN_DOJO_CACHE_ROOT / "repos").resolve(), LEAN_DOJO_CACHE_ROOT.resolve()]
    for raw in ownership["exact_candidate_paths"]:
        path = Path(raw).resolve(strict=False)
        if raw in preexisting:
            retained.append(raw)
            continue
        if not any(path != root and path.is_relative_to(root) for root in allowed_roots):
            raise ValueError(f"cache path escaped exact LeanDojo roots: {path}")
        before = exp63worker.allocated_bytes(path)
        if path.is_symlink():
            path.unlink()
        elif path.exists():
            shutil.rmtree(path)
        removed.append({"path": str(path), "allocated_bytes_before": before, "removed": not path.exists()})
    return {
        "policy": "remove only exact commit caches absent before this Exp64 repository began",
        "removed": removed,
        "preexisting_retained": retained,
    }


def load_frozen(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], str]:
    protocolp = root / "frozen/protocol.json"
    repositoriesp = root / "frozen/repositories.json"
    targetsp = root / "frozen/targets.json"
    protocol = read_json(protocolp)
    assert_sealed(protocol, "Exp64 protocol")
    validate_locks(protocol)
    repositories = json.loads(repositoriesp.read_text(encoding="utf-8"))
    targets = json.loads(targetsp.read_text(encoding="utf-8"))
    if file_sha256(repositoriesp) != protocol["repositories_sha256"]:
        raise ValueError("frozen repository frame changed")
    if file_sha256(targetsp) != protocol["targets_sha256"]:
        raise ValueError("frozen theorem frame changed")
    if len(repositories) != REPOSITORY_COUNT or len(targets) != REPOSITORY_COUNT * ROOTS_PER_REPOSITORY:
        raise ValueError("frozen dimensions changed")
    return protocol, repositories, targets, file_sha256(protocolp)


def clear_stale_build_outputs(root: Path, repository: dict[str, Any]) -> None:
    safe = safe_slug(repository["slug"])
    for stale in (
        root / "screening/build_trace" / f"{safe}.json",
        root / "screening/frames" / f"{safe}.jsonl",
        root / "screening/source_inventories" / f"{safe}.jsonl",
        root / "screening/enumeration_inputs" / f"{safe}.json",
        root / "screening/enumeration_receipts" / f"{safe}.json",
    ):
        stale.unlink(missing_ok=True)


def build_and_trace(root: Path, repository: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    clear_stale_build_outputs(root, repository)
    backend_candidate = exp63worker.candidate_for_backend(repository)
    old_args = SimpleNamespace(
        git_timeout=args.git_timeout,
        build_timeout=args.build_timeout,
        trace_timeout=args.trace_timeout,
        enumeration_timeout=args.enumeration_timeout,
        threads=args.threads,
    )
    return backend.build_trace_one(
        backend_candidate,
        old_args,
        root,
        threading.Semaphore(1),
        threading.Semaphore(1),
        threading.Semaphore(1),
    )


def live_targets(root: Path, repository: dict[str, Any], frozen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    framep = root / "screening/frames" / f"{safe_slug(repository['slug'])}.jsonl"
    frame = read_jsonl(framep)
    by_id = {row["theorem_id"]: row for row in frame}
    output = []
    for target in frozen:
        live = by_id.get(target["theorem_id"])
        if live is None:
            raise ValueError(f"frozen theorem absent after exact-commit rebuild: {target['theorem_id']}")
        if target_identity(live) != target_identity(target):
            raise ValueError(f"frozen theorem identity changed after rebuild: {target['theorem_id']}")
        runtime = dict(live)
        runtime["alternatives"] = list(target["alternatives"])
        runtime["robust_alternatives"] = list(target["robust_alternatives"])
        output.append(runtime)
    return output


def validate_worker(row: dict[str, Any], frozen: dict[str, Any], config_sha: str) -> None:
    expected_hash = json_sha256({key: value for key, value in row.items() if key != "record_sha256"})
    if row.get("record_sha256") != expected_hash:
        raise ValueError(f"worker record hash changed: {frozen['theorem_id']}")
    if not (
        row.get("protocol_version") == MEASUREMENT_ENGINE_PROTOCOL
        and row.get("mode") == "exp64_scientific"
        and row.get("config_sha256") == config_sha
        and row.get("slug") == frozen["slug"]
        and row.get("commit") == frozen["commit"]
        and row.get("theorem_id") == frozen["theorem_id"]
        and row.get("source_file_sha256") == frozen["source_file_sha256"]
        and row.get("candidate_order") == frozen["alternatives"]
    ):
        raise ValueError(f"worker identity mismatch: {frozen['theorem_id']}")


def synthetic_worker_failure(
    frozen: dict[str, Any], config_sha: str, error_type: str, message: str
) -> dict[str, Any]:
    row = {
        "schema": "experiment64-operational-worker-failure-v1",
        "version": VERSION,
        "protocol_version": MEASUREMENT_ENGINE_PROTOCOL,
        "exp64_protocol_version": PROTOCOL_VERSION,
        "mode": "exp64_scientific",
        "config_sha256": config_sha,
        "slug": frozen["slug"],
        "commit": frozen["commit"],
        "file_path": frozen["file_path"],
        "full_name": frozen["full_name"],
        "theorem_id": frozen["theorem_id"],
        "source_file_sha256": frozen["source_file_sha256"],
        "candidate_order": list(frozen["alternatives"]),
        "candidates": [],
        "worker_ok": False,
        "error_type": error_type,
        "error_message": message[-12000:],
    }
    return seal(row)


def invoke_target(
    root: Path,
    frozen: dict[str, Any],
    runtime: dict[str, Any],
    config_sha: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    safe = safe_slug(frozen["slug"])
    outp = root / "scientific/theorems" / safe / f"{frozen['rid']}.json"
    inputp = root / "scientific/inputs" / safe / f"{frozen['rid']}.json"
    if outp.is_file():
        row = read_json(outp)
        validate_worker(row, frozen, config_sha)
        return row
    payload = backend.worker_input(
        root, runtime, config_sha, list(frozen["alternatives"]), "exp64_scientific"
    )
    payload["environment_receipt_sha256"] = config_sha
    atomic_json_dump(payload, inputp)
    try:
        proc = exp63worker.monitored(
            [
                sys.executable,
                str(LIVE_WORKER),
                "--input", str(inputp),
                "--output", str(outp),
                "--generated-dir", str(root / "generated"),
                "--timeout", str(args.lean_timeout),
            ],
            EXP51_PACKAGE,
            args.lean_timeout + 120,
            False,
        )
        if outp.is_file():
            row = read_json(outp)
        else:
            row = synthetic_worker_failure(
                frozen, config_sha, "worker_failed_without_receipt",
                f"returncode={proc.returncode}\n{proc.stderr[-10000:]}",
            )
            atomic_json_dump(row, outp)
    except Exception as exc:
        row = synthetic_worker_failure(frozen, config_sha, type(exc).__name__, str(exc))
        atomic_json_dump(row, outp)
    validate_worker(row, frozen, config_sha)
    return row


def repository_receipt_path(root: Path, slug: str) -> Path:
    return root / "execution/repositories" / f"{safe_slug(slug)}.json"


def archive_for_fixed_operational_retry(
    root: Path, repository: dict[str, Any], receipt: dict[str, Any]
) -> bool:
    if receipt.get("status") == "scientific_execution_complete":
        return False
    attempt_root = root / "execution/repository_attempts" / safe_slug(repository["slug"])
    prior = sorted(attempt_root.glob("attempt_*.json")) if attempt_root.exists() else []
    if len(prior) >= MAX_OPERATIONAL_REPOSITORY_ATTEMPTS - 1:
        return False
    attemptp = attempt_root / f"attempt_{len(prior) + 1}.json"
    atomic_json_dump(receipt, attemptp)
    repository_receipt_path(root, repository["slug"]).unlink()
    return True


def run_repository(
    root: Path,
    repository: dict[str, Any],
    frozen_targets: list[dict[str, Any]],
    config_sha: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    outp = repository_receipt_path(root, repository["slug"])
    if outp.is_file():
        value = read_json(outp)
        assert_sealed(value, f"Exp64 repository {repository['slug']}")
        return value
    ownership = cache_ownership(root, repository)
    cleanup_checkout(repository)
    exp63worker.TRACKER = exp63worker.DiskTracker(checkout_path(repository))
    value: dict[str, Any] = {
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "slug": repository["slug"],
        "commit": repository["commit"],
        "frozen_roots": len(frozen_targets),
        "status": "operational_build_failure",
        "build_trace_gate": False,
        "roots_with_worker_receipts": 0,
        "evaluable_roots": 0,
        "candidate_invocations_requested": 0,
        "candidate_invocations_recorded": 0,
    }
    try:
        build = build_and_trace(root, repository, args)
        buildp = root / "screening/build_trace" / f"{safe_slug(repository['slug'])}.json"
        value["build_trace_receipt_sha256"] = file_sha256(buildp)
        value["build_trace_gate"] = build.get("build_trace_gate") is True
        if build.get("build_trace_gate") is not True:
            value["first_failed_gate"] = build.get("first_failed_gate")
            value["backend_error"] = build.get("error")
        else:
            runtime_targets = live_targets(root, repository, frozen_targets)
            rows = []
            for index, (frozen, runtime) in enumerate(zip(frozen_targets, runtime_targets), 1):
                row = invoke_target(root, frozen, runtime, config_sha, args)
                rows.append(row)
                print(
                    f"EXP64-ROOT {repository['slug']} {index}/{len(frozen_targets)} "
                    f"evaluable={int(row.get('worker_ok') is True)} "
                    f"recorded={len(row.get('candidates', []))}",
                    flush=True,
                )
            value.update({
                "status": "scientific_execution_complete",
                "roots_with_worker_receipts": len(rows),
                "evaluable_roots": sum(row.get("worker_ok") is True for row in rows),
                "candidate_invocations_requested": len(rows) * CANDIDATES_PER_ROOT,
                "candidate_invocations_recorded": sum(len(row.get("candidates", [])) for row in rows),
                "worker_failure_counts": dict(sorted({
                    reason: sum(
                        row.get("worker_ok") is not True and str(row.get("error_type", "worker_gate")) == reason
                        for row in rows
                    )
                    for reason in {
                        str(row.get("error_type", "worker_gate"))
                        for row in rows if row.get("worker_ok") is not True
                    }
                }.items())),
            })
    except Exception as exc:
        value["status"] = "operational_repository_exception"
        value["error"] = {"type": type(exc).__name__, "message": str(exc)[-12000:]}
    finally:
        tracker = exp63worker.TRACKER
        if tracker is not None:
            value["disk"] = tracker.record()
        value["checkout_cleanup"] = cleanup_checkout(repository)
        value["cache_cleanup"] = cleanup_new_exact_caches(ownership)
        if "disk" in value:
            value["disk"]["free_bytes_after_cleanup"] = shutil.disk_usage(MZX_ROOT).free
        exp63worker.TRACKER = None
    value = seal(value)
    atomic_json_dump(value, outp)
    return value


def progress(root: Path, repositories: list[dict[str, Any]], stopping_reason: str | None = None) -> dict[str, Any]:
    receipts = []
    for repository in repositories:
        path = repository_receipt_path(root, repository["slug"])
        if path.is_file():
            receipt = read_json(path)
            assert_sealed(receipt, f"Exp64 repository {repository['slug']}")
            receipts.append(receipt)
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "frozen_repositories": len(repositories),
        "completed_repositories": len(receipts),
        "scientific_execution_complete_repositories": sum(
            row.get("status") == "scientific_execution_complete" for row in receipts
        ),
        "operational_repository_failures": sum(
            row.get("status") != "scientific_execution_complete" for row in receipts
        ),
        "frozen_roots": len(repositories) * ROOTS_PER_REPOSITORY,
        "roots_with_worker_receipts": sum(int(row.get("roots_with_worker_receipts", 0)) for row in receipts),
        "evaluable_roots": sum(int(row.get("evaluable_roots", 0)) for row in receipts),
        "candidate_invocations_requested": sum(
            int(row.get("candidate_invocations_requested", 0)) for row in receipts
        ),
        "candidate_invocations_recorded": sum(
            int(row.get("candidate_invocations_recorded", 0)) for row in receipts
        ),
        "remaining_repositories": len(repositories) - len(receipts),
        "disk_free_bytes": shutil.disk_usage(MZX_ROOT).free,
        "disk_floor_bytes": GLOBAL_FREE_DISK_FLOOR_BYTES,
        "stopping_reason": stopping_reason,
    })
    atomic_json_dump(value, root / "execution/progress.json")
    return value


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.artifact_root).resolve()
    _, repositories, targets, config_sha = load_frozen(root)
    configure_backend(root)
    CHECKOUT_ROOT.mkdir(parents=True, exist_ok=True)
    for repository in repositories:
        if shutil.disk_usage(MZX_ROOT).free < GLOBAL_FREE_DISK_FLOOR_BYTES:
            value = progress(root, repositories, "global_disk_floor_reached_before_next_repository")
            print(json.dumps(value, ensure_ascii=False, indent=2))
            raise RuntimeError("Exp64 stopped safely at the 150-GiB global disk floor; clean exact caches and resume")
        if repository_receipt_path(root, repository["slug"]).is_file():
            continue
        selected = [row for row in targets if row["slug"] == repository["slug"]]
        print(
            f"EXP64-REPOSITORY {repository['repository_index']}/{len(repositories)} "
            f"{repository['slug']} roots={len(selected)}",
            flush=True,
        )
        while True:
            receipt = run_repository(root, repository, selected, config_sha, args)
            if not archive_for_fixed_operational_retry(root, repository, receipt):
                break
            print(
                f"EXP64-RETRY {repository['slug']} fixed_operational_attempt="
                f"{len(list((root / 'execution/repository_attempts' / safe_slug(repository['slug'])).glob('attempt_*.json'))) + 1}"
                f"/{MAX_OPERATIONAL_REPOSITORY_ATTEMPTS}",
                flush=True,
            )
        current = progress(root, repositories)
        print(
            f"EXP64-PROGRESS repositories={current['completed_repositories']}/{len(repositories)} "
            f"evaluable_roots={current['evaluable_roots']}/{current['frozen_roots']} "
            f"status={receipt['status']} free_gib={current['disk_free_bytes']/1024**3:.1f}",
            flush=True,
        )
    value = progress(root, repositories, "frozen_repository_frame_exhausted")
    atomic_json_dump(value, root / "scientific/summary.json")
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--git-timeout", type=int, default=1800)
    parser.add_argument("--build-timeout", type=int, default=14400)
    parser.add_argument("--trace-timeout", type=int, default=14400)
    parser.add_argument("--enumeration-timeout", type=int, default=7200)
    parser.add_argument("--lean-timeout", type=int, default=1200)
    parser.add_argument("--threads", type=int, default=2)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
