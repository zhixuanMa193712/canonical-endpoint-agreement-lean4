"""Compile the locked candidate-only worker without elaborating benchmark theorems."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from experiment58_protocol import *


def run(root: Path, checkout_root: Path, timeout: int) -> dict[str, Any]:
    load_protocol(root)
    frame = read_json(root / "frozen/source_frame_receipt.json")
    assert_sealed(frame, "source frame")
    if frame.get("frame_gate") is not True:
        raise ValueError("source frame gate failed")
    validate_vendor()
    sys.path.insert(0, str(PACKAGE_ROOT))
    import experiment58_candidate_worker as candidate_worker
    vendor = candidate_worker.load_vendor()
    lean_path = root / "generated/Experiment58CandidateOnlyWorker.lean"
    lean_path.parent.mkdir(parents=True, exist_ok=True)
    if lean_path.is_file() and file_sha256(lean_path) != vendor.LEAN_SOURCE_SHA256:
        raise ValueError("generated candidate worker changed")
    if not lean_path.is_file():
        lean_path.write_text(vendor.LEAN_SOURCE, encoding="utf-8")
    environment = read_json(root / "preflight/benchmark_environment.json")
    assert_sealed(environment, "benchmark environment")
    if environment.get("environment_gate") is not True:
        raise ValueError("benchmark environment gate failed")
    # The worker imports only Lean and Lake.  Compile it directly with the
    # frozen elan toolchain so preflight cannot silently download project
    # dependencies or elaborate benchmark theorem sources.
    proc = subprocess.run(["elan", "run", TARGET_TOOLCHAIN, "lean", str(lean_path)],
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout)
    rows = [{
        "dataset": row["dataset"], "project": row["project"],
        "commit_exact": row["commit_exact"], "toolchain_exact": row["toolchain_exact"],
        "environment_gate": row["dataset_gate"], "worker_compile_returncode": proc.returncode,
        "compile_ok": proc.returncode == 0 and row["dataset_gate"],
    } for row in environment["datasets"]]
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "diagnostic_only": True, "lean_source": str(lean_path),
        "lean_source_sha256": vendor.LEAN_SOURCE_SHA256, "compile_command": [
            "elan", "run", TARGET_TOOLCHAIN, "lean", str(lean_path)
        ], "compile_stdout_tail": proc.stdout[-2000:], "compile_stderr_tail": proc.stderr[-6000:],
        "dataset_results": rows,
        "compile_gate": all(row["compile_ok"] for row in rows),
        "theorem_sources_elaborated": 0, "candidate_only_tactics_executed": 0,
        "continuation_probes_executed": 0,
        "next_step": "Run the frozen candidate-only screening shards." if all(row["compile_ok"] for row in rows)
        else "STOP: candidate worker compile preflight failed.",
    })
    atomic_json_dump(value, root / "preflight/candidate_worker_compile.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--checkout-root", default=str(CHECKOUT_ROOT))
    parser.add_argument("--timeout", type=int, default=600)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run(Path(args.artifact_root).resolve(), Path(args.checkout_root).resolve(), args.timeout), indent=2))
