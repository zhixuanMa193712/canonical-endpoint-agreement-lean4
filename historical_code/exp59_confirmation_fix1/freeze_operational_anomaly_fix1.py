"""Freeze the post-execution Exp59 operational-anomaly amendment.

This is an offline, fail-closed amendment.  It executes no Lean command,
rewrites no scientific receipt, and accepts exactly the three pre-registered
evidence locks in ``experiment59_confirmation_fix1_protocol.py``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiment59_confirmation_fix1_protocol import *


def freeze(root: Path) -> dict:
    root = Path(root).resolve()
    path = root / AMENDMENT_RELATIVE
    if path.is_file():
        validated = validate_fix1_amendment(root)
        return {
            key: value for key, value in validated.items()
            if key not in {"corpus", "path", "sha256"}
        }

    original_analysis = root / "confirmation/analysis/summary.json"
    original_audit = root / "confirmation/audit/summary.json"
    fix1_analysis = root / FIX1_RELATIVE / "analysis/summary.json"
    fix1_audit = root / FIX1_RELATIVE / "audit/summary.json"
    if any(item.exists() for item in (
        original_analysis, original_audit, fix1_analysis, fix1_audit
    )):
        raise ValueError(
            "Fix1 amendment must be frozen before any confirmation analysis or audit"
        )

    corpus = load_fix1_corpus(root)
    value = seal({
        "version": FIX1_VERSION,
        "schema": AMENDMENT_SCHEMA,
        "fix1_protocol_version": FIX1_PROTOCOL_VERSION,
        "mechanical_fix_id": FIX1_MECHANICAL_ID,
        "source_confirmation_protocol_version": CONFIRMATION_PROTOCOL_VERSION,
        "source_design_record_sha256": corpus["design"]["record_sha256"],
        "source_job_ledger_sha256": corpus["job_ledger_sha256"],
        "source_jobs": corpus["jobs_count"],
        "source_cells": corpus["cells_count"],
        "locked_operational_anomaly_cells": corpus["invalid_cells"],
        "locked_operational_anomaly_ledger": corpus["anomalies"],
        "affected_roots": corpus["affected_roots"],
        "affected_root_count": len(corpus["affected_roots"]),
        "analysis_absent_before_amendment": True,
        "audit_absent_before_amendment": True,
        "original_receipts_rewritten": False,
        "efficiency_estimand_remains_64_root_process_call_accounting": True,
        "registered_coverage_estimand_complete": False,
        "coverage_disposition": (
            "one root is unevaluable; do not impute, delete, retry, or count "
            "the three panic cells as tactic failures"
        ),
        "lean_executed_by_amendment": False,
        "continuation_probes_executed_by_amendment": 0,
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
        "amendment_gate": True,
        "next_step": "Finalize the original receipts under the locked Fix1 amendment.",
    })
    atomic_json_dump(value, path)
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(freeze(Path(parse_args().artifact_root)), indent=2))
