"""Export and verify the immutable Exp57 evidence bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from experiment57_protocol import *


EXPORT_SCHEMA = "experiment57-four-policy-depth2-search-audit-export-v1"


def bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def export(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.artifact_root).resolve()
    design = load_design(root)
    analysis = read_json(root / "analysis/summary.json")
    audit = read_json(root / "audit/summary.json")
    assert_sealed(analysis, "Exp57 analysis")
    assert_sealed(audit, "Exp57 audit")
    if analysis.get("analysis_gate") is not True:
        raise ValueError("Exp57 export requires a passing analysis gate")
    if audit.get("audit_pass") is not True:
        raise ValueError("Exp57 export requires a passing independent audit")
    if audit.get("decision_label_preserved") != analysis.get("decision_label"):
        raise ValueError("Exp57 audited decision label changed")

    package = Path(__file__).resolve().parent
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    files: list[tuple[str, Path]] = []
    for path in sorted(package.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != "PACKAGE_MANIFEST.json":
            files.append((f"code/{path.name}", path))
    for path in sorted(root.rglob("*"), key=lambda item: str(item)):
        if path.is_file() and not path.is_relative_to(root / "export"):
            files.append((f"artifacts/{path.relative_to(root)}", path))

    arcnames = [arcname for arcname, _ in files]
    if len(arcnames) != len(set(arcnames)):
        raise ValueError("Exp57 export contains duplicate archive paths")

    manifest = [
        {
            "path": arcname,
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
        for arcname, path in files
    ]
    manifest_path = root / "export/manifest.json"
    atomic_json_dump(
        {
            "version": VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "export_schema": EXPORT_SCHEMA,
            "entries": manifest,
        },
        manifest_path,
    )
    files.append(("manifest.json", manifest_path))

    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for arcname, path in files:
            archive.write(path, arcname)

    verified = True
    with zipfile.ZipFile(output) as archive:
        if set(archive.namelist()) != {arcname for arcname, _ in files}:
            verified = False
        else:
            for arcname, path in files:
                if bytes_sha256(archive.read(arcname)) != file_sha256(path):
                    verified = False
                    break

    metrics = {row["policy"]: row for row in analysis["policy_metrics"]}
    value = {
        "version": VERSION,
        "export_schema": EXPORT_SCHEMA,
        "protocol_version": PROTOCOL_VERSION,
        "bundle": str(output),
        "bundle_sha256": file_sha256(output),
        "bundle_bytes": output.stat().st_size,
        "manifest_entries": len(files),
        "all_manifest_entries_verified": verified,
        "roots": design["roots"],
        "jobs": design["jobs"],
        "cells": sum(row["process_calls"] for row in analysis["policy_metrics"]),
        "full_process_calls": metrics["full"]["process_calls"],
        "effect_aware_process_calls": metrics["effect_aware"]["process_calls"],
        "full_selected_depth2_branches": metrics["full"]["selected_depth2_branches"],
        "effect_aware_selected_depth2_branches": metrics["effect_aware"][
            "selected_depth2_branches"
        ],
        "decision_label": analysis["decision_label"],
        "independent_reconstruction_audit_pass": audit["audit_pass"],
        "scientific_retry_count": analysis["scientific_retry_count"],
        "manual_reconciliation_count": analysis["manual_reconciliation_count"],
    }
    atomic_json_dump(value, root / "export/receipt.json")
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument(
        "--output",
        default=str(
            WORKSPACE_ROOT
            / "exports/experiment57_end_to_end_search_benchmark_results.zip"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    export(parse_args())
