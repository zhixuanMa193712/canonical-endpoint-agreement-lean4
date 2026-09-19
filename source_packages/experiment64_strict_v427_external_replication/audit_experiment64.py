"""Independent reconstruction audit for Exp64 scientific records."""
from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from experiment64_protocol import *

sys.path.insert(0, str(MZX_ROOT / "experiment51_external_repository_replication"))
import experiment51_protocol as exp51  # type: ignore


def root_indicator(worker: dict[str, Any], tactics: list[str]) -> tuple[bool, bool, bool, set[tuple[str, str]]]:
    initial = worker["initial_endpoints"]["struct"]["sha256"]
    allowed = set(tactics)
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for branch in worker["candidates"]:
        if branch["tactic"] not in allowed or branch.get("executable") is not True:
            continue
        endpoint = branch["endpoints"]["struct"]["sha256"]
        if endpoint != initial:
            clusters[endpoint].append(branch)
    pairs: set[tuple[str, str]] = set()
    nonterminal, cross_family = False, False
    for branches in clusters.values():
        for left, right in itertools.combinations(branches, 2):
            if left["head"] == right["head"]:
                continue
            pairs.add(tuple(sorted((left["head"], right["head"]))))
            if left.get("terminal") is False and right.get("terminal") is False:
                nonterminal = True
            if left["family"] != right["family"]:
                cross_family = True
    return bool(pairs), nonterminal, cross_family, pairs


def bootstrap(by_repo: dict[str, list[dict[str, Any]]], field: str, seed: int) -> list[float]:
    slugs = sorted(slug for slug, rows in by_repo.items() if rows)
    if not slugs:
        return []
    rng = random.Random(seed)
    output = []
    for _ in range(BOOTSTRAP_REPLICATES):
        chosen = [rng.choice(slugs) for _ in slugs]
        repository_means = []
        for slug in chosen:
            rows = by_repo[slug]
            sample = [rng.choice(rows) for _ in rows]
            repository_means.append(mean(int(row[field]) for row in sample))
        output.append(mean(repository_means))
    return output


def interval(values: list[float]) -> list[float]:
    return [quantile(values, 0.025), quantile(values, 0.975)] if values else [0.0, 0.0]


