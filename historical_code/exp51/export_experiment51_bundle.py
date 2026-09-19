"""Export a self-auditing Exp51 bundle for any completed frozen decision."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile
from pathlib import Path
from typing import Any

from experiment51_protocol import *


def export(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    cfg = read_json(root / "frozen/experiment51_config.json")
    summary = read_json(root / "analysis/summary.json")
    audit = read_json(root / "audit/summary.json")
    targets = read_json(root / "frozen/targets.json")
    validate_code_lock(cfg["code_lock"])
    if audit.get("audit_pass") is not True or audit.get("analysis_sha256") != file_sha256(root / "analysis/summary.json"):
        raise ValueError("independent Exp51 reconstruction audit did not pass")
    if summary.get("decision_label") not in {
        "robust_replication_go", "replication_go", "inconclusive",
        "replication_no_go", "invalid_execution"}:
        raise ValueError("Exp51 analysis has no frozen decision")
    output = Path(args.output).resolve()
    receiptp = root / "export/receipt.json"
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

    def add(zf: zipfile.ZipFile, path: Path, arc: str, role: str) -> None:
        if arc in seen:
            return
        if not path.is_file():
            raise FileNotFoundError(path)
        seen.add(arc)
        entries.append({"path": arc, "role": role, "sha256": file_sha256(path),
                        "bytes": path.stat().st_size})
        zf.write(path, arc)

    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6, allowZip64=True) as zf:
            for path in sorted(x for x in root.rglob("*") if x.is_file() and x != receiptp):
                add(zf, path, "artifacts/" + path.relative_to(root).as_posix(), "exp51_artifact")
            for path in sorted(PACKAGE_ROOT.iterdir()):
                if path.is_file():
                    add(zf, path, "code/" + path.name, "exp51_source_code")
            for key in ("exp49_config", "exp49_analysis", "exp50_summary"):
                path = Path(cfg["source"][key])
                add(zf, path, f"source_controls/{key}.json", "locked_source_control")
            for fix_name in ("fix0", "fix1"):
                diagnostic = cfg["source"][f"superseded_exp51_{fix_name}"]
                add(zf, Path(diagnostic["recruitment_config"]),
                    f"source_controls/exp51_{fix_name}/recruitment_config.json",
                    "superseded_zero-candidate_diagnostic")
                add(zf, Path(diagnostic["build_trace_summary"]),
                    f"source_controls/exp51_{fix_name}/build_trace_summary.json",
                    "superseded_zero-candidate_diagnostic")
                for index, row in enumerate(diagnostic["receipt_ledger"]):
                    add(zf, Path(row["path"]),
                        f"source_controls/exp51_{fix_name}/build_trace_receipts/{index:02d}.json",
                        "superseded_zero-candidate_diagnostic")
            fix2 = cfg["source"]["superseded_exp51_fix2"]
            fix2_root = Path(fix2["root"])
            for row in fix2["artifact_ledger"]:
                path = Path(row["path"])
                add(zf, path,
                    "source_controls/exp51_fix2/artifacts/" + path.relative_to(fix2_root).as_posix(),
                    "superseded_zero-candidate_scalability_diagnostic")
            fix3 = cfg["source"]["superseded_exp51_fix3"]
            fix3_root = Path(fix3["root"])
            for row in fix3["artifact_ledger"]:
                path = Path(row["path"])
                add(zf, path,
                    "source_controls/exp51_fix3/artifacts/" + path.relative_to(fix3_root).as_posix(),
                    "superseded_zero-candidate-enumeration-diagnostic")
            fix4 = cfg["source"]["superseded_exp51_fix4"]
            fix4_root = Path(fix4["root"])
            add(zf, Path(fix4["source_code_package"]),
                "source_controls/exp51_fix4/source_code_package.zip",
                "superseded-zero-candidate-source-code")
            for row in fix4["artifact_ledger"]:
                path = Path(row["path"])
                add(zf, path,
                    "source_controls/exp51_fix4/artifacts/" + path.relative_to(fix4_root).as_posix(),
                    "superseded-zero-candidate-v427-parser-diagnostic")
            fix5 = cfg["source"]["superseded_exp51_fix5"]
            fix5_root = Path(fix5["root"])
            add(zf, Path(fix5["source_code_package"]),
                "source_controls/exp51_fix5/source_code_package.zip",
                "superseded-zero-candidate-source-code")
            for row in fix5["artifact_ledger"]:
                path = Path(row["path"])
                add(zf, path,
                    "source_controls/exp51_fix5/artifacts/" + path.relative_to(fix5_root).as_posix(),
                    "superseded-zero-candidate-capacity-diagnostic")
            fix6 = cfg["source"]["superseded_exp51_fix6"]
            fix6_root = Path(fix6["root"])
            add(zf, Path(fix6["source_code_package"]),
                "source_controls/exp51_fix6/source_code_package.zip",
                "superseded-zero-candidate-source-code")
            for row in fix6["artifact_ledger"]:
                path = Path(row["path"])
                add(zf, path,
                    "source_controls/exp51_fix6/artifacts/" + path.relative_to(fix6_root).as_posix(),
                    "superseded-zero-candidate-parser-topology-diagnostic")
            fix7 = cfg["source"]["superseded_exp51_fix7"]
            fix7_root = Path(fix7["root"])
            add(zf, Path(fix7["source_code_package"]),
                "source_controls/exp51_fix7/source_code_package.zip",
                "superseded-zero-candidate-source-code")
            for row in fix7["artifact_ledger"]:
                path = Path(row["path"])
                add(zf, path,
                    "source_controls/exp51_fix7/artifacts/" + path.relative_to(fix7_root).as_posix(),
                    "superseded-zero-candidate-recovery-contract-diagnostic")
            fix8 = cfg["source"]["superseded_exp51_fix8"]
            fix8_root = Path(fix8["root"])
            add(zf, Path(fix8["source_code_package"]),
                "source_controls/exp51_fix8/source_code_package.zip",
                "superseded-zero-candidate-source-code")
            for row in fix8["artifact_ledger"]:
                path = Path(row["path"])
                add(zf, path,
                    "source_controls/exp51_fix8/artifacts/" + path.relative_to(fix8_root).as_posix(),
                    "superseded-zero-candidate-parser-compatibility-diagnostic")
            for target in targets:
                base = f"selected_live_evidence/{safe_slug(target['slug'])}"
                add(zf, Path(target["checkout"]) / target["file_path"],
                    f"{base}/sources/{target['file_path']}", "selected_repository_source")
                add(zf, Path(target["ast_path"]),
                    f"{base}/ast/{Path(target['file_path']).with_suffix('.ast.json').as_posix()}",
                    "selected_lean_dojo_ast")
                add(zf, Path(target["screening_worker_row"]),
                    f"{base}/authored_screen/{target['rid']}.json", "authored_only_screening_row")
            manifest = {
                "version": 1, "protocol_version": PROTOCOL_VERSION,
                "decision_label": summary["decision_label"],
                "replication_go": summary["replication_go"],
                "robust_replication_go": summary["robust_replication_go"],
                "independent_reconstruction_audit_pass": True,
                "entries": entries, "entries_sha256": json_sha256(entries),
                "claim_boundary": cfg["claim_boundary"],
            }
            zf.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False,
                                                     indent=2, sort_keys=True) + "\n")
        with zipfile.ZipFile(tmp, "r") as zf:
            manifest = json.loads(zf.read("MANIFEST.json"))
            if manifest["entries_sha256"] != json_sha256(entries):
                raise ValueError("manifest identity changed")
            for entry in entries:
                digest, size = hashlib.sha256(), 0
                with zf.open(entry["path"]) as handle:
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
        "bundle": str(output), "bundle_sha256": file_sha256(output),
        "bundle_bytes": output.stat().st_size, "manifest_entries": len(entries),
        "all_manifest_entries_verified": True,
        "decision_label": summary["decision_label"],
        "replication_go": summary["replication_go"],
        "robust_replication_go": summary["robust_replication_go"],
        "independent_reconstruction_audit_pass": True,
    }
    atomic_json_dump(value, receiptp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    p.add_argument("--output", default=str(SERVER_ROOT / "exports/experiment51_external_repository_replication_results.zip"))
    return p.parse_args()


if __name__ == "__main__":
    export(parse_args())
