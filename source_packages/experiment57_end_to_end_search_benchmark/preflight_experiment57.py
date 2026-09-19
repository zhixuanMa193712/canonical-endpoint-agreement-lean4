"""Compile-only Exp57 worker preflight; executes zero theorem targets."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from experiment57_protocol import *


def run(root: Path, timeout: int) -> dict:
    design = load_design(root)
    import sys
    sys.path.insert(0, str(WORKSPACE_ROOT / "experiment54_effect_aware_depth2_microbenchmark_fix3"))
    import experiment54_live_worker as backend  # type: ignore
    lean_source = backend.build_lean_source(root / "generated" / backend.LEAN_FILE_NAME)
    results = []
    seen = set()
    for meta in design["targets"]:
        if meta["slug"] in seen:
            continue
        seen.add(meta["slug"])
        target = read_json(meta["path"])
        project = portable_checkout(target["checkout"])
        proc = subprocess.run(
            ["lake", "env", "lean", str(lean_source)], cwd=project,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        )
        results.append({
            "slug": meta["slug"], "project": str(project),
            "compile_ok": proc.returncode == 0, "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-2000:], "stderr_tail": proc.stderr[-6000:],
        })
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "diagnostic_only": True, "repositories_compiled": len(results),
        "repository_results": results,
        "lean_source_sha256": backend.LEAN_SOURCE_SHA256,
        "compile_gate": len(results) == 4 and all(row["compile_ok"] for row in results),
        "theorem_sources_elaborated": 0, "scientific_search_cells_executed": 0,
        "next_step": "Run sixteen frozen root shards." if all(row["compile_ok"] for row in results)
                     else "STOP before scientific search execution.",
    })
    atomic_json_dump(value, root / "preflight/worker_compile.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--timeout", type=int, default=300)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run(Path(args.artifact_root).resolve(), args.timeout), indent=2))

