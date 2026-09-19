"""Finalize Exp59 candidate recruitment and freeze eligible pilot roots."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from experiment59_protocol import *
from run_experiment59_candidate_screening import valid_operational_receipt, valid_retained_failure


def run(root: Path) -> dict[str, Any]:
    protocol = load_protocol(root)
    panel = tuple(protocol["candidate_panel"])
    frame_path = Path(protocol["source_frame"]["frame"])
    if file_sha256(frame_path) != protocol["source_frame"]["frame_sha256"]:
        raise ValueError("Exp59 candidate frame changed")
    frame = read_jsonl(frame_path)
    if len(frame) != EXPECTED_UNUSED_SOURCE_TARGETS:
        raise ValueError("Exp59 frame is incomplete")
    shard_rows = []
    for index in range(SHARD_COUNT):
        path = root / f"screening/shards/shard-{index:02d}.json"
        row = read_json(path)
        assert_sealed(row, f"Exp59 shard {index:02d}")
        if row.get("shard_index") != index or row.get("shard_count") != SHARD_COUNT:
            raise ValueError("Exp59 shard identity changed")
        shard_rows.append(row)
    if not all(row.get("shard_gate") is True for row in shard_rows):
        raise ValueError("an Exp59 shard failed its frozen accounting gate")
    if sum(int(row.get("targets_expected", -1)) for row in shard_rows) != len(frame):
        raise ValueError("Exp59 shard target accounting is incomplete")
    if sum(int(row.get("receipts", -1)) for row in shard_rows) != len(frame):
        raise ValueError("Exp59 shard receipt accounting is incomplete")

    receipts = []
    ledger = []
    failure_counts = Counter()
    for target in frame:
        path = root / "screening/candidate_receipts" / f"{target['target_id']}.json"
        row = read_json(path)
        assert_sealed(row, f"Exp59 receipt {target['target_id']}")
        if row.get("target_identity") != target:
            raise ValueError(f"Exp59 target identity changed: {target['target_id']}")
        operational = valid_operational_receipt(row, len(panel))
        retained_failure = valid_retained_failure(row)
        if tuple(row.get("candidate_panel", [])) != panel or not (operational or retained_failure):
            raise ValueError(f"Exp59 receipt failed accounting: {target['target_id']}")
        if row.get("continuation_probes_executed") != 0 or row.get("scientific_retry_count") != 0:
            raise ValueError("Exp59 candidate screen contains a probe or retry")
        eligible = row.get("eligibility_gate") is True
        if eligible and not operational:
            raise ValueError("an operational failure was labeled eligible")
        if operational and eligible != (row.get("first_failed_gate") is None):
            raise ValueError("Exp59 eligibility and first-failed-gate labels disagree")
        reason = "eligible" if eligible else str(row.get("first_failed_gate"))
        failure_counts[reason] += 1
        receipts.append(row)
        ledger.append({
            "dataset": target["dataset"],
            "role": target["role"],
            "target_id": target["target_id"],
            "theorem_name": target["theorem_name"],
            "source_partition_role": target["source_partition_role"],
            "prospective_role_assignment_key": target["prospective_role_assignment_key"],
            "prospective_rank_within_dataset": target["prospective_rank_within_dataset"],
            "candidate_receipt": str(path),
            "candidate_receipt_sha256": file_sha256(path),
            "eligible": eligible,
            "exclusion_reason": None if eligible else row.get("first_failed_gate"),
            "pilot_selection_key": selection_key(PILOT_SELECTION_SEED, target["dataset"], target["target_id"]),
            "confirmation_selection_key": selection_key(
                CONFIRMATION_SELECTION_SEED, target["dataset"], target["target_id"]
            ),
        })

    selected = []
    counts: dict[str, dict[str, int]] = {}
    for dataset in sorted(protocol["datasets"]):
        pilot_pool = sorted(
            [row for row in ledger if row["dataset"] == dataset and row["role"] == "pilot" and row["eligible"]],
            key=lambda row: row["pilot_selection_key"],
        )
        confirmation_pool = [
            row for row in ledger
            if row["dataset"] == dataset and row["role"] == "confirmation" and row["eligible"]
        ]
        counts[dataset] = {
            "pilot_eligible": len(pilot_pool),
            "confirmation_eligible": len(confirmation_pool),
            "pilot_required": MIN_PILOT_ELIGIBLE_PER_DATASET,
            "confirmation_required": MIN_CONFIRMATION_POOL_PER_DATASET,
        }
        selected.extend(pilot_pool[:PILOT_ROOTS_PER_DATASET])
    gate = bool(
        len(receipts) == EXPECTED_UNUSED_SOURCE_TARGETS
        and len(selected) == 2 * PILOT_ROOTS_PER_DATASET
        and all(item["pilot_eligible"] >= item["pilot_required"] for item in counts.values())
        and all(item["confirmation_eligible"] >= item["confirmation_required"] for item in counts.values())
        and all(row.get("continuation_probes_executed") == 0 for row in receipts)
        and all(row.get("scientific_retry_count") == 0 for row in receipts)
    )
    ledger_path = root / "screening/eligibility_ledger.jsonl"
    pilot_path = root / "pilot/frozen/selected_roots.jsonl"
    atomic_jsonl_dump(ledger, ledger_path)
    atomic_jsonl_dump(selected, pilot_path)
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "screening_roots": len(receipts),
        "expected_screening_roots": EXPECTED_UNUSED_SOURCE_TARGETS,
        "operational_roots": sum(row.get("worker_ok") is True for row in receipts),
        "operational_failures_retained": sum(row.get("worker_ok") is False for row in receipts),
        "candidate_only_tactics_executed": sum(
            int(row.get("candidate_only_tactics_executed", 0)) for row in receipts
        ),
        "continuation_probes_executed": 0,
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
        "eligibility_counts": counts,
        "failure_counts": dict(sorted(failure_counts.items())),
        "eligibility_ledger": str(ledger_path),
        "eligibility_ledger_sha256": file_sha256(ledger_path),
        "pilot_roots": len(selected),
        "pilot_roots_path": str(pilot_path),
        "pilot_roots_sha256": file_sha256(pilot_path),
        "screening_gate": gate,
        "next_step": (
            "Freeze the four-policy pilot jobs before any continuation probe."
            if gate else "STOP: preserve the prospective recruitment No-Go; do not lower quotas."
        ),
    })
    atomic_json_dump(value, root / "screening/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(Path(parse_args().artifact_root).resolve()), indent=2))
