"""Freeze the token-free collection transport before candidate discovery.

This amendment changes only how public GitHub metadata are transported.  It
does not change the frozen queries, repository or root sample sizes,
eligibility rules, candidate panel, analysis, gates, or stopping rule.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiment56_protocol import *


COLLECTOR = PACKAGE_ROOT / "snapshot_github_frame_public.py"


def freeze(root: Path) -> dict[str, Any]:
    protocol = read_json(root / "frozen/protocol.json")
    assert_sealed(protocol, "prospective protocol")
    validate_implementation_locks(protocol)
    forbidden = [
        root / "recruitment_snapshot/candidate_frame_input.jsonl",
        root / "frozen/candidate_frame.jsonl",
        root / "frozen/selection_receipt.json",
        root / "scientific",
        root / "analysis/summary.json",
    ]
    if any(path.exists() for path in forbidden):
        raise ValueError("collection amendment must precede candidate or scientific data")
    if not COLLECTOR.is_file():
        raise FileNotFoundError(COLLECTOR)
    value = seal({
        "version": 1,
        "protocol_version": PROTOCOL_VERSION,
        "amendment_id": "experiment56-public-collection-transport-v1",
        "amendment_scope": "metadata retrieval transport only",
        "reason": "no GitHub token is present; public endpoints and Git smart-HTTP suffice",
        "base_protocol_path": str(root / "frozen/protocol.json"),
        "base_protocol_sha256": file_sha256(root / "frozen/protocol.json"),
        "base_protocol_record_sha256": protocol["record_sha256"],
        "collector_path": str(COLLECTOR),
        "collector_sha256": file_sha256(COLLECTOR),
        "collector_bytes": COLLECTOR.stat().st_size,
        "frozen_queries_exact": list(FROZEN_GITHUB_QUERIES),
        "search_pages_per_query": 3,
        "repositories_required_unchanged": REPOSITORIES_REQUIRED,
        "roots_per_repository_unchanged": ROOTS_PER_REPOSITORY,
        "eligibility_contract_unchanged": protocol["eligible_repository_contract"],
        "registered_analysis_unchanged": protocol["registered_analysis"],
        "scientific_candidate_tactics_executed": 0,
        "candidate_records_observed_before_amendment": 0,
        "scientific_rules_changed": False,
        "stopping_rule_changed": False,
    })
    atomic_json_dump(value, root / "frozen/public_collection_amendment.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(freeze(Path(parse_args().artifact_root).resolve()), indent=2))
