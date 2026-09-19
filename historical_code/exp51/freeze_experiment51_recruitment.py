"""Freeze the zero-scientific-candidate recruitment frame for Exp51."""
from __future__ import annotations

import argparse
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiment51_protocol import *


def locked_sources() -> list[Path]:
    files = sorted(PACKAGE_ROOT.glob("*.py"))
    files += [PACKAGE_ROOT / "repository_candidates.json", PACKAGE_ROOT / "README_SERVER.md",
              PACKAGE_ROOT / "requirements.txt"]
    return files


def validate_fix0_diagnostic() -> dict[str, Any]:
    configp = SOURCE_FIX0_ROOT / "recruitment_frozen/recruitment_config.json"
    summaryp = SOURCE_FIX0_ROOT / "screening/build_trace_summary.json"
    receipt_paths = sorted((SOURCE_FIX0_ROOT / "screening/build_trace").glob("*.json"))
    if not configp.is_file() or not summaryp.is_file() or len(receipt_paths) != 20:
        raise FileNotFoundError(
            "preserved Exp51 fix0 diagnostic is absent or incomplete; set MZX_EXP51_FIX0_ROOT"
        )
    config, summary = read_json(configp), read_json(summaryp)
    receipts = [read_json(path) for path in receipt_paths]
    if not (config.get("recruitment_version") == "experiment51-zero-candidate-recruitment-v1"
            and config.get("scientific_candidate_tactics_permitted") == 0
            and summary.get("passed") == 0
            and summary.get("scientific_candidate_tactics_executed") == 0
            and all(row.get("scientific_candidate_tactics_executed") == 0 for row in receipts)):
        raise ValueError("Exp51 fix0 diagnostic is not the protected zero-candidate failure")
    scientific_files = ([p for p in (SOURCE_FIX0_ROOT / "scientific").rglob("*") if p.is_file()]
                        if (SOURCE_FIX0_ROOT / "scientific").exists() else [])
    if scientific_files:
        raise ValueError("Exp51 fix0 archive contains scientific execution and cannot be superseded mechanically")
    ledger = [{"path": str(path), "sha256": file_sha256(path), "bytes": path.stat().st_size}
              for path in receipt_paths]
    return {
        "root": str(SOURCE_FIX0_ROOT),
        "reason": "20/20 build-trace qualification failures; 10 were missing-extractor mechanics",
        "scientific_candidate_tactics_executed": 0,
        "recruitment_config": str(configp),
        "recruitment_config_sha256": file_sha256(configp),
        "build_trace_summary": str(summaryp),
        "build_trace_summary_sha256": file_sha256(summaryp),
        "receipt_count": len(ledger),
        "receipt_ledger": ledger,
        "receipt_ledger_sha256": json_sha256(ledger),
    }


def validate_fix1_diagnostic() -> dict[str, Any]:
    configp = SOURCE_FIX1_ROOT / "recruitment_frozen/recruitment_config.json"
    summaryp = SOURCE_FIX1_ROOT / "screening/build_trace_summary.json"
    receipt_paths = sorted((SOURCE_FIX1_ROOT / "screening/build_trace").glob("*.json"))
    if not configp.is_file() or not summaryp.is_file() or len(receipt_paths) != 26:
        raise FileNotFoundError(
            "preserved Exp51 fix1 diagnostic is absent or incomplete; set MZX_EXP51_FIX1_ROOT"
        )
    config, summary = read_json(configp), read_json(summaryp)
    receipts = [read_json(path) for path in receipt_paths]
    failure_counts: dict[str, int] = {}
    for row in receipts:
        gate = str(row.get("first_failed_gate"))
        failure_counts[gate] = failure_counts.get(gate, 0) + 1
    if not (
        config.get("recruitment_version") == "experiment51-zero-candidate-recruitment-fix1"
        and config.get("scientific_candidate_tactics_permitted") == 0
        and summary.get("candidates") == 26
        and summary.get("passed") == 0
        and summary.get("scientific_candidate_tactics_executed") == 0
        and failure_counts.get("trace") == 19
        and all(row.get("scientific_candidate_tactics_executed") == 0 for row in receipts)
    ):
        raise ValueError("Exp51 fix1 diagnostic is not the protected 26-root zero-candidate failure")
    scientific_files = (
        [p for p in (SOURCE_FIX1_ROOT / "scientific").rglob("*") if p.is_file()]
        if (SOURCE_FIX1_ROOT / "scientific").exists() else []
    )
    if scientific_files:
        raise ValueError("Exp51 fix1 archive contains scientific execution and cannot be superseded mechanically")
    ledger = [
        {"path": str(path), "sha256": file_sha256(path), "bytes": path.stat().st_size}
        for path in receipt_paths
    ]
    return {
        "root": str(SOURCE_FIX1_ROOT),
        "reason": "26/26 build-trace qualification failures; 19 exact-build candidates lacked an importable LeanDojo tracing runtime",
        "failure_gate_counts": dict(sorted(failure_counts.items())),
        "scientific_candidate_tactics_executed": 0,
        "recruitment_config": str(configp),
        "recruitment_config_sha256": file_sha256(configp),
        "build_trace_summary": str(summaryp),
        "build_trace_summary_sha256": file_sha256(summaryp),
        "receipt_count": len(ledger),
        "receipt_ledger": ledger,
        "receipt_ledger_sha256": json_sha256(ledger),
    }


