"""Freeze the Exp62 pilot or untouched confirmation after registered gates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiment62_protocol import *


def select_targets(root: Path, phase: str) -> list[dict[str, Any]]:
    frame = read_jsonl(root / "frozen/candidate_frame.jsonl")
    role = phase
    n = PILOT_ROOTS_PER_STRATUM if phase == "pilot" else CONFIRMATION_ROOTS_PER_STRATUM
    selected: list[dict[str, Any]] = []
    for stratum in STRATA:
        candidates = sorted(
            (row for row in frame if row["role"] == role and row["stratum"] == stratum),
            key=lambda row: row["role_rank_within_stratum"],
        )
        passing = []
        for target in candidates:
            receipt_path = root / "qualification/receipts" / f"{target['target_id']}.json"
            receipt = read_json(receipt_path)
            assert_sealed(receipt, f"qualification {target['target_id']}")
            if receipt.get("target_record_sha256") != target["record_sha256"]:
                raise ValueError("qualification-to-frame identity changed")
            if receipt.get("qualification_gate") is True:
                passing.append((target, receipt, receipt_path))
        if len(passing) < n:
            raise ValueError(f"insufficient qualified {phase} roots in {stratum}")
        for target, receipt, receipt_path in passing[:n]:
            witness_map: dict[str, str] = {}
            for step in receipt["live_witness_steps"]:
                key = str(step["before_endpoint_key"])
                tactic = str(step["tactic"])
                if key in witness_map and witness_map[key] != tactic:
                    raise ValueError("one live witness endpoint has two registered next tactics")
                witness_map[key] = tactic
            value = dict(target)
            value.update({
                "qualification_receipt": str(receipt_path),
                "qualification_receipt_sha256": file_sha256(receipt_path),
                "live_initial_endpoint_key": receipt["initial_endpoint_key"],
                "live_witness_next_tactic_by_endpoint": witness_map,
                "live_witness_map_sha256": json_sha256(witness_map),
                "phase": phase,
                "phase_rank_within_stratum": len([
                    row for row in selected if row["stratum"] == stratum
                ]) + 1,
            })
            selected.append(seal(value))
    return selected


def freeze(root: Path, phase: str) -> dict[str, Any]:
    if phase not in {"pilot", "confirmation"}:
        raise ValueError("phase must be pilot or confirmation")
    protocol = load_installed_protocol(root)
    qualification = read_json(root / "qualification/summary.json")
    assert_sealed(qualification, "Exp62 qualification summary")
    if qualification.get("qualification_gate") is not True:
        raise ValueError("Exp62 qualification gate did not pass")
    if phase == "confirmation":
        pilot = read_json(root / "pilot/analysis/summary.json")
        assert_sealed(pilot, "Exp62 pilot analysis")
        if pilot.get("pilot_go") is not True:
            raise ValueError("Exp62 pilot did not authorize confirmation")

    phase_root = root / phase
    design_path = phase_root / "frozen/design.json"
    if design_path.is_file():
        existing = read_json(design_path)
        assert_sealed(existing, f"Exp62 {phase} design")
        return existing
    targets = select_targets(root, phase)
    expected = EXPECTED_PILOT_ROOTS if phase == "pilot" else EXPECTED_CONFIRMATION_ROOTS
    if len(targets) != expected:
        raise ValueError("Exp62 selected root count changed")
    target_path = phase_root / "frozen/targets.jsonl"
    atomic_jsonl_dump(targets, target_path)
    root_order = [
        row["target_id"]
        for row in sorted(
            targets,
            key=lambda row: (row["stratum"], row["phase_rank_within_stratum"]),
        )
    ]
    jobs = []
    for target in targets:
        order = policy_order(target["target_id"])
        for position, policy in enumerate(order):
            job = {
                "version": VERSION,
                "protocol_version": PROTOCOL_VERSION,
                "phase": phase,
                "target_id": target["target_id"],
                "theorem_id": target["theorem_id"],
                "stratum": target["stratum"],
                "policy": policy,
                "policy_execution_position": position + 1,
                "policy_order": order,
                "job_id": json_sha256([phase, target["target_id"], policy])[:24],
                "maximum_search_depth": MAX_SEARCH_DEPTH,
                "maximum_expanded_nodes": MAX_EXPANDED_NODES,
                "maximum_tactic_invocations": MAX_TACTIC_INVOCATIONS,
                "policy_timeout_seconds": POLICY_TIMEOUT_SECONDS,
                "tactic_timeout_seconds": TACTIC_TIMEOUT_SECONDS,
                "candidate_panel_sha256": target["candidate_panel_sha256"],
                "witness_injection_disclosed": True,
                "scientific_retry_permitted": False,
            }
            job["job_identity_sha256"] = json_sha256(job)
            jobs.append(job)
    jobs.sort(key=lambda row: (root_order.index(row["target_id"]), row["policy_execution_position"]))
    jobs_path = phase_root / "frozen/jobs.jsonl"
    atomic_jsonl_dump(jobs, jobs_path)
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "phase": phase,
        "initial_protocol_record_sha256": protocol["record_sha256"],
        "qualification_summary_sha256": file_sha256(root / "qualification/summary.json"),
        "pilot_analysis_sha256": (
            file_sha256(root / "pilot/analysis/summary.json")
            if phase == "confirmation" else None
        ),
        "roots": len(targets),
        "roots_per_stratum": {
            stratum: sum(row["stratum"] == stratum for row in targets)
            for stratum in STRATA
        },
        "root_order": root_order,
        "targets_path": str(target_path),
        "targets_sha256": file_sha256(target_path),
        "jobs": len(jobs),
        "jobs_path": str(jobs_path),
        "jobs_sha256": file_sha256(jobs_path),
        "policies": list(POLICIES),
        "policy_execution": "sequential within root in frozen target-specific cyclic order",
        "concurrent_policy_execution": False,
        "scientific_policy_jobs_executed_before_phase_freeze": 0,
        "manual_root_replacement_count": 0,
        "next_step": f"Run Exp62 {phase} root shards.",
    })
    atomic_json_dump(value, design_path)
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--phase", required=True, choices=("pilot", "confirmation"))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(freeze(Path(args.artifact_root).resolve(), args.phase), indent=2))
