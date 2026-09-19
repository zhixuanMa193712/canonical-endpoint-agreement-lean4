"""Enumerate source-exact theorem holes and freeze a deterministic screening frame."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from experiment58_protocol import *


THEOREM_START = re.compile(r"(?m)^theorem\s+([^\s(:]+)")
BY_SORRY = re.compile(r":=\s*by\s*\n[ \t]*(sorry)\b", re.MULTILINE)
DIRECT_SORRY = re.compile(r":=\s*(sorry)\b", re.MULTILINE)


def byte_offset(text: str, char_offset: int) -> int:
    return len(text[:char_offset].encode("utf-8"))


def target_record(dataset: str, role: str, source_path: Path, theorem_name: str,
                  source_text: str, theorem_text: str, measurement_text: str,
                  sorry_char_offset: int, transform: str, project: Path) -> dict[str, Any]:
    source_sha = file_sha256(source_path)
    theorem_sha = hashlib.sha256(theorem_text.encode("utf-8")).hexdigest()
    identity = json_sha256([dataset, DATASETS[dataset]["commit"], str(source_path.relative_to(project)),
                            theorem_name, theorem_sha])
    target_id = identity[:24]
    generated_rel = Path("screening/generated_sources") / dataset / f"{target_id}.lean"
    return {
        "dataset": dataset, "role": role, "target_id": target_id,
        "theorem_name": theorem_name, "source_file": str(source_path),
        "source_file_path": str(source_path.relative_to(project)),
        "source_file_sha256": source_sha, "theorem_text_sha256": theorem_sha,
        "source_commit": DATASETS[dataset]["commit"], "measurement_transform": transform,
        "measurement_source_relative": str(generated_rel),
        "measurement_source_sha256": hashlib.sha256(measurement_text.encode("utf-8")).hexdigest(),
        "target_pos": byte_offset(measurement_text, sorry_char_offset),
        "target_end_pos": byte_offset(measurement_text, sorry_char_offset + len("sorry")),
        "partition_key": selection_key(PARTITION_SEED, dataset, str(source_path.relative_to(project)), theorem_name, theorem_sha),
        "frame_key": selection_key(FRAME_SEED, dataset, role, str(source_path.relative_to(project)), theorem_name, theorem_sha),
        "_measurement_text": measurement_text,
    }


def enumerate_minif2f(project: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role, relative in DATASETS["minif2f"]["upstream_partition"].items():
        source_path = project / relative
        source = source_path.read_text(encoding="utf-8")
        matches = list(THEOREM_START.finditer(source))
        if len(matches) != MINIF2F_EXPECTED_THEOREMS[role]:
            raise ValueError(f"miniF2F {role} theorem count changed: {len(matches)}")
        header = source[:matches[0].start()]
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
            block = source[match.start():end]
            proofs = list(BY_SORRY.finditer(block))
            if not proofs:
                # The corrected Google fork contains a small number of already
                # proved declarations.  They are outside the proof-hole frame.
                continue
            if len(proofs) != 1:
                raise ValueError(f"miniF2F target proof shape changed: {match.group(1)}")
            proof = proofs[0]
            theorem_text = block[:proof.end(1)]
            measurement = header + theorem_text + "\n"
            sorry_offset = len(header) + proof.start(1)
            rows.append(target_record(
                "minif2f", role, source_path, match.group(1), source, theorem_text,
                measurement, sorry_offset, "isolated-theorem-exact-by-sorry-v1", project,
            ))
    return rows


def enumerate_putnam(project: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    paths = sorted((project / "src").glob("putnam_*.lean"))
    if len(paths) != 672:
        raise ValueError(f"PutnamBench Lean4 source count changed: {len(paths)}")
    for source_path in paths:
        source = source_path.read_text(encoding="utf-8")
        theorem_name = source_path.stem
        starts = [m for m in THEOREM_START.finditer(source) if m.group(1) == theorem_name]
        if len(starts) != 1:
            raise ValueError(f"PutnamBench theorem identity changed: {theorem_name}")
        theorem_start = starts[0].start()
        theorem_region = source[theorem_start:]
        by_matches = list(BY_SORRY.finditer(theorem_region))
        direct_matches = list(DIRECT_SORRY.finditer(theorem_region))
        if by_matches:
            proof = by_matches[-1]
            measurement = source
            sorry_offset = theorem_start + proof.start(1)
            transform = "exact-source-by-sorry-v1"
            theorem_text = theorem_region[:proof.end(1)]
        elif direct_matches:
            proof = direct_matches[-1]
            absolute_start = theorem_start + proof.start(1)
            absolute_end = theorem_start + proof.end(1)
            measurement = source[:absolute_start] + "by\n  sorry" + source[absolute_end:]
            sorry_offset = absolute_start + len("by\n  ")
            transform = "target-proof-hole-direct-sorry-to-by-sorry-v1"
            theorem_text = theorem_region[:proof.end(1)]
        else:
            raise ValueError(f"PutnamBench proof hole changed: {theorem_name}")
        partition = selection_key(PARTITION_SEED, "putnambench", source_path.name, theorem_name)
        role = "pilot" if int(partition[:16], 16) % 4 == 0 else "confirmation"
        rows.append(target_record(
            "putnambench", role, source_path, theorem_name, source, theorem_text,
            measurement, sorry_offset, transform, project,
        ))
    return rows


def run(root: Path, checkout_root: Path) -> dict[str, Any]:
    load_protocol(root)
    environment = read_json(root / "preflight/benchmark_environment.json")
    assert_sealed(environment, "benchmark environment")
    if environment.get("environment_gate") is not True:
        raise ValueError("benchmark environment gate failed")
    all_rows = enumerate_minif2f(project_path("minif2f", checkout_root))
    all_rows += enumerate_putnam(project_path("putnambench", checkout_root))
    source_census = {
        "minif2f": {
            "theorem_declarations": sum(MINIF2F_EXPECTED_THEOREMS.values()),
            "proof_holes": sum(row["dataset"] == "minif2f" for row in all_rows),
        },
        "putnambench": {"theorem_declarations": 672, "proof_holes": 672},
    }
    source_census["minif2f"]["authored_proof_exclusions"] = (
        source_census["minif2f"]["theorem_declarations"] - source_census["minif2f"]["proof_holes"]
    )
    source_census["putnambench"]["authored_proof_exclusions"] = 0
    selected: list[dict[str, Any]] = []
    counts: dict[str, dict[str, int]] = {}
    for dataset in sorted(DATASETS):
        counts[dataset] = {}
        for role, take in (("pilot", PILOT_FRAME_PER_DATASET),
                           ("confirmation", CONFIRMATION_FRAME_PER_DATASET)):
            pool = sorted(
                [row for row in all_rows if row["dataset"] == dataset and row["role"] == role],
                key=lambda row: row["frame_key"],
            )
            counts[dataset][f"{role}_available"] = len(pool)
            if len(pool) < take:
                raise ValueError(f"insufficient {dataset} {role} targets: {len(pool)} < {take}")
            selected.extend(pool[:take])
    generated_root = root
    for row in all_rows:
        measurement = row.pop("_measurement_text")
        if row in selected:
            path = generated_root / row["measurement_source_relative"]
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.is_file() and file_sha256(path) != row["measurement_source_sha256"]:
                raise ValueError(f"generated measurement source changed: {path}")
            if not path.is_file():
                path.write_text(measurement, encoding="utf-8")
            row["measurement_source"] = str(path)
    for row in selected:
        row["screening_rank_within_dataset_role"] = 1 + sorted(
            x["frame_key"] for x in selected
            if x["dataset"] == row["dataset"] and x["role"] == row["role"]
        ).index(row["frame_key"])
        row["candidate_panel_sha256"] = json_sha256(CANDIDATE_PANEL)
        row["continuation_probe_count"] = 0
    complete_path = root / "frozen/complete_source_ledger.jsonl"
    frame_path = root / "frozen/candidate_screening_frame.jsonl"
    atomic_jsonl_dump(sorted(all_rows, key=lambda row: (row["dataset"], row["role"], row["frame_key"])), complete_path)
    atomic_jsonl_dump(sorted(selected, key=lambda row: (row["dataset"], row["role"], row["frame_key"])), frame_path)
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "complete_source_targets": len(all_rows), "screening_targets": len(selected),
        "expected_screening_targets": SCREENING_ROOTS_TOTAL, "availability": counts,
        "source_census": source_census,
        "complete_source_ledger": str(complete_path), "complete_source_ledger_sha256": file_sha256(complete_path),
        "candidate_screening_frame": str(frame_path), "candidate_screening_frame_sha256": file_sha256(frame_path),
        "manual_replacement_count": 0, "candidate_only_tactics_executed": 0,
        "continuation_probes_executed": 0,
        "frame_gate": len(selected) == SCREENING_ROOTS_TOTAL,
        "next_step": "Run compile-only candidate-worker preflight." if len(selected) == SCREENING_ROOTS_TOTAL
        else "STOP: source frame incomplete.",
    })
    atomic_json_dump(value, root / "frozen/source_frame_receipt.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--checkout-root", default=str(CHECKOUT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run(Path(args.artifact_root).resolve(), Path(args.checkout_root).resolve()), indent=2))
