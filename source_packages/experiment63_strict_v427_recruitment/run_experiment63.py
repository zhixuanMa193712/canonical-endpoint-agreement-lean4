"""Orchestrate strict discovery, frame freeze, and serial Exp63 qualification."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from experiment63_protocol import *
import freeze_experiment63
import snapshot_strict_v427_frame
import strict_static_prefilter
import freeze_experiment63_frame


def exp62_processes() -> list[str]:
    proc = subprocess.run(["pgrep", "-af", "experiment62_multistep_solvable_search"],
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return [line for line in proc.stdout.splitlines() if line.strip() and "pgrep -af" not in line]


def wait_for_exp62() -> None:
    while True:
        processes = exp62_processes()
        if not processes:
            print("EXP63-WAIT Exp62 process not found; heavy qualification may begin.", flush=True)
            return
        print(f"EXP63-WAIT Exp62 still active ({len(processes)} process matches); checking again in 300s.", flush=True)
        time.sleep(300)


def inventory_hashes(root: Path, slug: str) -> set[str]:
    path = root / "screening/source_inventories" / f"{safe_slug(slug)}.jsonl"
    if not path.is_file():
        return set()
    return {str(row["normalized_whitespace_free_sha256"]) for row in read_jsonl(path)}


def overlap(left: set[str], right: set[str]) -> float:
    return len(left & right) / min(len(left), len(right)) if left and right else 0.0


def state(root: Path, frame: list[dict[str, Any]], stopping_reason: str | None = None) -> dict[str, Any]:
    receipts: dict[str, dict[str, Any]] = {}
    for candidate in frame:
        path = root / "qualification/repositories" / f"{safe_slug(candidate['slug'])}.json"
        if path.is_file():
            receipt = read_json(path); assert_sealed(receipt, candidate["slug"])
            receipts[candidate["slug"]] = receipt
    representatives: list[str] = []
    representative_hashes: dict[str, set[str]] = {}
    lineage_rows = []
    for candidate in frame:
        receipt = receipts.get(candidate["slug"])
        if not receipt or receipt.get("qualification_gate") is not True:
            continue
        hashes = inventory_hashes(root, candidate["slug"])
        if not hashes:
            raise ValueError(f"qualified repository lacks a nonempty source inventory: {candidate['slug']}")
        maximum, matching = 0.0, None
        for prior in representatives:
            score = overlap(hashes, representative_hashes[prior])
            if score > maximum:
                maximum, matching = score, prior
        representative = maximum < SOURCE_OVERLAP_THRESHOLD
        if representative:
            representatives.append(candidate["slug"])
            representative_hashes[candidate["slug"]] = hashes
        lineage_rows.append({
            "slug": candidate["slug"], "commit": candidate["commit"],
            "lineage_representative": representative,
            "maximum_prior_source_overlap": maximum,
            "matching_prior_representative": matching,
        })
    atomic_jsonl_dump(lineage_rows, root / "qualification/lineage_ledger.jsonl")
    completed = len(receipts)
    operational = sum(row.get("classification") == "operationally_unresolved" for row in receipts.values())
    definitive = sum(row.get("classification") == "definitive_ineligible" for row in receipts.values())
    qualified = sum(row.get("qualification_gate") is True for row in receipts.values())
    remaining = len(frame) - completed
    upper = len(representatives) + operational + remaining
    target_reached = len(representatives) >= TARGET_REPOSITORIES
    futility = upper < TARGET_REPOSITORIES
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "frozen_candidates": len(frame), "completed_repositories": completed,
        "qualified_repositories": qualified, "lineage_representatives": len(representatives),
        "definitive_ineligible": definitive, "operationally_unresolved": operational,
        "remaining_candidates": remaining, "conservative_upper_bound": upper,
        "repository_target": TARGET_REPOSITORIES, "target_reached": target_reached,
        "futility_reached": futility, "representative_slugs": representatives,
        "lineage_ledger_sha256": file_sha256(root / "qualification/lineage_ledger.jsonl"),
        "disk_free_bytes": shutil.disk_usage(MZX_ROOT).free,
        "disk_floor_bytes": GLOBAL_FREE_DISK_FLOOR_BYTES,
        "stopping_reason": stopping_reason,
        "scientific_candidate_tactics_executed": 0,
    })
    atomic_json_dump(value, root / "qualification/progress.json")
    return value


def qualify(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    receipt = read_json(root / "frozen/candidate_frame_receipt.json")
    assert_sealed(receipt, "Exp63 frame")
    if receipt.get("prequalification_upper_bound_reaches_target") is not True:
        raise RuntimeError("strict prequalification produced fewer than 38 candidates; no qualification executed")
    frame = read_jsonl(root / "frozen/candidate_frame.jsonl")
    if args.wait_for_exp62:
        wait_for_exp62()
    for candidate in frame:
        progress = state(root, frame)
        if progress["target_reached"]:
            return state(root, frame, "strict_target_reached")
        if progress["futility_reached"]:
            return state(root, frame, "deterministic_strict_recruitment_futility")
        if shutil.disk_usage(MZX_ROOT).free < GLOBAL_FREE_DISK_FLOOR_BYTES:
            return state(root, frame, "global_disk_floor_reached")
        outputp = root / "qualification/repositories" / f"{safe_slug(candidate['slug'])}.json"
        if outputp.is_file():
            continue
        inputp = root / "qualification/worker_inputs" / f"{safe_slug(candidate['slug'])}.json"
        atomic_json_dump(candidate, inputp)
        command = [
            sys.executable, str(PACKAGE_ROOT / "experiment63_qualification_worker.py"),
            "--artifact-root", str(root), "--candidate", str(inputp),
            "--git-timeout", str(args.git_timeout), "--build-timeout", str(args.build_timeout),
            "--trace-timeout", str(args.trace_timeout),
            "--enumeration-timeout", str(args.enumeration_timeout),
            "--replay-timeout", str(args.replay_timeout), "--threads", str(args.threads),
        ]
        proc = subprocess.run(command, cwd=PACKAGE_ROOT, text=True)
        if proc.returncode != 0 or not outputp.is_file():
            attempt = seal({
                "version": VERSION, "protocol_version": PROTOCOL_VERSION,
                "candidate": candidate, "classification": "operationally_unresolved",
                "worker_returncode": proc.returncode, "scientific_candidate_tactics_executed": 0,
            })
            atomic_json_dump(attempt, root / "qualification/worker_failures" / f"{safe_slug(candidate['slug'])}.json")
            raise RuntimeError(f"Exp63 worker exited without receipt for {candidate['slug']}")
        progress = state(root, frame)
        print(
            f"EXP63-PROGRESS done={progress['completed_repositories']}/{len(frame)} "
            f"qualified={progress['qualified_repositories']} reps={progress['lineage_representatives']} "
            f"operational={progress['operationally_unresolved']} upper={progress['conservative_upper_bound']} "
            f"free_gib={progress['disk_free_bytes']/1024**3:.1f}", flush=True,
        )
    return state(root, frame, "candidate_frame_exhausted")


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.artifact_root).resolve()
    phases = [args.phase] if args.phase != "all" else ["freeze", "discover", "static", "frame", "qualify", "audit"]
    result: dict[str, Any] = {}
    for phase in phases:
        print(f"EXP63-PHASE {phase}", flush=True)
        if phase == "freeze":
            result = freeze_experiment63.run(root, Path(args.source_exp61_root).resolve())
        elif phase == "discover":
            result = snapshot_strict_v427_frame.run(root, args.search_workers)
        elif phase == "static":
            result = strict_static_prefilter.run(root, args.static_workers, args.git_timeout)
        elif phase == "frame":
            result = freeze_experiment63_frame.run(root)
        elif phase == "qualify":
            result = qualify(root, args)
        elif phase == "audit":
            import audit_experiment63
            result = audit_experiment63.run(root)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--source-exp61-root", default=str(SOURCE61_ROOT))
    parser.add_argument("--phase", choices=("all", "freeze", "discover", "static", "frame", "qualify", "audit"), default="all")
    parser.add_argument("--search-workers", type=int, default=SEARCH_WORKERS)
    parser.add_argument("--static-workers", type=int, default=STATIC_WORKERS)
    parser.add_argument("--git-timeout", type=int, default=1800)
    parser.add_argument("--build-timeout", type=int, default=14400)
    parser.add_argument("--trace-timeout", type=int, default=14400)
    parser.add_argument("--enumeration-timeout", type=int, default=7200)
    parser.add_argument("--replay-timeout", type=int, default=1200)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--wait-for-exp62", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2))
