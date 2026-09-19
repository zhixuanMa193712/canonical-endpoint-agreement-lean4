"""Fresh-process Exp51 extension enumeration with no remote dependency metadata."""
from __future__ import annotations

import argparse
import hashlib
import inspect
import os
import traceback
from pathlib import Path
from typing import Any

from experiment51_extension_protocol import *
from experiment51_extension_protocol import base

import screen_experiment51_repositories as base_screen
from experiment51_trace_runtime import position_adapter_receipt


_OFFLINE_STATE: dict[str, Any] | None = None


class _ForbiddenGithub:
    def __init__(self, state: dict[str, Any]):
        self.state = state

    def get_repo(self, *args: Any, **kwargs: Any) -> Any:
        self.state["github_api_attempts"] += 1
        raise RuntimeError("GitHub API access is forbidden during offline root enumeration")


def install_offline_import_adapter() -> None:
    global _OFFLINE_STATE
    original_import = base_screen.import_traced_repo

    def import_traced_repo_offline():
        global _OFFLINE_STATE
        traced_repo = original_import()
        from lean_dojo.data_extraction import lean as lean_module  # type: ignore

        original = lean_module.LeanGitRepo.get_dependencies
        source = inspect.getsource(original)
        source_file = Path(inspect.getsourcefile(original) or "").resolve()
        state = {
            "schema": "leandojo-4.20.0-buildDeps-false-no-remote-metadata-v1",
            "dependency_queries_suppressed": 0,
            "github_api_attempts": 0,
            "returned_dependency_maps": [],
            "original_get_dependencies_sha256": hashlib.sha256(
                source.encode("utf-8")
            ).hexdigest(),
            "original_module_file": str(source_file),
            "original_module_file_sha256": file_sha256(source_file),
            "in_memory_only": True,
            "installed_lean_dojo_files_modified": False,
            "repository_checkout_modified": False,
        }

        def get_dependencies_offline(self: Any, path: Any = None) -> dict[str, Any]:
            state["dependency_queries_suppressed"] += 1
            state["returned_dependency_maps"].append(0)
            return {}

        lean_module.LeanGitRepo.get_dependencies = get_dependencies_offline
        lean_module.GITHUB = _ForbiddenGithub(state)
        _OFFLINE_STATE = state
        return traced_repo

    base_screen.import_traced_repo = import_traced_repo_offline


def offline_receipt() -> dict[str, Any]:
    if _OFFLINE_STATE is None:
        raise RuntimeError("offline dependency adapter was not instantiated")
    return dict(_OFFLINE_STATE)


def run(input_path: Path) -> dict:
    payload = read_json(input_path)
    identity = payload.get("identity_sha256")
    unsigned = {key: value for key, value in payload.items() if key != "identity_sha256"}
    if identity != json_sha256(unsigned):
        raise ValueError("extension enumeration input identity changed")
    if payload.get("mechanical_fix_id") != MECHANICAL_FIX_ID:
        raise ValueError("wrong extension enumeration mechanical fix")
    if payload.get("scientific_candidate_tactics_permitted") != 0:
        raise ValueError("extension enumeration requires an empty scientific candidate surface")

    project = Path(payload["project"]).resolve()
    framep = Path(payload["frame_output"]).resolve()
    receiptp = Path(payload["receipt_output"]).resolve()
    if not project.is_dir():
        raise FileNotFoundError(project)

    install_offline_import_adapter()
    try:
        frame, exclusions = base_screen.enumerate_frame(
            project, payload["slug"], payload["commit"]
        )
        adapter = position_adapter_receipt()
        offline = offline_receipt()
        parser_execution = adapter.get("parser_execution", {})
        if not (
            adapter.get("schema") == base.V427_POSITION_ADAPTER_SCHEMA
            and adapter.get("parser_compatibility_schema")
            == base.V427_PARSER_COMPATIBILITY_SCHEMA
            and adapter.get("installed_parser_files_unchanged") is True
            and adapter.get("counters", {}).get("v427_byteIdx", 0) > 0
            and adapter.get("counters", {}).get("rejected") == 0
            and adapter.get("section_adapter", {}).get("counters", {}).get("rejected") == 0
            and adapter.get("section_adapter", {}).get("header_counters", {}).get("rejected") == 0
            and adapter.get("crlf_adapter", {}).get("counters", {}).get("rejected") == 0
            and parser_execution.get("profile") == base.PARSER_EXECUTION_PROFILE
            and parser_execution.get("num_workers") == 1
            and parser_execution.get("ray_initialized") is False
            and parser_execution.get("adapter_process_pid") == os.getpid()
            and offline.get("dependency_queries_suppressed") == 1
            and offline.get("github_api_attempts") == 0
            and offline.get("returned_dependency_maps") == [0]
        ):
            raise ValueError("extension parser/offline-dependency gate failed")
        atomic_jsonl_dump(frame, framep)
        receipt = {
            "version": 1,
            "extension_version": EXTENSION_VERSION,
            "mechanical_fix_id": MECHANICAL_FIX_ID,
            "worker_ok": True,
            "worker_pid": os.getpid(),
            "input": str(input_path.resolve()),
            "input_identity_sha256": identity,
            "slug": payload["slug"],
            "commit": payload["commit"],
            "project": str(project),
            "pre_replay_frame": len(frame),
            "exclusions": dict(sorted(exclusions.items())),
            "frame": str(framep),
            "frame_sha256": file_sha256(framep),
            "position_adapter": adapter,
            "offline_dependency_adapter": offline,
            "trace_ledger_sha256": payload.get("trace_ledger_sha256"),
            "scientific_candidate_tactics_executed": 0,
        }
        atomic_json_dump(receipt, receiptp)
        return receipt
    except BaseException as exc:
        failure = {
            "version": 1,
            "extension_version": EXTENSION_VERSION,
            "mechanical_fix_id": MECHANICAL_FIX_ID,
            "worker_ok": False,
            "worker_pid": os.getpid(),
            "input_identity_sha256": identity,
            "slug": payload.get("slug"),
            "commit": payload.get("commit"),
            "error_type": type(exc).__name__,
            "error_message": str(exc)[-12000:],
            "traceback_tail": traceback.format_exc()[-12000:],
            "position_adapter": (
                position_adapter_receipt() if _OFFLINE_STATE is not None else None
            ),
            "offline_dependency_adapter": (
                offline_receipt() if _OFFLINE_STATE is not None else None
            ),
            "scientific_candidate_tactics_executed": 0,
        }
        atomic_json_dump(failure, receiptp)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(Path(args.input))
