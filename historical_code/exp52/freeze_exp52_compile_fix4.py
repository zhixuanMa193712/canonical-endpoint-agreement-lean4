"""Freeze the narrow Exp52 pre-probe compile-compatibility Fix4.

This command runs no Lean, elaborates no theorem, and executes no candidate or
continuation probe.  It requires and preserves the failed Fix3 compile receipt.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import alignment_protocol as protocol
from alignment_protocol import *  # noqa: F401,F403
from experiment52_live_worker import LEAN_SOURCE_SHA256


def build_amendment(
    source: dict[str, Any], failed: dict[str, Any], completed: dict[str, Any],
    created_utc: str,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "version": 1,
        "schema": AMENDMENT_SCHEMA,
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "mechanical_fix_id": EXECUTION_FIX_ID,
        "created_utc": created_utc,
        "frozen_before_first_continuation_probe": True,
        "continuation_probes_executed_before_amendment": 0,
        "source_fix3": {
            "alignment_version": SOURCE_FIX3_ALIGNMENT_VERSION,
            "mechanical_fix_id": SOURCE_FIX3_FIX_ID,
            "amendment": str(source["amendment_path"]),
            "amendment_sha256": source["amendment_sha256"],
            "amendment_receipt": str(
                source["root"] / SOURCE_FIX3_RECEIPT_RELATIVE
            ),
            "amendment_receipt_sha256": file_sha256(
                source["root"] / SOURCE_FIX3_RECEIPT_RELATIVE
            ),
            "failed_preflight": str(failed["path"]),
            "failed_preflight_sha256": failed["sha256"],
            "selection_summary": str(completed["paths"]["selection"]),
            "selection_summary_sha256": completed["hashes"]["selection"],
            "execution_cell_plan": str(completed["plan"]),
            "execution_cell_plan_sha256": completed["plan_sha256"],
            "exp51_summary_sha256": completed["hashes"]["exp51_summary"],
            "exp51_analysis_sha256": completed["hashes"]["exp51_analysis"],
            "exp51_audit_sha256": completed["hashes"]["exp51_audit"],
            "exp51_export_sha256": completed["hashes"]["exp51_export"],
        },
        "scope": {
            "lean_exception_render_sites_changed": 1,
            "source_fix3_lean_source_sha256": (
                SOURCE_FIX3_EXP52_LEAN_SOURCE_SHA256
            ),
            "fix4_lean_source_sha256": LEAN_SOURCE_SHA256,
            "generated_lean_diff_exact": (
                LEAN_SOURCE_SHA256 == FIX4_EXP52_LEAN_SOURCE_SHA256
            ),
            "change": (
                "replace the unsupported ToString Exception call with "
                "Exception.toMessageData.toString in BaseIO"
            ),
            "selection_changed": False,
            "execution_cell_count_changed": False,
            "probe_panel_changed": False,
            "endpoint_changed": False,
            "statistics_changed": False,
            "decision_thresholds_changed": False,
            "retry_policy_changed": False,
        },
        "execution": {
            "worker_version": EXP52_WORKER_VERSION,
            "shard_count": EXP52_SHARD_COUNT,
            "execution_cells": completed["selection"]["execution_cells"],
            "selection_source_amendment_sha256": source["amendment_sha256"],
            "compile_preflight": str(source["root"] / EXP52_PREFLIGHT_RELATIVE),
            "fresh_process_per_cell": True,
            "scientific_retry_permitted": False,
            "lean_timeout_seconds": LEAN_TIMEOUT_SECONDS,
        },
        "code_lock": package_code_lock(),
        "claim_boundary": [
            "mechanical pre-probe compile compatibility amendment only",
            "the failed Fix3 preflight remains immutable evidence",
            "Exp51 results and the Fix3 Exp52 selection remain unchanged",
            "state-conditioned one-step endpoint agreement only",
            "not tactic equivalence or global interchangeability",
            "not semantic, proof-strategy, proof-term, or runtime equivalence",
            "not proof-search or theorem-proving improvement",
        ],
        "next_step": (
            "Run the Fix4 compile-only Exp52 worker preflight; execute zero "
            "continuation probes during preflight."
        ),
    }
    value["identity_sha256"] = identity_sha256(value)
    return value


def build_receipt(path: Path, value: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": 1,
        "schema": "experiment52-pre-probe-compile-compatibility-receipt-v1",
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "mechanical_fix_id": EXECUTION_FIX_ID,
        "amendment": str(path),
        "amendment_sha256": file_sha256(path),
        "identity_sha256": value["identity_sha256"],
        "source_fix3_amendment_sha256": value["source_fix3"]["amendment_sha256"],
        "failed_fix3_preflight_sha256": value["source_fix3"]["failed_preflight_sha256"],
        "selection_summary_sha256": value["source_fix3"]["selection_summary_sha256"],
        "execution_cell_plan_sha256": value["source_fix3"]["execution_cell_plan_sha256"],
        "execution_cells": value["execution"]["execution_cells"],
        "continuation_probes_executed_before_amendment": 0,
        "amendment_gate": True,
        "next_step": value["next_step"],
    }


def freeze(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    path = root / AMENDMENT_RELATIVE
    receiptp = root / AMENDMENT_RECEIPT_RELATIVE
    if receiptp.exists() and not path.exists():
        raise ValueError("orphan Fix4 receipt exists without amendment")
    source = validate_fix3_source(root)
    failed = protocol._validate_fix3_failed_preflight(root)
    completed = protocol._validate_exp51_and_selection(root, source)
    if not path.exists():
        protocol._prove_no_exp52_probe_execution(root)
        value = build_amendment(
            source, failed, completed, datetime.now(timezone.utc).isoformat()
        )
        exclusive_create_json(path, value)
    validated = validate_amendment(root)
    expected = build_receipt(path, validated["amendment"])
    if not receiptp.exists():
        # Crash recovery is safe because the immutable amendment itself records
        # that it was exclusively written before any continuation-probe output.
        exclusive_create_json(receiptp, expected)
    receipt = read_json(receiptp)
    if receipt != expected:
        raise ValueError("existing Fix4 amendment receipt changed")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(SCIENTIFIC_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    freeze(parse_args())
