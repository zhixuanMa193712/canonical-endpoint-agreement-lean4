"""Freeze a zero-scientific-execution recovery from the Exp60 disk incident."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from experiment61_protocol import *


NO_SPACE_RE = re.compile(r"no space left on device|errno 28", re.I)
CONFIG_WRITE_RE = re.compile(
    r"failed to write new configuration file|could not set '"
    r"(?:core\.repositoryformatversion|remote\.origin\.(?:url|partialclonefilter))'",
    re.I,
)


def classify_checkout_error(receipt: dict[str, Any]) -> str:
    message = str(receipt.get("error", {}).get("message", ""))
    if NO_SPACE_RE.search(message):
        return "explicit_no_space_left_on_device"
    if CONFIG_WRITE_RE.search(message):
        return "git_config_write_failure_during_disk_exhaustion_incident"
    return "other_operational_checkout_failure"


def validate_source(root60: Path, archive60: Path) -> tuple[
        dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    if file_sha256(archive60) != SOURCE_ARCHIVE_60_SHA256:
        raise ValueError("Exp60 incident archive hash changed")
    protocol = read_json(root60 / "frozen/protocol.json")
    assert_sealed(protocol, "Exp60 protocol")
    if protocol.get("protocol_version") != PROTOCOL_VERSION_60:
        raise ValueError("wrong Exp60 source protocol")
    frame_receipt = read_json(root60 / "frozen/candidate_frame_receipt.json")
    assert_sealed(frame_receipt, "Exp60 candidate frame")
    frame_path = root60 / "frozen/candidate_frame.jsonl"
    if file_sha256(frame_path) != frame_receipt.get("frozen_frame_sha256"):
        raise ValueError("Exp60 candidate frame changed")
    candidates = read_jsonl(frame_path)
    summary = read_json(root60 / "recruitment_shortfall/summary.json")
    audit = read_json(root60 / "recruitment_shortfall/audit.json")
    assert_sealed(summary, "Exp60 shortfall summary")
    assert_sealed(audit, "Exp60 shortfall audit")
    if audit.get("audit_passed") is not True:
        raise ValueError("Exp60 arithmetic audit did not pass")
    if summary.get("scientific_candidate_tactics_executed") != 0:
        raise ValueError("Exp60 scientific tactics were executed")
    if any((root60 / "screening/authored_rows").rglob("*.json")):
        raise ValueError("Exp60 authored replay already started")
    if any((root60 / "scientific").rglob("*.json")):
        raise ValueError("Exp60 scientific execution already started")
    return protocol, frame_receipt, candidates


def run(root61: Path, root60: Path, archive60: Path) -> dict[str, Any]:
    if (root61 / "frozen/protocol.json").exists():
        raise FileExistsError("Exp61 recovery is already frozen")
    protocol60, frame_receipt60, candidates = validate_source(root60, archive60)
    active = [row for row in candidates if not row.get("prequalification_exclusion")]
    excluded = [row for row in candidates if row.get("prequalification_exclusion")]
    if len(active) != 88 or len(excluded) != 1001:
        raise ValueError("Exp60 frozen candidate counts changed")

    incident_rows = []
    recovery_rows = []
    carried_rows = []
    incident_counts: Counter[str] = Counter()
    gate_counts: Counter[str] = Counter()
    for candidate in active:
        slug = candidate["slug"]
        source_path = root60 / "screening/build_trace" / f"{safe_slug_61(slug)}.json"
        base = {"slug": slug, "commit": candidate["commit"]}
        if not source_path.is_file():
            status = "recovery_required_missing_receipt"
            incident_rows.append({**base, "status": status, "source_receipt_sha256": None})
            recovery_rows.append({**candidate, "recovery_reason": status})
            incident_counts[status] += 1
            continue
        receipt = read_json(source_path)
        if receipt.get("candidate") != backend_candidate_61(candidate):
            raise ValueError(f"Exp60 candidate identity changed: {slug}")
        if receipt.get("scientific_candidate_tactics_executed") != 0:
            raise ValueError(f"nonzero scientific tactic count: {slug}")
        gate = receipt.get("first_failed_gate")
        gate_counts[str(gate)] += 1
        receipt_sha = file_sha256(source_path)
        if receipt.get("build_trace_gate") is True:
            raise ValueError("Exp61 recovery expected zero Exp60 build/trace passes")
        if gate == "checkout":
            category = classify_checkout_error(receipt)
            status = "recovery_required_infrastructure_checkout"
            incident_rows.append({
                **base, "status": status, "checkout_error_category": category,
                "source_receipt_sha256": receipt_sha,
            })
            recovery_rows.append({
                **candidate, "recovery_reason": status,
                "source_checkout_error_category": category,
                "source_receipt_sha256": receipt_sha,
            })
            incident_counts[category] += 1
            continue
        if not isinstance(gate, str) or not gate:
            raise ValueError(f"definitive failure lacks a gate: {slug}")
        status = "carried_definitive_noncheckout_failure"
        incident_rows.append({
            **base, "status": status, "first_failed_gate": gate,
            "source_receipt_sha256": receipt_sha,
        })
        carried_rows.append((candidate, source_path, receipt_sha))
        incident_counts[status] += 1

    if incident_counts["explicit_no_space_left_on_device"] != 34:
        raise ValueError("expected 34 explicit no-space checkout receipts")
    if incident_counts["git_config_write_failure_during_disk_exhaustion_incident"] != 6:
        raise ValueError("expected six contemporaneous git-config write failures")
    if len(recovery_rows) != 70 or len(carried_rows) != 18:
        raise ValueError("Exp61 recovery partition changed")

    protocol61 = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION_61,
        "recovery_id": RECOVERY_ID,
        "purpose": "Recover qualification only after the Exp60 disk-exhaustion incident.",
        "source_exp60_archive": str(archive60),
        "source_exp60_archive_sha256": SOURCE_ARCHIVE_60_SHA256,
        "source_exp60_protocol_sha256": file_sha256(root60 / "frozen/protocol.json"),
        "source_exp60_candidate_frame_sha256": file_sha256(
            root60 / "frozen/candidate_frame.jsonl"
        ),
        "source_exp60_shortfall_summary_sha256": file_sha256(
            root60 / "recruitment_shortfall/summary.json"
        ),
        "source_exp60_shortfall_audit_sha256": file_sha256(
            root60 / "recruitment_shortfall/audit.json"
        ),
        "adjudication": {
            "arithmetic_audit_retained": True,
            "shortfall_decision_invalidated_by_infrastructure_contamination": True,
            "explicit_no_space_checkout_receipts": 34,
            "contemporaneous_git_config_write_failures": 6,
            "missing_receipts": 30,
            "carried_definitive_noncheckout_failures": 18,
            "recovery_candidates": 70,
            "corrected_pre_recovery_conservative_upper_bound": 70,
            "repository_target": REPOSITORIES_REQUIRED,
        },
        "recovery_policy": {
            "unchanged_candidate_frame": True,
            "unchanged_exact_commits": True,
            "unchanged_build_trace_backend": True,
            "carry_only_noncheckout_failures": True,
            "retry_checkout_and_missing_receipts": True,
            "new_checkout_failures_remain_operationally_unresolved": True,
            "failed_checkout_cleanup": True,
            "failed_noncheckout_cleanup": True,
            "passing_checkout_retained": True,
            "free_disk_floor_bytes": FREE_DISK_FLOOR_BYTES,
            "batch_size": RECOVERY_BATCH_SIZE,
            "futility_upper_bound": "build_trace_passes plus all unresolved active candidates",
            "stop_if_upper_bound_below": REPOSITORIES_REQUIRED,
        },
        "registered_scientific_design": protocol60,
        "implementation_locks": implementation_locks_61(),
        "scientific_candidate_execution_before_freeze": False,
        "scientific_candidate_tactics_executed": 0,
    })
    atomic_json_dump(protocol61, root61 / "frozen/protocol.json")
    atomic_copy(root60 / "frozen/candidate_frame.jsonl",
                root61 / "frozen/candidate_frame.jsonl")
    frame_receipt61 = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION_61,
        "candidate_count": len(candidates), "active_candidates": len(active),
        "prequalification_exclusions": len(excluded),
        "candidate_frame_sha256": file_sha256(root61 / "frozen/candidate_frame.jsonl"),
        "source_candidate_frame_receipt_sha256": file_sha256(
            root60 / "frozen/candidate_frame_receipt.json"
        ),
        "frame_byte_exact_from_exp60": True,
        "scientific_candidate_tactics_executed": 0,
    })
    atomic_json_dump(frame_receipt61, root61 / "frozen/candidate_frame_receipt.json")
    atomic_jsonl_dump(recovery_rows, root61 / "frozen/recovery_frame.jsonl")
    atomic_jsonl_dump(incident_rows, root61 / "frozen/incident_adjudication_ledger.jsonl")

    for candidate in excluded:
        receipt = seal({
            "version": VERSION, "protocol_version": PROTOCOL_VERSION_61,
            "candidate": candidate, "qualification_gate": False,
            "first_failed_gate": "prequalification_exclusion",
            "exclusion_reason": candidate["prequalification_exclusion"],
            "lineage_representative": False,
            "scientific_candidate_tactics_executed": 0,
        })
        atomic_json_dump(
            receipt,
            root61 / "qualification/repositories" / f"{safe_slug_61(candidate['slug'])}.json",
        )
    for candidate, source_path, receipt_sha in carried_rows:
        destination = root61 / "screening/build_trace" / source_path.name
        atomic_copy(source_path, destination)
        if file_sha256(destination) != receipt_sha:
            raise ValueError(f"carried receipt changed: {candidate['slug']}")

    summary = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION_61,
        "recovery_frozen": True, "source_repositories": len(candidates),
        "active_candidates": len(active), "recovery_candidates": len(recovery_rows),
        "carried_definitive_failures": len(carried_rows),
        "incident_counts": dict(sorted(incident_counts.items())),
        "source_gate_counts": dict(sorted(gate_counts.items())),
        "pre_recovery_conservative_upper_bound": len(recovery_rows),
        "repository_target": REPOSITORIES_REQUIRED,
        "scientific_candidate_tactics_executed": 0,
        "next_step": "Run disk-aware Exp61 qualification recovery.",
    })
    atomic_json_dump(summary, root61 / "frozen/recovery_freeze_receipt.json")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT_61))
    parser.add_argument("--source-artifact-root", default=str(SOURCE_ARTIFACT_ROOT_60))
    parser.add_argument("--source-archive", default=str(SOURCE_ARCHIVE_60))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run(Path(args.artifact_root).resolve(),
                         Path(args.source_artifact_root).resolve(),
                         Path(args.source_archive).resolve()), indent=2, sort_keys=True))
