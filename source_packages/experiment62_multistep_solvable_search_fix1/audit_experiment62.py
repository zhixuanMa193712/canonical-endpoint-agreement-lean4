"""Independent receipt-level reconstruction audit for Exp62."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiment62_protocol import *


def audit(root: Path, phase: str) -> dict[str, Any]:
    design_path = root / phase / "frozen/design.json"
    analysis_path = root / phase / "analysis/summary.json"
    design = read_json(design_path); assert_sealed(design, f"Exp62 {phase} design")
    analysis = read_json(analysis_path); assert_sealed(analysis, f"Exp62 {phase} analysis")
    jobs = read_jsonl(design["jobs_path"])
    receipts = []
    by_policy = {policy: [] for policy in POLICIES}
    identities_exact = True
    accounting_exact = True
    for job in jobs:
        path = root / phase / "execution/jobs" / f"{job['job_id']}.json"
        row = read_json(path); assert_sealed(row, f"Exp62 job {job['job_id']}")
        identities_exact = identities_exact and row.get("job") == job
        if row.get("transition_rows") is not None:
            accounting_exact = accounting_exact and (
                len(row["transition_rows"]) == row.get("tactic_invocations")
            )
        receipts.append(row)
        by_policy[job["policy"]].append(row)
    reconstructed = []
    for policy in POLICIES:
        rows = by_policy[policy]
        reconstructed.append({
            "policy": policy,
            "roots": len(rows),
            "solved_roots_missing_as_unsolved": sum(row.get("solved") is True for row in rows),
            "multistep_solved_roots_missing_as_unsolved": sum(row.get("multi_step_solved") is True for row in rows),
            "tactic_invocations": sum(int(row.get("tactic_invocations", 0)) for row in rows),
            "expanded_nodes": sum(int(row.get("expanded_nodes", 0)) for row in rows),
            "operational_failure_roots": sum(row.get("operational_failure") is True for row in rows),
        })
    reported = {row["policy"]: row for row in analysis["policy_metrics"]}
    metrics_exact = all(
        row["roots"] == reported[row["policy"]]["roots"]
        and row["solved_roots_missing_as_unsolved"] == reported[row["policy"]]["solved_roots_missing_as_unsolved"]
        and row["multistep_solved_roots_missing_as_unsolved"] == reported[row["policy"]]["multistep_solved_roots_missing_as_unsolved"]
        and row["tactic_invocations"] == reported[row["policy"]]["tactic_invocations"]
        and row["expanded_nodes"] == reported[row["policy"]]["expanded_nodes"]
        and row["operational_failure_roots"] == reported[row["policy"]]["operational_failure_roots"]
        for row in reconstructed
    )
    audit_passed = bool(
        len(receipts) == len(jobs)
        and identities_exact
        and accounting_exact
        and metrics_exact
        and all(row.get("attempt_ordinal") == 1 for row in receipts)
        and all(row.get("scientific_retry_count") == 0 for row in receipts)
        and all(row.get("manual_reconciliation_count") == 0 for row in receipts)
    )
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "phase": phase,
        "planned_jobs": len(jobs),
        "receipt_jobs": len(receipts),
        "job_identities_exact": identities_exact,
        "transition_to_invocation_accounting_exact": accounting_exact,
        "reported_policy_metrics_reconstructed": metrics_exact,
        "all_attempt_ordinals_one": all(row.get("attempt_ordinal") == 1 for row in receipts),
        "zero_scientific_retries": all(row.get("scientific_retry_count") == 0 for row in receipts),
        "zero_manual_reconciliation": all(row.get("manual_reconciliation_count") == 0 for row in receipts),
        "reconstructed_policy_metrics": reconstructed,
        "analysis_record_sha256": analysis["record_sha256"],
        "audit_passed": audit_passed,
        "next_step": "Export the immutable Exp62 bundle." if audit_passed else "STOP; audit failed.",
    })
    atomic_json_dump(value, root / phase / "audit/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--phase", required=True, choices=("pilot", "confirmation"))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(audit(Path(args.artifact_root).resolve(), args.phase), indent=2))
