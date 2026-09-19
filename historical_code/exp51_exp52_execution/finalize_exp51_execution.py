"""Reconstruct and finalize Exp51 smoke or scientific shard execution.

Completion is defined by one immutable receipt for every frozen root.  The
23-candidate condition applies only to evaluable rows, matching the frozen
evaluability gates.  No theorem is executed by this offline finalizer.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from alignment_protocol import *  # noqa: F401,F403


def amendment_sha(root: Path) -> str:
    return file_sha256(root / AMENDMENT_RELATIVE)


def assert_row(
    row: dict[str, Any], target: dict[str, Any], phase: str, cfg_sha: str
) -> None:
    if not (
        row.get("protocol_version") == base.PROTOCOL_VERSION
        and row.get("mode") == phase
        and row.get("config_sha256") == cfg_sha
        and row.get("theorem_id") == target["theorem_id"]
        and row.get("source_file_sha256") == target["source_file_sha256"]
        and row.get("candidate_order") == target["alternatives"]
        and row.get("record_sha256") == json_sha256({
            key: item for key, item in row.items() if key != "record_sha256"
        })
    ):
        raise ValueError(f"Exp51 row identity changed: {target['theorem_id']}")
    if row.get("worker_ok") is True and not (
        len(row.get("candidates", [])) == CANDIDATES_PER_ROOT
        and row.get("complete_candidate_order") is True
    ):
        raise ValueError(
            f"evaluable row lacks all {CANDIDATES_PER_ROOT} attempts: "
            f"{target['theorem_id']}"
        )


def expected_phase_targets(
    cfg: dict[str, Any], targets: list[dict[str, Any]], phase: str
) -> list[tuple[int, dict[str, Any], int]]:
    if phase == "smoke":
        ids = list(cfg.get("smoke_target_ids", []))
        identity = set(ids)
        selected = [
            (index, target, 0)
            for index, target in enumerate(targets)
            if target["theorem_id"] in identity
        ]
        if len(ids) != len(identity) or len(selected) != len(ids):
            raise ValueError("frozen smoke target identity changed")
        return selected
    return [
        (index, target, shard_index(index, EXP51_SHARD_COUNT))
        for index, target in enumerate(targets)
    ]


def row_path(root: Path, phase: str, target: dict[str, Any], shard: int) -> Path:
    if phase == "scientific":
        expected = exp51_row_path(root, target)
        if expected.parts[-4] != f"shard-{shard:02d}":
            raise ValueError("Exp51 deterministic shard path changed")
        return expected
    return (
        root / "smoke/shards/shard-00/theorems" / safe_slug(target["slug"])
        / f"{target['rid']}.json"
    )


def validate_shard_summaries(
    root: Path,
    phase: str,
    expected: list[tuple[int, dict[str, Any], int]],
    cfg_sha: str,
    amend_sha: str,
) -> None:
    shard_values = [0] if phase == "smoke" else list(range(EXP51_SHARD_COUNT))
    for shard in shard_values:
        path = root / phase / "shards" / f"shard-{shard:02d}" / "summary.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        value = read_json(path)
        assigned = [item for item in expected if item[2] == shard]
        assignment = [
            {"frozen_target_index": index, "theorem_id": target["theorem_id"]}
            for index, target, _ in assigned
        ]
        if not (
            value.get("shard_gate") is True
            and value.get("phase") == phase
            and value.get("shard_index") == shard
            and value.get("shard_count") == EXP51_SHARD_COUNT
            and value.get("config_sha256") == cfg_sha
            and value.get("amendment_sha256") == amend_sha
            and value.get("assignment_sha256") == json_sha256(assignment)
            and value.get("roots_expected") == len(assigned)
            and value.get("root_receipts") == len(assigned)
            and value.get("all_evaluable_rows_have_23_attempts") is True
            and value.get("manual_reconciliation_count") == 0
        ):
            raise ValueError(f"Exp51 shard summary changed: {phase}/{shard:02d}")


def finalize(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    source = validate_amendment(root)
    cfg, targets, _protocol, _amendment = load_source_bundle(root)
    cfg_sha = source["config_sha256"]
    amend_sha = amendment_sha(root)
    expected = expected_phase_targets(cfg, targets, args.phase)
    if args.phase == "scientific":
        smoke = read_json(root / "smoke/summary.json")
        if not (
            smoke.get("smoke_gate") is True
            and smoke.get("config_sha256") == cfg_sha
            and smoke.get("amendment_sha256") == amend_sha
        ):
            raise ValueError("fix3 smoke did not pass")
    validate_shard_summaries(root, args.phase, expected, cfg_sha, amend_sha)
    rows: list[dict[str, Any]] = []
    ledger = []
    for frozen_index, target, shard in expected:
        path = row_path(root, args.phase, target, shard)
        receiptp = (
            root / args.phase / "shards" / f"shard-{shard:02d}" / "receipts"
            / safe_slug(target["slug"]) / f"{target['rid']}.json"
        )
        if not path.is_file() or not receiptp.is_file():
            raise FileNotFoundError(path if not path.is_file() else receiptp)
        row, receipt = read_json(path), read_json(receiptp)
        assert_row(row, target, args.phase, cfg_sha)
        if not (
            receipt.get("amendment_sha256") == amend_sha
            and receipt.get("phase") == args.phase
            and receipt.get("frozen_target_index") == frozen_index
            and receipt.get("theorem_id") == target["theorem_id"]
            and receipt.get("target_identity_sha256")
            == target["target_identity_sha256"]
            and receipt.get("worker_row_sha256") == file_sha256(path)
            and receipt.get("worker_ok") is (row.get("worker_ok") is True)
            and receipt.get("candidate_attempts")
            == len(row.get("candidates", []))
            and receipt.get("manual_reconciliation_count") == 0
        ):
            raise ValueError(f"Exp51 row receipt changed: {target['theorem_id']}")
        rows.append(row)
        ledger.append({
            "frozen_target_index": frozen_index,
            "shard_index": shard,
            "slug": target["slug"],
            "rid": target["rid"],
            "theorem_id": target["theorem_id"],
            "row": str(path),
            "row_sha256": file_sha256(path),
            "receipt": str(receiptp),
            "receipt_sha256": file_sha256(receiptp),
            "worker_ok": row.get("worker_ok") is True,
            "candidate_attempts": len(row.get("candidates", [])),
        })
    if len({item["theorem_id"] for item in ledger}) != len(expected):
        raise ValueError("Exp51 finalized rows are not mutually exclusive")
    row_indexp = root / args.phase / "row_index.jsonl"
    if row_indexp.is_file() and read_jsonl(row_indexp) != ledger:
        raise ValueError("existing row index differs from immutable shard evidence")
    if not row_indexp.is_file():
        atomic_jsonl_dump(ledger, row_indexp)
    failures = Counter(
        row.get("error_type", "worker_gate") for row in rows
        if row.get("worker_ok") is not True
    )
    repo_rows = []
    for slug in [item["slug"] for item in cfg["repositories"]]:
        selected_rows = [row for row in rows if row["slug"] == slug]
        repo_failures = Counter(
            row.get("error_type", "worker_gate") for row in selected_rows
            if row.get("worker_ok") is not True
        )
        repo_rows.append({
            "slug": slug,
            "attempted": len(selected_rows),
            "evaluable": sum(row.get("worker_ok") is True for row in selected_rows),
            "gate_failures": dict(sorted(repo_failures.items())),
        })
    evaluable = sum(row.get("worker_ok") is True for row in rows)
    candidate_attempts = sum(len(row.get("candidates", [])) for row in rows)
    all_evaluable_complete = all(
        row.get("worker_ok") is not True
        or len(row.get("candidates", [])) == CANDIDATES_PER_ROOT
        for row in rows
    )
    value: dict[str, Any] = {
        "version": 1,
        "protocol_version": base.PROTOCOL_VERSION,
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "amendment_sha256": amend_sha,
        "phase": args.phase,
        "config_sha256": cfg_sha,
        "targets_sha256": source["targets_sha256"],
        "shards_expected": 1 if args.phase == "smoke" else EXP51_SHARD_COUNT,
        "roots_expected": len(expected),
        "root_receipts": len(ledger),
        "roots_attempted": len(rows),
        "evaluable_roots": evaluable,
        "unevaluable_roots": len(rows) - evaluable,
        "candidate_attempts_recorded": candidate_attempts,
        "candidate_attempts_expected_on_evaluable_roots": (
            evaluable * CANDIDATES_PER_ROOT
        ),
        "all_evaluable_rows_have_23_attempts": all_evaluable_complete,
        "failure_categories": dict(sorted(failures.items())),
        "repository_execution": repo_rows,
        "row_index": str(row_indexp),
        "row_index_sha256": file_sha256(row_indexp),
        "manual_reconciliation_count": 0,
        "scientific_retry_count": 0,
    }
    value["execution_complete"] = bool(
        value["root_receipts"] == value["roots_expected"]
        and value["roots_attempted"] == value["roots_expected"]
        and all_evaluable_complete
    )
    if args.phase == "smoke":
        value["smoke_gate"] = bool(
            value["execution_complete"] and evaluable == len(expected)
        )
        value["next_step"] = (
            "Run the sixteen frozen Exp51 scientific shards."
            if value["smoke_gate"] else "STOP; preserve immutable smoke evidence."
        )
    else:
        value["execution_gate"] = value["execution_complete"]
        value["next_step"] = (
            "Run frozen offline Fix3 analysis."
            if value["execution_gate"] else "STOP; preserve immutable shard evidence."
        )
    summaryp = root / args.phase / "summary.json"
    if summaryp.is_file() and read_json(summaryp) != value:
        raise ValueError("existing execution summary differs from reconstruction")
    atomic_json_dump(value, summaryp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(SCIENTIFIC_ROOT))
    parser.add_argument("--phase", choices=("smoke", "scientific"), required=True)
    return parser.parse_args()


if __name__ == "__main__":
    result = finalize(parse_args())
    gate = result.get("smoke_gate") if result.get("phase") == "smoke" else result.get("execution_gate")
    raise SystemExit(0 if gate is True else 2)
