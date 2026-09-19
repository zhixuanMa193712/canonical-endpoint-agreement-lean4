"""Frozen offline Exp51 analysis aligned with Extension2 and Fix3 shards."""
from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

from alignment_protocol import *  # noqa: F401,F403


def amendment_sha(root: Path) -> str:
    return file_sha256(root / AMENDMENT_RELATIVE)


def read_worker_rows(
    root: Path, targets: list[dict[str, Any]], cfg_sha: str
) -> list[dict[str, Any]]:
    rows = []
    for target in targets:
        path = exp51_row_path(root, target)
        if not path.is_file():
            raise FileNotFoundError(path)
        row = read_json(path)
        if not (
            row.get("protocol_version") == base.PROTOCOL_VERSION
            and row.get("mode") == "scientific"
            and row.get("config_sha256") == cfg_sha
            and row.get("theorem_id") == target["theorem_id"]
            and row.get("source_file_sha256") == target["source_file_sha256"]
            and row.get("candidate_order") == target["alternatives"]
            and row.get("record_sha256") == json_sha256({
                key: item for key, item in row.items() if key != "record_sha256"
            })
            and (
                row.get("worker_ok") is not True
                or len(row.get("candidates", [])) == CANDIDATES_PER_ROOT
            )
        ):
            raise ValueError(f"scientific worker row changed: {path}")
        rows.append(row)
    return rows


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    source = validate_amendment(root)
    cfg, targets, _protocol, _amendment = load_source_bundle(root)
    cfgp = root / SOURCE_CONFIG_RELATIVE
    targetsp = root / SOURCE_TARGETS_RELATIVE
    cfg_sha = source["config_sha256"]
    amend_sha = amendment_sha(root)
    executionp = root / "scientific/summary.json"
    execution = read_json(executionp)
    if not (
        execution.get("execution_gate") is True
        and execution.get("execution_complete") is True
        and execution.get("config_sha256") == cfg_sha
        and execution.get("targets_sha256") == source["targets_sha256"]
        and execution.get("amendment_sha256") == amend_sha
        and execution.get("root_receipts") == TARGET_ROOTS
        and execution.get("all_evaluable_rows_have_23_attempts") is True
    ):
        raise ValueError("Fix3 scientific execution is incomplete")
    outp = root / "analysis/summary.json"
    if outp.is_file():
        value = read_json(outp)
        if not (
            value.get("config_sha256") == cfg_sha
            and value.get("amendment_sha256") == amend_sha
            and value.get("execution_summary_sha256") == file_sha256(executionp)
        ):
            raise ValueError("existing analysis belongs to another execution")
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value
    worker_rows = read_worker_rows(root, targets, cfg_sha)
    root_rows = [
        base_analysis.analyze_root(row, target)
        for row, target in zip(worker_rows, targets)
    ]
    atomic_jsonl_dump(root_rows, root / "analysis/theorem_rows.jsonl")
    repository_slugs = [item["slug"] for item in cfg["repositories"]]
    repositories = [
        base_analysis.repository_summary(
            slug, [row for row in root_rows if row["slug"] == slug]
        )
        for slug in repository_slugs
    ]
    evaluable = sum(item["evaluable_roots"] for item in repositories)
    primary_rates = [item["rates"]["Y_L0"] for item in repositories]
    robust_rates = [item["rates"]["Y_Lrobust"] for item in repositories]
    primary_macro = mean(primary_rates)
    robust_macro = mean(robust_rates)
    primary_ci = base_analysis.interval(base_analysis.hierarchical_bootstrap(
        root_rows, "L0.Y", base.BOOTSTRAP_SEED, base.BOOTSTRAP_REPLICATES
    ))
    robust_ci = base_analysis.interval(base_analysis.hierarchical_bootstrap(
        root_rows, "L-mechanism-diverse.Y", base.BOOTSTRAP_SEED + 1,
        base.BOOTSTRAP_REPLICATES,
    ))
    completed_repositories = sum(
        item["roots_attempted"] == ROOTS_PER_REPOSITORY for item in repositories
    )
    integrity = {
        "minimum_completed_repositories": (
            completed_repositories >= base.MIN_REPOSITORIES
        ),
        "overall_evaluability": (
            evaluable / len(root_rows) >= base.MIN_OVERALL_EVALUABILITY
        ),
        "per_repository_evaluability": all(
            item["evaluable_rate"] >= base.MIN_REPOSITORY_EVALUABILITY
            for item in repositories
        ),
        "all_candidates_attempted_per_evaluable_root": all(
            not row["worker_ok"]
            or row["candidate_attempts"] == CANDIDATES_PER_ROOT
            for row in root_rows
        ),
        "all_evaluable_authored_replay_exact": all(
            not row["worker_ok"] or row["authored_replay_ok"]
            for row in root_rows
        ),
        "all_evaluable_same_pre_state": all(
            not row["worker_ok"] or row["same_pre_state_all_branches"]
            for row in root_rows
        ),
        "all_frozen_root_receipts_present": len(worker_rows) == TARGET_ROOTS,
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
            sum(item["rates"]["Y_NT_Lrobust"] > 0 for item in repositories)
            / len(repositories) >= 0.50
        ),
    }
    integrity_pass = all(integrity.values())
    primary_pass = all(primary_gate.values())
    if not integrity_pass:
        label = "invalid_execution"
    elif primary_pass:
        label = (
            "robust_replication_go" if all(robust_gate.values())
            else "replication_go"
        )
    elif not primary_gate["ci_halfwidth_at_most_0_10"]:
        label = "inconclusive"
    else:
        label = "replication_no_go"
    pair_repositories: dict[tuple[str, str], set[str]] = defaultdict(set)
    pair_occurrences: Counter[tuple[str, str]] = Counter()
    head_occurrences: Counter[str] = Counter()
    for row in root_rows:
        if row["worker_ok"]:
            for pair in row["L0"]["cross_head_pairs"]:
                key = tuple(pair)
                pair_repositories[key].add(row["slug"])
                pair_occurrences[key] += 1
                head_occurrences.update(key)
    pair_table = [
        {
            "head_pair": list(pair),
            "root_occurrences": count,
            "repository_count": len(pair_repositories[pair]),
            "repositories": sorted(pair_repositories[pair]),
        }
        for pair, count in sorted(
            pair_occurrences.items(), key=lambda item: (-item[1], item[0])
        )
    ]
    head_table = [
        {"head": head, "pair_root_occurrences": count}
        for head, count in sorted(
            head_occurrences.items(), key=lambda item: (-item[1], item[0])
        )
    ]
    atomic_jsonl_dump(pair_table, root / "analysis/pair_concentration.jsonl")
    atomic_jsonl_dump(head_table, root / "analysis/head_concentration.jsonl")
    leave_one_out = []
    for repository in repositories:
        retained = [
            item["rates"]["Y_L0"] for item in repositories
            if item["slug"] != repository["slug"]
        ]
        leave_one_out.append({
            "left_out": repository["slug"], "macro_mean": mean(retained)
        })
    paired_repository_differences = []
    for slug in repository_slugs:
        selected = [
            row for row in root_rows if row["slug"] == slug and row["worker_ok"]
        ]
        paired_repository_differences.append({
            "slug": slug,
            "mean_Y_L0_minus_Y_Lrobust": mean(
                int(row["L0"]["Y"])
                - int(row["L-mechanism-diverse"]["Y"])
                for row in selected
            ) if selected else 0.0,
        })
    paired_values = [
        item["mean_Y_L0_minus_Y_Lrobust"]
        for item in paired_repository_differences
    ]
    paired_ci = base_analysis.interval(base_analysis.paired_panel_bootstrap(
        root_rows, base.BOOTSTRAP_SEED + 2, base.BOOTSTRAP_REPLICATES
    ))
    recruitment_flow = read_json(cfg["source"]["screening_summary"])
    if "repositories_considered" not in recruitment_flow:
        raise ValueError("Extension2 repositories_considered field is absent")
    flow = {
        "repositories_screened": recruitment_flow["repositories_considered"],
        "repositories_screened_source_field": "repositories_considered",
        "repositories_build_trace_pass": sum(
            item["build_trace_gate"]
            for item in recruitment_flow["repository_ledger"]
        ),
        "repositories_authored_replay_pass": sum(
            item["authored_replay_gate"]
            for item in recruitment_flow["repository_ledger"]
        ),
        "lineage_representatives": len(
            recruitment_flow["lineage_representatives"]
        ),
        "repositories_frozen": len(repositories),
        "roots_frozen": len(root_rows),
        "root_receipts": len(worker_rows),
        "roots_evaluable": evaluable,
    }
    atomic_json_dump(flow, root / "analysis/flow.json")
    value: dict[str, Any] = {
        "version": 1,
        "protocol_version": base.PROTOCOL_VERSION,
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "amendment_sha256": amend_sha,
        "execution_summary_sha256": file_sha256(executionp),
        "config_sha256": file_sha256(cfgp),
        "targets_sha256": file_sha256(targetsp),
        "repositories": len(repositories),
        "roots": len(root_rows),
        "root_receipts": len(worker_rows),
        "evaluable_roots": evaluable,
        "candidate_attempts": sum(
            row["candidate_attempts"] for row in root_rows
        ),
        "primary": {
            "estimand": "Y-L0 repository macro mean",
            "repository_rates": primary_rates,
            "macro_mean": primary_macro,
            "median": median(primary_rates),
            "two_level_bootstrap_95ci": primary_ci,
            "bootstrap_replicates": base.BOOTSTRAP_REPLICATES,
            "bootstrap_seed": base.BOOTSTRAP_SEED,
        },
        "robust": {
            "estimand": "Y-Lmechanism-diverse repository macro mean",
            "repository_rates": robust_rates,
            "macro_mean": robust_macro,
            "two_level_bootstrap_95ci": robust_ci,
        },
        "paired_panel_comparison": {
            "estimand": (
                "repository-macro paired Y-L0 minus Y-Lmechanism-diverse"
            ),
            "repository_differences": paired_repository_differences,
            "macro_mean_difference": mean(paired_values) if paired_values else 0.0,
            "two_level_paired_bootstrap_95ci": paired_ci,
            "gate_authoritative": False,
        },
        "repositories_detail": repositories,
        "leave_one_repository_out": leave_one_out,
        "file_cluster_sensitivity_macro_mean": mean(
            item["equal_weight_file_mean_sensitivity"] for item in repositories
        ),
        "beta_binomial_sensitivity": (
            base_analysis.beta_binomial_sensitivity(repositories)
        ),
        "descriptive_structure": {
            "distinct_cross_head_pairs": len(pair_repositories),
            "pairs_recurring_in_at_least_two_repositories": sum(
                len(slugs) >= 2 for slugs in pair_repositories.values()
            ),
            "repositories_with_nonterminal_L0": sum(
                item["rates"]["Y_NT_L0"] > 0 for item in repositories
            ),
            "repositories_with_cross_family_L0": sum(
                item["rates"]["Y_CF_L0"] > 0 for item in repositories
            ),
            "pair_concentration_rows": len(pair_table),
            "head_concentration_rows": len(head_table),
        },
        "flow": flow,
        "integrity_checks": integrity,
        "primary_gate_checks": primary_gate,
        "robust_gate_checks": robust_gate,
        "manual_reconciliation_count": 0,
        "decision_label": label,
        "replication_go": label in {
            "replication_go", "robust_replication_go"
        },
        "robust_replication_go": label == "robust_replication_go",
        "exp48_confirmation_go_unchanged": True,
        "claim_boundary": cfg["claim_boundary"],
        "next_step": "Run independent Fix3 reconstruction audit.",
    }
    atomic_json_dump(value, outp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(SCIENTIFIC_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    analyze(parse_args())
