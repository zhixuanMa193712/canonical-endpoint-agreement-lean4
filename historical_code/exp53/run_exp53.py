"""Execute one frozen Exp53 shard with one fresh Lean process per root."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

from exp53_protocol import *


WORKER = PACKAGE_ROOT / "vendor/experiment51_live_worker.py"


def expected_input(
    artifact_root: Path, project: Path, target: dict[str, Any],
    subset_sha: str, environment_sha: str,
) -> dict[str, Any]:
    candidates = list(target["alternatives"])
    value = {
        "version": 1,
        "protocol_version": PROTOCOL_VERSION,
        "mode": "exp53-cross-machine-subset",
        "config_sha256": subset_sha,
        "environment_receipt_sha256": environment_sha,
        "artifact_root": str(artifact_root / "runtime"),
        "project": str(project),
        "slug": target["slug"],
        "commit": target["commit"],
        "file_path": target["file_path"],
        "full_name": target["full_name"],
        "theorem_id": target["theorem_id"],
        "source_file_sha256": target["source_file_sha256"],
        "trace_root_state": target["trace_root_state"],
        "trace_root_state_sha256": target["trace_root_state_sha256"],
        "authored_tactic": target["authored_tactic"],
        "target_pos": target["target_pos"],
        "target_end_pos": target["target_end_pos"],
        "ast_sha256": target["ast_sha256"],
        "candidates": candidates,
        "candidates_sha256": json_sha256(candidates),
        "candidate_positions_frozen": list(range(len(candidates))),
    }
    value["execution_record_id"] = json_sha256({
        "protocol": PROTOCOL_VERSION,
        "theorem_id": target["theorem_id"],
        "candidates": candidates,
    })
    return value


def run(args: argparse.Namespace) -> dict[str, Any]:
    if not 0 <= args.shard_index < args.shard_count:
        raise ValueError("invalid shard index")
    subset, receipt = validate_frozen()
    artifact_root = Path(args.artifact_root).resolve()
    preflight_path = artifact_root / "preflight/worker_compile.json"
    preflight = read_json(preflight_path)
    if not (
        preflight.get("compile_gate") is True
        and preflight.get("freeze_identity_sha256") == receipt["identity_sha256"]
    ):
        raise ValueError("Exp53 compile-only preflight did not pass")
    preparation = read_json(artifact_root / "environment/preparation.json")
    mapping = checkout_map(preparation["checkout_map"])
    selected = [
        (index, target) for index, target in enumerate(subset["targets"])
        if index % args.shard_count == args.shard_index
    ]
    shard_root = artifact_root / f"execution/shards/shard-{args.shard_index:02d}"
    rows = []
    for position, (frozen_index, target) in enumerate(selected, start=1):
        safe = safe_slug(target["slug"])
        rid = target["rid"]
        input_path = shard_root / "inputs" / safe / f"{rid}.json"
        row_path = shard_root / "rows" / safe / f"{rid}.json"
        claim_path = shard_root / "claims" / safe / f"{rid}.json"
        if row_path.exists():
            row = read_json(row_path)
        elif claim_path.exists():
            raise RuntimeError(
                f"immutable claim exists without row; retry prohibited: {target['theorem_id']}"
            )
        else:
            project = mapping[target["slug"]]
            inp = expected_input(
                artifact_root, project, target, file_sha256(PACKAGE_ROOT / "frozen/subset.json"),
                file_sha256(preflight_path),
            )
            atomic_json_dump(inp, input_path)
            atomic_json_dump({
                "version": 1,
                "protocol_version": PROTOCOL_VERSION,
                "freeze_identity_sha256": receipt["identity_sha256"],
                "frozen_target_index": frozen_index,
                "theorem_id": target["theorem_id"],
                "attempts_permitted": 1,
                "retry_permitted": False,
            }, claim_path)
            cmd = [
                sys.executable, str(WORKER), "--input", str(input_path),
                "--output", str(row_path),
                "--generated-dir", str(artifact_root / "generated"),
                "--timeout", str(args.lean_timeout),
            ]
            proc = subprocess.run(
                cmd, cwd=PACKAGE_ROOT, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=args.lean_timeout + 180,
            )
            if not row_path.is_file():
                raise RuntimeError(
                    f"Exp53 worker produced no row: {target['theorem_id']}\n"
                    f"stdout={proc.stdout[-4000:]}\nstderr={proc.stderr[-8000:]}"
                )
            row = read_json(row_path)
        rows.append(row)
        print(
            f"EXP53-SHARD {args.shard_index:02d} {position}/{len(selected)} "
            f"{target['slug']} {target['full_name']} worker_ok={int(row.get('worker_ok') is True)}",
            flush=True,
        )
    value = {
        "version": 1,
        "protocol_version": PROTOCOL_VERSION,
        "freeze_identity_sha256": receipt["identity_sha256"],
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "roots_expected": len(selected),
        "roots_recorded": len(rows),
        "evaluable_roots": sum(row.get("worker_ok") is True for row in rows),
        "candidate_attempts": sum(len(row.get("candidates", [])) for row in rows),
        "failure_categories": dict(Counter(
            row.get("failure_category") or row.get("error_type") or "worker_ok"
            for row in rows if row.get("worker_ok") is not True
        )),
        "manual_reconciliation_count": 0,
    }
    value["shard_gate"] = bool(
        value["roots_recorded"] == value["roots_expected"]
        and value["evaluable_roots"] == value["roots_expected"]
        and value["candidate_attempts"] == value["roots_expected"] * CANDIDATES_PER_ROOT
    )
    value["next_step"] = "Complete all shards, then run frozen comparison."
    atomic_json_dump(value, shard_root / "summary.json")
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default="artifacts/v53/cross_machine_subset")
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, default=DEFAULT_SHARDS)
    parser.add_argument("--lean-timeout", type=int, default=DEFAULT_TIMEOUT)
    return parser.parse_args()


if __name__ == "__main__":
    value = run(parse_args())
    raise SystemExit(0 if value["shard_gate"] else 2)