def validate_fix2_diagnostic() -> dict[str, Any]:
    configp = SOURCE_FIX2_ROOT / "recruitment_frozen/recruitment_config.json"
    runtimep = SOURCE_FIX2_ROOT / "preflight/trace_runtime.json"
    receipt_paths = sorted((SOURCE_FIX2_ROOT / "screening/build_trace").glob("*.json"))
    if not configp.is_file() or not runtimep.is_file():
        raise FileNotFoundError(
            "preserved Exp51 fix2 diagnostic is absent or incomplete; set MZX_EXP51_FIX2_ROOT"
        )
    config, runtime = read_json(configp), read_json(runtimep)
    receipts = [read_json(path) for path in receipt_paths]
    if not (
        config.get("recruitment_version") == "experiment51-zero-candidate-recruitment-fix2"
        and config.get("scientific_candidate_tactics_permitted") == 0
        and runtime.get("runtime_ok") is True
        and runtime.get("candidate_tactics_executed") == 0
        and runtime.get("runtime", {}).get("lean_dojo_source_ledger_exact") is True
        and all(row.get("scientific_candidate_tactics_executed") == 0 for row in receipts)
    ):
        raise ValueError("Exp51 fix2 is not the protected sequential zero-candidate diagnostic")
    scientific_files = (
        [p for p in (SOURCE_FIX2_ROOT / "scientific").rglob("*") if p.is_file()]
        if (SOURCE_FIX2_ROOT / "scientific").exists() else []
    )
    if scientific_files:
        raise ValueError("Exp51 fix2 archive contains scientific execution and cannot be superseded mechanically")
    artifact_paths = sorted(p for p in SOURCE_FIX2_ROOT.rglob("*") if p.is_file())
    ledger = [
        {"path": str(path), "sha256": file_sha256(path), "bytes": path.stat().st_size}
        for path in artifact_paths
    ]
    return {
        "root": str(SOURCE_FIX2_ROOT),
        "reason": "sequential full-repository tracing exposed multi-hour wall time on the first repository; no scientific candidates were run",
        "scientific_candidate_tactics_executed": 0,
        "recruitment_config": str(configp),
        "recruitment_config_sha256": file_sha256(configp),
        "trace_runtime_preflight": str(runtimep),
        "trace_runtime_preflight_sha256": file_sha256(runtimep),
        "completed_repository_receipts": len(receipt_paths),
        "artifact_count": len(ledger),
        "artifact_ledger": ledger,
        "artifact_ledger_sha256": json_sha256(ledger),
    }


def validate_fix3_diagnostic() -> dict[str, Any]:
    configp = SOURCE_FIX3_ROOT / "recruitment_frozen/recruitment_config.json"
    runtimep = SOURCE_FIX3_ROOT / "preflight/trace_runtime.json"
    summaryp = SOURCE_FIX3_ROOT / "screening/build_trace_summary.json"
    receipt_paths = sorted((SOURCE_FIX3_ROOT / "screening/build_trace").glob("*.json"))
    if not configp.is_file() or not runtimep.is_file() or not summaryp.is_file() or len(receipt_paths) != 26:
        raise FileNotFoundError(
            "preserved Exp51 fix3 diagnostic is absent or incomplete; set MZX_EXP51_FIX3_ROOT"
        )
    config, runtime, summary = read_json(configp), read_json(runtimep), read_json(summaryp)
    receipts = [read_json(path) for path in receipt_paths]
    failure_counts: dict[str, int] = {}
    for row in receipts:
        gate = str(row.get("first_failed_gate"))
        failure_counts[gate] = failure_counts.get(gate, 0) + 1
    expected_failures = {
        "checkout": 3,
        "exact_toolchain": 3,
        "root_enumeration": 15,
        "trace": 4,
        "unmodified_build": 1,
    }
    if not (
        config.get("recruitment_version") == "experiment51-zero-candidate-recruitment-fix3"
        and config.get("scientific_candidate_tactics_permitted") == 0
        and runtime.get("runtime_ok") is True
        and runtime.get("candidate_tactics_executed") == 0
        and runtime.get("runtime", {}).get("lean_dojo_source_ledger_exact") is True
        and summary.get("candidates") == 26
        and summary.get("passed") == 0
        and summary.get("scientific_candidate_tactics_executed") == 0
        and failure_counts == expected_failures
        and all(row.get("scientific_candidate_tactics_executed") == 0 for row in receipts)
    ):
        raise ValueError("Exp51 fix3 is not the protected parallel zero-candidate diagnostic")
    scientific_files = (
        [p for p in (SOURCE_FIX3_ROOT / "scientific").rglob("*") if p.is_file()]
        if (SOURCE_FIX3_ROOT / "scientific").exists() else []
    )
    if scientific_files:
        raise ValueError("Exp51 fix3 archive contains scientific execution and cannot be superseded mechanically")
    artifact_paths = sorted(p for p in SOURCE_FIX3_ROOT.rglob("*") if p.is_file())
    ledger = [
        {"path": str(path), "sha256": file_sha256(path), "bytes": path.stat().st_size}
        for path in artifact_paths
    ]
    return {
        "root": str(SOURCE_FIX3_ROOT),
        "reason": "26/26 parallel qualification completed with zero scientific candidates; 15 repositories reached AST generation but failed in thread-unsafe in-process root enumeration",
        "failure_gate_counts": dict(sorted(failure_counts.items())),
        "scientific_candidate_tactics_executed": 0,
        "recruitment_config": str(configp),
        "recruitment_config_sha256": file_sha256(configp),
        "trace_runtime_preflight": str(runtimep),
        "trace_runtime_preflight_sha256": file_sha256(runtimep),
        "build_trace_summary": str(summaryp),
        "build_trace_summary_sha256": file_sha256(summaryp),
        "receipt_count": len(receipt_paths),
        "artifact_count": len(ledger),
        "artifact_ledger": ledger,
        "artifact_ledger_sha256": json_sha256(ledger),
    }


