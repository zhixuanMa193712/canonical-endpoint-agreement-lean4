"""Freeze the complete Exp60 archival frame and regenerate every exclusion."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiment60_protocol import *


REQUIRED = {
    "slug", "url", "commit", "snapshot_source", "snapshot_record_sha256",
    "source_exp56_snapshot_record_sha256", "source_exp56_head_commit",
    "archival_selection_method", "lean_toolchain_observed",
    "prequalification_exclusion",
}


def run(input_path: Path, root: Path) -> dict[str, Any]:
    protocol_path = root / "frozen/protocol.json"
    protocol = read_json(protocol_path); assert_sealed(protocol, "Exp60 protocol")
    validate_implementation_locks(protocol)
    collector = protocol["archival_collector"]
    if file_sha256(Path(collector["path"])) != collector["sha256"]:
        raise ValueError("Exp60 archival collector changed after protocol freeze")
    summary_path = root / "recruitment_snapshot/summary.json"
    summary = read_json(summary_path); assert_sealed(summary, "Exp60 archival snapshot")
    if file_sha256(input_path) != summary["candidate_frame_input_sha256"]:
        raise ValueError("Exp60 candidate-frame input changed after snapshot")
    rows = read_jsonl(input_path)
    if len(rows) != protocol["source_universe"]["records"]:
        raise ValueError("Exp60 candidate frame is incomplete")
    if len({str(row.get("slug")).lower() for row in rows}) != len(rows):
        raise ValueError("Exp60 candidate frame has duplicate repository slugs")
    historical = {value.lower() for value in HISTORICAL_SCIENTIFIC_REPOSITORIES}
    eligible = 0
    for row in rows:
        if not REQUIRED.issubset(row):
            raise ValueError(f"candidate row lacks frozen archival provenance: {row}")
        if len(str(row["commit"])) != 40 or len(str(row["snapshot_record_sha256"])) != 64:
            raise ValueError(f"candidate identity is not fully pinned: {row['slug']}")
        observed_hash = json_sha256({key: value for key, value in row.items()
                                     if key != "snapshot_record_sha256"})
        if observed_hash != row["snapshot_record_sha256"]:
            raise ValueError(f"candidate snapshot record changed: {row['slug']}")
        if str(row["slug"]).lower() in historical:
            expected = "historical_scientific_repository"
        elif row["lean_toolchain_observed"] != TARGET_TOOLCHAIN:
            expected = "no_exact_v427_commit_in_frozen_archival_surface"
        else:
            expected = None
            eligible += 1
            if row["archival_selection_method"] not in {
                "frozen_head", "atom_feed", "exact_version_tag",
            }:
                raise ValueError(f"eligible row lacks a frozen archival method: {row['slug']}")
        if row["prequalification_exclusion"] != expected:
            raise ValueError(f"candidate prequalification changed: {row['slug']}")
    if eligible != summary["exact_v427_nonhistorical_candidates"]:
        raise ValueError("eligible-candidate count changed after archival snapshot")
    ordered = sorted(rows, key=lambda row: (str(row["slug"]).lower(), str(row["commit"])))
    frame_path = root / "frozen/candidate_frame.jsonl"
    atomic_jsonl_dump(ordered, frame_path)
    value = seal({
        "version": 1, "protocol_version": PROTOCOL_VERSION_60,
        "freezer_id": "experiment60-archival-frame-freezer-v1",
        "candidate_count": len(ordered),
        "exact_v427_nonhistorical_candidates": eligible,
        "input_path": str(input_path.resolve()), "input_sha256": file_sha256(input_path),
        "snapshot_summary_sha256": file_sha256(summary_path),
        "frozen_frame": str(frame_path), "frozen_frame_sha256": file_sha256(frame_path),
        "all_commits_full_length": True,
        "all_snapshot_records_hashed": True,
        "all_archival_prequalification_exclusions_regenerated": True,
        "selection_outcomes_observed": False,
        "scientific_candidate_tactics_executed": 0,
        "next_step": "Qualify all 1,089 records; only 88 may enter build/trace.",
    })
    atomic_json_dump(value, root / "frozen/candidate_frame_receipt.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT_60))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run(Path(args.input), Path(args.artifact_root).resolve()), indent=2))
