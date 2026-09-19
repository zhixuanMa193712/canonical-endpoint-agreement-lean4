"""Freeze the disjoint 658-root expansion-only source frame before execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiment59_protocol import *


IDENTITY_FIELDS = (
    "dataset", "target_id", "theorem_name", "source_file_path", "source_file_sha256",
    "theorem_text_sha256", "measurement_source_sha256", "target_pos", "target_end_pos",
    "source_commit", "measurement_transform",
)


def freeze(root: Path, checkout_root: Path) -> dict[str, Any]:
    exp58, enumeration, _ = load_exp58_modules()
    no_go_path = EXP58_ARTIFACT_ROOT / "recruitment_no_go/summary.json"
    no_go = read_json(no_go_path)
    assert_sealed(no_go, "Exp58 recruitment No-Go")
    if not (
        no_go.get("export_schema") == EXP58_NOGO_SCHEMA
        and no_go.get("decision_label") == EXP58_NOGO_LABEL
        and no_go.get("screening_roots") == EXPECTED_EXP58_SCREENING_ROOTS
        and no_go.get("operational_roots") == EXPECTED_EXP58_OPERATIONAL_ROOTS
        and no_go.get("candidate_only_tactics_executed") == EXPECTED_EXP58_CANDIDATE_ATTEMPTS
        and no_go.get("continuation_probes_executed") == 0
    ):
        raise ValueError("Exp58 recruitment No-Go is not the protected completed run")

    old_frame_receipt_path = EXP58_ARTIFACT_ROOT / "frozen/source_frame_receipt.json"
    old_frame_receipt = exp58.read_json(old_frame_receipt_path)
    exp58.assert_sealed(old_frame_receipt, "Exp58 source frame")
    old_complete_path = Path(old_frame_receipt["complete_source_ledger"])
    old_frame_path = Path(old_frame_receipt["candidate_screening_frame"])
    if exp58.file_sha256(old_complete_path) != old_frame_receipt["complete_source_ledger_sha256"]:
        raise ValueError("Exp58 complete source ledger changed")
    if exp58.file_sha256(old_frame_path) != old_frame_receipt["candidate_screening_frame_sha256"]:
        raise ValueError("Exp58 candidate frame changed")
    old_complete = exp58.read_jsonl(old_complete_path)
    old_frame = exp58.read_jsonl(old_frame_path)
    if len(old_complete) != EXPECTED_COMPLETE_SOURCE_TARGETS or len(old_frame) != EXPECTED_EXP58_SCREENING_ROOTS:
        raise ValueError("Exp58 source accounting changed")
    old_ids = {row["target_id"] for row in old_frame}
    if len(old_ids) != EXPECTED_EXP58_SCREENING_ROOTS:
        raise ValueError("Exp58 candidate frame contains duplicate target IDs")

    environment_path = EXP58_ARTIFACT_ROOT / "preflight/benchmark_environment.json"
    environment = exp58.read_json(environment_path)
    exp58.assert_sealed(environment, "Exp58 benchmark environment")
    if environment.get("environment_gate") is not True:
        raise ValueError("Exp58 exact benchmark environment is not reusable")

    all_rows = enumeration.enumerate_minif2f(exp58.project_path("minif2f", checkout_root))
    all_rows += enumeration.enumerate_putnam(exp58.project_path("putnambench", checkout_root))
    if len(all_rows) != EXPECTED_COMPLETE_SOURCE_TARGETS:
        raise ValueError("fresh source enumeration count changed")
    old_by_id = {row["target_id"]: row for row in old_complete}
    if set(old_by_id) != {row["target_id"] for row in all_rows}:
        raise ValueError("fresh source identities differ from the protected Exp58 census")
    for row in all_rows:
        old = old_by_id[row["target_id"]]
        if any(row.get(field) != old.get(field) for field in IDENTITY_FIELDS):
            raise ValueError(f"source identity changed: {row['target_id']}")

    panel = expansion_panel(exp58)
    genealogy, genealogy_path, genealogy_sha = load_genealogy(exp58)
    selected: list[dict[str, Any]] = []
    source_counts: dict[str, dict[str, int]] = {}
    unused_rows = [row for row in all_rows if row["target_id"] not in old_ids]
    if len(unused_rows) != EXPECTED_UNUSED_SOURCE_TARGETS:
        raise ValueError(f"unused source count changed: {len(unused_rows)}")
    for dataset in sorted(exp58.DATASETS):
        pool = [row for row in unused_rows if row["dataset"] == dataset]
        if len(pool) != EXPECTED_UNUSED_BY_DATASET[dataset]:
            raise ValueError(f"unused {dataset} count changed: {len(pool)}")
        pool.sort(key=lambda row: selection_key(ROLE_ASSIGNMENT_SEED, dataset, row["target_id"]))
        for rank, row in enumerate(pool, 1):
            measurement = row.pop("_measurement_text")
            source_partition_role = row["role"]
            role = "pilot" if rank <= PILOT_SOURCE_ROOTS_PER_DATASET else "confirmation"
            row["source_partition_role"] = source_partition_role
            row["role"] = role
            row["prospective_role_assignment_key"] = selection_key(
                ROLE_ASSIGNMENT_SEED, dataset, row["target_id"]
            )
            row["prospective_rank_within_dataset"] = rank
            row["prospective_rank_within_dataset_role"] = (
                rank if role == "pilot" else rank - PILOT_SOURCE_ROOTS_PER_DATASET
            )
            row["source_exp58_frame_exclusion_exact"] = row["target_id"] not in old_ids
            row["candidate_panel_sha256"] = json_sha256(panel)
            row["continuation_probe_count"] = 0
            path = root / row["measurement_source_relative"]
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.is_file() and file_sha256(path) != row["measurement_source_sha256"]:
                raise ValueError(f"Exp59 generated source changed: {path}")
            if not path.is_file():
                path.write_text(measurement, encoding="utf-8")
            row["measurement_source"] = str(path)
            selected.append(row)
        source_counts[dataset] = {
            "unused": len(pool),
            "pilot": PILOT_SOURCE_ROOTS_PER_DATASET,
            "confirmation": len(pool) - PILOT_SOURCE_ROOTS_PER_DATASET,
        }
    if any(source_counts[d]["confirmation"] != EXPECTED_CONFIRMATION_SOURCE_ROOTS[d] for d in source_counts):
        raise ValueError("Exp59 prospective role counts changed")
    selected.sort(key=lambda row: (row["dataset"], row["role"], row["prospective_role_assignment_key"]))
    frame_path = root / "frozen/candidate_screening_frame.jsonl"
    atomic_jsonl_dump(selected, frame_path)

    implementation = [
        {"path": path.name, "bytes": path.stat().st_size, "sha256": file_sha256(path)}
        for path in sorted(PACKAGE_ROOT.glob("*.py"), key=lambda item: item.name)
    ]
    protocol = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "purpose": "prospective external hard-root confirmation of actual depth-two call savings",
        "implementation_locks": implementation,
        "source_exp58_nogo": str(no_go_path),
        "source_exp58_nogo_sha256": file_sha256(no_go_path),
        "source_exp58_nogo_record_sha256": no_go["record_sha256"],
        "source_exp58_complete_ledger_sha256": old_frame_receipt["complete_source_ledger_sha256"],
        "source_exp58_screening_frame_sha256": old_frame_receipt["candidate_screening_frame_sha256"],
        "source_exp58_screened_target_count": len(old_ids),
        "source_exp58_candidate_only_tactics_executed": EXPECTED_EXP58_CANDIDATE_ATTEMPTS,
        "source_exp58_continuation_probes_executed": 0,
        "datasets": exp58.DATASETS,
        "target_toolchain": TARGET_TOOLCHAIN,
        "candidate_panel": list(panel),
        "candidate_panel_sha256": json_sha256(panel),
        "removed_direct_suggestions": list(REMOVED_DIRECT_SUGGESTIONS),
        "removal_rule": "remove exactly entries classified direct_suggestion by frozen Exp49 CANDIDATE_GENEALOGY",
        "removed_taxonomy_rows": {name: genealogy[name] for name in REMOVED_DIRECT_SUGGESTIONS},
        "genealogy_source": str(genealogy_path),
        "genealogy_source_sha256": genealogy_sha,
        "removal_decided_before_any_exp59_execution": True,
        "source_frame": {
            "all_unused_exp58_source_roots_included": True,
            "roots": len(selected),
            "roots_by_dataset_and_role": source_counts,
            "role_assignment": (
                "within each dataset, sort all unused roots by sha256(ROLE_ASSIGNMENT_SEED,dataset,target_id); "
                "first 64 are pilot and every remaining root is confirmation"
            ),
            "manual_replacement": False,
            "frame": str(frame_path),
            "frame_sha256": file_sha256(frame_path),
        },
        "candidate_only_eligibility": {
            "terminal_candidate_count": 0,
            "minimum_executable_nonterminal_candidates": MIN_EXECUTABLE_NONTERMINAL,
            "minimum_strict_endpoint_class_size": MIN_EFFECT_CLASS_SIZE,
            "minimum_pilot_eligible_per_dataset": MIN_PILOT_ELIGIBLE_PER_DATASET,
            "minimum_confirmation_pool_per_dataset": MIN_CONFIRMATION_POOL_PER_DATASET,
            "continuation_probe_count": 0,
        },
        "pilot_selection": {
            "roots_per_dataset": PILOT_ROOTS_PER_DATASET,
            "rule": "first eligible roots by frozen PILOT_SELECTION_SEED key",
        },
        "meta_search_baseline_policy": {
            "entries": list(REMOVED_DIRECT_SUGGESTIONS),
            "not_counted_as_ordinary_branch_calls": True,
            "future_comparison_requires_wall_clock_and_internal_search_cost_reporting": True,
        },
        "exp59_candidate_only_tactics_executed_before_freeze": 0,
        "exp59_continuation_probes_executed_before_freeze": 0,
        "manual_reconciliation_count": 0,
        "next_step": "Run compile-only Exp59 preflight, then the 32 frozen candidate-only shards.",
    })
    protocol_path = root / "frozen/protocol.json"
    if protocol_path.is_file():
        existing = read_json(protocol_path)
        if existing != protocol:
            raise ValueError("existing Exp59 freeze differs from deterministic reconstruction")
    atomic_json_dump(protocol, protocol_path)
    environment_reuse = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "source_environment": str(environment_path),
        "source_environment_sha256": file_sha256(environment_path),
        "source_environment_record_sha256": environment["record_sha256"],
        "datasets": environment["datasets"],
        "environment_gate": environment["environment_gate"],
        "candidate_only_tactics_executed": 0,
        "continuation_probes_executed": 0,
    })
    atomic_json_dump(environment_reuse, root / "preflight/reused_benchmark_environment.json")
    receipt = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "protocol": str(protocol_path),
        "protocol_sha256": file_sha256(protocol_path),
        "candidate_screening_frame": str(frame_path),
        "candidate_screening_frame_sha256": file_sha256(frame_path),
        "roots": len(selected),
        "roots_by_dataset_and_role": source_counts,
        "disjoint_from_exp58_screening": not bool(old_ids & {row["target_id"] for row in selected}),
        "candidate_panel_size": len(panel),
        "removed_direct_suggestions": list(REMOVED_DIRECT_SUGGESTIONS),
        "candidate_only_tactics_executed": 0,
        "continuation_probes_executed": 0,
        "freeze_gate": len(selected) == EXPECTED_UNUSED_SOURCE_TARGETS,
        "next_step": protocol["next_step"],
    })
    atomic_json_dump(receipt, root / "frozen/freeze_receipt.json")
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--checkout-root", default=str(CHECKOUT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(freeze(Path(args.artifact_root).resolve(), Path(args.checkout_root).resolve()), indent=2))
