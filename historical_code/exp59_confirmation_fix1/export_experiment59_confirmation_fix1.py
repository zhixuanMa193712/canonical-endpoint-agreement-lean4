"""Export immutable audited Exp59 confirmation Fix1 evidence."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

from experiment59_confirmation_fix1_protocol import *


def _artifact_files(root: Path) -> list[Path]:
    files = []
    confirmation = root / "confirmation"
    for path in confirmation.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(confirmation)
        if (
            relative.parts[0] == "export"
            or relative.parts[:2] == ("fix1", "export")
        ):
            continue
        files.append(path)
    return sorted(files)


def export(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    output = Path(output).resolve()
    amendment = validate_fix1_amendment(root)
    execution_path = root / FIX1_RELATIVE / "execution/summary.json"
    analysis_path = root / FIX1_RELATIVE / "analysis/summary.json"
    audit_path = root / FIX1_RELATIVE / "audit/summary.json"
    execution = read_json(execution_path)
    analysis = read_json(analysis_path)
    audit = read_json(audit_path)
    assert_sealed(execution, "Fix1 export execution")
    assert_sealed(analysis, "Fix1 export analysis")
    assert_sealed(audit, "Fix1 export audit")
    if not (
        audit.get("audit_pass") is True
        and audit.get("decision_label_preserved") == analysis.get("decision_label")
        and analysis.get("analysis_gate") is True
        and analysis.get("registered_joint_gate") is False
        and analysis.get("coverage_estimand", {}).get("registered_coverage_gate")
        is False
    ):
        raise ValueError("Exp59 confirmation Fix1 audit or claim boundary failed")

    entries = []
    for path in _artifact_files(root):
        entries.append({
            "source": str(path),
            "archive_path": (
                "artifacts/confirmation/"
                + str(path.relative_to(root / "confirmation"))
            ),
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        })
    for path in sorted(PACKAGE_ROOT.iterdir()):
        if path.is_file():
            entries.append({
                "source": str(path),
                "archive_path": "code/" + path.name,
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            })
    archive_paths = [row["archive_path"] for row in entries]
    if len(archive_paths) != len(set(archive_paths)):
        raise ValueError("Fix1 export archive paths are not unique")

    manifest = {
        "version": FIX1_VERSION,
        "export_schema": "experiment59-four-policy-confirmation-fix1-manifest-v1",
        "fix1_protocol_version": FIX1_PROTOCOL_VERSION,
        "mechanical_fix_id": FIX1_MECHANICAL_ID,
        "decision_label": analysis["decision_label"],
        "registered_joint_gate": False,
        "locked_operational_anomaly_cells": 3,
        "coverage_unevaluable_roots": 1,
        "entries": entries,
    }
    manifest_path = root / FIX1_RELATIVE / "export/manifest.json"
    atomic_json_dump(manifest, manifest_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        archive.write(manifest_path, "MANIFEST.json")
        for row in entries:
            archive.write(row["source"], row["archive_path"])

    verified = all(
        Path(row["source"]).stat().st_size == row["bytes"]
        and file_sha256(row["source"]) == row["sha256"]
        for row in entries
    )
    value = seal({
        "version": FIX1_VERSION,
        "export_schema": "experiment59-four-policy-confirmation-fix1-export-v1",
        "fix1_protocol_version": FIX1_PROTOCOL_VERSION,
        "mechanical_fix_id": FIX1_MECHANICAL_ID,
        "amendment_sha256": amendment["sha256"],
        "execution_summary_sha256": file_sha256(execution_path),
        "analysis_sha256": file_sha256(analysis_path),
        "audit_sha256": file_sha256(audit_path),
        "bundle": str(output),
        "bundle_sha256": file_sha256(output),
        "bundle_bytes": output.stat().st_size,
        "manifest_entries": len(entries),
        "all_manifest_entries_verified": verified,
        "roots": EXPECTED_ROOTS,
        "jobs": EXPECTED_JOBS,
        "locked_operational_anomaly_cells": 3,
        "coverage_unevaluable_roots": 1,
        "efficiency_evaluable_roots": EXPECTED_ROOTS,
        "coverage_evaluable_roots": EXPECTED_ROOTS - 1,
        "registered_efficiency_gate": analysis["efficiency_estimand"][
            "registered_efficiency_gate"
        ],
        "registered_coverage_gate": False,
        "registered_joint_gate": False,
        "decision_label": analysis["decision_label"],
        "independent_reconstruction_audit_pass": audit["audit_pass"],
        "original_receipts_rewritten": False,
        "lean_executed_by_fix1": False,
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
    })
    atomic_json_dump(value, root / FIX1_RELATIVE / "export/receipt.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument(
        "--output",
        default=str(
            WORKSPACE_ROOT
            / "exports/experiment59_four_policy_confirmation_fix1_results.zip"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(export(Path(args.artifact_root), Path(args.output)), indent=2))
