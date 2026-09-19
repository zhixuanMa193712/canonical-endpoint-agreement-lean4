"""Zero-candidate preflights for Exp51 repository-frame extension 1."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from experiment51_extension_protocol import *
from experiment51_trace_runtime import (
    LEAN_DOJO_SOURCE_LEDGER_SHA256,
    LEAN_DOJO_VERSION,
    V427_EXTRACTOR_SHA256,
    materialized_extractor,
)


def config_receipt(root: Path) -> tuple[dict[str, Any], Path, str]:
    configp = root / "frozen/extension_config.json"
    config = read_json(configp)
    validate_code_lock(config["code_lock"])
    if not (
        config.get("extension_version") == EXTENSION_VERSION
        and config.get("mechanical_fix_id") == MECHANICAL_FIX_ID
        and config.get("scientific_candidate_tactics_permitted") == 0
        and file_sha256(CANDIDATE_FRAME) == config.get("candidate_frame_sha256")
    ):
        raise ValueError("wrong frozen Exp51 extension config")
    identity = json_sha256({
        key: value for key, value in config.items()
        if key not in {"created_utc", "identity_sha256"}
    })
    if identity != config.get("identity_sha256"):
        raise ValueError("extension config identity changed")
    return config, configp, file_sha256(configp)


def print_existing(path: Path, config_sha: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = read_json(path)
    if value.get("config_sha256") != config_sha:
        raise ValueError(f"existing preflight belongs to another extension freeze: {path}")
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def linux_resources() -> dict[str, Any]:
    meminfo: dict[str, int] = {}
    with open("/proc/meminfo", encoding="utf-8") as handle:
        for line in handle:
            key, raw = line.split(":", 1)
            meminfo[key] = int(raw.strip().split()[0])
    affinity = (
        len(os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity")
        else int(os.cpu_count() or 0)
    )
    disk = shutil.disk_usage(SERVER_ROOT)
    value = {
        "logical_cpus_visible": os.cpu_count(),
        "cpus_allowed_by_affinity": affinity,
        "memory_total_gb": meminfo["MemTotal"] / 1024**2,
        "memory_available_gb": meminfo["MemAvailable"] / 1024**2,
        "disk_free_gb": disk.free / 1024**3,
        "required_cpus": REQUIRED_CPUS,
        "required_memory_total_gb": REQUIRED_MEMORY_TOTAL_GB,
        "required_memory_available_gb": REQUIRED_MEMORY_AVAILABLE_GB,
        "required_disk_free_gb": REQUIRED_DISK_FREE_GB,
        "schedule": {
            "repository_workers": REPOSITORY_WORKERS,
            "build_slots": BUILD_SLOTS,
            "trace_slots": TRACE_SLOTS,
            "enumeration_slots": ENUMERATION_SLOTS,
            "threads_per_trace": THREADS_PER_TRACE,
        },
    }
    value["parallel_capacity_ok"] = bool(
        affinity >= REQUIRED_CPUS
        and value["memory_total_gb"] >= REQUIRED_MEMORY_TOTAL_GB
        and value["memory_available_gb"] >= REQUIRED_MEMORY_AVAILABLE_GB
        and value["disk_free_gb"] >= REQUIRED_DISK_FREE_GB
    )
    return value


def environment_preflight(root: Path, config_sha: str) -> dict[str, Any]:
    outp = root / "preflight/environment.json"
    existing = print_existing(outp, config_sha)
    if existing is not None:
        return existing
    nogo = validate_nogo_bundle()
    carried = validate_base_carry_forward()
    _, runtime = materialized_extractor()
    resources = linux_resources()
    runtime_ok = bool(
        runtime.get("lean_dojo_version") == LEAN_DOJO_VERSION == "4.20.0"
        and runtime.get("v427_extractor_sha256") == V427_EXTRACTOR_SHA256
        and runtime.get("lean_dojo_source_ledger_sha256")
        == LEAN_DOJO_SOURCE_LEDGER_SHA256
        and runtime.get("lean_dojo_source_ledger_exact") is True
    )
    value = {
        "version": 1,
        "extension_version": EXTENSION_VERSION,
        "stage": "environment",
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "config_sha256": config_sha,
        "diagnostic_only": True,
        "trace_executed": False,
        "theorem_sources_elaborated": 0,
        "candidate_tactics_executed": 0,
        "base_recruitment_nogo": nogo,
        "archive_exact_carry_forward_repositories": len(carried),
        "all_carry_forward_evidence_exact": all(
            row.get("archive_evidence_exact") is True for row in carried
        ),
        "runtime": runtime,
        "runtime_ok": runtime_ok,
        "qualification_resources": resources,
    }
    value["environment_gate"] = bool(
        runtime_ok
        and value["all_carry_forward_evidence_exact"]
        and len(carried) == len(CARRY_FORWARD_SLUGS)
        and resources["parallel_capacity_ok"]
    )
    value["next_step"] = (
        "Carry forward the seven archive-exact zero-candidate qualification passes."
        if value["environment_gate"]
        else "STOP before carry-forward or new repository checkout."
    )
    atomic_json_dump(value, outp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def offline_parser_control(root: Path, config_sha: str, timeout: int) -> dict[str, Any]:
    outp = root / "preflight/offline_parser_control.json"
    existing = print_existing(outp, config_sha)
    if existing is not None:
        return existing
    environment = read_json(root / "preflight/environment.json")
    carry = read_json(root / "screening/carry_forward_summary.json")
    if not (
        environment.get("environment_gate") is True
        and carry.get("carry_forward_gate") is True
        and carry.get("trace_executed") is False
        and carry.get("scientific_candidate_tactics_executed") == 0
    ):
        raise ValueError("environment/carry-forward gate has not passed")

    from screen_experiment51_extension import enumerate_isolated

    smokes = []
    for slug in OFFLINE_CONTROL_SLUGS:
        safe = safe_slug(slug)
        build = read_json(root / "screening/build_trace" / f"{safe}.json")
        expectedp = root / "screening/frames" / f"{safe}.jsonl"
        smoke_root = root / "preflight/offline_parser_control" / safe
        observedp = smoke_root / "observed_frame.jsonl"
        roots, exclusions, worker = enumerate_isolated(
            Path(build["project"]),
            slug,
            build["commit"],
            smoke_root,
            observedp,
            timeout,
        )
        offline = worker.get("offline_dependency_adapter", {})
        adapter = worker.get("position_adapter", {})
        exact = bool(
            roots == read_jsonl(expectedp)
            and file_sha256(observedp) == file_sha256(expectedp)
        )
        gate = bool(
            exact
            and worker.get("scientific_candidate_tactics_executed") == 0
            and offline.get("dependency_queries_suppressed") == 1
            and offline.get("github_api_attempts") == 0
            and offline.get("returned_dependency_maps") == [0]
            and offline.get("in_memory_only") is True
            and offline.get("installed_lean_dojo_files_modified") is False
            and offline.get("repository_checkout_modified") is False
            and adapter.get("installed_parser_files_unchanged") is True
            and adapter.get("counters", {}).get("rejected") == 0
            and adapter.get("section_adapter", {}).get("counters", {}).get("rejected") == 0
            and adapter.get("section_adapter", {}).get("header_counters", {}).get("rejected") == 0
            and adapter.get("crlf_adapter", {}).get("counters", {}).get("rejected") == 0
        )
        smokes.append({
            "repository": slug,
            "project": build["project"],
            "commit": build["commit"],
            "expected_frame": str(expectedp),
            "expected_frame_sha256": file_sha256(expectedp),
            "observed_frame": str(observedp),
            "observed_frame_sha256": file_sha256(observedp),
            "roots": len(roots),
            "exclusions": dict(sorted(exclusions.items())),
            "frame_exact": exact,
            "offline_dependency_adapter": offline,
            "position_adapter": adapter,
            "control_gate": gate,
        })
    value = {
        "version": 1,
        "extension_version": EXTENSION_VERSION,
        "stage": "offline-parser-control",
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "config_sha256": config_sha,
        "diagnostic_only": True,
        "trace_executed": False,
        "theorem_sources_elaborated": 0,
        "candidate_tactics_executed": 0,
        "control_repositories": list(OFFLINE_CONTROL_SLUGS),
        "controls": smokes,
        "all_frames_exact": all(row["frame_exact"] for row in smokes),
        "github_api_attempts": sum(
            row["offline_dependency_adapter"].get("github_api_attempts", 0)
            for row in smokes
        ),
        "control_gate": len(smokes) == len(OFFLINE_CONTROL_SLUGS)
        and all(row["control_gate"] for row in smokes),
    }
    value["next_step"] = (
        "Run frozen zero-candidate build/trace screening for all 28 extension repositories."
        if value["control_gate"]
        else "STOP before any new repository trace."
    )
    atomic_json_dump(value, outp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def first_build_trace_project(root: Path) -> Path:
    for path in sorted((root / "screening/build_trace").glob("*.json")):
        row = read_json(path)
        if row.get("build_trace_gate") is True and row.get("project"):
            return Path(row["project"]).resolve()
    raise ValueError("no build/trace-passing extension repository is available")


def screening_worker_preflight(
    root: Path, config_sha: str, timeout: int
) -> dict[str, Any]:
    outp = root / "preflight/screening_worker_compile.json"
    existing = print_existing(outp, config_sha)
    if existing is not None:
        return existing
    build = read_json(root / "screening/build_trace_summary.json")
    if not (
        build.get("execution_complete") is True
        and build.get("build_trace_gate") is True
        and build.get("combined_build_trace_passes", 0) >= MIN_REPOSITORIES
        and build.get("scientific_candidate_tactics_executed") == 0
        and build.get("github_api_attempts") == 0
    ):
        raise ValueError("combined build/trace extension gate has not passed")

    from experiment51_live_worker import (
        LEAN_FILE_NAME,
        LEAN_SOURCE,
        LEAN_SOURCE_SHA256,
    )

    project = first_build_trace_project(root)
    generated = root / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    lean_file = generated / LEAN_FILE_NAME
    if lean_file.is_file() and lean_file.read_text(encoding="utf-8") != LEAN_SOURCE:
        raise ValueError("generated Exp51 live worker changed")
    if not lean_file.is_file():
        lean_file.write_text(LEAN_SOURCE, encoding="utf-8")
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
    worker_source = (BASE_PACKAGE_ROOT / "experiment51_live_worker.py").read_text(
        encoding="utf-8"
    )
    import_scan = {
        "imports_exp48_runner": "import experiment48" in worker_source,
        "imports_exp49_runner": "import experiment49" in worker_source,
        "imports_exp50_runner": "import experiment50" in worker_source,
    }
    value = {
        "version": 1,
        "extension_version": EXTENSION_VERSION,
        "stage": "screening",
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "config_sha256": config_sha,
        "diagnostic_only": True,
        "theorem_sources_elaborated": 0,
        "candidate_tactics_executed": 0,
        "project": str(project),
        "lean_version": version_text,
        "version_ok": version.returncode == 0 and "version 4.27.0" in version_text,
        "lean_source": str(lean_file),
        "lean_source_sha256": LEAN_SOURCE_SHA256,
        "compile_returncode": compiled.returncode,
        "stdout": compiled.stdout[-8000:],
        "stderr": compiled.stderr[-12000:],
        "import_scan": import_scan,
    }
    value["compile_ok"] = bool(
        value["version_ok"]
        and compiled.returncode == 0
        and not any(import_scan.values())
    )
    value["next_step"] = (
        "Run authored-only replay with an empty scientific candidate list."
        if value["compile_ok"]
        else "STOP before theorem replay."
    )
    atomic_json_dump(value, outp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    _, _, config_sha = config_receipt(root)
    if args.stage == "environment":
        return environment_preflight(root, config_sha)
    if args.stage == "offline-parser-control":
        return offline_parser_control(root, config_sha, args.timeout)
    return screening_worker_preflight(root, config_sha, args.timeout)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ARTIFACT_ROOT))
    parser.add_argument(
        "--stage",
        choices=("environment", "offline-parser-control", "screening"),
        required=True,
    )
    parser.add_argument("--timeout", type=int, default=300)
    return parser.parse_args()


if __name__ == "__main__":
    result = preflight(parse_args())
    gate = (
        result.get("environment_gate")
        if result.get("stage") == "environment"
        else result.get("control_gate")
        if result.get("stage") == "offline-parser-control"
        else result.get("compile_ok")
    )
    raise SystemExit(0 if gate is True else 2)
