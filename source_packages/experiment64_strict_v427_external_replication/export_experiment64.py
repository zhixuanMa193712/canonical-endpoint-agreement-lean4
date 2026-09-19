"""Create the immutable Exp64 result bundle after its independent audit passes."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

from experiment64_protocol import *


def run(root: Path, output: Path) -> dict[str, Any]:
    auditp = root / "audit/audit.json"
    analysisp = root / "analysis/summary.json"
    protocolp = root / "frozen/protocol.json"
    audit = read_json(auditp)
    assert_sealed(audit, "Exp64 audit")
    if audit.get("audit_passed") is not True:
        raise ValueError("refusing to export an unaudited Exp64 result")
    manifest = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "artifact_root": str(root),
        "protocol_sha256": file_sha256(protocolp),
        "analysis_sha256": file_sha256(analysisp),
        "audit_sha256": file_sha256(auditp),
        "repository_count": REPOSITORY_COUNT,
        "roots": REPOSITORY_COUNT * ROOTS_PER_REPOSITORY,
        "manual_reconciliation_count": 0,
    })
    manifestp = root / "export/manifest.json"
    atomic_json_dump(manifest, manifestp)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for base in (root, PACKAGE_ROOT):
            for path in sorted(base.rglob("*")):
                if not path.is_file() or path.name.endswith(".tmp") or "__pycache__" in path.parts:
                    continue
                try:
                    arcname = path.relative_to(MZX_ROOT)
                except ValueError:
                    prefix = "artifacts/v64/strict_v427_external_replication" if base == root else PACKAGE_ROOT.name
                    arcname = Path(prefix) / path.relative_to(base)
                archive.write(path, arcname=str(arcname))
    temporary.replace(output)
    digest = file_sha256(output)
    sha_path = output.with_suffix(output.suffix + ".sha256")
    sha_path.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    receipt = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "archive": str(output),
        "archive_bytes": output.stat().st_size,
        "archive_sha256": digest,
        "sha256_file": str(sha_path),
        "audit_record_sha256": audit["record_sha256"],
    })
    atomic_json_dump(receipt, root / "export/receipt.json")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument(
        "--output",
        default=str(MZX_ROOT / "exports/experiment64_strict_v427_external_replication_results.zip"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(Path(args.artifact_root).resolve(), Path(args.output).resolve())
