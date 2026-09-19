"""Build deterministic Python-only Exp59 confirmation Fix1 package."""
from __future__ import annotations

import json
import subprocess
import sys
import zipfile

from experiment59_confirmation_fix1_protocol import *


ARCHIVE = (
    WORKSPACE_ROOT
    / "experiment59_four_policy_confirmation_execution_fix1_python_only.zip"
)


def build() -> dict:
    test = subprocess.run(
        [
            sys.executable,
            str(PACKAGE_ROOT / "test_experiment59_confirmation_fix1_static.py"),
        ],
        cwd=PACKAGE_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if test.returncode != 0:
        raise RuntimeError(test.stderr or test.stdout)
    test_result = json.loads(test.stdout)
    members = sorted(
        path for path in PACKAGE_ROOT.iterdir()
        if path.is_file() and path.name != "PACKAGE_MANIFEST.json"
    )
    manifest = {
        "version": FIX1_VERSION,
        "package": "experiment59-four-policy-confirmation-operational-fix1",
        "fix1_protocol_version": FIX1_PROTOCOL_VERSION,
        "mechanical_fix_id": FIX1_MECHANICAL_ID,
        "source_confirmation_protocol_version": CONFIRMATION_PROTOCOL_VERSION,
        "python_only": True,
        "scientific_plan_changed": False,
        "original_receipts_rewritten": False,
        "static_test": test_result,
        "files": [
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for path in members
        ],
    }
    manifest_path = PACKAGE_ROOT / "PACKAGE_MANIFEST.json"
    atomic_json_dump(manifest, manifest_path)
    members.append(manifest_path)
    with zipfile.ZipFile(
        ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(members, key=lambda item: item.name):
            info = zipfile.ZipInfo(
                f"{PACKAGE_ROOT.name}/{path.name}",
                date_time=(2026, 8, 29, 0, 0, 0),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    result = {
        "archive": str(ARCHIVE),
        "archive_bytes": ARCHIVE.stat().st_size,
        "archive_sha256": file_sha256(ARCHIVE),
        "manifest_entries": len(members),
        "all_static_checks_passed": test_result["all_static_checks_passed"],
        "source_files_hash_locked": test_result["source_files_hash_locked"],
        "locked_operational_anomaly_cells": 3,
        "coverage_unevaluable_roots": 1,
        "lean_executed": False,
        "confirmation_cells_executed": 0,
        "continuation_probes_executed": 0,
    }
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    build()
