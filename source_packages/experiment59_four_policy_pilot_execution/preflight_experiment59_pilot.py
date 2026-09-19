"""Compile-only preflight for the frozen Exp59 pilot worker."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from experiment59_pilot_protocol import *


def run(root: Path, timeout: int) -> dict[str, Any]:
    design = load_design(root)
    source, _ = load_source()
    exp58 = source.load_exp58_modules()[0]
    backend = load_backend()
    lean_path = backend.build_lean_source(root / "pilot/generated/Experiment59PilotDepth2Worker.lean")
    targets = read_jsonl(design["targets_path"])
    rows = []
    for dataset in ("minif2f", "putnambench"):
        project = source.project_path(dataset, CHECKOUT_ROOT, exp58)
        proc = subprocess.run(
            ["lake", "env", "lean", str(lean_path)], cwd=project,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        )
        rows.append({
            "dataset": dataset,
            "project": str(project),
            "compile_ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-6000:],
        })
    gate = len(targets) == EXPECTED_PILOT_ROOTS and all(row["compile_ok"] for row in rows)
    value = seal({
        "version": VERSION,
        "pilot_protocol_version": PILOT_PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "diagnostic_only": True,
        "repositories_compiled": len(rows),
        "repository_results": rows,
        "lean_source": str(lean_path),
        "lean_source_sha256": backend.LEAN_SOURCE_SHA256,
        "compile_gate": gate,
        "theorem_sources_elaborated": 0,
        "scientific_search_cells_executed": 0,
        "continuation_probes_executed": 0,
        "next_step": "Run 32 frozen root shards." if gate else "STOP before pilot execution.",
    })
    atomic_json_dump(value, root / "pilot/preflight/worker_compile.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--timeout", type=int, default=900)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run(Path(args.artifact_root).resolve(), args.timeout), indent=2))
