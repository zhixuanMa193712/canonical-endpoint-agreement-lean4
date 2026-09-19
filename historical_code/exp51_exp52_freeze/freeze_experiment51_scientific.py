"""Freeze Exp51 scientific targets from exact Extension2 qualification evidence.

This bridge writes a new scientific artifact root.  It never modifies the
protected Extension2 qualification artifact or executes Lean.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiment52_protocol import (
    ALIGNMENT_FIX_ID,
    ALIGNMENT_VERSION,
    PACKAGE_ROOT,
    QUALIFICATION_ARTIFACT_RELATIVE,
    SCIENTIFIC_ARTIFACT_RELATIVE,
    SERVER_ROOT,
    build_exp52_protocol,
    document_lock,
    file_sha256,
    json_sha256,
    validate_protocol,
)

BASE_PACKAGE_ROOT = SERVER_ROOT / "experiment51_external_repository_replication"
if str(BASE_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(BASE_PACKAGE_ROOT))

import experiment51_protocol as base  # noqa: E402
import freeze_experiment51 as legacy_freeze  # noqa: E402
from freeze_experiment51_recruitment import locked_sources as base_locked_sources  # noqa: E402

EXTENSION2_VERSION = "experiment51-zero-candidate-frame-extension2-v1"
EXTENSION2_FIX_ID = (
    "exp51-extension2-public-github-discovery-frame-fix1-screen-wrapper-export"
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def validate_zero_candidate_replay(
    qualification_root: Path,
    slug: str,
    extension_config_sha256: str,
) -> dict[str, Any]:
    safe = base.safe_slug(slug)
    buildp = qualification_root / "screening/build_trace" / f"{safe}.json"
    replayp = qualification_root / "screening/replay" / f"{safe}.json"
    build, replay = base.read_json(buildp), base.read_json(replayp)
    eligiblep = Path(replay.get("eligible_frame", "")).resolve()
    if not (
        build.get("candidate", {}).get("slug") == slug
        and build.get("build_trace_gate") is True
        and build.get("scientific_candidate_tactics_executed") == 0
        and replay.get("slug") == slug
        and replay.get("authored_replay_gate") is True
        and replay.get("scientific_candidate_tactics_executed") == 0
        and replay.get("eligible_roots", 0) >= base.ROOTS_PER_REPOSITORY
        and eligiblep.is_file()
        and eligiblep.is_relative_to(qualification_root)
        and file_sha256(eligiblep) == replay.get("eligible_frame_sha256")
    ):
        raise ValueError(f"selected qualification row is invalid: {slug}")
    rows = read_jsonl(eligiblep)
    if len(rows) != replay["eligible_roots"]:
        raise ValueError(f"eligible-frame count changed: {slug}")
    row_hashes = []
    for row in rows:
        workerp = Path(row.get("screening_worker_row", "")).resolve()
        if not workerp.is_relative_to(qualification_root):
            raise ValueError(f"authored worker escaped qualification root: {slug}")
        if not workerp.is_file() or file_sha256(workerp) != row.get(
            "screening_worker_row_sha256"
        ):
            raise ValueError(f"authored worker receipt changed: {slug}")
        worker = base.read_json(workerp)
        if not (
            row.get("authored_replay_ok") is True
            and worker.get("protocol_version") == base.PROTOCOL_VERSION
            and worker.get("mode") == "screening_authored_only"
            and worker.get("config_sha256") == extension_config_sha256
            and worker.get("worker_ok") is True
            and worker.get("candidates") == []
            and worker.get("candidate_order") == []
            and worker.get("authored_replay_ok") is True
            and worker.get("same_pre_state_all_branches") is True
            and worker.get("complete_candidate_order") is True
        ):
            raise ValueError(f"non-zero-candidate authored row detected: {slug}")
        row_hashes.append(row["screening_worker_row_sha256"])
    return {
        "slug": slug,
        "build_trace_receipt": str(buildp),
        "build_trace_receipt_sha256": file_sha256(buildp),
        "replay_receipt": str(replayp),
        "replay_receipt_sha256": file_sha256(replayp),
        "eligible_frame": str(eligiblep),
        "eligible_frame_sha256": file_sha256(eligiblep),
        "eligible_roots": len(rows),
        "authored_worker_rows": len(row_hashes),
        "authored_worker_row_hashes_sha256": json_sha256(row_hashes),
        "scientific_candidate_tactics_executed": 0,
        "qualification_gate": True,
    }


def validate_extension2_qualification(qualification_root: Path) -> dict[str, Any]:
    configp = qualification_root / "frozen/extension_config.json"
    freezep = qualification_root / "frozen/freeze_receipt.json"
    environmentp = qualification_root / "preflight/environment.json"
    carryp = qualification_root / "screening/carry_forward_summary.json"
    parserp = qualification_root / "preflight/offline_parser_control.json"
    buildp = qualification_root / "screening/build_trace_summary.json"
    workerp = qualification_root / "preflight/screening_worker_compile.json"
    summaryp = qualification_root / "screening/summary.json"
    required = (
        configp, freezep, environmentp, carryp, parserp, buildp, workerp, summaryp
    )
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    config, freeze, environment, carry, parser, build, worker, summary = (
        base.read_json(path) for path in required
    )
    base.validate_code_lock(config["code_lock"])
    config_sha = file_sha256(configp)
    identity = json_sha256({
        key: item
        for key, item in config.items()
        if key not in {"created_utc", "identity_sha256"}
    })
    if not (
        config.get("extension_version") == EXTENSION2_VERSION
        and config.get("mechanical_fix_id") == EXTENSION2_FIX_ID
        and config.get("scientific_candidate_tactics_permitted") == 0
        and config.get("identity_sha256") == identity
        and freeze.get("config_sha256") == config_sha
        and freeze.get("scientific_candidate_tactics_executed") == 0
        and environment.get("config_sha256") == config_sha
        and environment.get("environment_gate") is True
        and environment.get("candidate_tactics_executed") == 0
        and environment.get("theorem_sources_elaborated") == 0
        and carry.get("config_sha256") == config_sha
        and carry.get("carry_forward_gate") is True
        and carry.get("scientific_candidate_tactics_executed") == 0
        and parser.get("config_sha256") == config_sha
        and parser.get("control_gate") is True
        and parser.get("candidate_tactics_executed") == 0
        and parser.get("theorem_sources_elaborated") == 0
        and build.get("config_sha256") == config_sha
        and build.get("build_trace_gate") is True
        and build.get("execution_complete") is True
        and build.get("combined_build_trace_passes", 0) >= base.MIN_REPOSITORIES
        and build.get("minimum_required") == base.MIN_REPOSITORIES
        and build.get("scientific_candidate_tactics_executed") == 0
        and worker.get("config_sha256") == config_sha
        and worker.get("compile_ok") is True
        and worker.get("candidate_tactics_executed") == 0
        and worker.get("theorem_sources_elaborated") == 0
        and summary.get("config_sha256") == config_sha
        and summary.get("screening_gate") is True
        and summary.get("selected_count", 0) >= base.MIN_REPOSITORIES
        and summary.get("scientific_candidate_tactics_executed") == 0
    ):
        raise ValueError("Extension2 qualification gates are not exact")
    selected = list(summary.get("selected_repositories", []))
    representatives = list(summary.get("lineage_representatives", []))
    backups = list(summary.get("ordered_backups", []))
    if not (
        summary.get("selected_count") == len(selected)
        and len(selected) == len(set(selected))
        and base.MIN_REPOSITORIES <= len(selected) <= base.TARGET_REPOSITORIES
        and selected == representatives[: base.TARGET_REPOSITORIES]
        and backups == representatives[base.TARGET_REPOSITORIES :]
    ):
        raise ValueError("Extension2 selected repository list changed")
    if any((qualification_root / phase).exists() for phase in ("scientific", "analysis", "audit")):
        raise ValueError("Extension2 qualification root contains scientific outcome artifacts")
    repositories = [
        validate_zero_candidate_replay(qualification_root, slug, config_sha)
        for slug in selected
    ]
    return {
        "extension_version": EXTENSION2_VERSION,
        "config": str(configp),
        "config_sha256": config_sha,
        "freeze_receipt": str(freezep),
        "freeze_receipt_sha256": file_sha256(freezep),
        "environment": str(environmentp),
        "environment_sha256": file_sha256(environmentp),
        "carry_forward_summary": str(carryp),
        "carry_forward_summary_sha256": file_sha256(carryp),
        "offline_parser_control": str(parserp),
        "offline_parser_control_sha256": file_sha256(parserp),
        "build_trace_summary": str(buildp),
        "build_trace_summary_sha256": file_sha256(buildp),
        "screening_worker_compile": str(workerp),
        "screening_worker_compile_sha256": file_sha256(workerp),
        "screening_summary": str(summaryp),
        "screening_summary_sha256": file_sha256(summaryp),
        "selected_repositories": selected,
        "ordered_backups": backups,
        "selected_count": len(selected),
        "repository_ledger": repositories,
        "authored_worker_rows": sum(row["authored_worker_rows"] for row in repositories),
        "scientific_candidate_tactics_executed": 0,
        "qualification_gate": True,
    }


def scientific_code_sources() -> list[Path]:
    sources = list(base_locked_sources())
    sources.extend(sorted(PACKAGE_ROOT.glob("*.py")))
    sources.append(PACKAGE_ROOT / "README_SERVER.md")
    sources.extend(Path(row["path"]) for row in document_lock()["files"])
    unique: dict[Path, None] = {}
    for path in sources:
        unique[Path(path).resolve()] = None
    return list(unique)


def validate_probe_surface(
    scientific_root: Path,
    qualification: dict[str, Any],
    targets: list[dict[str, Any]],
) -> tuple[dict[str, Any], Path]:
    receiptp = scientific_root / "preflight/exp52_probe_surface.json"
    if not receiptp.is_file():
        raise FileNotFoundError(
            f"run preflight_exp52_probe_surface.py before scientific freeze: {receiptp}"
        )
    receipt = base.read_json(receiptp)
    ledgerp = Path(receipt.get("module_ledger", "")).resolve()
    expected_target_sha = json_sha256(targets)
    retained = list(receipt.get("retained_panel", []))
    from experiment52_protocol import PROBE_POOL, retained_probe_panel
    ledger_rows = read_jsonl(ledgerp) if ledgerp.is_file() else []
    if not (
        receipt.get("alignment_version") == ALIGNMENT_VERSION
        and receipt.get("mechanical_fix_id") == ALIGNMENT_FIX_ID
        and receipt.get("qualification_config_sha256") == qualification["config_sha256"]
        and receipt.get("qualification_summary_sha256")
        == qualification["screening_summary_sha256"]
        and receipt.get("selected_repositories") == qualification["selected_repositories"]
        and receipt.get("staged_targets_sha256") == expected_target_sha
        and receipt.get("diagnostic_only") is True
        and receipt.get("theorem_sources_elaborated") == 0
        and receipt.get("candidate_tactics_executed") == 0
        and receipt.get("baseline_import_gate") is True
        and receipt.get("probe_surface_gate") is True
        and receipt.get("frozen_probe_pool") == PROBE_POOL
        and receipt.get("frozen_probe_pool_sha256") == json_sha256(PROBE_POOL)
        and retained == retained_probe_panel(retained)
        and receipt.get("retained_panel_sha256") == json_sha256(retained)
        and len(retained) >= 8
        and ledgerp.is_file()
        and ledgerp.is_relative_to(scientific_root)
        and file_sha256(ledgerp) == receipt.get("module_ledger_sha256")
        and len(ledger_rows) == receipt.get("unique_source_modules")
        and all(row.get("baseline", {}).get("compile_ok") is True for row in ledger_rows)
        and all(
            row.get("probe_results", {}).get(probe, {}).get("compile_ok") is True
            for row in ledger_rows
            for probe in retained
        )
    ):
        raise ValueError("Exp52 probe-surface preflight differs from staged targets")
    return receipt, receiptp


def copy_selected_build_receipts(
    scientific_root: Path,
    qualification_root: Path,
    selected: list[str],
) -> list[dict[str, Any]]:
    rows = []
    for slug in selected:
        name = f"{base.safe_slug(slug)}.json"
        source = qualification_root / "screening/build_trace" / name
        target = scientific_root / "screening/build_trace" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if file_sha256(target) != file_sha256(source):
                raise ValueError(f"copied build receipt changed: {slug}")
        else:
            shutil.copyfile(source, target)
        rows.append({
            "slug": slug,
            "source": str(source),
            "source_sha256": file_sha256(source),
            "copy": str(target),
            "copy_sha256": file_sha256(target),
            "exact": file_sha256(source) == file_sha256(target),
        })
    if not all(row["exact"] for row in rows):
        raise ValueError("selected build-receipt copy is not exact")
    return rows


def freeze(args: argparse.Namespace) -> dict[str, Any]:
    scientific_root = Path(args.root).resolve()
    qualification_root = Path(args.qualification_root).resolve()
    cfgp = scientific_root / "frozen/experiment51_config.json"
    targetsp = scientific_root / "frozen/targets.json"
    protocolp = scientific_root / "frozen/experiment52_protocol.json"
    txp = scientific_root / "frozen/freeze_transaction.json"
    if txp.is_file() and base.read_json(txp).get("completed") is True:
        config = base.read_json(cfgp)
        base.validate_code_lock(config["code_lock"])
        protocol = base.read_json(protocolp)
        validate_protocol(protocol)
        value = {
            "already_frozen": True,
            "config": str(cfgp),
            "config_sha256": file_sha256(cfgp),
            "exp52_protocol_sha256": file_sha256(protocolp),
        }
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value
    for phase in ("smoke", "scientific", "analysis", "audit", "environment"):
        if (scientific_root / phase).exists():
            raise ValueError(f"scientific freeze must precede {phase}")
    qualification = validate_extension2_qualification(qualification_root)
    base_recruitmentp = (
        base.ARTIFACT_ROOT / "recruitment_frozen/recruitment_config.json"
    )
    recruitment = base.read_json(base_recruitmentp)
    base.validate_code_lock(recruitment["code_lock"])
    selected = qualification["selected_repositories"][: base.TARGET_REPOSITORIES]
    targets, repositories = legacy_freeze.build_targets(
        qualification_root, selected
    )
    probe_receipt, probe_receiptp = validate_probe_surface(
        scientific_root, qualification, targets
    )
    code = base.code_lock(scientific_code_sources())
    created = datetime.now(timezone.utc).isoformat()
    config: dict[str, Any] = {
        "version": 1,
        "protocol_version": base.PROTOCOL_VERSION,
        "mechanical_fix_id": ALIGNMENT_FIX_ID,
        "alignment_version": ALIGNMENT_VERSION,
        "created_utc": created,
        "study_role": (
            "Tier-1 external repository replication if execution and preregistered gates pass"
        ),
        "target_lean_version": base.TARGET_LEAN_VERSION,
        "target_toolchain": base.TARGET_TOOLCHAIN,
        "repositories": repositories,
        "repository_count": len(repositories),
        "ordered_pre_candidate_backups": qualification["ordered_backups"],
        "minimum_repositories": base.MIN_REPOSITORIES,
        "roots_per_repository": base.ROOTS_PER_REPOSITORY,
        "roots": len(targets),
        "candidate_budget": base.CANDIDATES_PER_ROOT,
        "alternative_library": base.ALTERNATIVE_LIBRARY,
        "candidate_library_sha256": json_sha256(base.ALTERNATIVE_LIBRARY),
        "primary_panel": "L0",
        "robust_panel": "L-mechanism-diverse",
        "candidate_genealogy": base.CANDIDATE_GENEALOGY,
        "candidate_genealogy_sha256": json_sha256(base.CANDIDATE_GENEALOGY),
        "primary_endpoint": {
            "name": "kappa_struct_v1",
            "schema": base.STRICT_ENDPOINT_SCHEMA,
        },
        "root_sample": {
            "method": "simple_random_without_replacement",
            "master_seed": base.MASTER_SAMPLE_SEED,
            "roots_per_repository": base.ROOTS_PER_REPOSITORY,
        },
        "smoke_target_ids": [
            targets[index]["theorem_id"]
            for index in (0, 1, base.ROOTS_PER_REPOSITORY, base.ROOTS_PER_REPOSITORY + 1)
        ],
        "estimand": (
            "equal-weight mean of repository Y-L0 rates in the frozen eligible frame"
        ),
        "bootstrap": {
            "levels": ["repository", "root"],
            "replicates": base.BOOTSTRAP_REPLICATES,
            "seed": base.BOOTSTRAP_SEED,
            "interval": "percentile_95",
        },
        "gates": {
            "minimum_completed_repositories": base.MIN_REPOSITORIES,
            "overall_evaluability": base.MIN_OVERALL_EVALUABILITY,
            "per_repository_evaluability": base.MIN_REPOSITORY_EVALUABILITY,
            "all_candidates_attempted_per_evaluable_root": base.CANDIDATES_PER_ROOT,
            "primary_ci_halfwidth_at_most": base.MAX_CI_HALFWIDTH,
            "primary_ci_lower_gt": base.PRIMARY_DELTA,
            "primary_nonzero_repository_fraction": 0.75,
            "robust_ci_lower_gt": base.ROBUST_DELTA,
            "robust_nonzero_repository_fraction": 0.75,
            "robust_nonterminal_repository_fraction": 0.50,
            "manual_reconciliation_count": 0,
        },
        "source": {
            "recruitment_config": str(base_recruitmentp),
            "recruitment_config_sha256": file_sha256(base_recruitmentp),
            "screening_summary": qualification["screening_summary"],
            "screening_summary_sha256": qualification["screening_summary_sha256"],
            "extension2_qualification": qualification,
            "exp52_probe_surface": str(probe_receiptp),
            "exp52_probe_surface_sha256": file_sha256(probe_receiptp),
            **recruitment["source_controls"],
        },
        "exp52_freeze_required_before_execution": True,
        "claim_boundary": [
            "state-conditioned one-step endpoint agreement under frozen candidate panels",
            "not tactic equivalence or global tactic interchangeability",
            "not semantic, proof-strategy, or proof-term equivalence",
            "not runtime equivalence or improved theorem proving",
            "repository-macro estimand over this frozen eligible frame only",
        ],
        "code_lock": code,
        "next_step": (
            "Compile-only scientific worker preflight, environment receipt, then smoke."
        ),
    }
    config["identity_sha256"] = json_sha256({
        key: item
        for key, item in config.items()
        if key not in {"created_utc", "identity_sha256"}
    })
    protocol52 = build_exp52_protocol(
        created_utc=created,
        source_config_identity_sha256=config["identity_sha256"],
        selected_repositories=selected,
        probe_surface_receipt=str(probe_receiptp),
        probe_surface_receipt_sha256=file_sha256(probe_receiptp),
        available_probes=probe_receipt["retained_panel"],
    )
    validate_protocol(protocol52)
    copied = copy_selected_build_receipts(
        scientific_root, qualification_root, selected
    )
    base.exclusive_create_json(scientific_root / "frozen/freeze_claim.json", {
        "version": 1,
        "created_utc": created,
        "identity_sha256": config["identity_sha256"],
        "alignment_version": ALIGNMENT_VERSION,
    })
    base.atomic_json_dump(config, cfgp)
    base.atomic_json_dump(targets, targetsp)
    base.atomic_json_dump(protocol52, protocolp)
    receipt = {
        "version": 1,
        "alignment_version": ALIGNMENT_VERSION,
        "mechanical_fix_id": ALIGNMENT_FIX_ID,
        "config_sha256": file_sha256(cfgp),
        "targets_sha256": file_sha256(targetsp),
        "repositories": len(repositories),
        "roots": len(targets),
        "qualification_root": str(qualification_root),
        "qualification_config_sha256": qualification["config_sha256"],
        "qualification_summary_sha256": qualification["screening_summary_sha256"],
        "copied_build_receipts": copied,
        "copied_build_receipts_exact": all(row["exact"] for row in copied),
        "exp52_protocol_sha256": file_sha256(protocolp),
        "exp52_design_documents_bundle_sha256": protocol52[
            "preregistration_documents"
        ]["bundle_sha256"],
        "exp52_retained_probes": len(protocol52["probe_surface"]["retained_panel"]),
        "scientific_candidate_execution_before_freeze": False,
        "scientific_candidate_tactics_executed": 0,
    }
    base.atomic_json_dump(receipt, scientific_root / "frozen/freeze_receipt.json")
    base.atomic_json_dump(
        {"version": 1, "completed": True, **receipt}, txp
    )
    print(json.dumps({**receipt, "next_step": config["next_step"]}, ensure_ascii=False, indent=2))
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", default=str(SERVER_ROOT / SCIENTIFIC_ARTIFACT_RELATIVE)
    )
    parser.add_argument(
        "--qualification-root",
        default=str(SERVER_ROOT / QUALIFICATION_ARTIFACT_RELATIVE),
    )
    return parser.parse_args()


if __name__ == "__main__":
    freeze(parse_args())
