"""Freeze balanced confirmation roots only after pilot-based power planning passes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiment58_protocol import *


def freeze(root: Path) -> dict[str, Any]:
    protocol = load_protocol(root)
    screening = read_json(root / "screening/summary.json")
    assert_sealed(screening, "screening summary")
    power = read_json(root / "pilot/power/summary.json")
    assert_sealed(power, "power summary")
    if screening.get("screening_gate") is not True or power.get("power_gate") is not True:
        raise ValueError("screening or pilot-based power gate failed")
    if power.get("confirmation_continuation_probes_executed") != 0:
        raise ValueError("confirmation continuation occurred before confirmation freeze")
    n_total = int(power["registered_design"]["total_roots"])
    per_dataset = n_total // len(DATASETS)
    ledger = read_jsonl(screening["eligibility_ledger"])
    selected = []
    for dataset in sorted(DATASETS):
        pool = sorted(
            [row for row in ledger if row["dataset"] == dataset and row["role"] == "confirmation" and row["eligible"]],
            key=lambda row: row["confirmation_selection_key"],
        )
        if len(pool) < per_dataset:
            raise ValueError(f"insufficient {dataset} confirmation roots: {len(pool)} < {per_dataset}")
        for rank, row in enumerate(pool, 1):
            row = dict(row)
            row["confirmation_selection_rank"] = rank
            row["selected"] = rank <= per_dataset
            row["exclusion_reason"] = None if row["selected"] else "selection_rank_above_powered_n"
            if row["selected"]:
                selected.append(row)
    selected_path = root / "confirmation/frozen/selected_roots.jsonl"
    atomic_jsonl_dump(selected, selected_path)
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "protocol_record_sha256": protocol["record_sha256"],
        "power_summary_sha256": file_sha256(root / "pilot/power/summary.json"),
        "confirmation_roots": len(selected), "roots_per_dataset": per_dataset,
        "selected_roots": str(selected_path), "selected_roots_sha256": file_sha256(selected_path),
        "policies": list(POLICIES), "candidate_panel": list(CANDIDATE_PANEL),
        "probe_panel": list(PROBE_PANEL), "manual_replacement_count": 0,
        "primary_efficiency_estimand": "paired full-minus-effect-aware process calls per root",
        "coverage_noninferiority_margin": COVERAGE_NONINFERIORITY_MARGIN,
        "pilot_and_confirmation_disjoint": all(row["role"] == "confirmation" for row in selected),
        "confirmation_continuation_probes_executed_before_freeze": 0,
        "confirmation_freeze_gate": len(selected) == n_total,
        "next_step": "Create a separate immutable confirmation execution package; do not alter this selection.",
    })
    atomic_json_dump(value, root / "confirmation/frozen/design.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(freeze(Path(parse_args().artifact_root).resolve()), indent=2))
