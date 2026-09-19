"""Analysis for Exp48 live-TacticInfo counterfactual equivalence."""
from __future__ import annotations

import itertools
import random
from collections import defaultdict
from statistics import mean, median
from typing import Any, Iterable

from experiment48_protocol import BOOTSTRAP_REPLICATES, BOOTSTRAP_SEED


def _pairs(values: Iterable[str]) -> set[tuple[str, str]]:
    xs = sorted(set(values))
    return {tuple(sorted(p)) for p in itertools.combinations(xs, 2)}


def _group_equivalent(executions: list[dict[str, Any]], initial_endpoint: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ex in executions:
        if ex.get("source") != "alternative" or ex.get("executable") is not True:
            continue
        if ex.get("endpoint") == initial_endpoint:
            continue
        sha = ex.get("endpoint_sha256")
        if sha:
            groups[str(sha)].append(ex)
    return groups


def theorem_summary(worker: dict[str, Any]) -> dict[str, Any]:
    executions = list(worker.get("executions") or [])
    alternatives = [x for x in executions if x.get("source") == "alternative"]
    authored = next((x for x in executions if x.get("source") == "authored"), None)
    evaluable = bool(
        worker.get("theorem_start_ok") is True
        and worker.get("authored_replay_ok") is True
        and worker.get("complete_alternative_budget") is True
        and worker.get("same_pre_state_all_branches") is True
    )
    initial = worker.get("initial_endpoint")
    groups = _group_equivalent(alternatives, initial) if evaluable else {}

    cross_head_pairs: set[tuple[str, str]] = set()
    nonterminal_pairs: set[tuple[str, str]] = set()
    cross_family_pairs: set[tuple[str, str]] = set()
    qualifying_endpoints = []
    for sha, rows in groups.items():
        heads = {str(r.get("head")) for r in rows}
        families = {str(r.get("family")) for r in rows}
        if len(heads) >= 2:
            ps = _pairs(heads)
            cross_head_pairs |= ps
            qualifying_endpoints.append(sha)
            if all(r.get("terminal") is False for r in rows):
                nonterminal_pairs |= ps
            if len(families) >= 2:
                cross_family_pairs |= ps

    authored_anchor_pairs: set[tuple[str, str]] = set()
    if evaluable and authored and authored.get("executable") is True and authored.get("endpoint") != initial:
        for alt in alternatives:
            if alt.get("executable") is not True:
                continue
            if alt.get("endpoint") == authored.get("endpoint") and alt.get("head") != authored.get("head"):
                authored_anchor_pairs.add(tuple(sorted((str(authored.get("head")), str(alt.get("head"))))))

    return {
        "evaluable": evaluable,
        "theorem_start_ok": worker.get("theorem_start_ok") is True,
        "authored_replay_ok": worker.get("authored_replay_ok") is True,
        "complete_alternative_budget": worker.get("complete_alternative_budget") is True,
        "same_pre_state_all_branches": worker.get("same_pre_state_all_branches") is True,
        "pre_goal_count": worker.get("pre_goal_count"),
        "executable_alternatives": sum(x.get("executable") is True for x in alternatives),
        "nontrivial_executable_alternatives": sum(x.get("executable") is True and x.get("endpoint") != initial for x in alternatives),
        "any_nontrivial_cross_head": bool(cross_head_pairs),
        "authored_anchor_cross_head": bool(authored_anchor_pairs),
        "nonterminal_nontrivial_cross_head": bool(nonterminal_pairs),
        "cross_family_nontrivial_cross_head": bool(cross_family_pairs),
        "cross_head_pairs": [list(p) for p in sorted(cross_head_pairs)],
        "authored_anchor_pairs": [list(p) for p in sorted(authored_anchor_pairs)],
        "nonterminal_pairs": [list(p) for p in sorted(nonterminal_pairs)],
        "cross_family_pairs": [list(p) for p in sorted(cross_family_pairs)],
        "qualifying_endpoint_sha256": sorted(set(qualifying_endpoints)),
    }


def repository_summary(slug: str, theorem_rows: list[dict[str, Any]]) -> dict[str, Any]:
    analyses = [r["analysis"] for r in theorem_rows]
    attempted = len(analyses)
    evaluable = sum(a["evaluable"] for a in analyses)
    counts = {
        "primary": sum(a["evaluable"] and a["any_nontrivial_cross_head"] for a in analyses),
        "authored_anchor": sum(a["evaluable"] and a["authored_anchor_cross_head"] for a in analyses),
        "nonterminal": sum(a["evaluable"] and a["nonterminal_nontrivial_cross_head"] for a in analyses),
        "cross_family": sum(a["evaluable"] and a["cross_family_nontrivial_cross_head"] for a in analyses),
    }
    rates = {k: (v / evaluable if evaluable else 0.0) for k, v in counts.items()}
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    for a in analyses:
        if not a["evaluable"]:
            continue
        for pair in a["cross_head_pairs"]:
            pair_counts[tuple(pair)] += 1
    return {
        "slug": slug,
        "theorems_attempted": attempted,
        "evaluable_theorems": evaluable,
        "theorem_start_failures": sum(not a["theorem_start_ok"] for a in analyses),
        "authored_replay_failures": sum(a["theorem_start_ok"] and not a["authored_replay_ok"] for a in analyses),
        "candidate_budget_failures": sum(not a["complete_alternative_budget"] for a in analyses),
        "branch_prestate_failures": sum(not a["same_pre_state_all_branches"] for a in analyses),
        "counts": counts,
        "rates": rates,
        "distinct_cross_head_pairs": len(pair_counts),
        "cross_head_pair_theorem_counts": [
            {"pair": list(pair), "theorems": n} for pair, n in sorted(pair_counts.items())
        ],
    }


def bootstrap_repo_macro(rates: list[float], seed: int = BOOTSTRAP_SEED, reps: int = BOOTSTRAP_REPLICATES) -> list[float]:
    if not rates:
        return [0.0, 0.0]
    rng = random.Random(seed)
    n = len(rates)
    draws = []
    for _ in range(reps):
        draws.append(mean(rates[rng.randrange(n)] for _ in range(n)))
    draws.sort()
    lo_idx = max(0, min(reps - 1, int(0.025 * reps)))
    hi_idx = max(0, min(reps - 1, int(0.975 * reps) - 1))
    return [draws[lo_idx], draws[hi_idx]]


def phase_summary(phase: str, repo_summaries: list[dict[str, Any]], confirmation_gate: dict[str, Any], strong_go: dict[str, Any]) -> dict[str, Any]:
    rates = [float(r["rates"]["primary"]) for r in repo_summaries]
    pair_repos: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in repo_summaries:
        for row in r["cross_head_pair_theorem_counts"]:
            pair_repos[tuple(row["pair"])].add(r["slug"])
    recurring = [
        {"pair": list(pair), "repositories": sorted(repos), "repository_count": len(repos)}
        for pair, repos in sorted(pair_repos.items())
        if len(repos) >= 2
    ]
    ci = bootstrap_repo_macro(rates)
    out = {
        "phase": phase,
        "repositories": len(repo_summaries),
        "repository_summaries": repo_summaries,
        "primary_repo_macro_mean": mean(rates) if rates else 0.0,
        "primary_repo_median": median(rates) if rates else 0.0,
        "primary_repo_bootstrap_95ci": ci,
        "repositories_with_nonzero_primary": sum(r["counts"]["primary"] > 0 for r in repo_summaries),
        "repositories_with_nonterminal_signal": sum(r["counts"]["nonterminal"] > 0 for r in repo_summaries),
        "repositories_with_cross_family_signal": sum(r["counts"]["cross_family"] > 0 for r in repo_summaries),
        "distinct_cross_head_pairs": len(pair_repos),
        "head_pairs_replicating_in_at_least_two_repositories": len(recurring),
        "recurring_head_pairs": recurring,
    }
    if phase == "confirmation":
        checks = {
            "repository_count": len(repo_summaries) == int(confirmation_gate["repositories"]),
            "minimum_evaluable_theorems_each": all(
                r["evaluable_theorems"] >= int(confirmation_gate["minimum_evaluable_theorems_each"])
                for r in repo_summaries
            ),
            "minimum_repositories_with_nonzero_primary": out["repositories_with_nonzero_primary"] >= int(confirmation_gate["minimum_repositories_with_nonzero_primary"]),
            "repo_bootstrap_95ci_primary_lower_strictly_positive": ci[0] > 0.0,
            "minimum_distinct_cross_head_pairs": out["distinct_cross_head_pairs"] >= int(confirmation_gate["minimum_distinct_cross_head_pairs"]),
            "minimum_repositories_with_nonterminal_signal": out["repositories_with_nonterminal_signal"] >= int(confirmation_gate["minimum_repositories_with_nonterminal_signal"]),
        }
        out["confirmation_checks"] = checks
        out["confirmation_go"] = all(checks.values())
        strong_checks = {
            "minimum_repositories_with_cross_family_signal": out["repositories_with_cross_family_signal"] >= int(strong_go["minimum_repositories_with_cross_family_signal"]),
            "minimum_head_pairs_replicating_in_at_least_two_repositories": out["head_pairs_replicating_in_at_least_two_repositories"] >= int(strong_go["minimum_head_pairs_replicating_in_at_least_two_repositories"]),
        }
        out["strong_go_checks"] = strong_checks
        out["strong_go"] = all(strong_checks.values())
    return out
