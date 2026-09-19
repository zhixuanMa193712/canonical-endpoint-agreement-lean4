"""Freeze Exp51 repository-frame extension 1 before any new screening."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from experiment51_extension_protocol import *


def build_config(created_utc: str) -> dict:
    nogo = validate_nogo_bundle()
    carried = validate_base_carry_forward()
    frame = validate_candidate_frame()
    value = {
        "version": 1,
        "extension_version": EXTENSION_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "created_utc": created_utc,
        "target_toolchain": TARGET_TOOLCHAIN,
        "target_lean_version": TARGET_LEAN_VERSION,
        "target_repositories": TARGET_REPOSITORIES,
        "minimum_repositories": MIN_REPOSITORIES,
        "roots_per_repository": ROOTS_PER_REPOSITORY,
        "scientific_candidate_tactics_permitted": 0,
        "permitted_operations": [
            "content-addressed carry-forward of seven zero-candidate qualification passes",
            "clone and detach exact extension commits",
            "unmodified exact-toolchain build",
            "pinned LeanDojo v4.27 trace",
            "single-process parser-compatible root enumeration with remote dependency metadata disabled",
            "authored replay with an empty scientific candidate list",
            "source-lineage measurement",
        ],
        "base_recruitment_nogo": nogo,
        "carry_forward": carried,
        "carry_forward_count": len(carried),
        "candidate_frame": str(CANDIDATE_FRAME),
        "candidate_frame_sha256": file_sha256(CANDIDATE_FRAME),
        "extension_candidate_count": len(frame["candidates"]),
        "source_registry": frame["source_registry"],
        "selection_rule": frame["selection_rule"],
        "ordering_rule": frame["ordering_rule"],
        "source_overlap_threshold": SOURCE_OVERLAP_THRESHOLD,
        "qualification_schedule": {
            "repository_workers": REPOSITORY_WORKERS,
            "build_slots": BUILD_SLOTS,
            "trace_slots": TRACE_SLOTS,
            "enumeration_slots": ENUMERATION_SLOTS,
            "threads_per_trace": THREADS_PER_TRACE,
            "git_timeout_seconds": GIT_TIMEOUT,
            "build_timeout_seconds": BUILD_TIMEOUT,
            "trace_timeout_seconds": TRACE_TIMEOUT,
            "enumeration_timeout_seconds": ENUMERATION_TIMEOUT,
            "replay_timeout_seconds": REPLAY_TIMEOUT,
        },
        "offline_dependency_adapter": {
            "schema": "leandojo-4.20.0-buildDeps-false-no-remote-metadata-v1",
            "scope": "TracedRepo.from_traced_files(..., build_deps=False)",
            "effect": "return an empty dependency metadata map and reject every GitHub API request",
            "repository_checkout_modified": False,
            "installed_lean_dojo_files_modified": False,
            "control_repositories": list(OFFLINE_CONTROL_SLUGS),
            "exact_frame_control_required": True,
        },
        "claim_boundary": [
            "this extension is repository qualification only",
            "no scientific tactic alternative is executed before the later Exp51 scientific freeze",
            "repository recruitment outcomes are not scientific tactic outcomes",
            "Experiment 48 remains the existing Tier-1 scientific confirmation",
            "no tactic interchangeability, proof-strategy equivalence, proof-term equality, runtime equivalence, or prover-improvement claim",
        ],
        "code_lock": code_lock(locked_sources()),
        "next_step": "Run extension environment preflight; execute zero theorem roots and zero candidates.",
    }
    value["identity_sha256"] = json_sha256({
        key: item for key, item in value.items()
        if key not in {"created_utc", "identity_sha256"}
    })
    return value


def freeze(args: argparse.Namespace) -> dict:
    root = Path(args.root).resolve()
    frozen = root / "frozen"
    configp = frozen / "extension_config.json"
    transactionp = frozen / "freeze_transaction.json"
    if transactionp.is_file() and read_json(transactionp).get("completed") is True:
        config = read_json(configp)
        validate_code_lock(config["code_lock"])
        if file_sha256(CANDIDATE_FRAME) != config["candidate_frame_sha256"]:
            raise ValueError("extension candidate frame changed after freeze")
        print(json.dumps({"already_frozen": True, "config": str(configp)}, indent=2))
        return config
    for relative in ("screening", "preflight", "scientific", "analysis", "audit"):
        if (root / relative).exists():
            raise ValueError(f"extension must be frozen before {relative}")
    created = datetime.now(timezone.utc).isoformat()
    config = build_config(created)
    exclusive_create_json(frozen / "freeze_claim.json", {
        "version": 1,
        "created_utc": created,
        "identity_sha256": config["identity_sha256"],
    })
    atomic_json_dump(config, configp)
    receipt = {
        "version": 1,
        "extension_version": EXTENSION_VERSION,
        "config": str(configp),
        "config_sha256": file_sha256(configp),
        "candidate_frame_sha256": config["candidate_frame_sha256"],
        "carry_forward_count": config["carry_forward_count"],
        "extension_candidate_count": config["extension_candidate_count"],
        "scientific_candidate_tactics_executed": 0,
        "next_step": config["next_step"],
    }
    atomic_json_dump(receipt, frozen / "freeze_receipt.json")
    atomic_json_dump({
        "version": 1,
        "completed": True,
        "config_sha256": file_sha256(configp),
    }, transactionp)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    freeze(parse_args())
