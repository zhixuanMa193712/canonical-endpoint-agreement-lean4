"""Capture the frozen Exp51 scientific environment before any candidate execution."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from experiment51_protocol import *


def command(cmd: list[str], cwd: Path, timeout: int) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=timeout)
    return p.returncode, (p.stdout + "\n" + p.stderr).strip()


def capture(args: argparse.Namespace) -> dict:
    root = Path(args.root).resolve()
    cfgp = root / "frozen/experiment51_config.json"
    targetsp = root / "frozen/targets.json"
    preflightp = root / "preflight/scientific_worker_compile.json"
    p52 = root / "frozen/experiment52_protocol.json"
    cfg, targets, preflight = read_json(cfgp), read_json(targetsp), read_json(preflightp)
    validate_code_lock(cfg["code_lock"])
    outp = root / "environment/receipt.json"
    if outp.exists():
        value = read_json(outp)
        if value.get("config_sha256") != file_sha256(cfgp):
            raise ValueError("environment receipt belongs to another freeze")
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value
    if preflight.get("compile_ok") is not True or preflight.get("config_sha256") != file_sha256(cfgp):
        raise ValueError("scientific compile preflight did not pass for this freeze")
    if not p52.is_file() or cfg.get("exp52_freeze_required_before_execution") is not True:
        raise ValueError("Exp52 protocol was not frozen")
    repository_rows = []
    all_ok = True
    for repo in cfg["repositories"]:
        project = Path(repo["checkout"])
        rc, commit = command(["git", "rev-parse", "HEAD"], project, args.timeout)
        vr, version = command(["lake", "env", "lean", "--version"], project, args.timeout)
        sr, status = command(["git", "status", "--porcelain", "--untracked-files=no"],
                             project, args.timeout)
        source_rows = [x for x in targets if x["slug"] == repo["slug"]]
        source_ok = all((project / x["file_path"]).is_file()
                        and file_sha256(project / x["file_path"]) == x["source_file_sha256"]
                        and Path(x["ast_path"]).is_file()
                        and file_sha256(x["ast_path"]) == x["ast_sha256"] for x in source_rows)
        row = {"slug": repo["slug"], "commit": commit, "commit_ok": rc == 0 and commit == repo["commit"],
               "lean_version": version, "lean_version_ok": vr == 0 and "version 4.27.0" in version,
               "tracked_checkout_clean": sr == 0 and not status,
               "selected_source_and_ast_hashes_exact": source_ok,
               "roots": len(source_rows)}
        row["repository_gate"] = all(row[k] is True for k in (
            "commit_ok", "lean_version_ok", "tracked_checkout_clean",
            "selected_source_and_ast_hashes_exact")) and len(source_rows) == ROOTS_PER_REPOSITORY
        all_ok &= row["repository_gate"]
        repository_rows.append(row)
    value = {
        "version": 1, "protocol_version": PROTOCOL_VERSION,
        "config_sha256": file_sha256(cfgp), "targets_sha256": file_sha256(targetsp),
        "exp52_protocol_sha256": file_sha256(p52),
        "scientific_candidate_tactics_executed": 0,
        "repositories": repository_rows, "environment_gate": bool(all_ok),
        "next_step": "Run Exp51 smoke." if all_ok else "STOP before scientific execution.",
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
    result = capture(parse_args())
    raise SystemExit(0 if result.get("environment_gate") else 2)
