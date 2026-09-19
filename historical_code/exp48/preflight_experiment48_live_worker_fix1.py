"""Compile-only preflight for the Exp48 FilePath-v4.27 Fix1 worker."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from experiment48_protocol import ARTIFACT_ROOT, atomic_json_dump, read_json, validate_code_lock
from experiment48_live_tacticinfo_worker_fix1 import (
    FIX_ID, LEAN_FILE_NAME, LEAN_SOURCE, LEAN_SOURCE_SHA256, source_delta_contract
)


def main(args: argparse.Namespace) -> dict:
    root = Path(args.root).resolve()
    cfg = read_json(root / "frozen/experiment48_config.json")
    validate_code_lock(cfg["code_lock"])
    amendment = read_json(root / "amendments/experiment48_preflight_fix1.json")
    validate_code_lock(amendment["fix_code_lock"])
    if amendment.get("fix_id") != FIX_ID:
        raise ValueError("wrong Exp48 Fix1 amendment")
    outdir = root / "preflight_fix1"
    summaryp = outdir / "live_worker_compile.json"
    if summaryp.exists():
        value = read_json(summaryp)
        if value.get("lean_source_sha256") != LEAN_SOURCE_SHA256:
            raise ValueError("existing Fix1 preflight refers to different worker source")
        print(json.dumps(value, indent=2))
        return value
    generated = root / "generated_fix1"
    generated.mkdir(parents=True, exist_ok=True)
    lean_file = generated / LEAN_FILE_NAME
    if lean_file.exists() and lean_file.read_text(encoding="utf-8") != LEAN_SOURCE:
        raise ValueError("generated Fix1 Lean source differs")
    lean_file.write_text(LEAN_SOURCE, encoding="utf-8")
    repo = cfg["repositories"][0]
    proc = subprocess.run(
        ["lake", "env", "lean", str(lean_file)],
        cwd=repo["checkout"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=int(args.timeout),
    )
    value = {
        "version": 1,
        "fix_id": FIX_ID,
        "diagnostic_only": True,
        "scientific_candidate_tactics_executed": 0,
        "theorem_sources_elaborated": 0,
        "lean_source": str(lean_file),
        "lean_source_sha256": LEAN_SOURCE_SHA256,
        "source_delta_contract": source_delta_contract(),
        "project": repo["checkout"],
        "returncode": proc.returncode,
        "compile_ok": proc.returncode == 0,
        "stdout": proc.stdout[-12000:],
        "stderr": proc.stderr[-16000:],
        "next_step": "Run isolated Exp48 Fix1 smoke." if proc.returncode == 0 else "STOP: inspect Fix1 compile mechanics only; do not run smoke.",
    }
    atomic_json_dump(value, summaryp)
    print(json.dumps(value, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    p.add_argument("--timeout", type=int, default=180)
    return p.parse_args()


if __name__ == "__main__":
    result = main(parse_args())
    raise SystemExit(0 if result.get("compile_ok") else 2)
