"""Check and seal an Exp60 recruitment shortfall by a conservative upper bound.

Every unfinished build/trace candidate is counted as a potential success.  The
finalizer is therefore permitted to stop only when observed passes plus all
unfinished candidates are still fewer than the preregistered target of 38.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from experiment60_protocol import *


DECISION_LABEL = "conservative_upper_bound_recruitment_shortfall"
FINALIZER_ID = "experiment60-conservative-futility-finalizer-v1"


def safe_slug(slug: str) -> str:
    return slug.replace("/", "__")


def expected_backend_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": row["slug"],
        "url": row["url"],
        "ref": row["commit"],
        "commit": row["commit"],
        "domain": row.get("domain", "unclassified"),
        "subdir": row.get("subdir", "."),
        "snapshot_source": row["snapshot_source"],
        "snapshot_record_sha256": row["snapshot_record_sha256"],
    }


def load_frozen_inputs(root: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    protocol_path = root / "frozen/protocol.json"
    receipt_path = root / "frozen/candidate_frame_receipt.json"
    frame_path = root / "frozen/candidate_frame.jsonl"
    protocol = read_json(protocol_path)
    assert_sealed(protocol, "Exp60 protocol")
    if protocol.get("protocol_version") != PROTOCOL_VERSION_60:
        raise ValueError("not an Exp60 archival-v4.27 protocol")
    validate_implementation_locks(protocol)
    frame_receipt = read_json(receipt_path)
    assert_sealed(frame_receipt, "Exp60 candidate frame receipt")
    if frame_receipt.get("protocol_version") != PROTOCOL_VERSION_60:
        raise ValueError("candidate frame receipt has the wrong protocol version")
    if file_sha256(frame_path) != frame_receipt.get("frozen_frame_sha256"):
        raise ValueError("frozen candidate frame hash changed")
    candidates = read_jsonl(frame_path)
    if len(candidates) != int(frame_receipt.get("candidate_count", -1)):
        raise ValueError("frozen candidate count changed")
    slugs = [str(row["slug"]) for row in candidates]
    if len(slugs) != len(set(slugs)):
        raise ValueError("duplicate repository slug in frozen candidate frame")
    return protocol, frame_receipt, candidates


def compute_progress(root: Path) -> dict[str, Any]:
    protocol, frame_receipt, candidates = load_frozen_inputs(root)
    active = [row for row in candidates if not row.get("prequalification_exclusion")]
    excluded = [row for row in candidates if row.get("prequalification_exclusion")]
    if len(active) != int(frame_receipt.get("exact_v427_nonhistorical_candidates", -1)):
        raise ValueError("active archival candidate count changed")

    expected_paths = {
        root / "screening/build_trace" / f"{safe_slug(row['slug'])}.json": row
        for row in active
    }
    build_dir = root / "screening/build_trace"
    observed_paths = set(build_dir.glob("*.json")) if build_dir.is_dir() else set()
    extras = observed_paths - set(expected_paths)
    if extras:
        raise ValueError(f"unexpected build/trace receipt(s): {sorted(map(str, extras))}")

    passed: list[str] = []
    failed: list[str] = []
    unfinished: list[str] = []
    failure_counts: Counter[str] = Counter()
    receipt_rows: list[dict[str, Any]] = []
    for candidate in active:
        slug = str(candidate["slug"])
        path = root / "screening/build_trace" / f"{safe_slug(slug)}.json"
        if not path.is_file():
            unfinished.append(slug)
            receipt_rows.append({
                "slug": slug,
                "commit": candidate["commit"],
                "status": "unfinished_counted_as_potential_success",
                "build_trace_gate": None,
                "first_failed_gate": None,
                "receipt_sha256": None,
            })
            continue
        receipt = read_json(path)
        if receipt.get("candidate") != expected_backend_candidate(candidate):
            raise ValueError(f"build/trace candidate identity changed: {slug}")
        if receipt.get("scientific_candidate_tactics_executed") != 0:
            raise ValueError(f"scientific tactic count is nonzero in build receipt: {slug}")
        gate = receipt.get("build_trace_gate") is True
        failed_gate = receipt.get("first_failed_gate")
        if gate:
            if failed_gate is not None:
                raise ValueError(f"passing build receipt has a failure gate: {slug}")
            passed.append(slug)
            status = "completed_build_trace_pass"
        else:
            if not isinstance(failed_gate, str) or not failed_gate:
                raise ValueError(f"failed build receipt lacks a failure gate: {slug}")
            failed.append(slug)
            failure_counts[failed_gate] += 1
            status = "completed_build_trace_failure"
        receipt_rows.append({
            "slug": slug,
            "commit": candidate["commit"],
            "status": status,
            "build_trace_gate": gate,
            "first_failed_gate": failed_gate,
            "receipt_sha256": file_sha256(path),
        })

    completed = len(passed) + len(failed)
    upper_bound = len(passed) + len(unfinished)
    target = int(protocol["repository_sampling"]["take"])
    if target != REPOSITORIES_REQUIRED:
        raise ValueError("preregistered repository target changed")
    return {
        "protocol": protocol,
        "frame_receipt": frame_receipt,
        "candidates": candidates,
        "active": active,
        "excluded": excluded,
        "receipt_rows": receipt_rows,
        "completed": completed,
        "passed": passed,
        "failed": failed,
        "unfinished": unfinished,
        "failure_counts": dict(sorted(failure_counts.items())),
        "target": target,
        "conservative_upper_bound": upper_bound,
        "can_still_reach_target": upper_bound >= target,
    }


def check_only(root: Path) -> dict[str, Any]:
    state = compute_progress(root)
    return {
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION_60,
        "mode": "read_only_futility_check",
        "active_archival_candidates": len(state["active"]),
        "completed_build_trace_receipts": state["completed"],
        "observed_build_trace_passes": len(state["passed"]),
        "observed_build_trace_failures": len(state["failed"]),
        "unfinished_candidates": len(state["unfinished"]),
        "repository_target": state["target"],
        "conservative_upper_bound": state["conservative_upper_bound"],
        "can_still_reach_target": state["can_still_reach_target"],
        "safe_to_stop_for_deterministic_shortfall": not state["can_still_reach_target"],
        "failure_counts": state["failure_counts"],
        "scientific_candidate_tactics_executed": 0,
        "next_step": (
            "KEEP RUNNING: the conservative upper bound can still reach 38."
            if state["can_still_reach_target"]
            else "STOP THE QUALIFIER, then rerun this program with --finalize."
        ),
    }


def validate_zero_scientific_execution(root: Path, state: dict[str, Any]) -> dict[str, int]:
    authored_rows = sorted((root / "screening/authored_rows").rglob("*.json"))
    scientific_rows = sorted((root / "scientific").rglob("*.json"))
    if authored_rows:
        raise ValueError("authored replay already started; conservative pre-replay finalization refused")
    if scientific_rows:
        raise ValueError("scientific execution receipts exist; recruitment-only finalization refused")
    if (root / "frozen/selection_receipt.json").exists():
        raise ValueError("a scientific repository/root selection receipt already exists")

    expected_prequalified = {
        root / "qualification/repositories" / f"{safe_slug(row['slug'])}.json": row
        for row in state["excluded"]
    }
    qualification_dir = root / "qualification/repositories"
    observed = set(qualification_dir.glob("*.json")) if qualification_dir.is_dir() else set()
    missing = set(expected_prequalified) - observed
    if missing:
        raise ValueError(f"missing prequalification exclusion receipt(s): {len(missing)}")
    for path, candidate in expected_prequalified.items():
        receipt = read_json(path)
        assert_sealed(receipt, f"prequalification receipt {candidate['slug']}")
        if receipt.get("candidate") != candidate:
            raise ValueError(f"prequalification identity changed: {candidate['slug']}")
        if receipt.get("first_failed_gate") != "prequalification_exclusion":
            raise ValueError(f"prequalification failure gate changed: {candidate['slug']}")
        if receipt.get("exclusion_reason") != candidate.get("prequalification_exclusion"):
            raise ValueError(f"prequalification exclusion changed: {candidate['slug']}")
        if receipt.get("scientific_candidate_tactics_executed") != 0:
            raise ValueError(f"scientific tactic count is nonzero: {candidate['slug']}")
    for path in observed - set(expected_prequalified):
        receipt = read_json(path)
        assert_sealed(receipt, f"unexpected-stage qualification receipt {path.name}")
        if receipt.get("scientific_candidate_tactics_executed") != 0:
            raise ValueError(f"scientific tactic count is nonzero: {path}")
    return {
        "prequalification_receipts": len(expected_prequalified),
        "other_qualification_receipts": len(observed - set(expected_prequalified)),
        "authored_replay_rows": 0,
        "scientific_receipts": 0,
    }


def finalize(root: Path) -> dict[str, Any]:
    state = compute_progress(root)
    if state["can_still_reach_target"]:
        raise ValueError(
            "finalization refused: observed passes plus every unfinished candidate "
            f"can still reach {state['target']}"
        )
    zero_counts = validate_zero_scientific_execution(root, state)
    output_dir = root / "recruitment_shortfall"
    ledger_path = output_dir / "conservative_completion_ledger.jsonl"
    atomic_jsonl_dump(state["receipt_rows"], ledger_path)
    summary = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION_60,
        "finalizer_id": FINALIZER_ID,
        "decision_label": DECISION_LABEL,
        "stopping_rule": (
            "Stop when observed build/trace passes plus every unfinished exact-v4.27 "
            "candidate is fewer than the preregistered 38 repositories."
        ),
        "source_repositories": len(state["candidates"]),
        "prequalification_exclusions": len(state["excluded"]),
        "active_archival_candidates": len(state["active"]),
        "completed_build_trace_receipts": state["completed"],
        "observed_build_trace_passes": len(state["passed"]),
        "observed_build_trace_failures": len(state["failed"]),
        "unfinished_candidates": len(state["unfinished"]),
        "repository_target": state["target"],
        "conservative_upper_bound": state["conservative_upper_bound"],
        "shortfall_even_if_every_unfinished_candidate_passed": (
            state["target"] - state["conservative_upper_bound"]
        ),
        "unfinished_candidates_counted_as_successes_for_upper_bound": True,
        "failure_counts": state["failure_counts"],
        "observed_passing_slugs": state["passed"],
        "observed_failing_slugs": state["failed"],
        "unfinished_slugs": state["unfinished"],
        **zero_counts,
        "scientific_candidate_tactics_executed": 0,
        "scientific_result": False,
        "interpretation": (
            "Recruitment shortfall only; this is not a negative treatment-effect result "
            "and it does not change the historical Exp51 precision-inconclusive label."
        ),
        "historical_exp51_precision_inconclusive_retained": True,
        "protocol_sha256": file_sha256(root / "frozen/protocol.json"),
        "candidate_frame_receipt_sha256": file_sha256(
            root / "frozen/candidate_frame_receipt.json"
        ),
        "candidate_frame_sha256": file_sha256(root / "frozen/candidate_frame.jsonl"),
        "completion_ledger": str(ledger_path),
        "completion_ledger_sha256": file_sha256(ledger_path),
        "qualification_stopped_early_after_deterministic_futility": True,
        "next_step": "Do not execute Exp60 scientific candidates; design a new recruitment route.",
    })
    atomic_json_dump(summary, output_dir / "summary.json")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check-only", action="store_true")
    group.add_argument("--finalize", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    artifact_root = Path(args.artifact_root).resolve()
    result = check_only(artifact_root) if args.check_only else finalize(artifact_root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
