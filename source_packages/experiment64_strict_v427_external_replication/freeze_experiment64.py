"""Prospectively freeze the complete Exp64 repository and theorem frame."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from experiment64_protocol import *

sys.path.insert(0, str(MZX_ROOT / "experiment51_external_repository_replication"))
import experiment51_protocol as exp51  # type: ignore


def _verify_source(source: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    progressp = source / "qualification/progress.json"
    auditp = source / "audit/audit.json"
    lineagep = source / "qualification/lineage_ledger.jsonl"
    progress, audit = read_json(progressp), read_json(auditp)
    assert_sealed(progress, "Exp63 progress")
    assert_sealed(audit, "Exp63 audit")
    if audit.get("audit_passed") is not True:
        raise ValueError("Exp63 final audit did not pass")
    if progress.get("completed_repositories") != progress.get("frozen_candidates"):
        raise ValueError("Exp63 candidate frame was not exhausted")
    if progress.get("stopping_reason") != "candidate_frame_exhausted":
        raise ValueError("unexpected Exp63 stopping reason")
    if progress.get("scientific_candidate_tactics_executed") != 0:
        raise ValueError("Exp63 was not a zero-scientific-tactic recruitment run")
    if file_sha256(lineagep) != progress.get("lineage_ledger_sha256"):
        raise ValueError("Exp63 lineage ledger hash changed")
    source_receipt = {
        "exp63_progress": str(progressp),
        "exp63_progress_sha256": file_sha256(progressp),
        "exp63_audit": str(auditp),
        "exp63_audit_sha256": file_sha256(auditp),
        "exp63_lineage_ledger": str(lineagep),
        "exp63_lineage_ledger_sha256": file_sha256(lineagep),
        "exp63_audit_record_sha256": audit["record_sha256"],
        "exp63_progress_record_sha256": progress["record_sha256"],
    }
    return progress, audit, source_receipt


def _selected_rows(source: Path, progress: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    representatives = list(progress.get("representative_slugs", []))
    if len(representatives) != REPOSITORY_COUNT or len(set(representatives)) != REPOSITORY_COUNT:
        raise ValueError(f"expected exactly {REPOSITORY_COUNT} Exp63 lineage representatives")
    lineage = {row["slug"]: row for row in read_jsonl(source / "qualification/lineage_ledger.jsonl")}
    repositories: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    for repository_index, slug in enumerate(representatives, 1):
        safe = safe_slug(slug)
        if lineage.get(slug, {}).get("lineage_representative") is not True:
            raise ValueError(f"not an Exp63 lineage representative: {slug}")
        receiptp = source / "qualification/repositories" / f"{safe}.json"
        receipt = read_json(receiptp)
        assert_sealed(receipt, f"Exp63 qualification {slug}")
        candidate = dict(receipt["candidate"])
        if receipt.get("qualification_gate") is not True or receipt.get("classification") != "qualified":
            raise ValueError(f"Exp63 repository was not qualified: {slug}")
        strict = candidate.get("strict_v427_eligibility", {})
        if (candidate.get("lean_toolchain_observed") != TARGET_TOOLCHAIN
                or strict.get("exact_root_toolchain") != TARGET_TOOLCHAIN
                or strict.get("current_default_branch_commit") is not True):
            raise ValueError(f"strict current-v4.27 identity failed: {slug}")
        eligiblep = source / "qualification/eligible_frames" / f"{safe}.jsonl"
        eligible = read_jsonl(eligiblep)
        authored = receipt.get("authored_replay", {})
        if file_sha256(eligiblep) != authored.get("eligible_frame_sha256"):
            raise ValueError(f"eligible frame hash changed: {slug}")
        if len(eligible) != authored.get("eligible_roots") or len(eligible) < ROOTS_PER_REPOSITORY:
            raise ValueError(f"fewer than {ROOTS_PER_REPOSITORY} eligible roots: {slug}")
        ordered = sorted(
            eligible,
            key=lambda row: selection_key(ROOT_SELECTION_SEED, slug, row["theorem_id"]),
        )
        selected = ordered[:ROOTS_PER_REPOSITORY]
        for root_index, raw in enumerate(selected, 1):
            if raw.get("slug") != slug or raw.get("commit") != candidate["commit"]:
                raise ValueError(f"eligible target repository identity changed: {slug}")
            authoredp = source / "qualification/authored_rows" / safe / f"{raw['rid']}.json"
            authored_row = read_json(authoredp)
            if not (
                authored_row.get("theorem_id") == raw["theorem_id"]
                and authored_row.get("worker_ok") is True
                and authored_row.get("authored_replay_ok") is True
                and authored_row.get("same_pre_state_all_branches") is True
                and authored_row.get("candidate_order") == []
            ):
                raise ValueError(f"Exp63 authored eligibility changed: {slug} {raw['theorem_id']}")
            alternatives = exp51.expected_alternatives(raw["authored_tactic"])
            robust = exp51.select_candidate_view(alternatives, "L-mechanism-diverse")
            if len(alternatives) != CANDIDATES_PER_ROOT:
                raise ValueError("candidate panel width changed")
            target = dict(raw)
            target.update({
                "repository_index": repository_index,
                "root_index_within_repository": root_index,
                "selection_key": selection_key(ROOT_SELECTION_SEED, slug, raw["theorem_id"]),
                "alternatives": alternatives,
                "robust_alternatives": robust,
                "exp63_authored_receipt_sha256": file_sha256(authoredp),
            })
            targets.append(target)
        repositories.append({
            "repository_index": repository_index,
            "slug": slug,
            "url": candidate["url"],
            "commit": candidate["commit"],
            "subdir": candidate.get("subdir", "."),
            "domain": candidate.get("domain", "unclassified"),
            "snapshot_source": candidate["snapshot_source"],
            "snapshot_record_sha256": candidate["snapshot_record_sha256"],
            "lean_toolchain_observed": candidate["lean_toolchain_observed"],
            "strict_v427_eligibility": strict,
            "eligible_roots_available": len(eligible),
            "roots_frozen": ROOTS_PER_REPOSITORY,
            "exp63_qualification_receipt_sha256": file_sha256(receiptp),
            "exp63_eligible_frame_sha256": file_sha256(eligiblep),
        })
    if len(targets) != REPOSITORY_COUNT * ROOTS_PER_REPOSITORY:
        raise ValueError("frozen target count changed")
    return repositories, targets


def run(root: Path, source: Path) -> dict[str, Any]:
    progress, _, source_receipt = _verify_source(source)
    repositories, targets = _selected_rows(source, progress)
    repositoryp = root / "frozen/repositories.json"
    targetsp = root / "frozen/targets.json"
    sourcep = root / "frozen/source_receipt.json"
    protocolp = root / "frozen/protocol.json"
    atomic_json_dump(repositories, repositoryp)
    atomic_json_dump(targets, targetsp)
    atomic_json_dump(source_receipt, sourcep)
    protocol = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "measurement_engine_protocol": MEASUREMENT_ENGINE_PROTOCOL,
        "prospectively_frozen_before_scientific_execution": True,
        "source_exp63_root": str(source),
        "source_receipt_sha256": file_sha256(sourcep),
        "repositories_sha256": file_sha256(repositoryp),
        "targets_sha256": file_sha256(targetsp),
        "repository_count": REPOSITORY_COUNT,
        "roots_per_repository": ROOTS_PER_REPOSITORY,
        "roots": len(targets),
        "candidates_per_root": CANDIDATES_PER_ROOT,
        "candidate_invocations_planned": len(targets) * CANDIDATES_PER_ROOT,
        "root_selection_seed": ROOT_SELECTION_SEED,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "fixed_operational_repository_attempts": MAX_OPERATIONAL_REPOSITORY_ATTEMPTS,
        "primary_estimand": "equal-weight mean of repository-specific Y-L0 root frequencies",
        "uncertainty_method": "two-level nonparametric bootstrap over repositories and roots",
        "missingness_reporting": "complete-case estimate plus frozen-frame worst-case bounds",
        "scientific_decision_threshold": None,
        "historical_38_repository_target_is_a_recruitment_design_goal_not_a_validity_gate": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "implementation_locks": implementation_locks(),
        "source_locks": source_locks(),
        "scientific_candidate_tactics_executed": 0,
    })
    if protocolp.exists():
        prior = read_json(protocolp)
        if prior != protocol:
            raise ValueError("existing Exp64 freeze differs from deterministic reconstruction")
    atomic_json_dump(protocol, protocolp)
    result = {
        "protocol_version": PROTOCOL_VERSION,
        "repositories": len(repositories),
        "roots": len(targets),
        "candidate_invocations_planned": len(targets) * CANDIDATES_PER_ROOT,
        "protocol_sha256": file_sha256(protocolp),
        "targets_sha256": file_sha256(targetsp),
        "next_step": "Execute the frozen scientific frame without repository replacement.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--source-exp63-root", default=str(SOURCE_EXP63_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    parsed = parse_args()
    run(Path(parsed.artifact_root).resolve(), Path(parsed.source_exp63_root).resolve())
