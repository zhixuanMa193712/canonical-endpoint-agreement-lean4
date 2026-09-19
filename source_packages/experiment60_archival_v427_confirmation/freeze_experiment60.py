"""Freeze the archival-v4.27 frame and inherited scientific design."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiment60_protocol import *


COLLECTOR = PACKAGE_ROOT_60 / "snapshot_archival_v427_frame.py"


def freeze(root: Path) -> dict[str, Any]:
    for path in (SOURCE_EXP56_FRAME, SOURCE_EXP56_FRAME_RECEIPT,
                 SOURCE_EXP56_SHORTFALL, BASE_EXP56_PROTOCOL, COLLECTOR):
        if not path.is_file():
            raise FileNotFoundError(path)
    base = read_json(BASE_EXP56_PROTOCOL); assert_sealed(base, "Exp56 protocol")
    frame_receipt = read_json(SOURCE_EXP56_FRAME_RECEIPT)
    assert_sealed(frame_receipt, "Exp56 candidate frame")
    shortfall = read_json(SOURCE_EXP56_SHORTFALL)
    assert_sealed(shortfall, "Exp56 recruitment shortfall")
    if shortfall.get("decision_label") != "prequalification_recruitment_shortfall":
        raise ValueError("Exp60 requires the sealed Exp56 prequalification shortfall")
    if file_sha256(SOURCE_EXP56_FRAME) != frame_receipt["frozen_frame_sha256"]:
        raise ValueError("Exp56 source frame changed")
    if (root / "recruitment_snapshot/candidate_frame_input.jsonl").exists():
        raise FileExistsError("Exp60 archival discovery has already started")
    value = seal({
        "version": 1,
        "protocol_version": PROTOCOL_VERSION_60,
        "purpose": (
            "prospective precision confirmation over repositories in the frozen Exp56 "
            "GitHub universe that expose an exact archival Lean v4.27.0 root toolchain"
        ),
        "trigger": {
            "exp56_shortfall_sha256": file_sha256(SOURCE_EXP56_SHORTFALL),
            "decision_label": shortfall["decision_label"],
            "head_frame_upper_bound": shortfall["build_trace_entry_upper_bound"],
            "scientific_candidate_tactics_executed": 0,
        },
        "source_universe": {
            "path": str(SOURCE_EXP56_FRAME),
            "sha256": file_sha256(SOURCE_EXP56_FRAME),
            "records": frame_receipt["candidate_count"],
            "receipt_path": str(SOURCE_EXP56_FRAME_RECEIPT),
            "receipt_sha256": file_sha256(SOURCE_EXP56_FRAME_RECEIPT),
            "selection": "all frozen records; no repository is added by hand",
        },
        "archival_discovery": {
            "priority": [
                "frozen default-branch HEAD",
                "up to 20 commits in the public root lean-toolchain Atom feed, newest first",
                "dereferenced exact-version tags in case-insensitive lexical order",
            ],
            "feed_max_entries": ARCHIVAL_FEED_MAX_ENTRIES,
            "exact_tag_pattern": ARCHIVAL_TAG_PATTERN,
            "required_toolchain_bytes": TARGET_TOOLCHAIN + "\\n",
            "one_commit_per_repository": True,
            "subdirectory_toolchains_excluded": True,
            "retrieval_failure_policy": "abort the complete snapshot; never silently drop a repository",
        },
        "historical_scientific_exclusions": sorted(HISTORICAL_SCIENTIFIC_REPOSITORIES,
                                                    key=str.lower),
        "eligible_repository_contract": base["eligible_repository_contract"],
        "repository_sampling": base["repository_sampling"],
        "root_sampling": base["root_sampling"],
        "measurement": base["measurement"],
        "registered_analysis": base["registered_analysis"],
        "historical_claim_policy": {
            "exp51_inconclusive_retained": True,
            "exp56_shortfall_retained": True,
            "new_result_reported_separately": True,
            "failure_or_shortfall_retained": True,
        },
        "source_locks": base["source_locks"],
        "implementation_locks": base["implementation_locks"],
        "archival_collector": {
            "path": str(COLLECTOR), "sha256": file_sha256(COLLECTOR),
            "bytes": COLLECTOR.stat().st_size,
        },
        "scientific_candidate_execution_before_freeze": False,
        "scientific_candidate_tactics_executed": 0,
        "stopping_rule": (
            "After the complete archival frame is frozen, stop if its exact-v4.27 "
            "prequalification upper bound is below 38; otherwise qualify every candidate "
            "and stop if fewer than 38 lineage representatives remain."
        ),
    })
    atomic_json_dump(value, root / "frozen/protocol.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT_60))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(freeze(Path(parse_args().artifact_root).resolve()), indent=2))

