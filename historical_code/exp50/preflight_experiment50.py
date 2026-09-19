"""Compile-only preflight for the standalone Exp50 Lean worker."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from experiment50_independent_worker import LEAN_FILE_NAME, LEAN_SOURCE, LEAN_SOURCE_SHA256
from experiment50_protocol import *


def preflight(args: argparse.Namespace) -> dict:
    root = Path(args.root).resolve()
    cfg = read_json(root / "frozen/experiment50_config.json")
    if cfg.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("wrong Exp50 config")
    validate_code_lock(cfg["code_lock"])
    outp = root / "preflight/worker_compile.json"
    if outp.exists():
        value = read_json(outp)
        if value.get("lean_source_sha256") != LEAN_SOURCE_SHA256:
            raise ValueError("preflight worker source changed")
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value
    targets = read_json(root / "frozen/targets.json")
    project = Path(targets[0]["checkout"])
    generated = root / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    lean_file = generated / LEAN_FILE_NAME
    if lean_file.exists() and lean_file.read_text(encoding="utf-8") != LEAN_SOURCE:
        raise ValueError("generated Exp50 Lean file changed")
    lean_file.write_text(LEAN_SOURCE, encoding="utf-8")
    version = subprocess.run(["lake", "env", "lean", "--version"], cwd=project,
                             text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             timeout=int(args.timeout))
    compiled = subprocess.run(["lake", "env", "lean", str(lean_file)], cwd=project,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=int(args.timeout))
    version_text = (version.stdout + "\n" + version.stderr).strip()
    version_ok = version.returncode == 0 and "4.27.0" in version_text
    import_scan = {
        "imports_exp48_runner": "import experiment48" in (PACKAGE_ROOT / "experiment50_independent_worker.py").read_text(),
        "imports_exp49_runner": "import experiment49" in (PACKAGE_ROOT / "experiment50_independent_worker.py").read_text(),
    }
    value = {
        "version": 1, "protocol_version": PROTOCOL_VERSION, "diagnostic_only": True,
        "theorem_sources_elaborated": 0, "candidate_tactics_executed": 0,
        "lean_version": version_text, "version_ok": version_ok,
        "lean_source": str(lean_file), "lean_source_sha256": LEAN_SOURCE_SHA256,
        "project": str(project), "returncode": compiled.returncode,
        "compile_ok": bool(version_ok and compiled.returncode == 0 and not any(import_scan.values())),
        "independent_import_scan": import_scan,
        "stdout": compiled.stdout[-12000:], "stderr": compiled.stderr[-16000:],
    }
    value["next_step"] = "Capture Exp50 environment receipt." if value["compile_ok"] else "STOP before theorem execution."
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
