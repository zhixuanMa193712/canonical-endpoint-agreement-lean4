"""Freeze Exp49 before its compile preflight or any theorem execution."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiment49_protocol import (
    ALTERNATIVE_BUDGET,
    ARTIFACT_ROOT,
    BOOTSTRAP_REPLICATES,
    BOOTSTRAP_SEED,
    CANDIDATE_VIEWS,
    CONFIRMATION_REPOSITORIES,
    ENDPOINT_KINDS,
    MECHANICAL_FIX_ID,
    PROTOCOL_VERSION,
    RAREFACTION_BUDGETS,
    RAREFACTION_REPLICATES,
    RAREFACTION_SEED,
    ROOTS_PER_REPOSITORY,
    SOURCE_EXP48_CONFIG,
    SOURCE_EXP48_CONFIRMATION,
    STRICT_ENDPOINT_SCHEMA,
    TARGET_LEAN_VERSION,
    TARGET_TOOLCHAIN,
    atomic_json_dump,
    candidate_view_contract,
    code_lock,
    exclusive_create_json,
    expected_alternatives,
    file_sha256,
    json_sha256,
    read_json,
    safe_slug,
    validate_code_lock,
    validate_source_exp48,
)


def _locked_sources() -> list[Path]:
    here = Path(__file__).resolve().parent
    names = (
        "experiment49_protocol.py",
        "experiment49_strict_worker.py",
        "experiment49_analysis.py",
        "freeze_experiment49.py",
        "preflight_experiment49.py",
        "run_experiment49.py",
        "export_experiment49_bundle.py",
        "run_experiment49_full_pipeline.py",
    )
    return [here / name for name in names]


def _require_no_execution(root: Path) -> None:
    for rel in (
        "preflight/strict_worker_compile.json",
        "smoke/execution_summary.json",
        "validation/execution_summary.json",
        "analysis/summary.json",
    ):
        if (root / rel).exists():
            raise ValueError(f"Exp49 must freeze first: found {rel}")


def build_config(created_utc: str, source_cfg_path: Path,
                 source_summary_path: Path) -> dict[str, Any]:
    source_cfg = read_json(source_cfg_path)
    source_summary = read_json(source_summary_path)
    validate_source_exp48(source_cfg, source_summary)
    confirmation = list(source_cfg["repository_split"]["confirmation"])
    if confirmation != list(source_summary["repository_split"]["confirmation"]):
        raise ValueError("Exp48 confirmation repository order changed")
    if len(confirmation) != CONFIRMATION_REPOSITORIES:
        raise ValueError("Exp49 requires four confirmation repositories")

    repo_by = {r["slug"]: dict(r) for r in source_cfg["repositories"]}
    smoke_repos = list(source_cfg["smoke_repositories"])
    relevant = []
    for slug in list(dict.fromkeys([*smoke_repos, *confirmation])):
        repo = repo_by[slug]
        selected_path = Path(repo["selected_file"])
        if not selected_path.is_file() or file_sha256(selected_path) != repo["selected_file_sha256"]:
            raise ValueError(f"Exp48 selected theorem identity changed: {slug}")
        selected = read_json(selected_path)
        if slug in confirmation and len(selected.get("formal", [])) != ROOTS_PER_REPOSITORY:
            raise ValueError(f"Exp49 requires 24 formal roots in {slug}")
        for kind in ("formal", "smoke"):
            for theorem in selected.get(kind, []):
                alternatives = list(theorem.get("alternatives", []))
                expected = expected_alternatives(
                    str(theorem["authored_tactic"]), source_cfg["alternative_library"],
                    ALTERNATIVE_BUDGET,
                )
                if alternatives != expected or len(alternatives) != ALTERNATIVE_BUDGET:
                    raise ValueError(f"frozen Exp48 alternatives changed: {slug} {theorem['full_name']}")
        relevant.append(repo)

    confirmation_dir = source_summary_path.parent
    source_rows = sorted((confirmation_dir / "theorems").glob("*/*.json"))
    if len(source_rows) != CONFIRMATION_REPOSITORIES * ROOTS_PER_REPOSITORY:
        raise ValueError("Exp49 requires all 96 archived Exp48 theorem rows")
    for slug in confirmation:
        rows = list((confirmation_dir / "theorems" / safe_slug(slug)).glob("*.json"))
        if len(rows) != ROOTS_PER_REPOSITORY:
            raise ValueError(f"Exp48 archived row count changed: {slug}")

    library = list(source_cfg["alternative_library"])
    candidate_contract = candidate_view_contract(library)
    smoke_count = 0
    for slug in smoke_repos:
        smoke_count += len(read_json(repo_by[slug]["selected_file"])["smoke"])

    config: dict[str, Any] = {
        "version": 1,
        "protocol_version": PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "created_utc": created_utc,
        "study_role": "post-hoc candidate robustness and endpoint construct validation over Exp48; not independent confirmation",
        "source_exp48_config": str(source_cfg_path),
        "source_exp48_config_sha256": file_sha256(source_cfg_path),
        "source_exp48_confirmation": str(source_summary_path),
        "source_exp48_confirmation_sha256": file_sha256(source_summary_path),
        "source_exp48_confirmation_dir": str(confirmation_dir),
        "source_exp48_confirmation_go": True,
        "source_exp48_confirmation_metrics": {
            key: source_summary[key] for key in (
                "primary_repo_macro_mean", "primary_repo_bootstrap_95ci",
                "distinct_cross_head_pairs", "head_pairs_replicating_in_at_least_two_repositories",
            )
        },
        "target_lean_version": TARGET_LEAN_VERSION,
        "target_toolchain": TARGET_TOOLCHAIN,
        "repositories": relevant,
        "smoke_repositories": smoke_repos,
        "confirmation_repositories": confirmation,
        "expected_smoke_roots": smoke_count,
        "expected_validation_roots": CONFIRMATION_REPOSITORIES * ROOTS_PER_REPOSITORY,
        "roots_per_confirmation_repository": ROOTS_PER_REPOSITORY,
        "alternative_budget": ALTERNATIVE_BUDGET,
        "alternative_library": library,
        "candidate_library_sha256": source_cfg["candidate_library_sha256"],
        "candidate_views": list(CANDIDATE_VIEWS),
        "candidate_view_contract": candidate_contract,
        "endpoint_kinds": list(ENDPOINT_KINDS),
        "strict_endpoint": {
            "schema": STRICT_ENDPOINT_SCHEMA,
            "ordered_goals": True,
            "ordered_complete_local_declarations": True,
            "expression_ast": True,
            "alpha_normalization": "local fvars by context order; reachable unassigned expression/level metavariables and level parameters by deterministic first occurrence",
            "metadata_nodes": "stripped",
            "preserved": [
                "constants and universe structure", "binder information", "local declaration kind",
                "let-declaration value and nondependency flag", "local-instance membership",
                "goal metavariable kind/scope and local-instance registry",
                "reachable unassigned metavariable declaration type/kind/context/scope-count",
            ],
            "excluded": ["proof terms", "runtime", "messages", "internal tactic trace"],
        },
        "execution_backend": {
            "state_source": "unchanged exact source live TacticInfo",
            "pre_state": "ContextInfo + TacticInfo.mctxBefore + TacticInfo.goalsBefore",
            "branching": "authored syntax and 23 alternatives execute independently",
            "authored_gate": "both Exp48 text and strict structural endpoints reproduce original TacticInfo endpoint",
            "single_goal_pre_state_required": True,
        },
        "rarefaction": {"budgets": list(RAREFACTION_BUDGETS),
                        "replicates": RAREFACTION_REPLICATES, "seed": RAREFACTION_SEED},
        "bootstrap": {"replicates": BOOTSTRAP_REPLICATES, "seed": BOOTSTRAP_SEED,
                      "unit": "repository; descriptive post-hoc interval"},
        "primary_robustness_view": "L-mechanism-diverse",
        "analysis_plan": [
            "seven frozen candidate views evaluated offline from the same complete execution matrix",
            "raw/text48/strict endpoint agreement and exact text48-versus-strict confusion tables",
            "candidate-normalized cross-head pair density with failed attempts retained in denominator",
            "head concentration, leave-one-head-out, and deterministic rarefaction",
            "mechanical L0-text48 bridge to every archived Exp48 theorem row",
        ],
        "claim_boundary": [
            "state-conditioned one-step endpoint agreement only",
            "same 96 roots are reused, so Exp49 is not independent confirmation",
            "no tactic interchangeability or proof-strategy equivalence",
            "no proof-term equality, runtime equivalence, or theorem-proving improvement",
        ],
        "code_lock": code_lock(_locked_sources()),
        "next_step": "Run compile-only strict-worker preflight; execute zero theorem roots during preflight.",
    }
    config["frozen_config_sha256_self_excluded"] = json_sha256(
        {k: v for k, v in config.items() if k not in {"created_utc", "frozen_config_sha256_self_excluded"}}
    )
    return config


def freeze(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    frozen = root / "frozen"
    claimp = frozen / "experiment49_freeze_claim.json"
    cfgp = frozen / "experiment49_config.json"
    receiptp = frozen / "experiment49_freeze_receipt.json"
    txp = frozen / "experiment49_freeze_transaction.json"
    if txp.is_file() and read_json(txp).get("completed") is True:
        cfg = read_json(cfgp)
        validate_code_lock(cfg["code_lock"])
        print(json.dumps({"config": str(cfgp), "already_frozen": True}, indent=2))
        return cfg
    _require_no_execution(root)

    source_cfg = Path(args.source_exp48_config).resolve()
    source_summary = Path(args.source_exp48_confirmation).resolve()
    if claimp.exists():
        if not args.resume_freeze:
            raise FileExistsError("Exp49 freeze claim exists; use --resume-freeze")
        claim = read_json(claimp)
        cfg = build_config(claim["created_utc"], source_cfg, source_summary)
        if cfg["frozen_config_sha256_self_excluded"] != claim["config_identity"]:
            raise ValueError("Exp49 freeze reconstruction differs from claim")
    else:
        if args.resume_freeze:
            raise FileNotFoundError("--resume-freeze without claim")
        created = datetime.now(timezone.utc).isoformat()
        cfg = build_config(created, source_cfg, source_summary)
        exclusive_create_json(claimp, {
            "version": 1, "protocol_version": PROTOCOL_VERSION,
            "created_utc": created, "config_identity": cfg["frozen_config_sha256_self_excluded"],
        })
    atomic_json_dump({"version": 1, "completed": False, "phase": "claim_committed"}, txp)
    if cfgp.exists() and read_json(cfgp) != cfg:
        raise ValueError("existing Exp49 config differs")
    if not cfgp.exists():
        atomic_json_dump(cfg, cfgp)
    receipt = {
        "version": 1, "protocol_version": PROTOCOL_VERSION,
        "config": str(cfgp), "config_sha256": file_sha256(cfgp),
        "execution_before_freeze": False,
        "source_exp48_confirmation_sha256": cfg["source_exp48_confirmation_sha256"],
        "validation_roots": cfg["expected_validation_roots"],
        "candidate_views": len(cfg["candidate_views"]),
        "endpoint_kinds": cfg["endpoint_kinds"],
    }
    atomic_json_dump(receipt, receiptp)
    atomic_json_dump({
        "version": 1, "completed": True, "phase": "completed",
        "config_sha256": file_sha256(cfgp), "receipt_sha256": file_sha256(receiptp),
    }, txp)
    print(json.dumps({
        "config": str(cfgp), "source_exp48_confirmation_go": True,
        "validation_roots": cfg["expected_validation_roots"],
        "candidate_views": cfg["candidate_views"], "next_step": cfg["next_step"],
    }, ensure_ascii=False, indent=2))
    return cfg


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", default=str(ARTIFACT_ROOT))
    p.add_argument("--source-exp48-config", default=str(SOURCE_EXP48_CONFIG))
    p.add_argument("--source-exp48-confirmation", default=str(SOURCE_EXP48_CONFIRMATION))
    p.add_argument("--resume-freeze", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    freeze(parse_args())
