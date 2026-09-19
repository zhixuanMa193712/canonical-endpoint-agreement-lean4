"""Independent row-level reconstruction audit for Exp54 only."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from experiment54_protocol import *


def audit(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.artifact_root).resolve()
    frozen = load_freeze(root)
    superseded = frozen["superseded_v1"]
    superseded_root = Path(superseded["artifact_root"])
    superseded_receipt_path = Path(superseded["failure_receipt_path"])
    superseded_ledger_path = Path(superseded["row_and_raw_ledger_path"])
    superseded_lineage_exact = bool(
        superseded_receipt_path.is_file()
        and file_sha256(superseded_receipt_path)
        == superseded["failure_receipt_sha256"]
        and superseded_ledger_path.is_file()
        and file_sha256(superseded_ledger_path)
        == superseded["row_and_raw_ledger_file_sha256"]
        and len(read_jsonl(superseded_ledger_path)) == EXPECTED_CELLS
        and (superseded_root / "frozen/design.json").is_file()
        and file_sha256(superseded_root / "frozen/design.json")
        == superseded["design_sha256"]
        and (superseded_root / "execution/summary.json").is_file()
        and file_sha256(superseded_root / "execution/summary.json")
        == superseded["execution_summary_sha256"]
        and (superseded_root / "execution/row_index.jsonl").is_file()
        and file_sha256(superseded_root / "execution/row_index.jsonl")
        == superseded["row_index_sha256"]
        and all(
            Path(item["path"]).is_file()
            and Path(item["path"]).stat().st_size == item["bytes"]
            and file_sha256(item["path"]) == item["sha256"]
            for item in superseded["exact_snapshots"].values()
        )
    )
    superseded_fix1 = frozen["superseded_fix1"]
    superseded_fix1_root_path = Path(superseded_fix1["artifact_root"])
    fix1_receipt_path = Path(superseded_fix1["failure_receipt_path"])
    fix1_ledger_path = Path(superseded_fix1["row_and_raw_ledger_path"])
    superseded_fix1_lineage_exact = bool(
        fix1_receipt_path.is_file()
        and file_sha256(fix1_receipt_path)
        == superseded_fix1["failure_receipt_sha256"]
        and fix1_ledger_path.is_file()
        and file_sha256(fix1_ledger_path)
        == superseded_fix1["row_and_raw_ledger_file_sha256"]
        and len(read_jsonl(fix1_ledger_path)) == EXPECTED_CELLS
        and (superseded_fix1_root_path / "frozen/design.json").is_file()
        and file_sha256(superseded_fix1_root_path / "frozen/design.json")
        == superseded_fix1["design_sha256"]
        and (superseded_fix1_root_path / "execution/summary.json").is_file()
        and file_sha256(superseded_fix1_root_path / "execution/summary.json")
        == superseded_fix1["execution_summary_sha256"]
        and (superseded_fix1_root_path / "execution/row_index.jsonl").is_file()
        and file_sha256(superseded_fix1_root_path / "execution/row_index.jsonl")
        == superseded_fix1["row_index_sha256"]
        and all(
            Path(item["path"]).is_file()
            and Path(item["path"]).stat().st_size == item["bytes"]
            and file_sha256(item["path"]) == item["sha256"]
            for item in superseded_fix1["exact_snapshots"].values()
        )
    )
    superseded_fix2 = frozen["superseded_fix2"]
    superseded_fix2_root_path = Path(superseded_fix2["artifact_root"])
    fix2_receipt_path = Path(superseded_fix2["failure_receipt_path"])
    fix2_ledger_path = Path(superseded_fix2["row_and_raw_ledger_path"])
    superseded_fix2_lineage_exact = bool(
        fix2_receipt_path.is_file()
        and file_sha256(fix2_receipt_path)
        == superseded_fix2["failure_receipt_sha256"]
        and fix2_ledger_path.is_file()
        and file_sha256(fix2_ledger_path)
        == superseded_fix2["row_and_raw_ledger_file_sha256"]
        and len(read_jsonl(fix2_ledger_path)) == EXPECTED_CELLS
        and (superseded_fix2_root_path / "frozen/design.json").is_file()
        and file_sha256(superseded_fix2_root_path / "frozen/design.json")
        == superseded_fix2["design_sha256"]
        and (superseded_fix2_root_path / "execution/summary.json").is_file()
        and file_sha256(superseded_fix2_root_path / "execution/summary.json")
        == superseded_fix2["execution_summary_sha256"]
        and (superseded_fix2_root_path / "execution/row_index.jsonl").is_file()
        and file_sha256(superseded_fix2_root_path / "execution/row_index.jsonl")
        == superseded_fix2["row_index_sha256"]
        and all(
            Path(item["path"]).is_file()
            and Path(item["path"]).stat().st_size == item["bytes"]
            and file_sha256(item["path"]) == item["sha256"]
            for item in superseded_fix2["exact_snapshots"].values()
        )
    )
    reported = read_json(root / "analysis/summary.json")
    cells = {row["cell_id"]: row for row in read_jsonl(frozen["cells_path"])}
    rows = []
    all_hashes = True
    for item in read_jsonl(root / "execution/row_index.jsonl"):
        path = Path(item["path"])
        if file_sha256(path) != item["sha256"]:
            all_hashes = False
        row = read_json(path)
        if row.get("record_sha256") != record_sha(row):
            all_hashes = False
        rows.append(row)
    observed = {row["cell_id"]: row for row in rows}
    full = {
        (row["pair_id"], row["side"], row["probe"]): row
        for row in rows if row["policy"] == "full"
    }
    dedup = {
        (row["pair_id"], row["side"], row["probe"]): row
        for row in rows if row["policy"] == "dedup"
    }
    overlap_mismatches = sum(
        outcome_signature(full[item]) != outcome_signature(dedup[item])
        for item in set(full) & set(dedup)
    )
    pairs = {row["pair_id"]: row for row in read_jsonl(frozen["pairs_path"])}
    full_grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    dedup_grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        bucket = full_grouped if row["policy"] == "full" else dedup_grouped
        bucket[(row["pair_id"], row["probe"])].append(row)
    witness_probe_mismatches = 0
    witness_pair_mismatch: set[str] = set()
    coverage_mismatches = 0
    for item, full_rows in full_grouped.items():
        pair_id, _probe = item
        dedup_rows = dedup_grouped[item]
        full_set = {json_sha256(outcome_signature(row)) for row in full_rows}
        dedup_set = {json_sha256(outcome_signature(row)) for row in dedup_rows}
        if full_set != dedup_set:
            coverage_mismatches += 1
        if pairs[pair_id]["role"] == "witness":
            by_side = {row["side"]: outcome_signature(row) for row in full_rows}
            if by_side.get("left") != by_side.get("right"):
                witness_probe_mismatches += 1
                witness_pair_mismatch.add(pair_id)
    full_endpoints = {
        row["probe_endpoint"]["struct"]["sha256"]
        for row in rows
        if row["policy"] == "full" and row.get("probe_status") == "success"
    }
    dedup_endpoints = {
        row["probe_endpoint"]["struct"]["sha256"]
        for row in rows
        if row["policy"] == "dedup" and row.get("probe_status") == "success"
    }
    full_terminal_pair_probes = {
        (row["pair_id"], row["probe"]) for row in rows
        if row["policy"] == "full" and row.get("probe_status") == "success"
        and row["probe_endpoint"]["struct"]["terminal"] is True
    }
    dedup_terminal_pair_probes = {
        (row["pair_id"], row["probe"]) for row in rows
        if row["policy"] == "dedup" and row.get("probe_status") == "success"
        and row["probe_endpoint"]["struct"]["terminal"] is True
    }
    full_calls = sum(row["policy"] == "full" for row in rows)
    dedup_calls = sum(row["policy"] == "dedup" for row in rows)
    integrity = bool(
        set(cells) == set(observed)
        and all_hashes
        and all(row.get("valid_reconstruction") is True for row in rows)
        and all(
            row.get("process", {}).get("fresh_lean_process") is True
            and row.get("process", {}).get("attempt_ordinal") == 1
            for row in rows
        )
        and all(row.get("scientific_retry_count") == 0 for row in rows)
        and all(row.get("manual_reconciliation_count") == 0 for row in rows)
    )
    efficiency = bool(
        full_calls == EXPECTED_FULL_CELLS
        and dedup_calls == EXPECTED_DEDUP_CELLS
        and full_calls - dedup_calls == 128
    )
    preservation = bool(
        overlap_mismatches == 0
        and witness_probe_mismatches == 0
        and coverage_mismatches == 0
        and full_endpoints == dedup_endpoints
        and full_terminal_pair_probes == dedup_terminal_pair_probes
    )
    if integrity and efficiency and preservation:
        reconstructed_decision = "effect_aware_depth2_supported"
    elif integrity and efficiency:
        reconstructed_decision = "coverage_loss_detected"
    else:
        reconstructed_decision = "effect_aware_depth2_inconclusive"
    checks = {
        "superseded_v1_failure_lineage_exact": superseded_lineage_exact,
        "superseded_fix1_failure_lineage_exact": superseded_fix1_lineage_exact,
        "superseded_fix2_failure_lineage_exact": superseded_fix2_lineage_exact,
        "scientific_plan_exactly_carried_forward_from_v1": (
            frozen["scientific_plan_exactly_carried_forward_from_v1"] is True
        ),
        "scientific_plan_exactly_carried_forward_from_fix1": (
            frozen["scientific_plan_exactly_carried_forward_from_fix1"] is True
        ),
        "scientific_plan_exactly_carried_forward_from_fix2": (
            frozen["scientific_plan_exactly_carried_forward_from_fix2"] is True
        ),
        "all_frozen_cells_accounted": set(cells) == set(observed),
        "all_row_hashes_exact": all_hashes,
        "full_call_count_exact": full_calls == reported["search_efficiency"]["full_downstream_calls"],
        "dedup_call_count_exact": dedup_calls == reported["search_efficiency"]["dedup_downstream_calls"],
        "saved_call_count_exact": (
            full_calls - dedup_calls == reported["search_efficiency"]["calls_saved"]
        ),
        "overlap_mismatch_count_exact": overlap_mismatches == reported["overlap_mismatch_count"],
        "witness_probe_mismatch_count_exact": (
            witness_probe_mismatches == reported["coverage"]["witness_probe_mismatches"]
        ),
        "witness_pair_mismatch_count_exact": (
            len(witness_pair_mismatch)
            == reported["coverage"]["witness_pairs_with_any_mismatch"]
        ),
        "coverage_mismatch_count_exact": (
            coverage_mismatches == reported["coverage"]["coverage_mismatches"]
        ),
        "strict_endpoint_union_report_exact": (
            (full_endpoints == dedup_endpoints)
            == reported["coverage"]["successful_strict_endpoint_union_exact"]
        ),
        "terminal_success_pair_probe_report_exact": (
            (full_terminal_pair_probes == dedup_terminal_pair_probes)
            == reported["coverage"]["terminal_success_pair_probe_set_exact"]
        ),
        "decision_label_exact": reconstructed_decision == reported["decision_label"],
        "all_attempt_ordinals_one": all(
            row.get("process", {}).get("attempt_ordinal") == 1 for row in rows
        ),
        "zero_scientific_retries": all(
            row.get("scientific_retry_count") == 0 for row in rows
        ),
        "zero_manual_reconciliation": all(
            row.get("manual_reconciliation_count") == 0 for row in rows
        ),
    }
    value = {
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "execution_version": EXECUTION_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "cells_reconstructed": len(rows),
        "pairs_reconstructed": len(pairs),
        "witness_probe_comparisons_reconstructed": (
            sum(pair["role"] == "witness" for pair in pairs.values()) * len(PROBES)
        ),
        "full_calls_reconstructed": full_calls,
        "dedup_calls_reconstructed": dedup_calls,
        "witness_probe_mismatches_reconstructed": witness_probe_mismatches,
        "coverage_mismatches_reconstructed": coverage_mismatches,
        "manual_reconciliation_count": 0,
        "checks": checks,
        "audit_pass": all(checks.values()),
        "decision_label_preserved": reported["decision_label"],
        "next_step": (
            "Export immutable Exp54 bundle."
            if all(checks.values()) else "STOP; audit reconstruction failed."
        ),
    }
    atomic_json_dump(value, root / "audit/summary.json")
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--artifact-root", default=str(artifact_root()))
    return p.parse_args()


if __name__ == "__main__":
    audit(parse_args())
