"""Compile-only Exp52 execution preflight in all 12 frozen repositories.

This stage compiles definitions only.  It elaborates no theorem source and
executes neither an Exp51 candidate nor an Exp52 continuation probe.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

from alignment_protocol import *  # noqa: F401,F403
from experiment52_live_worker import (
    LEAN_FILE_NAME,
    LEAN_SOURCE,
    LEAN_SOURCE_SHA256,
)


PREFLIGHT_SCHEMA = "experiment52-execution-worker-compile-preflight-fix4-v1"
MINIMUM_AVAILABLE_MEMORY_GB = 64
MINIMUM_FREE_DISK_GB = 50


def _record_sha(value: Mapping[str, Any]) -> str:
    return json_sha256({
        key: item for key, item in value.items() if key != "record_sha256"
    })


def _resource_receipt(root: Path) -> dict[str, Any]:
    """Capture a read-only launch-capacity receipt before any probe runs."""
    meminfo: dict[str, int] = {}
    path = Path("/proc/meminfo")
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if ":" not in line:
                continue
            key, raw = line.split(":", 1)
            fields = raw.strip().split()
            if fields and fields[0].isdigit():
                meminfo[key] = int(fields[0])
    available_gb = meminfo.get("MemAvailable", 0) / 1024 ** 2
    disk = shutil.disk_usage(root)
    free_disk_gb = disk.free / 1024 ** 3
    logical_cpus = os.cpu_count() or 0
    return {
        "logical_cpus_visible": logical_cpus,
        "memory_available_gb": available_gb,
        "disk_free_gb": free_disk_gb,
        "minimum_available_memory_gb": MINIMUM_AVAILABLE_MEMORY_GB,
        "minimum_free_disk_gb": MINIMUM_FREE_DISK_GB,
        "resource_gate": bool(
            logical_cpus >= EXP52_SHARD_COUNT
            and available_gb >= MINIMUM_AVAILABLE_MEMORY_GB
            and free_disk_gb >= MINIMUM_FREE_DISK_GB
        ),
    }


def _validate_exp51_completion(root: Path, source: Mapping[str, Any]) -> dict[str, Any]:
    path = root / "scientific/summary.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    value = read_json(path)
    row_index = root / str(value.get("row_index", "scientific/row_index.jsonl"))
    if not (
        value.get("alignment_version") == SOURCE_FIX3_ALIGNMENT_VERSION
        and value.get("amendment_sha256")
        == source["source_fix3_amendment_sha256"]
        and value.get("config_sha256") == source["config_sha256"]
        and value.get("targets_sha256") == source["targets_sha256"]
        and value.get("shards_expected") == EXP51_SHARD_COUNT
        and value.get("roots_expected") == TARGET_ROOTS
        and value.get("root_receipts") == TARGET_ROOTS
        and value.get("roots_attempted") == TARGET_ROOTS
        and value.get("all_evaluable_rows_have_23_attempts") is True
        and value.get("execution_complete") is True
        and value.get("execution_gate") is True
        and value.get("manual_reconciliation_count") == 0
        and value.get("scientific_retry_count") == 0
        and row_index.is_file()
        and file_sha256(row_index) == value.get("row_index_sha256")
    ):
        raise ValueError("Exp51 Fix3 scientific execution is not complete and locked")
    return value


def _validate_selection(root: Path, source: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], Path]:
    summaryp = root / "exp52/selection/summary.json"
    if not summaryp.is_file():
        raise FileNotFoundError(summaryp)
    summary = read_json(summaryp)
    cellp = root / str(summary.get(
        "execution_cell_plan", "exp52/selection/execution_cells.jsonl"
    ))
    if not cellp.is_file():
        raise FileNotFoundError(cellp)
    cells = read_jsonl(cellp)
    identities = [str(row.get("cell_id")) for row in cells]
    if not (
        summary.get("selection_version") == fix3.EXP52_SELECTION_VERSION
        and summary.get("alignment_version") == SOURCE_FIX3_ALIGNMENT_VERSION
        and summary.get("mechanical_fix_id") == SOURCE_FIX3_FIX_ID
        and summary.get("amendment_sha256")
        == source["source_fix3_amendment_sha256"]
        and summary.get("exp51_config_sha256") == source["config_sha256"]
        and summary.get("exp51_targets_sha256") == source["targets_sha256"]
        and summary.get("exp52_protocol_sha256") == source["protocol_sha256"]
        and summary.get("roots_accounted") == TARGET_ROOTS
        and summary.get("source_exp51_rows") == TARGET_ROOTS
        and summary.get("selection_complete") is True
        and summary.get("manual_replacement_count") == 0
        and summary.get("manual_reconciliation_count") == 0
        and summary.get("execution_cells") == len(cells)
        and file_sha256(cellp) == summary.get("execution_cell_plan_sha256")
        and len(identities) == len(set(identities))
        and all(
            row.get("record_sha256") == _record_sha(row)
            and row.get("fresh_process_required") is True
            and row.get("scientific_retry_permitted") is False
            and row.get("manual_reconciliation_count") == 0
            for row in cells
        )
    ):
        raise ValueError("Exp52 immutable selection/cell plan is not exact")
    return summary, cells, cellp


def _compile_one(
    repository: Mapping[str, Any], lean_file: Path, timeout: int
) -> dict[str, Any]:
    project = Path(repository["checkout"]).resolve()
    version = subprocess.run(
        ["lake", "env", "lean", "--version"],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    compiled = subprocess.run(
        ["lake", "env", "lean", str(lean_file)],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    version_text = (version.stdout + "\n" + version.stderr).strip()
    return {
        "slug": repository["slug"],
        "project": str(project),
        "lean_version": version_text,
        "version_ok": version.returncode == 0 and "version 4.27.0" in version_text,
        "compile_returncode": compiled.returncode,
        "compile_ok": compiled.returncode == 0,
        "stdout_tail": compiled.stdout[-4000:],
        "stderr_tail": compiled.stderr[-8000:],
    }


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    source = validate_amendment(root)
    exp51 = _validate_exp51_completion(root, source)
    selection, cells, cellp = _validate_selection(root, source)
    outp = root / EXP52_PREFLIGHT_RELATIVE
    if outp.is_file():
        existing = read_json(outp)
        if not (
            existing.get("amendment_sha256") == source["amendment_sha256"]
            and existing.get("execution_cell_plan_sha256") == file_sha256(cellp)
            and existing.get("lean_source_sha256") == LEAN_SOURCE_SHA256
            and existing.get("compile_gate") is True
            and existing.get("launch_resources", {}).get("resource_gate")
            is True
            and existing.get("theorem_sources_elaborated") == 0
            and existing.get("candidate_tactics_executed") == 0
            and existing.get("continuation_probes_executed") == 0
        ):
            raise ValueError("existing Exp52 execution preflight changed")
        print(json.dumps(existing, ensure_ascii=False, indent=2))
        return existing
    generated = root / "exp52/preflight/generated_fix4"
    generated.mkdir(parents=True, exist_ok=True)
    lean_file = generated / LEAN_FILE_NAME
    if lean_file.is_file():
        if file_sha256(lean_file) != LEAN_SOURCE_SHA256:
            raise ValueError("generated Exp52 preflight worker changed")
    else:
        lean_file.write_text(LEAN_SOURCE, encoding="utf-8")
    imports = {
        name: f"import {name}" in Path(__file__).with_name(
            "experiment52_live_worker.py"
        ).read_text(encoding="utf-8")
        for name in ("experiment48", "experiment49", "experiment50")
    }
    workers = min(max(1, int(args.workers)), TARGET_REPOSITORIES)
    resources = _resource_receipt(root)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(
            lambda repository: _compile_one(repository, lean_file, args.timeout),
            source["config"]["repositories"],
        ))
    value: dict[str, Any] = {
        "schema": PREFLIGHT_SCHEMA,
        "version": 1,
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "mechanical_fix_id": EXECUTION_FIX_ID,
        "amendment_sha256": source["amendment_sha256"],
        "source_fix3_amendment_sha256": source[
            "source_fix3_amendment_sha256"
        ],
        "failed_fix3_preflight_sha256": source[
            "failed_fix3_preflight_sha256"
        ],
        "exp51_scientific_summary_sha256": file_sha256(
            root / "scientific/summary.json"
        ),
        "exp51_execution_gate": exp51.get("execution_gate") is True,
        "selection_summary_sha256": file_sha256(
            root / "exp52/selection/summary.json"
        ),
        "execution_cell_plan": str(cellp),
        "execution_cell_plan_sha256": file_sha256(cellp),
        "execution_cells": len(cells),
        "compile_workers": workers,
        "repositories": rows,
        "repositories_compiled": len(rows),
        "launch_resources": resources,
        "lean_source": str(lean_file),
        "lean_source_sha256": LEAN_SOURCE_SHA256,
        "diagnostic_only": True,
        "theorem_sources_elaborated": 0,
        "candidate_tactics_executed": 0,
        "continuation_probes_executed": 0,
        "import_scan": imports,
        "manual_reconciliation_count": 0,
    }
    value["compile_gate"] = bool(
        len(rows) == TARGET_REPOSITORIES
        and all(row["version_ok"] and row["compile_ok"] for row in rows)
        and resources["resource_gate"] is True
        and not any(imports.values())
        and value["theorem_sources_elaborated"] == 0
        and value["candidate_tactics_executed"] == 0
        and value["continuation_probes_executed"] == 0
    )
    value["next_step"] = (
        "Run the 32 frozen Exp52 execution shards."
        if value["compile_gate"] else
        "STOP before Exp52 scientific execution; preserve the compile receipt."
    )
    atomic_json_dump(value, outp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(SCIENTIFIC_ROOT))
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--timeout", type=int, default=300)
    return parser.parse_args()


if __name__ == "__main__":
    result = preflight(parse_args())
    raise SystemExit(0 if result.get("compile_gate") is True else 2)
