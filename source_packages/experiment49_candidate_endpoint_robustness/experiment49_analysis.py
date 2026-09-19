"""Frozen offline analysis for Exp49 candidate and endpoint robustness."""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable, Sequence

from experiment49_protocol import (
    ARTIFACT_ROOT,
    BOOTSTRAP_REPLICATES,
    BOOTSTRAP_SEED,
    CANDIDATE_VIEWS,
    ENDPOINT_KINDS,
    MECHANICAL_FIX_ID,
    PROTOCOL_VERSION,
    RAREFACTION_BUDGETS,
    RAREFACTION_REPLICATES,
    ROBUSTNESS_GATE,
    atomic_json_dump,
    atomic_jsonl_dump,
    file_sha256,
    genealogy_for,
    quantile,
    read_json,
    safe_slug,
    select_candidate_view,
    stable_seed,
)


def _alternative_rows(worker: dict[str, Any], tactics: Sequence[str]) -> list[dict[str, Any]]:
    wanted = set(tactics)
    return [x for x in worker.get("executions", [])
            if x.get("source") == "alternative" and x.get("tactic") in wanted]


def _endpoint(ex: dict[str, Any], kind: str) -> dict[str, Any] | None:
    return (ex.get("endpoints", {}).get(kind) or {}).get("value")


def _head_pairs(rows: Iterable[dict[str, Any]]) -> set[tuple[str, str]]:
    heads = sorted({str(x["head"]) for x in rows})
    return {tuple(x) for x in itertools.combinations(heads, 2)}


def analyze_subset(worker: dict[str, Any], tactics: Sequence[str], kind: str) -> dict[str, Any]:
    rows = _alternative_rows(worker, tactics)
    initial = (worker.get("initial_endpoints", {}).get(kind) or {}).get("value")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    executable = []
    for ex in rows:
        if ex.get("executable") is not True:
            continue
        executable.append(ex)
        ep = _endpoint(ex, kind)
        if ep is not None and ep != initial:
            groups[str((ex.get("endpoints", {}).get(kind) or {}).get("sha256"))].append(ex)

    qualifying = {sha: xs for sha, xs in groups.items() if len({x["head"] for x in xs}) >= 2}
    cross_head_pairs: set[tuple[str, str]] = set()
    nonterminal_pairs: set[tuple[str, str]] = set()
    cross_family_pairs: set[tuple[str, str]] = set()
    for xs in qualifying.values():
        pairs = _head_pairs(xs)
        cross_head_pairs |= pairs
        if all(x.get("terminal") is False for x in xs):
            nonterminal_pairs |= pairs
        families = {str(x["family"]) for x in xs}
        if len(families) >= 2:
            cross_family_pairs |= pairs

    attempted_pairs = 0
    successful_pairs = 0
    for a, b in itertools.combinations(rows, 2):
        if a.get("head") == b.get("head"):
            continue
        attempted_pairs += 1
        if (a.get("executable") is True and b.get("executable") is True
                and _endpoint(a, kind) is not None and _endpoint(a, kind) != initial
                and _endpoint(a, kind) == _endpoint(b, kind)):
            successful_pairs += 1

    endpoint_counts = Counter(
        str((x.get("endpoints", {}).get(kind) or {}).get("sha256"))
        for x in executable if _endpoint(x, kind) is not None and _endpoint(x, kind) != initial
    )
    head_counts = Counter(str(x["head"]) for x in executable)
    total = sum(head_counts.values())
    entropy = -sum((n / total) * math.log(n / total) for n in head_counts.values()) if total else 0.0
    return {
        "candidate_attempts": len(rows),
        "executable_candidates": len(executable),
        "noninitial_executable_candidates": sum(endpoint_counts.values()),
        "distinct_noninitial_endpoints": len(endpoint_counts),
        "maximum_endpoint_cluster_size": max(endpoint_counts.values(), default=0),
        "effective_executable_heads": math.exp(entropy) if total else 0.0,
        "any_nontrivial_cross_head": bool(cross_head_pairs),
        "nonterminal_nontrivial_cross_head": bool(nonterminal_pairs),
        "cross_family_nontrivial_cross_head": bool(cross_family_pairs),
        "cross_head_pairs": [list(x) for x in sorted(cross_head_pairs)],
        "nonterminal_pairs": [list(x) for x in sorted(nonterminal_pairs)],
        "cross_family_pairs": [list(x) for x in sorted(cross_family_pairs)],
        "qualifying_endpoint_sha256": sorted(qualifying),
        "cross_head_pair_successes": successful_pairs,
        "cross_head_pair_attempts": attempted_pairs,
        "candidate_normalized_pair_density": successful_pairs / attempted_pairs if attempted_pairs else 0.0,
    }


