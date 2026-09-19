"""Freeze deterministic repository and root selections from qualification receipts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from experiment56_protocol import *


sys.path.insert(0, str(WORKSPACE_ROOT / "experiment51_external_repository_replication"))
from experiment51_protocol import expected_alternatives, select_candidate_view  # type: ignore


def run(root: Path) -> dict:
    protocol = read_json(root / "frozen/protocol.json")
    assert_sealed(protocol, "prospective protocol")
    validate_implementation_locks(protocol)
    frame_receipt = read_json(root / "frozen/candidate_frame_receipt.json")
    assert_sealed(frame_receipt, "candidate frame")
    candidates = read_jsonl(root / "frozen/candidate_frame.jsonl")
    qualification_dir = root / "qualification/repositories"
    receipts = []
    for candidate in candidates:
        path = qualification_dir / f"{candidate['slug'].replace('/', '__')}.json"
        if not path.is_file():
            raise FileNotFoundError(f"missing qualification receipt: {path}")
        row = read_json(path)
        assert_sealed(row, f"qualification {candidate['slug']}")
        if row.get("candidate") != candidate:
            raise ValueError(f"qualification identity changed: {candidate['slug']}")
        receipts.append(row)
    eligible = [row for row in receipts if row.get("qualification_gate") is True]
    representatives = [row for row in eligible if row.get("lineage_representative") is True]
    ranked = sorted(representatives, key=lambda row: selection_key(
        MASTER_REPOSITORY_SEED, row["candidate"]["slug"], row["candidate"]["commit"]
    ))
    selected = ranked[:REPOSITORIES_REQUIRED]
    representative_rank = {
        (row["candidate"]["slug"], row["candidate"]["commit"]): rank
        for rank, row in enumerate(ranked, 1)
    }
    repository_ledger = []
    root_ledger = []
    selected_roots = []
    for row in receipts:
        candidate = row["candidate"]
        key = selection_key(MASTER_REPOSITORY_SEED, candidate["slug"], candidate["commit"])
        repository_ledger.append({
            "slug": candidate["slug"], "commit": candidate["commit"],
            "eligible": row.get("qualification_gate") is True,
            "lineage_representative": row.get("lineage_representative") is True,
            "exclusion_reason": row.get("first_failed_gate"),
            "selection_key": key,
            "selection_rank": representative_rank.get((candidate["slug"], candidate["commit"])),
            "selected": row in selected,
            "qualification_receipt_sha256": file_sha256(
                qualification_dir / f"{candidate['slug'].replace('/', '__')}.json"
            ),
        })
    for repository_rank, row in enumerate(ranked, 1):
        candidate = row["candidate"]
        frame_path = Path(row["eligible_root_frame"])
        if not frame_path.is_file() or file_sha256(frame_path) != row["eligible_root_frame_sha256"]:
            raise ValueError(f"eligible root frame changed: {candidate['slug']}")
        roots = read_jsonl(frame_path)
        for target in roots:
            target["selection_key"] = selection_key(
                MASTER_ROOT_SEED, candidate["slug"], candidate["commit"],
                target["source_file_sha256"], target["full_name"],
                target["target_pos"], target["target_end_pos"],
            )
        roots.sort(key=lambda target: target["selection_key"])
        repository_selected = repository_rank <= REPOSITORIES_REQUIRED
        for root_rank, target in enumerate(roots, 1):
            root_selected = repository_selected and root_rank <= ROOTS_PER_REPOSITORY
            exclusion_reason = None
            if not repository_selected:
                exclusion_reason = "repository_selection_rank_gt_38"
            elif root_rank > ROOTS_PER_REPOSITORY:
                exclusion_reason = "root_selection_rank_gt_16"
            root_ledger.append({
                "slug": candidate["slug"], "commit": candidate["commit"],
                "theorem_id": target["theorem_id"], "rid": target["rid"],
                "file_path": target["file_path"], "full_name": target["full_name"],
                "source_file_sha256": target["source_file_sha256"],
                "ast_sha256": target["ast_sha256"],
                "authored_row_sha256": target["authored_row_sha256"],
                "selection_key": target["selection_key"],
                "repository_selection_rank": repository_rank,
                "root_selection_rank": root_rank,
                "selected": root_selected, "exclusion_reason": exclusion_reason,
            })
            if root_selected:
                alternatives = expected_alternatives(target["authored_tactic"])
                if len(alternatives) != CANDIDATES_PER_ROOT:
                    raise ValueError("frozen candidate panel no longer has 23 entries")
                selected_roots.append({
                    **target,
                    "repository_selection_rank": repository_rank,
                    "root_selection_rank": root_rank,
                    "alternatives": alternatives,
                    "alternatives_sha256": json_sha256(alternatives),
                    "robust_alternatives": select_candidate_view(
                        alternatives, "L-mechanism-diverse"
                    ),
                })
    ledger_path = root / "frozen/repository_eligibility_ledger.jsonl"
    root_ledger_path = root / "frozen/root_eligibility_ledger.jsonl"
    roots_path = root / "frozen/selected_roots.jsonl"
    atomic_jsonl_dump(repository_ledger, ledger_path)
    atomic_jsonl_dump(root_ledger, root_ledger_path)
    atomic_jsonl_dump(selected_roots, roots_path)
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "candidate_repositories": len(receipts),
        "eligible_repositories": len(eligible),
        "lineage_representatives": len(representatives),
        "selected_repositories": len(selected),
        "selected_roots": len(selected_roots),
        "repository_eligibility_ledger": str(ledger_path),
        "repository_eligibility_ledger_sha256": file_sha256(ledger_path),
        "root_eligibility_records": len(root_ledger),
        "root_eligibility_ledger": str(root_ledger_path),
        "root_eligibility_ledger_sha256": file_sha256(root_ledger_path),
        "selected_roots_path": str(roots_path),
        "selected_roots_sha256": file_sha256(roots_path),
        "selection_gate": len(selected) == REPOSITORIES_REQUIRED and len(selected_roots) == TOTAL_ROOTS,
        "scientific_candidate_tactics_executed": 0,
        "next_step": "Compile-preflight the locked live worker, then execute the frozen scientific shards.",
    })
    if not value["selection_gate"]:
        value["next_step"] = "STOP: fewer than 38 independent eligible repositories or incomplete root frames."
    atomic_json_dump(value, root / "frozen/selection_receipt.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(Path(parse_args().artifact_root).resolve()), indent=2))