def is_fix4_position_parser_failure(message: str) -> bool:
    return bool(
        "convert_pos" in message
        and (
            "not supported between instances of 'int' and 'dict'" in message
            or "not supported between instances of \\'int\\' and \\'dict\\'" in message
        )
    )


def validate_fix4_diagnostic() -> dict[str, Any]:
    configp = SOURCE_FIX4_ROOT / "recruitment_frozen/recruitment_config.json"
    runtimep = SOURCE_FIX4_ROOT / "preflight/trace_runtime.json"
    summaryp = SOURCE_FIX4_ROOT / "screening/build_trace_summary.json"
    receipt_paths = sorted((SOURCE_FIX4_ROOT / "screening/build_trace").glob("*.json"))
    enumeration_inputs = sorted((SOURCE_FIX4_ROOT / "screening/enumeration_inputs").glob("*.json"))
    enumeration_receipts = sorted((SOURCE_FIX4_ROOT / "screening/enumeration_receipts").glob("*.json"))
    frame_paths = sorted((SOURCE_FIX4_ROOT / "screening/frames").glob("*.jsonl"))
    if (not configp.is_file() or not runtimep.is_file() or not summaryp.is_file()
            or not SOURCE_FIX4_PACKAGE.is_file() or len(receipt_paths) != 26):
        raise FileNotFoundError(
            "preserved Exp51 fix4 diagnostic is absent or incomplete; set MZX_EXP51_FIX4_ROOT"
        )
    config, runtime, summary = read_json(configp), read_json(runtimep), read_json(summaryp)
    receipts = [read_json(path) for path in receipt_paths]
    failure_counts: dict[str, int] = {}
    root_errors = []
    for row in receipts:
        gate = str(row.get("first_failed_gate"))
        failure_counts[gate] = failure_counts.get(gate, 0) + 1
        if gate == "root_enumeration":
            root_errors.append(str(row.get("error", {}).get("message", "")))
    expected_failures = {
        "checkout": 3,
        "exact_toolchain": 3,
        "root_enumeration": 15,
        "trace": 4,
        "unmodified_build": 1,
    }
    parser_signature_exact = bool(
        len(root_errors) == 15
        and all(is_fix4_position_parser_failure(message) for message in root_errors)
    )
    if not (
        config.get("recruitment_version") == "experiment51-zero-candidate-recruitment-fix4"
        and config.get("scientific_candidate_tactics_permitted") == 0
        and runtime.get("runtime_ok") is True
        and runtime.get("candidate_tactics_executed") == 0
        and runtime.get("runtime", {}).get("lean_dojo_source_ledger_exact") is True
        and summary.get("candidates") == 26
        and summary.get("passed") == 0
        and summary.get("scientific_candidate_tactics_executed") == 0
        and failure_counts == expected_failures
        and len(enumeration_inputs) == 15
        and len(enumeration_receipts) == 0
        and len(frame_paths) == 0
        and parser_signature_exact
        and file_sha256(SOURCE_FIX4_PACKAGE) == SOURCE_FIX4_PACKAGE_SHA256
        and all(row.get("scientific_candidate_tactics_executed") == 0 for row in receipts)
    ):
        raise ValueError("Exp51 fix4 is not the protected v4.27-parser zero-candidate diagnostic")
    scientific_files = (
        [p for p in (SOURCE_FIX4_ROOT / "scientific").rglob("*") if p.is_file()]
        if (SOURCE_FIX4_ROOT / "scientific").exists() else []
    )
    if scientific_files:
        raise ValueError("Exp51 fix4 archive contains scientific execution and cannot be superseded mechanically")
    artifact_paths = sorted(p for p in SOURCE_FIX4_ROOT.rglob("*") if p.is_file())
    ledger = [
        {"path": str(path), "sha256": file_sha256(path), "bytes": path.stat().st_size}
        for path in artifact_paths
    ]
    return {
        "root": str(SOURCE_FIX4_ROOT),
        "reason": "15 exact-v4.27 traces reached isolated enumeration; all failed because LeanDojo 4.20.0 passed structured byteIdx objects to an integer-only convert_pos",
        "failure_gate_counts": dict(sorted(failure_counts.items())),
        "parser_failure_signature_exact": True,
        "reusable_zero_candidate_trace_receipts": 15,
        "scientific_candidate_tactics_executed": 0,
        "recruitment_config": str(configp),
        "recruitment_config_sha256": file_sha256(configp),
        "trace_runtime_preflight": str(runtimep),
        "trace_runtime_preflight_sha256": file_sha256(runtimep),
        "build_trace_summary": str(summaryp),
        "build_trace_summary_sha256": file_sha256(summaryp),
        "receipt_count": len(receipt_paths),
        "source_code_package": str(SOURCE_FIX4_PACKAGE),
        "source_code_package_sha256": SOURCE_FIX4_PACKAGE_SHA256,
        "artifact_count": len(ledger),
        "artifact_ledger": ledger,
        "artifact_ledger_sha256": json_sha256(ledger),
    }


