"""Finalize 32 Exp52 shards into the frozen cell-plan order.

This is an accounting and integrity step only.  It performs no endpoint
analysis and never invokes Lean.  The combined ``cells.jsonl`` is ordered
exactly like ``selection/execution_cells.jsonl``.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from alignment_protocol import *  # noqa: F401,F403
from experiment52_live_worker import (
    LEAN_SOURCE_SHA256,
    WORKER_SCHEMA,
)


FINALIZE_SCHEMA = "experiment52-finalized-sharded-execution-fix4-v1"


def _record_sha(value: Mapping[str, Any]) -> str:
    return json_sha256({
        key: item for key, item in value.items() if key != "record_sha256"
    })


def _load_plan(
    root: Path, source: Mapping[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]], Path, str]:
    summaryp = root / "exp52/selection/summary.json"
    if not summaryp.is_file():
        raise FileNotFoundError(summaryp)
    summary = read_json(summaryp)
    planp = root / str(summary.get(
        "execution_cell_plan", "exp52/selection/execution_cells.jsonl"
    ))
    if not planp.is_file():
        raise FileNotFoundError(planp)
    plan = read_jsonl(planp)
    if not (
        summary.get("selection_complete") is True
        and summary.get("alignment_version") == SOURCE_FIX3_ALIGNMENT_VERSION
        and summary.get("mechanical_fix_id") == SOURCE_FIX3_FIX_ID
        and summary.get("amendment_sha256")
        == source["source_fix3_amendment_sha256"]
        and summary.get("exp52_protocol_sha256") == source["protocol_sha256"]
        and summary.get("execution_cells") == len(plan)
        and summary.get("execution_cell_plan_sha256") == file_sha256(planp)
        and len({row.get("cell_id") for row in plan}) == len(plan)
        and all(row.get("record_sha256") == _record_sha(row) for row in plan)
    ):
        raise ValueError("Exp52 execution-cell plan changed before finalization")
    return summary, plan, planp, file_sha256(planp)


def _validate_row(
    row: Mapping[str, Any], plan: Mapping[str, Any], index: int,
    source: Mapping[str, Any], plan_sha: str,
) -> None:
    if not (
        row.get("schema") == WORKER_SCHEMA
        and row.get("alignment_version") == EXECUTION_ALIGNMENT_VERSION
        and row.get("mechanical_fix_id") == EXECUTION_FIX_ID
        and row.get("cell_index") == index
        and row.get("cell_id") == plan["cell_id"]
        and row.get("root_id") == plan["root_id"]
        and row.get("theorem_id") == plan["theorem_id"]
        and row.get("pair_id") == plan["pair_id"]
        and row.get("pair_role") == plan["pair_role"]
        and row.get("side") == plan["side"]
        and row.get("probe") == plan["probe"]
        and row.get("probe_index") == plan["probe_index"]
        and row.get("repeat_kind") == plan["repeat_kind"]
        and row.get("amendment_sha256") == source["amendment_sha256"]
        and row.get("exp52_protocol_sha256") == source["protocol_sha256"]
        and row.get("selection_ledger_sha256") == plan_sha
        and row.get("selection_record_sha256")
        == plan["selection_record_sha256"]
        and row.get("cell_plan_record_sha256") == plan["record_sha256"]
        and row.get("source_exp51_row_sha256")
        == plan["source_exp51_row_sha256"]
        and row.get("candidate_tactic") == plan["candidate"]["tactic"]
        and row.get("candidate_head") == plan["candidate"]["head"]
        and row.get("candidate_position_frozen")
        == plan["candidate"]["candidate_index"]
        and row.get("candidate_record_sha256")
        == plan["candidate"]["candidate_record_sha256"]
        and row.get("expected_candidate_endpoint")
        == plan["candidate"]["endpoint"]
        and row.get("record_complete") is True
        and row.get("scientific_retry_permitted") is False
        and row.get("manual_reconciliation_count") == 0
        and row.get("record_sha256") == _record_sha(row)
    ):
        raise ValueError(f"Exp52 finalized cell differs from plan: {index}")


def finalize(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    source = validate_amendment(root)
    selection, plan, planp, plan_sha = _load_plan(root, source)
    preflightp = root / EXP52_PREFLIGHT_RELATIVE
    if not preflightp.is_file():
        raise FileNotFoundError(preflightp)
    preflight = read_json(preflightp)
    if not (
        preflight.get("compile_gate") is True
        and preflight.get("amendment_sha256") == source["amendment_sha256"]
        and preflight.get("execution_cell_plan_sha256") == plan_sha
        and preflight.get("lean_source_sha256") == LEAN_SOURCE_SHA256
    ):
        raise ValueError("Exp52 preflight differs from finalized execution")
    shard_summaries: list[dict[str, Any]] = []
    for shard in range(EXP52_SHARD_COUNT):
        path = root / "exp52/execution/shards" / f"shard-{shard:02d}" / "summary.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        value = read_json(path)
        expected_count = sum(
            shard_index(index, EXP52_SHARD_COUNT) == shard
            for index in range(len(plan))
        )
        if not (
            value.get("alignment_version") == EXECUTION_ALIGNMENT_VERSION
            and value.get("mechanical_fix_id") == EXECUTION_FIX_ID
            and value.get("amendment_sha256") == source["amendment_sha256"]
            and value.get("selection_ledger_sha256") == plan_sha
            and value.get("shard_index") == shard
            and value.get("shard_count") == EXP52_SHARD_COUNT
            and value.get("cells_expected") == expected_count
            and value.get("cells_recorded") == expected_count
            and value.get("shard_completion_gate") is True
            and value.get("shard_gate") is True
            and value.get("all_fresh_lean_processes")
            is (
                value.get("fresh_lean_process_receipts") == expected_count
            )
            and value.get("all_worker_process_launch_receipts_exact")
            is (
                value.get("worker_process_launch_receipts") == expected_count
            )
            and value.get("scientific_retry_count") == 0
            and value.get("manual_reconciliation_count") == 0
        ):
            raise ValueError(f"Exp52 shard summary failed: {shard}")
        shard_summaries.append(value)
    rows: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    exact_launch_receipts = 0
    for index, cell in enumerate(plan):
        shard = shard_index(index, EXP52_SHARD_COUNT)
        shard_root = root / "exp52/execution/shards" / f"shard-{shard:02d}"
        rowp = shard_root / "rows" / f"{cell['cell_id']}.json"
        receiptp = shard_root / "receipts" / f"{cell['cell_id']}.json"
        if not rowp.is_file() or not receiptp.is_file():
            raise FileNotFoundError(rowp if not rowp.is_file() else receiptp)
        row, receipt = read_json(rowp), read_json(receiptp)
        _validate_row(row, cell, index, source, plan_sha)
        inputp = shard_root / "inputs" / f"{cell['cell_id']}.json"
        if not inputp.is_file():
            raise FileNotFoundError(inputp)
        cell_input = read_json(inputp)
        input_identity = json_sha256({
            key: item for key, item in cell_input.items()
            if key != "input_identity_sha256"
        })
        if not (
            cell_input.get("cell_id") == cell["cell_id"]
            and cell_input.get("cell_index") == index
            and cell_input.get("amendment_sha256")
            == source["amendment_sha256"]
            and cell_input.get("selection_ledger_sha256") == plan_sha
            and cell_input.get("candidate_record_sha256")
            == cell["candidate"]["candidate_record_sha256"]
            and cell_input.get("expected_candidate_endpoint")
            == cell["candidate"]["endpoint"]
            and cell_input.get("input_identity_sha256") == input_identity
            and row.get("input_identity_sha256") == input_identity
        ):
            raise ValueError(f"Exp52 cell input identity changed: {index}")
        launch_raw = receipt.get("worker_process_receipt")
        launch_exact = False
        launchp: Path | None = None
        if launch_raw is not None:
            launchp = Path(str(launch_raw)).resolve()
            expected_launch_root = (shard_root / "worker_processes").resolve()
            if not (
                launchp.is_file()
                and launchp.is_relative_to(expected_launch_root)
                and receipt.get("worker_process_receipt_sha256")
                == file_sha256(launchp)
            ):
                raise ValueError(f"Exp52 worker launch receipt changed: {index}")
            launch = read_json(launchp)
            command = launch.get("command")
            expected_command_tail = [
                str(Path(__file__).resolve().with_name(
                    "experiment52_live_worker.py"
                )),
                "--input", str(inputp), "--output", str(rowp),
                "--runtime-root", str(shard_root / "runtime"),
                "--timeout", str(LEAN_TIMEOUT_SECONDS),
            ]
            launch_exact = bool(
                launch.get("schema")
                == PROCESS_LAUNCH_SCHEMA
                and launch.get("alignment_version")
                == EXECUTION_ALIGNMENT_VERSION
                and launch.get("mechanical_fix_id") == EXECUTION_FIX_ID
                and launch.get("amendment_sha256")
                == source["amendment_sha256"]
                and launch.get("selection_ledger_sha256") == plan_sha
                and launch.get("cell_id") == cell["cell_id"]
                and launch.get("cell_index") == index
                and launch.get("input") == str(inputp)
                and launch.get("input_sha256") == file_sha256(inputp)
                and launch.get("input_identity_sha256") == input_identity
                and launch.get("output") == str(rowp)
                and type(launch.get("worker_pid")) is int
                and int(launch["worker_pid"]) > 0
                and launch.get("attempt_ordinal") == 1
                and launch.get("scientific_retry_permitted") is False
                and isinstance(command, list)
                and len(command) == len(expected_command_tail) + 1
                and command[1:] == expected_command_tail
                and launch.get("command_sha256")
                == json_sha256(command)
                and launch.get("record_sha256") == _record_sha(launch)
            )
            if not launch_exact:
                raise ValueError(
                    f"Exp52 worker launch receipt identity changed: {index}"
                )
        elif not (
            receipt.get("worker_process_receipt_sha256") is None
            and receipt.get("worker_process_receipt_exact") is False
        ):
            raise ValueError(f"Exp52 absent launch receipt changed: {index}")
        exact_launch_receipts += int(launch_exact)
        if not (
            receipt.get("cell_index") == index
            and receipt.get("cell_id") == cell["cell_id"]
            and receipt.get("amendment_sha256") == source["amendment_sha256"]
            and receipt.get("selection_ledger_sha256") == plan_sha
            and receipt.get("worker_row") == str(rowp)
            and receipt.get("worker_row_sha256") == file_sha256(rowp)
            and receipt.get("record_complete") is True
            and receipt.get("attempt_ordinal") == 1
            and receipt.get("fresh_lean_process")
            is (row.get("process", {}).get("fresh_lean_process") is True)
            and receipt.get("scientific_retry_count") == 0
            and receipt.get("manual_reconciliation_count") == 0
            and receipt.get("worker_process_receipt_exact") is launch_exact
            and receipt.get("record_sha256") == _record_sha(receipt)
        ):
            raise ValueError(f"Exp52 cell receipt changed: {index}")
        rows.append(row)
        ledger.append({
            "cell_index": index,
            "cell_id": cell["cell_id"],
            "shard_index": shard,
            "row": str(rowp),
            "row_sha256": file_sha256(rowp),
            "receipt": str(receiptp),
            "receipt_sha256": file_sha256(receiptp),
            "input": str(inputp),
            "input_sha256": file_sha256(inputp),
            "worker_process_receipt": str(launchp) if launchp else None,
            "worker_process_receipt_sha256": (
                file_sha256(launchp) if launchp else None
            ),
        })
    execution_root = root / "exp52/execution"
    cellsp = execution_root / "cells.jsonl"
    ledgerp = execution_root / "row_index.jsonl"
    if cellsp.is_file() and read_jsonl(cellsp) != rows:
        raise ValueError("existing combined Exp52 cells differ from shard rows")
    if ledgerp.is_file() and read_jsonl(ledgerp) != ledger:
        raise ValueError("existing Exp52 row index differs from shard receipts")
    if not cellsp.is_file():
        atomic_jsonl_dump(rows, cellsp)
    if not ledgerp.is_file():
        atomic_jsonl_dump(ledger, ledgerp)
    statuses = Counter(str(row.get("probe_status")) for row in rows)
    failures = Counter(
        str(row.get("failure_category")) for row in rows
        if row.get("probe_status") != "success"
    )
    fresh = sum(
        row.get("process", {}).get("fresh_lean_process") is True
        for row in rows
    )
    attempts_one = all(
        row.get("process", {}).get("attempt_ordinal") == 1 for row in rows
    )
    value: dict[str, Any] = {
        "schema": FINALIZE_SCHEMA,
        "version": 1,
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "mechanical_fix_id": EXECUTION_FIX_ID,
        "amendment_sha256": source["amendment_sha256"],
        "exp52_protocol_sha256": source["protocol_sha256"],
        "selection_summary_sha256": file_sha256(
            root / "exp52/selection/summary.json"
        ),
        "execution_cell_plan_sha256": plan_sha,
        "preflight_sha256": file_sha256(preflightp),
        "shards_expected": EXP52_SHARD_COUNT,
        "shards_completed": len(shard_summaries),
        "cells_expected": len(plan),
        "cells_recorded": len(rows),
        "fresh_lean_process_receipts": fresh,
        "worker_process_launch_receipts_exact": exact_launch_receipts,
        "all_attempt_ordinals_one": attempts_one,
        "primary_cells": sum(
            row.get("repeat_kind") == "primary" for row in rows
        ),
        "determinism_audit_cells": sum(
            row.get("repeat_kind") == "determinism_audit" for row in rows
        ),
        "valid_reconstruction_cells": sum(
            row.get("valid_reconstruction") is True for row in rows
        ),
        "probe_status_counts": dict(sorted(statuses.items())),
        "failure_category_counts": dict(sorted(failures.items())),
        "cells": str(cellsp),
        "cells_sha256": file_sha256(cellsp),
        "row_index": str(ledgerp),
        "row_index_sha256": file_sha256(ledgerp),
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
    }
    value["execution_complete"] = bool(
        value["shards_completed"] == value["shards_expected"]
        and value["cells_recorded"] == value["cells_expected"]
        and [row["cell_id"] for row in rows]
        == [row["cell_id"] for row in plan]
    )
    value["all_fresh_lean_processes"] = fresh == len(plan)
    value["all_worker_process_launch_receipts_exact"] = (
        exact_launch_receipts == len(plan)
    )
    value["execution_gate"] = bool(
        value["execution_complete"]
        and attempts_one
        and value["scientific_retry_count"] == 0
        and value["manual_reconciliation_count"] == 0
    )
    value["execution_integrity_gate"] = bool(
        value["execution_gate"]
        and value["all_fresh_lean_processes"]
        and value["all_worker_process_launch_receipts_exact"]
    )
    value["next_step"] = (
        "Run frozen offline Exp52 analysis."
        if value["execution_gate"] else
        "STOP; complete immutable Exp52 cell accounting without retry."
    )
    summaryp = execution_root / "summary.json"
    if summaryp.is_file() and read_json(summaryp) != value:
        raise ValueError("existing Exp52 execution summary changed")
    atomic_json_dump(value, summaryp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(SCIENTIFIC_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    result = finalize(parse_args())
    raise SystemExit(0 if result.get("execution_gate") is True else 2)
