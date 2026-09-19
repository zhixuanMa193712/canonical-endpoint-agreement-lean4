"""Compile-only global Exp52 probe-syntax qualification for staged Exp51 roots.

The preflight imports already-built source modules and constructs tactic syntax
quotations.  It elaborates zero theorem source files and executes zero tactics.

Fix2 gives each quotation a valid expected type: a ``Lean.MacroM`` computation
returning typed tactic syntax. Fix1 annotated the same quotation as
``Lean.Syntax``; Lean therefore rejected every nonempty probe file with a type
mismatch before assessing any individual tactic syntax.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from experiment52_protocol import (
    ALIGNMENT_FIX_ID,
    ALIGNMENT_VERSION,
    PROBE_POOL,
    QUALIFICATION_ARTIFACT_RELATIVE,
    SCIENTIFIC_ARTIFACT_RELATIVE,
    SERVER_ROOT,
    file_sha256,
    json_sha256,
    retained_probe_panel,
)
from freeze_experiment51_scientific import (
    base,
    legacy_freeze,
    validate_extension2_qualification,
)

SIMPLE_COMPONENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_']*$")


def lean_module_name(file_path: str) -> str:
    path = Path(file_path)
    if path.suffix != ".lean" or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"invalid repository-relative Lean module path: {file_path}")
    parts = list(path.with_suffix("").parts)
    if not parts or any(part in {"", "."} for part in parts):
        raise ValueError(f"empty Lean module component: {file_path}")
    encoded = []
    for part in parts:
        if SIMPLE_COMPONENT.fullmatch(part):
            encoded.append(part)
            continue
        if any(token in part for token in ("«", "»", "\n", "\r")):
            raise ValueError(f"unsupported quoted Lean module component: {part}")
        encoded.append(f"«{part}»")
    return ".".join(encoded)


def source_for(module: str, probes: list[str]) -> str:
    definitions = [
        (
            f"def exp52ProbeSyntax{index} : "
            f"Lean.MacroM (Lean.TSyntax `tactic) := `(tactic| {probe})"
        )
        for index, probe in enumerate(probes)
    ]
    return "\n".join([
        f"import {module}",
        "import Lean",
        "open Lean",
        *definitions,
        "",
    ])


def compile_source(
    *,
    project: Path,
    source: Path,
    timeout: int,
) -> dict[str, Any]:
    try:
        process = subprocess.run(
            ["lake", "env", "lean", "--threads", "1", str(source)],
            cwd=project,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(
            exc.stdout, bytes
        ) else str(exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(
            exc.stderr, bytes
        ) else str(exc.stderr or "")
        return {
            "source": str(source),
            "source_sha256": file_sha256(source),
            "returncode": None,
            "compile_ok": False,
            "timeout": True,
            "stdout_tail": stdout[-4000:],
            "stderr_tail": stderr[-8000:],
        }
    return {
        "source": str(source),
        "source_sha256": file_sha256(source),
        "returncode": process.returncode,
        "compile_ok": process.returncode == 0,
        "timeout": False,
        "stdout_tail": process.stdout[-4000:],
        "stderr_tail": process.stderr[-8000:],
    }


def write_source(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = value.encode("utf-8")
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(f"existing generated probe preflight source changed: {path}")
        return
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(encoded)
    temporary.replace(path)


def module_rows(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for target in targets:
        key = (target["slug"], target["file_path"])
        row = {
            "slug": target["slug"],
            "project": target["checkout"],
            "file_path": target["file_path"],
            "module": lean_module_name(target["file_path"]),
        }
        if key in unique and unique[key] != row:
            raise ValueError(f"module identity changed: {key}")
        unique[key] = row
    return [unique[key] for key in sorted(unique)]


def qualify_module(
    root: Path,
    row: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    safe = base.safe_slug(row["slug"])
    module_id = json_sha256([row["slug"], row["file_path"]])[:20]
    generated = root / "preflight/exp52_probe_surface_generated" / safe / module_id
    baselinep = generated / "Baseline.lean"
    aggregatep = generated / "AllProbes.lean"
    write_source(baselinep, source_for(row["module"], []))
    baseline = compile_source(
        project=Path(row["project"]), source=baselinep, timeout=timeout
    )
    value = {
        **row,
        "module_id": module_id,
        "baseline": baseline,
        "aggregate": None,
        "probe_results": {},
    }
    if not baseline["compile_ok"]:
        value["module_gate"] = False
        value["first_failed_gate"] = "baseline_import"
        return value
    write_source(aggregatep, source_for(row["module"], list(PROBE_POOL)))
    aggregate = compile_source(
        project=Path(row["project"]), source=aggregatep, timeout=timeout
    )
    value["aggregate"] = aggregate
    if aggregate["compile_ok"]:
        value["probe_results"] = {
            probe: {"compile_ok": True, "source": str(aggregatep)}
            for probe in PROBE_POOL
        }
    else:
        for index, probe in enumerate(PROBE_POOL):
            probep = generated / f"Probe{index:02d}.lean"
            write_source(probep, source_for(row["module"], [probe]))
            value["probe_results"][probe] = compile_source(
                project=Path(row["project"]), source=probep, timeout=timeout
            )
    value["module_gate"] = True
    value["first_failed_gate"] = None
    return value


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    scientific_root = Path(args.root).resolve()
    qualification_root = Path(args.qualification_root).resolve()
    outp = scientific_root / "preflight/exp52_probe_surface.json"
    ledgerp = scientific_root / "preflight/exp52_probe_surface_modules.jsonl"
    qualification = validate_extension2_qualification(qualification_root)
    selected = qualification["selected_repositories"][: base.TARGET_REPOSITORIES]
    targets, _ = legacy_freeze.build_targets(qualification_root, selected)
    target_sha = json_sha256(targets)
    if outp.is_file():
        value = base.read_json(outp)
        if not (
            value.get("alignment_version") == ALIGNMENT_VERSION
            and value.get("mechanical_fix_id") == ALIGNMENT_FIX_ID
            and value.get("qualification_config_sha256") == qualification["config_sha256"]
            and value.get("qualification_summary_sha256")
            == qualification["screening_summary_sha256"]
            and value.get("staged_targets_sha256") == target_sha
            and value.get("module_ledger_sha256") == file_sha256(ledgerp)
        ):
            raise ValueError(
                "existing Exp52 probe-surface preflight belongs to another "
                "frame or mechanical-fix version"
            )
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value
    modules = module_rows(targets)
    if not 1 <= args.workers <= 64:
        raise ValueError("--workers must be between 1 and 64")
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(qualify_module, scientific_root, row, args.timeout): row
            for row in modules
        }
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            row = future.result()
            rows.append(row)
            print(
                f"EXP52-PROBE-SURFACE {index}/{len(modules)} "
                f"{row['slug']} {row['file_path']} "
                f"baseline={int(row['baseline']['compile_ok'])} "
                f"aggregate={int((row.get('aggregate') or {}).get('compile_ok') is True)}",
                flush=True,
            )
    rows.sort(key=lambda row: (row["slug"], row["file_path"]))
    base.atomic_jsonl_dump(rows, ledgerp)
    baseline_gate = all(row["baseline"]["compile_ok"] for row in rows)
    available = [
        probe
        for probe in PROBE_POOL
        if all(row["probe_results"].get(probe, {}).get("compile_ok") is True for row in rows)
    ] if baseline_gate else []
    retained = retained_probe_panel(available)
    probe_rows = [
        {
            "probe": probe,
            "available_in_all_staged_modules": probe in available,
            "failed_modules": sum(
                row["probe_results"].get(probe, {}).get("compile_ok") is not True
                for row in rows
            ),
            "retained": probe in retained,
        }
        for probe in PROBE_POOL
    ]
    value = {
        "version": 1,
        "alignment_version": ALIGNMENT_VERSION,
        "mechanical_fix_id": ALIGNMENT_FIX_ID,
        "stage": "exp52-probe-surface",
        "diagnostic_only": True,
        "qualification_root": str(qualification_root),
        "qualification_config_sha256": qualification["config_sha256"],
        "qualification_summary_sha256": qualification["screening_summary_sha256"],
        "selected_repositories": selected,
        "staged_targets": len(targets),
        "staged_targets_sha256": target_sha,
        "unique_source_modules": len(modules),
        "compile_workers": args.workers,
        "baseline_import_gate": baseline_gate,
        "frozen_probe_pool": list(PROBE_POOL),
        "frozen_probe_pool_sha256": json_sha256(PROBE_POOL),
        "probe_qualification": probe_rows,
        "retained_panel": retained,
        "retained_panel_sha256": json_sha256(retained),
        "globally_removed_probes": [probe for probe in PROBE_POOL if probe not in retained],
        "minimum_retained": 8,
        "module_ledger": str(ledgerp),
        "module_ledger_sha256": file_sha256(ledgerp),
        "trace_executed": False,
        "theorem_sources_elaborated": 0,
        "candidate_tactics_executed": 0,
        "scientific_candidate_tactics_executed": 0,
        "probe_surface_gate": baseline_gate and len(retained) >= 8,
    }
    value["next_step"] = (
        "Freeze Exp51 scientific targets and aligned Exp52 protocol."
        if value["probe_surface_gate"]
        else "STOP: probe_surface_no_go or baseline import failure."
    )
    base.atomic_json_dump(value, outp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", default=str(SERVER_ROOT / SCIENTIFIC_ARTIFACT_RELATIVE)
    )
    parser.add_argument(
        "--qualification-root",
        default=str(SERVER_ROOT / QUALIFICATION_ARTIFACT_RELATIVE),
    )
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--workers", type=int, default=16)
    return parser.parse_args()


if __name__ == "__main__":
    result = preflight(parse_args())
    raise SystemExit(0 if result.get("probe_surface_gate") is True else 2)
