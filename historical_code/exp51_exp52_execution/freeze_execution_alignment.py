"""Freeze the pre-candidate Fix3 execution amendment without running Lean."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alignment_protocol import *


def build_amendment(source: dict[str, Any], created_utc: str) -> dict[str, Any]:
    targets = source["targets"]
    shard_plan = []
    for shard in range(EXP51_SHARD_COUNT):
        rows = targets_for_shard(targets, shard, EXP51_SHARD_COUNT)
        shard_plan.append({
            "shard_index": shard,
            "target_count": len(rows),
            "theorem_ids_sha256": json_sha256(
                [row["theorem_id"] for row in rows]
            ),
        })
    value: dict[str, Any] = {
        "version": 1,
        "schema": AMENDMENT_SCHEMA,
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "mechanical_fix_id": EXECUTION_FIX_ID,
        "created_utc": created_utc,
        "frozen_before_exp51_scientific_execution": True,
        "scientific_candidate_execution_before_amendment": False,
        "source_fix2": {
            "alignment_version": fix2.ALIGNMENT_VERSION,
            "mechanical_fix_id": fix2.ALIGNMENT_FIX_ID,
            "config": str(source["paths"]["config"]),
            "config_sha256": source["config_sha256"],
            "targets": str(source["paths"]["targets"]),
            "targets_sha256": source["targets_sha256"],
            "exp52_protocol": str(source["paths"]["protocol"]),
            "exp52_protocol_sha256": source["protocol_sha256"],
            "freeze_receipt": str(source["paths"]["receipt"]),
            "freeze_receipt_sha256": source["receipt_sha256"],
            "freeze_transaction": str(source["paths"]["transaction"]),
            "freeze_transaction_sha256": source["transaction_sha256"],
            "qualification_config_sha256": source["receipt"][
                "qualification_config_sha256"
            ],
            "qualification_summary_sha256": source["receipt"][
                "qualification_summary_sha256"
            ],
            "copied_build_receipts_exact": source["receipt"][
                "copied_build_receipts_exact"
            ],
            "exp52_design_documents_bundle_sha256": source["receipt"][
                "exp52_design_documents_bundle_sha256"
            ],
            "exp52_retained_probes": source["receipt"][
                "exp52_retained_probes"
            ],
        },
        "portable_exp52_document_lock": source["portable_document_lock"],
        "exp51_execution": {
            "runner_version": EXP51_RUNNER_VERSION,
            "roots": TARGET_ROOTS,
            "repositories": TARGET_REPOSITORIES,
            "candidates_per_evaluable_root": CANDIDATES_PER_ROOT,
            "shard_count": EXP51_SHARD_COUNT,
            "shard_assignment": "frozen-target-position-modulo-shard-count",
            "shard_plan": shard_plan,
            "root_process_isolation": True,
            "shard_local_content_store": True,
            "shard_local_generated_worker": True,
            "scientific_retry_permitted": False,
            "execution_complete_definition": (
                "one identity-valid immutable worker receipt per frozen root"
            ),
            "candidate_completeness_scope": "evaluable_roots_only",
            "unevaluable_rows_retained": True,
            "lean_timeout_seconds": LEAN_TIMEOUT_SECONDS,
            "resource_gate": {
                "minimum_allowed_cpus": 16,
                "minimum_available_memory_gb": 64,
                "minimum_free_disk_gb": 50,
            },
        },
        "exp52_execution": {
            "worker_version": EXP52_WORKER_VERSION,
            "selection_version": EXP52_SELECTION_VERSION,
            "shard_count": EXP52_SHARD_COUNT,
            "shard_assignment": "frozen-cell-position-modulo-shard-count",
            "fresh_process_per_root_pair_role_side_probe": True,
            "candidate_post_state_exact_match_required": [
                "raw", "text48", "struct", "goal_count", "terminal"
            ],
            "lean_timeout_seconds": LEAN_TIMEOUT_SECONDS,
            "scientific_retry_permitted": False,
            "launch_dependency": (
                "completed locked Exp51 Fix3 scientific rows and mechanically "
                "selected witness/control ledgers"
            ),
            "may_run_in_parallel_with_exp51_scientific": False,
        },
        "protocol_repairs": {
            "downstream_fix2_identity_hard_validation": True,
            "portable_document_bundle_added_without_replacing_fix2_receipt": True,
            "safe_deterministic_exp51_shards": True,
            "execution_complete_separated_from_evaluability": True,
            "extension2_flow_field": "repositories_considered",
            "exp52_full_stack_locked_before_exp51_outcomes": True,
        },
        "code_lock": package_code_lock(),
        "claim_boundary": [
            "execution implementation amendment only; no scientific result",
            "Fix2 repository sample, roots, candidates, endpoints, probes, "
            "thresholds, and Exp52 v0.1 design remain unchanged",
            "state-conditioned one-step endpoint agreement only",
            "not tactic equivalence or global interchangeability",
            "not semantic, proof-strategy, proof-term, or runtime equivalence",
            "not proof-search or theorem-proving improvement",
        ],
        "next_step": (
            "Run Fix3 compile-only Exp51 worker preflight; execute zero theorem "
            "roots and zero scientific candidates."
        ),
    }
    value["identity_sha256"] = identity_sha256(value)
    return value


def build_receipt(
    amendmentp: Path,
    amendment: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    """Build the immutable receipt for an already validated amendment."""
    return {
        "version": 1,
        "schema": "exp51-exp52-execution-alignment-fix3-receipt-v1",
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "mechanical_fix_id": EXECUTION_FIX_ID,
        "amendment": str(amendmentp),
        "amendment_sha256": file_sha256(amendmentp),
        "identity_sha256": amendment["identity_sha256"],
        "source_config_sha256": source["config_sha256"],
        "source_targets_sha256": source["targets_sha256"],
        "source_exp52_protocol_sha256": source["protocol_sha256"],
        "source_freeze_receipt_sha256": source["receipt_sha256"],
        "source_freeze_transaction_sha256": source["transaction_sha256"],
        "source_qualification_config_sha256": source["receipt"][
            "qualification_config_sha256"
        ],
        "source_qualification_summary_sha256": source["receipt"][
            "qualification_summary_sha256"
        ],
        "source_exp52_design_documents_bundle_sha256": source["receipt"][
            "exp52_design_documents_bundle_sha256"
        ],
        "source_exp52_retained_probes": source["receipt"][
            "exp52_retained_probes"
        ],
        "source_copied_build_receipts_exact": source["receipt"][
            "copied_build_receipts_exact"
        ],
        "portable_exp52_document_bundle_sha256": source[
            "portable_document_lock"
        ]["bundle_sha256"],
        "repositories": TARGET_REPOSITORIES,
        "roots": TARGET_ROOTS,
        "exp51_shards": EXP51_SHARD_COUNT,
        "exp52_shards": EXP52_SHARD_COUNT,
        "scientific_candidate_execution_before_amendment": False,
        "scientific_candidate_tactics_executed": 0,
        "amendment_gate": True,
        "next_step": amendment["next_step"],
    }


def validate_receipt(
    receipt: dict[str, Any],
    amendmentp: Path,
    amendment: dict[str, Any],
    source: dict[str, Any],
) -> None:
    expected = build_receipt(amendmentp, amendment, source)
    if receipt != expected:
        raise ValueError("existing Fix3 execution amendment receipt changed")


def freeze(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    amendmentp = root / AMENDMENT_RELATIVE
    receiptp = root / AMENDMENT_RECEIPT_RELATIVE
    if receiptp.exists() and not amendmentp.exists():
        raise ValueError("orphan Fix3 receipt exists without its amendment")
    if amendmentp.exists():
        # A crash can occur after the exclusive amendment write but before its
        # receipt write.  Revalidate both the source's pre-candidate state and
        # the full amendment code lock before completing only that receipt.
        source = validate_source_bundle(
            root, require_pre_candidate=not receiptp.exists()
        )
        value = validate_amendment(root)
        expected = build_receipt(
            amendmentp, value["amendment"], source
        )
        if not receiptp.exists():
            exclusive_create_json(receiptp, expected)
        receipt = read_json(receiptp)
        validate_receipt(receipt, amendmentp, value["amendment"], source)
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return receipt
    source = validate_source_bundle(root, require_pre_candidate=True)
    amendment = build_amendment(
        source, datetime.now(timezone.utc).isoformat()
    )
    exclusive_create_json(amendmentp, amendment)
    validated = validate_amendment(root)
    receipt = build_receipt(
        amendmentp, validated["amendment"], source
    )
    exclusive_create_json(receiptp, receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(SCIENTIFIC_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    freeze(parse_args())
