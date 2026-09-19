"""Zero-scientific-candidate qualification of every frozen Exp56 candidate."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
import threading
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from experiment56_protocol import *


sys.path.insert(0, str(WORKSPACE_ROOT / "experiment51_external_repository_replication"))
import screen_experiment51_repositories as backend  # type: ignore


def configure_backend(root: Path) -> None:
    backend.SERVER_ROOT = WORKSPACE_ROOT
    backend.SCREEN_CHECKOUT_ROOT = WORKSPACE_ROOT / "external_repos/experiment56_prospective"
    backend.ARTIFACT_ROOT = root
    backend.ROOTS_PER_REPOSITORY = MIN_ELIGIBLE_ROOTS


def backend_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": row["slug"], "url": row["url"], "ref": row["commit"],
        "commit": row["commit"], "domain": row.get("domain", "unclassified"),
        "subdir": row.get("subdir", "."),
        "snapshot_source": row["snapshot_source"],
        "snapshot_record_sha256": row["snapshot_record_sha256"],
    }


def build_trace(root: Path, candidates: list[dict[str, Any]], args: argparse.Namespace) -> None:
    configure_backend(root)
    build_slots = threading.Semaphore(args.build_slots)
    trace_slots = threading.Semaphore(args.trace_slots)
    enumeration_slots = threading.Semaphore(args.enumeration_slots)
    old_args = SimpleNamespace(
        git_timeout=args.git_timeout, build_timeout=args.build_timeout,
        trace_timeout=args.trace_timeout, enumeration_timeout=args.enumeration_timeout,
        threads=args.threads,
    )
    active = []
    for row in candidates:
        if row.get("prequalification_exclusion"):
            safe = backend.safe_slug(row["slug"])
            receipt = seal({
                "version": VERSION, "protocol_version": PROTOCOL_VERSION,
                "candidate": row, "qualification_gate": False,
                "first_failed_gate": "prequalification_exclusion",
                "exclusion_reason": row["prequalification_exclusion"],
                "lineage_representative": False,
                "scientific_candidate_tactics_executed": 0,
            })
            atomic_json_dump(receipt, root / "qualification/repositories" / f"{safe}.json")
        else:
            active.append(row)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.repository_workers) as executor:
        futures = {
            executor.submit(
                backend.build_trace_one, backend_candidate(row), old_args, root,
                build_slots, trace_slots, enumeration_slots,
            ): row for row in active
        }
        for future in concurrent.futures.as_completed(futures):
            candidate = futures[future]
            receipt = future.result()
            print(
                f"EXP56-BUILD-TRACE {candidate['slug']} gate={int(receipt.get('build_trace_gate') is True)} "
                f"failed={receipt.get('first_failed_gate')}", flush=True,
            )


def compile_worker(root: Path, candidates: list[dict[str, Any]], timeout: int) -> dict[str, Any]:
    configure_backend(root)
    passed = []
    for candidate in candidates:
        if candidate.get("prequalification_exclusion"):
            continue
        path = root / "screening/build_trace" / f"{backend.safe_slug(candidate['slug'])}.json"
        if path.is_file():
            row = backend.read_json(path)
            if row.get("build_trace_gate") is True:
                passed.append(row)
    if not passed:
        raise ValueError("no build-trace-passing repository for compile preflight")
    sys.path.insert(0, str(WORKSPACE_ROOT / "experiment51_external_repository_replication"))
    import experiment51_live_worker as live  # type: ignore
    lean_path = root / "generated" / live.LEAN_FILE_NAME
    lean_path.parent.mkdir(parents=True, exist_ok=True)
    lean_path.write_text(live.LEAN_SOURCE, encoding="utf-8")
    results = []
    seen = set()
    for row in passed:
        slug = row["candidate"]["slug"]
        if slug in seen:
            continue
        seen.add(slug)
        proc = subprocess.run(
            ["lake", "env", "lean", str(lean_path)], cwd=Path(row["project"]),
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        )
        results.append({"slug": slug, "compile_ok": proc.returncode == 0,
                        "returncode": proc.returncode, "stderr_tail": proc.stderr[-6000:]})
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "diagnostic_only": True, "repositories_compiled": len(results),
        "results": results, "lean_source_sha256": file_sha256(lean_path),
        "compile_gate": bool(results) and all(row["compile_ok"] for row in results),
        "theorem_sources_elaborated": 0, "scientific_candidate_tactics_executed": 0,
    })
    atomic_json_dump(value, root / "preflight/screening_worker_compile.json")
    return value


def replay_repository(root: Path, candidate: dict[str, Any], args: argparse.Namespace,
                      config_sha: str) -> dict[str, Any]:
    configure_backend(root)
    safe = backend.safe_slug(candidate["slug"])
    qualified_path = root / "qualification/repositories" / f"{safe}.json"
    if qualified_path.exists():
        value = read_json(qualified_path)
        assert_sealed(value, f"qualification {candidate['slug']}")
        return value
    build_path = root / "screening/build_trace" / f"{safe}.json"
    build = backend.read_json(build_path)
    value: dict[str, Any] = {
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "candidate": candidate, "backend_build_receipt": str(build_path),
        "backend_build_receipt_sha256": file_sha256(build_path),
        "scientific_candidate_tactics_executed": 0,
    }
    if build.get("build_trace_gate") is not True:
        value.update({"qualification_gate": False,
                      "first_failed_gate": build.get("first_failed_gate") or "build_trace"})
        seal(value); atomic_json_dump(value, qualified_path); return value
    preflight = read_json(root / "preflight/screening_worker_compile.json")
    assert_sealed(preflight, "screening worker preflight")
    if preflight.get("compile_gate") is not True:
        raise ValueError("screening worker preflight failed")
    frame_path = root / "screening/frames" / f"{safe}.jsonl"
    frame = backend.read_jsonl(frame_path)
    eligible = []
    failures: Counter[str] = Counter()
    for index, target in enumerate(frame, 1):
        inp = backend.worker_input(root, target, config_sha, [], "exp56_prospective_authored_only")
        input_path = root / "screening/authored_inputs" / safe / f"{target['rid']}.json"
        output_path = root / "screening/authored_rows" / safe / f"{target['rid']}.json"
        if output_path.exists():
            raise FileExistsError("prospective authored replay retry prohibited")
        backend.atomic_json_dump(inp, input_path)
        proc = backend.run_cmd(
            [sys.executable, str(backend.WORKER), "--input", str(input_path),
             "--output", str(output_path), "--generated-dir", str(root / "generated"),
             "--timeout", str(args.replay_timeout)],
            backend.PACKAGE_ROOT, args.replay_timeout + 120,
        )
        if not output_path.is_file():
            raise RuntimeError(f"authored replay lacked receipt: {proc.stderr[-6000:]}")
        row = backend.read_json(output_path)
        ok = row.get("worker_ok") is True and len(row.get("candidates", [])) == 0
        if ok:
            eligible.append({
                **target, "authored_row": str(output_path),
                "authored_row_sha256": file_sha256(output_path),
            })
        else:
            failures[str(row.get("error_type") or "authored_gate")] += 1
        print(f"EXP56-AUTHORED {candidate['slug']} {index}/{len(frame)} ok={int(ok)}", flush=True)
    eligible_path = root / "qualification/eligible_roots" / f"{safe}.jsonl"
    atomic_jsonl_dump(eligible, eligible_path)
    gate = len(eligible) >= MIN_ELIGIBLE_ROOTS
    value.update({
        "commit": build["commit"], "project": build["project"],
        "build_trace_gate": True, "roots_replayed": len(frame),
        "eligible_roots": len(eligible), "authored_failure_counts": dict(sorted(failures.items())),
        "eligible_root_frame": str(eligible_path),
        "eligible_root_frame_sha256": file_sha256(eligible_path),
        "qualification_gate": gate,
        "first_failed_gate": None if gate else "minimum_authored_replay_roots",
        "lineage_representative": None,
    })
    seal(value); atomic_json_dump(value, qualified_path); return value


def finalize_lineages(root: Path, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    configure_backend(root)
    records = []
    hash_sets = {}
    for candidate in candidates:
        safe = backend.safe_slug(candidate["slug"])
        path = root / "qualification/repositories" / f"{safe}.json"
        row = read_json(path); assert_sealed(row, f"qualification {candidate['slug']}")
        records.append((path, row))
        inventory = root / "screening/source_inventories" / f"{safe}.jsonl"
        hash_sets[candidate["slug"]] = {
            item["normalized_whitespace_free_sha256"] for item in backend.read_jsonl(inventory)
        } if inventory.is_file() else set()
    eligible = [(path, row) for path, row in records if row.get("qualification_gate") is True]
    eligible.sort(key=lambda item: selection_key(
        MASTER_REPOSITORY_SEED, item[1]["candidate"]["slug"], item[1]["candidate"]["commit"]
    ))
    representatives = []
    pairs = []
    for path, row in eligible:
        slug = row["candidate"]["slug"]
        duplicate_of = None
        for representative in representatives:
            right = representative[1]["candidate"]["slug"]
            a, b = hash_sets[slug], hash_sets[right]
            overlap = len(a & b) / min(len(a), len(b)) if a and b else 0.0
            pairs.append({"left": slug, "right": right, "overlap": overlap,
                          "threshold": SOURCE_OVERLAP_THRESHOLD,
                          "same_lineage": overlap >= SOURCE_OVERLAP_THRESHOLD})
            if overlap >= SOURCE_OVERLAP_THRESHOLD:
                duplicate_of = right
                break
        row["lineage_representative"] = duplicate_of is None
        row["lineage_duplicate_of"] = duplicate_of
        seal(row); atomic_json_dump(row, path)
        if duplicate_of is None:
            representatives.append((path, row))
    for path, row in records:
        if row.get("qualification_gate") is not True:
            row["lineage_representative"] = False
            row["lineage_duplicate_of"] = None
            seal(row); atomic_json_dump(row, path)
    atomic_jsonl_dump(pairs, root / "qualification/lineage_pairs.jsonl")
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "candidate_repositories": len(records), "eligible_repositories": len(eligible),
        "lineage_representatives": len(representatives),
        "lineage_pairs": len(pairs),
        "qualification_gate": len(representatives) >= REPOSITORIES_REQUIRED,
        "scientific_candidate_tactics_executed": 0,
        "next_step": "Freeze repository and root selections." if len(representatives) >= REPOSITORIES_REQUIRED
                     else "STOP: insufficient independent eligible repositories.",
    })
    atomic_json_dump(value, root / "qualification/summary.json")
    return value


def main(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.artifact_root).resolve()
    protocol = read_json(root / "frozen/protocol.json"); assert_sealed(protocol, "protocol")
    validate_implementation_locks(protocol)
    frame_receipt = read_json(root / "frozen/candidate_frame_receipt.json")
    assert_sealed(frame_receipt, "candidate frame")
    candidates = read_jsonl(root / "frozen/candidate_frame.jsonl")
    config_sha = protocol["record_sha256"]
    if args.phase in ("build-trace", "all"):
        build_trace(root, candidates, args)
        compile_worker(root, candidates, args.compile_timeout)
    if args.phase in ("authored-replay", "all"):
        for candidate in candidates:
            replay_repository(root, candidate, args, config_sha)
    if args.phase in ("lineage", "all"):
        return finalize_lineages(root, candidates)
    return seal({"version": VERSION, "protocol_version": PROTOCOL_VERSION,
                 "phase": args.phase, "scientific_candidate_tactics_executed": 0})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--phase", choices=("build-trace", "authored-replay", "lineage", "all"), required=True)
    parser.add_argument("--repository-workers", type=int, default=16)
    parser.add_argument("--build-slots", type=int, default=4)
    parser.add_argument("--trace-slots", type=int, default=16)
    parser.add_argument("--enumeration-slots", type=int, default=4)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--git-timeout", type=int, default=1800)
    parser.add_argument("--build-timeout", type=int, default=7200)
    parser.add_argument("--trace-timeout", type=int, default=14400)
    parser.add_argument("--enumeration-timeout", type=int, default=7200)
    parser.add_argument("--compile-timeout", type=int, default=300)
    parser.add_argument("--replay-timeout", type=int, default=900)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(main(parse_args()), indent=2))
