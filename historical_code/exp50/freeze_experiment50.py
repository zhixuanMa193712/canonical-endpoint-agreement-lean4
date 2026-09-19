"""Freeze Exp50 targets, modes, gates, environment declaration, and code."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiment50_protocol import *


def locked_sources() -> list[Path]:
    return [PACKAGE_ROOT / name for name in (
        "experiment50_protocol.py", "experiment50_independent_worker.py",
        "freeze_experiment50.py", "preflight_experiment50.py",
        "capture_experiment50_environment.py", "run_experiment50.py",
        "analyze_experiment50.py", "export_experiment50_bundle.py",
        "run_experiment50_full_pipeline.py",
    )]


def require_no_execution(root: Path) -> None:
    for rel in (
        "preflight/worker_compile.json", "environment/receipt.json",
        "smoke/summary.json", "M0/summary.json", "orders/summary.json",
        "M5/summary.json", "analysis/summary.json",
    ):
        if (root / rel).exists():
            raise ValueError(f"Exp50 must freeze before execution: {rel}")


def validate_sources() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    for path in (SOURCE_EXP48_CONFIG, SOURCE_EXP48_SUMMARY, SOURCE_EXP49_CONFIG,
                 SOURCE_EXP49_VALIDATION, SOURCE_EXP49_ANALYSIS):
        if not path.is_file():
            raise FileNotFoundError(path)
    c48, s48 = read_json(SOURCE_EXP48_CONFIG), read_json(SOURCE_EXP48_SUMMARY)
    c49, v49, a49 = read_json(SOURCE_EXP49_CONFIG), read_json(SOURCE_EXP49_VALIDATION), read_json(SOURCE_EXP49_ANALYSIS)
    if c48.get("protocol_version") != "experiment48-live-tacticinfo-counterfactual-equivalence-v1":
        raise ValueError("wrong Exp48 source config")
    if s48.get("confirmation_go") is not True or s48.get("scientific_metrics_authoritative") is not True:
        raise ValueError("Exp50 requires authoritative Exp48 Confirmation Go")
    if c49.get("protocol_version") != "experiment49-candidate-endpoint-robustness-v1":
        raise ValueError("wrong Exp49 source config")
    if v49.get("validation_go") is not True or v49.get("evaluable_roots") != ROOTS:
        raise ValueError("Exp50 requires passing 96-root Exp49 validation")
    if a49.get("theorem_rows") != ROOTS or a49.get("evaluable_rows") != ROOTS:
        raise ValueError("Exp49 analysis is incomplete")
    if c48.get("target_lean_version") != TARGET_LEAN_VERSION or c48.get("target_toolchain") != TARGET_TOOLCHAIN:
        raise ValueError("Lean anchor changed")
    if c48.get("candidate_library_sha256") != c49.get("candidate_library_sha256"):
        raise ValueError("Exp48/Exp49 candidate library mismatch")
    return c48, s48, c49, v49, a49


def build_targets(c48: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    repos = list(c48["repository_split"]["confirmation"])
    repo_by = {r["slug"]: r for r in c48["repositories"]}
    targets = []
    evidence = []
    for slug in repos:
        repo = dict(repo_by[slug])
        selected_path = Path(repo["selected_file"])
        if not selected_path.is_file() or file_sha256(selected_path) != repo["selected_file_sha256"]:
            raise ValueError(f"selected theorem file changed: {slug}")
        selected = read_json(selected_path)
        if len(selected.get("formal", [])) != ROOTS_PER_REPOSITORY:
            raise ValueError(f"Exp50 requires 24 roots: {slug}")
        for theorem in selected["formal"]:
            alternatives = list(theorem["alternatives"])
            expected = expected_alternatives(theorem["authored_tactic"], c48["alternative_library"])
            if alternatives != expected or len(alternatives) != CANDIDATES_PER_ROOT:
                raise ValueError(f"candidate list changed: {slug} {theorem['full_name']}")
            rid = theorem_file_id(theorem)
            p48 = SOURCE_EXP48_ROOT / "confirmation_fix1/theorems" / safe_slug(slug) / f"{rid}.json"
            raw48 = SOURCE_EXP48_ROOT / "confirmation_fix1/worker" / safe_slug(slug) / f"{rid}.json.lean.json"
            p49 = SOURCE_EXP49_ROOT / "validation/theorems" / safe_slug(slug) / f"{rid}.json"
            raw49 = SOURCE_EXP49_ROOT / "validation/worker" / safe_slug(slug) / f"{rid}.json.lean.json"
            for p in (p48, raw48, p49, raw49):
                if not p.is_file():
                    raise FileNotFoundError(p)
            r48, r49 = read_json(p48), read_json(p49)
            if r48["identity"]["theorem_id"] != theorem["theorem_id"] or r49["identity"]["theorem_id"] != theorem["theorem_id"]:
                raise ValueError(f"archive theorem identity mismatch: {slug} {rid}")
            worker49 = r49["worker"]
            target = {
                "slug": slug, "commit": repo["commit"], "url": repo["url"],
                "checkout": repo["checkout"], "selected_file": str(selected_path),
                "selected_file_sha256": repo["selected_file_sha256"],
                "theorem_id": theorem["theorem_id"], "rid": rid,
                "full_name": theorem["full_name"], "file_path": theorem["file_path"],
                "source_file_sha256": theorem["source_file_sha256"],
                "trace_root_state": theorem["trace_root_state"],
                "trace_root_state_sha256": theorem["trace_root_state_sha256"],
                "authored_tactic": theorem["authored_tactic"],
                "alternatives": alternatives, "alternatives_sha256": json_sha256(alternatives),
                "target_pos": worker49["target_pos"], "target_end_pos": worker49["target_end_pos"],
                "ast_sha256": worker49["ast_sha256"],
                "source_exp48_row": str(p48), "source_exp48_row_sha256": file_sha256(p48),
                "source_exp48_raw": str(raw48), "source_exp48_raw_sha256": file_sha256(raw48),
                "source_exp49_row": str(p49), "source_exp49_row_sha256": file_sha256(p49),
                "source_exp49_raw": str(raw49), "source_exp49_raw_sha256": file_sha256(raw49),
            }
            target["target_identity_sha256"] = json_sha256(target)
            targets.append(target)
            evidence.extend({"path": str(p), "sha256": file_sha256(p), "bytes": p.stat().st_size}
                            for p in (p48, raw48, p49, raw49))
    if len(targets) != ROOTS:
        raise ValueError("Exp50 requires exactly 96 frozen targets")
    return targets, evidence


def build_config(created: str, args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    c48, s48, c49, v49, a49 = validate_sources()
    targets, evidence = build_targets(c48)
    repos = list(c48["repository_split"]["confirmation"])
    config: dict[str, Any] = {
        "version": 1, "protocol_version": PROTOCOL_VERSION, "created_utc": created,
        "study_role": "exact execution reproducibility and infrastructure validation over reused Exp48 roots; not a new scientific sample",
        "operator_statement": {
            "operator_id": args.operator_id,
            "machine_id": args.machine_id,
            "environment_mode": args.environment_mode,
            "runner_authorship": "separately packaged Exp50 implementation; imports no Exp48/Exp49 runner or analysis code",
            "independence_boundary": args.independence_boundary,
        },
        "target_lean_version": TARGET_LEAN_VERSION, "target_toolchain": TARGET_TOOLCHAIN,
        "repositories": repos, "roots": ROOTS, "roots_per_repository": ROOTS_PER_REPOSITORY,
        "candidates_per_root": CANDIDATES_PER_ROOT,
        "candidate_library_sha256": c48["candidate_library_sha256"],
        "order_modes": list(ORDER_MODES), "all_modes": list(ALL_MODES),
        "random_order_seeds": RANDOM_ORDER_SEEDS,
        "M5_process_contract": "one new lake env lean --run process per (root,candidate), with authored replay in every process",
        "smoke_target_ids": [x["theorem_id"] for x in targets[:SMOKE_ROOTS]],
        "smoke_M5_candidates_per_root": SMOKE_M5_CANDIDATES_PER_ROOT,
        "source": {
            "exp48_config": str(SOURCE_EXP48_CONFIG), "exp48_config_sha256": file_sha256(SOURCE_EXP48_CONFIG),
            "exp48_summary": str(SOURCE_EXP48_SUMMARY), "exp48_summary_sha256": file_sha256(SOURCE_EXP48_SUMMARY),
            "exp49_config": str(SOURCE_EXP49_CONFIG), "exp49_config_sha256": file_sha256(SOURCE_EXP49_CONFIG),
            "exp49_validation": str(SOURCE_EXP49_VALIDATION), "exp49_validation_sha256": file_sha256(SOURCE_EXP49_VALIDATION),
            "exp49_analysis": str(SOURCE_EXP49_ANALYSIS), "exp49_analysis_sha256": file_sha256(SOURCE_EXP49_ANALYSIS),
            "exp48_confirmation_go": s48["confirmation_go"],
            "exp49_validation_go": v49["validation_go"], "exp49_robustness": a49["robustness"]["label"],
        },
        "source_evidence_lock": {"rows": evidence, "bundle_sha256": json_sha256(evidence)},
        "gates": {
            "M0_roots_evaluable": ROOTS,
            "candidate_attempts_each_mode": ROOTS * CANDIDATES_PER_ROOT,
            "M0_exact_exp48_text_and_status": True,
            "M0_exact_exp48_aggregates": True,
            "M0_exact_exp49_strict": True,
            "M1_M4_exact_M0": True,
            "M5_exact_M0": True,
            "manual_reconciliation": 0,
        },
        "comparison_exclusions": ["wall-clock time", "process ids", "stdout/stderr byte equality"],
        "claim_boundary": [
            "Exp50 does not add repositories or estimate prevalence",
            "no runtime equivalence or proof-term equality",
            "no global tactic interchangeability or prover-improvement claim",
        ],
        "code_lock": code_lock(locked_sources()),
        "next_step": "Compile-only preflight, then capture the independent environment receipt.",
    }
    config["config_identity_sha256"] = json_sha256(
        {k: v for k, v in config.items() if k not in {"created_utc", "config_identity_sha256"}}
    )
    return config, targets


def freeze(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.output_dir).resolve()
    frozen = root / "frozen"
    cfgp = frozen / "experiment50_config.json"
    targetsp = frozen / "targets.json"
    claimp = frozen / "freeze_claim.json"
    txp = frozen / "freeze_transaction.json"
    receiptp = frozen / "freeze_receipt.json"
    if txp.is_file() and read_json(txp).get("completed") is True:
        cfg = read_json(cfgp)
        validate_code_lock(cfg["code_lock"])
        print(json.dumps({"already_frozen": True, "config": str(cfgp)}, indent=2))
        return cfg
    require_no_execution(root)
    if claimp.exists():
        if not args.resume_freeze:
            raise FileExistsError("use --resume-freeze")
        claim = read_json(claimp)
        cfg, targets = build_config(claim["created_utc"], args)
        if cfg["config_identity_sha256"] != claim["config_identity_sha256"]:
            raise ValueError("freeze reconstruction changed")
    else:
        if args.resume_freeze:
            raise FileNotFoundError("--resume-freeze without claim")
        created = datetime.now(timezone.utc).isoformat()
        cfg, targets = build_config(created, args)
        exclusive_create_json(claimp, {"version": 1, "protocol_version": PROTOCOL_VERSION,
            "created_utc": created, "config_identity_sha256": cfg["config_identity_sha256"]})
    atomic_json_dump({"version": 1, "completed": False}, txp)
    atomic_json_dump(cfg, cfgp)
    atomic_json_dump(targets, targetsp)
    receipt = {"version": 1, "config_sha256": file_sha256(cfgp),
               "targets_sha256": file_sha256(targetsp), "targets": len(targets),
               "execution_before_freeze": False, "operator_statement": cfg["operator_statement"]}
    atomic_json_dump(receipt, receiptp)
    atomic_json_dump({"version": 1, "completed": True, "config_sha256": file_sha256(cfgp),
                      "targets_sha256": file_sha256(targetsp),
                      "receipt_sha256": file_sha256(receiptp)}, txp)
    print(json.dumps({"config": str(cfgp), "targets": len(targets),
                      "modes": cfg["all_modes"], "operator_statement": cfg["operator_statement"],
                      "next_step": cfg["next_step"]}, ensure_ascii=False, indent=2))
    return cfg


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", default=str(ARTIFACT_ROOT))
    p.add_argument("--operator-id", default="music")
    p.add_argument("--machine-id", default="gpuserver01")
    p.add_argument("--environment-mode", default="same-server-frozen-checkouts")
    p.add_argument("--independence-boundary", default="independent runner implementation and fresh processes; same physical server and archived checkouts")
    p.add_argument("--resume-freeze", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    freeze(parse_args())