def run(root: Path) -> dict[str, Any]:
    protocolp = root / "frozen/protocol.json"
    targetsp = root / "frozen/targets.json"
    repositoriesp = root / "frozen/repositories.json"
    analysisp = root / "analysis/summary.json"
    protocol = read_json(protocolp)
    analysis = read_json(analysisp)
    assert_sealed(protocol, "Exp64 protocol")
    assert_sealed(analysis, "Exp64 analysis")
    validate_locks(protocol)
    targets = json.loads(targetsp.read_text(encoding="utf-8"))
    repositories = json.loads(repositoriesp.read_text(encoding="utf-8"))
    config_sha = file_sha256(protocolp)
    by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    per_repo = {
        repository["slug"]: {
            "evaluable": 0, "missing": ROOTS_PER_REPOSITORY,
            "success_l0": 0, "success_robust": 0,
            "nonterminal": 0, "cross_family": 0,
        }
        for repository in repositories
    }
    pair_repositories: dict[tuple[str, str], set[str]] = defaultdict(set)
    worker_receipts = 0
    candidate_requested = 0
    candidate_recorded = 0
    identity_ok = True
    candidate_panel_ok = True
    authored_ok = True
    prestate_ok = True
    for target in targets:
        path = root / "scientific/theorems" / safe_slug(target["slug"]) / f"{target['rid']}.json"
        if not path.is_file():
            continue
        worker_receipts += 1
        candidate_requested += CANDIDATES_PER_ROOT
        worker = read_json(path)
        candidate_recorded += len(worker.get("candidates", []))
        expected_hash = json_sha256({key: value for key, value in worker.items() if key != "record_sha256"})
        identity_ok &= bool(
            worker.get("record_sha256") == expected_hash
            and worker.get("mode") == "exp64_scientific"
            and worker.get("config_sha256") == config_sha
            and worker.get("theorem_id") == target["theorem_id"]
            and worker.get("source_file_sha256") == target["source_file_sha256"]
            and worker.get("candidate_order") == target["alternatives"]
        )
        if worker.get("worker_ok") is not True:
            continue
        candidate_panel_ok &= len(worker.get("candidates", [])) == CANDIDATES_PER_ROOT
        authored_ok &= worker.get("authored_replay_ok") is True
        prestate_ok &= worker.get("same_pre_state_all_branches") is True
        robust = exp51.select_candidate_view(target["alternatives"], "L-mechanism-diverse")
        if robust != target["robust_alternatives"]:
            raise ValueError("frozen robust panel changed")
        y0, nt, cf, pairs = root_indicator(worker, target["alternatives"])
        yr, _, _, _ = root_indicator(worker, target["robust_alternatives"])
        record = {"Y_L0": y0, "Y_robust": yr}
        by_repo[target["slug"]].append(record)
        summary = per_repo[target["slug"]]
        summary["evaluable"] += 1
        summary["missing"] -= 1
        summary["success_l0"] += int(y0)
        summary["success_robust"] += int(yr)
        summary["nonterminal"] += int(nt)
        summary["cross_family"] += int(cf)
        for pair in pairs:
            pair_repositories[pair].add(target["slug"])
    slugs = [repository["slug"] for repository in repositories]
    primary_rates = [
        mean(int(row["Y_L0"]) for row in by_repo[slug])
        for slug in slugs if by_repo[slug]
    ]
    robust_rates = [
        mean(int(row["Y_robust"]) for row in by_repo[slug])
        for slug in slugs if by_repo[slug]
    ]
    primary_ci = interval(bootstrap(by_repo, "Y_L0", BOOTSTRAP_SEED))
    robust_ci = interval(bootstrap(by_repo, "Y_robust", BOOTSTRAP_SEED + 1))
    lower = mean(per_repo[slug]["success_l0"] / ROOTS_PER_REPOSITORY for slug in slugs)
    upper = mean(
        (per_repo[slug]["success_l0"] + per_repo[slug]["missing"]) / ROOTS_PER_REPOSITORY
        for slug in slugs
    )
    robust_lower = mean(per_repo[slug]["success_robust"] / ROOTS_PER_REPOSITORY for slug in slugs)
    robust_upper = mean(
        (per_repo[slug]["success_robust"] + per_repo[slug]["missing"]) / ROOTS_PER_REPOSITORY
        for slug in slugs
    )
    checks = {
        "protocol_and_targets_exact": (
            analysis.get("protocol_sha256") == config_sha
            and analysis.get("targets_sha256") == file_sha256(targetsp)
        ),
        "worker_identity_records_exact": identity_ok,
        "repository_count_exact": analysis.get("repositories") == len(repositories) == REPOSITORY_COUNT,
        "root_count_exact": analysis.get("frozen_roots") == len(targets) == REPOSITORY_COUNT * ROOTS_PER_REPOSITORY,
        "evaluable_count_exact": analysis.get("evaluable_roots") == sum(len(rows) for rows in by_repo.values()),
        "candidate_requested_exact": analysis.get("candidate_invocations_requested") == candidate_requested,
        "candidate_recorded_exact": analysis.get("candidate_invocations_recorded") == candidate_recorded,
        "complete_candidate_panel_for_evaluable_rows": candidate_panel_ok,
        "authored_replay_exact_for_evaluable_rows": authored_ok,
        "same_prestate_for_evaluable_rows": prestate_ok,
        "primary_repository_rates_exact": analysis["primary"]["complete_case_repository_rates"] == primary_rates,
        "primary_macro_exact": analysis["primary"]["complete_case_macro_mean"] == (mean(primary_rates) if primary_rates else None),
        "primary_bootstrap_exact": analysis["primary"]["two_level_nonparametric_bootstrap_95ci"] == primary_ci,
        "primary_missingness_bounds_exact": analysis["primary"]["frozen_frame_worst_case_bounds"] == [lower, upper],
        "robust_repository_rates_exact": analysis["mechanism_diverse_sensitivity"]["complete_case_repository_rates"] == robust_rates,
        "robust_macro_exact": analysis["mechanism_diverse_sensitivity"]["complete_case_macro_mean"] == (mean(robust_rates) if robust_rates else None),
        "robust_bootstrap_exact": analysis["mechanism_diverse_sensitivity"]["two_level_nonparametric_bootstrap_95ci"] == robust_ci,
        "robust_missingness_bounds_exact": analysis["mechanism_diverse_sensitivity"]["frozen_frame_worst_case_bounds"] == [robust_lower, robust_upper],
        "pair_counts_exact": (
            analysis["descriptive_structure"]["distinct_cross_head_pairs"] == len(pair_repositories)
            and analysis["descriptive_structure"]["pairs_recurring_in_at_least_two_repositories"]
            == sum(len(values) >= 2 for values in pair_repositories.values())
        ),
        "no_scientific_threshold_decision": (
            protocol.get("scientific_decision_threshold") is None
            and analysis.get("scientific_decision_threshold") is None
            and analysis.get("historical_38_repository_target_used_as_scientific_gate") is False
        ),
        "manual_reconciliation_zero": analysis["integrity_checks"]["manual_reconciliation_zero"] is True,
    }
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "audit_passed": all(checks.values()),
        "checks": checks,
        "analysis_sha256": file_sha256(analysisp),
        "repositories_reconstructed": len(repositories),
        "roots_reconstructed": len(targets),
        "worker_receipts_reconstructed": worker_receipts,
        "evaluable_roots_reconstructed": sum(len(rows) for rows in by_repo.values()),
        "bootstrap_replicates_reconstructed": BOOTSTRAP_REPLICATES,
        "manual_reconciliation_count": 0,
        "claim_boundary": "This audit checks deterministic reconstruction; it adds no scientific result.",
    })
    atomic_json_dump(value, root / "audit/audit.json")
    print(json.dumps(value, ensure_ascii=False, indent=2))
    if not value["audit_passed"]:
        raise ValueError("Exp64 independent audit failed")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    run(Path(parse_args().artifact_root).resolve())
