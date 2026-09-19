"""Export the aggregate, redistribution-safe Exp58 recruitment No-Go bundle."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from experiment59_protocol import *


EXPORT_SCHEMA = "experiment58-candidate-panel-recruitment-nogo-export-v1"


def export(root: Path, output: Path) -> dict[str, Any]:
    summary_path = root / "recruitment_no_go/summary.json"
    summary = read_json(summary_path)
    assert_sealed(summary, "Exp58 recruitment No-Go")
    if not (
        summary.get("decision_label") == EXP58_NOGO_LABEL
        and summary.get("screening_roots") == EXPECTED_EXP58_SCREENING_ROOTS
        and summary.get("operational_roots") == EXPECTED_EXP58_OPERATIONAL_ROOTS
        and summary.get("candidate_only_tactics_executed") == EXPECTED_EXP58_CANDIDATE_ATTEMPTS
        and summary.get("continuation_probes_executed") == 0
    ):
        raise ValueError("Exp58 recruitment No-Go decision changed")

    files: list[tuple[str, Path]] = []
    for path in sorted(PACKAGE_ROOT.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != "PACKAGE_MANIFEST.json" and path.suffix not in {".pyc", ".zip"}:
            files.append((f"code/{path.name}", path))
    required = [
        root / "frozen/protocol.json",
        root / "frozen/source_frame_receipt.json",
        root / "frozen/complete_source_ledger.jsonl",
        root / "frozen/candidate_screening_frame.jsonl",
        root / "frozen/root_path_and_accounting_fix2.json",
        root / "preflight/benchmark_environment.json",
        root / "preflight/candidate_worker_compile.json",
        summary_path,
        root / "recruitment_no_go/private_receipt_hash_ledger.jsonl",
    ]
    required.extend(sorted((root / "screening/root_path_fix2/shards").glob("shard-*.json")))
    if any(not path.is_file() for path in required):
        raise FileNotFoundError("an aggregate Exp58 No-Go artifact is missing")
    for path in required:
        files.append((f"artifacts/{path.relative_to(root)}", path))
    manifest = [
        {"path": arcname, "bytes": path.stat().st_size, "sha256": file_sha256(path)}
        for arcname, path in files
    ]
    manifest_value = {
        "version": VERSION,
        "export_schema": EXPORT_SCHEMA,
        "decision_label": EXP58_NOGO_LABEL,
        "redistribution_profile": "aggregate-and-provenance-only",
        "target_to_successful_tactic_rows_included": False,
        "generated_proofs_included": False,
        "entries": manifest,
    }
    manifest_path = root / "recruitment_no_go/export_manifest.json"
    atomic_json_dump(manifest_value, manifest_path)
    files.append(("manifest.json", manifest_path))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for arcname, path in files:
            info = zipfile.ZipInfo(arcname, date_time=(2026, 8, 28, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    temporary.replace(output)
    with zipfile.ZipFile(output) as archive:
        verified = all(bytes_sha256(archive.read(name)) == file_sha256(path) for name, path in files)
    value = seal({
        "version": VERSION,
        "export_schema": EXPORT_SCHEMA,
        "bundle": str(output),
        "bundle_sha256": file_sha256(output),
        "bundle_bytes": output.stat().st_size,
        "manifest_entries": len(files),
        "all_manifest_entries_verified": verified,
        "decision_label": EXP58_NOGO_LABEL,
        "screening_roots": summary["screening_roots"],
        "operational_roots": summary["operational_roots"],
        "candidate_only_tactics_executed": summary["candidate_only_tactics_executed"],
        "continuation_probes_executed": 0,
        "target_to_successful_tactic_rows_included": False,
        "generated_proofs_included": False,
        "manual_reconciliation_count": 0,
    })
    atomic_json_dump(value, root / "recruitment_no_go/export_receipt.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(EXP58_ARTIFACT_ROOT))
    parser.add_argument(
        "--output",
        default=str(WORKSPACE_ROOT / "exports/experiment58_candidate_panel_recruitment_nogo_results.zip"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(export(Path(args.artifact_root).resolve(), Path(args.output).resolve()), indent=2))
