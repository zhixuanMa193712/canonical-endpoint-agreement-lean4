"""Independent reconstruction audit for Fix3 Exp51 shard evidence.

This module deliberately does not call ``base_analysis``.  It reconstructs
root indicators, repository rates, bootstrap intervals, pair recurrence, and
the frozen decision directly from the immutable worker rows.
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

from alignment_protocol import *  # noqa: F401,F403


def amendment_sha(root: Path) -> str:
    return file_sha256(root / AMENDMENT_RELATIVE)


def root_indicator(
    worker: dict[str, Any], tactics: list[str]
) -> tuple[bool, bool, set[tuple[str, str]]]:
    primary, nonterminal, _cross_family, pairs = root_structure(worker, tactics)
    return primary, nonterminal, pairs


def root_structure(
    worker: dict[str, Any], tactics: list[str]
) -> tuple[bool, bool, bool, set[tuple[str, str]]]:
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
    cross_family = False
    for branches in clusters.values():
        cluster_pairs: set[tuple[str, str]] = set()
        for left, right in itertools.combinations(branches, 2):
            if left["head"] != right["head"]:
                cluster_pairs.add(tuple(sorted((left["head"], right["head"]))))
        if cluster_pairs:
            pairs |= cluster_pairs
            if all(branch.get("terminal") is False for branch in branches):
                nonterminal = True
            if len({branch["family"] for branch in branches}) >= 2:
                cross_family = True
    return bool(pairs), nonterminal, cross_family, pairs


def bootstrap(
    by_repo: dict[str, list[dict[str, Any]]], field: str, seed: int
) -> list[float]:
    slugs = sorted(by_repo)
    if not slugs:
        return []
    rng = random.Random(seed)
    values = []
    for _ in range(base.BOOTSTRAP_REPLICATES):
        chosen = [rng.choice(slugs) for _ in slugs]
        repository_means = []
        for slug in chosen:
            rows = by_repo[slug]
            sampled = [rng.choice(rows) for _ in rows]
            repository_means.append(mean(int(row[field]) for row in sampled))
        values.append(mean(repository_means))
    return values


def interval(values: list[float]) -> list[float]:
    return (
        [base.quantile(values, 0.025), base.quantile(values, 0.975)]
        if values else [0.0, 0.0]
    )


def audit(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    source = validate_amendment(root)
    cfg, targets, _protocol, _amendment = load_source_bundle(root)
    cfgp = root / SOURCE_CONFIG_RELATIVE
    targetsp = root / SOURCE_TARGETS_RELATIVE
    executionp = root / "scientific/summary.json"
    analysisp = root / "analysis/summary.json"
    execution, reported = read_json(executionp), read_json(analysisp)
    amend_sha = amendment_sha(root)
    if not (
        execution.get("execution_gate") is True
        and execution.get("root_receipts") == TARGET_ROOTS
        and execution.get("amendment_sha256") == amend_sha
        and reported.get("amendment_sha256") == amend_sha
        and reported.get("execution_summary_sha256") == file_sha256(executionp)
    ):
        raise ValueError("Fix3 execution or analysis identity changed")
    outp = root / "audit/summary.json"
    if outp.is_file():
        value = read_json(outp)
        if not (
            value.get("analysis_sha256") == file_sha256(analysisp)
            and value.get("amendment_sha256") == amend_sha
        ):
            raise ValueError("existing audit belongs to another analysis")
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value
    reconstructed = []
    by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pair_repositories: dict[tuple[str, str], set[str]] = defaultdict(set)
    candidate_attempts = 0
    all_evaluable_complete = True
    for target in targets:
        rowp = exp51_row_path(root, target)
        if not rowp.is_file():
            raise FileNotFoundError(rowp)
        worker = read_json(rowp)
        if not (
            worker.get("protocol_version") == base.PROTOCOL_VERSION
            and worker.get("mode") == "scientific"
            and worker.get("config_sha256") == source["config_sha256"]
            and worker.get("theorem_id") == target["theorem_id"]
            and worker.get("source_file_sha256") == target["source_file_sha256"]
            and worker.get("candidate_order") == target["alternatives"]
            and worker.get("record_sha256") == json_sha256({
                key: item for key, item in worker.items()
                if key != "record_sha256"
            })
        ):
            raise ValueError(f"worker identity changed: {rowp}")
        count = len(worker.get("candidates", []))
        candidate_attempts += count
        worker_ok = worker.get("worker_ok") is True
        all_evaluable_complete &= (not worker_ok or count == CANDIDATES_PER_ROOT)
        record = {
            "slug": target["slug"],
            "worker_ok": worker_ok,
            "authored_replay_ok": worker.get("authored_replay_ok") is True,
            "same_pre_state_all_branches": (
                worker.get("same_pre_state_all_branches") is True
            ),
            "Y_L0": None,
            "Y_NT_L0": None,
            "Y_CF_L0": None,
            "Y_robust": None,
            "Y_NT_robust": None,
        }
        if worker_ok:
            primary, primary_nonterminal, primary_cross_family, pairs = root_structure(
                worker, target["alternatives"]
            )
            robust, robust_nonterminal, _robust_cross_family, _ = root_structure(
                worker, target["robust_alternatives"]
            )
            record.update({
                "Y_L0": primary,
                "Y_NT_L0": primary_nonterminal,
                "Y_CF_L0": primary_cross_family,
                "Y_robust": robust,
                "Y_NT_robust": robust_nonterminal,
            })
            for pair in pairs:
                pair_repositories[pair].add(target["slug"])
            by_repo[target["slug"]].append(record)
        reconstructed.append(record)
    slugs = [item["slug"] for item in cfg["repositories"]]
    primary_rates = [
        mean(int(row["Y_L0"]) for row in by_repo[slug])
        if by_repo[slug] else 0.0
        for slug in slugs
    ]
    robust_rates = [
        mean(int(row["Y_robust"]) for row in by_repo[slug])
        if by_repo[slug] else 0.0
        for slug in slugs
    ]
    reconstructed_nonterminal_repositories = sum(
        any(row["Y_NT_L0"] for row in by_repo[slug]) for slug in slugs
    )
    reconstructed_cross_family_repositories = sum(
        any(row["Y_CF_L0"] for row in by_repo[slug]) for slug in slugs
    )
    primary_ci = interval(bootstrap(by_repo, "Y_L0", base.BOOTSTRAP_SEED))
    robust_ci = interval(bootstrap(by_repo, "Y_robust", base.BOOTSTRAP_SEED + 1))
    evaluable = sum(row["worker_ok"] for row in reconstructed)
    per_repository_evaluable = [len(by_repo[slug]) for slug in slugs]
    integrity = {
        "minimum_completed_repositories": len(slugs) >= base.MIN_REPOSITORIES,
        "overall_evaluability": (
            evaluable / len(reconstructed) >= base.MIN_OVERALL_EVALUABILITY
        ),
        "per_repository_evaluability": all(
            count / ROOTS_PER_REPOSITORY >= base.MIN_REPOSITORY_EVALUABILITY
            for count in per_repository_evaluable
        ),
        "all_candidates_attempted_per_evaluable_root": all_evaluable_complete,
        "all_evaluable_authored_replay_exact": all(
            not row["worker_ok"] or row["authored_replay_ok"]
            for row in reconstructed
        ),
        "all_evaluable_same_pre_state": all(
            not row["worker_ok"] or row["same_pre_state_all_branches"]
            for row in reconstructed
        ),
        "all_frozen_root_receipts_present": len(reconstructed) == TARGET_ROOTS,
        "manual_reconciliation_zero": True,
    }
    primary_gate = {
        "ci_halfwidth_at_most_0_10": (
            (primary_ci[1] - primary_ci[0]) / 2 <= base.MAX_CI_HALFWIDTH
        ),
        "ci_lower_gt_0_20": primary_ci[0] > base.PRIMARY_DELTA,
        "at_least_75pct_repositories_nonzero": (
            sum(rate > 0 for rate in primary_rates) / len(primary_rates) >= 0.75
        ),
    }
    robust_gate = {
        "ci_lower_gt_0_10": robust_ci[0] > base.ROBUST_DELTA,
        "at_least_75pct_repositories_nonzero": (
            sum(rate > 0 for rate in robust_rates) / len(robust_rates) >= 0.75
        ),
        "nonterminal_signal_at_least_50pct_repositories": (
            sum(
                any(row["Y_NT_robust"] for row in by_repo[slug])
                for slug in slugs
            ) / len(slugs) >= 0.50
        ),
    }
    if not all(integrity.values()):
        decision = "invalid_execution"
    elif all(primary_gate.values()):
        decision = (
            "robust_replication_go" if all(robust_gate.values())
            else "replication_go"
        )
    elif not primary_gate["ci_halfwidth_at_most_0_10"]:
        decision = "inconclusive"
    else:
        decision = "replication_no_go"
    recruitment = read_json(cfg["source"]["screening_summary"])
    row_indexp = root / "scientific/row_index.jsonl"
    row_index = read_jsonl(row_indexp)
    index_hashes_exact = (
        len(row_index) == TARGET_ROOTS
        and all(
            Path(item["row"]).is_file()
            and file_sha256(item["row"]) == item["row_sha256"]
            for item in row_index
        )
    )
    checks = {
        "amendment_and_execution_exact": (
            execution.get("amendment_sha256") == amend_sha
            and execution.get("execution_complete") is True
            and execution.get("execution_gate") is True
        ),
        "config_and_targets_exact": (
            reported.get("config_sha256") == file_sha256(cfgp)
            and reported.get("targets_sha256") == file_sha256(targetsp)
        ),
        "row_index_exact": (
            execution.get("row_index_sha256") == file_sha256(row_indexp)
            and index_hashes_exact
        ),
        "root_count_exact": len(reconstructed) == reported.get("roots"),
        "root_receipt_count_exact": (
            len(reconstructed) == reported.get("root_receipts") == TARGET_ROOTS
        ),
        "evaluable_count_exact": evaluable == reported.get("evaluable_roots"),
        "candidate_attempts_exact": candidate_attempts == reported.get(
            "candidate_attempts"
        ),
        "all_evaluable_rows_have_23_attempts": all_evaluable_complete,
        "primary_repository_rates_exact": (
            primary_rates == reported["primary"]["repository_rates"]
        ),
        "primary_macro_exact": (
            mean(primary_rates) == reported["primary"]["macro_mean"]
        ),
        "primary_bootstrap_ci_exact": (
            primary_ci == reported["primary"]["two_level_bootstrap_95ci"]
        ),
        "robust_repository_rates_exact": (
            robust_rates == reported["robust"]["repository_rates"]
        ),
        "robust_macro_exact": (
            mean(robust_rates) == reported["robust"]["macro_mean"]
        ),
        "robust_bootstrap_ci_exact": (
            robust_ci == reported["robust"]["two_level_bootstrap_95ci"]
        ),
        "distinct_pair_count_exact": (
            len(pair_repositories)
            == reported["descriptive_structure"]["distinct_cross_head_pairs"]
        ),
        "recurring_pair_count_exact": (
            sum(len(items) >= 2 for items in pair_repositories.values())
            == reported["descriptive_structure"][
                "pairs_recurring_in_at_least_two_repositories"
            ]
        ),
        "repositories_with_nonterminal_L0_exact": (
            reconstructed_nonterminal_repositories
            == reported["descriptive_structure"][
                "repositories_with_nonterminal_L0"
            ]
        ),
        "repositories_with_cross_family_L0_exact": (
            reconstructed_cross_family_repositories
            == reported["descriptive_structure"][
                "repositories_with_cross_family_L0"
            ]
        ),
        "extension2_flow_field_exact": (
            "repositories_considered" in recruitment
            and reported["flow"]["repositories_screened"]
            == recruitment["repositories_considered"]
            and reported["flow"]["repositories_screened_source_field"]
            == "repositories_considered"
        ),
        "integrity_checks_exact": integrity == reported["integrity_checks"],
        "primary_gate_checks_exact": primary_gate == reported["primary_gate_checks"],
        "robust_gate_checks_exact": robust_gate == reported["robust_gate_checks"],
        "decision_label_exact": decision == reported["decision_label"],
        "manual_reconciliation_zero": (
            reported.get("manual_reconciliation_count") == 0
        ),
    }
    value: dict[str, Any] = {
        "version": 1,
        "protocol_version": base.PROTOCOL_VERSION,
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "amendment_sha256": amend_sha,
        "audit_scope": "Exp51 Fix3 shard evidence only",
        "analysis_sha256": file_sha256(analysisp),
        "execution_summary_sha256": file_sha256(executionp),
        "roots_reconstructed": len(reconstructed),
        "repositories_reconstructed": len(slugs),
        "bootstrap_replicates_reconstructed": base.BOOTSTRAP_REPLICATES,
        "manual_reconciliation_count": 0,
        "checks": checks,
        "audit_pass": all(checks.values()),
        "decision_label_preserved": decision,
        "claim_boundary": (
            "audit validates Exp51 Fix3 reconstruction only; it adds no scientific result"
        ),
    }
    value["next_step"] = (
        "Export the immutable Fix3 Exp51 evidence bundle."
        if value["audit_pass"] else "STOP; inspect immutable mismatch evidence."
    )
    atomic_json_dump(value, outp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(SCIENTIFIC_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    result = audit(parse_args())
    raise SystemExit(0 if result.get("audit_pass") is True else 2)
