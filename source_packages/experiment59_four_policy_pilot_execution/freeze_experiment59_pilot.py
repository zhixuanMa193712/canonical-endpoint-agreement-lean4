"""Freeze four-policy pilot jobs over the 32 selected Exp59 roots."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiment59_pilot_protocol import *


EXPECTED_SCREENING_COUNTS = {
    "minif2f": {"pilot_eligible": 36, "confirmation_eligible": 89},
    "putnambench": {"pilot_eligible": 48, "confirmation_eligible": 286},
}


def freeze(root: Path) -> dict[str, Any]:
    source, _ = load_source()
    source_protocol = source.load_protocol(root)
    summary_path = root / "screening/summary.json"
    summary = read_json(summary_path)
    assert_sealed(summary, "Exp59 screening summary")
    if not (
        summary.get("record_sha256") == EXPECTED_SCREENING_SUMMARY_RECORD_SHA256
        and summary.get("screening_roots") == EXPECTED_SCREENING_ROOTS
        and summary.get("operational_roots") == EXPECTED_SCREENING_ROOTS
        and summary.get("operational_failures_retained") == 0
        and summary.get("candidate_only_tactics_executed") == EXPECTED_SCREENING_ROOTS * CANDIDATES_PER_ROOT
        and summary.get("continuation_probes_executed") == 0
        and summary.get("scientific_retry_count") == 0
        and summary.get("manual_reconciliation_count") == 0
        and summary.get("screening_gate") is True
        and summary.get("eligibility_ledger_sha256") == EXPECTED_ELIGIBILITY_LEDGER_SHA256
        and summary.get("pilot_roots_sha256") == EXPECTED_PILOT_ROOTS_SHA256
    ):
        raise ValueError("Exp59 screening summary is not the protected completed run")
    for dataset, expected in EXPECTED_SCREENING_COUNTS.items():
        observed = summary["eligibility_counts"][dataset]
        if any(observed.get(key) != value for key, value in expected.items()):
            raise ValueError(f"Exp59 {dataset} eligibility counts changed")
    if any((root / relative).exists() for relative in (
        "pilot/execution/cells", "pilot/execution/jobs", "pilot/execution/shards",
        "pilot/analysis/summary.json", "pilot/power/summary.json",
    )):
        raise ValueError("pilot execution artifacts exist before the pilot freeze")
    eligibility_path = Path(summary["eligibility_ledger"])
    selected_path = Path(summary["pilot_roots_path"])
    if file_sha256(eligibility_path) != EXPECTED_ELIGIBILITY_LEDGER_SHA256:
        raise ValueError("Exp59 eligibility ledger changed")
    if file_sha256(selected_path) != EXPECTED_PILOT_ROOTS_SHA256:
        raise ValueError("Exp59 selected pilot roots changed")
    selected = read_jsonl(selected_path)
    if len(selected) != EXPECTED_PILOT_ROOTS:
        raise ValueError("Exp59 pilot selection is incomplete")
    if {row["dataset"] for row in selected} != {"minif2f", "putnambench"}:
        raise ValueError("Exp59 pilot dataset coverage changed")
    if any(sum(row["dataset"] == dataset for row in selected) != 16 for dataset in ("minif2f", "putnambench")):
        raise ValueError("Exp59 pilot is not balanced 16+16")

    jobs = []
    targets = []
    panel = tuple(source_protocol["candidate_panel"])
    if len(panel) != CANDIDATES_PER_ROOT:
        raise ValueError("Exp59 source candidate panel changed")
    for meta in selected:
        receipt_path = Path(meta["candidate_receipt"])
        if file_sha256(receipt_path) != meta["candidate_receipt_sha256"]:
            raise ValueError(f"candidate receipt changed: {meta['target_id']}")
        receipt = read_json(receipt_path)
        assert_sealed(receipt, f"candidate receipt {meta['target_id']}")
        target = receipt["target_identity"]
        if not (
            receipt.get("eligibility_gate") is True
            and receipt.get("worker_ok") is True
            and receipt.get("candidate_accounting_exact") is True
            and receipt.get("same_pre_state_all_branches") is True
            and receipt.get("terminal_candidate_count") == 0
            and receipt.get("candidate_only_tactics_executed") == CANDIDATES_PER_ROOT
            and receipt.get("continuation_probes_executed") == 0
            and tuple(receipt.get("candidate_panel", [])) == panel
            and len(receipt.get("candidate_rows", [])) == CANDIDATES_PER_ROOT
        ):
            raise ValueError(f"pilot root is not candidate-exact eligible: {meta['target_id']}")
        branches = []
        for row in receipt["candidate_rows"]:
            branch = {
                "branch_id": json_sha256([
                    target["target_id"], row["candidate_position_frozen"], row["tactic"]
                ])[:24],
                "candidate_position_frozen": row["candidate_position_frozen"],
                "tactic": row["tactic"],
                "head": row["head"],
                "expected_executable": row["executable"],
                "terminal": row["terminal"],
            }
            if row["executable"]:
                branch.update({"goal_count": row["goal_count"], "endpoints": row["endpoints"]})
            branches.append(branch)
        executable = [row for row in branches if row["expected_executable"] and not row["terminal"]]
        target_record = {
            "dataset": target["dataset"],
            "target_id": target["target_id"],
            "theorem_name": target["theorem_name"],
            "measurement_source": target["measurement_source"],
            "measurement_source_sha256": target["measurement_source_sha256"],
            "target_pos": target["target_pos"],
            "target_end_pos": target["target_end_pos"],
            "initial_endpoints": receipt["initial_endpoints"],
            "candidate_receipt": str(receipt_path),
            "candidate_receipt_sha256": file_sha256(receipt_path),
            "candidate_panel": branches,
            "executable_candidate_order": [row["branch_id"] for row in executable],
        }
        target_record["target_record_sha256"] = json_sha256(target_record)
        targets.append(target_record)
        for policy in POLICIES:
            chosen = choose(policy, executable, target["target_id"])
            job = {
                "phase": "pilot",
                "dataset": target["dataset"],
                "target_id": target["target_id"],
                "theorem_name": target["theorem_name"],
                "policy": policy,
                "candidate_order": [row["branch_id"] for row in branches],
                "executable_candidate_order": [row["branch_id"] for row in executable],
                "selected_branches": chosen,
                "selected_branch_ids": [row["branch_id"] for row in chosen],
                "probe_order": list(PROBE_PANEL),
                "maximum_process_calls": CANDIDATES_PER_ROOT + len(chosen) * len(PROBE_PANEL),
                "time_budget_seconds": ROOT_POLICY_TIME_BUDGET_SECONDS,
                "selection_uses_downstream_outcomes": False,
            }
            job["job_id"] = json_sha256([target["target_id"], policy, job])[:24]
            job["job_identity_sha256"] = json_sha256(job)
            jobs.append(job)
    targets.sort(key=lambda row: (row["dataset"], row["target_id"]))
    root_order = [row["target_id"] for row in targets]
    jobs.sort(key=lambda row: (root_order.index(row["target_id"]), POLICIES.index(row["policy"])))
    targets_path = root / "pilot/frozen/targets.jsonl"
    jobs_path = root / "pilot/frozen/jobs.jsonl"
    atomic_jsonl_dump(targets, targets_path)
    atomic_jsonl_dump(jobs, jobs_path)
    implementation = [
        {"path": path.name, "bytes": path.stat().st_size, "sha256": file_sha256(path)}
        for path in sorted(PACKAGE_ROOT.glob("*.py"), key=lambda item: item.name)
    ]
    backend_worker, backend_protocol = validate_backend()
    design = seal({
        "version": VERSION,
        "source_protocol_version": SOURCE_PROTOCOL_VERSION,
        "pilot_protocol_version": PILOT_PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "implementation_locks": implementation,
        "source_exp59_protocol_record_sha256": source_protocol["record_sha256"],
        "source_screening_summary": str(summary_path),
        "source_screening_summary_sha256": file_sha256(summary_path),
        "source_screening_summary_record_sha256": summary["record_sha256"],
        "source_eligibility_ledger_sha256": EXPECTED_ELIGIBILITY_LEDGER_SHA256,
        "source_pilot_roots_sha256": EXPECTED_PILOT_ROOTS_SHA256,
        "backend_worker": str(backend_worker),
        "backend_worker_sha256": BACKEND_WORKER_SHA256,
        "backend_protocol": str(backend_protocol),
        "backend_protocol_sha256": BACKEND_PROTOCOL_SHA256,
        "roots": len(targets),
        "roots_by_dataset": {dataset: sum(row["dataset"] == dataset for row in targets) for dataset in ("minif2f", "putnambench")},
        "root_order": root_order,
        "policies": list(POLICIES),
        "jobs": len(jobs),
        "targets_path": str(targets_path),
        "targets_sha256": file_sha256(targets_path),
        "jobs_path": str(jobs_path),
        "jobs_sha256": file_sha256(jobs_path),
        "candidate_panel": list(panel),
        "probe_panel": list(PROBE_PANEL),
        "candidate_stage": "each policy independently executes all 21 candidates in fresh Lean processes",
        "planned_candidate_process_calls": len(jobs) * CANDIDATES_PER_ROOT,
        "planned_max_process_calls_by_policy": {
            policy: sum(job["maximum_process_calls"] for job in jobs if job["policy"] == policy)
            for policy in POLICIES
        },
        "planned_max_process_calls_total": sum(job["maximum_process_calls"] for job in jobs),
        "primary_efficiency_estimand": "paired full-minus-effect-aware actual Lean process calls per root",
        "coverage_estimand": "full solves and effect-aware does not solve within the identical budget",
        "coverage_noninferiority_margin": COVERAGE_NONINFERIORITY_MARGIN,
        "efficiency_and_coverage_are_separate_estimands": True,
        "common_root_policy_time_budget_seconds": ROOT_POLICY_TIME_BUDGET_SECONDS,
        "time_budget_definition": "sum of recorded fresh-Lean-process elapsed seconds; restart-invariant",
        "cell_timeout_seconds": CELL_TIMEOUT_SECONDS,
        "stopping_rule": "after exact candidate stage, stop at first terminal strict endpoint or common root-policy time budget",
        "wall_clock_role": "descriptive secondary outcome only",
        "scientific_search_cells_executed_before_freeze": 0,
        "continuation_probes_executed_before_freeze": 0,
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
        "pilot_freeze_gate": len(targets) == EXPECTED_PILOT_ROOTS and len(jobs) == EXPECTED_JOBS,
        "next_step": "Run compile-only pilot worker preflight, then 32 frozen root shards.",
    })
    atomic_json_dump(design, root / "pilot/frozen/design.json")
    return design


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(freeze(Path(parse_args().artifact_root).resolve()), indent=2))