def validate_fix5_diagnostic() -> dict[str, Any]:
    configp = SOURCE_FIX5_ROOT / "recruitment_frozen/recruitment_config.json"
    runtimep = SOURCE_FIX5_ROOT / "preflight/trace_runtime.json"
    receipt_paths = sorted((SOURCE_FIX5_ROOT / "screening/build_trace").glob("*.json"))
    parser_preflightp = SOURCE_FIX5_ROOT / "preflight/parser_adapter.json"
    if (not configp.is_file() or not runtimep.is_file()
            or not SOURCE_FIX5_PACKAGE.is_file()):
        raise FileNotFoundError(
            "preserved Exp51 fix5 diagnostic is absent or incomplete; set MZX_EXP51_FIX5_ROOT"
        )
    config, runtime = read_json(configp), read_json(runtimep)
    resources = runtime.get("qualification_resources", {})
    if not (
        config.get("recruitment_version") == "experiment51-zero-candidate-recruitment-fix5"
        and config.get("scientific_candidate_tactics_permitted") == 0
        and runtime.get("runtime_ok") is True
        and runtime.get("theorem_sources_elaborated") == 0
        and runtime.get("candidate_tactics_executed") == 0
        and runtime.get("runtime", {}).get("lean_dojo_source_ledger_exact") is True
        and resources.get("required_disk_free_gb") == 250
        and resources.get("disk_free_gb", 250) < 250
        and resources.get("parallel_capacity_ok") is False
        and len(receipt_paths) == 0
        and not parser_preflightp.exists()
        and file_sha256(SOURCE_FIX5_PACKAGE) == SOURCE_FIX5_PACKAGE_SHA256
    ):
        raise ValueError("Exp51 fix5 is not the protected recovery-capacity preflight failure")
    scientific_files = (
        [p for p in (SOURCE_FIX5_ROOT / "scientific").rglob("*") if p.is_file()]
        if (SOURCE_FIX5_ROOT / "scientific").exists() else []
    )
    if scientific_files:
        raise ValueError("Exp51 fix5 archive contains scientific execution and cannot be superseded mechanically")
    artifact_paths = sorted(p for p in SOURCE_FIX5_ROOT.rglob("*") if p.is_file())
    ledger = [
        {"path": str(path), "sha256": file_sha256(path), "bytes": path.stat().st_size}
        for path in artifact_paths
    ]
    return {
        "root": str(SOURCE_FIX5_ROOT),
        "reason": "pinned runtime passed, but a stale 52-Lean-trace 250-GB disk gate blocked the four-parser trace-reuse workload",
        "runtime_ok": True,
        "parallel_capacity_ok": False,
        "observed_disk_free_gb": resources["disk_free_gb"],
        "stale_required_disk_free_gb": 250,
        "trace_executed": False,
        "scientific_candidate_tactics_executed": 0,
        "recruitment_config": str(configp),
        "recruitment_config_sha256": file_sha256(configp),
        "trace_runtime_preflight": str(runtimep),
        "trace_runtime_preflight_sha256": file_sha256(runtimep),
        "source_code_package": str(SOURCE_FIX5_PACKAGE),
        "source_code_package_sha256": SOURCE_FIX5_PACKAGE_SHA256,
        "artifact_count": len(ledger),
        "artifact_ledger": ledger,
        "artifact_ledger_sha256": json_sha256(ledger),
    }


def validate_fix6_diagnostic() -> dict[str, Any]:
    configp = SOURCE_FIX6_ROOT / "recruitment_frozen/recruitment_config.json"
    runtimep = SOURCE_FIX6_ROOT / "preflight/trace_runtime.json"
    parser_preflightp = SOURCE_FIX6_ROOT / "preflight/parser_adapter.json"
    smoke_root = SOURCE_FIX6_ROOT / "preflight/parser_adapter_smoke"
    inputp = smoke_root / "screening/enumeration_inputs/GasStationManager__SafeVerify.json"
    receiptp = smoke_root / "screening/enumeration_receipts/GasStationManager__SafeVerify.json"
    framep = smoke_root / "frame.jsonl"
    build_receipts = sorted((SOURCE_FIX6_ROOT / "screening/build_trace").glob("*.json"))
    if (not configp.is_file() or not runtimep.is_file() or not inputp.is_file()
            or not SOURCE_FIX6_PACKAGE.is_file()):
        raise FileNotFoundError(
            "preserved Exp51 fix6 diagnostic is absent or incomplete; set MZX_EXP51_FIX6_ROOT"
        )
    config, runtime, worker_input = read_json(configp), read_json(runtimep), read_json(inputp)
    resources = runtime.get("qualification_resources", {})
    unsigned_input = {k: v for k, v in worker_input.items() if k != "identity_sha256"}
    with zipfile.ZipFile(SOURCE_FIX6_PACKAGE, "r") as archive:
        fix6_runtime_source = archive.read(
            "experiment51_external_repository_replication/experiment51_trace_runtime.py"
        ).decode("utf-8")
    import_body = fix6_runtime_source.split("def import_traced_repo():", 1)[1]
    late_topology_order = (
        import_body.index("install_v427_position_adapter()")
        < import_body.index('os.environ.setdefault("NUM_PROCS", "2")')
    )
    if not (
        config.get("recruitment_version") == "experiment51-zero-candidate-recruitment-fix6"
        and config.get("mechanical_fix_id")
        == "exp51-recruitment-fix6-recovery-specific-capacity-gate"
        and config.get("scientific_candidate_tactics_permitted") == 0
        and runtime.get("runtime_ok") is True
        and runtime.get("theorem_sources_elaborated") == 0
        and runtime.get("candidate_tactics_executed") == 0
        and runtime.get("runtime", {}).get("lean_dojo_source_ledger_exact") is True
        and resources.get("capacity_profile") == RECOVERY_CAPACITY_PROFILE
        and resources.get("required_disk_free_gb") == 100
        and resources.get("parallel_capacity_ok") is True
        and worker_input.get("mechanical_fix_id")
        == "exp51-recruitment-fix6-recovery-specific-capacity-gate"
        and worker_input.get("slug") == "GasStationManager/SafeVerify"
        and worker_input.get("scientific_candidate_tactics_permitted") == 0
        and worker_input.get("identity_sha256") == json_sha256(unsigned_input)
        and worker_input.get("position_adapter_schema") == V427_POSITION_ADAPTER_SCHEMA
        and not parser_preflightp.exists()
        and not receiptp.exists()
        and not framep.exists()
        and len(build_receipts) == 0
        and late_topology_order
        and file_sha256(SOURCE_FIX6_PACKAGE) == SOURCE_FIX6_PACKAGE_SHA256
    ):
        raise ValueError("Exp51 fix6 is not the protected parser-topology preflight failure")
    scientific_files = (
        [p for p in (SOURCE_FIX6_ROOT / "scientific").rglob("*") if p.is_file()]
        if (SOURCE_FIX6_ROOT / "scientific").exists() else []
    )
    if scientific_files:
        raise ValueError("Exp51 fix6 archive contains scientific execution and cannot be superseded mechanically")
    artifact_paths = sorted(p for p in SOURCE_FIX6_ROOT.rglob("*") if p.is_file())
    ledger = [
        {"path": str(path), "sha256": file_sha256(path), "bytes": path.stat().st_size}
        for path in artifact_paths
    ]
    return {
        "root": str(SOURCE_FIX6_ROOT),
        "reason": "the position adapter was installed before NUM_PROCS fixed LeanDojo's import-time worker topology, so Ray actors parsed with the unadapted method",
        "runtime_ok": True,
        "parallel_capacity_ok": True,
        "parser_worker_input_preserved": True,
        "parser_worker_receipt_absent": True,
        "parser_frame_absent": True,
        "late_topology_order_exact_in_source_package": True,
        "trace_executed": False,
        "scientific_candidate_tactics_executed": 0,
        "recruitment_config": str(configp),
        "recruitment_config_sha256": file_sha256(configp),
        "trace_runtime_preflight": str(runtimep),
        "trace_runtime_preflight_sha256": file_sha256(runtimep),
        "parser_worker_input": str(inputp),
        "parser_worker_input_sha256": file_sha256(inputp),
        "source_code_package": str(SOURCE_FIX6_PACKAGE),
        "source_code_package_sha256": SOURCE_FIX6_PACKAGE_SHA256,
        "artifact_count": len(ledger),
        "artifact_ledger": ledger,
        "artifact_ledger_sha256": json_sha256(ledger),
    }


