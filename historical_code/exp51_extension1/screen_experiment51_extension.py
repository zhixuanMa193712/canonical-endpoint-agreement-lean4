"""Run the frozen zero-scientific-candidate Exp51 repository-frame extension."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import shutil
import subprocess
import sys
import threading
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from experiment51_extension_protocol import *

import screen_experiment51_repositories as base_screen

ENUMERATION_WORKER = PACKAGE_ROOT / "experiment51_extension_enumeration_worker.py"


def extension_config(root: Path) -> tuple[dict, Path, str]:
    path = root / "frozen/extension_config.json"
    config = read_json(path)
    validate_code_lock(config["code_lock"])
    if file_sha256(CANDIDATE_FRAME) != config["candidate_frame_sha256"]:
        raise ValueError("extension candidate frame changed")
    identity = json_sha256({
        key: value for key, value in config.items()
        if key not in {"created_utc", "identity_sha256"}
    })
    if identity != config.get("identity_sha256"):
        raise ValueError("extension config identity changed")
    return config, path, file_sha256(path)


def enumerate_isolated(
    project: Path,
    slug: str,
    commit: str,
    root: Path,
    framep: Path,
    timeout: int,
    trace_ledger_sha256: str | None = None,
) -> tuple[list[dict], Counter[str], dict]:
    safe = safe_slug(slug)
    inputp = root / "screening/enumeration_inputs" / f"{safe}.json"
    receiptp = root / "screening/enumeration_receipts" / f"{safe}.json"
    payload = {
        "version": 1,
        "extension_version": EXTENSION_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "project": str(project.resolve()),
        "slug": slug,
        "commit": commit,
        "frame_output": str(framep.resolve()),
        "receipt_output": str(receiptp.resolve()),
        "trace_ledger_sha256": trace_ledger_sha256,
        "scientific_candidate_tactics_permitted": 0,
    }
    payload["identity_sha256"] = json_sha256(payload)
    atomic_json_dump(payload, inputp)
    proc = base_screen.run_cmd_isolated(
        [sys.executable, str(ENUMERATION_WORKER), "--input", str(inputp)],
        PACKAGE_ROOT,
        timeout,
    )
    if proc.returncode != 0:
        receipt = read_json(receiptp) if receiptp.is_file() else None
        raise RuntimeError(
            f"extension enumeration failed returncode={proc.returncode}; "
            f"receipt={receipt!r}; stdout={proc.stdout[-2000:]!r}; "
            f"stderr={proc.stderr[-6000:]!r}"
        )
    if not receiptp.is_file() or not framep.is_file():
        raise FileNotFoundError(f"extension enumeration omitted outputs: {slug}")
    receipt = read_json(receiptp)
    offline = receipt.get("offline_dependency_adapter", {})
    if not (
        receipt.get("worker_ok") is True
        and receipt.get("input_identity_sha256") == payload["identity_sha256"]
        and receipt.get("slug") == slug
        and receipt.get("commit") == commit
        and receipt.get("frame_sha256") == file_sha256(framep)
        and receipt.get("scientific_candidate_tactics_executed") == 0
        and offline.get("schema")
        == "leandojo-4.20.0-buildDeps-false-no-remote-metadata-v1"
        and offline.get("dependency_queries_suppressed") == 1
        and offline.get("github_api_attempts") == 0
        and offline.get("returned_dependency_maps") == [0]
        and offline.get("installed_lean_dojo_files_modified") is False
        and offline.get("repository_checkout_modified") is False
    ):
        raise ValueError(f"invalid extension enumeration receipt: {slug}")
    frame = read_jsonl(framep)
    if receipt.get("pre_replay_frame") != len(frame):
        raise ValueError(f"extension enumeration count differs: {slug}")
    exclusions = Counter({
        str(key): int(value) for key, value in receipt.get("exclusions", {}).items()
    })
    return frame, exclusions, receipt


def carry_forward(root: Path, config_sha: str) -> dict:
    _, configp, observed_sha = extension_config(root)
    if observed_sha != config_sha:
        raise ValueError("extension config identity changed")
    rows = validate_base_carry_forward()
    ledger = []
    for source in rows:
        slug = source["slug"]
        safe = safe_slug(slug)
        source_receipt = Path(source["receipt"])
        value = read_json(source_receipt)
        value["extension_carry_forward"] = {
            "extension_version": EXTENSION_VERSION,
            "extension_config_sha256": config_sha,
            "source_receipt": str(source_receipt),
            "source_receipt_sha256": source["receipt_sha256"],
            "source_frame_sha256": source["frame_sha256"],
            "source_inventory_sha256": source["source_inventory_sha256"],
            "scientific_candidate_tactics_executed": 0,
        }
        out_receipt = root / "screening/build_trace" / f"{safe}.json"
        out_frame = root / "screening/frames" / f"{safe}.jsonl"
        out_inventory = root / "screening/source_inventories" / f"{safe}.jsonl"
        atomic_json_dump(value, out_receipt)
        out_frame.parent.mkdir(parents=True, exist_ok=True)
        out_inventory.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source["frame"], out_frame)
        shutil.copy2(source["source_inventory"], out_inventory)
        if file_sha256(out_frame) != source["frame_sha256"]:
            raise ValueError(f"carried frame changed: {slug}")
        if file_sha256(out_inventory) != source["source_inventory_sha256"]:
            raise ValueError(f"carried source inventory changed: {slug}")
        ledger.append({
            "slug": slug,
            "source_receipt_sha256": source["receipt_sha256"],
            "active_receipt_sha256": file_sha256(out_receipt),
            "frame_sha256": file_sha256(out_frame),
            "source_inventory_sha256": file_sha256(out_inventory),
            "pre_replay_frame": source["pre_replay_frame"],
        })
    result = {
        "version": 1,
        "extension_version": EXTENSION_VERSION,
        "config": str(configp),
        "config_sha256": config_sha,
        "repositories": len(ledger),
        "repository_ledger": ledger,
        "all_build_trace_gates_preserved": True,
        "trace_executed": False,
        "theorem_sources_elaborated": 0,
        "scientific_candidate_tactics_executed": 0,
        "carry_forward_gate": len(ledger) == len(CARRY_FORWARD_SLUGS),
        "next_step": "Run offline parser controls.",
    }
    atomic_json_dump(result, root / "screening/carry_forward_summary.json")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def base_args() -> SimpleNamespace:
    return SimpleNamespace(
        threads=THREADS_PER_TRACE,
        git_timeout=GIT_TIMEOUT,
        build_timeout=BUILD_TIMEOUT,
        trace_timeout=TRACE_TIMEOUT,
        enumeration_timeout=ENUMERATION_TIMEOUT,
        replay_timeout=REPLAY_TIMEOUT,
    )


def run_build_trace(root: Path, config_sha: str) -> dict:
    carry = read_json(root / "screening/carry_forward_summary.json")
    controls = read_json(root / "preflight/offline_parser_control.json")
    runtime = read_json(root / "preflight/environment.json")
    if carry.get("carry_forward_gate") is not True:
        raise ValueError("carry-forward gate has not passed")
    if controls.get("control_gate") is not True:
        raise ValueError("offline parser controls have not passed")
    if runtime.get("environment_gate") is not True:
        raise ValueError("extension environment gate has not passed")

    frame = validate_candidate_frame()
    candidates = list(frame["candidates"])
    base_screen.SCREEN_CHECKOUT_ROOT = CHECKOUT_ROOT
    base_screen.enumerate_frame_isolated = enumerate_isolated
    build_slots = threading.Semaphore(BUILD_SLOTS)
    trace_slots = threading.Semaphore(TRACE_SLOTS)
    enumeration_slots = threading.Semaphore(ENUMERATION_SLOTS)
    args = base_args()
    rows: list[dict | None] = [None] * len(candidates)
    for index, candidate in enumerate(candidates, 1):
        print(f"EXP51-EXT-QUEUED {index}/{len(candidates)} {candidate['slug']}", flush=True)
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=REPOSITORY_WORKERS,
        thread_name_prefix="exp51-extension1",
    ) as executor:
        futures = {
            executor.submit(
                base_screen.build_trace_one,
                candidate,
                args,
                root,
                build_slots,
                trace_slots,
                enumeration_slots,
            ): (index, candidate)
            for index, candidate in enumerate(candidates)
        }
        for future in concurrent.futures.as_completed(futures):
            index, candidate = futures[future]
            row = future.result()
            row["extension_version"] = EXTENSION_VERSION
            row["extension_config_sha256"] = config_sha
            row["mechanical_fix_id"] = MECHANICAL_FIX_ID
            row["scientific_candidate_tactics_executed"] = 0
            atomic_json_dump(
                row,
                root / "screening/build_trace" / f"{safe_slug(candidate['slug'])}.json",
            )
            rows[index] = row
            print(
                f"EXP51-EXT-DONE {index + 1}/{len(candidates)} {candidate['slug']} "
                f"gate={int(row.get('build_trace_gate') is True)} "
                f"failed={row.get('first_failed_gate')}",
                flush=True,
            )
    if any(row is None for row in rows):
        raise RuntimeError("extension build/trace returned an incomplete result vector")
    completed = [row for row in rows if row is not None]
    if any(row.get("scientific_candidate_tactics_executed") != 0 for row in completed):
        raise ValueError("extension build/trace executed scientific candidates")
    new_passed = sum(row.get("build_trace_gate") is True for row in completed)
    total_passed = len(CARRY_FORWARD_SLUGS) + new_passed
    failure_counts = Counter(
        row.get("first_failed_gate") or "passed" for row in completed
    )
    parser_receipts = sorted((root / "screening/enumeration_receipts").glob("*.json"))
    parser_rows = [read_json(path) for path in parser_receipts]
    trace_qualified = sum(
        row.get("trace", {}).get("trace_ok") is True for row in completed
    )
    receipt_accounting_exact = len(parser_rows) == trace_qualified
    github_api_attempts = sum(
        (row.get("offline_dependency_adapter") or {}).get("github_api_attempts", 0)
        for row in parser_rows
    )
    result = {
        "version": 1,
        "extension_version": EXTENSION_VERSION,
        "config_sha256": config_sha,
        "carry_forward_passes": len(CARRY_FORWARD_SLUGS),
        "extension_candidates": len(completed),
        "extension_passes": new_passed,
        "combined_build_trace_passes": total_passed,
        "target_repositories": TARGET_REPOSITORIES,
        "minimum_required": MIN_REPOSITORIES,
        "failure_gate_counts": dict(sorted(failure_counts.items())),
        "trace_qualified_for_enumeration": trace_qualified,
        "enumeration_receipts_found": len(parser_rows),
        "enumeration_receipt_accounting_exact": receipt_accounting_exact,
        "enumeration_failure_receipts_preserved": sum(
            row.get("worker_ok") is False for row in parser_rows
        ),
        "github_api_attempts": github_api_attempts,
        "scientific_candidate_tactics_executed": 0,
        "execution_complete": len(completed) == len(candidates),
        "build_trace_gate": bool(
            len(completed) == len(candidates)
            and receipt_accounting_exact
            and github_api_attempts == 0
            and total_passed >= MIN_REPOSITORIES
        ),
    }
    result["next_step"] = (
        "Run compile-only authored-replay worker preflight."
        if result["build_trace_gate"]
        else "STOP: combined extension frame still has fewer than twelve build/trace passes."
    )
    atomic_json_dump(result, root / "screening/build_trace_summary.json")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def combined_candidates(config: dict) -> list[dict]:
    carried = [row["candidate"] for row in config["carry_forward"]]
    extension = list(validate_candidate_frame()["candidates"])
    return carried + extension


def finalize(root: Path, config: dict, config_sha: str, candidates: list[dict]) -> dict:
    ledger = []
    hash_sets: dict[str, set[str]] = {}
    for candidate in candidates:
        slug = candidate["slug"]
        replay = read_json(root / "screening/replay" / f"{safe_slug(slug)}.json")
        build = read_json(root / "screening/build_trace" / f"{safe_slug(slug)}.json")
        ledger.append({
            "slug": slug,
            "commit": build.get("commit"),
            "build_trace_gate": build.get("build_trace_gate") is True,
            "authored_replay_gate": replay.get("authored_replay_gate") is True,
            "eligible_roots": replay.get("eligible_roots", 0),
            "first_failed_gate": (
                replay.get("first_failed_gate") or build.get("first_failed_gate")
            ),
            "source": "carry_forward" if slug in CARRY_FORWARD_SLUGS else "extension1",
        })
        inventoryp = root / "screening/source_inventories" / f"{safe_slug(slug)}.jsonl"
        hash_sets[slug] = {
            row["normalized_whitespace_free_sha256"] for row in read_jsonl(inventoryp)
        } if inventoryp.is_file() else set()
    eligible_order = [row["slug"] for row in ledger if row["authored_replay_gate"]]
    lineage = []
    blocked: set[str] = set()
    for index, left in enumerate(eligible_order):
        for right in eligible_order[index + 1:]:
            score = base_screen.overlap(hash_sets[left], hash_sets[right])
            same = score >= SOURCE_OVERLAP_THRESHOLD
            lineage.append({
                "left": left,
                "right": right,
                "overlap": score,
                "threshold": SOURCE_OVERLAP_THRESHOLD,
                "same_lineage": same,
            })
            if same:
                blocked.add(right)
    representatives = [slug for slug in eligible_order if slug not in blocked]
    selected = representatives[:TARGET_REPOSITORIES]
    result = {
        "version": 1,
        "extension_version": EXTENSION_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "config_sha256": config_sha,
        "scientific_candidate_tactics_executed": 0,
        "repositories_considered": len(candidates),
        "repository_ledger": ledger,
        "lineage_pairs": lineage,
        "lineage_representatives": representatives,
        "selected_repositories": selected,
        "ordered_backups": representatives[TARGET_REPOSITORIES:],
        "selected_count": len(selected),
        "minimum_required": MIN_REPOSITORIES,
        "screening_gate": len(selected) >= MIN_REPOSITORIES,
    }
    result["next_step"] = (
        "Freeze Exp51 scientific targets and Exp52 before any scientific alternative execution."
        if result["screening_gate"]
        else "STOP: extension authored-replay frame remains below twelve repositories."
    )
    atomic_json_dump(result, root / "screening/summary.json")
    atomic_jsonl_dump(lineage, root / "screening/lineage_table.jsonl")
    return result


def run_authored_replay(root: Path, config: dict, config_sha: str) -> dict:
    build = read_json(root / "screening/build_trace_summary.json")
    preflight = read_json(root / "preflight/screening_worker_compile.json")
    if build.get("build_trace_gate") is not True:
        raise ValueError("combined build/trace gate did not pass")
    if preflight.get("compile_ok") is not True:
        raise ValueError("screening worker compile-only preflight did not pass")
    candidates = combined_candidates(config)
    args = base_args()
    for index, candidate in enumerate(candidates, 1):
        print(
            f"EXP51-EXT-AUTHORED {index}/{len(candidates)} {candidate['slug']}",
            flush=True,
        )
        base_screen.replay_one(candidate, args, root, config_sha)
    result = finalize(root, config, config_sha, candidates)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main(args: argparse.Namespace) -> dict:
    root = Path(args.root).resolve()
    config, _, config_sha = extension_config(root)
    if args.phase == "carry-forward":
        return carry_forward(root, config_sha)
    if args.phase == "build-trace":
        return run_build_trace(root, config_sha)
    return run_authored_replay(root, config, config_sha)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ARTIFACT_ROOT))
    parser.add_argument(
        "--phase",
        choices=("carry-forward", "build-trace", "authored-replay"),
        required=True,
    )
    return parser.parse_args()


if __name__ == "__main__":
    parsed = parse_args()
    result = main(parsed)
    gate = (
        result.get("carry_forward_gate")
        if parsed.phase == "carry-forward"
        else result.get("build_trace_gate")
        if parsed.phase == "build-trace"
        else result.get("screening_gate")
    )
    raise SystemExit(0 if gate is True else 2)
