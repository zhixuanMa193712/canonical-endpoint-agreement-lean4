"""Build deterministic Python-only Exp59 confirmation package."""
from __future__ import annotations

import json
import subprocess
import sys
import zipfile

from experiment59_confirmation_protocol import *

ARCHIVE = WORKSPACE_ROOT / "experiment59_four_policy_confirmation_execution_python_only.zip"


def build() -> dict:
    test = subprocess.run([sys.executable, str(PACKAGE_ROOT / "test_experiment59_confirmation_static.py")],
                          cwd=PACKAGE_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if test.returncode != 0: raise RuntimeError(test.stderr or test.stdout)
    test_result = json.loads(test.stdout)
    members = sorted(path for path in PACKAGE_ROOT.iterdir() if path.is_file() and path.name != "PACKAGE_MANIFEST.json")
    manifest = {"version": VERSION, "package": "experiment59-four-policy-confirmation-execution",
        "confirmation_protocol_version": CONFIRMATION_PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID, "python_only": True, "static_test": test_result,
        "files": [{"path": path.name, "bytes": path.stat().st_size, "sha256": file_sha256(path)} for path in members]}
    atomic_json_dump(manifest, PACKAGE_ROOT / "PACKAGE_MANIFEST.json"); members.append(PACKAGE_ROOT / "PACKAGE_MANIFEST.json")
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(members, key=lambda item: item.name):
            info = zipfile.ZipInfo(f"{PACKAGE_ROOT.name}/{path.name}", date_time=(2026, 8, 28, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    result = {"archive": str(ARCHIVE), "archive_bytes": ARCHIVE.stat().st_size,
        "archive_sha256": file_sha256(ARCHIVE), "manifest_entries": len(members),
        "all_static_checks_passed": test_result["all_static_checks_passed"],
        "lean_executed": False, "continuation_probes_executed": 0}
    print(json.dumps(result, indent=2)); return result


if __name__ == "__main__": build()
