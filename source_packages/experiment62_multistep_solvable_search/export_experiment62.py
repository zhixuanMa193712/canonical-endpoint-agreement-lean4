"""Export audited Exp62 confirmation code and receipts as one immutable ZIP."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

from experiment62_protocol import *


def export(root: Path, output: Path) -> dict[str, Any]:
    audit = read_json(root / "confirmation/audit/summary.json")
    assert_sealed(audit, "Exp62 confirmation audit")
    if audit.get("audit_passed") is not True:
        raise ValueError("Exp62 confirmation audit did not pass")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError("Exp62 export overwrite is forbidden")
    files = []
    for path in sorted(PACKAGE_ROOT.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            files.append((path, Path(PACKAGE_ROOT.name) / path.relative_to(PACKAGE_ROOT)))
    for path in sorted(root.rglob("*")):
        if path.is_file() and "runtime" not in path.parts and path.suffix != ".tmp":
            files.append((path, Path("artifacts/v62/multistep_solvable_search") / path.relative_to(root)))
    manifest_rows = [
        {"archive_member": str(member), "bytes": path.stat().st_size, "sha256": file_sha256(path)}
        for path, member in files
    ]
    manifest = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "files": len(files),
        "entries": manifest_rows,
        "confirmation_audit_sha256": file_sha256(root / "confirmation/audit/summary.json"),
    })
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, member in files:
            archive.write(path, str(member))
        archive.writestr("EXP62_EXPORT_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    receipt = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "output": str(output),
        "bytes": output.stat().st_size,
        "sha256": file_sha256(output),
        "files": len(files),
        "audit_passed": True,
    })
    atomic_json_dump(receipt, root / "confirmation/export/receipt.json")
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument(
        "--output",
        default=str(WORKSPACE_ROOT / "exports/experiment62_multistep_solvable_search_results.zip"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(export(
        Path(args.artifact_root).resolve(), Path(args.output).resolve()
    ), indent=2))
