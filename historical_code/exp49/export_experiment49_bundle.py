"""Export a self-auditing Exp49 result bundle after frozen analysis completes."""
from __future__ import annotations

import argparse
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from experiment49_protocol import (
    ARTIFACT_ROOT,
    MECHANICAL_FIX_ID,
    PACKAGE_ROOT,
    PROTOCOL_VERSION,
    SERVER_ROOT,
    atomic_json_dump,
    file_sha256,
    json_sha256,
    read_json,
    safe_slug,
    validate_code_lock,
)


def _artifact_entries(root: Path) -> Iterable[tuple[Path, str]]:
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.name.endswith(".tmp"):
            yield p, f"artifacts/{p.relative_to(root)}"


def export(args: argparse.Namespace) -> dict:
    root = Path(args.root).resolve()
    cfgp = root / "frozen/experiment49_config.json"
    cfg = read_json(cfgp)
    if (cfg.get("protocol_version") != PROTOCOL_VERSION
            or cfg.get("mechanical_fix_id") != MECHANICAL_FIX_ID):
        raise ValueError("wrong Exp49 config")
    validate_code_lock(cfg["code_lock"])
    validation = read_json(root / "validation/execution_summary.json")
    analysis = read_json(root / "analysis/summary.json")
    if validation.get("validation_go") is not True:
        raise ValueError("cannot export: Exp49 validation did not pass")
    if analysis.get("theorem_rows") != cfg.get("expected_validation_roots"):
        raise ValueError("cannot export: analysis row count mismatch")

    output = Path(args.output).resolve()
    if output.exists():
        raise FileExistsError(f"never overwrite an Exp49 export: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[Path, str]] = list(_artifact_entries(root))
    for p in sorted(PACKAGE_ROOT.glob("*.py")):
        entries.append((p, f"code/{p.name}"))
    for name in ("README_SERVER.md", "requirements.txt"):
        p = PACKAGE_ROOT / name
        if p.is_file():
            entries.append((p, f"code/{p.name}"))
    source_cfg = Path(cfg["source_exp48_config"])
    source_summary = Path(cfg["source_exp48_confirmation"])
    entries.extend([
        (source_cfg, "source_exp48/frozen/experiment48_config.json"),
        (source_summary, "source_exp48/confirmation_fix1/summary.json"),
    ])
    source_dir = Path(cfg["source_exp48_confirmation_dir"])
    for slug in cfg["confirmation_repositories"]:
        for p in sorted((source_dir / "theorems" / safe_slug(slug)).glob("*.json")):
            entries.append((p, f"source_exp48/confirmation_fix1/theorems/{safe_slug(slug)}/{p.name}"))

    seen: set[str] = set()
    manifest_rows = []
    for path, arcname in entries:
        if arcname in seen:
            continue
        seen.add(arcname)
        manifest_rows.append({"archive_path": arcname, "sha256": file_sha256(path),
                              "bytes": path.stat().st_size, "source": str(path)})
    manifest = {
        "version": 1, "protocol_version": PROTOCOL_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "config_sha256": file_sha256(cfgp),
        "validation_summary_sha256": file_sha256(root / "validation/execution_summary.json"),
        "analysis_summary_sha256": file_sha256(root / "analysis/summary.json"),
        "source_exp48_confirmation_sha256": cfg["source_exp48_confirmation_sha256"],
        "files": manifest_rows,
    }
    manifest["manifest_identity_sha256"] = json_sha256(
        {k: v for k, v in manifest.items() if k != "created_utc"}
    )
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        written: set[str] = set()
        for path, arcname in entries:
            if arcname in written:
                continue
            written.add(arcname)
            zf.write(path, arcname)
        zf.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    receipt = {
        "version": 1, "protocol_version": PROTOCOL_VERSION,
        "bundle": str(output), "bundle_sha256": file_sha256(output),
        "bundle_bytes": output.stat().st_size,
        "manifest_identity_sha256": manifest["manifest_identity_sha256"],
        "files": len(manifest_rows),
    }
    atomic_json_dump(receipt, output.with_suffix(output.suffix + ".receipt.json"))
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return receipt


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    p.add_argument("--output", default=str(SERVER_ROOT / "exports/experiment49_candidate_endpoint_robustness_results.zip"))
    return p.parse_args()


if __name__ == "__main__":
    export(parse_args())
