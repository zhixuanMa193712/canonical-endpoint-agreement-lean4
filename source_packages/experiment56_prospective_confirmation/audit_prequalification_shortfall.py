"""Seal the deterministic Exp56 frame-level recruitment shortfall."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from experiment56_protocol import *


def run(root: Path) -> dict[str, Any]:
    protocol_path = root / "frozen/protocol.json"
    protocol = read_json(protocol_path); assert_sealed(protocol, "protocol")
    validate_implementation_locks(protocol)
    amendment_path = root / "frozen/public_collection_amendment.json"
    amendment = read_json(amendment_path); assert_sealed(amendment, "collection amendment")
    frame_receipt_path = root / "frozen/candidate_frame_receipt.json"
    frame_receipt = read_json(frame_receipt_path); assert_sealed(frame_receipt, "candidate frame")
    frame_path = root / "frozen/candidate_frame.jsonl"
    if file_sha256(frame_path) != frame_receipt["frozen_frame_sha256"]:
        raise ValueError("candidate frame changed")
    rows = read_jsonl(frame_path)
    if len(rows) != frame_receipt["candidate_count"]:
        raise ValueError("candidate-frame count changed")
    ledger = []
    for row in rows:
        expected_hash = json_sha256({key: value for key, value in row.items()
                                     if key != "snapshot_record_sha256"})
        if row.get("snapshot_record_sha256") != expected_hash:
            raise ValueError(f"candidate snapshot record changed: {row.get('slug')}")
        ledger.append({
            "slug": row["slug"], "commit": row["commit"],
            "lean_toolchain_observed": row["lean_toolchain_observed"],
            "prequalification_exclusion": row["prequalification_exclusion"],
            "can_enter_build_trace": row["prequalification_exclusion"] is None,
            "scientific_candidate_tactics_executed": 0,
        })
    ledger_path = root / "recruitment_shortfall/prequalification_ledger.jsonl"
    atomic_jsonl_dump(ledger, ledger_path)
    reasons = Counter(str(row["prequalification_exclusion"]) for row in rows
                      if row["prequalification_exclusion"] is not None)
    upper_bound = sum(row["prequalification_exclusion"] is None for row in rows)
    if upper_bound >= REPOSITORIES_REQUIRED:
        raise ValueError("frame does not have a deterministic prequalification shortfall")
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "decision_label": "prequalification_recruitment_shortfall",
        "candidate_repositories": len(rows),
        "repositories_required": REPOSITORIES_REQUIRED,
        "build_trace_entry_upper_bound": upper_bound,
        "lineage_representative_upper_bound": upper_bound,
        "shortfall": REPOSITORIES_REQUIRED - upper_bound,
        "prequalification_exclusion_counts": dict(sorted(reasons.items())),
        "prequalification_ledger": str(ledger_path),
        "prequalification_ledger_sha256": file_sha256(ledger_path),
        "candidate_frame_sha256": file_sha256(frame_path),
        "base_protocol_sha256": file_sha256(protocol_path),
        "collection_amendment_sha256": file_sha256(amendment_path),
        "candidate_frame_receipt_sha256": file_sha256(frame_receipt_path),
        "qualification_skipped": True,
        "qualification_skip_reason": (
            "Even perfect build, trace, authored replay, and lineage outcomes cannot raise "
            "the frozen frame above its 16-repository prequalification upper bound."
        ),
        "scientific_candidate_tactics_executed": 0,
        "historical_exp51_decision_overwritten": False,
        "historical_exp51_decision": "inconclusive retained unchanged",
        "next_step": (
            "Preserve this shortfall.  A separately frozen archival-v4.27 frame is "
            "required; do not lower the 38-repository target."
        ),
    })
    atomic_json_dump(value, root / "recruitment_shortfall/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(Path(parse_args().artifact_root).resolve()), indent=2))
