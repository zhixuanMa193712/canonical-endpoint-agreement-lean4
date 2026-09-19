"""Finalize candidate-only eligibility and freeze the disjoint pilot roots."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from experiment58_protocol import *


def run(root: Path) -> dict[str, Any]:
    load_protocol(root)
    frame_receipt = read_json(root / "frozen/source_frame_receipt.json")
    assert_sealed(frame_receipt, "source frame")
    frame = read_jsonl(frame_receipt["candidate_screening_frame"])
    execution_root = root / CANDIDATE_SCREENING_EXECUTION_ROOT
    receipts = []
    ledger = []
    for target in frame:
        path = execution_root / "candidate_receipts" / f"{target['target_id']}.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        row = read_json(path)
        assert_sealed(row, f"candidate receipt {target['target_id']}")
        if row.get("target_identity") != target:
            raise ValueError(f"target identity changed: {target['target_id']}")
        if not (
            row.get("worker_ok") is True
            and row.get("candidate_accounting_exact") is True
            and row.get("same_pre_state_all_branches") is True
            and row.get("candidate_only_tactics_executed") == CANDIDATES_PER_ROOT
            and row.get("continuation_probes_executed") == 0
            and row.get("staged_source_content_exact") is True
            and row.get("staged_measurement_source_sha256") == target["measurement_source_sha256"]
        ):
            raise ValueError(f"candidate receipt failed operational gate: {target['target_id']}")
        eligible = row.get("eligibility_gate") is True
        failed_gate = row.get("first_failed_gate")
        if eligible != (failed_gate is None):
            raise ValueError(f"candidate eligibility/failure label mismatch: {target['target_id']}")
        receipts.append(row)
        ledger.append({
            "dataset": target["dataset"], "role": target["role"],
            "target_id": target["target_id"], "theorem_name": target["theorem_name"],
            "source_file_sha256": target["source_file_sha256"],
            "theorem_text_sha256": target["theorem_text_sha256"],
            "frame_key": target["frame_key"], "eligible": eligible,
            "exclusion_reason": failed_gate,
            "candidate_receipt": str(path), "candidate_receipt_sha256": file_sha256(path),
            "pilot_selection_key": selection_key(PILOT_SELECTION_SEED, target["dataset"], target["target_id"]),
            "confirmation_selection_key": selection_key(CONFIRMATION_SELECTION_SEED, target["dataset"], target["target_id"]),
        })
    pilot = []
    counts: dict[str, dict[str, int]] = {}
    for dataset in sorted(DATASETS):
        pilot_pool = sorted(
            [row for row in ledger if row["dataset"] == dataset and row["role"] == "pilot" and row["eligible"]],
            key=lambda row: row["pilot_selection_key"],
        )
        confirmation_pool = [row for row in ledger if row["dataset"] == dataset and row["role"] == "confirmation" and row["eligible"]]
        counts[dataset] = {"pilot_eligible": len(pilot_pool), "confirmation_eligible": len(confirmation_pool)}
        pilot.extend(pilot_pool[:PILOT_ROOTS_PER_DATASET])
    ledger_path = execution_root / "eligibility_ledger.jsonl"
    pilot_path = root / "pilot/root_path_fix2/selected_roots.jsonl"
    atomic_jsonl_dump(ledger, ledger_path)
    atomic_jsonl_dump(pilot, pilot_path)
    failure_counts = Counter(
        "eligible" if row.get("eligibility_gate") is True else row["first_failed_gate"]
        for row in receipts
    )
    gate = bool(
        len(receipts) == SCREENING_ROOTS_TOTAL
        and len(pilot) == 2 * PILOT_ROOTS_PER_DATASET
        and all(counts[d]["pilot_eligible"] >= MIN_PILOT_ELIGIBLE_PER_DATASET for d in DATASETS)
        and all(counts[d]["confirmation_eligible"] >= MIN_CONFIRMATION_POOL_PER_DATASET for d in DATASETS)
        and all(row.get("continuation_probes_executed") == 0 for row in receipts)
    )
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "screening_roots": len(receipts), "expected_screening_roots": SCREENING_ROOTS_TOTAL,
        "eligibility_counts": counts, "failure_counts": dict(failure_counts),
        "eligibility_ledger": str(ledger_path), "eligibility_ledger_sha256": file_sha256(ledger_path),
        "pilot_roots": len(pilot), "pilot_roots_path": str(pilot_path),
        "pilot_roots_sha256": file_sha256(pilot_path), "manual_replacement_count": 0,
        "candidate_only_tactics_executed": sum(int(row["candidate_only_tactics_executed"]) for row in receipts),
        "continuation_probes_executed": 0, "screening_gate": gate,
        "next_step": "Freeze and run only the disjoint pilot policy cells; then estimate confirmation n." if gate
        else "STOP: insufficient candidate-only eligible roots or incomplete screening.",
    })
    atomic_json_dump(value, execution_root / "summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(Path(parse_args().artifact_root).resolve()), indent=2))