def theorem_analysis(worker: dict[str, Any], library: Sequence[str]) -> dict[str, Any]:
    evaluable = bool(
        worker.get("worker_ok") is True
        and worker.get("theorem_start_ok") is True
        and worker.get("authored_replay_text_ok") is True
        and worker.get("authored_replay_struct_ok") is True
        and worker.get("complete_alternative_budget") is True
        and worker.get("same_pre_state_text_all_branches") is True
        and worker.get("same_pre_state_struct_all_branches") is True
    )
    out: dict[str, Any] = {
        "evaluable": evaluable,
        "gates": {
            key: worker.get(key) is True for key in (
                "theorem_start_ok", "authored_replay_text_ok", "authored_replay_struct_ok",
                "complete_alternative_budget", "same_pre_state_text_all_branches",
                "same_pre_state_struct_all_branches",
            )
        },
        "views": {},
    }
    for view in CANDIDATE_VIEWS:
        tactics = select_candidate_view(library, view)
        out["views"][view] = {
            "candidate_tactics": tactics,
            "candidate_count": len(tactics),
            "endpoints": {
                kind: analyze_subset(worker, tactics, kind) if evaluable else None
                for kind in ENDPOINT_KINDS
            },
        }
    return out


def _rates(rows: Sequence[dict[str, Any]], view: str, kind: str) -> dict[str, Any]:
    evaluable = [r for r in rows if r["analysis"]["evaluable"]]
    endpoint_rows = [r["analysis"]["views"][view]["endpoints"][kind] for r in evaluable]
    keys = {
        "primary": "any_nontrivial_cross_head",
        "nonterminal": "nonterminal_nontrivial_cross_head",
        "cross_family": "cross_family_nontrivial_cross_head",
    }
    counts = {name: sum(bool(x[field]) for x in endpoint_rows) for name, field in keys.items()}
    n = len(evaluable)
    pair_successes = sum(x["cross_head_pair_successes"] for x in endpoint_rows)
    pair_attempts = sum(x["cross_head_pair_attempts"] for x in endpoint_rows)
    return {
        "theorems_attempted": len(rows),
        "evaluable_theorems": n,
        "counts": counts,
        "rates": {k: value / n if n else 0.0 for k, value in counts.items()},
        "candidate_normalized_pair_density": pair_successes / pair_attempts if pair_attempts else 0.0,
        "pair_successes": pair_successes,
        "pair_attempts": pair_attempts,
        "mean_executable_candidates": mean(x["executable_candidates"] for x in endpoint_rows) if n else 0.0,
        "mean_distinct_noninitial_endpoints": mean(x["distinct_noninitial_endpoints"] for x in endpoint_rows) if n else 0.0,
        "mean_maximum_endpoint_cluster_size": mean(x["maximum_endpoint_cluster_size"] for x in endpoint_rows) if n else 0.0,
        "mean_effective_executable_heads": mean(x["effective_executable_heads"] for x in endpoint_rows) if n else 0.0,
    }


def repository_summary(slug: str, rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "slug": slug,
        "theorems_attempted": len(rows),
        "evaluable_theorems": sum(r["analysis"]["evaluable"] for r in rows),
        "gate_failures": Counter(
            gate for r in rows for gate, ok in r["analysis"]["gates"].items() if not ok
        ),
        "views": {
            view: {kind: _rates(rows, view, kind) for kind in ENDPOINT_KINDS}
            for view in CANDIDATE_VIEWS
        },
    }


def _bootstrap_repo_macro(values: Sequence[float], seed: int) -> list[float]:
    if not values:
        return [0.0, 0.0]
    rng = random.Random(seed)
    draws = [mean(values[rng.randrange(len(values))] for _ in values)
             for _ in range(BOOTSTRAP_REPLICATES)]
    draws.sort()
    return [quantile(draws, 0.025), quantile(draws, 0.975)]


def _macro(repo_summaries: Sequence[dict[str, Any]], view: str, kind: str) -> dict[str, Any]:
    rates = [float(r["views"][view][kind]["rates"]["primary"]) for r in repo_summaries]
    nonterminal = [float(r["views"][view][kind]["rates"]["nonterminal"]) for r in repo_summaries]
    cross_family = [float(r["views"][view][kind]["rates"]["cross_family"]) for r in repo_summaries]
    return {
        "repository_primary_rates": rates,
        "primary_repo_macro_mean": mean(rates) if rates else 0.0,
        "primary_repo_median": median(rates) if rates else 0.0,
        "primary_repo_bootstrap_95ci": _bootstrap_repo_macro(
            rates, stable_seed("bootstrap", view, kind, master=BOOTSTRAP_SEED)
        ),
        "nonterminal_repo_macro_mean": mean(nonterminal) if nonterminal else 0.0,
        "cross_family_repo_macro_mean": mean(cross_family) if cross_family else 0.0,
        "repositories_with_primary": sum(x > 0 for x in rates),
        "repositories_with_nonterminal": sum(x > 0 for x in nonterminal),
        "repositories_with_cross_family": sum(x > 0 for x in cross_family),
    }


