"""Compile-only Exp51 worker preflight; executes zero theorem roots and candidates."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from experiment51_live_worker import LEAN_FILE_NAME, LEAN_SOURCE, LEAN_SOURCE_SHA256
from experiment51_protocol import *
from experiment51_trace_runtime import materialized_extractor


def first_project(root: Path) -> Path:
    build_only = None
    for path in sorted((root / "screening/build_trace").glob("*.json")):
        row = read_json(path)
        if row.get("build_trace_gate") is True:
            return Path(row["project"]).resolve()
        if (build_only is None and row.get("toolchain") == TARGET_TOOLCHAIN
                and row.get("build", {}).get("returncode") == 0 and row.get("project")):
            build_only = Path(row["project"]).resolve()
    if build_only is not None:
        return build_only
    raise ValueError("STOP: no exact-v4.27 build-passing repository is available for preflight")


def preflight(args: argparse.Namespace) -> dict:
    root = Path(args.root).resolve()
    if args.stage == "trace-runtime":
        cfgp = root / "recruitment_frozen/recruitment_config.json"
        outp = root / "preflight/trace_runtime.json"
        cfg = read_json(cfgp)
        validate_code_lock(cfg["code_lock"])
        cfg_sha = file_sha256(cfgp)
        if outp.exists():
            value = read_json(outp)
            if value.get("config_sha256") != cfg_sha:
                raise ValueError("existing trace-runtime preflight belongs to another freeze")
            print(json.dumps(value, ensure_ascii=False, indent=2))
            return value
        _, runtime = materialized_extractor()
        meminfo = {}
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                key, raw = line.split(":", 1)
                meminfo[key] = int(raw.strip().split()[0])
        disk = shutil.disk_usage(SERVER_ROOT)
        resources = {
            "logical_cpus_visible": os.cpu_count(),
            "cpus_allowed_by_affinity": len(os.sched_getaffinity(0)),
            "memory_total_gb": meminfo["MemTotal"] / 1024**2,
            "memory_available_gb": meminfo["MemAvailable"] / 1024**2,
            "disk_free_gb": disk.free / 1024**3,
            "capacity_profile": RECOVERY_CAPACITY_PROFILE,
            "workload": "four isolated Python AST parsers; zero Lean trace processes",
            "required_cpus": 8,
            "required_memory_total_gb": 64,
            "required_memory_available_gb": 32,
            "required_disk_free_gb": 100,
        }
        resources["parallel_capacity_ok"] = bool(
            resources["cpus_allowed_by_affinity"] >= resources["required_cpus"]
            and resources["memory_total_gb"] >= resources["required_memory_total_gb"]
            and resources["memory_available_gb"] >= resources["required_memory_available_gb"]
            and resources["disk_free_gb"] >= resources["required_disk_free_gb"]
        )
        value = {
            "version": 1, "protocol_version": PROTOCOL_VERSION,
            "stage": args.stage, "mechanical_fix_id": MECHANICAL_FIX_ID,
            "config_sha256": cfg_sha, "diagnostic_only": True,
            "theorem_sources_elaborated": 0, "candidate_tactics_executed": 0,
            "runtime": runtime,
            "qualification_resources": resources,
            "runtime_ok": (
                runtime.get("runtime_version") == TRACE_RUNTIME_VERSION
                and runtime.get("lean_dojo_version") == "4.20.0"
                and runtime.get("lean_dojo_source_ledger_exact") is True
                and runtime.get("v427_extractor_sha256")
                == "b50bebdef8adde06d1f6948edc0ac52f67dd8b40045df72290a1f225049ffc50"
            ),
        }
        value["next_step"] = (
            "Run zero-candidate parser-adapter preflight."
            if value["runtime_ok"] and resources["parallel_capacity_ok"]
            else "STOP before trace recovery."
        )
        atomic_json_dump(value, outp)
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value
    if args.stage == "parser-adapter":
        from screen_experiment51_repositories import (
            enumerate_frame_isolated,
            validate_fix4_trace_reuse,
        )

        cfgp = root / "recruitment_frozen/recruitment_config.json"
        outp = root / "preflight/parser_adapter.json"
        cfg = read_json(cfgp)
        validate_code_lock(cfg["code_lock"])
        cfg_sha = file_sha256(cfgp)
        if outp.is_file():
            value = read_json(outp)
            if value.get("config_sha256") != cfg_sha:
                raise ValueError("existing parser-adapter preflight belongs to another freeze")
            print(json.dumps(value, ensure_ascii=False, indent=2))
            return value
        frame = read_json(cfg["candidate_frame"])
        by_slug = {row["slug"]: row for row in frame["candidates"]}
        if any(slug not in by_slug for slug in PARSER_ADAPTER_PREFLIGHT_REPOSITORIES):
            raise ValueError("parser-adapter preflight repository set changed")
        smokes = []
        controls_exact = True
        for slug in PARSER_ADAPTER_PREFLIGHT_REPOSITORIES:
            candidate = by_slug[slug]
            reuse = validate_fix4_trace_reuse(candidate, root)
            source = read_json(
                SOURCE_FIX4_ROOT / "screening/build_trace" / f"{safe_slug(slug)}.json"
            )
            smoke_root = root / "preflight/parser_adapter_smoke" / safe_slug(slug)
            framep = smoke_root / "frame.jsonl"
            roots, exclusions, worker = enumerate_frame_isolated(
                Path(source["project"]), slug, source["commit"],
                smoke_root, framep, args.timeout, reuse["ast_ledger_sha256"],
            )
            adapter = worker["position_adapter"]
            parser_execution = adapter.get("parser_execution", {})
            section = adapter.get("section_adapter", {}).get("counters", {})
            section_headers = adapter.get("section_adapter", {}).get("header_counters", {})
            crlf = adapter.get("crlf_adapter", {}).get("counters", {})
            source_line_endings = reuse.get("source_line_endings", {})
            common_gate = bool(
                adapter.get("schema") == V427_POSITION_ADAPTER_SCHEMA
                and adapter.get("parser_compatibility_schema")
                == V427_PARSER_COMPATIBILITY_SCHEMA
                and adapter.get("installed_parser_files_unchanged") is True
                and adapter.get("counters", {}).get("v427_byteIdx", 0) > 0
                and adapter.get("counters", {}).get("rejected") == 0
                and section.get("rejected") == 0
                and section_headers.get("rejected") == 0
                and crlf.get("rejected") == 0
                and adapter.get("crlf_adapter", {}).get("accepted")
                == "standard-CRLF-normalized-to-LF-byte-width"
                and adapter.get("crlf_adapter", {}).get("byte_index_semantics")
                == "Lean-v4.27-LF-normalized-source-buffer"
                and adapter.get("crlf_adapter", {}).get("checkout_modified") is False
                and parser_execution.get("profile") == PARSER_EXECUTION_PROFILE
                and parser_execution.get("num_procs") == 2
                and parser_execution.get("num_workers") == 1
                and parser_execution.get("ray_initialized") is False
                and parser_execution.get("adapter_process_pid") == worker.get("worker_pid")
            )
            repository_gate = common_gate
            if slug == "AfonsoBitoque/LeanServer":
                repository_gate = bool(
                    repository_gate
                    and section.get("v427_named_three_child", 0) > 0
                    and crlf.get("standard_crlf_files")
                    == PARSER_COMPATIBILITY_EXPECTED["traced_standard_crlf_files"]
                    and crlf.get("standard_crlf_lines")
                    == PARSER_COMPATIBILITY_EXPECTED["traced_standard_crlf_lines"]
                    and source_line_endings.get("standard_crlf_files")
                    == CHECKOUT_LINE_ENDING_EXPECTED["standard_crlf_files"]
                    and source_line_endings.get("standard_crlf_lines")
                    == CHECKOUT_LINE_ENDING_EXPECTED["standard_crlf_lines"]
                    and source_line_endings.get("line_ending_rejections") == 0
                )
            if slug == "PatrickMassot/GlimpseOfLean":
                repository_gate = bool(
                    repository_gate
                    and section.get("v427_named_three_child", 0) > 0
                    and section.get("v427_unnamed_three_child", 0) > 0
                    and section_headers.get("noncomputable", 0) > 0
                )
            fix8_control = None
            if slug in FIX8_FRAME_CONTROLS:
                expectedp = (
                    SOURCE_FIX8_ROOT / "screening/frames" / f"{safe_slug(slug)}.jsonl"
                )
                if not expectedp.is_file():
                    raise FileNotFoundError(expectedp)
                expected = [json.loads(line) for line in expectedp.read_text(encoding="utf-8").splitlines()
                            if line.strip()]
                exact = bool(
                    len(expected) == FIX8_FRAME_CONTROLS[slug]
                    and roots == expected
                    and file_sha256(framep) == file_sha256(expectedp)
                )
                controls_exact = controls_exact and exact
                repository_gate = repository_gate and exact
                fix8_control = {
                    "expected_frame": str(expectedp),
                    "expected_frame_sha256": file_sha256(expectedp),
                    "observed_frame_sha256": file_sha256(framep),
                    "expected_roots": FIX8_FRAME_CONTROLS[slug],
                    "observed_roots": len(roots),
                    "exact": exact,
                }
            smokes.append({
                "repository": slug,
                "trace_reuse": reuse,
                "roots_enumerated": len(roots),
                "exclusions": dict(sorted(exclusions.items())),
                "frame": str(framep),
                "frame_sha256": file_sha256(framep),
                "enumeration_worker_pid": worker["worker_pid"],
                "position_adapter": adapter,
                "fix8_frame_control": fix8_control,
                "smoke_gate": repository_gate,
            })
        value = {
            "version": 1,
            "protocol_version": PROTOCOL_VERSION,
            "stage": args.stage,
            "mechanical_fix_id": MECHANICAL_FIX_ID,
            "config_sha256": cfg_sha,
            "diagnostic_only": True,
            "trace_executed": False,
            "theorem_sources_elaborated": 0,
            "candidate_tactics_executed": 0,
            "parser_compatibility_schema": V427_PARSER_COMPATIBILITY_SCHEMA,
            "repositories": list(PARSER_ADAPTER_PREFLIGHT_REPOSITORIES),
            "compatibility_smokes": smokes,
            "fix8_success_frames_exact": controls_exact,
            "adapter_ok": bool(controls_exact and all(row["smoke_gate"] for row in smokes)),
        }
        value["next_step"] = (
            "Run all 15 hash-validated fix4 trace recovery enumerations."
            if value["adapter_ok"] else "STOP before recovery enumeration."
        )
        atomic_json_dump(value, outp)
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value
    if args.stage == "screening":
        cfgp = root / "recruitment_frozen/recruitment_config.json"
        outp = root / "preflight/screening_worker_compile.json"
        build_summaryp = root / "screening/build_trace_summary.json"
        if not build_summaryp.is_file():
            raise ValueError("STOP: recovery summary is absent; screening preflight prohibited")
        build_summary = read_json(build_summaryp)
        if (
            build_summary.get("recovery_gate") is not True
            or build_summary.get("passed", 0) < MIN_REPOSITORIES
            or build_summary.get("fix8_success_frames_exact") is not True
            or build_summary.get("parser_compatibility_measurement", {}).get("exact") is not True
        ):
            raise ValueError(
                "STOP: fewer than 12 repositories passed or fix8 controls changed; "
                "screening preflight prohibited"
            )
    else:
        cfgp = root / "frozen/experiment51_config.json"
        outp = root / "preflight/scientific_worker_compile.json"
    cfg = read_json(cfgp)
    validate_code_lock(cfg["code_lock"])
    cfg_sha = file_sha256(cfgp)
    if outp.exists():
        value = read_json(outp)
        if value.get("config_sha256") != cfg_sha or value.get("lean_source_sha256") != LEAN_SOURCE_SHA256:
            raise ValueError("existing preflight belongs to another freeze")
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value
    project = first_project(root)
    generated = root / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    lean_file = generated / LEAN_FILE_NAME
    if lean_file.exists() and lean_file.read_text(encoding="utf-8") != LEAN_SOURCE:
        raise ValueError("generated Exp51 Lean worker changed")
    if not lean_file.exists():
        lean_file.write_text(LEAN_SOURCE, encoding="utf-8")
    version = subprocess.run(["lake", "env", "lean", "--version"], cwd=project,
                             text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             timeout=args.timeout)
    compiled = subprocess.run(["lake", "env", "lean", str(lean_file)], cwd=project,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=args.timeout)
    version_text = (version.stdout + "\n" + version.stderr).strip()
    source_text = (PACKAGE_ROOT / "experiment51_live_worker.py").read_text(encoding="utf-8")
    import_scan = {"imports_exp48_runner": "import experiment48" in source_text,
                   "imports_exp49_runner": "import experiment49" in source_text,
                   "imports_exp50_runner": "import experiment50" in source_text}
    value = {
        "version": 1, "protocol_version": PROTOCOL_VERSION, "stage": args.stage,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "config_sha256": cfg_sha, "diagnostic_only": True,
        "theorem_sources_elaborated": 0, "candidate_tactics_executed": 0,
        "project": str(project), "lean_version": version_text,
        "version_ok": version.returncode == 0 and "version 4.27.0" in version_text,
        "lean_source": str(lean_file), "lean_source_sha256": LEAN_SOURCE_SHA256,
        "compile_returncode": compiled.returncode, "stdout": compiled.stdout[-8000:],
        "stderr": compiled.stderr[-12000:], "import_scan": import_scan,
    }
    value["compile_ok"] = bool(value["version_ok"] and compiled.returncode == 0
                               and not any(import_scan.values()))
    value["next_step"] = (
        "Run authored-only repository screening." if args.stage == "screening" and value["compile_ok"]
        else "Run Exp51 scientific smoke." if args.stage == "scientific" and value["compile_ok"]
        else "STOP before theorem execution.")
    atomic_json_dump(value, outp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    p.add_argument(
        "--stage",
        choices=("trace-runtime", "parser-adapter", "screening", "scientific"),
        required=True,
    )
    p.add_argument("--timeout", type=int, default=300)
    return p.parse_args()


if __name__ == "__main__":
    result = preflight(parse_args())
    gate = (
        result.get("runtime_ok") is True
        and result.get("qualification_resources", {}).get("parallel_capacity_ok") is True
        if result.get("stage") == "trace-runtime"
        else result.get("adapter_ok") if result.get("stage") == "parser-adapter"
        else result.get("compile_ok")
    )
    raise SystemExit(0 if gate else 2)
