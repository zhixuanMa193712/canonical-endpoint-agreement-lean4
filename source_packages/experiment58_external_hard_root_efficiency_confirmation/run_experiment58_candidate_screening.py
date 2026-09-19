"""Run one deterministic shard of candidate-only eligibility screening."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from experiment58_protocol import *


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.artifact_root).resolve()
    checkout_root = Path(args.checkout_root).resolve()
    protocol = load_protocol(root)
    preflight = read_json(root / "preflight/candidate_worker_compile.json")
    assert_sealed(preflight, "candidate worker preflight")
    if preflight.get("compile_gate") is not True:
        raise ValueError("candidate worker compile gate failed")
    frame_receipt = read_json(root / "frozen/source_frame_receipt.json")
    assert_sealed(frame_receipt, "source frame")
    frame = read_jsonl(frame_receipt["candidate_screening_frame"])
    if file_sha256(frame_receipt["candidate_screening_frame"]) != frame_receipt["candidate_screening_frame_sha256"]:
        raise ValueError("candidate screening frame changed")
    assigned = [row for index, row in enumerate(frame) if index % args.shard_count == args.shard_index]
    worker = PACKAGE_ROOT / "experiment58_candidate_worker.py"
    rows = []
    execution_root = root / CANDIDATE_SCREENING_EXECUTION_ROOT
    for ordinal, target in enumerate(assigned, 1):
        output = execution_root / "candidate_receipts" / f"{target['target_id']}.json"
        if output.is_file():
            existing = read_json(output)
            assert_sealed(existing, f"candidate receipt {target['target_id']}")
            rows.append(existing)
            print(f"EXP58-CANDIDATE {args.shard_index:02d} {ordinal}/{len(assigned)} {target['dataset']} {target['theorem_name']} reused", flush=True)
            continue
        inp = {
            "version": VERSION, "protocol_version": PROTOCOL_VERSION,
            "protocol_record_sha256": protocol["record_sha256"],
            "artifact_root": str(root), "checkout_root": str(checkout_root),
            "target": target, "candidate_panel": list(CANDIDATE_PANEL),
            "continuation_probe_count": 0,
        }
        inp["input_identity_sha256"] = json_sha256(inp)
        input_path = execution_root / "inputs" / f"{target['target_id']}.json"
        atomic_json_dump(inp, input_path)
        proc = subprocess.run([sys.executable, str(worker), "--input", str(input_path),
                               "--output", str(output), "--timeout", str(args.timeout)],
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0 or not output.is_file():
            raise RuntimeError(f"candidate worker failed for {target['target_id']}: {proc.stderr[-6000:]}")
        row = read_json(output)
        assert_sealed(row, f"candidate receipt {target['target_id']}")
        rows.append(row)
        print(f"EXP58-CANDIDATE {args.shard_index:02d} {ordinal}/{len(assigned)} {target['dataset']} {target['theorem_name']} eligible={int(row['eligibility_gate'])}", flush=True)
    summary = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "shard_index": args.shard_index, "shard_count": args.shard_count,
        "targets_expected": len(assigned), "receipts": len(rows),
        "eligible": sum(row.get("eligibility_gate") is True for row in rows),
        "candidate_only_tactics_executed": sum(int(row.get("candidate_only_tactics_executed", 0)) for row in rows),
        "continuation_probes_executed": 0,
        "shard_gate": bool(
            len(rows) == len(assigned)
            and all(row.get("continuation_probes_executed") == 0 for row in rows)
            and all(row.get("worker_ok") is True for row in rows)
            and all(row.get("candidate_accounting_exact") is True for row in rows)
            and all(row.get("same_pre_state_all_branches") is True for row in rows)
            and all(row.get("candidate_only_tactics_executed") == CANDIDATES_PER_ROOT for row in rows)
        ),
    })
    atomic_json_dump(summary, execution_root / f"shards/shard-{args.shard_index:02d}.json")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--checkout-root", default=str(CHECKOUT_ROOT))
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, default=32)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    if not 0 <= args.shard_index < args.shard_count:
        parser.error("shard-index must be in [0, shard-count)")
    return args


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2))
