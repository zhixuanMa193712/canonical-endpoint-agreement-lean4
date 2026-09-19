"""Analyze Exp64 without converting a design target into a scientific gate."""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

from experiment64_protocol import *

sys.path.insert(0, str(MZX_ROOT / "experiment51_external_repository_replication"))
import experiment51_protocol as exp51  # type: ignore


def candidate_pairs(rows: Iterable[dict[str, Any]]) -> set[tuple[str, str]]:
    output = set()
    for left, right in itertools.combinations(list(rows), 2):
        if left["head"] != right["head"]:
            output.add(tuple(sorted((left["head"], right["head"]))))
    return output


def analyze_view(worker: dict[str, Any], tactics: list[str]) -> dict[str, Any]:
    if worker.get("worker_ok") is not True:
        return {"evaluable": False, "candidate_count": len(tactics), "Y": None,
                "Y_nonterminal": None, "Y_cross_family": None}
    allowed = set(tactics)
    selected = [row for row in worker["candidates"] if row["tactic"] in allowed]
    expected = [tactic for tactic in worker["candidate_order"] if tactic in allowed]
    if [row["tactic"] for row in selected] != expected:
        raise ValueError("candidate view order changed")
    initial = worker["initial_endpoints"]["struct"]["sha256"]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for branch in selected:
        if branch.get("executable") is True:
            endpoint = branch["endpoints"]["struct"]["sha256"]
            if endpoint != initial:
                groups[endpoint].append(branch)
    pairs: set[tuple[str, str]] = set()
    nonterminal_pairs: set[tuple[str, str]] = set()
    cross_family_pairs: set[tuple[str, str]] = set()
    tactic_pair_count = 0
    clusters = []
    for endpoint, branches in sorted(groups.items()):
        heads = {row["head"] for row in branches}
        if len(heads) < 2:
            continue
        branch_pairs = candidate_pairs(branches)
        pairs |= branch_pairs
        tactic_pair_count += sum(
            left["head"] != right["head"] for left, right in itertools.combinations(branches, 2)
        )
        nonterminal = all(row.get("terminal") is False for row in branches)
        families = {row["family"] for row in branches}
        if nonterminal:
            nonterminal_pairs |= branch_pairs
        if len(families) >= 2:
            cross_family_pairs |= branch_pairs
        clusters.append({
            "endpoint_sha256": endpoint,
            "cluster_size": len(branches),
            "heads": sorted(heads),
            "families": sorted(families),
            "nonterminal": nonterminal,
        })
    denominator = math.comb(len(tactics), 2) if len(tactics) >= 2 else 0
    return {
        "evaluable": True,
        "candidate_count": len(tactics),
        "executable_candidates": sum(row.get("executable") is True for row in selected),
        "nontrivial_executable_candidates": sum(
            row.get("executable") is True
            and row["endpoints"]["struct"]["sha256"] != initial
            for row in selected
        ),
        "Y": bool(pairs),
        "Y_nonterminal": bool(nonterminal_pairs),
        "Y_cross_family": bool(cross_family_pairs),
        "W_pair_density": tactic_pair_count / denominator if denominator else 0.0,
        "cross_head_pairs": [list(pair) for pair in sorted(pairs)],
        "nonterminal_pairs": [list(pair) for pair in sorted(nonterminal_pairs)],
        "cross_family_pairs": [list(pair) for pair in sorted(cross_family_pairs)],
        "qualifying_endpoint_clusters": clusters,
    }


def worker_path(root: Path, target: dict[str, Any]) -> Path:
    return root / "scientific/theorems" / safe_slug(target["slug"]) / f"{target['rid']}.json"


