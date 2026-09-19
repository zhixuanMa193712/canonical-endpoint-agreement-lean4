"""Export immutable audited Exp59 confirmation evidence."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

from experiment59_confirmation_protocol import *


def export(root: Path, output: Path) -> dict[str, Any]:
    analysis = read_json(root / "confirmation/analysis/summary.json")
    audit = read_json(root / "confirmation/audit/summary.json")
    assert_sealed(analysis, "confirmation analysis"); assert_sealed(audit, "confirmation audit")
    if audit.get("audit_pass") is not True: raise ValueError("confirmation audit did not pass")
    artifact_files = sorted(path for path in (root / "confirmation").rglob("*")
                            if path.is_file() and "confirmation/export" not in str(path))
    code_files = sorted(path for path in PACKAGE_ROOT.iterdir() if path.is_file())
    entries = []
    for path in artifact_files:
        entries.append({"source": str(path), "archive_path": "artifacts/confirmation/" + str(path.relative_to(root / "confirmation")),
                        "bytes": path.stat().st_size, "sha256": file_sha256(path)})
    for path in code_files:
        entries.append({"source": str(path), "archive_path": "code/" + path.name,
                        "bytes": path.stat().st_size, "sha256": file_sha256(path)})
    manifest = {"version": VERSION, "confirmation_protocol_version": CONFIRMATION_PROTOCOL_VERSION,
                "decision_label": analysis["decision_label"], "entries": entries}
    manifest_path = root / "confirmation/export/manifest.json"; atomic_json_dump(manifest, manifest_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.write(manifest_path, "MANIFEST.json")
        for row in entries: archive.write(row["source"], row["archive_path"])
    value = seal({"version": VERSION, "export_schema": "experiment59-four-policy-confirmation-export-v1",
        "confirmation_protocol_version": CONFIRMATION_PROTOCOL_VERSION,
        "bundle": str(output), "bundle_sha256": file_sha256(output), "bundle_bytes": output.stat().st_size,
        "manifest_entries": len(entries), "all_manifest_entries_verified": all(
            Path(row["source"]).stat().st_size == row["bytes"] and file_sha256(row["source"]) == row["sha256"] for row in entries),
        "roots": EXPECTED_ROOTS, "jobs": EXPECTED_JOBS, "decision_label": analysis["decision_label"],
        "independent_reconstruction_audit_pass": audit["audit_pass"],
        "manual_reconciliation_count": 0})
    atomic_json_dump(value, root / "confirmation/export/receipt.json"); return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT)); parser.add_argument("--output", default=str(WORKSPACE_ROOT / "exports/experiment59_four_policy_confirmation_results.zip")); return parser.parse_args()


if __name__ == "__main__":
    args = parse_args(); print(json.dumps(export(Path(args.artifact_root).resolve(), Path(args.output).resolve()), indent=2))
