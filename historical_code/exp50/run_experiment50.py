"""Run frozen Exp50 smoke, M0, order perturbations, or M5 isolation."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from experiment50_protocol import *

WORKER = PACKAGE_ROOT / "experiment50_independent_worker.py"


def load_frozen(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    cfgp = root / "frozen/experiment50_config.json"
    targetsp = root / "frozen/targets.json"
    envp = root / "environment/receipt.json"
    for path in (cfgp, targetsp, envp):
        if not path.is_file():
            raise FileNotFoundError(path)
    cfg, targets, env = read_json(cfgp), read_json(targetsp), read_json(envp)
    validate_code_lock(cfg["code_lock"])
    cfg_sha = file_sha256(cfgp)
    if env.get("environment_gate") is not True or env.get("config_sha256") != cfg_sha:
        raise ValueError("Exp50 environment gate did not pass for this freeze")
    if len(targets) != ROOTS:
        raise ValueError("wrong Exp50 target count")
    return cfg, targets, cfg_sha


def worker_input(root: Path, target: dict[str, Any], mode: str,
                 candidates: list[str]) -> dict[str, Any]:
    value = {
        "version": 1, "protocol_version": PROTOCOL_VERSION,
        "config_sha256": file_sha256(root / "frozen/experiment50_config.json"),
        "environment_receipt_sha256": file_sha256(root / "environment/receipt.json"),
        "artifact_root": str(root), "mode": mode,
        "project": target["checkout"], "slug": target["slug"],
        "commit": target["commit"], "file_path": target["file_path"],
        "full_name": target["full_name"], "theorem_id": target["theorem_id"],
        "source_file_sha256": target["source_file_sha256"],
        "trace_root_state": target["trace_root_state"],
        "trace_root_state_sha256": target["trace_root_state_sha256"],
        "authored_tactic": target["authored_tactic"],
        "target_pos": target["target_pos"], "target_end_pos": target["target_end_pos"],
        "ast_sha256": target["ast_sha256"], "candidates": candidates,
        "candidates_sha256": json_sha256(candidates),
        "candidate_positions_frozen": [target["alternatives"].index(x) for x in candidates],
        "target_identity_sha256": target["target_identity_sha256"],
    }
    value["execution_record_id"] = json_sha256({
        "protocol_version": PROTOCOL_VERSION, "mode": mode,
        "target_identity_sha256": target["target_identity_sha256"],
        "candidates": candidates,
    })
    return value


def assert_existing(row: dict[str, Any], target: dict[str, Any], mode: str,
                    candidates: list[str]) -> None:
    checks = (
        row.get("protocol_version", PROTOCOL_VERSION) == PROTOCOL_VERSION,
        row.get("mode") == mode,
        row.get("theorem_id") == target["theorem_id"],
        row.get("source_file_sha256") == target["source_file_sha256"],
        row.get("candidate_order") == candidates,
        row.get("lean_source_sha256") is not None,
    )
    if not all(checks):
        raise ValueError(f"existing Exp50 row identity mismatch: {mode} {target['theorem_id']}")


def invoke(root: Path, target: dict[str, Any], mode: str, candidates: list[str],
           outp: Path, inputp: Path, args: argparse.Namespace) -> dict[str, Any]:
    if outp.exists():
        row = read_json(outp)
        assert_existing(row, target, mode, candidates)
        return row
    inp = worker_input(root, target, mode, candidates)
    atomic_json_dump(inp, inputp)
    cmd = [sys.executable, str(WORKER), "--input", str(inputp), "--output", str(outp),
           "--generated-dir", str(root / "generated"), "--timeout", str(args.lean_timeout)]
    proc = subprocess.run(cmd, cwd=PACKAGE_ROOT, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=args.lean_timeout + 120)
    if not outp.is_file():
        raise RuntimeError(f"Exp50 Python worker failed without record: {proc.returncode}\n{proc.stderr[-8000:]}")
    row = read_json(outp)
    assert_existing(row, target, mode, candidates)
    return row


def branch_fingerprint(branch: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"tactic": branch.get("tactic"),
                           "executable": branch.get("executable") is True}
    if out["executable"]:
        out.update({
            "goal_count": branch.get("goal_count"), "terminal": branch.get("terminal"),
            "raw": branch["endpoints"]["raw"]["sha256"],
            "text48": branch["endpoints"]["text48"]["sha256"],
            "struct": branch["endpoints"]["struct"]["sha256"],
        })
    else:
        out["failure_category"] = branch.get("failure_category")
    return out


def exact_rows(left: dict[str, Any], right: dict[str, Any]) -> bool:
    lm = {x["tactic"]: branch_fingerprint(x) for x in left.get("candidates", [])}
    rm = {x["tactic"]: branch_fingerprint(x) for x in right.get("candidates", [])}
    return bool(left.get("worker_ok") and right.get("worker_ok") and lm == rm)


def phase_claim(root: Path, name: str, cfg_sha: str) -> None:
    path = root / f"{name}/execution_claim.json"
    if path.exists():
        old = read_json(path)
        if old.get("config_sha256") != cfg_sha:
            raise ValueError(f"{name} claim belongs to another freeze")
        return
    exclusive_create_json(path, {"version": 1, "protocol_version": PROTOCOL_VERSION,
                                  "phase": name, "config_sha256": cfg_sha})


def mode_paths(root: Path, phase_dir: str, mode: str, target: dict[str, Any],
               candidate_index: int | None = None) -> tuple[Path, Path]:
    slug = safe_slug(target["slug"])
    rid = target["rid"]
    if candidate_index is None:
        base = root / phase_dir
        return (base / "theorems" / slug / f"{rid}.json",
                base / "inputs" / slug / f"{rid}.json")
    base = root / phase_dir / "processes" / slug / rid
    return base / f"{candidate_index:02d}.json", base / f"{candidate_index:02d}.input.json"


def summarize_mode(root: Path, mode: str, rows: list[dict[str, Any]], expected_roots: int,
                   expected_candidates: int, output: Path, cfg_sha: str) -> dict[str, Any]:
    repository_execution = []
    for slug in sorted({x["slug"] for x in rows}):
        rs = [x for x in rows if x["slug"] == slug]
        failures = Counter(x.get("error_type", "worker_gate") for x in rs if not x.get("worker_ok"))
        repository_execution.append({"slug": slug, "attempted": len(rs),
                                     "evaluable": sum(x.get("worker_ok") is True for x in rs),
                                     "gate_failures": dict(sorted(failures.items()))})
    value = {
        "version": 1, "protocol_version": PROTOCOL_VERSION, "mode": mode,
        "config_sha256": cfg_sha, "roots_expected": expected_roots,
        "roots_attempted": len(rows),
        "candidate_attempts_expected": expected_candidates,
        "candidate_attempts": sum(len(x.get("candidates", [])) for x in rows),
        "evaluable_roots": sum(x.get("worker_ok") is True for x in rows),
        "repository_execution": repository_execution,
    }
    value["execution_complete"] = (value["roots_attempted"] == expected_roots and
                                   value["candidate_attempts"] == expected_candidates)
    value["mode_gate"] = bool(value["execution_complete"] and
                              value["evaluable_roots"] == expected_roots)
    atomic_json_dump(value, output)
    return value


def run_regular_mode(root: Path, targets: list[dict[str, Any]], mode: str,
                     phase_dir: str, args: argparse.Namespace, cfg_sha: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    summaryp = root / phase_dir / "summary.json"
    selected = targets
    if summaryp.exists():
        summary = read_json(summaryp)
        if summary.get("config_sha256") != cfg_sha:
            raise ValueError(f"existing {mode} summary belongs to another freeze")
    rows = []
    for index, target in enumerate(selected, 1):
        candidates = candidate_order(mode, target["alternatives"], target["slug"],
                                     target["theorem_id"], target["full_name"])
        outp, inputp = mode_paths(root, phase_dir, mode, target)
        print(f"EXP50-{mode} {index}/{len(selected)} {target['slug']} {target['full_name']}", flush=True)
        row = invoke(root, target, mode, candidates, outp, inputp, args)
        print(f"EXP50-RESULT worker_ok={int(row.get('worker_ok') is True)} candidates={len(row.get('candidates', []))}", flush=True)
        rows.append(row)
    summary = summarize_mode(root, mode, rows, len(selected),
                             len(selected) * CANDIDATES_PER_ROOT,
                             summaryp, cfg_sha)
    return rows, summary


def run_m5(root: Path, targets: list[dict[str, Any]], phase_dir: str,
           args: argparse.Namespace, cfg_sha: str, smoke_candidates: int | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    theorem_dir = root / phase_dir / "theorems"
    aggregate_rows = []
    process_count = 0
    candidates_expected = 0
    for root_index, target in enumerate(targets, 1):
        ordered = candidate_order("M5", target["alternatives"], target["slug"],
                                  target["theorem_id"], target["full_name"])
        if smoke_candidates is not None:
            ordered = ordered[:smoke_candidates]
        candidates_expected += len(ordered)
        process_rows = []
        for candidate_index, candidate in enumerate(ordered):
            outp, inputp = mode_paths(root, phase_dir, "M5", target, candidate_index)
            print(f"EXP50-M5 root={root_index}/{len(targets)} candidate={candidate_index + 1}/{len(ordered)} {target['slug']} {target['full_name']}", flush=True)
            process_rows.append(invoke(root, target, "M5", [candidate], outp, inputp, args))
            process_count += 1
        first = process_rows[0]
        anchor = next((x for x in process_rows if x.get("worker_ok") is True), first)
        consistent_pre = all(
            x.get("worker_ok") is True
            and x["initial_endpoints"]["text48"]["sha256"] == anchor["initial_endpoints"]["text48"]["sha256"]
            and x["initial_endpoints"]["struct"]["sha256"] == anchor["initial_endpoints"]["struct"]["sha256"]
            and x["authored"]["endpoints"]["text48"]["sha256"] == anchor["authored"]["endpoints"]["text48"]["sha256"]
            and x["authored"]["endpoints"]["struct"]["sha256"] == anchor["authored"]["endpoints"]["struct"]["sha256"]
            for x in process_rows
        )
        candidates = [x["candidates"][0] for x in process_rows if len(x.get("candidates", [])) == 1]
        aggregate = {
            "version": 1, "protocol_version": PROTOCOL_VERSION, "mode": "M5",
            "slug": target["slug"], "commit": target["commit"],
            "file_path": target["file_path"], "full_name": target["full_name"],
            "theorem_id": target["theorem_id"], "source_file_sha256": target["source_file_sha256"],
            "candidate_order": ordered, "candidate_order_sha256": json_sha256(ordered),
            "initial_endpoints": anchor.get("initial_endpoints"),
            "original_authored_endpoints": anchor.get("original_authored_endpoints"),
            "authored": anchor.get("authored"), "candidates": candidates,
            "fresh_lean_processes": len(process_rows),
            "process_record_sha256": [x.get("record_sha256") for x in process_rows],
            "authored_and_pre_consistent_across_processes": consistent_pre,
            "worker_ok": bool(consistent_pre and len(candidates) == len(ordered)),
        }
        aggregate["record_sha256"] = json_sha256({k: v for k, v in aggregate.items() if k != "record_sha256"})
        aggregatep = theorem_dir / safe_slug(target["slug"]) / f"{target['rid']}.json"
        if aggregatep.exists():
            old = read_json(aggregatep)
            if old.get("record_sha256") != aggregate["record_sha256"]:
                raise ValueError(f"M5 aggregate changed: {target['theorem_id']}")
        else:
            atomic_json_dump(aggregate, aggregatep)
        aggregate_rows.append(aggregate)
    summaryp = root / phase_dir / "summary.json"
    summary = summarize_mode(root, "M5", aggregate_rows, len(targets),
                             candidates_expected, summaryp, cfg_sha)
    summary["fresh_lean_processes_expected"] = candidates_expected
    summary["fresh_lean_processes_observed"] = process_count
    summary["one_process_per_root_candidate"] = process_count == candidates_expected
    summary["mode_gate"] = bool(summary["mode_gate"] and summary["one_process_per_root_candidate"])
    atomic_json_dump(summary, summaryp)
    return aggregate_rows, summary


def run_smoke(root: Path, targets: list[dict[str, Any]], args: argparse.Namespace,
              cfg_sha: str) -> dict[str, Any]:
    summaryp = root / "smoke/summary.json"
    if summaryp.exists():
        value = read_json(summaryp)
        if value.get("config_sha256") != cfg_sha:
            raise ValueError("smoke summary belongs to another freeze")
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value
    phase_claim(root, "smoke", cfg_sha)
    chosen = targets[:SMOKE_ROOTS]
    m0, s0 = run_regular_mode(root, chosen, "M0", "smoke/M0", args, cfg_sha)
    m1, s1 = run_regular_mode(root, chosen, "M1", "smoke/M1", args, cfg_sha)
    m5, s5 = run_m5(root, chosen, "smoke/M5", args, cfg_sha,
                    smoke_candidates=SMOKE_M5_CANDIDATES_PER_ROOT)
    m0_by = {x["theorem_id"]: x for x in m0}
    exact_m1 = all(exact_rows(m0_by[x["theorem_id"]], x) for x in m1)
    exact_m5 = True
    for row in m5:
        baseline = {x["tactic"]: branch_fingerprint(x) for x in m0_by[row["theorem_id"]]["candidates"]}
        exact_m5 = exact_m5 and row.get("worker_ok") is True and all(
            baseline[x["tactic"]] == branch_fingerprint(x) for x in row["candidates"])
    checks = {"M0_gate": s0["mode_gate"], "M1_gate": s1["mode_gate"],
              "M5_gate": s5["mode_gate"], "M1_exact_M0": exact_m1,
              "M5_subset_exact_M0": exact_m5}
    value = {"version": 1, "protocol_version": PROTOCOL_VERSION,
             "config_sha256": cfg_sha, "roots": len(chosen),
             "M5_candidates_per_root": SMOKE_M5_CANDIDATES_PER_ROOT,
             "checks": checks, "smoke_gate": all(checks.values())}
    value["next_step"] = "Run M0." if value["smoke_gate"] else "STOP; do not run the 96-root phases."
    atomic_json_dump(value, summaryp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def require_gate(path: Path, key: str) -> None:
    if not path.is_file() or read_json(path).get(key) is not True:
        raise ValueError(f"required Exp50 gate absent: {path} -> {key}")


def run_phase(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    cfg, targets, cfg_sha = load_frozen(root)
    if args.phase == "smoke":
        return run_smoke(root, targets, args, cfg_sha)
    require_gate(root / "smoke/summary.json", "smoke_gate")
    if args.phase == "M0":
        phase_claim(root, "M0", cfg_sha)
        _, summary = run_regular_mode(root, targets, "M0", "M0", args, cfg_sha)
        summary["next_step"] = "Run order perturbations M1-M4." if summary["mode_gate"] else "STOP."
        atomic_json_dump(summary, root / "M0/summary.json")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return summary
    require_gate(root / "M0/summary.json", "mode_gate")
    if args.phase == "orders":
        phase_claim(root, "orders", cfg_sha)
        mode_summaries = []
        all_ok = True
        for mode in ("M1", "M2", "M3", "M4"):
            _, summary = run_regular_mode(root, targets, mode, f"orders/{mode}", args, cfg_sha)
            mode_summaries.append(summary)
            all_ok = all_ok and summary["mode_gate"]
            if not summary["mode_gate"]:
                break
        value = {"version": 1, "protocol_version": PROTOCOL_VERSION,
                 "config_sha256": cfg_sha, "modes_expected": ["M1", "M2", "M3", "M4"],
                 "mode_summaries": mode_summaries,
                 "orders_execution_gate": bool(all_ok and len(mode_summaries) == 4)}
        value["next_step"] = "Run M5 process isolation." if value["orders_execution_gate"] else "STOP."
        atomic_json_dump(value, root / "orders/summary.json")
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value
    if args.phase == "M5":
        require_gate(root / "orders/summary.json", "orders_execution_gate")
        phase_claim(root, "M5", cfg_sha)
        _, summary = run_m5(root, targets, "M5", args, cfg_sha)
        summary["next_step"] = "Run frozen exact comparison analysis." if summary["mode_gate"] else "STOP."
        atomic_json_dump(summary, root / "M5/summary.json")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return summary
    raise KeyError(args.phase)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    p.add_argument("--phase", required=True, choices=("smoke", "M0", "orders", "M5"))
    p.add_argument("--lean-timeout", type=int, default=900)
    return p.parse_args()


if __name__ == "__main__":
    cli = parse_args()
    result = run_phase(cli)
    key = {"smoke": "smoke_gate", "M0": "mode_gate",
           "orders": "orders_execution_gate", "M5": "mode_gate"}[cli.phase]
    raise SystemExit(0 if result.get(key) else 2)
