"""Independent deterministic reconstruction audit for the Exp56 analysis."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiment56_protocol import *
from analyze_prospective_confirmation import analyze


def run(root: Path) -> dict[str, Any]:
    path = root / "analysis/summary.json"
    original = read_json(path); assert_sealed(original, "analysis")
    before = file_sha256(path)
    reconstructed = analyze(root)
    checks = {
        "analysis_byte_exact": before == file_sha256(path),
        "decision_label_exact": original["decision_label"] == reconstructed["decision_label"],
        "repository_details_exact": original["repository_details"] == reconstructed["repository_details"],
        "bootstrap_exact": original["two_level_bootstrap_95ci"] == reconstructed["two_level_bootstrap_95ci"],
        "gates_exact": original["confirmation_checks"] == reconstructed["confirmation_checks"],
        "historical_exp48_not_overwritten": original["historical_exp48_conclusion_overwritten"] is False,
        "zero_manual_reconciliation": original["manual_reconciliation_count"] == 0,
        "zero_retry": original["scientific_retry_count"] == 0,
    }
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "checks": checks, "audit_pass": all(checks.values()),
        "decision_label_preserved": original["decision_label"],
    })
    atomic_json_dump(value, root / "audit/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(Path(parse_args().artifact_root).resolve()), indent=2))

