"""Run the frozen Exp49 smoke or 96-root validation phase."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from experiment49_analysis import theorem_analysis
from experiment49_protocol import (
    ALTERNATIVE_BUDGET,
    ARTIFACT_ROOT,
    MECHANICAL_FIX_ID,
    PROTOCOL_VERSION,
    RAID_DATA_ROOT,
    atomic_json_dump,
    atomic_jsonl_dump,
    exclusive_create_json,
    expected_alternatives,
    file_sha256,
    json_sha256,
    read_json,
    safe_slug,
    validate_code_lock,
)


def _theorem_file_id(th: dict[str, Any]) -> str:
    tid = str(th.get("theorem_id") or "")
    return tid[:20] if tid else json_sha256(
        {"full_name": th["full_name"], "root": th["trace_root_state_sha256"]}
    )[:20]


def validate_config(path: Path) -> tuple[dict[str, Any], Path]:
    cfg = read_json(path)
    if (cfg.get("protocol_version") != PROTOCOL_VERSION
            or cfg.get("mechanical_fix_id") != MECHANICAL_FIX_ID):
        raise ValueError("wrong Exp49 protocol config")
    validate_code_lock(cfg["code_lock"])
    for key in ("source_exp48_config", "source_exp48_confirmation"):
        p = Path(cfg[key])
        if not p.is_file() or file_sha256(p) != cfg[f"{key}_sha256"]:
            raise ValueError(f"frozen source identity changed: {key}")
    for repo in cfg["repositories"]:
        p = Path(repo["selected_file"])
        if not p.is_file() or file_sha256(p) != repo["selected_file_sha256"]:
            raise ValueError(f"frozen selected theorem file changed: {repo['slug']}")
    return cfg, path.parent.parent


def _phase_repositories(cfg: dict[str, Any], phase: str) -> list[str]:
    return list(cfg["smoke_repositories"] if phase == "smoke" else cfg["confirmation_repositories"])


def _phase_theorems(selected: dict[str, Any], phase: str) -> list[dict[str, Any]]:
    return list(selected["smoke"] if phase == "smoke" else selected["formal"])


def _identity(cfg: dict[str, Any], repo: dict[str, Any], th: dict[str, Any], phase: str) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "config_sha256": cfg["frozen_config_sha256_self_excluded"],
        "phase": phase,
        "slug": repo["slug"],
        "commit": repo["commit"],
        "theorem_id": th.get("theorem_id"),
        "full_name": th["full_name"],
        "source_file_sha256": th["source_file_sha256"],
        "trace_root_state_sha256": th["trace_root_state_sha256"],
        "authored_tactic": th["authored_tactic"],
        "alternatives_sha256": json_sha256(th["alternatives"]),
        "source_selected_file_sha256": repo["selected_file_sha256"],
        "candidate_library_sha256": cfg["candidate_library_sha256"],
        "strict_endpoint_schema": cfg["strict_endpoint"]["schema"],
    }


def _run_worker(th: dict[str, Any], repo: dict[str, Any], output: Path,
                generated: Path, lean_timeout: int) -> dict[str, Any]:
    def tail(value: Any, size: int) -> str:
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        return str(value or "")[-size:]

    worker = Path(__file__).resolve().with_name("experiment49_strict_worker.py")
    inputp = output.with_suffix(output.suffix + ".input.json")
    atomic_json_dump({
        "project": repo["checkout"], "slug": repo["slug"], "commit": repo["commit"],
        "file_path": th["file_path"], "full_name": th["full_name"],
        "source_file_sha256": th["source_file_sha256"],
        "trace_root_state": th["trace_root_state"],
        "trace_root_state_sha256": th["trace_root_state_sha256"],
        "authored_tactic": th["authored_tactic"], "alternatives": th["alternatives"],
    }, inputp)
    cmd = [
        sys.executable, str(worker), "--input", str(inputp), "--output", str(output),
        "--generated-dir", str(generated), "--raid-data-root", str(RAID_DATA_ROOT),
        "--timeout", str(lean_timeout),
    ]
    try:
        proc = subprocess.run(
            cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=lean_timeout + 120,
        )
        process = {"returncode": proc.returncode, "stdout": proc.stdout[-6000:],
                   "stderr": proc.stderr[-12000:]}
    except subprocess.TimeoutExpired as exc:
        process = {"returncode": None, "stdout": tail(exc.stdout, 6000),
                   "stderr": tail(exc.stderr, 12000), "timeout": True}
    if not output.is_file():
        value = {"worker_ok": False, "theorem_start_ok": False, "executions": [],
                 "error_type": "WorkerProcessFailure", "error": "worker produced no output"}
        value["worker_process"] = process
        atomic_json_dump(value, output)
        return value
    value = read_json(output)
    value["worker_process"] = process
    atomic_json_dump(value, output)
    return value


def _exp48_source_row(cfg: dict[str, Any], slug: str, rid: str) -> dict[str, Any]:
    p = Path(cfg["source_exp48_confirmation_dir"]) / "theorems" / safe_slug(slug) / f"{rid}.json"
    if not p.is_file():
        raise FileNotFoundError(f"archived Exp48 theorem row missing: {p}")
    return read_json(p)


def _bridge_row(exp49: dict[str, Any], exp48row: dict[str, Any]) -> dict[str, Any]:
    current = exp49["analysis"]["views"]["L0"]["endpoints"]["text48"]
    prior = exp48row["analysis"]
    checks = {
        "evaluable": exp49["analysis"]["evaluable"] == prior.get("evaluable"),
        "primary": current["any_nontrivial_cross_head"] == prior.get("any_nontrivial_cross_head"),
        "nonterminal": current["nonterminal_nontrivial_cross_head"] == prior.get("nonterminal_nontrivial_cross_head"),
        "cross_family": current["cross_family_nontrivial_cross_head"] == prior.get("cross_family_nontrivial_cross_head"),
        "executable_alternatives": current["executable_candidates"] == prior.get("executable_alternatives"),
        "cross_head_pairs": current["cross_head_pairs"] == prior.get("cross_head_pairs"),
    }
    return {"checks": checks, "all_match": all(checks.values())}


def run(args: argparse.Namespace) -> dict[str, Any]:
    cfgp = Path(args.config).resolve()
    cfg, root = validate_config(cfgp)
    phase = args.phase
    preflight = read_json(root / "preflight/strict_worker_compile.json")
    if preflight.get("compile_ok") is not True:
        raise ValueError("Exp49 requires passing compile-only preflight")
    if phase == "validation":
        smoke = read_json(root / "smoke/execution_summary.json")
        if smoke.get("protocol_smoke_ok") is not True:
            raise ValueError("Exp49 validation requires passing strict-worker smoke")

    outdir = root / phase
    summaryp = outdir / "execution_summary.json"
    claimp = root / f"experiment49_{phase}_claim.json"
    if summaryp.exists():
        raise FileExistsError(f"Exp49 {phase} is complete; never overwrite")
    claim = {"version": 1, "protocol_version": PROTOCOL_VERSION, "phase": phase,
             "config_sha256": file_sha256(cfgp)}
    if claimp.exists():
        if not args.resume or read_json(claimp) != claim:
            raise FileExistsError(f"Exp49 {phase} claim exists; use --resume")
    else:
        if args.resume:
            raise FileNotFoundError(f"--resume without Exp49 {phase} claim")
        exclusive_create_json(claimp, claim)
    outdir.mkdir(parents=True, exist_ok=True)

    repo_by = {r["slug"]: r for r in cfg["repositories"]}
    rows: list[dict[str, Any]] = []
    bridges = []
    per_repo = []
    for slug in _phase_repositories(cfg, phase):
        repo = repo_by[slug]
        selected = read_json(repo["selected_file"])
        repo_rows = []
        for th in _phase_theorems(selected, phase):
            expected = expected_alternatives(
                th["authored_tactic"], cfg["alternative_library"], ALTERNATIVE_BUDGET
            )
            if list(th["alternatives"]) != expected:
                raise ValueError(f"frozen alternatives changed: {slug} {th['full_name']}")
            rid = _theorem_file_id(th)
            rowp = outdir / "theorems" / safe_slug(slug) / f"{rid}.json"
            workerp = outdir / "worker" / safe_slug(slug) / f"{rid}.json"
            identity = _identity(cfg, repo, th, phase)
            if rowp.is_file():
                row = read_json(rowp)
                if row.get("identity") != identity:
                    raise ValueError(f"Exp49 resume identity mismatch: {slug} {th['full_name']}")
            else:
                print(f"EXP49-{phase.upper()} {slug} {th['full_name']}", flush=True)
                workerp.parent.mkdir(parents=True, exist_ok=True)
                worker = _run_worker(th, repo, workerp, root / "generated", int(args.lean_timeout))
                analysis = theorem_analysis(worker, th["alternatives"])
                row = {"version": 1, "identity": identity, "selection": th,
                       "worker": worker, "analysis": analysis}
                atomic_json_dump(row, rowp)
                print(f"EXP49-RESULT evaluable={int(analysis['evaluable'])}", flush=True)
            repo_rows.append(row)
            rows.append(row)
            if phase == "validation":
                bridge = _bridge_row(row, _exp48_source_row(cfg, slug, rid))
                bridge.update({"slug": slug, "theorem_id": th.get("theorem_id"),
                               "full_name": th["full_name"]})
                bridges.append(bridge)
        per_repo.append({
            "slug": slug, "attempted": len(repo_rows),
            "evaluable": sum(r["analysis"]["evaluable"] for r in repo_rows),
            "gate_failures": dict(Counter(
                gate for r in repo_rows for gate, ok in r["analysis"]["gates"].items() if not ok
            )),
        })

    expected = int(cfg["expected_smoke_roots"] if phase == "smoke" else cfg["expected_validation_roots"])
    execution_complete = len(rows) == expected
    all_evaluable = execution_complete and all(r["analysis"]["evaluable"] for r in rows)
    bridge_ok = phase != "validation" or (len(bridges) == expected and all(x["all_match"] for x in bridges))
    summary = {
        "version": 1, "protocol_version": PROTOCOL_VERSION, "phase": phase,
        "config_sha256": file_sha256(cfgp), "roots_expected": expected,
        "roots_attempted": len(rows), "evaluable_roots": sum(r["analysis"]["evaluable"] for r in rows),
        "execution_complete": execution_complete, "all_roots_evaluable": all_evaluable,
        "repository_execution": per_repo,
        "exp48_bridge": {
            "applicable": phase == "validation", "rows_checked": len(bridges),
            "all_text48_L0_results_match_archived_exp48": bridge_ok,
            "mismatches": [x for x in bridges if not x["all_match"]],
        },
    }
    if phase == "smoke":
        summary["protocol_smoke_ok"] = all_evaluable
        summary["next_step"] = "Run frozen 96-root validation." if all_evaluable else "STOP and diagnose mechanics only."
    else:
        summary["validation_go"] = bool(all_evaluable and bridge_ok)
        summary["next_step"] = "Run frozen offline analysis." if summary["validation_go"] else "STOP; do not analyze incomplete or unbridged rows."
        atomic_jsonl_dump(bridges, outdir / "exp48_bridge_rows.jsonl")
    atomic_json_dump(summary, summaryp)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", default=str(ARTIFACT_ROOT / "frozen/experiment49_config.json"))
    p.add_argument("--phase", choices=("smoke", "validation"), required=True)
    p.add_argument("--lean-timeout", type=int, default=900)
    p.add_argument("--resume", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    run(parse_args())
