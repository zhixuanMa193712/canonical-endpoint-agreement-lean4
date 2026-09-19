"""Export the completed zero-candidate Exp51 recruitment No-Go decision.

This exporter is intentionally separate from the scientific Exp51 exporter.
It accepts only a stopped recruitment run, rejects any evidence of scientific
candidate execution, and records that the frozen candidate frame could not
reach the preregistered twelve-repository minimum.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from experiment51_protocol import (
    ARTIFACT_ROOT,
    MECHANICAL_FIX_ID,
    MIN_REPOSITORIES,
    PACKAGE_ROOT,
    PROTOCOL_VERSION,
    RECRUITMENT_VERSION,
    SERVER_ROOT,
    atomic_json_dump,
    file_sha256,
    json_sha256,
    read_json,
    validate_code_lock,
)


DECISION_LABEL = "recruitment_no_go"
EXPORT_SCHEMA = "experiment51-zero-candidate-recruitment-nogo-export-v1"


def derive_decision(
    config: dict[str, Any],
    recovery: dict[str, Any],
    rows: list[dict[str, Any]],
    receipt_names: Iterable[str] = (),
) -> dict[str, Any]:
    """Reconstruct the recruitment decision without reading scientific data."""
    if config.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("wrong Exp51 protocol")
    if config.get("recruitment_version") != RECRUITMENT_VERSION:
        raise ValueError("wrong Exp51 recruitment version")
    if config.get("mechanical_fix_id") != MECHANICAL_FIX_ID:
        raise ValueError("wrong Exp51 mechanical fix")
    if config.get("scientific_candidate_tactics_permitted") != 0:
        raise ValueError("scientific candidates were permitted during recruitment")
    if int(config.get("minimum_repositories", -1)) != MIN_REPOSITORIES:
        raise ValueError("the preregistered repository minimum changed")

    if recovery.get("phase") != "recover-enumeration":
        raise ValueError("recovery phase is incomplete")
    if recovery.get("mechanical_fix_id") != MECHANICAL_FIX_ID:
        raise ValueError("recovery mechanical fix changed")
    if recovery.get("trace_executed") is not False:
        raise ValueError("fix9 recovery unexpectedly executed tracing")
    if recovery.get("scientific_candidate_tactics_executed") != 0:
        raise ValueError("recovery executed scientific candidate tactics")
    if recovery.get("fix8_success_frames_exact") is not True:
        raise ValueError("protected fix8 success frames changed")
    if recovery.get("checkout_line_ending_measurement", {}).get("exact") is not True:
        raise ValueError("checkout line-ending qualification changed")
    if recovery.get("recovery_gate") is not False:
        raise ValueError("this exporter accepts only the stopped recruitment No-Go")

    expected_count = int(config.get("candidate_count", -1))
    if len(rows) != expected_count or recovery.get("candidates") != expected_count:
        raise ValueError("candidate receipt ledger is incomplete")
    slugs = [row.get("candidate", {}).get("slug") for row in rows]
    if any(not slug for slug in slugs) or len(slugs) != len(set(slugs)):
        raise ValueError("candidate receipt identities are missing or duplicated")
    if any(row.get("scientific_candidate_tactics_executed") != 0 for row in rows):
        raise ValueError("a recruitment receipt executed scientific candidates")

    passed_rows = [row for row in rows if row.get("build_trace_gate") is True]
    failure_counts = Counter(
        row.get("first_failed_gate") or "passed" for row in rows
    )
    passed = len(passed_rows)
    if recovery.get("passed") != passed:
        raise ValueError("recovery pass count differs from theorem receipts")
    if passed >= MIN_REPOSITORIES:
        raise ValueError("recruitment met its minimum and is not a No-Go")

    root_failures = [
        row for row in rows if row.get("first_failed_gate") == "root_enumeration"
    ]
    low_frames = [
        {
            "slug": row["candidate"]["slug"],
            "pre_replay_frame": row.get("enumeration", {}).get("pre_replay_frame"),
        }
        for row in rows
        if row.get("first_failed_gate") == "minimum_pre_replay_frame"
    ]
    current_frame_upper_bound = passed + len(root_failures)
    if current_frame_upper_bound >= MIN_REPOSITORIES:
        raise ValueError(
            "unresolved root enumeration could still reach the minimum; "
            "do not declare a frame-level No-Go"
        )

    receipt_names_set = set(receipt_names)
    root_errors = []
    for row in root_failures:
        slug = row["candidate"]["slug"]
        message = " ".join(str(row.get("error", {}).get("message", "")).split())
        root_errors.append({
            "slug": slug,
            "error_type": row.get("error", {}).get("type"),
            "error_message_sha256": hashlib.sha256(message.encode("utf-8")).hexdigest(),
            "error_tail": message[-2000:],
            "parser_receipt_present": slug.replace("/", "__") + ".json" in receipt_names_set,
        })

    parser_measurement = dict(recovery.get("parser_compatibility_measurement", {}))
    observed_parser_repositories = parser_measurement.get("observed", {}).get("repositories")
    expected_parser_repositories = parser_measurement.get(
        "expected_from_frozen_parser_qualification", {}
    ).get("repositories")

    return {
        "version": 1,
        "export_schema": EXPORT_SCHEMA,
        "protocol_version": PROTOCOL_VERSION,
        "recruitment_version": RECRUITMENT_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "decision_label": DECISION_LABEL,
        "scientific_result": False,
        "scientific_candidate_tactics_executed": 0,
        "trace_reexecuted_by_fix9": False,
        "candidate_frame_count": expected_count,
        "repositories_passed": passed,
        "minimum_required": MIN_REPOSITORIES,
        "current_frame_upper_bound": current_frame_upper_bound,
        "current_frame_can_reach_minimum": False,
        "passed_repositories": sorted(
            row["candidate"]["slug"] for row in passed_rows
        ),
        "failure_gate_counts": dict(sorted(failure_counts.items())),
        "minimum_pre_replay_frame_failures": sorted(
            low_frames, key=lambda item: item["slug"]
        ),
        "unresolved_root_enumeration_failures": sorted(
            root_errors, key=lambda item: item["slug"]
        ),
        "parser_compatibility_accounting": {
            "expected_repositories": expected_parser_repositories,
            "observed_completed_receipts": observed_parser_repositories,
            "exact": parser_measurement.get("exact"),
            "interpretation": (
                "descriptive receipt aggregation is incomplete because failed "
                "enumeration workers emitted no final parser receipt"
            ),
        },
        "protected_controls": {
            "fix8_success_frames_exact": True,
            "checkout_line_ending_measurement_exact": True,
            "manual_reconciliation_count": 0,
        },
        "claim_boundary": [
            "this is a repository-recruitment qualification outcome, not a scientific tactic result",
            "Experiment 48 remains the existing Tier-1 confirmation",
            "no claim of tactic interchangeability, proof-strategy equivalence, proof-term equality, runtime equivalence, or prover improvement",
        ],
        "next_step": (
            "Preserve this frame-level No-Go and preregister a new zero-candidate "
            "repository-frame extension; do not lower the twelve-repository minimum."
        ),
    }


def export(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    configp = root / "recruitment_frozen/recruitment_config.json"
    recoveryp = root / "screening/build_trace_summary.json"
    config = read_json(configp)
    recovery = read_json(recoveryp)
    validate_code_lock(config["code_lock"])

    forbidden = [
        root / "screening/summary.json",
        root / "frozen/experiment51_config.json",
        root / "scientific/summary.json",
        root / "analysis/summary.json",
        root / "audit/summary.json",
    ]
    if any(path.exists() for path in forbidden):
        raise ValueError("post-recruitment or scientific Exp51 artifacts already exist")

    row_paths = sorted((root / "screening/build_trace").glob("*.json"))
    rows = [read_json(path) for path in row_paths]
    receipt_paths = sorted((root / "screening/enumeration_receipts").glob("*.json"))
    decision = derive_decision(config, recovery, rows, (p.name for p in receipt_paths))

    decision_dir = root / "recruitment_nogo"
    summaryp = decision_dir / "summary.json"
    receiptp = decision_dir / "export_receipt.json"
    if summaryp.is_file() and read_json(summaryp) != decision:
        raise ValueError("an existing Exp51 recruitment No-Go decision differs")
    atomic_json_dump(decision, summaryp)

    output = Path(args.output).resolve()
    if output.exists():
        if receiptp.is_file() and read_json(receiptp).get("bundle_sha256") == file_sha256(output):
            value = read_json(receiptp)
            print(json.dumps(value, ensure_ascii=False, indent=2))
            return value
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_name(output.name + ".tmp")
    if tmp.exists():
        raise FileExistsError(tmp)

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(zf: zipfile.ZipFile, path: Path, arc: str, role: str) -> None:
        if arc in seen:
            raise ValueError(f"duplicate bundle member: {arc}")
        if not path.is_file():
            raise FileNotFoundError(path)
        seen.add(arc)
        entries.append({
            "path": arc,
            "role": role,
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        })
        zf.write(path, arc)

    try:
        with zipfile.ZipFile(
            tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6,
            allowZip64=True,
        ) as zf:
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                relative = path.relative_to(root)
                if relative.parts[0] == "logs" or path == receiptp:
                    continue
                add(zf, path, "artifacts/" + relative.as_posix(), "recruitment_artifact")
            for path in sorted(p for p in PACKAGE_ROOT.iterdir() if p.is_file()):
                add(zf, path, "code/" + path.name, "exp51_source_code")

            manifest = {
                "version": 1,
                "export_schema": EXPORT_SCHEMA,
                "decision_label": DECISION_LABEL,
                "scientific_result": False,
                "scientific_candidate_tactics_executed": 0,
                "entries": entries,
                "entries_sha256": json_sha256(entries),
                "decision_sha256": file_sha256(summaryp),
                "claim_boundary": decision["claim_boundary"],
            }
            zf.writestr(
                "MANIFEST.json",
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            )

        with zipfile.ZipFile(tmp, "r") as zf:
            manifest = json.loads(zf.read("MANIFEST.json"))
            if manifest["entries_sha256"] != json_sha256(entries):
                raise ValueError("bundle manifest identity changed")
            for entry in entries:
                digest = hashlib.sha256()
                size = 0
                with zf.open(entry["path"]) as handle:
                    for block in iter(lambda: handle.read(1 << 20), b""):
                        digest.update(block)
                        size += len(block)
                if size != entry["bytes"] or digest.hexdigest() != entry["sha256"]:
                    raise ValueError(f"bundle member verification failed: {entry['path']}")
        os.replace(tmp, output)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise

    value = {
        "version": 1,
        "export_schema": EXPORT_SCHEMA,
        "bundle": str(output),
        "bundle_sha256": file_sha256(output),
        "bundle_bytes": output.stat().st_size,
        "manifest_entries": len(entries),
        "all_manifest_entries_verified": True,
        "decision_label": DECISION_LABEL,
        "repositories_passed": decision["repositories_passed"],
        "minimum_required": decision["minimum_required"],
        "current_frame_upper_bound": decision["current_frame_upper_bound"],
        "scientific_candidate_tactics_executed": 0,
    }
    atomic_json_dump(value, receiptp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ARTIFACT_ROOT))
    parser.add_argument(
        "--output",
        default=str(
            SERVER_ROOT / "exports/experiment51_recruitment_nogo_fix9_fix3_results.zip"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    export(parse_args())
