"""Freeze Exp63's corrected recruitment-only protocol before new qualification."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from experiment63_protocol import *


def backend_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": row["slug"], "url": row["url"], "ref": row["commit"],
        "commit": row["commit"], "domain": row.get("domain", "unclassified"),
        "subdir": row.get("subdir", "."),
        "snapshot_source": row["snapshot_source"],
        "snapshot_record_sha256": row["snapshot_record_sha256"],
    }


def load_exp61(root61: Path) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    framep = root61 / "frozen/candidate_frame.jsonl"
    summaryp = root61 / "recruitment_shortfall/summary.json"
    auditp = root61 / "recruitment_shortfall/audit.json"
    for path in (framep, summaryp, auditp):
        if not path.is_file():
            raise FileNotFoundError(path)
    summary, audit = read_json(summaryp), read_json(auditp)
    assert_sealed(summary, "Exp61 shortfall summary")
    assert_sealed(audit, "Exp61 shortfall audit")
    if audit.get("audit_passed") is not True:
        raise ValueError("Exp61 audit did not pass")
    if summary.get("scientific_candidate_tactics_executed") != 0:
        raise ValueError("Exp61 executed scientific candidate tactics")
    frame = [row for row in read_jsonl(framep) if not row.get("prequalification_exclusion")]
    if len(frame) != 88:
        raise ValueError(f"expected 88 active Exp61 candidates, found {len(frame)}")
    return frame, summary, audit


def run(root: Path, root61: Path) -> dict[str, Any]:
    protocolp = root / "frozen/protocol.json"
    if protocolp.is_file():
        value = read_json(protocolp)
        assert_sealed(value, "Exp63 protocol")
        validate_locks(value)
        return read_json(root / "frozen/recovery_freeze_receipt.json")

    candidates, summary61, audit61 = load_exp61(root61)
    ledger: list[dict[str, Any]] = []
    recovery: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    for candidate in candidates:
        receiptp = root61 / "screening/build_trace" / f"{safe_slug(candidate['slug'])}.json"
        receipt = read_json(receiptp) if receiptp.is_file() else None
        if receipt is not None and receipt.get("candidate") != backend_identity(candidate):
            raise ValueError(f"Exp61 candidate identity changed: {candidate['slug']}")
        status, reason = classify_build_trace_receipt(receipt)
        counts[status] += 1
        reason_counts[reason] += 1
        source_sha = file_sha256(receiptp) if receiptp.is_file() else None
        row = {
            "slug": candidate["slug"], "commit": candidate["commit"],
            "exp61_reported_gate": None if receipt is None else receipt.get("first_failed_gate"),
            "exp63_reclassification": status, "exp63_reason": reason,
            "source_receipt_sha256": source_sha,
            "scientific_candidate_tactics_executed": 0,
        }
        ledger.append(row)
        if status != "definitive_ineligible":
            recovery.append({
                **candidate, "exp61_reclassification": status,
                "exp63_recovery_reason": reason,
                "source_exp61_receipt_sha256": source_sha,
            })

    corrected_upper = counts["build_trace_pass"] + counts["operationally_unresolved"]
    if corrected_upper < int(summary61["conservative_upper_bound"]):
        raise ValueError("corrected adjudication cannot reduce Exp61's reported upper bound")
    protocol = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "purpose": "Strictly recruit current v4.27 repositories without scientific candidate tactics.",
        "source_exp61_root": str(root61),
        "source_exp61_summary_sha256": file_sha256(root61 / "recruitment_shortfall/summary.json"),
        "source_exp61_audit_sha256": file_sha256(root61 / "recruitment_shortfall/audit.json"),
        "adjudication": {
            "exp61_reported_upper_bound": summary61["conservative_upper_bound"],
            "exp61_reported_passes": summary61["definitive_build_trace_passes"],
            "exp61_reported_failures": summary61["definitive_build_trace_failures"],
            "exp61_reported_unresolved": summary61["operationally_unresolved_candidates"],
            "corrected_conservative_upper_bound": corrected_upper,
            "corrected_status_counts": dict(sorted(counts.items())),
            "corrected_reason_counts": dict(sorted(reason_counts.items())),
            "principle": "Infrastructure and parser failures are unresolved, never scientific ineligibility.",
        },
        "strict_recruitment_contract": {
            "complete_github_search_by_date_partition": True,
            "current_default_branch_commit_only": True,
            "exact_root_toolchain": TARGET_TOOLCHAIN,
            "public_nonfork_nonarchived": True,
            "root_license_required": True,
            "root_lakefile_required": True,
            "source_static_tactic_root_lower_bound": MIN_STATIC_TACTIC_ROOTS,
            "full_build_trace_authored_replay_before_acceptance": True,
            "minimum_trace_and_replay_roots": MIN_TRACE_ROOTS,
            "historical_scientific_repository_exclusion": sorted(HISTORICAL_SCIENTIFIC_REPOSITORIES),
            "candidate_frame_frozen_before_qualification": True,
            "scientific_candidate_tactics_permitted": 0,
        },
        "resource_contract": {
            "qualification_repositories_in_parallel": 1,
            "global_free_disk_floor_bytes": GLOBAL_FREE_DISK_FLOOR_BYTES,
            "per_repository_disk_limit_bytes": PER_REPOSITORY_DISK_LIMIT_BYTES,
            "static_checkout_limit_bytes": STATIC_CHECKOUT_LIMIT_BYTES,
            "lean_prefix_materialization": "hardlink-first-with-copy-fallback",
            "cleanup_after_every_repository": True,
            "single_repository_exceeding_limit_is_ineligible_for_this_protocol": True,
            "wait_for_experiment62_before_heavy_qualification": True,
        },
        "repository_target": TARGET_REPOSITORIES,
        "source_overlap_threshold": SOURCE_OVERLAP_THRESHOLD,
        "implementation_locks": implementation_locks(),
        "source_locks": source_locks(),
        "scientific_candidate_tactics_executed": 0,
    })
    atomic_json_dump(protocol, protocolp)
    atomic_jsonl_dump(ledger, root / "frozen/exp61_reclassification_ledger.jsonl")
    atomic_jsonl_dump(recovery, root / "frozen/exp61_recovery_candidates.jsonl")
    receipt = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "exp61_active_candidates": len(candidates),
        "recovery_candidates": len(recovery),
        "corrected_conservative_upper_bound": corrected_upper,
        "status_counts": dict(sorted(counts.items())),
        "reclassification_ledger_sha256": file_sha256(root / "frozen/exp61_reclassification_ledger.jsonl"),
        "recovery_candidates_sha256": file_sha256(root / "frozen/exp61_recovery_candidates.jsonl"),
        "protocol_sha256": file_sha256(protocolp),
        "scientific_candidate_tactics_executed": 0,
    })
    atomic_json_dump(receipt, root / "frozen/recovery_freeze_receipt.json")
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--source-exp61-root", default=str(SOURCE61_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run(Path(args.artifact_root).resolve(), Path(args.source_exp61_root).resolve()), indent=2))