def validate_fix7_diagnostic() -> dict[str, Any]:
    configp = SOURCE_FIX7_ROOT / "recruitment_frozen/recruitment_config.json"
    runtimep = SOURCE_FIX7_ROOT / "preflight/trace_runtime.json"
    parserp = SOURCE_FIX7_ROOT / "preflight/parser_adapter.json"
    recovery_logp = SOURCE_FIX7_ROOT / "logs/recover_enumeration_fix7.log"
    build_receipts = sorted((SOURCE_FIX7_ROOT / "screening/build_trace").glob("*.json"))
    if (not configp.is_file() or not runtimep.is_file() or not parserp.is_file()
            or not recovery_logp.is_file() or not SOURCE_FIX7_PACKAGE.is_file()):
        raise FileNotFoundError(
            "preserved Exp51 fix7 diagnostic is absent or incomplete; set MZX_EXP51_FIX7_ROOT"
        )
    config, runtime, parser = read_json(configp), read_json(runtimep), read_json(parserp)
    adapter = parser.get("position_adapter", {})
    parser_execution = adapter.get("parser_execution", {})
    recovery_log = recovery_logp.read_text(encoding="utf-8", errors="replace")
    with zipfile.ZipFile(SOURCE_FIX7_PACKAGE, "r") as archive:
        fix7_screen_source = archive.read(
            "experiment51_external_repository_replication/screen_experiment51_repositories.py"
        ).decode("utf-8")
    expected_body = fix7_screen_source.split("expected_recovery = {", 1)[1].split("}", 1)[0]
    config_has_profile_but_expected_omits_it = bool(
        config.get("qualification_recovery", {}).get("parser_execution_profile")
        == PARSER_EXECUTION_PROFILE
        and "parser_execution_profile" not in expected_body
    )
    if not (
        config.get("recruitment_version") == "experiment51-zero-candidate-recruitment-fix7"
        and config.get("mechanical_fix_id")
        == "exp51-recruitment-fix7-preimport-single-parser-adapter"
        and config.get("scientific_candidate_tactics_permitted") == 0
        and runtime.get("runtime_ok") is True
        and runtime.get("candidate_tactics_executed") == 0
        and runtime.get("qualification_resources", {}).get("parallel_capacity_ok") is True
        and parser.get("adapter_ok") is True
        and parser.get("trace_executed") is False
        and parser.get("theorem_sources_elaborated") == 0
        and parser.get("candidate_tactics_executed") == 0
        and adapter.get("installed_parser_files_unchanged") is True
        and adapter.get("counters", {}).get("v427_byteIdx", 0) > 0
        and adapter.get("counters", {}).get("rejected") == 0
        and parser_execution.get("profile") == PARSER_EXECUTION_PROFILE
        and parser_execution.get("num_procs") == 2
        and parser_execution.get("num_workers") == 1
        and parser_execution.get("ray_initialized") is False
        and parser_execution.get("adapter_process_pid") == parser.get("enumeration_worker_pid")
        and "frozen fix7 recovery contract changed" in recovery_log
        and config_has_profile_but_expected_omits_it
        and len(build_receipts) == 0
        and file_sha256(SOURCE_FIX7_PACKAGE) == SOURCE_FIX7_PACKAGE_SHA256
    ):
        raise ValueError("Exp51 fix7 is not the protected recovery-contract preflight failure")
    scientific_files = (
        [p for p in (SOURCE_FIX7_ROOT / "scientific").rglob("*") if p.is_file()]
        if (SOURCE_FIX7_ROOT / "scientific").exists() else []
    )
    if scientific_files:
        raise ValueError("Exp51 fix7 archive contains scientific execution and cannot be superseded mechanically")
    artifact_paths = sorted(p for p in SOURCE_FIX7_ROOT.rglob("*") if p.is_file())
    ledger = [
        {"path": str(path), "sha256": file_sha256(path), "bytes": path.stat().st_size}
        for path in artifact_paths
    ]
    return {
        "root": str(SOURCE_FIX7_ROOT),
        "reason": "the frozen recovery config contained the parser-execution profile but the exact-equality expected dictionary omitted that same field",
        "runtime_ok": True,
        "parser_adapter_ok": True,
        "config_has_profile_but_expected_omits_it": True,
        "recovery_workers_submitted": 0,
        "trace_executed": False,
        "scientific_candidate_tactics_executed": 0,
        "recruitment_config": str(configp),
        "recruitment_config_sha256": file_sha256(configp),
        "trace_runtime_preflight": str(runtimep),
        "trace_runtime_preflight_sha256": file_sha256(runtimep),
        "parser_adapter_preflight": str(parserp),
        "parser_adapter_preflight_sha256": file_sha256(parserp),
        "recovery_failure_log": str(recovery_logp),
        "recovery_failure_log_sha256": file_sha256(recovery_logp),
        "source_code_package": str(SOURCE_FIX7_PACKAGE),
        "source_code_package_sha256": SOURCE_FIX7_PACKAGE_SHA256,
        "artifact_count": len(ledger),
        "artifact_ledger": ledger,
        "artifact_ledger_sha256": json_sha256(ledger),
    }


