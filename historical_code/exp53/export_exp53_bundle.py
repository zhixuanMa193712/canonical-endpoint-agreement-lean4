"""Export an immutable Exp53 result bundle with a verified manifest."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

from exp53_protocol import *


def export(args: argparse.Namespace) -> dict[str, Any]:
    subset, receipt = validate_frozen()
    artifact_root = Path(args.artifact_root).resolve()
    analysis_path = artifact_root / "analysis/summary.json"
    analysis = read_json(analysis_path)
    if analysis.get("decision_label") not in {
        "cross_machine_exact", "cross_machine_mismatch", "invalid_execution"
    }:
        raise ValueError("Exp53 analysis is incomplete")
    files: list[tuple[str, Path]] = []
    for path in sorted(PACKAGE_ROOT.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            files.append((f"code/{path.relative_to(PACKAGE_ROOT)}", path))
    for path in sorted(artifact_root.rglob("*")):
        if path.is_file() and path.name != "receipt.json":
            files.append((f"artifacts/{path.relative_to(artifact_root)}", path))
    manifest = [
        {"path": name, "sha256": file_sha256(path), "bytes": path.stat().st_size}
        for name, path in files
    ]
    manifest_path = artifact_root / "export/manifest.json"
    atomic_json_dump(manifest, manifest_path)
    files.append(("MANIFEST.json", manifest_path))
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, path in files:
            zf.write(path, name)
    with zipfile.ZipFile(output) as zf:
        bad = zf.testzip()
        if bad is not None:
            raise ValueError(f"corrupt exported member: {bad}")
        archived_manifest = json.loads(zf.read("MANIFEST.json").decode("utf-8"))
        exact = all(
            bytes_sha256(zf.read(row["path"])) == row["sha256"]
            and len(zf.read(row["path"])) == row["bytes"]
            for row in archived_manifest
        )
    value = {
        "version": 1,
        "export_schema": "experiment53-cross-machine-subset-export-v1",
        "protocol_version": PROTOCOL_VERSION,
        "freeze_identity_sha256": receipt["identity_sha256"],
        "bundle": str(output),
        "bundle_sha256": file_sha256(output),
        "bundle_bytes": output.stat().st_size,
        "manifest_entries": len(manifest),
        "all_manifest_entries_verified": exact,
        "decision_label": analysis["decision_label"],
        "roots": analysis["roots_recorded"],
        "manual_reconciliation_count": analysis["manual_reconciliation_count"],
    }
    atomic_json_dump(value, artifact_root / "export/receipt.json")
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default="artifacts/v53/cross_machine_subset")
    parser.add_argument(
        "--output", default="exports/experiment53_cross_machine_subset_results.zip"
    )
    return parser.parse_args()


if __name__ == "__main__":
    result = export(parse_args())
    raise SystemExit(0 if result["all_manifest_entries_verified"] else 2)

