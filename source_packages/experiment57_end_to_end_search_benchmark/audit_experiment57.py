"""Independent offline reconstruction audit for Experiment 57."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiment57_protocol import *
from analyze_experiment57 import analyze


def run(root: Path) -> dict:
    original_path = root / "analysis/summary.json"
    if not original_path.is_file():
        raise FileNotFoundError(original_path)
    original = read_json(original_path)
    assert_sealed(original, "original analysis")
    before = file_sha256(original_path)
    reconstructed = analyze(root)
    after = file_sha256(original_path)
    checks = {
        "analysis_byte_exact": before == after,
        "decision_label_exact": reconstructed["decision_label"] == original["decision_label"],
        "policy_metrics_exact": reconstructed["policy_metrics"] == original["policy_metrics"],
        "comparisons_exact": reconstructed["comparisons_vs_full"] == original["comparisons_vs_full"],
        "estimands_exact": reconstructed["estimands"] == original["estimands"],
        "integrity_checks_exact": reconstructed["integrity_checks"] == original["integrity_checks"],
        "zero_retry": original["scientific_retry_count"] == 0,
        "zero_manual_reconciliation": original["manual_reconciliation_count"] == 0,
    }
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "jobs_reconstructed": EXPECTED_JOBS, "checks": checks,
        "audit_pass": all(checks.values()),
        "decision_label_preserved": original["decision_label"],
        "next_step": "Export immutable benchmark bundle." if all(checks.values()) else "STOP; audit mismatch.",
    })
    atomic_json_dump(value, root / "audit/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(Path(parse_args().artifact_root).resolve()), indent=2))

