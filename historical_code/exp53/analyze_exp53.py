"""Compare Exp53 second-machine rows with frozen Exp51 content projections."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from exp53_protocol import *


def leaf_differences(expected: Any, observed: Any, prefix: str = "") -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(expected, dict) and isinstance(observed, dict):
        for key in sorted(set(expected) | set(observed)):
            path = f"{prefix}.{key}" if prefix else key
            out.extend(leaf_differences(expected.get(key), observed.get(key), path))
    elif isinstance(expected, list) and isinstance(observed, list):
        for index in range(max(len(expected), len(observed))):
            left = expected[index] if index < len(expected) else None
            right = observed[index] if index < len(observed) else None
            out.extend(leaf_differences(left, right, f"{prefix}[{index}]"))
    elif expected != observed:
        out.append({"path": prefix, "expected": expected, "observed": observed})
    return out


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    subset, receipt = validate_frozen()
    artifact_root = Path(args.artifact_root).resolve()
    preflight = read_json(artifact_root / "preflight/worker_compile.json")
    reference_index = read_json(PACKAGE_ROOT / "frozen/reference_index.json")
    references = {row["theorem_id"]: row for row in reference_index}
    observed_rows: dict[str, dict[str, Any]] = {}
    shard_summaries = []
    for shard in range(args.shard_count):
        shard_root = artifact_root / f"execution/shards/shard-{shard:02d}"
        summary = read_json(shard_root / "summary.json")
        shard_summaries.append(summary)
        for path in sorted((shard_root / "rows").glob("*/*.json")):
            row = read_json(path)
            observed_rows[row["theorem_id"]] = row
    mismatches: list[dict[str, Any]] = []
    roots_exact = 0
    for target in subset["targets"]:
        theorem_id = target["theorem_id"]
        observed = observed_rows.get(theorem_id)
        if observed is None:
            mismatches.append({
                "theorem_id": theorem_id,
                "slug": target["slug"],
                "category": "missing_row",
                "differences": [],
            })
            continue
        ref_entry = references[theorem_id]
        expected = read_json(PACKAGE_ROOT / ref_entry["path"])
        expected.pop("reference_projection_sha256", None)
        projection = row_projection(observed)
        differences = leaf_differences(expected, projection)
        if differences:
            mismatches.append({
                "theorem_id": theorem_id,
                "rid": target["rid"],
                "slug": target["slug"],
                "category": "content_mismatch",
                "differences": differences,
            })
        else:
            roots_exact += 1
    integrity = bool(
        preflight.get("compile_gate") is True
        and preflight.get("freeze_identity_sha256") == receipt["identity_sha256"]
        and len(shard_summaries) == args.shard_count
        and all(row.get("shard_gate") is True for row in shard_summaries)
        and len(observed_rows) == ROOTS
        and all(row.get("worker_ok") is True for row in observed_rows.values())
    )
    decision = (
        "invalid_execution" if not integrity
        else "cross_machine_exact" if not mismatches
        else "cross_machine_mismatch"
    )
    mismatch_path = artifact_root / "analysis/mismatch_ledger.jsonl"
    atomic_jsonl_dump(mismatches, mismatch_path)
    value = {
        "version": 1,
        "schema": RESULT_SCHEMA,
        "protocol_version": PROTOCOL_VERSION,
        "freeze_identity_sha256": receipt["identity_sha256"],
        "repositories": REPOSITORIES,
        "roots_expected": ROOTS,
        "roots_recorded": len(observed_rows),
        "roots_exact": roots_exact,
        "candidate_attempts_expected": ROOTS * CANDIDATES_PER_ROOT,
        "candidate_attempts_recorded": sum(
            len(row.get("candidates", [])) for row in observed_rows.values()
        ),
        "mismatch_count": len(mismatches),
        "mismatch_field_count": sum(len(row["differences"]) for row in mismatches),
        "mismatch_categories": dict(Counter(row["category"] for row in mismatches)),
        "mismatch_ledger": str(mismatch_path),
        "mismatch_ledger_sha256": file_sha256(mismatch_path),
        "execution_integrity_gate": integrity,
        "manual_reconciliation_count": 0,
        "decision_label": decision,
        "source_exp51_decision_unchanged": True,
        "source_exp52_decision_unchanged": True,
        "claim_boundary": "cross-machine exactness on sixteen frozen roots only",
        "next_step": "Export the immutable Exp53 bundle.",
    }
    atomic_json_dump(value, artifact_root / "analysis/summary.json")
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default="artifacts/v53/cross_machine_subset")
    parser.add_argument("--shard-count", type=int, default=DEFAULT_SHARDS)
    return parser.parse_args()


if __name__ == "__main__":
    result = analyze(parse_args())
    raise SystemExit(0 if result["decision_label"] == "cross_machine_exact" else 2)
