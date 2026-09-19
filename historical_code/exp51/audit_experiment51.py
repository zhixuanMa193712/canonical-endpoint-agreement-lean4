"""Independent offline reconstruction audit for Exp51 scientific rows.

This script intentionally imports no function from ``analyze_experiment51``.
It reconstructs the primary and robust root indicators, repository rates,
hierarchical bootstrap intervals, and descriptive pair recurrence directly from
the immutable worker rows.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from experiment51_protocol import *


def root_indicator(worker: dict[str, Any], tactics: list[str]) -> tuple[bool, bool, set[tuple[str, str]]]:
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
    nonterminal = False
    for branches in clusters.values():
        for left, right in itertools.combinations(branches, 2):
            if left["head"] != right["head"]:
                pairs.add(tuple(sorted((left["head"], right["head"]))))
                if left.get("terminal") is False and right.get("terminal") is False:
                    nonterminal = True
    return bool(pairs), nonterminal, pairs


def bootstrap(by_repo: dict[str, list[dict[str, Any]]], field: str,
              seed: int) -> list[float]:
    slugs = sorted(by_repo)
    if not slugs:
        return []
    rng = random.Random(seed)
    values = []
    for _ in range(BOOTSTRAP_REPLICATES):
        chosen = [rng.choice(slugs) for _ in slugs]
        repo_means = []
        for slug in chosen:
            rows = by_repo[slug]
            sampled = [rng.choice(rows) for _ in rows]
            repo_means.append(mean(int(x[field]) for x in sampled))
        values.append(mean(repo_means))
    return values


def ci(values: list[float]) -> list[float]:
    return [quantile(values, 0.025), quantile(values, 0.975)] if values else [0.0, 0.0]


def audit(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    cfgp = root / "frozen/experiment51_config.json"
    targetsp = root / "frozen/targets.json"
    analysisp = root / "analysis/summary.json"
    cfg, targets, reported = read_json(cfgp), read_json(targetsp), read_json(analysisp)
    validate_code_lock(cfg["code_lock"])
    outp = root / "audit/summary.json"
    if outp.exists():
        value = read_json(outp)
        if value.get("analysis_sha256") != file_sha256(analysisp):
            raise ValueError("audit belongs to another analysis")
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value
    reconstructed = []
    by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pair_repositories: dict[tuple[str, str], set[str]] = defaultdict(set)
    candidate_attempts = 0
    for target in targets:
        rowp = root / "scientific/theorems" / safe_slug(target["slug"]) / f"{target['rid']}.json"
        worker = read_json(rowp)
        if (worker.get("theorem_id") != target["theorem_id"]
                or worker.get("candidate_order") != target["alternatives"]):
            raise ValueError(f"worker identity changed: {rowp}")
        candidate_attempts += len(worker.get("candidates", []))
        record = {"slug": target["slug"], "worker_ok": worker.get("worker_ok") is True,
                  "Y_L0": None, "Y_robust": None, "Y_NT_robust": None}
        if record["worker_ok"]:
            y0, _, pairs = root_indicator(worker, target["alternatives"])
            yr, ntr, _ = root_indicator(worker, target["robust_alternatives"])
            record.update({"Y_L0": y0, "Y_robust": yr, "Y_NT_robust": ntr})
            for pair in pairs:
                pair_repositories[pair].add(target["slug"])
            by_repo[target["slug"]].append(record)
        reconstructed.append(record)
    slugs = [x["slug"] for x in cfg["repositories"]]
    primary_rates = [mean(int(x["Y_L0"]) for x in by_repo[slug]) if by_repo[slug] else 0.0
                     for slug in slugs]
    robust_rates = [mean(int(x["Y_robust"]) for x in by_repo[slug]) if by_repo[slug] else 0.0
                    for slug in slugs]
    primary_ci = ci(bootstrap(by_repo, "Y_L0", BOOTSTRAP_SEED))
    robust_ci = ci(bootstrap(by_repo, "Y_robust", BOOTSTRAP_SEED + 1))
    checks = {
        "config_and_targets_exact": reported.get("config_sha256") == file_sha256(cfgp)
                                    and reported.get("targets_sha256") == file_sha256(targetsp),
        "root_count_exact": len(reconstructed) == reported.get("roots"),
        "evaluable_count_exact": sum(x["worker_ok"] for x in reconstructed)
                                 == reported.get("evaluable_roots"),
        "candidate_attempts_exact": candidate_attempts == reported.get("candidate_attempts"),
        "primary_repository_rates_exact": primary_rates == reported["primary"]["repository_rates"],
        "primary_macro_exact": mean(primary_rates) == reported["primary"]["macro_mean"],
        "primary_bootstrap_ci_exact": primary_ci == reported["primary"]["two_level_bootstrap_95ci"],
        "robust_repository_rates_exact": robust_rates == reported["robust"]["repository_rates"],
        "robust_macro_exact": mean(robust_rates) == reported["robust"]["macro_mean"],
        "robust_bootstrap_ci_exact": robust_ci == reported["robust"]["two_level_bootstrap_95ci"],
        "distinct_pair_count_exact": len(pair_repositories)
                                     == reported["descriptive_structure"]["distinct_cross_head_pairs"],
        "recurring_pair_count_exact": sum(len(x) >= 2 for x in pair_repositories.values())
                                      == reported["descriptive_structure"]["pairs_recurring_in_at_least_two_repositories"],
        "manual_reconciliation_zero": reported.get("manual_reconciliation_count") == 0,
    }
    value = {
        "version": 1, "protocol_version": PROTOCOL_VERSION,
        "audit_scope": "Exp51 only", "analysis_sha256": file_sha256(analysisp),
        "roots_reconstructed": len(reconstructed), "repositories_reconstructed": len(slugs),
        "bootstrap_replicates_reconstructed": BOOTSTRAP_REPLICATES,
        "manual_reconciliation_count": 0, "checks": checks,
        "audit_pass": all(checks.values()),
        "decision_label_preserved": reported["decision_label"],
        "claim_boundary": "audit validates Exp51 reconstruction only; it adds no scientific result",
        "next_step": "Export the immutable Exp51 audit bundle." if all(checks.values())
                     else "STOP; inspect immutable mismatch evidence.",
    }
    atomic_json_dump(value, outp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    return p.parse_args()


if __name__ == "__main__":
    result = audit(parse_args())
    raise SystemExit(0 if result.get("audit_pass") else 2)
