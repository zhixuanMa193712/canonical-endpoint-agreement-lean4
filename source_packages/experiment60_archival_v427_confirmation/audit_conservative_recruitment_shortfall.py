"""Independently audit an Exp60 conservative recruitment-shortfall seal."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from experiment60_protocol import *


def safe_slug(slug: str) -> str:
    return slug.replace("/", "__")


def backend_identity(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": candidate["slug"], "url": candidate["url"],
        "ref": candidate["commit"], "commit": candidate["commit"],
        "domain": candidate.get("domain", "unclassified"),
        "subdir": candidate.get("subdir", "."),
        "snapshot_source": candidate["snapshot_source"],
        "snapshot_record_sha256": candidate["snapshot_record_sha256"],
    }


def audit(root: Path) -> dict[str, Any]:
    protocol = read_json(root / "frozen/protocol.json")
    assert_sealed(protocol, "Exp60 protocol")
    validate_implementation_locks(protocol)
    frame_receipt = read_json(root / "frozen/candidate_frame_receipt.json")
    assert_sealed(frame_receipt, "Exp60 candidate frame")
    frame_path = root / "frozen/candidate_frame.jsonl"
    if file_sha256(frame_path) != frame_receipt.get("frozen_frame_sha256"):
        raise ValueError("candidate frame hash mismatch")
    candidates = read_jsonl(frame_path)
    active = [row for row in candidates if not row.get("prequalification_exclusion")]
    excluded = [row for row in candidates if row.get("prequalification_exclusion")]

    passes = 0
    failures = 0
    unfinished = 0
    failure_counts: Counter[str] = Counter()
    rebuilt_ledger = []
    for candidate in active:
        slug = str(candidate["slug"])
        path = root / "screening/build_trace" / f"{safe_slug(slug)}.json"
        if not path.is_file():
            unfinished += 1
            rebuilt_ledger.append({
                "slug": slug, "commit": candidate["commit"],
                "status": "unfinished_counted_as_potential_success",
                "build_trace_gate": None, "first_failed_gate": None,
                "receipt_sha256": None,
            })
            continue
        receipt = read_json(path)
        if receipt.get("candidate") != backend_identity(candidate):
            raise ValueError(f"build candidate identity mismatch: {slug}")
        if receipt.get("scientific_candidate_tactics_executed") != 0:
            raise ValueError(f"nonzero scientific tactic count: {slug}")
        gate = receipt.get("build_trace_gate") is True
        failed_gate = receipt.get("first_failed_gate")
        if gate:
            passes += 1
            status = "completed_build_trace_pass"
            if failed_gate is not None:
                raise ValueError(f"pass has a failure gate: {slug}")
        else:
            failures += 1
            status = "completed_build_trace_failure"
            if not isinstance(failed_gate, str) or not failed_gate:
                raise ValueError(f"failure lacks failure gate: {slug}")
            failure_counts[failed_gate] += 1
        rebuilt_ledger.append({
            "slug": slug, "commit": candidate["commit"], "status": status,
            "build_trace_gate": gate, "first_failed_gate": failed_gate,
            "receipt_sha256": file_sha256(path),
        })

    ledger_path = root / "recruitment_shortfall/conservative_completion_ledger.jsonl"
    if read_jsonl(ledger_path) != rebuilt_ledger:
        raise ValueError("completion ledger differs from frozen frame and build receipts")
    summary_path = root / "recruitment_shortfall/summary.json"
    summary = read_json(summary_path)
    assert_sealed(summary, "recruitment shortfall summary")
    target = int(protocol["repository_sampling"]["take"])
    upper_bound = passes + unfinished
    checks = {
        "protocol_version": summary.get("protocol_version") == PROTOCOL_VERSION_60,
        "decision_label": summary.get("decision_label")
        == "conservative_upper_bound_recruitment_shortfall",
        "source_repositories": summary.get("source_repositories") == len(candidates),
        "prequalification_exclusions": summary.get("prequalification_exclusions") == len(excluded),
        "active_archival_candidates": summary.get("active_archival_candidates") == len(active),
        "completed_receipts": summary.get("completed_build_trace_receipts") == passes + failures,
        "observed_passes": summary.get("observed_build_trace_passes") == passes,
        "observed_failures": summary.get("observed_build_trace_failures") == failures,
        "unfinished": summary.get("unfinished_candidates") == unfinished,
        "target": summary.get("repository_target") == target,
        "upper_bound": summary.get("conservative_upper_bound") == upper_bound,
        "strict_shortfall": upper_bound < target,
        "unobserved_counted_as_success": summary.get(
            "unfinished_candidates_counted_as_successes_for_upper_bound"
        ) is True,
        "failure_counts": summary.get("failure_counts") == dict(sorted(failure_counts.items())),
        "protocol_sha256": summary.get("protocol_sha256")
        == file_sha256(root / "frozen/protocol.json"),
        "frame_receipt_sha256": summary.get("candidate_frame_receipt_sha256")
        == file_sha256(root / "frozen/candidate_frame_receipt.json"),
        "frame_sha256": summary.get("candidate_frame_sha256") == file_sha256(frame_path),
        "ledger_sha256": summary.get("completion_ledger_sha256") == file_sha256(ledger_path),
        "zero_authored_rows": not any((root / "screening/authored_rows").rglob("*.json")),
        "zero_scientific_receipts": not any((root / "scientific").rglob("*.json")),
        "zero_scientific_tactics": summary.get("scientific_candidate_tactics_executed") == 0,
        "not_a_scientific_result": summary.get("scientific_result") is False,
        "exp51_inconclusive_retained": summary.get(
            "historical_exp51_precision_inconclusive_retained"
        ) is True,
    }
    failed_checks = sorted(name for name, passed in checks.items() if not passed)
    if failed_checks:
        raise ValueError(f"recruitment-shortfall audit failed: {failed_checks}")
    result = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION_60,
        "audit_id": "experiment60-conservative-futility-audit-v1",
        "audit_passed": True,
        "checks": checks,
        "completed_build_trace_receipts": passes + failures,
        "observed_build_trace_passes": passes,
        "observed_build_trace_failures": failures,
        "unfinished_candidates": unfinished,
        "conservative_upper_bound": upper_bound,
        "repository_target": target,
        "summary_sha256": file_sha256(summary_path),
        "scientific_candidate_tactics_executed": 0,
    })
    atomic_json_dump(result, root / "recruitment_shortfall/audit.json")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(audit(Path(parse_args().artifact_root).resolve()), indent=2, sort_keys=True))
