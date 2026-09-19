"""Compile-only Exp49 preflight; elaborates zero theorem sources and runs zero candidates."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from experiment49_protocol import (
    ARTIFACT_ROOT,
    MECHANICAL_FIX_ID,
    PROTOCOL_VERSION,
    TARGET_LEAN_VERSION,
    atomic_json_dump,
    read_json,
    validate_code_lock,
)
from experiment49_strict_worker import LEAN_FILE_NAME, LEAN_SOURCE, LEAN_SOURCE_SHA256


def preflight(args: argparse.Namespace) -> dict:
    root = Path(args.root).resolve()
    cfg = read_json(root / "frozen/experiment49_config.json")
    if (cfg.get("protocol_version") != PROTOCOL_VERSION
            or cfg.get("mechanical_fix_id") != MECHANICAL_FIX_ID):
        raise ValueError("wrong Exp49 config")
    validate_code_lock(cfg["code_lock"])
    outp = root / "preflight/strict_worker_compile.json"
    if outp.exists():
        value = read_json(outp)
        if (value.get("lean_source_sha256") != LEAN_SOURCE_SHA256
                or value.get("mechanical_fix_id") != MECHANICAL_FIX_ID):
            raise ValueError("existing preflight refers to a different strict worker")
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value

    generated = root / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    lean_file = generated / LEAN_FILE_NAME
    if lean_file.exists() and lean_file.read_text(encoding="utf-8") != LEAN_SOURCE:
        raise ValueError("generated Exp49 Lean source differs")
    lean_file.write_text(LEAN_SOURCE, encoding="utf-8")
    project = Path(cfg["repositories"][0]["checkout"])
    version = subprocess.run(
        ["lake", "env", "lean", "--version"], cwd=project, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=int(args.timeout),
    )
    compile_proc = subprocess.run(
        ["lake", "env", "lean", str(lean_file)], cwd=project, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=int(args.timeout),
    )
    version_text = (version.stdout + "\n" + version.stderr).strip()
    version_ok = version.returncode == 0 and "4.27.0" in version_text
    compile_ok = version_ok and compile_proc.returncode == 0
    value = {
        "version": 1, "protocol_version": PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "diagnostic_only": True,
        "scientific_candidate_tactics_executed": 0,
        "theorem_sources_elaborated": 0,
        "target_lean_version": TARGET_LEAN_VERSION,
        "version_ok": version_ok, "lean_version_output": version_text,
        "lean_source": str(lean_file), "lean_source_sha256": LEAN_SOURCE_SHA256,
        "project": str(project), "returncode": compile_proc.returncode,
        "compile_ok": compile_ok,
        "stdout": compile_proc.stdout[-12000:], "stderr": compile_proc.stderr[-16000:],
        "next_step": "Run Exp49 smoke." if compile_ok else "STOP; repair compile mechanics and refreeze before theorem execution.",
    }
    atomic_json_dump(value, outp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    p.add_argument("--timeout", type=int, default=300)
    return p.parse_args()


if __name__ == "__main__":
    result = preflight(parse_args())
    raise SystemExit(0 if result.get("compile_ok") else 2)
