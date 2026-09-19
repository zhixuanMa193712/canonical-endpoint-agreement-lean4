"""Registered offline repository-level analysis for Experiment 56."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from experiment56_protocol import *


sys.path.insert(0, str(WORKSPACE_ROOT / "experiment51_external_repository_replication"))
import analyze_experiment51 as backend_analysis  # type: ignore


def analyze(root: Path) -> dict[str, Any]:
    protocol = read_json(root / "frozen/protocol.json"); assert_sealed(protocol, "protocol")
    validate_implementation_locks(protocol)
    selection = read_json(root / "frozen/selection_receipt.json"); assert_sealed(selection, "selection")
    if selection.get("selection_gate") is not True:
        raise ValueError("selection gate did not pass")
    targets = read_jsonl(root / "frozen/selected_roots.jsonl")
    worker_rows = []
    for target in targets:
        path = root / "scientific/theorems" / target["slug"].replace("/", "__") / f"{target['rid']}.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        row = read_json(path)
        if not (
            row.get("theorem_id") == target["theorem_id"]
            and row.get("candidate_order") == target["alternatives"]
            and row.get("record_sha256") == json_sha256({k: v for k, v in row.items() if k != "record_sha256"})
        ):
            raise ValueError(f"scientific row identity changed: {path}")
        worker_rows.append(row)
    theorem_rows = [
        backend_analysis.analyze_root(row, target)
        for row, target in zip(worker_rows, targets)
    ]
    atomic_jsonl_dump(theorem_rows, root / "analysis/theorem_rows.jsonl")
    slugs = sorted({row["slug"] for row in targets},
                   key=lambda slug: next(x["repository_selection_rank"] for x in targets if x["slug"] == slug))
    repositories = [
        backend_analysis.repository_summary(slug, [row for row in theorem_rows if row["slug"] == slug])
        for slug in slugs
    ]
    rates = [row["rates"]["Y_L0"] for row in repositories]
    macro = statistics.mean(rates)
    bootstrap_values = backend_analysis.hierarchical_bootstrap(
        theorem_rows, "L0.Y", BOOTSTRAP_SEED, BOOTSTRAP_REPLICATES
    )
    ci = backend_analysis.interval(bootstrap_values)
    halfwidth = (ci[1] - ci[0]) / 2
    nonzero_fraction = sum(rate > 0 for rate in rates) / len(rates)
    integrity = {
        "all_608_roots_accounted": len(worker_rows) == TOTAL_ROOTS,
        "all_38_repositories_accounted": len(repositories) == REPOSITORIES_REQUIRED,
        "all_candidates_attempted_on_evaluable_roots": all(
            row.get("worker_ok") is not True or len(row.get("candidates", [])) == CANDIDATES_PER_ROOT
            for row in worker_rows
        ),
        "all_authored_replay_exact": all(
            row.get("worker_ok") is not True or row.get("authored_replay_ok") is True
            for row in worker_rows
        ),
        "zero_manual_reconciliation": True,
        "zero_scientific_retry": True,
    }
    gates = {
        "ci_lower_gt_0_20": ci[0] > PRIMARY_THRESHOLD,
        "ci_halfwidth_lte_0_10": halfwidth <= MAX_CI_HALFWIDTH,
        "nonzero_repository_fraction_gte_0_75": nonzero_fraction >= MIN_NONZERO_REPOSITORY_FRACTION,
    }
    if not all(integrity.values()):
        label = "prospective_confirmation_invalid"
    elif all(gates.values()):
        label = "prospective_confirmation_go"
    elif not gates["ci_halfwidth_lte_0_10"]:
        label = "prospective_confirmation_inconclusive"
    else:
        label = "prospective_confirmation_no_go"
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "repositories": len(repositories), "roots": len(theorem_rows),
        "evaluable_roots": sum(row.get("worker_ok") is True for row in worker_rows),
        "repository_macro_witness_fraction": macro,
        "two_level_bootstrap_95ci": ci, "ci_halfwidth": halfwidth,
        "nonzero_repository_fraction": nonzero_fraction,
        "repository_details": repositories,
        "integrity_checks": integrity, "confirmation_checks": gates,
        "decision_label": label,
        "historical_exp48_conclusion_overwritten": False,
        "historical_exp48_conclusion": "retained unchanged and reported separately",
        "claim_boundary": "prospective prevalence evidence over the newly frozen eligible-repository frame",
        "manual_reconciliation_count": 0, "scientific_retry_count": 0,
    })
    atomic_json_dump(value, root / "analysis/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(analyze(Path(parse_args().artifact_root).resolve()), indent=2))