def load_root_row(root: Path, target: dict[str, Any], config_sha: str) -> dict[str, Any]:
    path = worker_path(root, target)
    base = {
        "slug": target["slug"], "commit": target["commit"],
        "theorem_id": target["theorem_id"], "full_name": target["full_name"],
        "file_path": target["file_path"], "rid": target["rid"],
        "worker_receipt_present": path.is_file(), "worker_ok": False,
        "candidate_attempts": 0, "candidate_invocations_requested": 0,
    }
    if not path.is_file():
        base.update({
            "operational_reason": "repository_or_root_receipt_absent",
            "L0": {"evaluable": False, "Y": None},
            "L-mechanism-diverse": {"evaluable": False, "Y": None},
        })
        return base
    worker = read_json(path)
    expected_hash = json_sha256({key: value for key, value in worker.items() if key != "record_sha256"})
    if worker.get("record_sha256") != expected_hash:
        raise ValueError(f"worker record hash changed: {path}")
    if not (
        worker.get("mode") == "exp64_scientific"
        and worker.get("config_sha256") == config_sha
        and worker.get("theorem_id") == target["theorem_id"]
        and worker.get("source_file_sha256") == target["source_file_sha256"]
        and worker.get("candidate_order") == target["alternatives"]
    ):
        raise ValueError(f"worker identity changed: {path}")
    robust = exp51.select_candidate_view(target["alternatives"], "L-mechanism-diverse")
    if robust != target["robust_alternatives"]:
        raise ValueError("mechanism-diverse panel changed")
    base.update({
        "worker_ok": worker.get("worker_ok") is True,
        "candidate_attempts": len(worker.get("candidates", [])),
        "candidate_invocations_requested": CANDIDATES_PER_ROOT,
        "operational_reason": None if worker.get("worker_ok") is True
                              else str(worker.get("error_type", "worker_gate")),
        "authored_replay_ok": worker.get("authored_replay_ok") is True,
        "same_pre_state_all_branches": worker.get("same_pre_state_all_branches") is True,
        "L0": analyze_view(worker, target["alternatives"]),
        "L-mechanism-diverse": analyze_view(worker, target["robust_alternatives"]),
    })
    return base


