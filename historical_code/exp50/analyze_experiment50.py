"""Frozen exact comparison and final gate for Exp50 independent re-execution."""
from __future__ import annotations

import argparse
import itertools
import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

from experiment50_protocol import *


def pairs(values: Iterable[str]) -> set[tuple[str, str]]:
    xs = sorted(set(values))
    return {tuple(sorted(p)) for p in itertools.combinations(xs, 2)}


def branch_map(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {x["tactic"]: x for x in row.get("candidates", [])}


def endpoint_sha(branch: dict[str, Any], kind: str) -> str | None:
    if branch.get("executable") is not True:
        return None
    return branch["endpoints"][kind]["sha256"]


def compact_signature(branch: dict[str, Any]) -> dict[str, Any]:
    out = {"executable": branch.get("executable") is True}
    if out["executable"]:
        out.update({"goal_count": branch.get("goal_count"), "terminal": branch.get("terminal"),
                    "raw": endpoint_sha(branch, "raw"),
                    "text48": endpoint_sha(branch, "text48"),
                    "struct": endpoint_sha(branch, "struct")})
    return out


def full_row_signature(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "worker_ok": row.get("worker_ok") is True,
        "initial": {k: row["initial_endpoints"][k]["sha256"] for k in ("raw", "text48", "struct")},
        "original": {k: row["original_authored_endpoints"][k]["sha256"] for k in ("raw", "text48", "struct")},
        "authored": compact_signature(row["authored"]),
        "candidates": {k: compact_signature(v) for k, v in sorted(branch_map(row).items())},
    }


def m0_theorem_summary(row: dict[str, Any]) -> dict[str, Any]:
    alternatives = list(row.get("candidates", []))
    initial_sha = row["initial_endpoints"]["text48"]["exp48_legacy_sha256"]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    evaluable = row.get("worker_ok") is True
    if evaluable:
        for branch in alternatives:
            if branch.get("executable") is not True:
                continue
            sha = branch["endpoints"]["text48"]["exp48_legacy_sha256"]
            if sha != initial_sha:
                groups[sha].append(branch)
    cross_head: set[tuple[str, str]] = set()
    nonterminal: set[tuple[str, str]] = set()
    cross_family: set[tuple[str, str]] = set()
    qualifying = []
    for sha, rows in groups.items():
        heads = {str(x["head"]) for x in rows}
        families = {str(x["family"]) for x in rows}
        if len(heads) >= 2:
            ps = pairs(heads)
            cross_head |= ps
            qualifying.append(sha)
            if all(x.get("terminal") is False for x in rows):
                nonterminal |= ps
            if len(families) >= 2:
                cross_family |= ps
    authored_pairs: set[tuple[str, str]] = set()
    authored = row.get("authored") or {}
    if evaluable and authored.get("executable") is True:
        authored_sha = authored["endpoints"]["text48"]["exp48_legacy_sha256"]
        if authored_sha != initial_sha:
            for alt in alternatives:
                if (alt.get("executable") is True
                        and alt["endpoints"]["text48"]["exp48_legacy_sha256"] == authored_sha
                        and alt.get("head") != authored.get("head")):
                    authored_pairs.add(tuple(sorted((str(authored.get("head")), str(alt.get("head"))))))
    return {
        "evaluable": evaluable,
        "theorem_start_ok": row.get("target_found") is True and row.get("trace_root_match") is True
                              and row.get("pre_goal_count") == 1,
        "authored_replay_ok": row.get("authored_replay_ok") is True,
        "complete_alternative_budget": row.get("complete_candidate_order") is True
                                        and len(alternatives) == CANDIDATES_PER_ROOT,
        "same_pre_state_all_branches": row.get("same_pre_state_all_branches") is True,
        "pre_goal_count": row.get("pre_goal_count"),
        "executable_alternatives": sum(x.get("executable") is True for x in alternatives),
        "nontrivial_executable_alternatives": sum(
            x.get("executable") is True
            and x["endpoints"]["text48"]["exp48_legacy_sha256"] != initial_sha
            for x in alternatives),
        "any_nontrivial_cross_head": bool(cross_head),
        "authored_anchor_cross_head": bool(authored_pairs),
        "nonterminal_nontrivial_cross_head": bool(nonterminal),
        "cross_family_nontrivial_cross_head": bool(cross_family),
        "cross_head_pairs": [list(x) for x in sorted(cross_head)],
        "authored_anchor_pairs": [list(x) for x in sorted(authored_pairs)],
        "nonterminal_pairs": [list(x) for x in sorted(nonterminal)],
        "cross_family_pairs": [list(x) for x in sorted(cross_family)],
        "qualifying_endpoint_sha256": sorted(set(qualifying)),
    }


def repository_summary(slug: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    analyses = [x["reconstructed_analysis"] for x in rows]
    attempted = len(analyses)
    evaluable = sum(x["evaluable"] for x in analyses)
    counts = {
        "primary": sum(x["evaluable"] and x["any_nontrivial_cross_head"] for x in analyses),
        "authored_anchor": sum(x["evaluable"] and x["authored_anchor_cross_head"] for x in analyses),
        "nonterminal": sum(x["evaluable"] and x["nonterminal_nontrivial_cross_head"] for x in analyses),
        "cross_family": sum(x["evaluable"] and x["cross_family_nontrivial_cross_head"] for x in analyses),
    }
    rates = {k: v / evaluable if evaluable else 0.0 for k, v in counts.items()}
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    for analysis in analyses:
        if analysis["evaluable"]:
            for pair in analysis["cross_head_pairs"]:
                pair_counts[tuple(pair)] += 1
    return {
        "slug": slug, "theorems_attempted": attempted, "evaluable_theorems": evaluable,
        "theorem_start_failures": sum(not x["theorem_start_ok"] for x in analyses),
        "authored_replay_failures": sum(x["theorem_start_ok"] and not x["authored_replay_ok"] for x in analyses),
        "candidate_budget_failures": sum(not x["complete_alternative_budget"] for x in analyses),
        "branch_prestate_failures": sum(not x["same_pre_state_all_branches"] for x in analyses),
        "counts": counts, "rates": rates, "distinct_cross_head_pairs": len(pair_counts),
        "cross_head_pair_theorem_counts": [
            {"pair": list(pair), "theorems": count} for pair, count in sorted(pair_counts.items())],
    }


def bootstrap_repo_macro(rates: list[float]) -> list[float]:
    rng = random.Random(EXP48_BOOTSTRAP_SEED)
    n = len(rates)
    draws = sorted(mean(rates[rng.randrange(n)] for _ in range(n))
                   for _ in range(EXP48_BOOTSTRAP_REPLICATES))
    lo = max(0, min(EXP48_BOOTSTRAP_REPLICATES - 1,
                    int(0.025 * EXP48_BOOTSTRAP_REPLICATES)))
    hi = max(0, min(EXP48_BOOTSTRAP_REPLICATES - 1,
                    int(0.975 * EXP48_BOOTSTRAP_REPLICATES) - 1))
    return [draws[lo], draws[hi]]


def confirmation_summary(repo_rows: list[dict[str, Any]], c48: dict[str, Any]) -> dict[str, Any]:
    rates = [float(x["rates"]["primary"]) for x in repo_rows]
    pair_repos: dict[tuple[str, str], set[str]] = defaultdict(set)
    for repo in repo_rows:
        for row in repo["cross_head_pair_theorem_counts"]:
            pair_repos[tuple(row["pair"])].add(repo["slug"])
    recurring = [{"pair": list(pair), "repositories": sorted(repos),
                  "repository_count": len(repos)}
                 for pair, repos in sorted(pair_repos.items()) if len(repos) >= 2]
    ci = bootstrap_repo_macro(rates)
    out: dict[str, Any] = {
        "phase": "confirmation", "repositories": len(repo_rows),
        "repository_summaries": repo_rows,
        "primary_repo_macro_mean": mean(rates), "primary_repo_median": median(rates),
        "primary_repo_bootstrap_95ci": ci,
        "repositories_with_nonzero_primary": sum(x["counts"]["primary"] > 0 for x in repo_rows),
        "repositories_with_nonterminal_signal": sum(x["counts"]["nonterminal"] > 0 for x in repo_rows),
        "repositories_with_cross_family_signal": sum(x["counts"]["cross_family"] > 0 for x in repo_rows),
        "distinct_cross_head_pairs": len(pair_repos),
        "head_pairs_replicating_in_at_least_two_repositories": len(recurring),
        "recurring_head_pairs": recurring,
    }
    gate = c48["confirmation_gate"]
    checks = {
        "repository_count": len(repo_rows) == int(gate["repositories"]),
        "minimum_evaluable_theorems_each": all(
            x["evaluable_theorems"] >= int(gate["minimum_evaluable_theorems_each"]) for x in repo_rows),
        "minimum_repositories_with_nonzero_primary": out["repositories_with_nonzero_primary"] >= int(gate["minimum_repositories_with_nonzero_primary"]),
        "repo_bootstrap_95ci_primary_lower_strictly_positive": ci[0] > 0.0,
        "minimum_distinct_cross_head_pairs": out["distinct_cross_head_pairs"] >= int(gate["minimum_distinct_cross_head_pairs"]),
        "minimum_repositories_with_nonterminal_signal": out["repositories_with_nonterminal_signal"] >= int(gate["minimum_repositories_with_nonterminal_signal"]),
    }
    out["confirmation_checks"] = checks
    out["confirmation_go"] = all(checks.values())
    strong = c48["strong_go_diagnostics"]
    strong_checks = {
        "minimum_repositories_with_cross_family_signal": out["repositories_with_cross_family_signal"] >= int(strong["minimum_repositories_with_cross_family_signal"]),
        "minimum_head_pairs_replicating_in_at_least_two_repositories": out["head_pairs_replicating_in_at_least_two_repositories"] >= int(strong["minimum_head_pairs_replicating_in_at_least_two_repositories"]),
    }
    out["strong_go_checks"] = strong_checks
    out["strong_go"] = all(strong_checks.values())
    return out


def add_mismatch(ledger: list[dict[str, Any]], target: dict[str, Any], category: str,
                 expected: Any, observed: Any, mode: str = "M0", tactic: str | None = None) -> None:
    ledger.append({"slug": target["slug"], "theorem_id": target["theorem_id"],
                   "full_name": target["full_name"], "mode": mode, "tactic": tactic,
                   "category": category, "expected": expected, "observed": observed})


def compare_source(target: dict[str, Any], m0: dict[str, Any], ledger: list[dict[str, Any]]) -> dict[str, Any]:
    e48 = read_json(target["source_exp48_row"])
    raw48 = read_json(target["source_exp48_raw"])
    e49 = read_json(target["source_exp49_row"])
    raw49 = read_json(target["source_exp49_raw"])
    start = len(ledger)
    if file_sha256(target["source_exp48_row"]) != target["source_exp48_row_sha256"]:
        add_mismatch(ledger, target, "exp48_row_hash", target["source_exp48_row_sha256"],
                     file_sha256(target["source_exp48_row"]))
    if file_sha256(target["source_exp48_raw"]) != target["source_exp48_raw_sha256"]:
        add_mismatch(ledger, target, "exp48_raw_row_hash", target["source_exp48_raw_sha256"],
                     file_sha256(target["source_exp48_raw"]))
    if file_sha256(target["source_exp49_row"]) != target["source_exp49_row_sha256"]:
        add_mismatch(ledger, target, "exp49_row_hash", target["source_exp49_row_sha256"],
                     file_sha256(target["source_exp49_row"]))
    if file_sha256(target["source_exp49_raw"]) != target["source_exp49_raw_sha256"]:
        add_mismatch(ledger, target, "exp49_raw_row_hash", target["source_exp49_raw_sha256"],
                     file_sha256(target["source_exp49_raw"]))

    old48 = {x["tactic"]: x for x in e48["worker"]["executions"] if x["source"] == "alternative"}
    old48_raw = {x["tactic"]: x for x in raw48["alternatives"]}
    old49 = {x["tactic"]: x for x in e49["worker"]["executions"] if x["source"] == "alternative"}
    old49_raw = {x["tactic"]: x for x in raw49["alternatives"]}
    new = branch_map(m0)
    agreement48, agreement49 = empty_agreement(), empty_agreement()
    if set(new) != set(old48) or set(new) != set(old49):
        add_mismatch(ledger, target, "candidate_set", sorted(old48), sorted(new))
    if m0.get("candidate_order") != target["alternatives"]:
        add_mismatch(ledger, target, "exp48_candidate_order", target["alternatives"],
                     m0.get("candidate_order"))
    for tactic in sorted(set(new) | set(old48) | set(old49)):
        if tactic not in new or tactic not in old48 or tactic not in old49:
            continue
        branch, b48, b49 = new[tactic], old48[tactic], old49[tactic]
        observed48 = {"executable": branch.get("executable") is True,
                      "raw": branch.get("endpoints", {}).get("raw", {}).get("state", {}).get("sha256"),
                      "text48": branch.get("endpoints", {}).get("text48", {}).get("exp48_legacy_sha256")}
        expected48 = {"executable": b48.get("executable") is True,
                      "raw": text_sha256(str(old48_raw[tactic].get("stateAfter"))),
                      "text48": b48.get("endpoint_sha256")}
        add_agreement(agreement48, expected48, observed48, has_strict=False)
        observed49 = {"executable": branch.get("executable") is True,
                      **{k: branch.get("endpoints", {}).get(k, {}).get("sha256")
                         for k in ("raw", "text48", "struct")}}
        expected49 = {"executable": b49.get("executable") is True,
                      **{k: b49.get("endpoints", {}).get(k, {}).get("sha256")
                         for k in ("raw", "text48", "struct")}}
        add_agreement(agreement49, expected49, observed49)
        if (branch.get("executable") is True) != (old48_raw[tactic].get("executable") is True):
            add_mismatch(ledger, target, "exp48_raw_executable_status",
                         old48_raw[tactic].get("executable"), branch.get("executable"), tactic=tactic)
        if (branch.get("executable") is True) != (old49_raw[tactic].get("executable") is True):
            add_mismatch(ledger, target, "exp49_raw_executable_status",
                         old49_raw[tactic].get("executable"), branch.get("executable"), tactic=tactic)
        if (branch.get("executable") is True) != (b48.get("executable") is True):
            add_mismatch(ledger, target, "exp48_executable_status", b48.get("executable"), branch.get("executable"), tactic=tactic)
        if (branch.get("executable") is True) != (b49.get("executable") is True):
            add_mismatch(ledger, target, "exp49_executable_status", b49.get("executable"), branch.get("executable"), tactic=tactic)
        if branch.get("executable") is True and b48.get("executable") is True:
            observed = {"endpoint_sha256": branch["endpoints"]["text48"]["exp48_legacy_sha256"],
                        "goal_count": branch["goal_count"], "terminal": branch["terminal"],
                        "no_op": branch["no_op"]["text48"]}
            expected = {k: b48.get(k) for k in ("endpoint_sha256", "goal_count", "terminal", "no_op")}
            if observed != expected:
                add_mismatch(ledger, target, "exp48_text_endpoint", expected, observed, tactic=tactic)
            raw_expected = {"state_sha256": text_sha256(str(old48_raw[tactic]["stateAfter"])),
                            "goal_count": old48_raw[tactic]["goalCount"],
                            "terminal": old48_raw[tactic]["terminal"]}
            raw_observed = {"state_sha256": branch["endpoints"]["raw"]["state"]["sha256"],
                            "goal_count": branch["goal_count"], "terminal": branch["terminal"]}
            if raw_expected != raw_observed:
                add_mismatch(ledger, target, "exp48_raw_endpoint", raw_expected, raw_observed, tactic=tactic)
        if branch.get("executable") is True and b49.get("executable") is True:
            observed = {k: branch["endpoints"][k]["sha256"] for k in ("raw", "text48", "struct")}
            expected = {k: b49["endpoints"][k]["sha256"] for k in ("raw", "text48", "struct")}
            if observed != expected:
                add_mismatch(ledger, target, "exp49_endpoint", expected, observed, tactic=tactic)
            raw49_expected = {
                "raw_state_sha256": text_sha256(str(old49_raw[tactic]["stateAfter"])),
                "strict_state_sha256": text_sha256(str(old49_raw[tactic]["strictStateAfter"])),
                "goal_count": old49_raw[tactic]["goalCount"],
                "terminal": old49_raw[tactic]["terminal"],
            }
            raw49_observed = {
                "raw_state_sha256": branch["endpoints"]["raw"]["state"]["sha256"],
                "strict_state_sha256": branch["endpoints"]["struct"]["state"]["sha256"],
                "goal_count": branch["goal_count"], "terminal": branch["terminal"],
            }
            if raw49_expected != raw49_observed:
                add_mismatch(ledger, target, "exp49_raw_endpoint", raw49_expected,
                             raw49_observed, tactic=tactic)

    old48_authored = next(x for x in e48["worker"]["executions"] if x["source"] == "authored")
    old49_authored = next(x for x in e49["worker"]["executions"] if x["source"] == "authored")
    new_authored = m0["authored"]
    auth48_observed = (new_authored.get("executable") is True,
                       new_authored.get("endpoints", {}).get("text48", {}).get("exp48_legacy_sha256"))
    auth48_expected = (old48_authored.get("executable") is True, old48_authored.get("endpoint_sha256"))
    if auth48_observed != auth48_expected:
        add_mismatch(ledger, target, "exp48_authored", auth48_expected, auth48_observed, tactic=target["authored_tactic"])
    raw_auth_expected = {"state_sha256": text_sha256(str(raw48["authored"]["stateAfter"])),
                         "goal_count": raw48["authored"]["goalCount"],
                         "terminal": raw48["authored"]["terminal"]}
    raw_auth_observed = {"state_sha256": new_authored["endpoints"]["raw"]["state"]["sha256"],
                         "goal_count": new_authored["goal_count"], "terminal": new_authored["terminal"]}
    if raw_auth_expected != raw_auth_observed:
        add_mismatch(ledger, target, "exp48_raw_authored", raw_auth_expected, raw_auth_observed,
                     tactic=target["authored_tactic"])
    auth49_observed = (new_authored.get("executable") is True,
                       {k: new_authored.get("endpoints", {}).get(k, {}).get("sha256") for k in ("raw", "text48", "struct")})
    auth49_expected = (old49_authored.get("executable") is True,
                       {k: old49_authored.get("endpoints", {}).get(k, {}).get("sha256") for k in ("raw", "text48", "struct")})
    if auth49_observed != auth49_expected:
        add_mismatch(ledger, target, "exp49_authored", auth49_expected, auth49_observed, tactic=target["authored_tactic"])
    raw49_auth_expected = {
        "raw_state_sha256": text_sha256(str(raw49["authored"]["stateAfter"])),
        "strict_state_sha256": text_sha256(str(raw49["authored"]["strictStateAfter"])),
        "goal_count": raw49["authored"]["goalCount"], "terminal": raw49["authored"]["terminal"],
    }
    raw49_auth_observed = {
        "raw_state_sha256": new_authored["endpoints"]["raw"]["state"]["sha256"],
        "strict_state_sha256": new_authored["endpoints"]["struct"]["state"]["sha256"],
        "goal_count": new_authored["goal_count"], "terminal": new_authored["terminal"],
    }
    if raw49_auth_expected != raw49_auth_observed:
        add_mismatch(ledger, target, "exp49_raw_authored", raw49_auth_expected,
                     raw49_auth_observed, tactic=target["authored_tactic"])

    initial48 = json_sha256(e48["worker"]["initial_endpoint"])
    if m0["initial_endpoints"]["text48"]["exp48_legacy_sha256"] != initial48:
        add_mismatch(ledger, target, "exp48_initial", initial48,
                     m0["initial_endpoints"]["text48"]["exp48_legacy_sha256"])
    raw_initial_expected = text_sha256(str(raw48["stateBefore"]))
    raw_initial_observed = m0["initial_endpoints"]["raw"]["state"]["sha256"]
    if raw_initial_expected != raw_initial_observed:
        add_mismatch(ledger, target, "exp48_raw_initial", raw_initial_expected, raw_initial_observed)
    initial49 = {k: e49["worker"]["initial_endpoints"][k]["sha256"] for k in ("raw", "text48", "struct")}
    initial_new = {k: m0["initial_endpoints"][k]["sha256"] for k in ("raw", "text48", "struct")}
    if initial49 != initial_new:
        add_mismatch(ledger, target, "exp49_initial", initial49, initial_new)
    raw49_initial_expected = {"raw": text_sha256(str(raw49["stateBefore"])),
                              "struct": text_sha256(str(raw49["strictStateBefore"]))}
    raw49_initial_observed = {"raw": m0["initial_endpoints"]["raw"]["state"]["sha256"],
                              "struct": m0["initial_endpoints"]["struct"]["state"]["sha256"]}
    if raw49_initial_expected != raw49_initial_observed:
        add_mismatch(ledger, target, "exp49_raw_initial", raw49_initial_expected,
                     raw49_initial_observed)

    reconstructed = m0_theorem_summary(m0)
    if reconstructed != e48["analysis"]:
        add_mismatch(ledger, target, "exp48_theorem_analysis", e48["analysis"], reconstructed)
    return {"slug": target["slug"], "theorem_id": target["theorem_id"],
            "full_name": target["full_name"], "reconstructed_analysis": reconstructed,
            "source_exp48_analysis": e48["analysis"],
            "candidate_agreement_exp48": agreement48,
            "candidate_agreement_exp49": agreement49,
            "exact": len(ledger) == start, "mismatch_count": len(ledger) - start}


def compare_mode(target: dict[str, Any], baseline: dict[str, Any], observed: dict[str, Any],
                 mode: str, ledger: list[dict[str, Any]]) -> dict[str, Any]:
    expected = full_row_signature(baseline)
    actual = full_row_signature(observed)
    exact = expected == actual
    if not exact:
        add_mismatch(ledger, target, "mode_exact_signature", expected, actual, mode=mode)
    agreement = empty_agreement()
    baseline_candidates, observed_candidates = branch_map(baseline), branch_map(observed)
    for tactic in sorted(set(baseline_candidates) & set(observed_candidates)):
        add_agreement(agreement, compact_signature(baseline_candidates[tactic]),
                      compact_signature(observed_candidates[tactic]))
    return {"slug": target["slug"], "theorem_id": target["theorem_id"],
            "full_name": target["full_name"], "mode": mode, "exact": exact,
            "candidate_agreement": agreement}


def row_path(root: Path, phase: str, target: dict[str, Any]) -> Path:
    return root / phase / "theorems" / safe_slug(target["slug"]) / f"{target['rid']}.json"


def empty_agreement() -> dict[str, Any]:
    return {"candidate_total": 0, "status_equal": 0,
            "status_confusion": {"failure/failure": 0, "failure/success": 0,
                                 "success/failure": 0, "success/success": 0},
            "executable_in_both": 0, "raw_endpoint_equal": 0,
            "text48_endpoint_equal": 0, "strict_endpoint_equal": 0}


def add_agreement(out: dict[str, Any], expected: dict[str, Any], observed: dict[str, Any],
                  has_strict: bool = True) -> None:
    es, os = expected.get("executable") is True, observed.get("executable") is True
    out["candidate_total"] += 1
    out["status_equal"] += es == os
    out["status_confusion"][f"{'success' if es else 'failure'}/{'success' if os else 'failure'}"] += 1
    if es and os:
        out["executable_in_both"] += 1
        out["raw_endpoint_equal"] += expected.get("raw") == observed.get("raw")
        out["text48_endpoint_equal"] += expected.get("text48") == observed.get("text48")
        if has_strict:
            out["strict_endpoint_equal"] += expected.get("struct") == observed.get("struct")


def merge_agreements(values: Iterable[dict[str, Any]]) -> dict[str, Any]:
    out = empty_agreement()
    for value in values:
        for key in ("candidate_total", "status_equal", "executable_in_both",
                    "raw_endpoint_equal", "text48_endpoint_equal", "strict_endpoint_equal"):
            out[key] += int(value[key])
        for key, count in value["status_confusion"].items():
            out["status_confusion"][key] += int(count)
    return out


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    cfgp, targetsp = root / "frozen/experiment50_config.json", root / "frozen/targets.json"
    cfg, targets = read_json(cfgp), read_json(targetsp)
    validate_code_lock(cfg["code_lock"])
    cfg_sha = file_sha256(cfgp)
    for path, key in ((root / "M0/summary.json", "mode_gate"),
                      (root / "orders/summary.json", "orders_execution_gate"),
                      (root / "M5/summary.json", "mode_gate")):
        if not path.is_file() or read_json(path).get(key) is not True:
            raise ValueError(f"execution gate absent: {path} -> {key}")
    summaryp = root / "analysis/summary.json"
    if summaryp.exists():
        value = read_json(summaryp)
        if value.get("config_sha256") != cfg_sha:
            raise ValueError("analysis belongs to another freeze")
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value

    ledger: list[dict[str, Any]] = []
    source_rows, order_rows, m5_rows = [], [], []
    m0_by: dict[str, dict[str, Any]] = {}
    for target in targets:
        path = row_path(root, "M0", target)
        if not path.is_file():
            raise FileNotFoundError(path)
        m0 = read_json(path)
        m0_by[target["theorem_id"]] = m0
        source_rows.append(compare_source(target, m0, ledger))
    for mode in ("M1", "M2", "M3", "M4"):
        for target in targets:
            observed = read_json(row_path(root, f"orders/{mode}", target))
            order_rows.append(compare_mode(target, m0_by[target["theorem_id"]], observed, mode, ledger))
    for target in targets:
        observed = read_json(row_path(root, "M5", target))
        m5_rows.append(compare_mode(target, m0_by[target["theorem_id"]], observed, "M5", ledger))

    c48 = read_json(cfg["source"]["exp48_config"])
    archived = read_json(cfg["source"]["exp48_summary"])
    repo_rows = [repository_summary(slug, [x for x in source_rows if x["slug"] == slug])
                 for slug in cfg["repositories"]]
    reconstructed = confirmation_summary(repo_rows, c48)
    aggregate_keys = (
        "repository_summaries", "primary_repo_macro_mean", "primary_repo_median",
        "primary_repo_bootstrap_95ci", "repositories_with_nonzero_primary",
        "repositories_with_nonterminal_signal", "repositories_with_cross_family_signal",
        "distinct_cross_head_pairs", "head_pairs_replicating_in_at_least_two_repositories",
        "recurring_head_pairs", "confirmation_checks", "confirmation_go",
        "strong_go_checks", "strong_go",
    )
    aggregate_expected = {k: archived.get(k) for k in aggregate_keys}
    aggregate_observed = {k: reconstructed.get(k) for k in aggregate_keys}
    aggregates_exact = aggregate_expected == aggregate_observed
    if not aggregates_exact:
        ledger.append({"slug": None, "theorem_id": None, "full_name": None,
                       "mode": "M0", "tactic": None, "category": "exp48_aggregate",
                       "expected": aggregate_expected, "observed": aggregate_observed})

    atomic_jsonl_dump(source_rows, root / "analysis/m0_source_comparisons.jsonl")
    atomic_jsonl_dump(order_rows, root / "analysis/order_comparisons.jsonl")
    atomic_jsonl_dump(m5_rows, root / "analysis/m5_comparisons.jsonl")
    atomic_jsonl_dump(ledger, root / "analysis/mismatch_ledger.jsonl")
    atomic_json_dump(reconstructed, root / "analysis/reconstructed_exp48_confirmation.json")
    agreements = {
        "M0_vs_archived_Exp48": merge_agreements(x["candidate_agreement_exp48"] for x in source_rows),
        "M0_vs_archived_Exp49": merge_agreements(x["candidate_agreement_exp49"] for x in source_rows),
        "order_and_process_modes_vs_M0": {
            **{mode: merge_agreements(x["candidate_agreement"] for x in order_rows if x["mode"] == mode)
               for mode in ("M1", "M2", "M3", "M4")},
            "M5": merge_agreements(x["candidate_agreement"] for x in m5_rows),
        },
    }
    atomic_json_dump(agreements, root / "analysis/agreement_counts.json")
    source_categories = [x["category"] for x in ledger if x.get("mode") == "M0"]
    checks = {
        "M0_96_evaluable": len(source_rows) == ROOTS and all(m0_by[x["theorem_id"]].get("worker_ok") is True for x in targets),
        "M0_exact_exp48_status_text_and_theorem_rows": all(x["exact"] for x in source_rows),
        "M0_exact_exp48_aggregates": aggregates_exact,
        "M0_exact_exp49_raw_text_strict": not any(x.startswith("exp49_") for x in source_categories),
        "M1_M4_384_roots_exact_M0": len(order_rows) == ROOTS * 4 and all(x["exact"] for x in order_rows),
        "M5_96_roots_2208_processes_exact_M0": (len(m5_rows) == ROOTS and all(x["exact"] for x in m5_rows)
            and read_json(root / "M5/summary.json").get("fresh_lean_processes_observed") == ROOTS * CANDIDATES_PER_ROOT),
        "zero_mismatches": len(ledger) == 0,
        "manual_reconciliation_zero": True,
    }
    value = {
        "version": 1, "protocol_version": PROTOCOL_VERSION, "config_sha256": cfg_sha,
        "study_role": cfg["study_role"], "independence_label": cfg["operator_statement"]["independence_boundary"],
        "independence_limit": "same physical server and frozen checkouts; not strongest machine-level independence",
        "roots": len(source_rows), "candidates_per_root": CANDIDATES_PER_ROOT,
        "order_comparisons": len(order_rows), "M5_fresh_processes": ROOTS * CANDIDATES_PER_ROOT,
        "mismatch_count": len(ledger), "manual_reconciliation_count": 0,
        "agreement_counts": agreements,
        "root_level_complete_agreement": {
            "M0_source": sum(x["exact"] for x in source_rows),
            **{mode: sum(x["exact"] for x in order_rows if x["mode"] == mode)
               for mode in ("M1", "M2", "M3", "M4")},
            "M5": sum(x["exact"] for x in m5_rows),
        },
        "repository_level_complete_agreement": {
            slug: all(x["exact"] for x in source_rows if x["slug"] == slug)
            and all(x["exact"] for x in order_rows if x["slug"] == slug)
            and all(x["exact"] for x in m5_rows if x["slug"] == slug)
            for slug in cfg["repositories"]},
        "checks": checks, "reexecution_pass": all(checks.values()),
        "archived_exp48_confirmation_go_preserved": reconstructed["confirmation_go"],
        "reconstructed_exp48": {k: reconstructed[k] for k in (
            "primary_repo_macro_mean", "primary_repo_median", "primary_repo_bootstrap_95ci",
            "distinct_cross_head_pairs", "head_pairs_replicating_in_at_least_two_repositories",
            "repositories_with_nonterminal_signal", "repositories_with_cross_family_signal")},
        "claim_boundary": cfg["claim_boundary"],
    }
    value["next_step"] = "Export immutable Exp50 audit bundle." if value["reexecution_pass"] else "STOP; inspect mismatch ledger without manual reconciliation."
    atomic_json_dump(value, summaryp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    return p.parse_args()


if __name__ == "__main__":
    result = analyze(parse_args())
    raise SystemExit(0 if result.get("reexecution_pass") else 2)
