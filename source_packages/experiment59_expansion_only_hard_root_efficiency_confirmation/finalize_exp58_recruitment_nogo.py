"""Freeze the completed Exp58 candidate-panel recruitment as a fail-closed No-Go."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from experiment59_protocol import *


EXPECTED_REGISTERED_COUNTS = {
    "eligible": 4,
    "minimum_executable_nonterminal": 1,
    "terminal_candidate": 506,
    "timeout": 1,
}
EXPECTED_WITHOUT_EXACT_COUNTS = {
    "eligible": 364,
    "minimum_executable_nonterminal": 77,
    "terminal_candidate": 70,
    "timeout": 1,
}
EXPECTED_WITHOUT_SUGGESTIONS_COUNTS = {
    "eligible": 339,
    "minimum_effect_class_size": 13,
    "minimum_executable_nonterminal": 89,
    "terminal_candidate": 70,
    "timeout": 1,
}


def classify(row: dict[str, Any], excluded: set[str]) -> str:
    if row.get("worker_ok") is not True:
        return str(row.get("first_failed_gate") or row.get("failure_category") or "worker")
    candidates = [item for item in row["candidate_rows"] if item["tactic"] not in excluded]
    terminal = sum(item.get("terminal") is True for item in candidates)
    executable = [item for item in candidates if item.get("executable") is True and not item.get("terminal")]
    classes = Counter(item["endpoints"]["struct"]["sha256"] for item in executable)
    maximum = max(classes.values(), default=0)
    if terminal:
        return "terminal_candidate"
    if len(executable) < MIN_EXECUTABLE_NONTERMINAL:
        return "minimum_executable_nonterminal"
    if maximum < MIN_EFFECT_CLASS_SIZE:
        return "minimum_effect_class_size"
    return "eligible"


def derive(root: Path) -> dict[str, Any]:
    exp58, _, _ = load_exp58_modules()
    protocol = exp58.load_protocol(root)
    if protocol.get("mechanical_fix_id") != "exp58-pre-continuation-root-path-and-accounting-fix2":
        raise ValueError("Exp58 is not the protected root-path Fix2 execution")
    frame_receipt_path = root / "frozen/source_frame_receipt.json"
    frame_receipt = exp58.read_json(frame_receipt_path)
    exp58.assert_sealed(frame_receipt, "Exp58 source frame")
    frame_path = Path(frame_receipt["candidate_screening_frame"])
    if exp58.file_sha256(frame_path) != frame_receipt["candidate_screening_frame_sha256"]:
        raise ValueError("Exp58 candidate frame changed")
    frame = exp58.read_jsonl(frame_path)
    if len(frame) != EXPECTED_EXP58_SCREENING_ROOTS:
        raise ValueError("Exp58 candidate frame is incomplete")

    execution = root / exp58.CANDIDATE_SCREENING_EXECUTION_ROOT
    receipts: list[dict[str, Any]] = []
    hash_ledger: list[dict[str, Any]] = []
    operational = 0
    attempts = 0
    timeout_ids: list[str] = []
    for target in frame:
        path = execution / "candidate_receipts" / f"{target['target_id']}.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        row = exp58.read_json(path)
        exp58.assert_sealed(row, f"Exp58 receipt {target['target_id']}")
        if row.get("target_identity") != target:
            raise ValueError(f"Exp58 target identity changed: {target['target_id']}")
        if row.get("continuation_probes_executed") != 0 or row.get("scientific_retry_count") != 0:
            raise ValueError("Exp58 screening contains a probe or retry")
        if tuple(row.get("candidate_panel", [])) != tuple(exp58.CANDIDATE_PANEL):
            raise ValueError("Exp58 registered candidate panel changed")
        if row.get("worker_ok") is True:
            if not (
                row.get("candidate_accounting_exact") is True
                and row.get("same_pre_state_all_branches") is True
                and row.get("candidate_only_tactics_executed") == 23
                and len(row.get("candidate_rows", [])) == 23
                and row.get("staged_source_content_exact") is True
            ):
                raise ValueError(f"Exp58 operational receipt failed integrity: {target['target_id']}")
            operational += 1
        else:
            process = row.get("process", {})
            if not (
                row.get("first_failed_gate") == "timeout"
                and row.get("failure_category") == "timeout"
                and row.get("candidate_only_tactics_executed") == 0
                and process.get("timed_out") is True
                and process.get("returncode") == -15
            ):
                raise ValueError(f"unexpected Exp58 operational failure: {target['target_id']}")
            timeout_ids.append(target["target_id"])
        attempts += int(row.get("candidate_only_tactics_executed", 0))
        receipts.append(row)
        hash_ledger.append({
            "dataset": target["dataset"],
            "role": target["role"],
            "target_id": target["target_id"],
            "receipt": str(path),
            "receipt_sha256": exp58.file_sha256(path),
            "record_sha256": row["record_sha256"],
        })
    if operational != EXPECTED_EXP58_OPERATIONAL_ROOTS:
        raise ValueError(f"Exp58 operational count changed: {operational}")
    if attempts != EXPECTED_EXP58_CANDIDATE_ATTEMPTS:
        raise ValueError(f"Exp58 candidate attempt count changed: {attempts}")
    if timeout_ids != [EXPECTED_EXP58_TIMEOUT_TARGET_ID]:
        raise ValueError(f"Exp58 timeout identity changed: {timeout_ids}")

    shard_rows = []
    for index in range(SHARD_COUNT):
        path = execution / f"shards/shard-{index:02d}.json"
        row = exp58.read_json(path)
        exp58.assert_sealed(row, f"Exp58 shard {index:02d}")
        if row.get("shard_index") != index or row.get("shard_count") != SHARD_COUNT:
            raise ValueError("Exp58 shard identity changed")
        shard_rows.append(row)
    if sum(row.get("receipts", 0) for row in shard_rows) != EXPECTED_EXP58_SCREENING_ROOTS:
        raise ValueError("Exp58 shard receipt accounting changed")
    failed_shards = [row["shard_index"] for row in shard_rows if row.get("shard_gate") is not True]
    if failed_shards != [22]:
        raise ValueError(f"Exp58 failed shard identity changed: {failed_shards}")

    registered = Counter(classify(row, set()) for row in receipts)
    without_exact = Counter(classify(row, {"exact?"}) for row in receipts)
    without_suggestions = Counter(classify(row, set(REMOVED_DIRECT_SUGGESTIONS)) for row in receipts)
    if dict(registered) != EXPECTED_REGISTERED_COUNTS:
        raise ValueError(f"Exp58 registered counts changed: {dict(registered)}")
    if dict(without_exact) != EXPECTED_WITHOUT_EXACT_COUNTS:
        raise ValueError(f"Exp58 exact?-exclusion sensitivity changed: {dict(without_exact)}")
    if dict(without_suggestions) != EXPECTED_WITHOUT_SUGGESTIONS_COUNTS:
        raise ValueError(f"Exp58 suggestion-exclusion sensitivity changed: {dict(without_suggestions)}")

    strata: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in receipts:
        target = row["target_identity"]
        strata[target["dataset"]][target["role"] + "_" + classify(row, set())] += 1
    observed = {
        dataset: {
            "pilot_eligible": strata[dataset]["pilot_eligible"],
            "confirmation_eligible": strata[dataset]["confirmation_eligible"],
            "unresolved_pilot": strata[dataset]["pilot_timeout"],
            "unresolved_confirmation": strata[dataset]["confirmation_timeout"],
        }
        for dataset in sorted(exp58.DATASETS)
    }
    upper = {
        dataset: {
            "pilot_eligible_upper_bound": item["pilot_eligible"] + item["unresolved_pilot"],
            "confirmation_eligible_upper_bound": item["confirmation_eligible"] + item["unresolved_confirmation"],
        }
        for dataset, item in observed.items()
    }
    if any(item["pilot_eligible_upper_bound"] >= exp58.MIN_PILOT_ELIGIBLE_PER_DATASET for item in upper.values()):
        raise ValueError("Exp58 unresolved receipts could change the pilot recruitment decision")
    if any(item["confirmation_eligible_upper_bound"] >= exp58.MIN_CONFIRMATION_POOL_PER_DATASET for item in upper.values()):
        raise ValueError("Exp58 unresolved receipts could change the confirmation recruitment decision")

    exact_terminal = sum(
        any(item.get("tactic") == "exact?" and item.get("terminal") is True for item in row.get("candidate_rows", []))
        for row in receipts if row.get("worker_ok") is True
    )
    if exact_terminal != 506:
        raise ValueError(f"Exp58 exact? terminal domination changed: {exact_terminal}")

    ledger_path = root / "recruitment_no_go/private_receipt_hash_ledger.jsonl"
    atomic_jsonl_dump(hash_ledger, ledger_path)
    value = seal({
        "version": VERSION,
        "export_schema": EXP58_NOGO_SCHEMA,
        "source_protocol_version": exp58.PROTOCOL_VERSION,
        "source_mechanical_fix_id": protocol["mechanical_fix_id"],
        "decision_label": EXP58_NOGO_LABEL,
        "decision_scope": "registered 23-candidate panel recruitment only",
        "screening_roots": len(receipts),
        "operational_roots": operational,
        "operational_failures": len(timeout_ids),
        "timeout_target_ids": timeout_ids,
        "candidate_only_tactics_executed": attempts,
        "continuation_probes_executed": 0,
        "scientific_retries": 0,
        "manual_reconciliation_count": 0,
        "shards_expected": SHARD_COUNT,
        "shards_completed": len(shard_rows),
        "shard_gates_passed": sum(row.get("shard_gate") is True for row in shard_rows),
        "failed_shards": failed_shards,
        "registered_panel_counts": dict(sorted(registered.items())),
        "registered_eligibility_by_dataset_role": observed,
        "registered_eligibility_upper_bounds": upper,
        "registered_requirements": {
            "pilot_eligible_per_dataset": exp58.MIN_PILOT_ELIGIBLE_PER_DATASET,
            "confirmation_eligible_per_dataset": exp58.MIN_CONFIRMATION_POOL_PER_DATASET,
        },
        "direct_suggestion_diagnostic": {
            "pre_existing_taxonomy": "Exp49 CANDIDATE_GENEALOGY class=direct_suggestion",
            "exact_question_terminal_roots": exact_terminal,
            "without_exact_question_counts": dict(sorted(without_exact.items())),
            "without_direct_suggestions_counts": dict(sorted(without_suggestions.items())),
            "post_execution_sensitivity_only": True,
            "changes_exp58_decision": False,
        },
        "source_frame_receipt_sha256": file_sha256(frame_receipt_path),
        "candidate_screening_frame_sha256": frame_receipt["candidate_screening_frame_sha256"],
        "private_receipt_hash_ledger": str(ledger_path),
        "private_receipt_hash_ledger_sha256": file_sha256(ledger_path),
        "claim_boundary": [
            "the registered Exp58 panel failed its preregistered recruitment quotas",
            "the outcome is not evidence that hard roots lack nonterminal tactics",
            "the post-run sensitivity analysis is diagnostic and cannot rescue or redefine Exp58",
            "no downstream continuation probe or policy comparison was executed",
        ],
        "next_step": (
            "Freeze a disjoint prospective source frame before execution; remove only the two "
            "direct-suggestion entries identified by the pre-existing Exp49 taxonomy."
        ),
    })
    atomic_json_dump(value, root / "recruitment_no_go/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(EXP58_ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(derive(Path(parse_args().artifact_root).resolve()), indent=2))
