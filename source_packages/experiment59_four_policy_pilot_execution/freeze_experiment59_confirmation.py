"""Freeze balanced, disjoint Exp59 confirmation roots after pilot power planning."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiment59_pilot_protocol import *


def freeze(root: Path) -> dict[str, Any]:
    design = load_design(root)
    screening = read_json(root / "screening/summary.json")
    power_path = root / "pilot/power/summary.json"
    power = read_json(power_path)
    assert_sealed(screening, "Exp59 screening summary")
    assert_sealed(power, "Exp59 pilot power summary")
    if not (
        screening.get("record_sha256") == EXPECTED_SCREENING_SUMMARY_RECORD_SHA256
        and screening.get("screening_gate") is True
        and power.get("power_gate") is True
        and power.get("confirmation_continuation_probes_executed") == 0
        and power.get("manual_reconciliation_count") == 0
    ):
        raise ValueError("Exp59 screening or power gate failed")
    if any((root / path).exists() for path in (
        "confirmation/execution", "confirmation/analysis", "confirmation/audit"
    )):
        raise ValueError("confirmation execution artifacts exist before confirmation freeze")
    total_n = int(power["registered_design"]["total_roots"])
    per_dataset = total_n // 2
    ledger_path = Path(screening["eligibility_ledger"])
    if file_sha256(ledger_path) != EXPECTED_ELIGIBILITY_LEDGER_SHA256:
        raise ValueError("Exp59 eligibility ledger changed")
    ledger = read_jsonl(ledger_path)
    selected = []
    selection_audit = []
    for dataset in ("minif2f", "putnambench"):
        pool = sorted(
            [row for row in ledger if row["dataset"] == dataset
             and row["role"] == "confirmation" and row["eligible"] is True],
            key=lambda row: row["confirmation_selection_key"],
        )
        if len(pool) < per_dataset:
            raise ValueError(f"insufficient {dataset} confirmation roots: {len(pool)} < {per_dataset}")
        for rank, source_row in enumerate(pool, 1):
            row = dict(source_row)
            row["confirmation_selection_rank"] = rank
            row["selected"] = rank <= per_dataset
            row["post_eligibility_exclusion_reason"] = (
                None if row["selected"] else "selection_rank_above_powered_n"
            )
            selection_audit.append(row)
            if row["selected"]:
                selected.append(row)
    selected_path = root / "confirmation/frozen/selected_roots.jsonl"
    audit_path = root / "confirmation/frozen/selection_audit.jsonl"
    atomic_jsonl_dump(selected, selected_path)
    atomic_jsonl_dump(selection_audit, audit_path)
    gate = bool(
        len(selected) == total_n
        and all(sum(row["dataset"] == dataset for row in selected) == per_dataset
                for dataset in ("minif2f", "putnambench"))
        and all(row["role"] == "confirmation" and row["eligible"] is True for row in selected)
        and not ({row["target_id"] for row in selected} & set(design["root_order"]))
    )
    value = seal({
        "version": VERSION,
        "pilot_protocol_version": PILOT_PROTOCOL_VERSION,
        "confirmation_protocol_version": "experiment59-expansion-only-four-policy-confirmation-v1",
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "source_pilot_design_sha256": file_sha256(root / "pilot/frozen/design.json"),
        "source_power_summary": str(power_path),
        "source_power_summary_sha256": file_sha256(power_path),
        "confirmation_roots": len(selected),
        "roots_per_dataset": per_dataset,
        "selected_roots": str(selected_path),
        "selected_roots_sha256": file_sha256(selected_path),
        "selection_audit": str(audit_path),
        "selection_audit_sha256": file_sha256(audit_path),
        "policies": list(POLICIES),
        "candidate_panel": design["candidate_panel"],
        "probe_panel": design["probe_panel"],
        "primary_efficiency_estimand": design["primary_efficiency_estimand"],
        "coverage_estimand": design["coverage_estimand"],
        "coverage_noninferiority_margin": COVERAGE_NONINFERIORITY_MARGIN,
        "pilot_and_confirmation_disjoint": True,
        "manual_replacement_count": 0,
        "confirmation_continuation_probes_executed_before_freeze": 0,
        "confirmation_freeze_gate": gate,
        "next_step": (
            "Create a separate immutable confirmation execution package; do not alter this selection."
            if gate else "STOP; confirmation freeze failed."
        ),
    })
    atomic_json_dump(value, root / "confirmation/frozen/design.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(freeze(Path(parse_args().artifact_root).resolve()), indent=2))
