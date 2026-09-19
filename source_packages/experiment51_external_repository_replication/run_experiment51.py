"""Run frozen Exp51 smoke or full scientific external replication."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from experiment51_protocol import *
from screen_experiment51_repositories import worker_input

WORKER = PACKAGE_ROOT / "experiment51_live_worker.py"


def load_frozen(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    cfgp = root / "frozen/experiment51_config.json"
    targetsp = root / "frozen/targets.json"
    envp = root / "environment/receipt.json"
    preflightp = root / "preflight/scientific_worker_compile.json"
    for path in (cfgp, targetsp, envp, preflightp, root / "frozen/experiment52_protocol.json"):
        if not path.is_file():
            raise FileNotFoundError(path)
    cfg, targets, env, preflight = (read_json(cfgp), read_json(targetsp),
                                    read_json(envp), read_json(preflightp))
    validate_code_lock(cfg["code_lock"])
    cfg_sha = file_sha256(cfgp)
    if env.get("environment_gate") is not True or env.get("config_sha256") != cfg_sha:
        raise ValueError("environment gate did not pass for this freeze")
    if preflight.get("compile_ok") is not True or preflight.get("config_sha256") != cfg_sha:
        raise ValueError("scientific preflight did not pass for this freeze")
    if len(targets) != cfg["roots"] or len(targets) != cfg["repository_count"] * ROOTS_PER_REPOSITORY:
        raise ValueError("frozen target count changed")
    return cfg, targets, cfg_sha


def assert_existing(row: dict[str, Any], target: dict[str, Any], phase: str,
                    cfg_sha: str) -> None:
    if not (row.get("protocol_version") == PROTOCOL_VERSION
            and row.get("mode") == phase
            and row.get("config_sha256") == cfg_sha
            and row.get("theorem_id") == target["theorem_id"]
            and row.get("source_file_sha256") == target["source_file_sha256"]
            and row.get("candidate_order") == target["alternatives"]):
        raise ValueError(f"existing row identity mismatch: {target['theorem_id']}")


def invoke(root: Path, target: dict[str, Any], phase: str, cfg_sha: str,
           args: argparse.Namespace) -> dict[str, Any]:
    slug = safe_slug(target["slug"])
    outp = root / phase / "theorems" / slug / f"{target['rid']}.json"
    inputp = root / phase / "inputs" / slug / f"{target['rid']}.json"
    if outp.exists():
        row = read_json(outp)
        assert_existing(row, target, phase, cfg_sha)
        return row
    inp = worker_input(root, target, cfg_sha, target["alternatives"], phase)
    inp["environment_receipt_sha256"] = file_sha256(root / "environment/receipt.json")
    atomic_json_dump(inp, inputp)
    proc = subprocess.run([sys.executable, str(WORKER), "--input", str(inputp),
                           "--output", str(outp), "--generated-dir", str(root / "generated"),
                           "--timeout", str(args.lean_timeout)], cwd=PACKAGE_ROOT,
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=args.lean_timeout + 120)
    if not outp.is_file():
        raise RuntimeError(f"worker failed without record: {proc.returncode}\n{proc.stderr[-10000:]}")
    row = read_json(outp)
    assert_existing(row, target, phase, cfg_sha)
    return row


def summarize(root: Path, rows: list[dict[str, Any]], targets: list[dict[str, Any]],
              phase: str, cfg_sha: str) -> dict[str, Any]:
    repo_rows = []
    for slug in sorted({x["slug"] for x in targets}):
        rs = [x for x in rows if x["slug"] == slug]
        failures = Counter(x.get("error_type", "worker_gate") for x in rs if not x.get("worker_ok"))
        repo_rows.append({"slug": slug, "attempted": len(rs),
                          "evaluable": sum(x.get("worker_ok") is True for x in rs),
                          "gate_failures": dict(sorted(failures.items()))})
    value = {
        "version": 1, "protocol_version": PROTOCOL_VERSION, "phase": phase,
        "config_sha256": cfg_sha, "roots_expected": len(targets),
        "roots_attempted": len(rows),
        "candidate_attempts_expected": len(targets) * CANDIDATES_PER_ROOT,
        "candidate_attempts": sum(len(x.get("candidates", [])) for x in rows),
        "evaluable_roots": sum(x.get("worker_ok") is True for x in rows),
        "repository_execution": repo_rows,
    }
    value["execution_complete"] = (value["roots_attempted"] == value["roots_expected"]
                                     and value["candidate_attempts"] == value["candidate_attempts_expected"])
    if phase == "smoke":
        value["smoke_gate"] = bool(value["execution_complete"]
                                    and value["evaluable_roots"] == value["roots_expected"])
        value["next_step"] = "Run frozen full scientific execution." if value["smoke_gate"] else "STOP."
    else:
        value["execution_gate"] = bool(value["execution_complete"])
        value["next_step"] = "Run frozen offline analysis."
    atomic_json_dump(value, root / phase / "summary.json")
    return value


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    cfg, all_targets, cfg_sha = load_frozen(root)
    if args.phase == "smoke":
        ids = set(cfg["smoke_target_ids"])
        targets = [x for x in all_targets if x["theorem_id"] in ids]
        if len(targets) != len(ids):
            raise ValueError("smoke target identity changed")
    else:
        smoke = read_json(root / "smoke/summary.json")
        if smoke.get("smoke_gate") is not True or smoke.get("config_sha256") != cfg_sha:
            raise ValueError("smoke did not pass for this freeze")
        targets = all_targets
    claimp = root / args.phase / "execution_claim.json"
    if not claimp.exists():
        exclusive_create_json(claimp, {"version": 1, "protocol_version": PROTOCOL_VERSION,
                                       "phase": args.phase, "config_sha256": cfg_sha})
    rows = []
    for index, target in enumerate(targets, 1):
        print(f"EXP51-{args.phase.upper()} {index}/{len(targets)} {target['slug']} {target['full_name']}",
              flush=True)
        row = invoke(root, target, args.phase, cfg_sha, args)
        print(f"EXP51-RESULT evaluable={int(row.get('worker_ok') is True)} "
              f"candidates={len(row.get('candidates', []))}", flush=True)
        rows.append(row)
    value = summarize(root, rows, targets, args.phase, cfg_sha)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    p.add_argument("--phase", choices=("smoke", "scientific"), required=True)
    p.add_argument("--lean-timeout", type=int, default=900)
    return p.parse_args()


if __name__ == "__main__":
    run(parse_args())
