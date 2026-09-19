"""Finalize immutable Exp54 shard accounting before offline analysis."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from experiment54_protocol import *


def finalize(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.artifact_root).resolve()
    frozen = load_freeze(root)
    output = root / "execution/summary.json"
    if output.is_file():
        value = read_json(output)
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value
    rows = []
    shard_summaries = []
    index = []
    for shard in range(SHARD_COUNT):
        shard_root = root / f"execution/shards/shard-{shard:02d}"
        summary_path = shard_root / "summary.json"
        if not summary_path.is_file():
            raise FileNotFoundError(f"missing Exp54 shard {shard:02d}")
        shard_summary = read_json(summary_path)
        shard_summaries.append(shard_summary)
        for path in sorted((shard_root / "rows").glob("*.json")):
            row = read_json(path)
            assert_sealed(row, f"execution row {path.name}")
            rows.append(row)
            index.append(seal({
                "version": VERSION,
                "cell_id": row["cell_id"],
                "cell_index": row["cell"]["cell_index"],
                "policy": row["policy"],
                "path": str(path),
                "sha256": file_sha256(path),
                "row_record_sha256": row["record_sha256"],
            }))
    planned = {cell["cell_id"]: cell for cell in read_jsonl(frozen["cells_path"])}
    observed = {row["cell_id"]: row for row in rows}
    if len(observed) != len(rows):
        raise ValueError("duplicate Exp54 cell rows")
    status_counts = Counter(row.get("probe_status") for row in rows)
    failure_counts = Counter(
        row.get("failure_category") for row in rows
        if row.get("failure_category") is not None
    )
    accounting_exact = set(planned) == set(observed)
    execution_gate = bool(
        accounting_exact
        and len(rows) == EXPECTED_CELLS
        and all(s.get("shard_gate") is True for s in shard_summaries)
        and all(row.get("record_complete") is True for row in rows)
    )
    integrity_gate = bool(
        execution_gate
        and all(row.get("valid_reconstruction") is True for row in rows)
        and all(
            row.get("process", {}).get("fresh_lean_process") is True
            and row.get("process", {}).get("attempt_ordinal") == 1
            for row in rows
        )
        and all(row.get("scientific_retry_count") == 0 for row in rows)
        and all(row.get("manual_reconciliation_count") == 0 for row in rows)
    )
    index.sort(key=lambda row: row["cell_index"])
    atomic_jsonl_dump(index, root / "execution/row_index.jsonl")
    value = {
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "execution_version": EXECUTION_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "shards_expected": SHARD_COUNT,
        "shards_completed": len(shard_summaries),
        "cells_expected": EXPECTED_CELLS,
        "cells_recorded": len(rows),
        "full_cells_expected": EXPECTED_FULL_CELLS,
        "full_cells_recorded": sum(row["policy"] == "full" for row in rows),
        "dedup_cells_expected": EXPECTED_DEDUP_CELLS,
        "dedup_cells_recorded": sum(row["policy"] == "dedup" for row in rows),
        "valid_reconstruction_cells": sum(
            row.get("valid_reconstruction") is True for row in rows
        ),
        "fresh_lean_process_cells": sum(
            row.get("process", {}).get("fresh_lean_process") is True
            for row in rows
        ),
        "probe_status_counts": dict(status_counts),
        "failure_category_counts": dict(failure_counts),
        "cell_accounting_exact": accounting_exact,
        "all_attempt_ordinals_one": all(
            row.get("process", {}).get("attempt_ordinal") == 1 for row in rows
        ),
        "scientific_retry_count": sum(
            row.get("scientific_retry_count", 0) for row in rows
        ),
        "manual_reconciliation_count": sum(
            row.get("manual_reconciliation_count", 0) for row in rows
        ),
        "row_index": str(root / "execution/row_index.jsonl"),
        "row_index_sha256": file_sha256(root / "execution/row_index.jsonl"),
        "execution_complete": execution_gate,
        "execution_gate": execution_gate,
        "execution_integrity_gate": integrity_gate,
        "next_step": (
            "Run frozen offline Exp54 analysis."
            if integrity_gate else "STOP; preserve incomplete or invalid execution."
        ),
    }
    atomic_json_dump(value, output)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--artifact-root", default=str(artifact_root()))
    return p.parse_args()


if __name__ == "__main__":
    finalize(parse_args())
