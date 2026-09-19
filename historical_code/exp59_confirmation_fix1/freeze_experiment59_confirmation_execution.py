"""Freeze exact four-policy jobs for the already selected 64 confirmation roots."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiment59_confirmation_protocol import *


def freeze(root: Path) -> dict[str, Any]:
    pilot, selection = load_selection()
    pilot_design = pilot.load_design(root)
    if any((root / path).exists() for path in (
        "confirmation/execution/cells", "confirmation/execution/jobs",
        "confirmation/execution/shards", "confirmation/analysis/summary.json",
        "confirmation/audit/summary.json",
    )):
        raise ValueError("confirmation execution artifacts exist before execution freeze")
    selected_path = Path(selection["selected_roots"])
    audit_path = Path(selection["selection_audit"])
    if file_sha256(selected_path) != EXPECTED_SELECTED_ROOTS_SHA256:
        raise ValueError("selected confirmation roots changed")
    if file_sha256(audit_path) != EXPECTED_SELECTION_AUDIT_SHA256:
        raise ValueError("confirmation selection audit changed")
    selected = read_jsonl(selected_path)
    if not (
        len(selected) == EXPECTED_ROOTS
        and all(sum(row["dataset"] == dataset for row in selected) == ROOTS_PER_DATASET
                for dataset in ("minif2f", "putnambench"))
        and all(row["eligible"] is True and row["role"] == "confirmation" for row in selected)
        and not ({row["target_id"] for row in selected} & set(pilot_design["root_order"]))
    ):
        raise ValueError("confirmation root selection changed")
    source_protocol = pilot.load_source()[0].load_protocol(root)
    panel = tuple(source_protocol["candidate_panel"])
    if len(panel) != CANDIDATES_PER_ROOT:
        raise ValueError("source candidate panel changed")
    targets = []; jobs = []
    for meta in selected:
        receipt_path = Path(meta["candidate_receipt"])
        if file_sha256(receipt_path) != meta["candidate_receipt_sha256"]:
            raise ValueError(f"candidate receipt changed: {meta['target_id']}")
        receipt = read_json(receipt_path); assert_sealed(receipt, f"candidate {meta['target_id']}")
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
            raise ValueError(f"confirmation root is not candidate-exact eligible: {meta['target_id']}")
        branches = []
        for row in receipt["candidate_rows"]:
            branch = {
                "branch_id": json_sha256([target["target_id"], row["candidate_position_frozen"], row["tactic"]])[:24],
                "candidate_position_frozen": row["candidate_position_frozen"],
                "tactic": row["tactic"], "head": row["head"],
                "expected_executable": row["executable"], "terminal": row["terminal"],
            }
            if row["executable"]:
                branch.update({"goal_count": row["goal_count"], "endpoints": row["endpoints"]})
            branches.append(branch)
        executable = [row for row in branches if row["expected_executable"] and not row["terminal"]]
        target_record = {
            "dataset": target["dataset"], "target_id": target["target_id"],
            "theorem_name": target["theorem_name"],
            "measurement_source": target["measurement_source"],
            "measurement_source_sha256": target["measurement_source_sha256"],
            "target_pos": target["target_pos"], "target_end_pos": target["target_end_pos"],
            "initial_endpoints": receipt["initial_endpoints"],
            "candidate_receipt": str(receipt_path),
            "candidate_receipt_sha256": file_sha256(receipt_path),
            "candidate_panel": branches,
            "executable_candidate_order": [row["branch_id"] for row in executable],
        }
        target_record["target_record_sha256"] = json_sha256(target_record); targets.append(target_record)
        for policy in POLICIES:
            chosen = choose(policy, executable, target["target_id"])
            job = {
                "phase": "confirmation", "dataset": target["dataset"],
                "target_id": target["target_id"], "theorem_name": target["theorem_name"],
                "policy": policy, "candidate_order": [row["branch_id"] for row in branches],
                "executable_candidate_order": [row["branch_id"] for row in executable],
                "selected_branches": chosen,
                "selected_branch_ids": [row["branch_id"] for row in chosen],
                "probe_order": list(PROBE_PANEL),
                "maximum_process_calls": CANDIDATES_PER_ROOT + len(chosen) * len(PROBE_PANEL),
                "time_budget_seconds": ROOT_POLICY_TIME_BUDGET_SECONDS,
                "selection_uses_downstream_outcomes": False,
            }
            job["job_id"] = json_sha256([target["target_id"], policy, job])[:24]
            job["job_identity_sha256"] = json_sha256(job); jobs.append(job)
    targets.sort(key=lambda row: (row["dataset"], row["target_id"]))
    root_order = [row["target_id"] for row in targets]
    jobs.sort(key=lambda row: (root_order.index(row["target_id"]), POLICIES.index(row["policy"])))
    targets_path = root / "confirmation/frozen/execution_targets.jsonl"
    jobs_path = root / "confirmation/frozen/execution_jobs.jsonl"
    atomic_jsonl_dump(targets, targets_path); atomic_jsonl_dump(jobs, jobs_path)
    implementation = [
        {"path": path.name, "bytes": path.stat().st_size, "sha256": file_sha256(path)}
        for path in sorted(PACKAGE_ROOT.glob("*.py"), key=lambda item: item.name)
    ]
    value = seal({
        "version": VERSION, "confirmation_protocol_version": CONFIRMATION_PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID, "implementation_locks": implementation,
        "source_selection_design": str(root / "confirmation/frozen/design.json"),
        "source_selection_design_sha256": file_sha256(root / "confirmation/frozen/design.json"),
        "source_selection_design_record_sha256": selection["record_sha256"],
        "source_selected_roots_sha256": EXPECTED_SELECTED_ROOTS_SHA256,
        "source_selection_audit_sha256": EXPECTED_SELECTION_AUDIT_SHA256,
        "source_pilot_design_record_sha256": pilot_design["record_sha256"],
        "roots": len(targets), "roots_per_dataset": ROOTS_PER_DATASET,
        "root_order": root_order, "policies": list(POLICIES), "jobs": len(jobs),
        "targets_path": str(targets_path), "targets_sha256": file_sha256(targets_path),
        "jobs_path": str(jobs_path), "jobs_sha256": file_sha256(jobs_path),
        "candidate_panel": list(panel), "probe_panel": list(PROBE_PANEL),
        "planned_candidate_process_calls": len(jobs) * CANDIDATES_PER_ROOT,
        "planned_max_process_calls_total": sum(job["maximum_process_calls"] for job in jobs),
        "primary_efficiency_rule": "one-sided normal lower bound for paired mean actual call saving is greater than zero",
        "coverage_rule": "one-sided Wilson upper bound for paired solved-root loss is at most 0.05",
        "coverage_noninferiority_margin": COVERAGE_NONINFERIORITY_MARGIN,
        "strict_endpoint_union_preservation": "separate registered diagnostic",
        "efficiency_and_coverage_are_separate_estimands": True,
        "common_root_policy_time_budget_seconds": ROOT_POLICY_TIME_BUDGET_SECONDS,
        "cell_timeout_seconds": CELL_TIMEOUT_SECONDS,
        "confirmation_search_cells_executed_before_execution_freeze": 0,
        "confirmation_continuation_probes_executed_before_execution_freeze": 0,
        "scientific_retry_count": 0, "manual_reconciliation_count": 0,
        "execution_freeze_gate": len(targets) == EXPECTED_ROOTS and len(jobs) == EXPECTED_JOBS,
        "next_step": "Run compile-only confirmation worker preflight.",
    })
    atomic_json_dump(value, root / "confirmation/frozen/execution_design.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(freeze(Path(parse_args().artifact_root).resolve()), indent=2))
