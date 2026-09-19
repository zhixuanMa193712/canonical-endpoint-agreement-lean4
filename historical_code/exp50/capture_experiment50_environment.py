"""Capture and gate the exact Exp50 execution environment before re-execution."""
from __future__ import annotations

import argparse
import json
import platform
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

from experiment50_protocol import *


def command(args: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    proc = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout)
    return {
        "argv": args,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def optional_hash(project: Path, relative: str) -> dict[str, Any] | None:
    path = project / relative
    if not path.is_file():
        return None
    return {"path": str(path), "sha256": file_sha256(path), "bytes": path.stat().st_size}


def capture(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    cfgp = root / "frozen/experiment50_config.json"
    targetsp = root / "frozen/targets.json"
    preflightp = root / "preflight/worker_compile.json"
    for path in (cfgp, targetsp, preflightp):
        if not path.is_file():
            raise FileNotFoundError(path)
    cfg, targets, preflight = read_json(cfgp), read_json(targetsp), read_json(preflightp)
    validate_code_lock(cfg["code_lock"])
    if preflight.get("compile_ok") is not True:
        raise ValueError("Exp50 compile-only preflight did not pass")
    outp = root / "environment/receipt.json"
    if outp.exists():
        value = read_json(outp)
        if value.get("config_sha256") != file_sha256(cfgp):
            raise ValueError("existing environment receipt belongs to another freeze")
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value

    source_lock_rows = cfg["source_evidence_lock"]["rows"]
    source_evidence_ok = (
        json_sha256(source_lock_rows) == cfg["source_evidence_lock"]["bundle_sha256"]
        and all(Path(x["path"]).is_file()
                and Path(x["path"]).stat().st_size == int(x["bytes"])
                and file_sha256(x["path"]) == x["sha256"] for x in source_lock_rows)
    )
    source_control_ok = all(
        Path(cfg["source"][name]).is_file()
        and file_sha256(cfg["source"][name]) == cfg["source"][name + "_sha256"]
        for name in ("exp48_config", "exp48_summary", "exp49_config",
                     "exp49_validation", "exp49_analysis")
    )

    repository_rows = []
    selected_source_ok = True
    commits_ok = True
    lean_versions_ok = True
    for slug in cfg["repositories"]:
        rows = [x for x in targets if x["slug"] == slug]
        if len(rows) != ROOTS_PER_REPOSITORY:
            raise ValueError(f"wrong frozen target count: {slug}")
        project = Path(rows[0]["checkout"]).resolve()
        if not project.is_dir():
            raise FileNotFoundError(project)
        head = command(["git", "rev-parse", "HEAD"], project, args.timeout)
        dirty = command(["git", "status", "--porcelain"], project, args.timeout)
        version = command(["lake", "env", "lean", "--version"], project, args.timeout)
        source_rows = []
        for target in rows:
            source = project / target["file_path"]
            ok = source.is_file() and file_sha256(source) == target["source_file_sha256"]
            selected_source_ok = selected_source_ok and ok
            source_rows.append({
                "theorem_id": target["theorem_id"], "file_path": target["file_path"],
                "expected_sha256": target["source_file_sha256"],
                "observed_sha256": file_sha256(source) if source.is_file() else None,
                "ok": ok,
            })
        commit_ok = head["returncode"] == 0 and head["stdout"] == rows[0]["commit"]
        version_text = (version["stdout"] + "\n" + version["stderr"]).strip()
        version_ok = version["returncode"] == 0 and "4.27.0" in version_text
        commits_ok = commits_ok and commit_ok
        lean_versions_ok = lean_versions_ok and version_ok
        repository_rows.append({
            "slug": slug, "checkout": str(project), "expected_commit": rows[0]["commit"],
            "observed_commit": head["stdout"], "commit_ok": commit_ok,
            "git_status_porcelain": dirty["stdout"],
            "checkout_clean_descriptive": dirty["returncode"] == 0 and not dirty["stdout"],
            "lean_version": version_text, "lean_version_ok": version_ok,
            "build_identity_files": [x for x in (
                optional_hash(project, "lean-toolchain"),
                optional_hash(project, "lake-manifest.json"),
                optional_hash(project, "lakefile.lean"),
                optional_hash(project, "lakefile.toml"),
            ) if x is not None],
            "selected_sources": source_rows,
            "selected_sources_ok": all(x["ok"] for x in source_rows),
        })

    checks = {
        "compile_only_preflight_passed": preflight.get("compile_ok") is True,
        "lean_v4_27_all_repositories": lean_versions_ok,
        "all_repository_commits_exact": commits_ok,
        "all_96_selected_source_hashes_exact": selected_source_ok,
        "source_exp48_exp49_control_files_exact": source_control_ok,
        "source_exp48_exp49_theorem_evidence_exact": source_evidence_ok,
        "code_lock_exact": True,
    }
    value: dict[str, Any] = {
        "version": 1, "protocol_version": PROTOCOL_VERSION,
        "config_sha256": file_sha256(cfgp), "targets_sha256": file_sha256(targetsp),
        "operator_statement": cfg["operator_statement"],
        "independence_label": "same-server independent implementation and fresh-process re-execution",
        "independence_limit": "not a physically independent machine or independently reconstructed checkout",
        "host": {"hostname": socket.gethostname(), "platform": platform.platform(),
                 "python": sys.version, "python_executable": sys.executable},
        "repositories": repository_rows, "checks": checks,
        "environment_gate": all(checks.values()),
    }
    value["next_step"] = "Run Exp50 smoke." if value["environment_gate"] else "STOP before theorem execution."
    atomic_json_dump(value, outp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    p.add_argument("--timeout", type=int, default=300)
    return p.parse_args()


if __name__ == "__main__":
    result = capture(parse_args())
    raise SystemExit(0 if result.get("environment_gate") else 2)
