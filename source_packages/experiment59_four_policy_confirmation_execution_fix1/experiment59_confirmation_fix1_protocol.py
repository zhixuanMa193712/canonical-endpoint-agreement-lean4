"""Fail-closed post-execution amendment helpers for Exp59 confirmation Fix1.

Fix1 does not execute Lean and does not rewrite an original receipt.  It locks
three deterministic Lean internal-panic rows, preserves the 64-root process-
call estimand, and makes the registered coverage estimand unevaluable.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from experiment59_confirmation_protocol import *  # noqa: F401,F403


FIX1_VERSION = 1
FIX1_PROTOCOL_VERSION = (
    "experiment59-expansion-only-four-policy-confirmation-operational-"
    "anomaly-fix1-v1"
)
FIX1_MECHANICAL_ID = (
    "exp59-confirmation-fix1-retain-three-lean-internal-panics-and-"
    "separate-efficiency-coverage-gates"
)
AMENDMENT_SCHEMA = "experiment59-confirmation-operational-anomaly-amendment-v1"
AMENDMENT_RELATIVE = Path("confirmation/frozen/operational_anomaly_fix1.json")
FIX1_RELATIVE = Path("confirmation/fix1")
PANIC_MESSAGE = "INTERNAL PANIC: Nat.pow exponent is too big\n"
PANIC_STDERR_SHA256 = (
    "aade23fe7e645ed081eca9d66b8aad233ff8862aaa483cecda98bbb99db73f2d"
)
AFFECTED_TARGET_ID = "b3ef16b88207962858403285"
AFFECTED_DATASET = "minif2f"
AFFECTED_BRANCH_ID = "52927745410fdbbd319435d4"
AFFECTED_CANDIDATE_TACTIC = "simp_all"
AFFECTED_PROBE = "omega"
AFFECTED_ENDPOINT_SHA256 = (
    "195f4711141f8c733df4077564fe59bfb39ac6dbf72f0c9c1cc5a144c2cd0bea"
)

ANOMALY_LOCKS: tuple[dict[str, str], ...] = (
    {
        "policy": "effect_aware",
        "job_id": "53a8edc7136583763fd718e2",
        "job_sha256": "df5ed1d0f689ce8b993e710482df450e8b091da2aa0462d7700050f44bc326b5",
        "cell_id": "6be77822b87c8eb2fed9ea3a",
        "row_sha256": "803725baa098d4225558bc20b2d72864ba53b57f42210071d1faf46ac31ccb24",
        "input_sha256": "e738406d8b52197bab577a84d6436bb99b6aa23632be6c2148bd4bb2056139c8",
        "record_sha256": "7159088cdefaede36b30aa5a389b0d06e605048ab50ba7df631a93145366f9c8",
        "control_cell_id": "88ccce9138f18851d9e75869",
        "control_sha256": "10bae4deb10a5bcb7de9a3cf05444cd376089c38079040526bdc2840892547f3",
    },
    {
        "policy": "head_dedup",
        "job_id": "683acceb2a8d879d8959d9cf",
        "job_sha256": "2bdbc0b11c51c81f7a4bef14b1d6321522525a9196f3e091fde81ee876c68882",
        "cell_id": "3504b88c806e0f0cad101c81",
        "row_sha256": "c87b28a17921a3ecce9ef469f12f1df66d0d9c6836eb3fb8ca76ebd5a266314c",
        "input_sha256": "6abc292e74704de6c67b1ba641e285e6f188020bb0bce116032ff933670ebe89",
        "record_sha256": "2cb12972d043c5a40b2419e3ae35cdf2bb209f95e6eb32876cdd2e2cac468399",
        "control_cell_id": "f54cc9c8b2e82d4fb8708dca",
        "control_sha256": "03df03019b5375d87933afd79de1b3fa5813fbc6d2ee44e9424ee6e271cb7342",
    },
    {
        "policy": "full",
        "job_id": "bf36335f1908152b5bcc1a54",
        "job_sha256": "44eaff83c7cd27d3a49db9fca8b99c7a695be8b83fe98cfe319dfd91928daac2",
        "cell_id": "6518c20db28d368af653a7cf",
        "row_sha256": "f33329cf1810bea8afd2952476c4f39f5617e0d7c029798e1a0dac657a0edda5",
        "input_sha256": "3abc6364859b011840d9c40026edfe5d5dcf24011f7ac6b30dedadf8b408997f",
        "record_sha256": "149850c3cb5bf25dfdf7a97f51c6d0cab0b0f6071ba579505756e4bdc6a4b968",
        "control_cell_id": "fcd892e2e0a00188d93b2ca3",
        "control_sha256": "5f6452d6e96ccf6fce7aae6d18ccb3f4a8d959cb9bc37cc67d219499a640e910",
    },
)

ANOMALY_BY_CELL = {row["cell_id"]: row for row in ANOMALY_LOCKS}
ANOMALY_BY_JOB = {row["job_id"]: row for row in ANOMALY_LOCKS}


def _input_exact(value: dict[str, Any]) -> bool:
    return value.get("input_identity_sha256") == json_sha256({
        key: item for key, item in value.items()
        if key != "input_identity_sha256"
    })


def _validate_locked_anomaly(
    root: Path,
    job: dict[str, Any],
    cells: list[tuple[Path, dict[str, Any]]],
    lock: dict[str, str],
) -> dict[str, Any]:
    job_path = root / "confirmation/execution/jobs" / f"{lock['job_id']}.json"
    if file_sha256(job_path) != lock["job_sha256"]:
        raise ValueError(f"locked panic job changed: {lock['job_id']}")
    by_id = {row["cell_id"]: (path, row) for path, row in cells}
    if lock["cell_id"] not in by_id or lock["control_cell_id"] not in by_id:
        raise ValueError("locked panic or candidate-only control is missing")
    row_path, row = by_id[lock["cell_id"]]
    control_path, control = by_id[lock["control_cell_id"]]
    input_path = root / "confirmation/execution/inputs" / f"{lock['cell_id']}.json"
    inp = read_json(input_path)
    raw_path = root / "confirmation/execution/runtime/lean_raw" / f"{lock['cell_id']}.json"
    process = row.get("process", {})
    exact = bool(
        file_sha256(row_path) == lock["row_sha256"]
        and file_sha256(input_path) == lock["input_sha256"]
        and row.get("record_sha256") == lock["record_sha256"]
        and row.get("job_id") == lock["job_id"]
        and row.get("target_id") == AFFECTED_TARGET_ID
        and row.get("dataset") == AFFECTED_DATASET
        and row.get("policy") == lock["policy"]
        and row.get("mode") == "candidate_probe"
        and row.get("branch_id") == AFFECTED_BRANCH_ID
        and row.get("candidate_tactic") == AFFECTED_CANDIDATE_TACTIC
        and row.get("probe") == AFFECTED_PROBE
        and row.get("valid_reconstruction") is False
        and row.get("status") == "worker_failure"
        and row.get("failure_category") == "worker_or_protocol_failure"
        and process.get("returncode") == 1
        and process.get("timed_out") is False
        and process.get("fresh_lean_process") is True
        and process.get("attempt_ordinal") == 1
        and process.get("stderr_tail") == PANIC_MESSAGE
        and hashlib.sha256(PANIC_MESSAGE.encode("utf-8")).hexdigest()
        == PANIC_STDERR_SHA256
        and not raw_path.exists()
        and _input_exact(inp)
        and inp.get("cell_id") == lock["cell_id"]
        and inp.get("job_id") == lock["job_id"]
        and inp.get("probe") == AFFECTED_PROBE
        and inp.get("candidate", {}).get("branch_id") == AFFECTED_BRANCH_ID
        and file_sha256(control_path) == lock["control_sha256"]
        and control.get("valid_reconstruction") is True
        and control.get("candidate_executable") is True
        and control.get("candidate_endpoint_sha256")
        == AFFECTED_ENDPOINT_SHA256
        and control.get("branch_id") == AFFECTED_BRANCH_ID
        and control.get("mode") == "candidate_only"
    )
    if not exact:
        raise ValueError(f"locked Lean panic evidence changed: {lock['cell_id']}")
    return {
        **lock,
        "target_id": AFFECTED_TARGET_ID,
        "dataset": AFFECTED_DATASET,
        "branch_id": AFFECTED_BRANCH_ID,
        "candidate_tactic": AFFECTED_CANDIDATE_TACTIC,
        "probe": AFFECTED_PROBE,
        "candidate_endpoint_sha256": AFFECTED_ENDPOINT_SHA256,
        "stderr_sha256": PANIC_STDERR_SHA256,
    }


def load_fix1_corpus(root: Path = ARTIFACT_ROOT) -> dict[str, Any]:
    """Validate all original jobs while retaining exactly three locked panics."""
    root = Path(root).resolve()
    design = load_execution_design(root)
    planned = read_jsonl(design["jobs_path"])
    if len(planned) != EXPECTED_JOBS:
        raise ValueError("frozen confirmation job count changed")
    jobs: list[dict[str, Any]] = []
    cells_by_job: dict[str, list[dict[str, Any]]] = {}
    index: list[dict[str, Any]] = []
    job_ledger: list[dict[str, Any]] = []
    seen: set[str] = set()
    observed_invalid: set[str] = set()
    validated_anomalies: list[dict[str, Any]] = []
    cells_root = (root / "confirmation/execution/cells").resolve()
    for plan in planned:
        job_path = root / "confirmation/execution/jobs" / f"{plan['job_id']}.json"
        job = read_json(job_path)
        assert_sealed(job, f"Fix1 source job {plan['job_id']}")
        if not (
            job.get("schema") == JOB_SCHEMA
            and job.get("job") == plan
            and job.get("job_id") == plan["job_id"]
            and job.get("policy") == plan["policy"]
        ):
            raise ValueError("Fix1 source job identity changed")
        cell_pairs: list[tuple[Path, dict[str, Any]]] = []
        receipt_ledger: list[dict[str, str]] = []
        for receipt in job["cell_receipts"]:
            path = Path(receipt["path"]).resolve()
            if path.parent != cells_root:
                raise ValueError("Fix1 source cell escaped the frozen cells directory")
            if not path.is_file() or file_sha256(path) != receipt["sha256"]:
                raise ValueError("Fix1 source cell file changed")
            row = read_json(path)
            assert_sealed(row, f"Fix1 source cell {receipt['cell_id']}")
            if not (
                row.get("schema") == ROW_SCHEMA
                and row.get("cell_id") == receipt["cell_id"]
                and row.get("job_id") == plan["job_id"]
                and row.get("target_id") == plan["target_id"]
                and row.get("policy") == plan["policy"]
                and row["cell_id"] not in seen
            ):
                raise ValueError("Fix1 source cell identity or uniqueness changed")
            seen.add(row["cell_id"])
            if row.get("valid_reconstruction") is not True:
                observed_invalid.add(row["cell_id"])
            cell_pairs.append((path, row))
            receipt_ledger.append({
                "cell_id": row["cell_id"], "sha256": receipt["sha256"]
            })
            index.append({
                "cell_id": row["cell_id"], "job_id": plan["job_id"],
                "target_id": plan["target_id"], "dataset": plan["dataset"],
                "policy": plan["policy"], "mode": row["mode"],
                "path": str(path), "sha256": receipt["sha256"],
                "record_sha256": row["record_sha256"],
                "operational_anomaly": row["cell_id"] in ANOMALY_BY_CELL,
            })
        cells = [row for _, row in cell_pairs]
        invalid = sum(row.get("valid_reconstruction") is not True for row in cells)
        anomaly_lock = ANOMALY_BY_JOB.get(plan["job_id"])
        expected_invalid = 1 if anomaly_lock else 0
        if not (
            len(cells) == job["process_calls"] == len(job["cell_ids"])
            and [row["cell_id"] for row in cells] == job["cell_ids"]
            and sum(row["mode"] == "candidate_only" for row in cells)
            == job["candidate_process_calls"] == CANDIDATES_PER_ROOT
            and sum(row["mode"] == "candidate_probe" for row in cells)
            == job["downstream_process_calls"]
            and sum(row.get("valid_reconstruction") is True for row in cells)
            == job["valid_reconstruction_cells"]
            and invalid == job["invalid_cells"] == expected_invalid
            and job["candidate_stage_exact"] is True
            and job["all_fresh_lean_processes"] is True
            and job["all_attempt_ordinals_one"] is True
            and job["maximum_process_calls_respected"] is True
            and job["within_common_time_budget"] is True
            and job["scientific_retry_count"] == 0
            and job["manual_reconciliation_count"] == 0
        ):
            raise ValueError(f"Fix1 source job accounting failed: {plan['job_id']}")
        if anomaly_lock:
            validated_anomalies.append(
                _validate_locked_anomaly(root, job, cell_pairs, anomaly_lock)
            )
        jobs.append(job)
        cells_by_job[plan["job_id"]] = cells
        job_ledger.append({
            "job_id": plan["job_id"], "sha256": file_sha256(job_path),
            "cell_receipts": receipt_ledger,
        })
    if observed_invalid != set(ANOMALY_BY_CELL):
        raise ValueError("Fix1 invalid-cell census differs from the locked three")
    if {row["cell_id"] for row in validated_anomalies} != set(ANOMALY_BY_CELL):
        raise ValueError("Fix1 locked anomaly validation is incomplete")
    return {
        "root": root,
        "design": design,
        "planned": planned,
        "jobs": jobs,
        "cells_by_job": cells_by_job,
        "index": index,
        "job_ledger_sha256": json_sha256(job_ledger),
        "jobs_count": len(jobs),
        "cells_count": len(index),
        "invalid_cells": len(observed_invalid),
        "anomalies": sorted(validated_anomalies, key=lambda row: row["policy"]),
        "affected_roots": [AFFECTED_TARGET_ID],
    }


def validate_fix1_amendment(root: Path = ARTIFACT_ROOT) -> dict[str, Any]:
    root = Path(root).resolve()
    path = root / AMENDMENT_RELATIVE
    value = read_json(path)
    assert_sealed(value, "Exp59 operational-anomaly Fix1 amendment")
    corpus = load_fix1_corpus(root)
    if not (
        value.get("schema") == AMENDMENT_SCHEMA
        and value.get("fix1_protocol_version") == FIX1_PROTOCOL_VERSION
        and value.get("mechanical_fix_id") == FIX1_MECHANICAL_ID
        and value.get("source_confirmation_protocol_version")
        == CONFIRMATION_PROTOCOL_VERSION
        and value.get("source_design_record_sha256")
        == corpus["design"]["record_sha256"]
        and value.get("source_job_ledger_sha256")
        == corpus["job_ledger_sha256"]
        and value.get("source_jobs") == EXPECTED_JOBS
        and value.get("source_cells") == corpus["cells_count"]
        and value.get("locked_operational_anomaly_cells") == 3
        and value.get("locked_operational_anomaly_ledger") == corpus["anomalies"]
        and value.get("affected_roots") == [AFFECTED_TARGET_ID]
        and value.get("affected_root_count") == 1
        and value.get("analysis_absent_before_amendment") is True
        and value.get("audit_absent_before_amendment") is True
        and value.get("original_receipts_rewritten") is False
        and value.get("efficiency_estimand_remains_64_root_process_call_accounting")
        is True
        and value.get("registered_coverage_estimand_complete") is False
        and value.get("lean_executed_by_amendment") is False
        and value.get("continuation_probes_executed_by_amendment") == 0
        and value.get("scientific_retry_count") == 0
        and value.get("manual_reconciliation_count") == 0
        and value.get("amendment_gate") is True
    ):
        raise ValueError("Exp59 operational-anomaly Fix1 amendment changed")
    return {**value, "path": str(path), "sha256": file_sha256(path), "corpus": corpus}
