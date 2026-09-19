"""Export and verify the immutable Exp54 evidence bundle."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

from experiment54_protocol import *


def export(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.artifact_root).resolve()
    frozen = load_freeze(root)
    audit = read_json(root / "audit/summary.json")
    analysis = read_json(root / "analysis/summary.json")
    if audit.get("audit_pass") is not True:
        raise ValueError("Exp54 export requires passing independent audit")
    package = Path(__file__).resolve().parent
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files: list[tuple[str, Path]] = []
    for path in sorted(package.iterdir()):
        if path.is_file() and path.name != "PACKAGE_MANIFEST.json":
            files.append((f"code/{path.name}", path))
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_relative_to(root / "export"):
            files.append((f"artifacts/{path.relative_to(root)}", path))
    manifest = [
        {
            "path": arcname,
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
        for arcname, path in files
    ]
    manifest_path = root / "export/manifest.json"
    atomic_json_dump({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "execution_version": EXECUTION_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "entries": manifest,
    }, manifest_path)
    files.append(("manifest.json", manifest_path))
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as zf:
        for arcname, path in files:
            zf.write(path, arcname)
    verified = True
    with zipfile.ZipFile(output) as zf:
        for arcname, path in files:
            if bytes_sha256(zf.read(arcname)) != file_sha256(path):
                verified = False
                break
    value = {
        "version": VERSION,
        "export_schema": "experiment54-effect-aware-depth2-audit-export-fix3-v1",
        "protocol_version": PROTOCOL_VERSION,
        "execution_version": EXECUTION_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "bundle": str(output),
        "bundle_sha256": file_sha256(output),
        "bundle_bytes": output.stat().st_size,
        "manifest_entries": len(files),
        "all_manifest_entries_verified": verified,
        "roots": frozen["roots"],
        "witness_pairs": frozen["witness_pairs"],
        "control_pairs": frozen["control_pairs"],
        "full_calls": analysis["search_efficiency"]["full_downstream_calls"],
        "dedup_calls": analysis["search_efficiency"]["dedup_downstream_calls"],
        "decision_label": analysis["decision_label"],
        "independent_reconstruction_audit_pass": audit["audit_pass"],
        "manual_reconciliation_count": 0,
    }
    atomic_json_dump(value, root / "export/receipt.json")
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--artifact-root", default=str(artifact_root()))
    p.add_argument(
        "--output",
        default=str(
            server_root()
            / "exports/experiment54_effect_aware_depth2_fix3_results.zip"
        ),
    )
    return p.parse_args()


if __name__ == "__main__":
    export(parse_args())
