"""Integrity helpers for the pre-probe Exp52 compile-compatibility Fix4.

Fix4 is downstream of the immutable Fix3 execution amendment.  It preserves
the completed Exp51 execution and the frozen Exp52 selection verbatim, records
the failed Fix3 compile-only preflight, and changes only Lean exception-message
rendering before the first continuation probe is executed.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

PACKAGE_ROOT = Path(__file__).resolve().parent
SERVER_ROOT = Path(os.environ.get("MZX_ROOT", str(PACKAGE_ROOT.parent))).resolve()
FIX3_PACKAGE_ROOT = SERVER_ROOT / "experiment51_exp52_execution_alignment_fix3"
FIX3_PROTOCOL_PATH = FIX3_PACKAGE_ROOT / "alignment_protocol.py"

if not FIX3_PROTOCOL_PATH.is_file():
    raise FileNotFoundError(FIX3_PROTOCOL_PATH)
_spec = importlib.util.spec_from_file_location(
    "_exp51_exp52_execution_alignment_fix3_protocol", FIX3_PROTOCOL_PATH
)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load the immutable Fix3 alignment protocol")
fix3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fix3)

# Re-export the complete frozen protocol surface.  Fix4 overrides only the
# package/code identity and its own amendment/preflight locations below.
for _name in dir(fix3):
    if not _name.startswith("_"):
        globals()[_name] = getattr(fix3, _name)

PACKAGE_ROOT = Path(__file__).resolve().parent
SERVER_ROOT = Path(os.environ.get("MZX_ROOT", str(PACKAGE_ROOT.parent))).resolve()
SCIENTIFIC_ROOT = SERVER_ROOT / fix3.SCIENTIFIC_ARTIFACT_RELATIVE

SOURCE_FIX3_ALIGNMENT_VERSION = fix3.EXECUTION_ALIGNMENT_VERSION
SOURCE_FIX3_FIX_ID = fix3.EXECUTION_FIX_ID
SOURCE_FIX3_AMENDMENT_SHA256 = (
    "8fe2a9653ec6f0547c95380e7344689a1f92e40206866c92a268a923a03e84bb"
)
SOURCE_FIX3_AMENDMENT_RELATIVE = fix3.AMENDMENT_RELATIVE
SOURCE_FIX3_RECEIPT_RELATIVE = fix3.AMENDMENT_RECEIPT_RELATIVE

EXECUTION_ALIGNMENT_VERSION = "experiment52-pre-probe-compile-compatibility-fix4"
EXECUTION_FIX_ID = "exp52-pre-probe-fix4-lean-exception-message-rendering"
AMENDMENT_SCHEMA = "experiment52-pre-probe-compile-compatibility-amendment-v1"
AMENDMENT_RELATIVE = Path("frozen/exp52_compile_compatibility_fix4.json")
AMENDMENT_RECEIPT_RELATIVE = Path(
    "frozen/exp52_compile_compatibility_fix4_receipt.json"
)
EXP52_FAILED_FIX3_PREFLIGHT_RELATIVE = Path("exp52/preflight/worker_compile.json")
EXP52_PREFLIGHT_RELATIVE = Path("exp52/preflight/worker_compile_fix4.json")
EXP52_WORKER_VERSION = "experiment52-live-continuation-worker-fix4-v1"
WORKER_SCHEMA = "experiment52-live-continuation-cell-record-fix4-v1"
INPUT_SCHEMA = "experiment52-live-continuation-cell-input-fix4-v1"
# The checkpoint payload layout is unchanged; retaining its Fix3 schema makes
# the generated Lean-source diff consist solely of the exception renderer.
CHECKPOINT_RAW_SCHEMA = "experiment52-candidate-checkpoint-raw-fix3-v1"
CHECKPOINT_COMPACT_SCHEMA = "experiment52-candidate-checkpoint-compact-fix3-v1"
PROCESS_LAUNCH_SCHEMA = "experiment52-worker-process-launch-fix4-v1"
SOURCE_FIX3_EXP52_LEAN_SOURCE_SHA256 = (
    "c6e426f91a8e8e53d8e68bf7683ae2446f8e39c40aa8750588ab762ab9521988"
)
FIX4_EXP52_LEAN_SOURCE_SHA256 = (
    "0206ec1db910c6a04ca8051671009216e45a4b60523854bceff595055c0c19f1"
)


def package_code_sources() -> list[Path]:
    paths = sorted(PACKAGE_ROOT.glob("*.py"))
    for name in ("README_SERVER.md", "PACKAGE_MANIFEST.json"):
        path = PACKAGE_ROOT / name
        if path.is_file():
            paths.append(path)
    return [path.resolve() for path in paths]


def package_code_lock() -> dict[str, Any]:
    return base.code_lock(package_code_sources())


def _record_sha(value: Mapping[str, Any]) -> str:
    return json_sha256({
        key: item for key, item in value.items() if key != "record_sha256"
    })


def _validate_fix3_failed_preflight(root: Path) -> dict[str, Any]:
    path = root / EXP52_FAILED_FIX3_PREFLIGHT_RELATIVE
    if not path.is_file():
        raise FileNotFoundError(path)
    value = read_json(path)
    rows = list(value.get("repositories", []))
    signature = "failed to synthesize instance of type class\n  ToString Exception"
    if not (
        value.get("schema")
        == "experiment52-execution-worker-compile-preflight-fix3-v1"
        and value.get("alignment_version") == SOURCE_FIX3_ALIGNMENT_VERSION
        and value.get("mechanical_fix_id") == SOURCE_FIX3_FIX_ID
        and value.get("amendment_sha256") == SOURCE_FIX3_AMENDMENT_SHA256
        and value.get("lean_source_sha256")
        == SOURCE_FIX3_EXP52_LEAN_SOURCE_SHA256
        and value.get("compile_gate") is False
        and value.get("repositories_compiled") == TARGET_REPOSITORIES
        and len(rows) == TARGET_REPOSITORIES
        and all(row.get("version_ok") is True for row in rows)
        and all(row.get("compile_ok") is False for row in rows)
        and all(row.get("compile_returncode") == 1 for row in rows)
        and all(signature in str(row.get("stdout_tail", "")) for row in rows)
        and all(
            "Experiment52LiveContinuationWorker.lean:359:36" in
            str(row.get("stdout_tail", "")) for row in rows
        )
        and value.get("launch_resources", {}).get("resource_gate") is True
        and value.get("theorem_sources_elaborated") == 0
        and value.get("candidate_tactics_executed") == 0
        and value.get("continuation_probes_executed") == 0
        and not any(value.get("import_scan", {}).values())
    ):
        raise ValueError("Fix3 failed Exp52 preflight is not the locked compiler diagnostic")
    return {"path": path, "value": value, "sha256": file_sha256(path)}


def _validate_exp51_and_selection(root: Path, source: Mapping[str, Any]) -> dict[str, Any]:
    paths = {
        "exp51_summary": root / "scientific/summary.json",
        "exp51_analysis": root / "analysis/summary.json",
        "exp51_audit": root / "audit/summary.json",
        "exp51_export": root / "export_fix3/receipt.json",
        "selection": root / "exp52/selection/summary.json",
    }
    # Accept the exact paths produced by the frozen Fix3 stack if the two
    # optional Exp51 filenames differ in an installation.
    alternatives = {
        "exp51_analysis": [root / "analysis/summary.json", root / "analysis/fix3_summary.json"],
        "exp51_audit": [root / "audit/summary.json"],
        "exp51_export": [root / "export_fix3/receipt.json"],
    }
    for key, candidates in alternatives.items():
        paths[key] = next((p for p in candidates if p.is_file()), candidates[0])
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    exp51 = read_json(paths["exp51_summary"])
    analysis = read_json(paths["exp51_analysis"])
    audit = read_json(paths["exp51_audit"])
    export = read_json(paths["exp51_export"])
    selection = read_json(paths["selection"])
    plan = root / str(selection.get(
        "execution_cell_plan", "exp52/selection/execution_cells.jsonl"
    ))
    if not plan.is_file():
        raise FileNotFoundError(plan)
    if not (
        exp51.get("alignment_version") == SOURCE_FIX3_ALIGNMENT_VERSION
        and exp51.get("amendment_sha256") == source["amendment_sha256"]
        and exp51.get("roots_expected") == TARGET_ROOTS
        and exp51.get("root_receipts") == TARGET_ROOTS
        and exp51.get("evaluable_roots") == TARGET_ROOTS
        and exp51.get("candidate_attempts_recorded") == TARGET_ROOTS * CANDIDATES_PER_ROOT
        and exp51.get("execution_gate") is True
        and exp51.get("manual_reconciliation_count") == 0
        and analysis.get("decision_label") == "inconclusive"
        and audit.get("audit_pass") is True
        and audit.get("decision_label_preserved") == "inconclusive"
        and export.get("audit_pass") is True
        and export.get("decision_label") == "inconclusive"
        and selection.get("selection_version") == fix3.EXP52_SELECTION_VERSION
        and selection.get("alignment_version") == SOURCE_FIX3_ALIGNMENT_VERSION
        and selection.get("mechanical_fix_id") == SOURCE_FIX3_FIX_ID
        and selection.get("amendment_sha256") == source["amendment_sha256"]
        and selection.get("roots_accounted") == TARGET_ROOTS
        and selection.get("source_exp51_rows") == TARGET_ROOTS
        and selection.get("execution_cells") == 1320
        and selection.get("selection_complete") is True
        and selection.get("manual_replacement_count") == 0
        and selection.get("manual_reconciliation_count") == 0
        and selection.get("execution_cell_plan_sha256") == file_sha256(plan)
    ):
        raise ValueError("completed Exp51 or frozen Exp52 selection changed")
    return {
        "paths": paths,
        "selection": selection,
        "plan": plan,
        "hashes": {key: file_sha256(path) for key, path in paths.items()},
        "plan_sha256": file_sha256(plan),
    }


def _prove_no_exp52_probe_execution(root: Path) -> None:
    forbidden = [
        root / "exp52/execution",
        root / "exp52/analysis",
        root / "exp52/audit",
        root / "exp52/export",
    ]
    found = [str(path) for path in forbidden if path.exists() and any(
        item.is_file() for item in path.rglob("*")
    )]
    if found:
        raise ValueError("Fix4 is too late; Exp52 outcome artifacts exist: " + ",".join(found))


def validate_fix3_source(root: str | Path = SCIENTIFIC_ROOT) -> dict[str, Any]:
    value = fix3.validate_amendment(Path(root).resolve())
    if value.get("amendment_sha256") != SOURCE_FIX3_AMENDMENT_SHA256:
        raise ValueError("source Fix3 amendment differs from the reviewed anchor")
    return value


def validate_amendment(root: str | Path = SCIENTIFIC_ROOT) -> dict[str, Any]:
    root = Path(root).resolve()
    source = validate_fix3_source(root)
    failed = _validate_fix3_failed_preflight(root)
    completed = _validate_exp51_and_selection(root, source)
    path = root / AMENDMENT_RELATIVE
    if not path.is_file():
        raise FileNotFoundError(path)
    value = read_json(path)
    if not (
        value.get("schema") == AMENDMENT_SCHEMA
        and value.get("alignment_version") == EXECUTION_ALIGNMENT_VERSION
        and value.get("mechanical_fix_id") == EXECUTION_FIX_ID
        and value.get("identity_sha256") == identity_sha256(value)
        and value.get("frozen_before_first_continuation_probe") is True
        and value.get("continuation_probes_executed_before_amendment") == 0
        and value.get("source_fix3", {}).get("alignment_version")
        == SOURCE_FIX3_ALIGNMENT_VERSION
        and value.get("source_fix3", {}).get("mechanical_fix_id")
        == SOURCE_FIX3_FIX_ID
        and value.get("source_fix3", {}).get("amendment_sha256")
        == source["amendment_sha256"]
        and value.get("source_fix3", {}).get("failed_preflight_sha256")
        == failed["sha256"]
        and value.get("source_fix3", {}).get("selection_summary_sha256")
        == completed["hashes"]["selection"]
        and value.get("source_fix3", {}).get("execution_cell_plan_sha256")
        == completed["plan_sha256"]
        and value.get("source_fix3", {}).get("exp51_summary_sha256")
        == completed["hashes"]["exp51_summary"]
        and value.get("source_fix3", {}).get("exp51_analysis_sha256")
        == completed["hashes"]["exp51_analysis"]
        and value.get("source_fix3", {}).get("exp51_audit_sha256")
        == completed["hashes"]["exp51_audit"]
        and value.get("source_fix3", {}).get("exp51_export_sha256")
        == completed["hashes"]["exp51_export"]
        and value.get("scope", {}).get("lean_exception_render_sites_changed") == 1
        and value.get("scope", {}).get("source_fix3_lean_source_sha256")
        == SOURCE_FIX3_EXP52_LEAN_SOURCE_SHA256
        and value.get("scope", {}).get("fix4_lean_source_sha256")
        == FIX4_EXP52_LEAN_SOURCE_SHA256
        and value.get("scope", {}).get("generated_lean_diff_exact") is True
        and value.get("scope", {}).get("selection_changed") is False
        and value.get("scope", {}).get("probe_panel_changed") is False
        and value.get("scope", {}).get("endpoint_changed") is False
        and value.get("scope", {}).get("statistics_changed") is False
        and value.get("scope", {}).get("decision_thresholds_changed") is False
    ):
        raise ValueError("Fix4 amendment differs from its frozen compatibility scope")
    base.validate_code_lock(value["code_lock"])
    return {
        **source,
        "source_fix3_amendment": source["amendment"],
        "source_fix3_amendment_sha256": source["amendment_sha256"],
        "failed_fix3_preflight": failed["value"],
        "failed_fix3_preflight_sha256": failed["sha256"],
        "selection_summary": completed["selection"],
        "selection_summary_sha256": completed["hashes"]["selection"],
        "selection_plan_sha256": completed["plan_sha256"],
        "amendment": value,
        "amendment_path": path,
        "amendment_sha256": file_sha256(path),
    }


def load_source_bundle(
    root: str | Path = SCIENTIFIC_ROOT,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    value = validate_amendment(root)
    return value["config"], list(value["targets"]), value["protocol"], value["amendment"]
