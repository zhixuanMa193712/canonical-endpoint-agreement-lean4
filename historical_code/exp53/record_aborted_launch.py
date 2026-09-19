"""Freeze a machine-verifiable receipt for the incomplete parallel Exp53 launch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from exp53_protocol import atomic_json_dump, file_sha256, json_sha256, read_json


PACKAGE_ROOT = Path(__file__).resolve().parent


def record(artifact_root: Path) -> dict[str, Any]:
    artifact_root = artifact_root.resolve()
    execution_root = artifact_root / "execution/shards"
    if (artifact_root / "analysis/summary.json").exists():
        raise ValueError("comparison analysis exists in the aborted artifact")
    ledger = []
    for path in sorted(p for p in execution_root.rglob("*") if p.is_file()):
        ledger.append({
            "path": str(path.relative_to(artifact_root)),
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        })
    claims = sorted(execution_root.glob("shard-*/claims/*/*.json"))
    rows = sorted(execution_root.glob("shard-*/rows/*/*.json"))
    summaries = sorted(execution_root.glob("shard-*/summary.json"))
    row_keys = {
        (path.parents[2].name, path.parent.name, path.name) for path in rows
    }
    missing_claims = [
        path for path in claims
        if (path.parents[2].name, path.parent.name, path.name) not in row_keys
    ]
    if not (
        len(claims) == 15
        and len(rows) == 14
        and len(summaries) == 3
        and len(missing_claims) == 1
        and {path.parent.name for path in summaries}
        == {"shard-01", "shard-02", "shard-03"}
    ):
        raise ValueError("aborted parallel-launch dimensions changed")
    row_values = [read_json(path) for path in rows]
    ledger_path = PACKAGE_ROOT / "frozen/aborted_parallel_launch_ledger.json"
    atomic_json_dump(ledger, ledger_path)
    preflight = read_json(artifact_root / "preflight/worker_compile.json")
    value = {
        "version": 1,
        "schema": "experiment53-aborted-parallel-launch-receipt-v1",
        "freeze_identity_sha256": preflight["freeze_identity_sha256"],
        "shards_completed": 3,
        "claims_created": len(claims),
        "rows_persisted": len(rows),
        "candidate_attempts_in_persisted_rows": sum(
            len(row.get("candidates", [])) for row in row_values
        ),
        "scientific_root_process_without_row": 1,
        "missing_row_theorem_id": read_json(missing_claims[0])["theorem_id"],
        "comparison_analysis_executed": False,
        "manual_reconciliation_count": 0,
        "ledger_entries": len(ledger),
        "ledger_sha256": file_sha256(ledger_path),
        "ledger_identity_sha256": json_sha256(ledger),
        "disposition": "aborted_not_a_completed_exp53_run",
    }
    atomic_json_dump(
        value, PACKAGE_ROOT / "frozen/aborted_parallel_launch_receipt.json"
    )
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-root",
        default="artifacts/v53/cross_machine_subset_aborted_parallel_race_20260825",
    )
    return parser.parse_args()


if __name__ == "__main__":
    record(Path(parse_args().artifact_root))
