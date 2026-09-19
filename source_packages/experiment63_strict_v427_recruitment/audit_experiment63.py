"""Audit Exp63 recruitment integrity, resource compliance, and arithmetic."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiment63_protocol import *


def run(root: Path) -> dict[str, Any]:
    protocol = read_json(root / "frozen/protocol.json")
    frame_receipt = read_json(root / "frozen/candidate_frame_receipt.json")
    progress = read_json(root / "qualification/progress.json")
    for label, value in (("protocol", protocol), ("frame", frame_receipt), ("progress", progress)):
        assert_sealed(value, f"Exp63 {label}")
    validate_locks(protocol)
    framep = root / "frozen/candidate_frame.jsonl"
    frame = read_jsonl(framep)
    checks: dict[str, bool] = {
        "frame_hash": frame_receipt["candidate_frame_sha256"] == file_sha256(framep),
        "frame_count": frame_receipt["candidate_count"] == len(frame),
        "strict_toolchain": all(row["strict_v427_eligibility"]["exact_root_toolchain"] == TARGET_TOOLCHAIN for row in frame),
        "current_commit": all(row["strict_v427_eligibility"]["current_default_branch_commit"] is True for row in frame),
        "static_minimum": all(int(row["static_tactic_roots"]) >= MIN_STATIC_TACTIC_ROOTS for row in frame),
        "unique_slug_commit": len({(row["slug"].lower(), row["commit"]) for row in frame}) == len(frame),
        "target_arithmetic": progress["conservative_upper_bound"] == (
            progress["lineage_representatives"] + progress["operationally_unresolved"] + progress["remaining_candidates"]),
        "receipt_partition": progress["completed_repositories"] == (
            progress["qualified_repositories"] + progress["definitive_ineligible"] + progress["operationally_unresolved"]),
        "target_flag": progress["target_reached"] == (progress["lineage_representatives"] >= TARGET_REPOSITORIES),
        "zero_scientific_tactics": protocol["scientific_candidate_tactics_executed"] == 0
                                  and progress["scientific_candidate_tactics_executed"] == 0,
    }
    resource_violations = []
    counted = {row["slug"] for row in frame}
    for path in sorted((root / "qualification/repositories").glob("*.json")):
        receipt = read_json(path); assert_sealed(receipt, path.name)
        slug = receipt["candidate"]["slug"]
        if slug not in counted:
            resource_violations.append({"slug": slug, "reason": "outside_frozen_frame"})
        if receipt.get("scientific_candidate_tactics_executed") != 0:
            resource_violations.append({"slug": slug, "reason": "nonzero_scientific_tactics"})
        disk = receipt.get("disk", {})
        if receipt.get("qualification_gate") is True and disk.get("maximum_observed_physical_growth_bytes", 0) > PER_REPOSITORY_DISK_LIMIT_BYTES:
            resource_violations.append({"slug": slug, "reason": "qualified_above_disk_limit"})
        if receipt.get("checkout_cleanup", {}).get("removed") is not True:
            resource_violations.append({"slug": slug, "reason": "checkout_not_cleaned"})
    checks["resource_contract"] = not resource_violations
    checks["receipt_count"] = progress["completed_repositories"] == len(list((root / "qualification/repositories").glob("*.json")))
    audit_passed = all(checks.values())
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "audit_passed": audit_passed, "checks": checks,
        "resource_violations": resource_violations,
        "frozen_candidates": len(frame), "completed_repositories": progress["completed_repositories"],
        "lineage_representatives": progress["lineage_representatives"],
        "repository_target": TARGET_REPOSITORIES, "target_reached": progress["target_reached"],
        "futility_reached": progress["futility_reached"],
        "scientific_candidate_tactics_executed": 0,
    })
    atomic_json_dump(value, root / "audit/audit.json")
    if not audit_passed:
        raise ValueError(json.dumps(checks, sort_keys=True))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(Path(parse_args().artifact_root).resolve()), indent=2))
