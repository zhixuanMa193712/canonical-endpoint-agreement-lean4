"""Capture the Fix3 Exp51 environment before any scientific candidate runs."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from alignment_protocol import *


def command(cmd: list[str], cwd: Path, timeout: int) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return proc.returncode, (proc.stdout + "\n" + proc.stderr).strip()


def available_memory_gb() -> float:
    path = Path("/proc/meminfo")
    if not path.is_file():
        return 0.0
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, raw = line.split(":", 1)
        values[key] = int(raw.strip().split()[0])
    return values.get("MemAvailable", 0) / 1024 ** 2


def capture(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    frozen = validate_amendment(root)
    outp = root / EXP51_ENVIRONMENT_RELATIVE
    preflightp = root / EXP51_PREFLIGHT_RELATIVE
    if not preflightp.is_file():
        raise FileNotFoundError(preflightp)
    preflight = read_json(preflightp)
    if not (
        preflight.get("compile_ok") is True
        and preflight.get("alignment_version") == EXECUTION_ALIGNMENT_VERSION
        and preflight.get("mechanical_fix_id") == EXECUTION_FIX_ID
        and preflight.get("amendment_sha256") == frozen["amendment_sha256"]
        and preflight.get("source_config_sha256") == frozen["config_sha256"]
        and preflight.get("source_exp52_protocol_sha256") == frozen["protocol_sha256"]
        and preflight.get("theorem_sources_elaborated") == 0
        and preflight.get("candidate_tactics_executed") == 0
    ):
        raise ValueError("Fix3 scientific worker preflight is not exact")
    if outp.exists():
        value = read_json(outp)
        if not (
            value.get("alignment_version") == EXECUTION_ALIGNMENT_VERSION
            and value.get("amendment_sha256") == frozen["amendment_sha256"]
            and value.get("source_config_sha256") == frozen["config_sha256"]
            and value.get("environment_gate") is True
            and value.get("scientific_candidate_tactics_executed") == 0
        ):
            raise ValueError("existing Fix3 environment receipt changed")
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value
    for relative in ("smoke", "scientific", "analysis", "audit"):
        phase = root / relative
        if phase.exists() and any(item.is_file() for item in phase.rglob("*")):
            raise ValueError("environment capture must precede scientific outcomes")
    targets = frozen["targets"]
    repository_rows = []
    for repo in frozen["config"]["repositories"]:
        project = Path(repo["checkout"]).resolve()
        rc, commit = command(["git", "rev-parse", "HEAD"], project, args.timeout)
        vr, version = command(["lake", "env", "lean", "--version"], project, args.timeout)
        sr, status = command(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            project,
            args.timeout,
        )
        selected = [row for row in targets if row["slug"] == repo["slug"]]
        sources_ok = all(
            (project / row["file_path"]).is_file()
            and file_sha256(project / row["file_path"]) == row["source_file_sha256"]
            and Path(row["ast_path"]).is_file()
            and file_sha256(row["ast_path"]) == row["ast_sha256"]
            for row in selected
        )
        item = {
            "slug": repo["slug"],
            "checkout": str(project),
            "commit": commit,
            "commit_ok": rc == 0 and commit == repo["commit"],
            "lean_version": version,
            "lean_version_ok": vr == 0 and "version 4.27.0" in version,
            "tracked_checkout_clean": sr == 0 and not status,
            "selected_source_and_ast_hashes_exact": sources_ok,
            "roots": len(selected),
        }
        item["repository_gate"] = bool(
            item["commit_ok"]
            and item["lean_version_ok"]
            and item["tracked_checkout_clean"]
            and item["selected_source_and_ast_hashes_exact"]
            and item["roots"] == ROOTS_PER_REPOSITORY
        )
        repository_rows.append(item)
    requirements = frozen["amendment"]["exp51_execution"]["resource_gate"]
    allowed_cpus = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 0)
    memory_gb = available_memory_gb()
    free_disk_gb = shutil.disk_usage(root).free / 1024 ** 3
    resources = {
        "allowed_cpus": allowed_cpus,
        "available_memory_gb": memory_gb,
        "free_disk_gb": free_disk_gb,
        **requirements,
    }
    resources["resource_gate"] = bool(
        allowed_cpus >= requirements["minimum_allowed_cpus"]
        and memory_gb >= requirements["minimum_available_memory_gb"]
        and free_disk_gb >= requirements["minimum_free_disk_gb"]
    )
    value = {
        "version": 1,
        "stage": "exp51-scientific-environment-fix3",
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "mechanical_fix_id": EXECUTION_FIX_ID,
        "runner_version": EXP51_RUNNER_VERSION,
        "amendment_sha256": frozen["amendment_sha256"],
        "source_config_sha256": frozen["config_sha256"],
        "source_targets_sha256": frozen["targets_sha256"],
        "source_exp52_protocol_sha256": frozen["protocol_sha256"],
        "portable_exp52_document_bundle_sha256": frozen[
            "portable_document_lock"
        ]["bundle_sha256"],
        "preflight_sha256": file_sha256(preflightp),
        "scientific_candidate_tactics_executed": 0,
        "repositories": repository_rows,
        "qualification_resources": resources,
    }
    value["environment_gate"] = bool(
        len(repository_rows) == TARGET_REPOSITORIES
        and all(row["repository_gate"] for row in repository_rows)
        and resources["resource_gate"]
    )
    value["next_step"] = (
        "Run the frozen four-root Fix3 Exp51 smoke."
        if value["environment_gate"]
        else "STOP before scientific candidate execution."
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
    result = capture(parse_args())
    raise SystemExit(0 if result.get("environment_gate") else 2)