def repository_summary(slug: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    evaluable = [row for row in rows if row["worker_ok"]]
    successes_l0 = sum(row["L0"]["Y"] is True for row in evaluable)
    successes_robust = sum(row["L-mechanism-diverse"]["Y"] is True for row in evaluable)
    missing = len(rows) - len(evaluable)
    files = Counter(row["file_path"] for row in evaluable)
    file_rates = [
        mean(int(row["L0"]["Y"]) for row in evaluable if row["file_path"] == name)
        for name in sorted(files)
    ]
    return {
        "slug": slug,
        "frozen_roots": len(rows),
        "worker_receipts": sum(row["worker_receipt_present"] for row in rows),
        "evaluable_roots": len(evaluable),
        "missing_roots": missing,
        "evaluable_rate": len(evaluable) / len(rows) if rows else 0.0,
        "Y_L0_successes": successes_l0,
        "Y_Lrobust_successes": successes_robust,
        "Y_L0_complete_case_rate": successes_l0 / len(evaluable) if evaluable else None,
        "Y_Lrobust_complete_case_rate": successes_robust / len(evaluable) if evaluable else None,
        "Y_L0_frozen_frame_lower": successes_l0 / len(rows) if rows else 0.0,
        "Y_L0_frozen_frame_upper": (successes_l0 + missing) / len(rows) if rows else 1.0,
        "Y_Lrobust_frozen_frame_lower": successes_robust / len(rows) if rows else 0.0,
        "Y_Lrobust_frozen_frame_upper": (successes_robust + missing) / len(rows) if rows else 1.0,
        "Y_nonterminal_L0_successes": sum(row["L0"].get("Y_nonterminal") is True for row in evaluable),
        "Y_cross_family_L0_successes": sum(row["L0"].get("Y_cross_family") is True for row in evaluable),
        "unique_sampled_files": len(files),
        "equal_weight_file_mean_sensitivity": mean(file_rates) if file_rates else None,
    }


def hierarchical_bootstrap(
    root_rows: list[dict[str, Any]], view: str, seed: int, replicates: int
) -> list[float]:
    by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in root_rows:
        if row["worker_ok"]:
            by_repo[row["slug"]].append(row)
    slugs = sorted(by_repo)
    if not slugs:
        return []
    rng = random.Random(seed)
    values = []
    for _ in range(replicates):
        chosen = [rng.choice(slugs) for _ in slugs]
        repository_means = []
        for slug in chosen:
            rows = by_repo[slug]
            sampled = [rng.choice(rows) for _ in rows]
            repository_means.append(mean(int(row[view]["Y"]) for row in sampled))
        values.append(mean(repository_means))
    return values


def interval(values: list[float]) -> list[float]:
    return [quantile(values, 0.025), quantile(values, 0.975)] if values else [0.0, 0.0]


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.artifact_root).resolve()
    protocolp = root / "frozen/protocol.json"
    targetsp = root / "frozen/targets.json"
    repositoriesp = root / "frozen/repositories.json"
    protocol = read_json(protocolp)
    assert_sealed(protocol, "Exp64 protocol")
    validate_locks(protocol)
    targets = json.loads(targetsp.read_text(encoding="utf-8"))
    repositories = json.loads(repositoriesp.read_text(encoding="utf-8"))
    scientific = read_json(root / "scientific/summary.json")
    assert_sealed(scientific, "Exp64 scientific summary")
    if scientific.get("completed_repositories") != REPOSITORY_COUNT:
        raise ValueError("frozen repository execution is incomplete")
    config_sha = file_sha256(protocolp)
    root_rows = [load_root_row(root, target, config_sha) for target in targets]
    atomic_jsonl_dump(root_rows, root / "analysis/theorem_rows.jsonl")
    repository_rows = [
        repository_summary(
            repository["slug"],
            [row for row in root_rows if row["slug"] == repository["slug"]],
        )
        for repository in repositories
    ]
    primary_rates = [
        row["Y_L0_complete_case_rate"] for row in repository_rows
        if row["Y_L0_complete_case_rate"] is not None
    ]
    robust_rates = [
        row["Y_Lrobust_complete_case_rate"] for row in repository_rows
        if row["Y_Lrobust_complete_case_rate"] is not None
    ]
    primary_bootstrap = hierarchical_bootstrap(
        root_rows, "L0", BOOTSTRAP_SEED, BOOTSTRAP_REPLICATES
    )
    robust_bootstrap = hierarchical_bootstrap(
        root_rows, "L-mechanism-diverse", BOOTSTRAP_SEED + 1, BOOTSTRAP_REPLICATES
    )
    primary_ci = interval(primary_bootstrap)
    robust_ci = interval(robust_bootstrap)
    pair_repositories: dict[tuple[str, str], set[str]] = defaultdict(set)
    pair_occurrences: Counter[tuple[str, str]] = Counter()
    for row in root_rows:
        if row["worker_ok"]:
            for pair in row["L0"]["cross_head_pairs"]:
                key = tuple(pair)
                pair_repositories[key].add(row["slug"])
                pair_occurrences[key] += 1
    pair_table = [
        {
            "head_pair": list(pair),
            "root_occurrences": count,
            "repository_count": len(pair_repositories[pair]),
            "repositories": sorted(pair_repositories[pair]),
        }
        for pair, count in sorted(pair_occurrences.items(), key=lambda item: (-item[1], item[0]))
    ]
    atomic_jsonl_dump(pair_table, root / "analysis/pair_concentration.jsonl")
    lower = mean(row["Y_L0_frozen_frame_lower"] for row in repository_rows)
    upper = mean(row["Y_L0_frozen_frame_upper"] for row in repository_rows)
    robust_lower = mean(row["Y_Lrobust_frozen_frame_lower"] for row in repository_rows)
    robust_upper = mean(row["Y_Lrobust_frozen_frame_upper"] for row in repository_rows)
    loo = []
    for repository in repository_rows:
        retained = [
            row["Y_L0_complete_case_rate"] for row in repository_rows
            if row["slug"] != repository["slug"] and row["Y_L0_complete_case_rate"] is not None
        ]
        loo.append({"left_out": repository["slug"], "complete_case_macro_mean": mean(retained) if retained else None})
    integrity = {
        "frozen_repository_count_exact": len(repository_rows) == REPOSITORY_COUNT,
        "frozen_root_count_exact": len(root_rows) == REPOSITORY_COUNT * ROOTS_PER_REPOSITORY,
        "repository_receipts_complete": scientific.get("completed_repositories") == REPOSITORY_COUNT,
        "all_evaluable_rows_have_complete_candidate_panel": all(
            not row["worker_ok"] or row["candidate_attempts"] == CANDIDATES_PER_ROOT
            for row in root_rows
        ),
        "all_evaluable_authored_replays_exact": all(
            not row["worker_ok"] or row.get("authored_replay_ok") is True for row in root_rows
        ),
        "all_evaluable_branches_share_prestate": all(
            not row["worker_ok"] or row.get("same_pre_state_all_branches") is True
            for row in root_rows
        ),
        "manual_reconciliation_zero": True,
    }
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": config_sha,
        "targets_sha256": file_sha256(targetsp),
        "repositories": len(repository_rows),
        "frozen_roots": len(root_rows),
        "evaluable_roots": sum(row["worker_ok"] for row in root_rows),
        "repositories_with_any_evaluable_root": len(primary_rates),
        "candidate_invocations_requested": sum(row["candidate_invocations_requested"] for row in root_rows),
        "candidate_invocations_recorded": sum(row["candidate_attempts"] for row in root_rows),
        "primary": {
            "estimand": "equal-weight repository macro mean of candidate-relative Y-L0 root frequency",
            "complete_case_repository_rates": primary_rates,
            "complete_case_macro_mean": mean(primary_rates) if primary_rates else None,
            "complete_case_median": median(primary_rates) if primary_rates else None,
            "two_level_nonparametric_bootstrap_95ci": primary_ci,
            "bootstrap_interval_half_width": (primary_ci[1] - primary_ci[0]) / 2,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "frozen_frame_worst_case_bounds": [lower, upper],
            "repositories_with_nonzero_observed_frequency": sum(
                rate > 0 for rate in primary_rates
            ),
        },
        "mechanism_diverse_sensitivity": {
            "estimand": "equal-weight repository macro mean after mechanism-diverse panel restriction",
            "complete_case_repository_rates": robust_rates,
            "complete_case_macro_mean": mean(robust_rates) if robust_rates else None,
            "two_level_nonparametric_bootstrap_95ci": robust_ci,
            "frozen_frame_worst_case_bounds": [robust_lower, robust_upper],
        },
        "repositories_detail": repository_rows,
        "leave_one_repository_out": loo,
        "descriptive_structure": {
            "distinct_cross_head_pairs": len(pair_repositories),
            "pairs_recurring_in_at_least_two_repositories": sum(
                len(slugs) >= 2 for slugs in pair_repositories.values()
            ),
            "repositories_with_nonterminal_L0": sum(
                row["Y_nonterminal_L0_successes"] > 0 for row in repository_rows
            ),
            "repositories_with_cross_family_L0": sum(
                row["Y_cross_family_L0_successes"] > 0 for row in repository_rows
            ),
        },
        "integrity_checks": integrity,
        "integrity_passed": all(integrity.values()),
        "scientific_decision_threshold": None,
        "historical_38_repository_target_used_as_scientific_gate": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "interpretation": (
            "Report the observed frequency, bootstrap interval, repository distribution, "
            "and missingness bounds directly; do not convert the historical recruitment target "
            "or a design-stage effect threshold into a scientific validity claim."
        ),
    })
    atomic_json_dump(value, root / "analysis/summary.json")
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    analyze(parse_args())
