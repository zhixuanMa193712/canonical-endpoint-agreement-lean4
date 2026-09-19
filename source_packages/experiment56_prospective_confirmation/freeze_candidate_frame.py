"""Freeze a complete externally collected repository frame and every exclusion.

Input is JSONL with one row per candidate.  Required fields are ``slug``,
``url``, ``commit``, ``snapshot_source``, and ``snapshot_record_sha256``.  The
collector may be GitHub, Reservoir, or a deposited static catalogue; this step
is deliberately source-agnostic but refuses an unsealed or duplicate frame.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiment56_protocol import *


REQUIRED = {
    "slug", "url", "commit", "snapshot_source", "snapshot_record_sha256",
    "lean_toolchain_observed", "prequalification_exclusion",
}


def run(input_path: Path, root: Path) -> dict:
    protocol = read_json(root / "frozen/protocol.json")
    assert_sealed(protocol, "prospective protocol")
    validate_implementation_locks(protocol)
    rows = read_jsonl(input_path)
    if not rows:
        raise ValueError("candidate frame is empty")
    if len({row.get("slug") for row in rows}) != len(rows):
        raise ValueError("candidate frame has duplicate repository slugs")
    for row in rows:
        if not REQUIRED.issubset(row):
            raise ValueError(f"candidate row lacks frozen provenance: {row}")
        if len(str(row["commit"])) != 40 or len(str(row["snapshot_record_sha256"])) != 64:
            raise ValueError(f"candidate identity is not fully pinned: {row['slug']}")
        observed_record_hash = json_sha256({
            key: value for key, value in row.items() if key != "snapshot_record_sha256"
        })
        if observed_record_hash != row["snapshot_record_sha256"]:
            raise ValueError(f"candidate snapshot hash changed: {row['slug']}")
        historical = str(row["slug"]).lower() in {
            value.lower() for value in HISTORICAL_SCIENTIFIC_REPOSITORIES
        }
        expected_exclusion = (
            "historical_scientific_repository" if historical
            else "missing_or_non_v427_root_toolchain"
            if row["lean_toolchain_observed"] != TARGET_TOOLCHAIN
            else None
        )
        if row["prequalification_exclusion"] != expected_exclusion:
            raise ValueError(f"candidate prequalification changed: {row['slug']}")
    ordered = sorted(rows, key=lambda row: (str(row["slug"]), str(row["commit"])))
    frame_path = root / "frozen/candidate_frame.jsonl"
    atomic_jsonl_dump(ordered, frame_path)
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "candidate_count": len(ordered),
        "input_path": str(input_path.resolve()),
        "input_sha256": file_sha256(input_path),
        "frozen_frame": str(frame_path),
        "frozen_frame_sha256": file_sha256(frame_path),
        "all_commits_full_length": True,
        "all_snapshot_records_hashed": True,
        "all_prequalification_exclusions_regenerated": True,
        "scientific_candidate_tactics_executed": 0,
        "next_step": "Qualify every candidate and preserve a receipt for every pass or exclusion.",
    })
    atomic_json_dump(value, root / "frozen/candidate_frame_receipt.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run(Path(args.input), Path(args.artifact_root).resolve()), indent=2))
