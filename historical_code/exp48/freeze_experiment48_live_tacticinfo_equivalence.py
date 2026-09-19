"""Freeze Experiment 48 before any exact-state candidate execution."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiment48_protocol import *

FROZEN_CONFIG = Path("frozen/experiment48_config.json")
FREEZE_CLAIM = Path("frozen/experiment48_freeze_claim.json")
FREEZE_TX = Path("frozen/experiment48_freeze_transaction.json")
FREEZE_RECEIPT = Path("frozen/experiment48_freeze_receipt.json")


def _require_no_exp48_execution(root: Path) -> None:
    for rel in ("smoke/summary.json", "discovery/summary.json", "confirmation/summary.json"):
        if (root / rel).exists():
            raise ValueError(f"Exp48 must freeze before execution: {rel}")


def _validate_probe(probe: dict[str, Any]) -> None:
    required = {
        "diagnostic_only": True,
        "scientific_metrics_authoritative": False,
        "scientific_candidate_tactics_executed": 0,
        "fresh_trace_performed": False,
        "serialized_state_restoration_used": False,
        "pantograph_used": False,
        "lean_compile_ok": True,
        "theorem_rows": 6,
        "target_info_nodes_found": 6,
        "frozen_trace_root_matches": 6,
        "authored_replay1_exact": 6,
        "authored_replay2_exact": 6,
        "double_replay_exact": 6,
        "live_tacticinfo_mechanics_qualified": True,
    }
    for key, expected in required.items():
        if probe.get(key) != expected:
            raise ValueError(f"Exp48 mechanics qualification failed: {key}={probe.get(key)!r} expected {expected!r}")


def build_config(created_utc: str, exp46_config_path: Path, probe_path: Path) -> dict[str, Any]:
    if not exp46_config_path.is_file() or not probe_path.is_file():
        raise FileNotFoundError("Exp46 frozen config or Exp47 live-TacticInfo qualification missing")
    e46 = read_json(exp46_config_path)
    probe = read_json(probe_path)
    _validate_probe(probe)
    if e46.get("protocol_version") != "experiment46-eight-repo-cross-repository-executable-effect-equivalence-v1":
        raise ValueError("wrong Exp46 source config")
    if e46.get("target_lean_version") != TARGET_LEAN_VERSION or e46.get("target_toolchain") != TARGET_TOOLCHAIN:
        raise ValueError("Exp48 exact Lean anchor changed")
    repos = [dict(r) for r in e46.get("repositories", [])]
    split = e46.get("repository_split")
    if len(repos) != EXPECTED_REPOSITORIES:
        raise ValueError(f"Exp48 requires exactly {EXPECTED_REPOSITORIES} frozen repos")
    if len(split.get("discovery", [])) != DISCOVERY_REPOSITORIES or len(split.get("confirmation", [])) != CONFIRMATION_REPOSITORIES:
        raise ValueError("Exp48 inherits the exact Exp46 4/4 split")
    if list(e46.get("smoke_repositories", [])) != list(split["discovery"][:SMOKE_REPOSITORIES]):
        raise ValueError("Exp48 smoke repo anchor changed")
    library = list(e46.get("alternative_library", []))
    if not library or int(e46.get("alternative_budget", -1)) != ALTERNATIVE_BUDGET:
        raise ValueError("Exp48 candidate library/budget anchor changed")
    for repo in repos:
        selected_path = Path(repo["selected_file"])
        if not selected_path.is_file() or file_sha256(selected_path) != repo["selected_file_sha256"]:
            raise ValueError(f"frozen selected file changed: {repo['slug']}")
        selected = read_json(selected_path)
        if selected.get("ready") is not True or int(selected.get("formal_count", -1)) != TARGET_FORMAL_THEOREMS_PER_REPO:
            raise ValueError(f"Exp48 requires 24 frozen formal theorems: {repo['slug']}")
        for kind in ("formal", "smoke"):
            for th in selected.get(kind, []):
                alts = list(th.get("alternatives", []))
                expected = expected_alternatives(str(th["authored_tactic"]), library, ALTERNATIVE_BUDGET)
                if alts != expected:
                    raise ValueError(f"frozen theorem alternatives changed: {repo['slug']} {th['full_name']}")
                if len(alts) != ALTERNATIVE_BUDGET:
                    raise ValueError("candidate budget mismatch")

    here = Path(__file__).resolve().parent
    locked = [
        here / "experiment48_protocol.py",
        here / "experiment48_live_tacticinfo_worker.py",
        here / "experiment48_analysis.py",
        here / "preflight_experiment48_live_worker.py",
        here / "freeze_experiment48_live_tacticinfo_equivalence.py",
        here / "run_experiment48_live_tacticinfo_equivalence.py",
        here / "export_experiment48_mac_bundle.py",
        here / "run_experiment48_full_pipeline.py",
        here / "tests/test_experiment48_protocol.py",
        here / "tests/test_experiment48_preflight_static.py",
        here / "tests/test_experiment48_analysis.py",
        here / "tests/test_experiment48_worker_static.py",
        here / "tests/test_experiment48_runner_static.py",
    ]
    config = {
        "version": 1,
        "protocol_version": PROTOCOL_VERSION,
        "created_utc": created_utc,
        "scientific_experiment": True,
        "source_exp46_config": str(exp46_config_path.resolve()),
        "source_exp46_config_sha256": file_sha256(exp46_config_path),
        "source_live_tacticinfo_qualification": str(probe_path.resolve()),
        "source_live_tacticinfo_qualification_sha256": file_sha256(probe_path),
        "source_live_tacticinfo_qualification_probe_id": probe.get("probe_id"),
        "scientific_candidate_tactics_executed_during_backend_qualification": 0,
        "source_exp46_exp47_formal_scientific_outcomes_used_for_backend_selection": False,
        "source_exp46_exp47_note": "Exp46/Exp47 protocol smokes had zero evaluable theorem roots; wrong-root candidate behavior was not used to tune the frozen candidate library, theorem sample, repository frame, or gates.",
        "target_lean_version": TARGET_LEAN_VERSION,
        "target_toolchain": TARGET_TOOLCHAIN,
        "execution_backend": {
            "name": "live_lean_tacticinfo_branch",
            "state_source": "unchanged exact source elaboration InfoTree TacticInfo",
            "pre_state": "ContextInfo plus TacticInfo.mctxBefore plus TacticInfo.goalsBefore",
            "branch_runner": "Lean.Elab.Tactic.run on the unique pre-state MVarId with independent MetaM executions",
            "authored_validation": "exact authored Syntax replay must reproduce original live TacticInfo stateAfter",
            "serialized_state_restoration": False,
            "pantograph": False,
            "single_goal_pre_state_required": True,
        },
        "repositories": repos,
        "excluded_repositories": list(e46.get("excluded_repositories", [])),
        "repository_split": split,
        "smoke_repositories": list(e46["smoke_repositories"]),
        "formal_theorems_per_repo": TARGET_FORMAL_THEOREMS_PER_REPO,
        "alternative_budget": ALTERNATIVE_BUDGET,
        "alternative_library": library,
        "candidate_library_sha256": json_sha256(library),
        "primary_estimand": "repo-level fraction of evaluable formal theorem roots for which at least two executable frozen alternatives with distinct tactic heads reach the same non-initial canonical live Lean endpoint",
        "secondary_estimands": [
            "authored-anchor cross-head endpoint equivalence",
            "nonterminal cross-head endpoint equivalence",
            "cross-family endpoint equivalence",
            "cross-repository head-pair breadth and recurrence",
        ],
        "endpoint_semantics": {
            "raw": "LeanDojo-compatible pretty print of live post-tactic goals using the same Pp routine as extraction",
            "canonicalization": "normalize generated IDs and horizontal whitespace; compare only within the same theorem root",
            "nontrivial": "canonical endpoint differs from the canonical initial live state",
            "terminal": "zero goals / 'no goals'",
        },
        "evaluable_gate": [
            "unique frozen TacticInfo root edge found in exact ast/source identity",
            "live root canonical text matches frozen trace root",
            "live pre-state has exactly one goal",
            "authored syntax replay is executable and exactly reproduces original live stateAfter",
            "all 23 frozen alternatives are attempted independently from the same pre-state",
        ],
        "confirmation_gate": dict(CONFIRMATION_GATE),
        "strong_go_diagnostics": dict(STRONG_GO_DIAGNOSTICS),
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "prohibitions": [
            "do not change the eight-repository frame or 4/4 split after freeze",
            "do not change theorem samples after freeze",
            "do not change the 23-alternative library or per-theorem deterministic duplicate-removal rule",
            "do not relax the single-goal live-state backend gate based on outcomes",
            "do not alter endpoint canonicalization based on discovery outcomes",
            "do not change confirmation thresholds after smoke/discovery",
            "do not interpret smoke outcomes as confirmation evidence",
        ],
        "code_lock": code_lock(locked),
        "next_step": "Run Exp48 exact-state protocol smoke; if it passes, run frozen discovery and untouched confirmation.",
    }
    config["config_identity_sha256"] = json_sha256({k: v for k, v in config.items() if k != "created_utc"})
    return config


def freeze(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    _require_no_exp48_execution(root)
    claimp, txp = root / FREEZE_CLAIM, root / FREEZE_TX
    cfgp, receiptp = root / FROZEN_CONFIG, root / FREEZE_RECEIPT
    if txp.is_file() and read_json(txp).get("completed") is True:
        cfg = read_json(cfgp)
        validate_code_lock(cfg["code_lock"])
        return cfg
    if claimp.exists():
        if not args.resume_freeze:
            raise FileExistsError("Exp48 freeze claim exists; use --resume-freeze")
        claim = read_json(claimp)
        cfg = build_config(claim["created_utc"], Path(args.source_exp46_config).resolve(), Path(args.source_probe).resolve())
        if cfg["config_identity_sha256"] != claim["config_identity_sha256"]:
            raise ValueError("Exp48 freeze reconstruction differs from claim")
    else:
        if args.resume_freeze:
            raise FileNotFoundError("--resume-freeze without claim")
        created = datetime.now(timezone.utc).isoformat()
        cfg = build_config(created, Path(args.source_exp46_config).resolve(), Path(args.source_probe).resolve())
        exclusive_create_json(claimp, {
            "version": 1,
            "protocol_version": PROTOCOL_VERSION,
            "created_utc": created,
            "config_identity_sha256": cfg["config_identity_sha256"],
        })
    atomic_json_dump({"version": 1, "completed": False, "phase": "claim_committed"}, txp)
    if cfgp.exists() and read_json(cfgp) != cfg:
        raise ValueError("existing Exp48 config differs")
    if not cfgp.exists():
        atomic_json_dump(cfg, cfgp)
    receipt = {
        "version": 1,
        "protocol_version": PROTOCOL_VERSION,
        "config": str(cfgp.resolve()),
        "config_sha256": file_sha256(cfgp),
        "counterfactual_execution_before_freeze": False,
        "backend_qualification_scientific_candidates": 0,
        "repositories": len(cfg["repositories"]),
        "discovery": len(cfg["repository_split"]["discovery"]),
        "confirmation": len(cfg["repository_split"]["confirmation"]),
    }
    if receiptp.exists() and read_json(receiptp) != receipt:
        raise ValueError("existing Exp48 receipt differs")
    if not receiptp.exists():
        atomic_json_dump(receipt, receiptp)
    atomic_json_dump({
        "version": 1,
        "completed": True,
        "phase": "completed",
        "config_sha256": file_sha256(cfgp),
        "receipt_sha256": file_sha256(receiptp),
    }, txp)
    print(json.dumps({
        "config": str(cfgp),
        "repository_split": cfg["repository_split"],
        "smoke_repositories": cfg["smoke_repositories"],
        "execution_backend": cfg["execution_backend"],
        "confirmation_gate": cfg["confirmation_gate"],
        "next_step": cfg["next_step"],
    }, ensure_ascii=False, indent=2))
    return cfg


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", default=str(ARTIFACT_ROOT))
    p.add_argument("--source-exp46-config", default=str(SOURCE_EXP46_CONFIG))
    p.add_argument("--source-probe", default=str(SOURCE_EXP47_PROBE))
    p.add_argument("--resume-freeze", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    freeze(parse_args())