def is_fix8_section_parser_failure(message: str) -> bool:
    """Identify the protected failure in the exact pinned ast.py traceback."""
    return bool(
        "site-packages/lean_dojo/data_extraction/ast.py" in message
        and "line 1480, in from_data" in message
        and "assert len(children) == 2" in message
        and "AssertionError" in message
    )


def validate_fix8_diagnostic() -> dict[str, Any]:
    configp = SOURCE_FIX8_ROOT / "recruitment_frozen/recruitment_config.json"
    runtimep = SOURCE_FIX8_ROOT / "preflight/trace_runtime.json"
    parserp = SOURCE_FIX8_ROOT / "preflight/parser_adapter.json"
    summaryp = SOURCE_FIX8_ROOT / "screening/build_trace_summary.json"
    receipt_paths = sorted((SOURCE_FIX8_ROOT / "screening/build_trace").glob("*.json"))
    if (
        not configp.is_file()
        or not runtimep.is_file()
        or not parserp.is_file()
        or not summaryp.is_file()
        or not SOURCE_FIX8_PACKAGE.is_file()
        or len(receipt_paths) != 26
    ):
        raise FileNotFoundError(
            "preserved Exp51 fix8 diagnostic is absent or incomplete; set MZX_EXP51_FIX8_ROOT"
        )
    config, runtime, parser, summary = (
        read_json(configp), read_json(runtimep), read_json(parserp), read_json(summaryp)
    )
    receipts = [read_json(path) for path in receipt_paths]
    failure_counts: dict[str, int] = {}
    root_errors: list[str] = []
    for row in receipts:
        gate = "passed" if row.get("build_trace_gate") is True else str(row.get("first_failed_gate"))
        failure_counts[gate] = failure_counts.get(gate, 0) + 1
        if gate == "root_enumeration":
            root_errors.append(str(row.get("error", {}).get("message", "")))
    expected_failures = {
        "checkout": 3,
        "exact_toolchain": 3,
        "minimum_pre_replay_frame": 1,
        "passed": 2,
        "root_enumeration": 12,
        "trace": 4,
        "unmodified_build": 1,
    }
    passed_slugs = sorted(
        row["candidate"]["slug"] for row in receipts if row.get("build_trace_gate") is True
    )
    expected_passed = sorted(FIX8_FRAME_CONTROLS)
    section_errors = [message for message in root_errors
                      if is_fix8_section_parser_failure(message)]
    crlf_errors = [message for message in root_errors if "Windows-style line endings" in message]
    frame_controls = {}
    for slug, expected_count in FIX8_FRAME_CONTROLS.items():
        framep = SOURCE_FIX8_ROOT / "screening/frames" / f"{safe_slug(slug)}.jsonl"
        if not framep.is_file():
            raise FileNotFoundError(framep)
        rows = [json.loads(line) for line in framep.read_text(encoding="utf-8").splitlines()
                if line.strip()]
        if len(rows) != expected_count:
            raise ValueError(f"Exp51 fix8 control frame count changed: {slug}")
        frame_controls[slug] = {
            "rows": len(rows),
            "frame": str(framep),
            "frame_sha256": file_sha256(framep),
            "rows_sha256": json_sha256(rows),
        }
    adapter = parser.get("position_adapter", {})
    parser_execution = adapter.get("parser_execution", {})
    if not (
        config.get("recruitment_version") == "experiment51-zero-candidate-recruitment-fix8"
        and config.get("mechanical_fix_id")
        == "exp51-recruitment-fix8-recovery-contract-profile-alignment"
        and config.get("scientific_candidate_tactics_permitted") == 0
        and runtime.get("runtime_ok") is True
        and runtime.get("candidate_tactics_executed") == 0
        and runtime.get("runtime", {}).get("lean_dojo_source_ledger_exact") is True
        and runtime.get("qualification_resources", {}).get("parallel_capacity_ok") is True
        and parser.get("adapter_ok") is True
        and parser.get("trace_executed") is False
        and parser.get("candidate_tactics_executed") == 0
        and adapter.get("installed_parser_files_unchanged") is True
        and adapter.get("parser_file_sha256") == {
            "ast.py": "d8aee2af9cae0a35732a25e49c20adaf41bef265c60bd8c297445db03f866edc",
            "lean.py": "7b2e2905e733ec674bf704536087b0acfb2ba6e4b6f43f114fd98eb51e1a3d47",
        }
        and adapter.get("counters", {}).get("rejected") == 0
        and parser_execution.get("profile") == PARSER_EXECUTION_PROFILE
        and parser_execution.get("num_workers") == 1
        and parser_execution.get("ray_initialized") is False
        and summary.get("phase") == "recover-enumeration"
        and summary.get("mechanical_fix_id")
        == "exp51-recruitment-fix8-recovery-contract-profile-alignment"
        and summary.get("candidates") == 26
        and summary.get("passed") == 2
        and summary.get("reused_trace_repositories") == 15
        and summary.get("trace_executed") is False
        and summary.get("scientific_candidate_tactics_executed") == 0
        and failure_counts == expected_failures
        and passed_slugs == expected_passed
        and len(section_errors) == 11
        and len(crlf_errors) == 1
        and all(row.get("scientific_candidate_tactics_executed") == 0 for row in receipts)
        and file_sha256(SOURCE_FIX8_PACKAGE) == SOURCE_FIX8_PACKAGE_SHA256
    ):
        raise ValueError("Exp51 fix8 is not the protected parser-compatibility diagnostic")
    scientific_files = (
        [path for path in (SOURCE_FIX8_ROOT / "scientific").rglob("*") if path.is_file()]
        if (SOURCE_FIX8_ROOT / "scientific").exists() else []
    )
    if scientific_files:
        raise ValueError("Exp51 fix8 archive contains scientific execution and cannot be superseded mechanically")
    artifact_paths = sorted(path for path in SOURCE_FIX8_ROOT.rglob("*") if path.is_file())
    ledger = [
        {"path": str(path), "sha256": file_sha256(path), "bytes": path.stat().st_size}
        for path in artifact_paths
    ]
    return {
        "root": str(SOURCE_FIX8_ROOT),
        "reason": "15 hash-validated traces were parsed under the pinned topology; 11 stopped at the sole observed Lean 4.27 section layout, one stopped at standard CRLF, two passed, and one yielded zero roots",
        "failure_gate_counts": dict(sorted(failure_counts.items())),
        "section_parser_failure_count": len(section_errors),
        "standard_crlf_failure_count": len(crlf_errors),
        "passed_repositories": passed_slugs,
        "frame_controls": frame_controls,
        "trace_executed": False,
        "scientific_candidate_tactics_executed": 0,
        "recruitment_config": str(configp),
        "recruitment_config_sha256": file_sha256(configp),
        "trace_runtime_preflight": str(runtimep),
        "trace_runtime_preflight_sha256": file_sha256(runtimep),
        "parser_adapter_preflight": str(parserp),
        "parser_adapter_preflight_sha256": file_sha256(parserp),
        "build_trace_summary": str(summaryp),
        "build_trace_summary_sha256": file_sha256(summaryp),
        "source_code_package": str(SOURCE_FIX8_PACKAGE),
        "source_code_package_sha256": SOURCE_FIX8_PACKAGE_SHA256,
        "artifact_count": len(ledger),
        "artifact_ledger": ledger,
        "artifact_ledger_sha256": json_sha256(ledger),
    }


