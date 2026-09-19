"""Install the packaged immutable Exp62 design into an artifact root."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from experiment62_protocol import *


def install(root: Path) -> dict[str, Any]:
    protocol = load_initial_protocol()
    benchmark = WORKSPACE_ROOT / BENCHMARK_RELATIVE
    if not benchmark.is_file() or file_sha256(benchmark) != BENCHMARK_SHA256:
        raise ValueError("required LeanDojo Benchmark 4 random/test file is absent or changed")
    destination = root / "frozen"
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("initial_protocol.json", "candidate_frame.jsonl"):
        source = PACKAGE_ROOT / "frozen" / name
        target = destination / name
        if target.exists():
            if file_sha256(target) != file_sha256(source):
                raise ValueError(f"installed frozen file differs: {target}")
        else:
            shutil.copy2(source, target)
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "artifact_root": str(root),
        "initial_protocol_sha256": file_sha256(destination / "initial_protocol.json"),
        "candidate_frame_sha256": file_sha256(destination / "candidate_frame.jsonl"),
        "benchmark": str(benchmark),
        "benchmark_sha256": file_sha256(benchmark),
        "install_gate": True,
        "scientific_policy_jobs_executed": 0,
        "next_step": "Run preflight_experiment62.py.",
    })
    atomic_json_dump(value, root / "frozen/install_receipt.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(install(Path(parse_args().artifact_root).resolve()), indent=2))
