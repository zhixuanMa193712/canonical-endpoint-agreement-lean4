"""Compile-only Exp54 preflight; executes zero theorem roots and zero probes."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from experiment54_live_worker import LEAN_FILE_NAME, LEAN_SOURCE_SHA256, build_lean_source
from experiment54_protocol import *


def run_cmd(cmd: list[str], cwd: Path, timeout: int) -> dict[str, object]:
    proc = subprocess.run(
        cmd, cwd=cwd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=timeout,
    )
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-8000:],
        "stderr": proc.stderr[-12000:],
    }


def preflight(args: argparse.Namespace) -> dict[str, object]:
    root = Path(args.artifact_root).resolve()
    frozen = load_freeze(root)
    out = root / "preflight/worker_compile.json"
    if out.is_file():
        existing = read_json(out)
        if existing.get("compile_gate") is not True:
            raise ValueError("existing Exp54 preflight did not pass")
        print(json.dumps(existing, ensure_ascii=False, indent=2))
        return existing
    lean_file = build_lean_source(root / "generated" / LEAN_FILE_NAME)
    target_by_repo: dict[str, dict[str, object]] = {}
    for meta in frozen["targets"]:
        target = read_json(meta["path"])
        target_by_repo.setdefault(target["slug"], target)
    rows = []
    for slug in REPOSITORIES:
        target = target_by_repo[slug]
        project = Path(target["checkout"])
        version = run_cmd(["lake", "env", "lean", "--version"], project, args.timeout)
        commit = run_cmd(["git", "rev-parse", "HEAD"], project, args.timeout)
        compile_result = run_cmd(
            ["lake", "env", "lean", str(lean_file)], project, args.timeout
        )
        rows.append({
            "slug": slug,
            "checkout": str(project),
            "commit_expected": target["commit"],
            "commit_observed": str(commit["stdout"]).strip(),
            "commit_ok": (
                commit["returncode"] == 0
                and str(commit["stdout"]).strip() == target["commit"]
            ),
            "lean_version": str(version["stdout"]).strip(),
            "version_ok": (
                version["returncode"] == 0
                and "Lean (version 4.27.0" in str(version["stdout"])
            ),
            "compile_ok": compile_result["returncode"] == 0,
            "compile_returncode": compile_result["returncode"],
            "compile_stdout": compile_result["stdout"],
            "compile_stderr": compile_result["stderr"],
        })
    gate = all(
        row["commit_ok"] and row["version_ok"] and row["compile_ok"]
        for row in rows
    )
    value: dict[str, object] = {
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "execution_version": EXECUTION_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "diagnostic_only": True,
        "lean_source": str(lean_file),
        "lean_source_sha256": LEAN_SOURCE_SHA256,
        "counterfactual_max_heartbeats": COUNTERFACTUAL_MAX_HEARTBEATS,
        "candidate_and_probe_heartbeat_budgets_isolated": True,
        "repositories_compiled": len(rows),
        "repository_results": rows,
        "theorem_sources_elaborated": 0,
        "scientific_candidates_executed": 0,
        "downstream_probes_executed": 0,
        "compile_gate": gate,
        "next_step": (
            "Run the sixteen frozen Exp54 scientific shards."
            if gate else "STOP; repair compile mechanics before scientific execution."
        ),
    }
    atomic_json_dump(value, out)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--artifact-root", default=str(artifact_root()))
    p.add_argument("--timeout", type=int, default=300)
    return p.parse_args()


if __name__ == "__main__":
    preflight(parse_args())
