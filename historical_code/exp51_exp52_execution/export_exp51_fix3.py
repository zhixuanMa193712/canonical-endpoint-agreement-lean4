"""Export and twice verify the completed Exp51 Fix3 evidence bundle.

This exporter is offline: it invokes neither Lean nor a scientific worker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from alignment_protocol import *  # noqa: F401,F403


EXPORT_SCHEMA = "experiment51-scientific-execution-fix3-export-v1"


def artifact_role(relative: Path) -> str:
    parts = relative.parts
    if parts and parts[0] == "frozen":
        return "frozen_configuration_or_receipt"
    if len(parts) >= 4 and parts[:2] == ("scientific", "shards"):
        return "scientific_shard_execution_artifact"
    if parts and parts[0] == "scientific":
        return "scientific_execution_summary_or_index"
    if parts and parts[0] == "analysis":
        return "frozen_offline_analysis"
    if parts and parts[0] == "audit":
        return "independent_reconstruction_audit"
    if parts and parts[0] in {"preflight", "environment", "smoke"}:
        return "execution_qualification_artifact"
    return "exp51_fix3_artifact"


def validate_completed_chain(root: Path) -> dict[str, Any]:
    source = validate_amendment(root)
    cfg, targets, protocol, amendment = load_source_bundle(root)
    executionp = root / "scientific/summary.json"
    analysisp = root / "analysis/summary.json"
    auditp = root / "audit/summary.json"
    for path in (executionp, analysisp, auditp):
        if not path.is_file():
            raise FileNotFoundError(path)
    execution, analysis, audit = (
        read_json(executionp), read_json(analysisp), read_json(auditp)
    )
    amend_sha = source["amendment_sha256"]
    if not (
        execution.get("alignment_version") == EXECUTION_ALIGNMENT_VERSION
        and execution.get("amendment_sha256") == amend_sha
        and execution.get("config_sha256") == source["config_sha256"]
        and execution.get("targets_sha256") == source["targets_sha256"]
        and execution.get("shards_expected") == EXP51_SHARD_COUNT
        and execution.get("root_receipts") == TARGET_ROOTS
        and execution.get("roots_attempted") == TARGET_ROOTS
        and execution.get("all_evaluable_rows_have_23_attempts") is True
        and execution.get("execution_complete") is True
        and execution.get("execution_gate") is True
        and execution.get("manual_reconciliation_count") == 0
        and execution.get("scientific_retry_count") == 0
        and analysis.get("alignment_version") == EXECUTION_ALIGNMENT_VERSION
        and analysis.get("amendment_sha256") == amend_sha
        and analysis.get("execution_summary_sha256") == file_sha256(executionp)
        and analysis.get("config_sha256") == source["config_sha256"]
        and analysis.get("targets_sha256") == source["targets_sha256"]
        and analysis.get("root_receipts") == TARGET_ROOTS
        and analysis.get("manual_reconciliation_count") == 0
        and audit.get("alignment_version") == EXECUTION_ALIGNMENT_VERSION
        and audit.get("amendment_sha256") == amend_sha
        and audit.get("execution_summary_sha256") == file_sha256(executionp)
        and audit.get("analysis_sha256") == file_sha256(analysisp)
        and audit.get("roots_reconstructed") == TARGET_ROOTS
        and audit.get("manual_reconciliation_count") == 0
        and audit.get("audit_pass") is True
    ):
        raise ValueError("completed Exp51 Fix3 evidence chain is not exact")
    base.validate_code_lock(amendment["code_lock"])
    row_ledger = []
    for frozen_index, target in enumerate(targets):
        shard = shard_index(frozen_index, EXP51_SHARD_COUNT)
        rowp = exp51_row_path(root, target).resolve()
        receiptp = (
            root / "scientific/shards" / f"shard-{shard:02d}" / "receipts"
            / safe_slug(target["slug"]) / f"{target['rid']}.json"
        ).resolve()
        if not rowp.is_file() or not receiptp.is_file():
            raise FileNotFoundError(rowp if not rowp.is_file() else receiptp)
        row, receipt = read_json(rowp), read_json(receiptp)
        if not (
            row.get("protocol_version") == base.PROTOCOL_VERSION
            and row.get("mode") == "scientific"
            and row.get("config_sha256") == source["config_sha256"]
            and row.get("theorem_id") == target["theorem_id"]
            and row.get("source_file_sha256") == target["source_file_sha256"]
            and row.get("candidate_order") == target["alternatives"]
            and row.get("record_sha256") == json_sha256({
                key: item for key, item in row.items() if key != "record_sha256"
            })
            and (
                row.get("worker_ok") is not True
                or len(row.get("candidates", [])) == CANDIDATES_PER_ROOT
            )
            and receipt.get("amendment_sha256") == amend_sha
            and receipt.get("phase") == "scientific"
            and receipt.get("frozen_target_index") == frozen_index
            and receipt.get("theorem_id") == target["theorem_id"]
            and receipt.get("target_identity_sha256")
            == target["target_identity_sha256"]
            and receipt.get("worker_row_sha256") == file_sha256(rowp)
            and receipt.get("worker_ok") is (row.get("worker_ok") is True)
            and receipt.get("candidate_attempts")
            == len(row.get("candidates", []))
            and receipt.get("manual_reconciliation_count") == 0
        ):
            raise ValueError(f"Fix3 row/receipt changed: {target['theorem_id']}")
        row_ledger.append({
            "frozen_target_index": frozen_index,
            "shard_index": shard,
            "theorem_id": target["theorem_id"],
            "row": str(rowp),
            "row_sha256": file_sha256(rowp),
            "receipt": str(receiptp),
            "receipt_sha256": file_sha256(receiptp),
        })
    if len(row_ledger) != TARGET_ROOTS:
        raise ValueError("wrong Fix3 scientific row count")
    return {
        **source,
        "config": cfg,
        "targets": targets,
        "protocol": protocol,
        "amendment": amendment,
        "execution": execution,
        "analysis": analysis,
        "audit": audit,
        "execution_path": executionp,
        "analysis_path": analysisp,
        "audit_path": auditp,
        "row_ledger": row_ledger,
    }


def code_arc(path: Path, index: int) -> str:
    resolved = path.resolve()
    roots = (
        (PACKAGE_ROOT, "code/fix3"),
        (BASE_PACKAGE_ROOT, "code/base"),
        (FIX2_PACKAGE_ROOT, "code/fix2"),
        (EXP52_DOCUMENT_ROOT, "design/exp52"),
    )
    for source_root, prefix in roots:
        source_root = source_root.resolve()
        if resolved.is_relative_to(source_root):
            return f"{prefix}/{resolved.relative_to(source_root).as_posix()}"
    return f"code/other_locked/{index:03d}_{resolved.name}"


def export(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    completed = validate_completed_chain(root)
    output = Path(args.output).resolve()
    receiptp = root / "export_fix3/receipt.json"
    if output.is_file():
        if receiptp.is_file():
            receipt = read_json(receiptp)
            if (
                receipt.get("export_schema") == EXPORT_SCHEMA
                and receipt.get("bundle_sha256") == file_sha256(output)
                and receipt.get("audit_sha256")
                == file_sha256(completed["audit_path"])
            ):
                print(json.dumps(receipt, ensure_ascii=False, indent=2))
                return receipt
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    if temporary.exists():
        raise FileExistsError(temporary)
    entries: list[dict[str, Any]] = []
    seen: dict[str, tuple[str, int]] = {}
    official_rows = {
        Path(item["row"]).resolve() for item in completed["row_ledger"]
    }
    official_receipts = {
        Path(item["receipt"]).resolve() for item in completed["row_ledger"]
    }

    def add(archive: zipfile.ZipFile, path: Path, arc: str, role: str) -> None:
        path = path.resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        digest = file_sha256(path)
        if arc in seen:
            if seen[arc] != (digest, path.stat().st_size):
                raise ValueError(f"conflicting Fix3 archive member: {arc}")
            return
        seen[arc] = (digest, path.stat().st_size)
        entry = {
            "path": arc,
            "role": role,
            "sha256": digest,
            "bytes": path.stat().st_size,
        }
        entries.append(entry)
        archive.write(path, arc)

    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED,
            compresslevel=6, allowZip64=True,
        ) as archive:
            # The complete local Exp51 artifact is retained, except export
            # products and the later, separately exported Exp52 phase.
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                if path.resolve() in {output, temporary}:
                    continue
                relative = path.relative_to(root)
                if relative.parts[0] in {"export", "export_fix3", "exp52"}:
                    continue
                resolved = path.resolve()
                if resolved in official_rows:
                    role = "scientific_shard_row"
                elif resolved in official_receipts:
                    role = "scientific_shard_receipt"
                else:
                    role = artifact_role(relative)
                add(
                    archive, path,
                    "artifacts/" + relative.as_posix(),
                    role,
                )
            for index, item in enumerate(
                completed["amendment"]["code_lock"]["files"]
            ):
                path = Path(item["path"])
                if not (
                    path.is_file()
                    and path.stat().st_size == int(item["bytes"])
                    and file_sha256(path) == item["sha256"]
                ):
                    raise ValueError(f"Fix3 code-lock member changed: {path}")
                add(archive, path, code_arc(path, index), "fix3_locked_source")
            for index, item in enumerate(completed["config"]["code_lock"]["files"]):
                path = Path(item["path"])
                if not (
                    path.is_file()
                    and path.stat().st_size == int(item["bytes"])
                    and file_sha256(path) == item["sha256"]
                ):
                    raise ValueError(f"Fix2 source-lock member changed: {path}")
                add(
                    archive, path,
                    f"code/fix2_source_lock/{index:03d}_{path.name}",
                    "fix2_frozen_source",
                )
            role_counts = Counter(item["role"] for item in entries)
            if not (
                role_counts["scientific_shard_row"] == TARGET_ROOTS
                and role_counts["scientific_shard_receipt"] == TARGET_ROOTS
                and role_counts["frozen_configuration_or_receipt"] > 0
                and role_counts["frozen_offline_analysis"] > 0
                and role_counts["independent_reconstruction_audit"] > 0
                and role_counts["fix3_locked_source"] > 0
            ):
                raise ValueError("Fix3 export evidence classes are incomplete")
            manifest = {
                "version": 1,
                "export_schema": EXPORT_SCHEMA,
                "protocol_version": base.PROTOCOL_VERSION,
                "alignment_version": EXECUTION_ALIGNMENT_VERSION,
                "amendment_sha256": completed["amendment_sha256"],
                "config_sha256": completed["config_sha256"],
                "targets_sha256": completed["targets_sha256"],
                "exp52_protocol_sha256": completed["protocol_sha256"],
                "execution_summary_sha256": file_sha256(
                    completed["execution_path"]
                ),
                "analysis_sha256": file_sha256(completed["analysis_path"]),
                "audit_sha256": file_sha256(completed["audit_path"]),
                "audit_pass": True,
                "decision_label": completed["analysis"]["decision_label"],
                "scientific_rows": len(completed["row_ledger"]),
                "manual_reconciliation_count": 0,
                "entries": entries,
                "entries_sha256": json_sha256(entries),
                "role_counts": dict(sorted(role_counts.items())),
                "claim_boundary": completed["config"]["claim_boundary"],
            }
            archive.writestr(
                "MANIFEST.json",
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
            )
        # Second pass reads compressed members and independently verifies every
        # byte count and digest from the just-written manifest.
        with zipfile.ZipFile(temporary, "r") as archive:
            manifest = json.loads(archive.read("MANIFEST.json"))
            if not (
                manifest.get("entries_sha256") == json_sha256(entries)
                and manifest.get("amendment_sha256")
                == completed["amendment_sha256"]
                and manifest.get("audit_pass") is True
            ):
                raise ValueError("Fix3 export manifest identity changed")
            if len({item["path"] for item in entries}) != len(entries):
                raise ValueError("Fix3 export contains duplicate member paths")
            for entry in entries:
                digest = hashlib.sha256()
                size = 0
                with archive.open(entry["path"]) as handle:
                    for block in iter(lambda: handle.read(1 << 20), b""):
                        digest.update(block)
                        size += len(block)
                if size != entry["bytes"] or digest.hexdigest() != entry["sha256"]:
                    raise ValueError(
                        f"Fix3 bundle member verification failed: {entry['path']}"
                    )
        os.replace(temporary, output)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise
    value = {
        "version": 1,
        "export_schema": EXPORT_SCHEMA,
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "amendment_sha256": completed["amendment_sha256"],
        "bundle": str(output),
        "bundle_sha256": file_sha256(output),
        "bundle_bytes": output.stat().st_size,
        "manifest_entries": len(entries),
        "all_manifest_entries_verified": True,
        "scientific_rows": TARGET_ROOTS,
        "execution_summary_sha256": file_sha256(completed["execution_path"]),
        "analysis_sha256": file_sha256(completed["analysis_path"]),
        "audit_sha256": file_sha256(completed["audit_path"]),
        "audit_pass": True,
        "decision_label": completed["analysis"]["decision_label"],
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
            SERVER_ROOT
            / "exports/experiment51_external_repository_replication_fix3_results.zip"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    export(parse_args())
