"""Build the server-side Exp62 Python/frozen-design package."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from experiment62_protocol import *


def build(output: Path) -> dict:
    protocol = load_initial_protocol()
    members = []
    for path in sorted(PACKAGE_ROOT.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        member = Path(PACKAGE_ROOT.name) / path.relative_to(PACKAGE_ROOT)
        members.append((path, member))
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, member in members:
            archive.write(path, str(member))
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "output": str(output),
        "bytes": output.stat().st_size,
        "sha256": file_sha256(output),
        "files": len(members),
        "initial_protocol_record_sha256": protocol["record_sha256"],
    })
    atomic_json_dump(value, output.with_suffix(".receipt.json"))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(WORKSPACE_ROOT / "experiment62_multistep_solvable_search_python_only.zip"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(build(Path(parse_args().output).resolve()), indent=2))