def validate_controls() -> dict[str, Any]:
    for path in (SOURCE_EXP49_CONFIG, SOURCE_EXP49_ANALYSIS, SOURCE_EXP50_SUMMARY):
        if not path.is_file():
            raise FileNotFoundError(path)
    c49, a49, s50 = (read_json(SOURCE_EXP49_CONFIG), read_json(SOURCE_EXP49_ANALYSIS),
                     read_json(SOURCE_EXP50_SUMMARY))
    if c49.get("protocol_version") != "experiment49-candidate-endpoint-robustness-v1":
        raise ValueError("wrong Exp49 source")
    if c49.get("alternative_library") != ALTERNATIVE_LIBRARY:
        raise ValueError("Exp49 candidate library differs from Exp51 L0")
    if c49.get("strict_endpoint", {}).get("schema") != STRICT_ENDPOINT_SCHEMA:
        raise ValueError("Exp49 strict endpoint differs")
    if c49.get("primary_robustness_view") != "L-mechanism-diverse":
        raise ValueError("Exp49 robust view differs")
    if a49.get("robustness", {}).get("label") != "Green":
        raise ValueError("Exp51 requires Exp49 Green")
    if s50.get("reexecution_pass") is not True or s50.get("analysis_fix1_pass") is not True:
        raise ValueError("Exp51 requires the final passing Exp50 fix1 analysis")
    if s50.get("mismatch_count") != 0 or s50.get("manual_reconciliation_count") != 0:
        raise ValueError("Exp50 exact reexecution gate is not clean")
    return {
        "exp49_config": str(SOURCE_EXP49_CONFIG),
        "exp49_config_sha256": file_sha256(SOURCE_EXP49_CONFIG),
        "exp49_analysis": str(SOURCE_EXP49_ANALYSIS),
        "exp49_analysis_sha256": file_sha256(SOURCE_EXP49_ANALYSIS),
        "exp49_robustness_label": "Green",
        "exp50_summary": str(SOURCE_EXP50_SUMMARY),
        "exp50_summary_sha256": file_sha256(SOURCE_EXP50_SUMMARY),
        "exp50_reexecution_pass": True,
        "superseded_exp51_fix0": validate_fix0_diagnostic(),
        "superseded_exp51_fix1": validate_fix1_diagnostic(),
        "superseded_exp51_fix2": validate_fix2_diagnostic(),
        "superseded_exp51_fix3": validate_fix3_diagnostic(),
        "superseded_exp51_fix4": validate_fix4_diagnostic(),
        "superseded_exp51_fix5": validate_fix5_diagnostic(),
        "superseded_exp51_fix6": validate_fix6_diagnostic(),
        "superseded_exp51_fix7": validate_fix7_diagnostic(),
        "superseded_exp51_fix8": validate_fix8_diagnostic(),
    }


