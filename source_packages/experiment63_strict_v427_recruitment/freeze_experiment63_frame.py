"""Freeze the strict v4.27 candidate frame before any qualification execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiment63_protocol import *


def run(root: Path) -> dict[str, Any]:
    outp = root / "frozen/candidate_frame.jsonl"
    receiptp = root / "frozen/candidate_frame_receipt.json"
    if outp.is_file() and receiptp.is_file():
        receipt = read_json(receiptp); assert_sealed(receipt, "Exp63 candidate frame")
        if receipt["candidate_frame_sha256"] != file_sha256(outp):
            raise ValueError("frozen candidate frame changed")
        return receipt
    protocol = read_json(root / "frozen/protocol.json")
    discovery = read_json(root / "discovery/summary.json")
    static = read_json(root / "static/summary.json")
    for label, value in (("protocol", protocol), ("discovery", discovery), ("static", static)):
        assert_sealed(value, f"Exp63 {label}")
    validate_locks(protocol)
    if discovery.get("complete_github_search") is not True:
        raise ValueError("GitHub discovery was not complete")
    candidates = read_jsonl(root / "static/strict_candidates_unfrozen.jsonl")
    candidates.sort(key=lambda row: selection_key(FRAME_ORDER_SEED, row["slug"], row["commit"]))
    frozen = []
    for index, row in enumerate(candidates, 1):
        frozen.append({
            **row, "frame_index": index,
            "frame_selection_key": selection_key(FRAME_ORDER_SEED, row["slug"], row["commit"]),
            "strict_v427_eligibility": {
                "current_default_branch_commit": True,
                "exact_root_toolchain": TARGET_TOOLCHAIN,
                "root_license": True, "root_lakefile": True,
                "minimum_static_tactic_roots": MIN_STATIC_TACTIC_ROOTS,
            },
            "scientific_candidate_tactics_executed": 0,
        })
    atomic_jsonl_dump(frozen, outp)
    receipt = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "candidate_count": len(frozen), "repository_target": TARGET_REPOSITORIES,
        "prequalification_upper_bound_reaches_target": len(frozen) >= TARGET_REPOSITORIES,
        "candidate_frame_sha256": file_sha256(outp),
        "discovery_summary_sha256": file_sha256(root / "discovery/summary.json"),
        "static_summary_sha256": file_sha256(root / "static/summary.json"),
        "qualification_receipts_at_freeze": len(list((root / "qualification/repositories").glob("*.json"))),
        "scientific_candidate_tactics_executed": 0,
        "next_step": "Run serial, disk-bounded qualification." if len(frozen) >= TARGET_REPOSITORIES
                     else "Stop: strict prequalification cannot reach the target.",
    })
    if receipt["qualification_receipts_at_freeze"] != 0:
        raise ValueError("qualification started before candidate-frame freeze")
    atomic_json_dump(receipt, receiptp)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(Path(parse_args().artifact_root).resolve()), indent=2))
