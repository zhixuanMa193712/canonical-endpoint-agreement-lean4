"""Compile-only Exp53 preflight; executes zero theorem roots and candidates."""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from exp53_protocol import *


def load_worker():
    vendor = PACKAGE_ROOT / "vendor"
    sys.path.insert(0, str(vendor))
    import experiment51_live_worker as worker
    return worker


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    subset, receipt = validate_frozen()
    artifact_root = Path(args.artifact_root).resolve()
    preparation = read_json(artifact_root / "environment/preparation.json")
    mapping = checkout_map(preparation["checkout_map"])
    worker = load_worker()
    generated = artifact_root / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    lean_file = generated / worker.LEAN_FILE_NAME
    if lean_file.exists() and file_sha256(lean_file) != worker.LEAN_SOURCE_SHA256:
        raise ValueError("generated Exp53 Lean worker changed")
    if not lean_file.exists():
        lean_file.write_text(worker.LEAN_SOURCE, encoding="utf-8")
    rows = []
    for repo in subset["repositories"]:
        slug = repo["slug"]
        project = mapping.get(slug)
        if project is None or not project.is_dir():
            raise FileNotFoundError(f"missing checkout: {slug}")
        version = subprocess.run(
            ["lake", "env", "lean", "--version"], cwd=project, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=args.timeout,
        )
        compiled = subprocess.run(
            ["lake", "env", "lean", str(lean_file)], cwd=project, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=args.timeout,
        )
        version_text = (version.stdout + "\n" + version.stderr).strip()
        sources_exact = all(
            (project / target["file_path"]).is_file()
            and file_sha256(project / target["file_path"])
            == target["source_file_sha256"]
            for target in subset["targets"] if target["slug"] == slug
        )
        rows.append({
            "slug": slug,
            "project": str(project),
            "commit": repo["commit"],
            "version": version_text,
            "version_ok": version.returncode == 0 and "version 4.27.0" in version_text,
            "source_hashes_exact": sources_exact,
            "compile_returncode": compiled.returncode,
            "compile_ok": compiled.returncode == 0,
            "stdout": compiled.stdout[-4000:],
            "stderr": compiled.stderr[-8000:],
        })
    machine = machine_receipt()
    value = {
        "version": 1,
        "protocol_version": PROTOCOL_VERSION,
        "diagnostic_only": True,
        "freeze_identity_sha256": receipt["identity_sha256"],
        "machine": machine,
        "repositories_compiled": len(rows),
        "repositories": rows,
        "lean_source_sha256": file_sha256(lean_file),
        "expected_lean_source_sha256": worker.LEAN_SOURCE_SHA256,
        "theorem_sources_elaborated": 0,
        "candidate_tactics_executed": 0,
        "compile_gate": all(
            row["version_ok"] and row["source_hashes_exact"] and row["compile_ok"]
            for row in rows
        ) and file_sha256(lean_file) == worker.LEAN_SOURCE_SHA256
        and machine["hostname_distinct_from_source"]
        and machine["target_machine_system_ok"],
    }
    value["next_step"] = (
        "Run four frozen Exp53 shards."
        if value["compile_gate"]
        else "STOP before theorem or candidate execution."
    )
    out = artifact_root / "preflight/worker_compile.json"
    atomic_json_dump(value, out)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default="artifacts/v53/cross_machine_subset")
    parser.add_argument("--timeout", type=int, default=900)
    return parser.parse_args()


if __name__ == "__main__":
    value = preflight(parse_args())
    raise SystemExit(0 if value["compile_gate"] else 2)
