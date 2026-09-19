"""Seal Exp61 only when the corrected conservative upper bound is below 38."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiment61_protocol import *
from run_experiment61_recovery import build_state, load_inputs


def finalize(root: Path) -> dict[str, Any]:
    protocol, candidates, _ = load_inputs(root)
    state = build_state(root, candidates)
    if not state["futility_reached"]:
        raise ValueError(
            f"shortfall finalization refused: conservative upper bound "
            f"{state['conservative_upper_bound']} can still reach {REPOSITORIES_REQUIRED}"
        )
    if any((root / "screening/authored_rows").rglob("*.json")):
        raise ValueError("authored replay exists")
    if any((root / "scientific").rglob("*.json")):
        raise ValueError("scientific execution exists")
    ledger = []
    for candidate in [row for row in candidates if not row.get("prequalification_exclusion")]:
        slug = candidate["slug"]
        path = root / "screening/build_trace" / f"{safe_slug_61(slug)}.json"
        if not path.is_file():
            ledger.append({"slug": slug, "commit": candidate["commit"],
                           "status": "operationally_unresolved_counted_as_potential_success",
                           "receipt_sha256": None, "first_failed_gate": None})
            continue
        receipt = read_json(path)
        gate = receipt.get("first_failed_gate")
        ledger.append({
            "slug": slug, "commit": candidate["commit"],
            "status": "build_trace_pass" if receipt.get("build_trace_gate") is True
                      else "definitive_noncheckout_failure",
            "receipt_sha256": file_sha256(path), "first_failed_gate": gate,
        })
    ledger_path = root / "recruitment_shortfall/completion_ledger.jsonl"
    atomic_jsonl_dump(ledger, ledger_path)
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION_61,
        "decision_label": "infrastructure_recovered_conservative_recruitment_shortfall",
        "active_candidates": state["active"],
        "definitive_build_trace_passes": len(state["passed"]),
        "definitive_build_trace_failures": len(state["failed"]),
        "operationally_unresolved_candidates": len(state["unresolved"]),
        "failure_counts": state["failure_counts"],
        "conservative_upper_bound": state["conservative_upper_bound"],
        "repository_target": REPOSITORIES_REQUIRED,
        "strict_shortfall": state["conservative_upper_bound"] < REPOSITORIES_REQUIRED,
        "operationally_unresolved_counted_as_successes": True,
        "source_exp60_incident_archive_sha256": SOURCE_ARCHIVE_60_SHA256,
        "exp60_shortfall_decision_superseded": True,
        "completion_ledger_sha256": file_sha256(ledger_path),
        "protocol_sha256": file_sha256(root / "frozen/protocol.json"),
        "scientific_candidate_tactics_executed": 0,
        "scientific_result": False,
        "historical_exp51_precision_inconclusive_retained": True,
    })
    atomic_json_dump(value, root / "recruitment_shortfall/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT_61))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(finalize(Path(parse_args().artifact_root).resolve()), indent=2, sort_keys=True))
