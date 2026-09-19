"""Compile-only Fix3 Exp51 worker preflight; execute zero theorem roots."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from alignment_protocol import *


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    frozen = validate_amendment(root)
    outp = root / EXP51_PREFLIGHT_RELATIVE
    if outp.exists():
        value = read_json(outp)
        if not (
            value.get("alignment_version") == EXECUTION_ALIGNMENT_VERSION
            and value.get("mechanical_fix_id") == EXECUTION_FIX_ID
            and value.get("amendment_sha256") == frozen["amendment_sha256"]
            and value.get("source_config_sha256") == frozen["config_sha256"]
            and value.get("lean_source_sha256") == base_worker.LEAN_SOURCE_SHA256
            and value.get("theorem_sources_elaborated") == 0
            and value.get("candidate_tactics_executed") == 0
        ):
            raise ValueError("existing Fix3 Exp51 preflight belongs to another freeze")
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value
    target = frozen["targets"][0]
    project = Path(target["checkout"]).resolve()
    generated = root / "generated/fix3_exp51_preflight"
    generated.mkdir(parents=True, exist_ok=True)
    leanp = generated / base_worker.LEAN_FILE_NAME
    if leanp.exists() and file_sha256(leanp) != base_worker.LEAN_SOURCE_SHA256:
        raise ValueError("generated Fix3 Exp51 worker source changed")
    if not leanp.exists():
        leanp.write_text(base_worker.LEAN_SOURCE, encoding="utf-8")
    version = subprocess.run(
        ["lake", "env", "lean", "--version"],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=args.timeout,
    )
    compiled = subprocess.run(
        ["lake", "env", "lean", str(leanp)],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=args.timeout,
    )
    version_text = (version.stdout + "\n" + version.stderr).strip()
    worker_text = (BASE_PACKAGE_ROOT / "experiment51_live_worker.py").read_text(
        encoding="utf-8"
    )
    import_scan = {
        "imports_exp48_runner": "import experiment48" in worker_text,
        "imports_exp49_runner": "import experiment49" in worker_text,
        "imports_exp50_runner": "import experiment50" in worker_text,
    }
    value = {
        "version": 1,
        "stage": "exp51-scientific-worker-compile-fix3",
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "mechanical_fix_id": EXECUTION_FIX_ID,
        "runner_version": EXP51_RUNNER_VERSION,
        "diagnostic_only": True,
        "amendment_sha256": frozen["amendment_sha256"],
        "source_config_sha256": frozen["config_sha256"],
        "source_targets_sha256": frozen["targets_sha256"],
        "source_exp52_protocol_sha256": frozen["protocol_sha256"],
        "theorem_sources_elaborated": 0,
        "candidate_tactics_executed": 0,
        "scientific_candidate_tactics_executed": 0,
        "project": str(project),
        "lean_version": version_text,
        "version_ok": version.returncode == 0 and "version 4.27.0" in version_text,
        "lean_source": str(leanp),
        "lean_source_sha256": file_sha256(leanp),
        "expected_lean_source_sha256": base_worker.LEAN_SOURCE_SHA256,
        "compile_returncode": compiled.returncode,
        "stdout": compiled.stdout[-8000:],
        "stderr": compiled.stderr[-12000:],
        "independent_import_scan": import_scan,
    }
    value["compile_ok"] = bool(
        value["version_ok"]
        and compiled.returncode == 0
        and value["lean_source_sha256"] == base_worker.LEAN_SOURCE_SHA256
        and not any(import_scan.values())
    )
    value["next_step"] = (
        "Capture the Fix3 Exp51 environment receipt."
        if value["compile_ok"]
        else "STOP before environment capture or scientific candidate execution."
    )
    atomic_json_dump(value, outp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(SCIENTIFIC_ROOT))
    parser.add_argument("--timeout", type=int, default=300)
    return parser.parse_args()


if __name__ == "__main__":
    result = preflight(parse_args())
    raise SystemExit(0 if result.get("compile_ok") else 2)
