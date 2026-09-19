"""Freeze selected repositories, sampled roots, Exp51 gates, and Exp52 rules."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiment51_protocol import *
from freeze_experiment51_recruitment import locked_sources

PROBES52 = ["rfl", "assumption", "simp", "simp_all", "aesop", "norm_num",
            "omega", "ring_nf", "constructor", "intro", "solve_by_elim",
            "first | rfl | assumption"]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def exp52_protocol(created: str, config_identity: str) -> dict[str, Any]:
    value: dict[str, Any] = {
        "version": 1, "protocol_version": "experiment52-bounded-continuation-probe-v1",
        "created_utc": created, "frozen_before_exp51_scientific_execution": True,
        "source_experiment": PROTOCOL_VERSION, "source_config_identity_sha256": config_identity,
        "source_population": [
            "Exp51 evaluable root", "at least two executable L-mechanism-diverse candidates",
            "distinct heads", "same non-initial strict endpoint", "nonterminal endpoint",
        ],
        "witness_rule": {
            "one_pair_per_root": True,
            "internal_pair_order": ["head", "tactic_text", "candidate_index"],
            "pair_order": ["endpoint_hash", "first_pair_key", "second_pair_key"],
            "maximum_roots_per_repository": None,
            "target_witness_roots": 200, "target_repositories": 12,
        },
        "control_rule": {
            "preference": ["within_root", "repository_local"],
            "eligibility": ["executable L-mechanism-diverse", "distinct heads",
                            "different non-initial strict endpoints", "both nonterminal"],
            "distance_order": ["absolute_goal_count_difference", "local_context_bin_mismatch",
                               "target_expression_bin_mismatch", "executable_count_bin_mismatch",
                               "pair_tactic_head_key"],
            "local_context_bins": [0, 4, 8, 16, 32, "infinity"],
            "target_expression_byte_bins": [0, 256, 512, 1024, 2048, "infinity"],
            "executable_candidate_bins": [0, 4, 8, 12, 16, 24],
        },
        "probe_library": PROBES52,
        "probe_library_sha256": json_sha256(PROBES52),
        "probe_contract": [
            "remove exact tactic text of every witness/control pair member",
            "use the identical remaining subset on both pair sides and matched control",
            "no theorem-specific generated term", "fresh independent branch per side and probe",
            "no sequential chaining", "at least one-side success defines informative denominator",
        ],
        "response_categories": [
            "both_success_same_strict_endpoint", "both_success_different_strict_endpoint",
            "left_success_only", "right_success_only", "both_fail_same_category",
            "both_fail_different_category", "invalid_reconstruction",
        ],
        "bootstrap": {"levels": ["repository", "root"], "replicates": 20000,
                      "seed": 520052, "interval": "percentile_95"},
        "gates": {
            "overall_reconstruction": 0.95, "per_repository_reconstruction": 0.90,
            "all_frozen_probes_attempted_both_sides": True, "manual_replacement_count": 0,
            "minimum_valid_witness_roots": 200, "minimum_repositories": 12,
            "asymmetric_success_one_sided_95_upper_lt": 0.05,
            "delta_concordance_95_lower_gt": 0.0,
            "repositories_nonnegative_delta_fraction": 0.75,
        },
        "claim_boundary": [
            "bounded immediate continuation probes only", "not arbitrary future trajectories",
            "not authored proof replacement", "not global tactic interchangeability",
        ],
    }
    value["identity_sha256"] = json_sha256({k: v for k, v in value.items()
                                             if k not in {"created_utc", "identity_sha256"}})
    return value


def build_targets(root: Path, selected: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    targets, repos = [], []
    for slug in selected:
        replayp = root / "screening/replay" / f"{safe_slug(slug)}.json"
        replay = read_json(replayp)
        if replay.get("authored_replay_gate") is not True:
            raise ValueError(f"selected repository failed replay: {slug}")
        eligiblep = Path(replay["eligible_frame"])
        if file_sha256(eligiblep) != replay["eligible_frame_sha256"]:
            raise ValueError(f"eligible frame changed: {slug}")
        frame = read_jsonl(eligiblep)
        if len(frame) < ROOTS_PER_REPOSITORY:
            raise ValueError(f"insufficient eligible roots: {slug}")
        sample = deterministic_sample(frame, slug)
        build = read_json(root / "screening/build_trace" / f"{safe_slug(slug)}.json")
        project = Path(build["project"])
        commit_now = __import__("subprocess").run(
            ["git", "rev-parse", "HEAD"], cwd=project, text=True,
            stdout=__import__("subprocess").PIPE, check=True).stdout.strip()
        if commit_now != build["commit"]:
            raise ValueError(f"checkout commit changed: {slug}")
        repo = {
            "slug": slug, "url": build["candidate"]["url"], "ref": build["candidate"]["ref"],
            "commit": build["commit"], "checkout": build["project"],
            "domain": build["candidate"]["domain"], "license_files": build["license_files"],
            "eligible_roots": replay["eligible_roots"], "selected_roots": len(sample),
            "eligible_frame": str(eligiblep), "eligible_frame_sha256": file_sha256(eligiblep),
        }
        repo["repository_identity_sha256"] = json_sha256(repo)
        repos.append(repo)
        for row in sample:
            source = project / row["file_path"]
            ast = Path(row["ast_path"])
            screening_row = Path(row["screening_worker_row"])
            if (not source.is_file() or file_sha256(source) != row["source_file_sha256"]
                    or not ast.is_file() or file_sha256(ast) != row["ast_sha256"]
                    or not screening_row.is_file()
                    or file_sha256(screening_row) != row["screening_worker_row_sha256"]):
                raise ValueError(f"sampled root evidence changed: {slug} {row['full_name']}")
            alternatives = expected_alternatives(row["authored_tactic"])
            if len(alternatives) != CANDIDATES_PER_ROOT:
                raise ValueError("candidate budget changed")
            target = dict(row)
            target.update({"alternatives": alternatives,
                           "alternatives_sha256": json_sha256(alternatives),
                           "robust_alternatives": select_candidate_view(alternatives, "L-mechanism-diverse")})
            target["target_identity_sha256"] = json_sha256({
                k: target[k] for k in ("slug", "commit", "file_path", "full_name", "theorem_id",
                                       "source_file_sha256", "target_pos", "target_end_pos",
                                       "authored_tactic", "alternatives_sha256")})
            targets.append(target)
    if len(targets) != len(selected) * ROOTS_PER_REPOSITORY:
        raise ValueError("wrong target count")
    return targets, repos


def freeze(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    screeningp = root / "screening/summary.json"
    screening = read_json(screeningp)
    runtimep = root / "preflight/trace_runtime.json"
    runtime = read_json(runtimep)
    adapterp = root / "preflight/parser_adapter.json"
    adapter = read_json(adapterp)
    recruitmentp = root / "recruitment_frozen/recruitment_config.json"
    recruitment = read_json(recruitmentp)
    validate_code_lock(recruitment["code_lock"])
    if screening.get("screening_gate") is not True or screening.get("selected_count", 0) < MIN_REPOSITORIES:
        raise ValueError("insufficient_repository_frame; scientific freeze prohibited")
    if screening.get("scientific_candidate_tactics_executed") != 0:
        raise ValueError("screening candidate protection failed")
    if (runtime.get("runtime_ok") is not True
            or runtime.get("qualification_resources", {}).get("parallel_capacity_ok") is not True
            or runtime.get("qualification_resources", {}).get("capacity_profile")
            != RECOVERY_CAPACITY_PROFILE
            or runtime.get("config_sha256") != file_sha256(recruitmentp)
            or runtime.get("candidate_tactics_executed") != 0):
        raise ValueError("pinned trace-runtime preflight is not exact")
    if not (
        adapter.get("adapter_ok") is True
        and adapter.get("config_sha256") == file_sha256(recruitmentp)
        and adapter.get("parser_compatibility_schema") == V427_PARSER_COMPATIBILITY_SCHEMA
        and adapter.get("repositories") == list(PARSER_ADAPTER_PREFLIGHT_REPOSITORIES)
        and adapter.get("fix8_success_frames_exact") is True
        and len(adapter.get("compatibility_smokes", []))
        == len(PARSER_ADAPTER_PREFLIGHT_REPOSITORIES)
        and all(row.get("smoke_gate") is True for row in adapter.get("compatibility_smokes", []))
        and adapter.get("trace_executed") is False
        and adapter.get("candidate_tactics_executed") == 0
    ):
        raise ValueError("pinned Lean 4.27 parser-adapter preflight is not exact")
    for rel in ("scientific/summary.json", "analysis/summary.json"):
        if (root / rel).exists():
            raise ValueError(f"freeze must precede {rel}")
    cfgp = root / "frozen/experiment51_config.json"
    targetsp = root / "frozen/targets.json"
    txp = root / "frozen/freeze_transaction.json"
    if txp.is_file() and read_json(txp).get("completed") is True:
        cfg = read_json(cfgp)
        validate_code_lock(cfg["code_lock"])
        print(json.dumps({"already_frozen": True, "config": str(cfgp)}, indent=2))
        return cfg
    created = datetime.now(timezone.utc).isoformat()
    selected = list(screening["selected_repositories"][:TARGET_REPOSITORIES])
    targets, repositories = build_targets(root, selected)
    code = code_lock(locked_sources())
    config: dict[str, Any] = {
        "version": 1, "protocol_version": PROTOCOL_VERSION, "created_utc": created,
        "study_role": "Tier-1 external repository replication if execution and preregistered gates pass",
        "target_lean_version": TARGET_LEAN_VERSION, "target_toolchain": TARGET_TOOLCHAIN,
        "repositories": repositories, "repository_count": len(repositories),
        "ordered_pre_candidate_backups": screening.get("ordered_backups", []),
        "minimum_repositories": MIN_REPOSITORIES, "roots_per_repository": ROOTS_PER_REPOSITORY,
        "roots": len(targets), "candidate_budget": CANDIDATES_PER_ROOT,
        "alternative_library": ALTERNATIVE_LIBRARY,
        "candidate_library_sha256": json_sha256(ALTERNATIVE_LIBRARY),
        "primary_panel": "L0", "robust_panel": "L-mechanism-diverse",
        "candidate_genealogy": CANDIDATE_GENEALOGY,
        "candidate_genealogy_sha256": json_sha256(CANDIDATE_GENEALOGY),
        "primary_endpoint": {"name": "kappa_struct_v1", "schema": STRICT_ENDPOINT_SCHEMA},
        "root_sample": {"method": "simple_random_without_replacement",
                        "master_seed": MASTER_SAMPLE_SEED, "roots_per_repository": ROOTS_PER_REPOSITORY},
        "smoke_target_ids": [targets[i]["theorem_id"] for i in (0, 1, ROOTS_PER_REPOSITORY,
                                                                  ROOTS_PER_REPOSITORY + 1)],
        "estimand": "equal-weight mean of repository Y-L0 rates in the frozen eligible frame",
        "bootstrap": {"levels": ["repository", "root"], "replicates": BOOTSTRAP_REPLICATES,
                      "seed": BOOTSTRAP_SEED, "interval": "percentile_95"},
        "gates": {
            "minimum_completed_repositories": MIN_REPOSITORIES,
            "overall_evaluability": MIN_OVERALL_EVALUABILITY,
            "per_repository_evaluability": MIN_REPOSITORY_EVALUABILITY,
            "all_candidates_attempted_per_evaluable_root": CANDIDATES_PER_ROOT,
            "primary_ci_halfwidth_at_most": MAX_CI_HALFWIDTH,
            "primary_ci_lower_gt": PRIMARY_DELTA,
            "primary_nonzero_repository_fraction": 0.75,
            "robust_ci_lower_gt": ROBUST_DELTA,
            "robust_nonzero_repository_fraction": 0.75,
            "robust_nonterminal_repository_fraction": 0.50,
            "manual_reconciliation_count": 0,
        },
        "source": {"recruitment_config": str(recruitmentp),
                   "recruitment_config_sha256": file_sha256(recruitmentp),
                   "trace_runtime_preflight": str(runtimep),
                   "trace_runtime_preflight_sha256": file_sha256(runtimep),
                   "parser_adapter_preflight": str(adapterp),
                   "parser_adapter_preflight_sha256": file_sha256(adapterp),
                   "screening_summary": str(screeningp),
                   "screening_summary_sha256": file_sha256(screeningp),
                   **recruitment["source_controls"]},
        "exp52_freeze_required_before_execution": True,
        "claim_boundary": [
            "state-conditioned one-step endpoint agreement under frozen candidate panels",
            "not tactic equivalence or global tactic interchangeability",
            "not proof-strategy or proof-term equivalence", "not improved theorem proving",
            "repository-macro estimand over this frozen eligible frame only",
        ],
        "code_lock": code,
        "next_step": "Compile-only scientific preflight, environment receipt, then smoke.",
    }
    config["identity_sha256"] = json_sha256({k: v for k, v in config.items()
                                              if k not in {"created_utc", "identity_sha256"}})
    protocol52 = exp52_protocol(created, config["identity_sha256"])
    exclusive_create_json(root / "frozen/freeze_claim.json", {
        "version": 1, "created_utc": created, "identity_sha256": config["identity_sha256"]})
    atomic_json_dump(config, cfgp)
    atomic_json_dump(targets, targetsp)
    atomic_json_dump(protocol52, root / "frozen/experiment52_protocol.json")
    receipt = {
        "version": 1, "config_sha256": file_sha256(cfgp),
        "targets_sha256": file_sha256(targetsp), "repositories": len(repositories),
        "roots": len(targets), "exp52_protocol_sha256": file_sha256(root / "frozen/experiment52_protocol.json"),
        "scientific_candidate_execution_before_freeze": False,
    }
    atomic_json_dump(receipt, root / "frozen/freeze_receipt.json")
    atomic_json_dump({"version": 1, "completed": True, **receipt}, txp)
    print(json.dumps({**receipt, "next_step": config["next_step"]}, ensure_ascii=False, indent=2))
    return config


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    return p.parse_args()


if __name__ == "__main__":
    freeze(parse_args())
