"""Build the deterministic code-only Exp58-No-Go/Exp59 transition archive."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from experiment59_protocol import *


def build(output: Path) -> dict[str, Any]:
    package_files = [
        path for path in sorted(PACKAGE_ROOT.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name != "PACKAGE_MANIFEST.json" and path.suffix not in {".pyc", ".zip"}
    ]
    entries = [
        {
            "path": f"{PACKAGE_ROOT.name}/{path.name}",
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
        for path in package_files
    ]
    manifest = {
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "package": PACKAGE_ROOT.name,
        "code_only": True,
        "contains_exp58_scientific_reinterpretation": False,
        "contains_exp59_candidate_execution_runner": True,
        "contains_exp59_continuation_runner": False,
        "entries": entries,
        "entries_sha256": json_sha256(entries),
    }
    manifest_path = PACKAGE_ROOT / "PACKAGE_MANIFEST.json"
    atomic_json_dump(manifest, manifest_path)
    sources = [(path, f"{PACKAGE_ROOT.name}/{path.name}") for path in package_files]
    sources.append((manifest_path, f"{PACKAGE_ROOT.name}/PACKAGE_MANIFEST.json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, arcname in sources:
            info = zipfile.ZipInfo(arcname, date_time=(2026, 8, 28, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    temporary.replace(output)
    with zipfile.ZipFile(output) as archive:
        verified = all(bytes_sha256(archive.read(arcname)) == file_sha256(path) for path, arcname in sources)
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "bundle": str(output),
        "bundle_sha256": file_sha256(output),
        "bundle_bytes": output.stat().st_size,
        "manifest_entries": len(entries),
        "all_manifest_entries_verified": verified,
        "contains_exp59_continuation_runner": False,
        "candidate_only_tactics_executed": 0,
        "continuation_probes_executed": 0,
    })
    atomic_json_dump(value, output.with_suffix(".receipt.json"))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(WORKSPACE_ROOT / "experiment58_nogo_exp59_expansion_only_transition_python_only.zip"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(build(Path(parse_args().output).resolve()), indent=2))
