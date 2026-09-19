"""Apply the protected pre-candidate root-path/accounting Fix2 amendment."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from experiment58_protocol import *


FIX1_ID = "exp58-pre-continuation-build-cli-compatibility-fix1"
FAILURE_TEXT = "must be contained in root directory"


def apply(root: Path) -> dict[str, Any]:
    protocol_path = root / "frozen/protocol.json"
    previous = read_json(protocol_path)
    assert_sealed(previous, "Exp58 pre-Fix2 protocol")
    amendment_path = root / "frozen/root_path_and_accounting_fix2.json"
    if previous.get("mechanical_fix_id") == MECHANICAL_FIX_ID:
        amendment = read_json(amendment_path)
        assert_sealed(amendment, "Exp58 Fix2 amendment")
        return amendment
    if previous.get("mechanical_fix_id") != FIX1_ID:
        raise ValueError("existing Exp58 protocol is not the protected Fix1 freeze")

    frame_receipt = read_json(root / "frozen/source_frame_receipt.json")
    assert_sealed(frame_receipt, "Exp58 source frame")
    frame = read_jsonl(frame_receipt["candidate_screening_frame"])
    if len(frame) != SCREENING_ROOTS_TOTAL:
        raise ValueError("protected Fix1 screening frame is incomplete")

    failed_summary_path = root / "screening/summary.json"
    failed_summary = read_json(failed_summary_path)
    assert_sealed(failed_summary, "Exp58 failed Fix1 screening summary")
    if not (
        failed_summary.get("screening_gate") is False
        and failed_summary.get("screening_roots") == SCREENING_ROOTS_TOTAL
        and failed_summary.get("candidate_only_tactics_executed") == 0
        and failed_summary.get("continuation_probes_executed") == 0
        and failed_summary.get("pilot_roots") == 0
    ):
        raise ValueError("Fix1 summary is not the protected pre-candidate root-path failure")

    receipt_root = root / "screening/candidate_receipts"
    receipt_entries = []
    signatures = Counter()
    for target in frame:
        path = receipt_root / f"{target['target_id']}.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        row = read_json(path)
        assert_sealed(row, f"Fix1 failed receipt {target['target_id']}")
        process = row.get("process", {})
        stderr = str(process.get("stderr_tail", ""))
        if not (
            row.get("target_identity") == target
            and row.get("worker_ok") is False
            and row.get("eligibility_gate") is False
            and row.get("failure_category") == "worker_failure"
            and row.get("candidate_only_tactics_executed") == 0
            and row.get("continuation_probes_executed") == 0
            and row.get("scientific_retry_count") == 0
            and process.get("returncode") == 1
            and process.get("timed_out") is False
            and FAILURE_TEXT in stderr
            and str(target["measurement_source"]) in stderr
        ):
            raise ValueError(f"receipt is not the protected root-path failure: {target['target_id']}")
        signatures[(row["dataset"], row["failure_category"], process["returncode"])] += 1
        receipt_entries.append({
            "target_id": target["target_id"],
            "dataset": target["dataset"],
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
            "record_sha256": row["record_sha256"],
        })

    shard_entries = []
    receipt_total = 0
    for index in range(32):
        path = root / f"screening/shards/shard-{index:02d}.json"
        row = read_json(path)
        assert_sealed(row, f"Fix1 shard {index:02d}")
        if row.get("shard_index") != index or row.get("shard_count") != 32:
            raise ValueError(f"Fix1 shard identity changed: {index:02d}")
        receipt_total += int(row.get("receipts", 0))
        shard_entries.append({
            "shard_index": index,
            "path": str(path),
            "sha256": file_sha256(path),
            "record_sha256": row["record_sha256"],
        })
    if receipt_total != SCREENING_ROOTS_TOTAL:
        raise ValueError("Fix1 shard receipt accounting is incomplete")

    implementation = []
    for path in sorted(PACKAGE_ROOT.glob("*.py"), key=lambda item: item.name):
        implementation.append({"path": path.name, "sha256": file_sha256(path), "bytes": path.stat().st_size})

    previous_protocol_sha = file_sha256(protocol_path)
    amendment = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "superseded_mechanical_fix_id": FIX1_ID,
        "source_protocol_path": str(protocol_path),
        "source_protocol_file_sha256": previous_protocol_sha,
        "source_protocol_record_sha256": previous["record_sha256"],
        "source_frame_receipt_sha256": file_sha256(root / "frozen/source_frame_receipt.json"),
        "candidate_screening_frame_sha256": frame_receipt["candidate_screening_frame_sha256"],
        "failed_summary_path": str(failed_summary_path),
        "failed_summary_file_sha256": file_sha256(failed_summary_path),
        "failed_summary_record_sha256": failed_summary["record_sha256"],
        "failed_receipts": len(receipt_entries),
        "failed_receipt_ledger_sha256": json_sha256(receipt_entries),
        "failed_shards": len(shard_entries),
        "failed_shard_ledger_sha256": json_sha256(shard_entries),
        "failure_signatures": [
            {"dataset": key[0], "failure_category": key[1], "returncode": key[2], "count": count}
            for key, count in sorted(signatures.items())
        ],
        "failure_text": FAILURE_TEXT,
        "failed_execution_preserved_in_place": True,
        "replacement_execution_root": str(root / CANDIDATE_SCREENING_EXECUTION_ROOT),
        "scientific_plan_exactly_carried_forward": True,
        "candidate_only_tactics_executed_before_fix2": 0,
        "continuation_probes_executed_before_fix2": 0,
        "scientific_search_cells_executed_before_fix2": 0,
        "manual_reconciliation_count": 0,
        "next_step": "Re-run compile-only preflight, then the frozen candidate-only screening in the isolated Fix2 execution root.",
    })
    atomic_json_dump(amendment, amendment_path)

    replacement = dict(previous)
    replacement.pop("record_sha256", None)
    replacement["mechanical_fix_id"] = MECHANICAL_FIX_ID
    replacement["mechanical_fix_lineage"] = {
        "fix2_amendment": str(amendment_path),
        "fix2_amendment_sha256": file_sha256(amendment_path),
        "fix2_amendment_record_sha256": amendment["record_sha256"],
        "superseded_protocol_file_sha256": previous_protocol_sha,
        "superseded_protocol_record_sha256": previous["record_sha256"],
        "prior_lineage": previous.get("mechanical_fix_lineage"),
    }
    replacement["implementation_locks"] = implementation
    replacement["candidate_screening_execution_root"] = str(CANDIDATE_SCREENING_EXECUTION_ROOT)
    replacement["candidate_only_tactics_executed_before_freeze"] = 0
    replacement["continuation_probes_executed_before_freeze"] = 0
    replacement["scientific_search_cells_executed_before_freeze"] = 0
    replacement["next_step"] = amendment["next_step"]
    replacement = seal(replacement)
    atomic_json_dump(replacement, protocol_path)
    return amendment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(apply(Path(parse_args().artifact_root).resolve()), indent=2))
