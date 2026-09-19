"""Pure protocol constants for the Exp51-to-Exp52 scientific freeze bridge.

This module performs no Lean execution and reads no scientific outcome rows.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Sequence

PACKAGE_ROOT = Path(__file__).resolve().parent
SERVER_ROOT = Path(os.environ.get("MZX_ROOT", PACKAGE_ROOT.parent)).resolve()
DOCUMENT_ROOT = SERVER_ROOT / "experiment52_continuation_probe"

ALIGNMENT_VERSION = "experiment51-exp52-scientific-freeze-alignment-fix2"
ALIGNMENT_FIX_ID = (
    "exp51-exp52-preregistration-v0.1-extension2-"
    "scientific-freeze-bridge-fix2-monadic-tactic-quotation"
)
EXP52_PROTOCOL_VERSION = "experiment52-bounded-continuation-probe-v1"
EXP52_DESIGN_LOCK_VERSION = "exp52-preregistration-v0.1"
STRICT_ENDPOINT_SCHEMA = "exp49-strict-goal-structure-v1"

SCIENTIFIC_ARTIFACT_RELATIVE = (
    "artifacts/v51/external_repository_replication_scientific"
)
QUALIFICATION_ARTIFACT_RELATIVE = (
    "artifacts/v51/external_repository_replication_extension2"
)

PREREGISTRATION_DOCUMENTS = {
    "EXP52_PREREGISTRATION.md": (
        "06495a35ff54c5cb1a5ef235f109ac8743c9ea21ba6698125c4f84f8219dd452"
    ),
    "EXP52_FALSIFICATION_MATRIX.md": (
        "9cc1da7fe3955085a6e9ee174d2eda173da7bf7464095ec66c6c19ccc55a493a"
    ),
}

PROBE_POOL = [
    "rfl",
    "assumption",
    "simp",
    "simp_all",
    "aesop",
    "norm_num",
    "omega",
    "ring_nf",
    "constructor",
    "intro",
    "solve_by_elim",
    "first | rfl | assumption",
]


def file_sha256(path: str | Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def json_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def document_lock() -> dict[str, Any]:
    rows = []
    for name, expected in PREREGISTRATION_DOCUMENTS.items():
        path = DOCUMENT_ROOT / name
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = file_sha256(path)
        if observed != expected:
            raise ValueError(f"Exp52 preregistration document changed: {path}")
        rows.append({
            "path": str(path),
            "name": name,
            "sha256": observed,
            "bytes": path.stat().st_size,
        })
    return {"files": rows, "bundle_sha256": json_sha256(rows)}


def retained_probe_panel(available: Sequence[str]) -> list[str]:
    available_list = list(available)
    available_set = set(available_list)
    if len(available_set) != len(available_list):
        raise ValueError("probe-surface receipt contains duplicate probes")
    if not available_set.issubset(PROBE_POOL):
        raise ValueError("probe-surface receipt contains an unfrozen probe")
    return [probe for probe in PROBE_POOL if probe in available_set]


def build_exp52_protocol(
    *,
    created_utc: str,
    source_config_identity_sha256: str,
    selected_repositories: Sequence[str],
    probe_surface_receipt: str,
    probe_surface_receipt_sha256: str,
    available_probes: Sequence[str],
) -> dict[str, Any]:
    probes = retained_probe_panel(available_probes)
    if len(probes) < 8:
        raise ValueError("probe_surface_no_go: fewer than eight global probes remain")
    documents = document_lock()
    value: dict[str, Any] = {
        "version": 1,
        "protocol_version": EXP52_PROTOCOL_VERSION,
        "design_lock_version": EXP52_DESIGN_LOCK_VERSION,
        "alignment_version": ALIGNMENT_VERSION,
        "mechanical_fix_id": ALIGNMENT_FIX_ID,
        "created_utc": created_utc,
        "frozen_before_exp51_scientific_execution": True,
        "scientific_candidate_execution_before_freeze": False,
        "source_experiment": "experiment51-preregistered-external-repository-replication-v1",
        "source_config_identity_sha256": source_config_identity_sha256,
        "source_repositories": list(selected_repositories),
        "strict_endpoint": {
            "name": "kappa_struct_v1",
            "schema": STRICT_ENDPOINT_SCHEMA,
            "non_initial_required": True,
            "nonterminal_required": True,
        },
        "source_population": [
            "frozen evaluable Exp51 scientific root",
            "at least two executable L-mechanism-diverse candidates",
            "distinct heads and distinct frozen genealogy groups",
            "same non-initial strict endpoint",
            "nonterminal endpoint",
            "exact source/pre-state/post-state reconstruction",
        ],
        "witness_rule": {
            "one_pair_per_root": True,
            "internal_pair_order": [
                "head_utf8_bytes", "exact_tactic_text_utf8_bytes", "candidate_index"
            ],
            "pair_order": [
                "strict_endpoint_sha256", "left_pair_key", "right_pair_key"
            ],
            "maximum_roots_per_repository": None,
            "manual_replacement_permitted": False,
        },
        "primary_control_rule": {
            "scope": "within_root_only",
            "repository_local_fallback": False,
            "eligibility": [
                "two executable L-mechanism-diverse candidates",
                "distinct heads and distinct frozen genealogy groups",
                "two different non-initial strict endpoints",
                "both endpoints nonterminal",
                "pair differs from witness pair",
            ],
            "endpoint_feature_vector": [
                "residual_goal_count",
                "total_local_declarations_bin",
                "strict_target_ast_utf8_bytes_bin",
            ],
            "local_declaration_bin_edges": [0, 4, 8, 16, 32, "infinity"],
            "target_ast_utf8_byte_bin_edges": [
                0, 256, 512, 1024, 2048, "infinity"
            ],
            "distance_order": [
                "summed_absolute_residual_goal_count_difference",
                "summed_absolute_local_declaration_bin_difference",
                "summed_absolute_target_ast_byte_bin_difference",
                "sorted_control_endpoint_hashes",
                "internal_pair_key",
            ],
            "no_control_action": "retain absolute witness; exclude root from paired delta",
        },
        "probe_surface": {
            "frozen_pool": list(PROBE_POOL),
            "frozen_pool_sha256": json_sha256(PROBE_POOL),
            "qualification_mode": (
                "global-removal-only-after-zero-theorem-zero-candidate-compile-quotation-failure"
            ),
            "receipt": probe_surface_receipt,
            "receipt_sha256": probe_surface_receipt_sha256,
            "retained_panel": probes,
            "retained_panel_sha256": json_sha256(probes),
            "minimum_retained": 8,
            "maximum_retained": 12,
        },
        "probe_contract": [
            "remove exact tactic text of every witness/control pair member",
            "use one identical remaining subset on witness and matched control",
            "no theorem-specific generated term",
            "fresh Lean process per root/pair-role/side/probe",
            "no sequential probe chaining",
            "one tactic command per probe cell",
            "at least one-side success defines informative denominator",
            "both-fail cells are reported and never positive agreement",
        ],
        "execution": {
            "live_state_source": [
                "ContextInfo", "TacticInfo.mctxBefore", "TacticInfo.goalsBefore"
            ],
            "candidate_post_state_must_match_exp51": [
                "raw", "text48", "struct", "goal_count", "terminal"
            ],
            "fresh_process_per_probe_side": True,
            "lean_timeout_seconds": 900,
            "scientific_retry_permitted": False,
            "determinism_audit": {
                "selection": (
                    "first ceil(0.10*n_repo) valid witness root IDs by SHA-256 within repository"
                ),
                "repeat_all_witness_probe_cells": True,
                "fresh_process": True,
                "required_mismatches": 0,
                "audit_repeats_are_scientific_samples": False,
            },
        },
        "response_categories": [
            "both_success_same_strict_endpoint",
            "both_success_different_strict_endpoint",
            "left_success_only",
            "right_success_only",
            "both_fail_same_category",
            "both_fail_different_category",
            "invalid_reconstruction",
        ],
        "failure_categories": [
            "tactic_failure",
            "syntax_or_elaboration_failure",
            "timeout",
            "resource_failure",
            "worker_or_protocol_failure",
        ],
        "estimands": {
            "C": "both_success_same_strict_endpoint / at_least_one_success",
            "A": "exactly_one_success / at_least_one_success",
            "B": (
                "(exactly_one_success + both_success_different_strict_endpoint) "
                "/ at_least_one_success"
            ),
            "D": (
                "root has at least one exactly-one-success or "
                "both-success-different-strict-endpoint probe"
            ),
            "delta_C": "same_strict_endpoint_C - within_root_different_endpoint_control_C",
            "unit": "root-selected pair; probes are repeated measurements",
            "repository_weighting": "equal-weight repository macro",
        },
        "bootstrap": {
            "levels": ["repository", "root"],
            "replicates": 20000,
            "seed": 520052,
            "interval": "percentile_95",
            "paired_control_resampling": True,
        },
        "gates": {
            "overall_reconstruction_at_least": 0.95,
            "per_repository_reconstruction_at_least": 0.90,
            "all_retained_probes_attempted_both_sides": True,
            "manual_reconciliation_count": 0,
            "determinism_audit_mismatch_count": 0,
            "minimum_valid_witness_roots": 200,
            "minimum_witness_repositories": 12,
            "minimum_within_root_control_pairs": 100,
            "minimum_control_repositories": 8,
            "overall_nonzero_informative_denominator_fraction_at_least": 0.80,
            "per_repository_nonzero_informative_denominator_fraction_at_least": 0.50,
            "total_informative_discordance_B_one_sided_95_upper_lt": 0.05,
            "delta_C_95_lower_gt": 0.0,
            "control_repositories_nonnegative_delta_fraction_at_least": 0.75,
        },
        "decision_order": [
            "invalid_execution",
            "continuation_inconclusive",
            "continuation_support",
            "continuation_no_go",
        ],
        "claim_boundary": [
            "state-conditioned immediate continuation response under a frozen probe panel only",
            "not arbitrary future trajectories",
            "not authored proof replacement",
            "not tactic equivalence or global tactic interchangeability",
            "not semantic equivalence or proof-strategy equivalence",
            "not proof-term equality, runtime equivalence, or prover improvement",
        ],
        "preregistration_documents": documents,
    }
    value["identity_sha256"] = json_sha256({
        key: item
        for key, item in value.items()
        if key not in {"created_utc", "identity_sha256"}
    })
    return value


def validate_protocol(value: dict[str, Any]) -> None:
    if not (
        value.get("protocol_version") == EXP52_PROTOCOL_VERSION
        and value.get("design_lock_version") == EXP52_DESIGN_LOCK_VERSION
        and value.get("alignment_version") == ALIGNMENT_VERSION
        and value.get("mechanical_fix_id") == ALIGNMENT_FIX_ID
        and value.get("frozen_before_exp51_scientific_execution") is True
        and value.get("scientific_candidate_execution_before_freeze") is False
        and value.get("strict_endpoint", {}).get("schema") == STRICT_ENDPOINT_SCHEMA
        and value.get("primary_control_rule", {}).get("scope") == "within_root_only"
        and value.get("primary_control_rule", {}).get("repository_local_fallback") is False
        and len(value.get("probe_surface", {}).get("retained_panel", [])) >= 8
        and value.get("gates", {}).get(
            "total_informative_discordance_B_one_sided_95_upper_lt"
        ) == 0.05
        and value.get("execution", {}).get("determinism_audit", {}).get(
            "required_mismatches"
        ) == 0
        and value.get("preregistration_documents") == document_lock()
    ):
        raise ValueError("Exp52 machine protocol differs from preregistration v0.1")
    identity = json_sha256({
        key: item
        for key, item in value.items()
        if key not in {"created_utc", "identity_sha256"}
    })
    if value.get("identity_sha256") != identity:
        raise ValueError("Exp52 protocol identity changed")
