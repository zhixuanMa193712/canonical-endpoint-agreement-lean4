"""Export the versioned Exp50 analysis-fix1 audit bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile
from pathlib import Path
from typing import Any

from experiment50_protocol import *


def export(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    cfg = read_json(root / "frozen/experiment50_config.json")
    summary = read_json(root / "analysis_fix1/summary.json")
    amendment = read_json(root / "analysis_fix1/amendment.json")
    validate_code_lock(cfg["code_lock"])
    if summary.get("reexecution_pass") is not True or summary.get("analysis_fix1_pass") is not True:
        raise ValueError("Exp50 analysis-fix1 gate did not pass")
    if file_sha256(amendment["fix_script"]) != amendment["fix_script_sha256"]:
        raise ValueError("Exp50 analysis-fix1 script changed")
    if amendment.get("execution_rows_modified") != 0 or amendment.get("lean_processes_executed") != 0:
        raise ValueError("invalid Exp50 amendment scope")
    output = Path(args.output).resolve()
    receiptp = root / "export_fix1/receipt.json"
    if output.exists():
        if receiptp.is_file() and read_json(receiptp).get("bundle_sha256") == file_sha256(output):
            value = read_json(receiptp)
            print(json.dumps(value, ensure_ascii=False, indent=2))
            return value
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_name(output.name + ".tmp")
    if tmp.exists():
        raise FileExistsError(tmp)
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_file(zf: zipfile.ZipFile, path: Path, arcname: str, role: str) -> None:
        if arcname in seen:
            raise ValueError(f"duplicate bundle path: {arcname}")
        if not path.is_file():
            raise FileNotFoundError(path)
        seen.add(arcname)
        entries.append({"path": arcname, "role": role, "sha256": file_sha256(path),
                        "bytes": path.stat().st_size})
        zf.write(path, arcname)

    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6, allowZip64=True) as zf:
            for path in sorted(x for x in root.rglob("*") if x.is_file()):
                if path == receiptp:
                    continue
                add_file(zf, path, "artifacts/" + path.relative_to(root).as_posix(),
                         "exp50_artifact_including_preserved_original_analysis")
            for path in sorted(PACKAGE_ROOT.iterdir()):
                if path.is_file():
                    add_file(zf, path, "code/" + path.name, "exp50_source_code")
            controls = {
                "exp48_config": "source_controls/exp48_config.json",
                "exp48_summary": "source_controls/exp48_confirmation_summary.json",
                "exp49_config": "source_controls/exp49_config.json",
                "exp49_validation": "source_controls/exp49_validation_execution_summary.json",
                "exp49_analysis": "source_controls/exp49_analysis_summary.json",
            }
            for key, arcname in controls.items():
                add_file(zf, Path(cfg["source"][key]), arcname, "locked_source_control")
            for target in read_json(root / "frozen/targets.json"):
                base = f"source_theorem_evidence/{safe_slug(target['slug'])}/{target['rid']}"
                add_file(zf, Path(target["source_exp48_row"]), base + ".exp48.json",
                         "locked_exp48_theorem_row")
                add_file(zf, Path(target["source_exp48_raw"]), base + ".exp48.lean.json",
                         "locked_exp48_raw_worker_row")
                add_file(zf, Path(target["source_exp49_row"]), base + ".exp49.json",
                         "locked_exp49_theorem_row")
                add_file(zf, Path(target["source_exp49_raw"]), base + ".exp49.lean.json",
                         "locked_exp49_raw_worker_row")
            manifest = {
                "version": 1, "protocol_version": PROTOCOL_VERSION,
                "analysis_fix_id": summary["fix_id"], "reexecution_pass": True,
                "original_failed_analysis_preserved": True,
                "entries": entries, "entries_sha256": json_sha256(entries),
                "claim_boundary": cfg["claim_boundary"],
            }
            zf.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False,
                                                     indent=2, sort_keys=True) + "\n")
        with zipfile.ZipFile(tmp, "r") as zf:
            archived_manifest = json.loads(zf.read("MANIFEST.json"))
            if archived_manifest.get("entries_sha256") != json_sha256(entries):
                raise ValueError("Exp50 fix1 bundle manifest changed")
            for entry in entries:
                digest, size = hashlib.sha256(), 0
                with zf.open(entry["path"], "r") as handle:
                    for block in iter(lambda: handle.read(1 << 20), b""):
                        digest.update(block)
                        size += len(block)
                if size != entry["bytes"] or digest.hexdigest() != entry["sha256"]:
                    raise ValueError(f"bundle member verification failed: {entry['path']}")
        os.replace(tmp, output)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise
    value = {
        "version": 1, "protocol_version": PROTOCOL_VERSION,
        "analysis_fix_id": summary["fix_id"], "bundle": str(output),
        "bundle_sha256": file_sha256(output), "bundle_bytes": output.stat().st_size,
        "manifest_entries": len(entries), "all_manifest_entries_verified": True,
        "original_failed_analysis_preserved": True, "reexecution_pass": True,
        "independence_limit": summary["independence_limit"],
    }
    atomic_json_dump(value, receiptp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    p.add_argument("--output", default=str(
        SERVER_ROOT / "exports/experiment50_independent_reexecution_fix1_results.zip"))
    return p.parse_args()


if __name__ == "__main__":
    export(parse_args())