def endpoint_confusion(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    tables: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        if not row["analysis"]["evaluable"]:
            continue
        a = row["analysis"]["views"]["L0"]["endpoints"]
        for left, right in (("raw", "text48"), ("text48", "struct")):
            tables[f"{left}_vs_{right}:root_primary"][(
                a[left]["any_nontrivial_cross_head"],
                a[right]["any_nontrivial_cross_head"],
            )] += 1
            tables[f"{left}_vs_{right}:root_nonterminal"][(
                a[left]["nonterminal_nontrivial_cross_head"],
                a[right]["nonterminal_nontrivial_cross_head"],
            )] += 1
        worker = row["worker"]
        alts = _alternative_rows(worker, row["analysis"]["views"]["L0"]["candidate_tactics"])
        for x, y in itertools.combinations(alts, 2):
            executable = x.get("executable") is True and y.get("executable") is True
            cross_head = x.get("head") != y.get("head")
            for left, right in (("raw", "text48"), ("text48", "struct")):
                initial_left = worker["initial_endpoints"][left]["value"]
                initial_right = worker["initial_endpoints"][right]["value"]
                left_equal = bool(executable and _endpoint(x, left) != initial_left
                                  and _endpoint(x, left) == _endpoint(y, left))
                right_equal = bool(executable and _endpoint(x, right) != initial_right
                                   and _endpoint(x, right) == _endpoint(y, right))
                tables[f"{left}_vs_{right}:all_candidate_pairs"][(left_equal, right_equal)] += 1
                if cross_head:
                    tables[f"{left}_vs_{right}:cross_head_candidate_pairs"][(left_equal, right_equal)] += 1
                    left_nonterminal = bool(left_equal and x.get("terminal") is False
                                            and y.get("terminal") is False)
                    right_nonterminal = bool(right_equal and x.get("terminal") is False
                                             and y.get("terminal") is False)
                    tables[f"{left}_vs_{right}:nonterminal_cross_head_pairs"][(
                        left_nonterminal, right_nonterminal,
                    )] += 1
    def named(table: Counter) -> dict[str, int]:
        return {
            "both_negative": table[(False, False)],
            "left_only": table[(True, False)],
            "right_only": table[(False, True)],
            "both_positive": table[(True, True)],
        }
    out: dict[str, Any] = {}
    for key, table in sorted(tables.items()):
        comparison, unit = key.split(":", 1)
        out.setdefault(comparison, {})[unit] = named(table)
    return out


def leave_one_head_out(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    heads = sorted({x["head"] for r in rows for x in r["worker"].get("executions", [])
                    if x.get("source") == "alternative"})
    result = {}
    for removed in heads:
        by_repo: dict[str, list[bool]] = defaultdict(list)
        for row in rows:
            if not row["analysis"]["evaluable"]:
                continue
            tactics = [x["tactic"] for x in row["worker"].get("executions", [])
                       if x.get("source") == "alternative" and x.get("head") != removed]
            by_repo[row["identity"]["slug"]].append(
                analyze_subset(row["worker"], tactics, "struct")["any_nontrivial_cross_head"]
            )
        rates = [sum(xs) / len(xs) if xs else 0.0 for _, xs in sorted(by_repo.items())]
        result[removed] = {
            "repository_primary_rates": rates,
            "primary_repo_macro_mean": mean(rates) if rates else 0.0,
            "repositories_with_primary": sum(x > 0 for x in rates),
        }
    return result


def pair_head_concentration(rows: Sequence[dict[str, Any]], view: str, kind: str) -> dict[str, Any]:
    pair_counts: Counter = Counter()
    pair_repos: dict[tuple[str, str], set[str]] = defaultdict(set)
    head_counts: Counter = Counter()
    for row in rows:
        if not row["analysis"]["evaluable"]:
            continue
        pairs = [tuple(x) for x in row["analysis"]["views"][view]["endpoints"][kind]["cross_head_pairs"]]
        for pair in pairs:
            pair_counts[pair] += 1
            pair_repos[pair].add(row["identity"]["slug"])
            for head in pair:
                head_counts[head] += 1
    def concentration(counts: Counter) -> dict[str, Any]:
        total = sum(counts.values())
        shares = [n / total for n in counts.values()] if total else []
        return {
            "occurrences": total,
            "distinct": len(counts),
            "herfindahl": sum(x * x for x in shares),
            "top_share": max(shares, default=0.0),
        }
    return {
        "pairs": concentration(pair_counts),
        "heads": concentration(head_counts),
        "pairs_recurring_in_at_least_two_repositories": sum(len(x) >= 2 for x in pair_repos.values()),
        "pair_theorem_counts": [
            {"pair": list(pair), "theorems": n,
             "repositories": sorted(pair_repos[pair]),
             "repository_count": len(pair_repos[pair])}
            for pair, n in sorted(pair_counts.items())
        ],
    }


def rarefaction(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for budget in RAREFACTION_BUDGETS:
        macro_draws = []
        for rep in range(RAREFACTION_REPLICATES):
            by_repo: dict[str, list[bool]] = defaultdict(list)
            for row in rows:
                if not row["analysis"]["evaluable"]:
                    continue
                library = row["analysis"]["views"]["L0"]["candidate_tactics"]
                rng = random.Random(stable_seed("rarefaction", budget, rep,
                                                row["identity"]["slug"],
                                                row["identity"]["theorem_id"],
                                                row["identity"]["full_name"]))
                tactics = rng.sample(library, budget)
                signal = analyze_subset(row["worker"], tactics, "struct")["any_nontrivial_cross_head"]
                by_repo[row["identity"]["slug"]].append(signal)
            repo_rates = [sum(xs) / len(xs) if xs else 0.0 for _, xs in sorted(by_repo.items())]
            macro_draws.append(mean(repo_rates) if repo_rates else 0.0)
        macro_draws.sort()
        out[str(budget)] = {
            "replicates": RAREFACTION_REPLICATES,
            "struct_primary_repo_macro_mean": mean(macro_draws),
            "subset_95_interval": [quantile(macro_draws, 0.025), quantile(macro_draws, 0.975)],
        }
    return out


def robustness_label(macros: dict[str, Any]) -> dict[str, Any]:
    primary = macros[ROBUSTNESS_GATE["primary_view"]]["struct"]
    rp = primary["repositories_with_primary"]
    rn = primary["repositories_with_nonterminal"]
    if (rp >= ROBUSTNESS_GATE["green_min_repositories_with_primary"]
            and rn >= ROBUSTNESS_GATE["green_min_repositories_with_nonterminal"]):
        label = "Green"
    elif rp >= ROBUSTNESS_GATE["amber_min_repositories_with_primary"]:
        label = "Amber"
    else:
        label = "Red"
    return {"label": label, "frozen_gate": ROBUSTNESS_GATE, "observed": primary}


def load_rows(root: Path) -> list[dict[str, Any]]:
    return [read_json(p) for p in sorted((root / "validation/theorems").glob("*/*.json"))]


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    cfgp = root / "frozen/experiment49_config.json"
    cfg = read_json(cfgp)
    if (cfg.get("protocol_version") != PROTOCOL_VERSION
            or cfg.get("mechanical_fix_id") != MECHANICAL_FIX_ID):
        raise ValueError("wrong Exp49 config")
    validation = read_json(root / "validation/execution_summary.json")
    if validation.get("execution_complete") is not True:
        raise ValueError("Exp49 analysis requires completed 96-root validation")
    rows = load_rows(root)
    if len(rows) != int(cfg["expected_validation_roots"]):
        raise ValueError("Exp49 validation row count changed")
    repos: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        repos[row["identity"]["slug"]].append(row)
    repo_summaries = [repository_summary(slug, repos[slug]) for slug in cfg["confirmation_repositories"]]
    macros = {
        view: {kind: _macro(repo_summaries, view, kind) for kind in ENDPOINT_KINDS}
        for view in CANDIDATE_VIEWS
    }
    out = {
        "version": 1,
        "protocol_version": PROTOCOL_VERSION,
        "study_role": "post-hoc robustness and endpoint construct validation; not independent confirmation",
        "config_sha256": file_sha256(cfgp),
        "theorem_rows": len(rows),
        "evaluable_rows": sum(r["analysis"]["evaluable"] for r in rows),
        "repository_summaries": repo_summaries,
        "macros": macros,
        "endpoint_confusion": endpoint_confusion(rows),
        "pair_head_concentration": {
            view: {kind: pair_head_concentration(rows, view, kind) for kind in ENDPOINT_KINDS}
            for view in CANDIDATE_VIEWS
        },
        "leave_one_head_out_struct": leave_one_head_out(rows),
        "rarefaction_struct": rarefaction(rows),
        "robustness": robustness_label(macros),
        "exp48_bridge": validation["exp48_bridge"],
        "claim_boundary": [
            "same frozen 96 roots and frozen alternatives as Exp48",
            "strict state-conditioned one-step endpoint agreement only",
            "no tactic interchangeability, proof-term equality, runtime equivalence, or prover-improvement claim",
        ],
    }
    outdir = root / "analysis"
    atomic_json_dump(out, outdir / "summary.json")
    atomic_jsonl_dump(repo_summaries, outdir / "repository_summaries.jsonl")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    return p.parse_args()


if __name__ == "__main__":
    analyze(parse_args())
