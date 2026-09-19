"""Build a deterministic code-only server archive with locked Exp49 vendor sources."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from experiment58_protocol import *


def build(output: Path) -> dict[str, Any]:
    protocol_vendor, worker_vendor = vendor_paths()
    validate_vendor()
    package_files = [
        path for path in sorted(PACKAGE_ROOT.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name not in {"PACKAGE_MANIFEST.json"}
        and path.suffix not in {".pyc", ".zip"}
    ]
    entries = []
    sources: list[tuple[Path, str]] = []
    for path in package_files:
        arcname = f"{PACKAGE_ROOT.name}/{path.name}"
        sources.append((path, arcname))
        entries.append({"path": arcname, "bytes": path.stat().st_size, "sha256": file_sha256(path)})
    for path in (protocol_vendor, worker_vendor):
        arcname = f"{PACKAGE_ROOT.name}/vendor/{path.name}"
        sources.append((path, arcname))
        entries.append({"path": arcname, "bytes": path.stat().st_size, "sha256": file_sha256(path)})
    manifest = {
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "package": PACKAGE_ROOT.name, "code_only": True,
        "contains_scientific_results": False,
        "contains_confirmation_execution_runner": False,
        "entries": entries, "entries_sha256": json_sha256(entries),
    }
    manifest_path = PACKAGE_ROOT / "PACKAGE_MANIFEST.json"
    atomic_json_dump(manifest, manifest_path)
    sources.append((manifest_path, f"{PACKAGE_ROOT.name}/PACKAGE_MANIFEST.json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, arcname in sources:
            info = zipfile.ZipInfo(arcname, date_time=(2026, 8, 28, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())
    temporary.replace(output)
    receipt = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "bundle": str(output), "bundle_sha256": file_sha256(output),
        "bundle_bytes": output.stat().st_size, "manifest_entries": len(entries),
        "contains_confirmation_execution_runner": False,
        "candidate_only_tactics_executed": 0, "continuation_probes_executed": 0,
    })
    atomic_json_dump(receipt, output.with_suffix(".receipt.json"))
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(WORKSPACE_ROOT /
                        "experiment58_external_hard_root_efficiency_confirmation_python_only.zip"))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(build(Path(parse_args().output).resolve()), indent=2))
