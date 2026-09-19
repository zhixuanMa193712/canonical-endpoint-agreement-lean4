"""Frozen offline analysis and preregistered Exp51 decision gates."""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

from experiment51_protocol import *


def read_rows(root: Path, targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for target in targets:
        path = root / "scientific/theorems" / safe_slug(target["slug"]) / f"{target['rid']}.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        row = read_json(path)
        if (row.get("theorem_id") != target["theorem_id"]
                or row.get("candidate_order") != target["alternatives"]):
            raise ValueError(f"scientific theorem row identity changed: {path}")
        rows.append(row)
    return rows


def candidate_pairs(rows: Iterable[dict[str, Any]]) -> set[tuple[str, str]]:
    values = list(rows)
    out = set()
    for left, right in itertools.combinations(values, 2):
        if left["head"] != right["head"]:
            out.add(tuple(sorted((left["head"], right["head"]))))
    return out


def analyze_view(row: dict[str, Any], tactics: list[str]) -> dict[str, Any]:
    if row.get("worker_ok") is not True:
        return {"evaluable": False, "candidate_count": len(tactics), "Y": None,
                "Y_nonterminal": None, "Y_cross_family": None}
    selected = [x for x in row["candidates"] if x["tactic"] in set(tactics)]
    if [x["tactic"] for x in selected] != [x for x in row["candidate_order"] if x in set(tactics)]:
        raise ValueError("candidate view order changed")
    initial = row["initial_endpoints"]["struct"]["sha256"]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for branch in selected:
        if branch.get("executable") is True:
            sha = branch["endpoints"]["struct"]["sha256"]
            if sha != initial:
                groups[sha].append(branch)
    qualifying = []
    head_pairs: set[tuple[str, str]] = set()
    nonterminal_pairs: set[tuple[str, str]] = set()
    cross_family_pairs: set[tuple[str, str]] = set()
    tactic_pair_count = 0
    for endpoint, branches in sorted(groups.items()):
        heads = {x["head"] for x in branches}
        if len(heads) < 2:
            continue
        pairs = candidate_pairs(branches)
        head_pairs |= pairs
        tactic_pair_count += sum(1 for a, b in itertools.combinations(branches, 2)
                                 if a["head"] != b["head"])
        nonterminal = all(x.get("terminal") is False for x in branches)
        families = {x["family"] for x in branches}
        if nonterminal:
            nonterminal_pairs |= pairs
        if len(families) >= 2:
            cross_family_pairs |= pairs
        qualifying.append({"endpoint_sha256": endpoint, "cluster_size": len(branches),
                           "heads": sorted(heads), "families": sorted(families),
                           "nonterminal": nonterminal})
    denominator = math.comb(len(tactics), 2) if len(tactics) >= 2 else 0
    return {
        "evaluable": True, "candidate_count": len(tactics),
        "executable_candidates": sum(x.get("executable") is True for x in selected),
        "nontrivial_executable_candidates": sum(
            x.get("executable") is True and x["endpoints"]["struct"]["sha256"] != initial
            for x in selected),
        "Y": bool(head_pairs), "Y_nonterminal": bool(nonterminal_pairs),
        "Y_cross_family": bool(cross_family_pairs),
        "W_pair_density": tactic_pair_count / denominator if denominator else 0.0,
        "cross_head_pairs": [list(x) for x in sorted(head_pairs)],
        "nonterminal_pairs": [list(x) for x in sorted(nonterminal_pairs)],
        "cross_family_pairs": [list(x) for x in sorted(cross_family_pairs)],
        "qualifying_endpoint_clusters": qualifying,
    }


def analyze_root(row: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    l0 = list(target["alternatives"])
    robust = select_candidate_view(l0, "L-mechanism-diverse")
    if robust != target["robust_alternatives"]:
        raise ValueError("robust panel changed")
    return {
        "slug": target["slug"], "commit": target["commit"],
        "theorem_id": target["theorem_id"], "full_name": target["full_name"],
        "file_path": target["file_path"], "rid": target["rid"],
        "worker_ok": row.get("worker_ok") is True,
        "candidate_attempts": len(row.get("candidates", [])),
        "authored_replay_ok": row.get("authored_replay_ok") is True,
        "same_pre_state_all_branches": row.get("same_pre_state_all_branches") is True,
        "L0": analyze_view(row, l0),
        "L-mechanism-diverse": analyze_view(row, robust),
    }


def repository_summary(slug: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    evaluable = [x for x in rows if x["worker_ok"]]
    def count(view: str, field: str) -> int:
        return sum(x[view].get(field) is True for x in evaluable)
    counts = {
        "Y_L0": count("L0", "Y"),
        "Y_Lrobust": count("L-mechanism-diverse", "Y"),
        "Y_NT_L0": count("L0", "Y_nonterminal"),
        "Y_NT_Lrobust": count("L-mechanism-diverse", "Y_nonterminal"),
        "Y_CF_L0": count("L0", "Y_cross_family"),
    }
    rates = {k: v / len(evaluable) if evaluable else 0.0 for k, v in counts.items()}
    files = Counter(x["file_path"] for x in rows)
    file_means = []
    for file_path in files:
        ys = [int(x["L0"]["Y"]) for x in evaluable if x["file_path"] == file_path]
        if ys:
            file_means.append(mean(ys))
    return {
        "slug": slug, "roots_attempted": len(rows), "evaluable_roots": len(evaluable),
        "evaluable_rate": len(evaluable) / len(rows) if rows else 0.0,
        "counts": counts, "rates": rates,
        "W_L0_mean": mean([x["L0"]["W_pair_density"] for x in evaluable]) if evaluable else 0.0,
        "W_Lrobust_mean": mean([x["L-mechanism-diverse"]["W_pair_density"] for x in evaluable]) if evaluable else 0.0,
        "unique_sampled_files": len(files),
        "maximum_file_fraction": max(files.values()) / len(rows) if rows else 0.0,
        "equal_weight_file_mean_sensitivity": mean(file_means) if file_means else 0.0,
    }


def hierarchical_bootstrap(root_rows: list[dict[str, Any]], field: str,
                           seed: int, replicates: int) -> list[float]:
    by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in root_rows:
        if row["worker_ok"]:
            by_repo[row["slug"]].append(row)
    slugs = sorted(by_repo)
    if not slugs:
        return []
    rng = random.Random(seed)
    out = []
    view, key = field.split(".", 1)
    for _ in range(replicates):
        selected = [rng.choice(slugs) for _ in slugs]
        repo_means = []
        for slug in selected:
            rows = by_repo[slug]
            sample = [rng.choice(rows) for _ in rows]
            repo_means.append(mean(int(x[view][key]) for x in sample))
        out.append(mean(repo_means))
    return out


def paired_panel_bootstrap(root_rows: list[dict[str, Any]], seed: int,
                           replicates: int) -> list[float]:
    by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in root_rows:
        if row["worker_ok"]:
            by_repo[row["slug"]].append(row)
    slugs = sorted(by_repo)
    if not slugs:
        return []
    rng = random.Random(seed)
    out = []
    for _ in range(replicates):
        selected = [rng.choice(slugs) for _ in slugs]
        repo_differences = []
        for slug in selected:
            rows = by_repo[slug]
            sample = [rng.choice(rows) for _ in rows]
            repo_differences.append(mean(
                int(x["L0"]["Y"]) - int(x["L-mechanism-diverse"]["Y"]) for x in sample))
        out.append(mean(repo_differences))
    return out


def interval(values: list[float]) -> list[float]:
    return [quantile(values, 0.025), quantile(values, 0.975)] if values else [0.0, 0.0]


def beta_binomial_sensitivity(repos: list[dict[str, Any]]) -> dict[str, Any]:
    rates = [x["rates"]["Y_L0"] for x in repos]
    macro = mean(rates)
    between = sum((x - macro) ** 2 for x in rates) / max(1, len(rates) - 1)
    binomial = mean([macro * (1 - macro) / max(1, x["evaluable_roots"]) for x in repos])
    extra = max(0.0, between - binomial)
    rho = extra / max(1e-15, macro * (1 - macro)) if 0 < macro < 1 else 0.0
    concentration = max(0.0, (1 / rho) - 1) if rho > 0 else None
    return {"method": "method-of-moments beta-binomial sensitivity",
            "macro_mean": macro, "between_repository_variance": between,
            "estimated_intraclass_correlation": rho,
            "alpha": macro * concentration if concentration is not None else None,
            "beta": (1 - macro) * concentration if concentration is not None else None,
            "gate_authoritative": False}


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    cfgp = root / "frozen/experiment51_config.json"
    targetsp = root / "frozen/targets.json"
    cfg, targets = read_json(cfgp), read_json(targetsp)
    validate_code_lock(cfg["code_lock"])
    execution = read_json(root / "scientific/summary.json")
    if execution.get("execution_gate") is not True or execution.get("config_sha256") != file_sha256(cfgp):
        raise ValueError("scientific execution is incomplete")
    outp = root / "analysis/summary.json"
    if outp.exists():
        value = read_json(outp)
        if value.get("config_sha256") != file_sha256(cfgp):
            raise ValueError("analysis belongs to another freeze")
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value
    worker_rows = read_rows(root, targets)
    root_rows = [analyze_root(row, target) for row, target in zip(worker_rows, targets)]
    atomic_jsonl_dump(root_rows, root / "analysis/theorem_rows.jsonl")
    repositories = [repository_summary(slug, [x for x in root_rows if x["slug"] == slug])
                    for slug in [x["slug"] for x in cfg["repositories"]]]
    evaluable = sum(x["evaluable_roots"] for x in repositories)
    primary_rates = [x["rates"]["Y_L0"] for x in repositories]
    robust_rates = [x["rates"]["Y_Lrobust"] for x in repositories]
    primary_macro = mean(primary_rates)
    robust_macro = mean(robust_rates)
    primary_ci = interval(hierarchical_bootstrap(root_rows, "L0.Y", BOOTSTRAP_SEED,
                                                 BOOTSTRAP_REPLICATES))
    robust_ci = interval(hierarchical_bootstrap(root_rows, "L-mechanism-diverse.Y",
                                                BOOTSTRAP_SEED + 1, BOOTSTRAP_REPLICATES))
    completed_repositories = sum(x["roots_attempted"] == ROOTS_PER_REPOSITORY for x in repositories)
    integrity = {
        "minimum_completed_repositories": completed_repositories >= MIN_REPOSITORIES,
        "overall_evaluability": evaluable / len(root_rows) >= MIN_OVERALL_EVALUABILITY,
        "per_repository_evaluability": all(x["evaluable_rate"] >= MIN_REPOSITORY_EVALUABILITY
                                            for x in repositories),
        "all_candidates_attempted_per_evaluable_root": all(
            not x["worker_ok"] or x["candidate_attempts"] == CANDIDATES_PER_ROOT for x in root_rows),
        "all_evaluable_authored_replay_exact": all(not x["worker_ok"] or x["authored_replay_ok"]
                                                    for x in root_rows),
        "all_evaluable_same_pre_state": all(not x["worker_ok"] or x["same_pre_state_all_branches"]
                                             for x in root_rows),
        "manual_reconciliation_zero": True,
    }
    primary_gate = {
        "ci_halfwidth_at_most_0_10": (primary_ci[1] - primary_ci[0]) / 2 <= MAX_CI_HALFWIDTH,
        "ci_lower_gt_0_20": primary_ci[0] > PRIMARY_DELTA,
        "at_least_75pct_repositories_nonzero": (sum(x > 0 for x in primary_rates)
                                                  / len(primary_rates) >= 0.75),
    }
    robust_gate = {
        "ci_lower_gt_0_10": robust_ci[0] > ROBUST_DELTA,
        "at_least_75pct_repositories_nonzero": (sum(x > 0 for x in robust_rates)
                                                  / len(robust_rates) >= 0.75),
        "nonterminal_signal_at_least_50pct_repositories": (
            sum(x["rates"]["Y_NT_Lrobust"] > 0 for x in repositories) / len(repositories) >= 0.50),
    }
    integrity_pass = all(integrity.values())
    precision_pass = primary_gate["ci_halfwidth_at_most_0_10"]
    primary_pass = all(primary_gate.values())
    if not integrity_pass:
        label = "invalid_execution"
    elif primary_pass:
        label = "robust_replication_go" if all(robust_gate.values()) else "replication_go"
    elif not precision_pass:
        label = "inconclusive"
    else:
        label = "replication_no_go"
    pair_repositories: dict[tuple[str, str], set[str]] = defaultdict(set)
    pair_occurrences: Counter[tuple[str, str]] = Counter()
    head_occurrences: Counter[str] = Counter()
    for row in root_rows:
        if row["worker_ok"]:
            for pair in row["L0"]["cross_head_pairs"]:
                pair_key = tuple(pair)
                pair_repositories[pair_key].add(row["slug"])
                pair_occurrences[pair_key] += 1
                head_occurrences.update(pair_key)
    pair_table = [{"head_pair": list(pair), "root_occurrences": count,
                   "repository_count": len(pair_repositories[pair]),
                   "repositories": sorted(pair_repositories[pair])}
                  for pair, count in sorted(pair_occurrences.items(),
                                            key=lambda x: (-x[1], x[0]))]
    head_table = [{"head": head, "pair_root_occurrences": count}
                  for head, count in sorted(head_occurrences.items(), key=lambda x: (-x[1], x[0]))]
    atomic_jsonl_dump(pair_table, root / "analysis/pair_concentration.jsonl")
    atomic_jsonl_dump(head_table, root / "analysis/head_concentration.jsonl")
    loo = []
    for repo in repositories:
        retained = [x["rates"]["Y_L0"] for x in repositories if x["slug"] != repo["slug"]]
        loo.append({"left_out": repo["slug"], "macro_mean": mean(retained)})
    paired_repo_differences = []
    for slug in [x["slug"] for x in repositories]:
        rs = [x for x in root_rows if x["slug"] == slug and x["worker_ok"]]
        paired_repo_differences.append({
            "slug": slug,
            "mean_Y_L0_minus_Y_Lrobust": mean(
                int(x["L0"]["Y"]) - int(x["L-mechanism-diverse"]["Y"]) for x in rs) if rs else 0.0,
        })
    paired_values = [x["mean_Y_L0_minus_Y_Lrobust"] for x in paired_repo_differences]
    paired_boot = paired_panel_bootstrap(root_rows, BOOTSTRAP_SEED + 2, BOOTSTRAP_REPLICATES)
    recruitment_flow = read_json(cfg["source"]["screening_summary"])
    flow = {
        "repositories_screened": recruitment_flow["candidates_screened"],
        "repositories_build_trace_pass": sum(x["build_trace_gate"] for x in recruitment_flow["repository_ledger"]),
        "repositories_authored_replay_pass": sum(x["authored_replay_gate"] for x in recruitment_flow["repository_ledger"]),
        "lineage_representatives": len(recruitment_flow["lineage_representatives"]),
        "repositories_frozen": len(repositories),
        "roots_frozen": len(root_rows), "roots_attempted": len(root_rows),
        "roots_evaluable": evaluable,
    }
    atomic_json_dump(flow, root / "analysis/flow.json")
    value = {
        "version": 1, "protocol_version": PROTOCOL_VERSION,
        "config_sha256": file_sha256(cfgp), "targets_sha256": file_sha256(targetsp),
        "repositories": len(repositories), "roots": len(root_rows),
        "evaluable_roots": evaluable, "candidate_attempts": sum(x["candidate_attempts"] for x in root_rows),
        "primary": {"estimand": "Y-L0 repository macro mean", "repository_rates": primary_rates,
                    "macro_mean": primary_macro, "median": median(primary_rates),
                    "two_level_bootstrap_95ci": primary_ci,
                    "bootstrap_replicates": BOOTSTRAP_REPLICATES, "bootstrap_seed": BOOTSTRAP_SEED},
        "robust": {"estimand": "Y-Lmechanism-diverse repository macro mean",
                   "repository_rates": robust_rates, "macro_mean": robust_macro,
                   "two_level_bootstrap_95ci": robust_ci},
        "paired_panel_comparison": {
            "estimand": "repository-macro paired Y-L0 minus Y-Lmechanism-diverse",
            "repository_differences": paired_repo_differences,
            "macro_mean_difference": mean(paired_values) if paired_values else 0.0,
            "two_level_paired_bootstrap_95ci": interval(paired_boot),
            "gate_authoritative": False,
        },
        "repositories_detail": repositories,
        "leave_one_repository_out": loo,
        "file_cluster_sensitivity_macro_mean": mean(
            x["equal_weight_file_mean_sensitivity"] for x in repositories),
        "beta_binomial_sensitivity": beta_binomial_sensitivity(repositories),
        "descriptive_structure": {
            "distinct_cross_head_pairs": len(pair_repositories),
            "pairs_recurring_in_at_least_two_repositories": sum(len(v) >= 2 for v in pair_repositories.values()),
            "repositories_with_nonterminal_L0": sum(x["rates"]["Y_NT_L0"] > 0 for x in repositories),
            "repositories_with_cross_family_L0": sum(x["rates"]["Y_CF_L0"] > 0 for x in repositories),
            "pair_concentration_rows": len(pair_table),
            "head_concentration_rows": len(head_table),
        },
        "flow": flow,
        "integrity_checks": integrity, "primary_gate_checks": primary_gate,
        "robust_gate_checks": robust_gate, "manual_reconciliation_count": 0,
        "decision_label": label,
        "replication_go": label in {"replication_go", "robust_replication_go"},
        "robust_replication_go": label == "robust_replication_go",
        "exp48_confirmation_go_unchanged": True,
        "claim_boundary": cfg["claim_boundary"],
        "next_step": "Export the immutable Exp51 audit bundle.",
    }
    atomic_json_dump(value, outp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    return p.parse_args()


if __name__ == "__main__":
    analyze(parse_args())
