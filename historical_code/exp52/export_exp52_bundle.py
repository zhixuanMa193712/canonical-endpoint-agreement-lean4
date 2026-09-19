"""Export a self-auditing Exp52 continuation-probe evidence bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping

from alignment_protocol import *  # noqa: F401,F403


EXPORT_SCHEMA = "experiment52-continuation-probe-audit-export-fix4-v1"


def _content_references(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if (
            set(("path", "sha256", "bytes")).issubset(value)
            and isinstance(value.get("path"), str)
            and isinstance(value.get("sha256"), str)
        ):
            yield value
        for item in value.values():
            yield from _content_references(item)
    elif isinstance(value, list):
        for item in value:
            yield from _content_references(item)


def export(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    source = validate_amendment(root)
    exp52_root = root / "exp52"
    analysisp = exp52_root / "analysis/summary.json"
    auditp = exp52_root / "audit/summary.json"
    selectionp = exp52_root / "selection/summary.json"
    executionp = exp52_root / "execution/summary.json"
    source_row_ledgerp = exp52_root / "selection/source_exp51_rows.jsonl"
    for path in (analysisp, auditp, selectionp, executionp, source_row_ledgerp):
        if not path.is_file():
            raise FileNotFoundError(path)
    analysis, audit = read_json(analysisp), read_json(auditp)
    allowed = {
        "invalid_execution", "continuation_inconclusive",
        "continuation_support", "continuation_no_go",
    }
    if not (
        analysis.get("decision_label") in allowed
        and analysis.get("amendment_sha256") == source["amendment_sha256"]
        and audit.get("audit_pass") is True
        and audit.get("analysis_sha256") == file_sha256(analysisp)
        and audit.get("decision_label_preserved") == analysis["decision_label"]
        and audit.get("manual_reconciliation_count") == 0
    ):
        raise ValueError("Exp52 independent audit did not validate this analysis")
    output = Path(args.output).resolve()
    receiptp = exp52_root / "export/receipt.json"
    if output.is_file():
        if receiptp.is_file() and read_json(receiptp).get("bundle_sha256") == file_sha256(output):
            value = read_json(receiptp)
            print(json.dumps(value, ensure_ascii=False, indent=2))
            return value
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    if temporary.exists():
        raise FileExistsError(temporary)

    entries: list[dict[str, Any]] = []
    seen_arcs: set[str] = set()
    seen_content: set[str] = set()

    def add(zf: zipfile.ZipFile, path: Path, arc: str, role: str) -> None:
        path = path.resolve()
        if arc in seen_arcs:
            return
        if not path.is_file():
            raise FileNotFoundError(path)
        seen_arcs.add(arc)
        entries.append({
            "path": arc, "role": role, "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        })
        zf.write(path, arc)

    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED,
            compresslevel=6, allowZip64=True,
        ) as archive:
            for path in sorted(item for item in exp52_root.rglob("*")
                               if item.is_file() and item != receiptp):
                add(
                    archive, path,
                    "artifacts/exp52/" + path.relative_to(exp52_root).as_posix(),
                    "exp52_immutable_artifact",
                )
            source_files = {
                "experiment51_config.json": root / SOURCE_CONFIG_RELATIVE,
                "targets.json": root / SOURCE_TARGETS_RELATIVE,
                "experiment52_protocol.json": root / SOURCE_EXP52_PROTOCOL_RELATIVE,
                "fix2_freeze_receipt.json": root / SOURCE_FREEZE_RECEIPT_RELATIVE,
                "fix2_freeze_transaction.json": root / SOURCE_FREEZE_TRANSACTION_RELATIVE,
                "execution_alignment_fix3.json": root / SOURCE_FIX3_AMENDMENT_RELATIVE,
                "execution_alignment_fix3_receipt.json": root / SOURCE_FIX3_RECEIPT_RELATIVE,
                "exp52_compile_compatibility_fix4.json": root / AMENDMENT_RELATIVE,
                "exp52_compile_compatibility_fix4_receipt.json": root / AMENDMENT_RECEIPT_RELATIVE,
                "exp52_failed_fix3_preflight.json": root / EXP52_FAILED_FIX3_PREFLIGHT_RELATIVE,
                "exp52_fix4_preflight.json": root / EXP52_PREFLIGHT_RELATIVE,
                "exp51_scientific_summary.json": root / "scientific/summary.json",
                "exp51_scientific_row_index.jsonl": root / "scientific/row_index.jsonl",
                "exp51_analysis_summary.json": root / "analysis/summary.json",
                "exp51_audit_summary.json": root / "audit/summary.json",
            }
            for name, path in source_files.items():
                add(archive, path, "source_exp51/" + name, "locked_source_control")

            source_rows = read_jsonl(source_row_ledgerp)
            exp51_index = read_jsonl(root / "scientific/row_index.jsonl")
            if len(source_rows) != TARGET_ROOTS:
                raise ValueError("Exp52 source-row ledger no longer accounts for 576 roots")
            if len(exp51_index) != TARGET_ROOTS:
                raise ValueError("Exp51 finalized row index no longer accounts for 576 roots")
            for index, entry in enumerate(exp51_index):
                receipt = Path(entry["receipt"])
                if not (
                    receipt.is_file()
                    and file_sha256(receipt) == entry["receipt_sha256"]
                    and entry["frozen_target_index"] == index
                ):
                    raise ValueError(
                        f"source Exp51 receipt changed: {entry.get('theorem_id')}"
                    )
                add(
                    archive, receipt,
                    f"source_exp51/scientific_receipts/{index:03d}_"
                    f"{safe_slug(entry['theorem_id'])}.json",
                    "source_exp51_scientific_receipt",
                )
            for ledger in source_rows:
                path = Path(ledger["path"])
                if not (
                    path.is_file() and file_sha256(path) == ledger["sha256"]
                    and path.stat().st_size == ledger["bytes"]
                ):
                    raise ValueError(f"source Exp51 row changed: {ledger['theorem_id']}")
                arc = (
                    f"source_exp51/scientific_rows/{ledger['frozen_target_index']:03d}_"
                    f"{safe_slug(ledger['theorem_id'])}.json"
                )
                add(archive, path, arc, "source_exp51_scientific_row")
                row = read_json(path)
                for reference in _content_references(row):
                    content = Path(reference["path"])
                    digest = str(reference["sha256"])
                    if digest in seen_content:
                        continue
                    if not (
                        content.is_file() and file_sha256(content) == digest
                        and content.stat().st_size == int(reference["bytes"])
                    ):
                        raise ValueError(f"source content-store entry changed: {content}")
                    seen_content.add(digest)
                    suffix = content.suffix or ".bin"
                    add(
                        archive, content,
                        f"source_exp51/content_store/{digest[:2]}/{digest}{suffix}",
                        "source_exp51_content_addressed_state",
                    )

            for path in package_code_sources():
                if path.is_relative_to(PACKAGE_ROOT):
                    arc = "code/" + path.relative_to(PACKAGE_ROOT).as_posix()
                    role = "fix4_execution_source"
                else:
                    raise ValueError(f"unclassified Fix4 code-lock path: {path}")
                add(archive, path, arc, role)
            for path in fix3.package_code_sources():
                path = path.resolve()
                if path.is_relative_to(fix3.PACKAGE_ROOT.resolve()):
                    arc = "source_code/fix3/" + path.relative_to(
                        fix3.PACKAGE_ROOT.resolve()
                    ).as_posix()
                    role = "locked_fix3_source"
                elif path.is_relative_to(fix3.EXP52_DOCUMENT_ROOT.resolve()):
                    arc = "design/" + path.relative_to(
                        fix3.EXP52_DOCUMENT_ROOT.resolve()
                    ).as_posix()
                    role = "locked_exp52_design_document"
                else:
                    raise ValueError(f"unclassified Fix3 code-lock path: {path}")
                add(archive, path, arc, role)

            manifest = {
                "version": 1,
                "export_schema": EXPORT_SCHEMA,
                "alignment_version": EXECUTION_ALIGNMENT_VERSION,
                "mechanical_fix_id": EXECUTION_FIX_ID,
                "amendment_sha256": source["amendment_sha256"],
                "exp52_protocol_sha256": source["protocol_sha256"],
                "selection_summary_sha256": file_sha256(selectionp),
                "execution_summary_sha256": file_sha256(executionp),
                "analysis_sha256": file_sha256(analysisp),
                "audit_sha256": file_sha256(auditp),
                "decision_label": analysis["decision_label"],
                "independent_reconstruction_audit_pass": True,
                "manual_reconciliation_count": 0,
                "entries": entries,
                "entries_sha256": json_sha256(entries),
                "claim_boundary": analysis["claim_boundary"],
            }
            archive.writestr(
                "MANIFEST.json",
                json.dumps(manifest, ensure_ascii=False, indent=2,
                           sort_keys=True) + "\n",
            )

        with zipfile.ZipFile(temporary, "r") as archive:
            manifest = json.loads(archive.read("MANIFEST.json"))
            if manifest.get("entries_sha256") != json_sha256(entries):
                raise ValueError("Exp52 export manifest identity changed")
            for entry in entries:
                digest, size = hashlib.sha256(), 0
                with archive.open(entry["path"]) as handle:
                    for block in iter(lambda: handle.read(1 << 20), b""):
                        digest.update(block)
                        size += len(block)
                if digest.hexdigest() != entry["sha256"] or size != entry["bytes"]:
                    raise ValueError(f"bundle member verification failed: {entry['path']}")
        os.replace(temporary, output)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise

    value = {
        "version": 1,
        "export_schema": EXPORT_SCHEMA,
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "mechanical_fix_id": EXECUTION_FIX_ID,
        "bundle": str(output),
        "bundle_sha256": file_sha256(output),
        "bundle_bytes": output.stat().st_size,
        "manifest_entries": len(entries),
        "all_manifest_entries_verified": True,
        "source_exp51_rows": TARGET_ROOTS,
        "source_content_entries": len(seen_content),
        "decision_label": analysis["decision_label"],
        "independent_reconstruction_audit_pass": True,
        "manual_reconciliation_count": 0,
    }
    atomic_json_dump(value, receiptp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(SCIENTIFIC_ROOT))
    parser.add_argument(
        "--output",
        default=str(
            SERVER_ROOT / "exports/experiment52_continuation_probe_fix4_results.zip"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    export(parse_args())
