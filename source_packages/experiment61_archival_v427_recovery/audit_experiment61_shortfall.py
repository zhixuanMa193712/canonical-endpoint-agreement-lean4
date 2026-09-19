"""Audit the corrected Exp61 recruitment shortfall independently."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiment61_protocol import *


def audit(root: Path) -> dict:
    protocol = read_json(root / "frozen/protocol.json")
    assert_sealed(protocol, "Exp61 protocol")
    validate_implementation_locks_61(protocol)
    candidates = read_jsonl(root / "frozen/candidate_frame.jsonl")
    active = [row for row in candidates if not row.get("prequalification_exclusion")]
    passes = failures = unresolved = 0
    rebuilt = []
    for candidate in active:
        slug = candidate["slug"]
        path = root / "screening/build_trace" / f"{safe_slug_61(slug)}.json"
        if not path.is_file():
            unresolved += 1
            rebuilt.append({"slug": slug, "commit": candidate["commit"],
                            "status": "operationally_unresolved_counted_as_potential_success",
                            "receipt_sha256": None, "first_failed_gate": None})
            continue
        receipt = read_json(path)
        if receipt.get("candidate") != backend_candidate_61(candidate):
            raise ValueError(f"candidate identity changed: {slug}")
        if receipt.get("scientific_candidate_tactics_executed") != 0:
            raise ValueError(f"nonzero scientific tactic count: {slug}")
        if receipt.get("build_trace_gate") is True:
            passes += 1; status = "build_trace_pass"
        else:
            if receipt.get("first_failed_gate") == "checkout":
                raise ValueError(f"checkout failure counted as definitive: {slug}")
            failures += 1; status = "definitive_noncheckout_failure"
        rebuilt.append({
            "slug": slug, "commit": candidate["commit"], "status": status,
            "receipt_sha256": file_sha256(path),
            "first_failed_gate": receipt.get("first_failed_gate"),
        })
    ledger_path = root / "recruitment_shortfall/completion_ledger.jsonl"
    if read_jsonl(ledger_path) != rebuilt:
        raise ValueError("Exp61 completion ledger mismatch")
    summary_path = root / "recruitment_shortfall/summary.json"
    summary = read_json(summary_path); assert_sealed(summary, "Exp61 summary")
    upper = passes + unresolved
    checks = {
        "decision": summary.get("decision_label")
        == "infrastructure_recovered_conservative_recruitment_shortfall",
        "passes": summary.get("definitive_build_trace_passes") == passes,
        "failures": summary.get("definitive_build_trace_failures") == failures,
        "unresolved": summary.get("operationally_unresolved_candidates") == unresolved,
        "upper_bound": summary.get("conservative_upper_bound") == upper,
        "strict_shortfall": upper < REPOSITORIES_REQUIRED,
        "unresolved_counted_as_success": summary.get(
            "operationally_unresolved_counted_as_successes") is True,
        "ledger_hash": summary.get("completion_ledger_sha256") == file_sha256(ledger_path),
        "protocol_hash": summary.get("protocol_sha256")
        == file_sha256(root / "frozen/protocol.json"),
        "zero_authored": not any((root / "screening/authored_rows").rglob("*.json")),
        "zero_scientific": not any((root / "scientific").rglob("*.json")),
        "zero_tactics": summary.get("scientific_candidate_tactics_executed") == 0,
        "exp60_superseded": summary.get("exp60_shortfall_decision_superseded") is True,
        "exp51_retained": summary.get("historical_exp51_precision_inconclusive_retained") is True,
    }
    failed = sorted(k for k, v in checks.items() if not v)
    if failed:
        raise ValueError(f"Exp61 audit failed: {failed}")
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION_61,
        "audit_passed": True, "checks": checks,
        "definitive_build_trace_passes": passes,
        "definitive_build_trace_failures": failures,
        "operationally_unresolved_candidates": unresolved,
        "conservative_upper_bound": upper,
        "repository_target": REPOSITORIES_REQUIRED,
        "summary_sha256": file_sha256(summary_path),
        "scientific_candidate_tactics_executed": 0,
    })
    atomic_json_dump(value, root / "recruitment_shortfall/audit.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT_61))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(audit(Path(parse_args().artifact_root).resolve()), indent=2, sort_keys=True))
