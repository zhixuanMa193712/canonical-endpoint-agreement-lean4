"""Compile the locked Exp59 candidate worker without elaborating target sources."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from experiment59_protocol import *


def run(root: Path, timeout: int) -> dict[str, Any]:
    protocol = load_protocol(root)
    freeze_receipt = read_json(root / "frozen/freeze_receipt.json")
    assert_sealed(freeze_receipt, "Exp59 freeze receipt")
    if freeze_receipt.get("freeze_gate") is not True or freeze_receipt.get("continuation_probes_executed") != 0:
        raise ValueError("Exp59 freeze gate failed")
    environment = read_json(root / "preflight/reused_benchmark_environment.json")
    assert_sealed(environment, "Exp59 reused environment")
    if environment.get("environment_gate") is not True:
        raise ValueError("Exp59 environment gate failed")
    _, _, exp58_worker = load_exp58_modules()
    vendor = exp58_worker.load_vendor()
    lean_path = root / "generated/Experiment59CandidateOnlyWorker.lean"
    lean_path.parent.mkdir(parents=True, exist_ok=True)
    if lean_path.is_file() and file_sha256(lean_path) != vendor.LEAN_SOURCE_SHA256:
        raise ValueError("generated Exp59 Lean worker changed")
    if not lean_path.is_file():
        lean_path.write_text(vendor.LEAN_SOURCE, encoding="utf-8")
    proc = subprocess.run(
        ["elan", "run", TARGET_TOOLCHAIN, "lean", str(lean_path)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
    )
    dataset_rows = [
        {
            "dataset": row["dataset"],
            "project": row["project"],
            "commit_exact": row["commit_exact"],
            "toolchain_exact": row["toolchain_exact"],
            "environment_gate": row["dataset_gate"],
            "worker_compile_returncode": proc.returncode,
            "compile_ok": proc.returncode == 0 and row["dataset_gate"],
        }
        for row in environment["datasets"]
    ]
    gate = all(row["compile_ok"] for row in dataset_rows)
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "diagnostic_only": True,
        "protocol_record_sha256": protocol["record_sha256"],
        "lean_source": str(lean_path),
        "lean_source_sha256": vendor.LEAN_SOURCE_SHA256,
        "candidate_panel_size": len(protocol["candidate_panel"]),
        "removed_direct_suggestions": protocol["removed_direct_suggestions"],
        "dataset_results": dataset_rows,
        "compile_gate": gate,
        "theorem_sources_elaborated": 0,
        "candidate_only_tactics_executed": 0,
        "continuation_probes_executed": 0,
        "next_step": "Run the 32 frozen Exp59 candidate-only shards." if gate else "STOP: compile preflight failed.",
    })
    atomic_json_dump(value, root / "preflight/candidate_worker_compile.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--timeout", type=int, default=900)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run(Path(args.artifact_root).resolve(), args.timeout), indent=2))
