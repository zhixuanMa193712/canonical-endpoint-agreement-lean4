"""Freeze the disjoint pilot policy design without executing any continuation."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from experiment58_protocol import *


def choose(policy: str, branches: list[dict[str, Any]], target_id: str) -> list[dict[str, Any]]:
    if policy == "full":
        return branches
    if policy == "effect_aware":
        key = lambda row: row["endpoints"]["struct"]["sha256"]
    elif policy == "head_dedup":
        key = lambda row: row["head"]
    elif policy == "fixed_budget_random":
        budget = len(choose("effect_aware", branches, target_id))
        seed = int(selection_key(RANDOM_POLICY_SEED, target_id)[:16], 16)
        indices = sorted(random.Random(seed).sample(range(len(branches)), budget))
        return [branches[index] for index in indices]
    else:
        raise ValueError(policy)
    selected = []
    seen = set()
    for row in branches:
        identity = key(row)
        if identity not in seen:
            seen.add(identity)
            selected.append(row)
    return selected


def freeze(root: Path) -> dict[str, Any]:
    protocol = load_protocol(root)
    summary = read_json(root / CANDIDATE_SCREENING_EXECUTION_ROOT / "summary.json")
    assert_sealed(summary, "candidate screening summary")
    if summary.get("screening_gate") is not True or summary.get("continuation_probes_executed") != 0:
        raise ValueError("candidate screening did not reach the no-continuation gate")
    selected = read_jsonl(summary["pilot_roots_path"])
    jobs = []
    target_records = []
    for meta in selected:
        receipt = read_json(meta["candidate_receipt"])
        assert_sealed(receipt, f"candidate receipt {meta['target_id']}")
        if receipt.get("eligibility_gate") is not True:
            raise ValueError("ineligible root entered the pilot")
        target = receipt["target_identity"]
        executable = [row for row in receipt["candidate_rows"] if row["executable"] and not row["terminal"]]
        target_records.append({
            "dataset": target["dataset"], "target_id": target["target_id"],
            "theorem_name": target["theorem_name"], "candidate_receipt_sha256": file_sha256(meta["candidate_receipt"]),
            "measurement_source": target["measurement_source"],
            "measurement_source_sha256": target["measurement_source_sha256"],
            "target_pos": target["target_pos"], "target_end_pos": target["target_end_pos"],
        })
        for policy in POLICIES:
            chosen = choose(policy, executable, target["target_id"])
            job = {
                "phase": "pilot", "dataset": target["dataset"], "target_id": target["target_id"],
                "theorem_name": target["theorem_name"], "policy": policy,
                "candidate_panel": receipt["candidate_rows"],
                "executable_candidate_order": [row["candidate_position_frozen"] for row in executable],
                "selected_branches": chosen,
                "selected_candidate_positions": [row["candidate_position_frozen"] for row in chosen],
                "probe_order": list(PROBE_PANEL),
                "maximum_process_calls": CANDIDATES_PER_ROOT + len(chosen) * len(PROBE_PANEL),
                "selection_uses_downstream_outcomes": False,
            }
            job["job_id"] = json_sha256(job)[:24]
            job["job_identity_sha256"] = json_sha256(job)
            jobs.append(job)
    jobs.sort(key=lambda row: (row["dataset"], row["target_id"], POLICIES.index(row["policy"])))
    jobs_path = root / "pilot/frozen/jobs.jsonl"
    atomic_jsonl_dump(jobs, jobs_path)
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "protocol_record_sha256": protocol["record_sha256"], "pilot_roots": len(selected),
        "pilot_roots_by_dataset": {dataset: sum(row["dataset"] == dataset for row in selected) for dataset in DATASETS},
        "policies": list(POLICIES), "jobs": len(jobs), "targets": target_records,
        "jobs_path": str(jobs_path), "jobs_sha256": file_sha256(jobs_path),
        "primary_efficiency_estimand": "paired full-minus-effect-aware process calls per root",
        "coverage_noninferiority_margin": COVERAGE_NONINFERIORITY_MARGIN,
        "candidate_only_tactics_executed_before_pilot_freeze": summary["candidate_only_tactics_executed"],
        "pilot_continuation_probes_executed_before_freeze": 0,
        "confirmation_continuation_probes_executed_before_freeze": 0,
        "pilot_gate": len(selected) == 2 * PILOT_ROOTS_PER_DATASET and len(jobs) == len(selected) * len(POLICIES),
        "next_step": (
            "Use a separately audited execution package to run only these pilot jobs; then write paired_root_metrics.jsonl."
        ),
    })
    atomic_json_dump(value, root / "pilot/frozen/design.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(freeze(Path(parse_args().artifact_root).resolve()), indent=2))
