"""Run one frozen shard of Exp59 candidate-only screening."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from experiment59_protocol import *


def valid_operational_receipt(row: dict[str, Any], panel_size: int) -> bool:
    return bool(
        row.get("worker_ok") is True
        and row.get("candidate_accounting_exact") is True
        and row.get("same_pre_state_all_branches") is True
        and row.get("candidate_only_tactics_executed") == panel_size
        and row.get("staged_source_content_exact") is True
        and len(row.get("candidate_panel", [])) == panel_size
        and len(row.get("candidate_rows", [])) == panel_size
        and row.get("continuation_probes_executed") == 0
        and row.get("scientific_retry_count") == 0
        and row.get("process", {}).get("attempt_ordinal") == 1
        and row.get("process", {}).get("fresh_lean_process") is True
    )


def valid_retained_failure(row: dict[str, Any]) -> bool:
    return bool(
        row.get("worker_ok") is False
        and row.get("candidate_only_tactics_executed") == 0
        and row.get("continuation_probes_executed") == 0
        and row.get("first_failed_gate") in {"timeout", "worker_failure"}
        and row.get("process", {}).get("attempt_ordinal") == 1
        and row.get("process", {}).get("fresh_lean_process") is True
        and row.get("scientific_retry_count") == 0
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.artifact_root).resolve()
    checkout_root = Path(args.checkout_root).resolve()
    protocol = load_protocol(root)
    preflight = read_json(root / "preflight/candidate_worker_compile.json")
    assert_sealed(preflight, "Exp59 candidate preflight")
    if preflight.get("compile_gate") is not True:
        raise ValueError("Exp59 compile preflight failed")
    frame_path = Path(protocol["source_frame"]["frame"])
    if file_sha256(frame_path) != protocol["source_frame"]["frame_sha256"]:
        raise ValueError("Exp59 candidate frame changed")
    frame = read_jsonl(frame_path)
    assigned = [row for index, row in enumerate(frame) if index % args.shard_count == args.shard_index]
    panel = tuple(protocol["candidate_panel"])
    if panel != expansion_panel(load_exp58_modules()[0]):
        raise ValueError("Exp59 expansion panel changed")
    worker = PACKAGE_ROOT / "experiment59_candidate_worker.py"
    receipt_root = root / "screening/candidate_receipts"
    receipt_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for ordinal, target in enumerate(assigned, 1):
        output = receipt_root / f"{target['target_id']}.json"
        if output.is_file():
            row = read_json(output)
            assert_sealed(row, f"Exp59 receipt {target['target_id']}")
            rows.append(row)
            print(
                f"EXP59-CANDIDATE {args.shard_index:02d} {ordinal}/{len(assigned)} "
                f"{target['dataset']} {target['theorem_name']} reused",
                flush=True,
            )
            continue
        inp = {
            "version": VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "protocol_record_sha256": protocol["record_sha256"],
            "artifact_root": str(root),
            "checkout_root": str(checkout_root),
            "target": target,
            "candidate_panel": list(panel),
            "continuation_probe_count": 0,
        }
        inp["input_identity_sha256"] = json_sha256(inp)
        input_path = root / "screening/inputs" / f"{target['target_id']}.json"
        atomic_json_dump(inp, input_path)
        proc = subprocess.run(
            [
                sys.executable, str(worker), "--input", str(input_path), "--output", str(output),
                "--timeout", str(args.timeout),
            ],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if proc.returncode != 0 or not output.is_file():
            raise RuntimeError(f"Exp59 candidate wrapper failed for {target['target_id']}: {proc.stderr[-6000:]}")
        row = read_json(output)
        assert_sealed(row, f"Exp59 receipt {target['target_id']}")
        rows.append(row)
        print(
            f"EXP59-CANDIDATE {args.shard_index:02d} {ordinal}/{len(assigned)} "
            f"{target['dataset']} {target['theorem_name']} eligible={int(row.get('eligibility_gate') is True)} "
            f"status={'ok' if row.get('worker_ok') is True else row.get('first_failed_gate')}",
            flush=True,
        )
    identities_exact = all(row.get("target_identity") == target for row, target in zip(rows, assigned))
    accounting = all(
        tuple(row.get("candidate_panel", [])) == panel
        and (valid_operational_receipt(row, len(panel)) or valid_retained_failure(row))
        for row in rows
    )
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "targets_expected": len(assigned),
        "receipts": len(rows),
        "operational_roots": sum(row.get("worker_ok") is True for row in rows),
        "operational_failures_retained": sum(row.get("worker_ok") is False for row in rows),
        "eligible": sum(row.get("eligibility_gate") is True for row in rows),
        "candidate_only_tactics_executed": sum(int(row.get("candidate_only_tactics_executed", 0)) for row in rows),
        "continuation_probes_executed": 0,
        "all_target_identities_exact": identities_exact,
        "all_receipts_operational_or_retained_failures": accounting,
        "shard_gate": len(rows) == len(assigned) and identities_exact and accounting,
    })
    atomic_json_dump(value, root / f"screening/shards/shard-{args.shard_index:02d}.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--checkout-root", default=str(CHECKOUT_ROOT))
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, default=SHARD_COUNT)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    if args.shard_count != SHARD_COUNT:
        parser.error(f"shard-count is frozen at {SHARD_COUNT}")
    if not 0 <= args.shard_index < args.shard_count:
        parser.error("shard-index must be in [0, shard-count)")
    return args


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2))