def build_config(created: str) -> dict[str, Any]:
    framep = PACKAGE_ROOT / "repository_candidates.json"
    frame = read_json(framep)
    candidates = list(frame.get("candidates", []))
    slugs = [x["slug"] for x in candidates]
    if len(candidates) < TARGET_REPOSITORIES or len(slugs) != len(set(slugs)):
        raise ValueError("candidate frame is too small or contains duplicate slugs")
    forbidden = set(frame["historical_scientific_exclusions"])
    if forbidden.intersection(slugs):
        raise ValueError("Exp51 candidate frame reuses a historical scientific repository")
    for row in candidates:
        if not all(row.get(k) for k in ("slug", "url", "ref", "domain", "provenance_url")):
            raise ValueError(f"incomplete candidate: {row}")
    controls = validate_controls()
    value: dict[str, Any] = {
        "version": 1, "recruitment_version": RECRUITMENT_VERSION,
        "protocol_version": PROTOCOL_VERSION, "mechanical_fix_id": MECHANICAL_FIX_ID,
        "created_utc": created,
        "scientific_candidate_tactics_permitted": 0,
        "permitted_operations": [
            "clone and resolve candidate ref", "read license and repository metadata",
            "unmodified exact-toolchain build", "LeanDojo no-dependency trace",
            "root enumeration", "live authored replay only", "source lineage hashing",
        ],
        "target_lean_version": TARGET_LEAN_VERSION,
        "target_toolchain": TARGET_TOOLCHAIN,
        "target_repositories": TARGET_REPOSITORIES,
        "minimum_repositories": MIN_REPOSITORIES,
        "roots_per_repository": ROOTS_PER_REPOSITORY,
        "qualification_recovery": {
            "source": "preserved-exp51-fix4",
            "trace_reuse_schema": TRACE_REUSE_SCHEMA,
            "position_adapter_schema": V427_POSITION_ADAPTER_SCHEMA,
            "parser_compatibility_schema": V427_PARSER_COMPATIBILITY_SCHEMA,
            "parser_compatibility_expected": PARSER_COMPATIBILITY_EXPECTED,
            "checkout_line_endings_expected": CHECKOUT_LINE_ENDING_EXPECTED,
            "parser_execution_profile": PARSER_EXECUTION_PROFILE,
            "enumeration_workers": RECOVERY_ENUMERATION_WORKERS,
            "enumeration_timeout_seconds": RECOVERY_ENUMERATION_TIMEOUT,
            "capacity_profile": RECOVERY_CAPACITY_PROFILE,
            "trace_execution_permitted": False,
            "scientific_candidate_tactics_permitted": 0,
        },
        "selection_rule": frame["selection_rule"],
        "source_overlap_threshold": frame["source_overlap_threshold"],
        "source_overlap_metric": "shared whitespace-free whole-file SHA-256 count divided by the smaller repository file count",
        "candidate_frame": str(framep),
        "candidate_frame_sha256": file_sha256(framep),
        "candidate_count": len(candidates),
        "historical_scientific_exclusions": frame["historical_scientific_exclusions"],
        "eligibility_gates": [
            "public checkout and archival license", "exact Lean v4.27.0 toolchain",
            "unmodified build", "at least 48 repository-authored replay-valid roots",
            "one root per theorem", "single live goalsBefore goal",
            "exact authored replay", "no dependency/build/vendor/generated/benchmark source",
            "one representative per source-overlap lineage cluster",
        ],
        "source_controls": controls,
        "claim_boundary": [
            "screening outcomes are not scientific tactic outcomes",
            "no scientific alternative is executed before the Exp51 scientific freeze",
            "Exp51 concerns state-conditioned one-step executable-effect measurement only",
            "no global tactic interchangeability, proof-term equality, runtime equivalence, or prover improvement",
        ],
        "code_lock": code_lock(locked_sources()),
        "next_step": "Run zero-candidate repository screening.",
    }
    value["identity_sha256"] = json_sha256({k: v for k, v in value.items()
                                             if k not in {"created_utc", "identity_sha256"}})
    return value


def freeze(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.output_dir).resolve()
    frozen = root / "recruitment_frozen"
    cfgp = frozen / "recruitment_config.json"
    txp = frozen / "freeze_transaction.json"
    if txp.is_file() and read_json(txp).get("completed") is True:
        cfg = read_json(cfgp)
        validate_code_lock(cfg["code_lock"])
        print(json.dumps({"already_frozen": True, "config": str(cfgp)}, indent=2))
        return cfg
    for rel in ("screening/summary.json", "frozen/experiment51_config.json",
                "scientific/summary.json", "analysis/summary.json"):
        if (root / rel).exists():
            raise ValueError(f"recruitment must be frozen before {rel}")
    created = datetime.now(timezone.utc).isoformat()
    cfg = build_config(created)
    exclusive_create_json(frozen / "freeze_claim.json", {
        "version": 1, "created_utc": created, "identity_sha256": cfg["identity_sha256"]})
    atomic_json_dump(cfg, cfgp)
    receipt = {
        "version": 1, "config": str(cfgp), "config_sha256": file_sha256(cfgp),
        "candidate_frame_sha256": cfg["candidate_frame_sha256"],
        "scientific_candidate_tactics_executed": 0,
        "next_step": cfg["next_step"],
    }
    atomic_json_dump(receipt, frozen / "freeze_receipt.json")
    atomic_json_dump({"version": 1, "completed": True,
                      "config_sha256": file_sha256(cfgp)}, txp)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return cfg


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", default=str(ARTIFACT_ROOT))
    return p.parse_args()


if __name__ == "__main__":
    freeze(parse_args())
