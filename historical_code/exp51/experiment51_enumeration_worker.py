"""Fresh-process LeanDojo root enumeration worker for Exp51 qualification."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from experiment51_protocol import (
    MECHANICAL_FIX_ID,
    atomic_json_dump,
    atomic_jsonl_dump,
    file_sha256,
    json_sha256,
    read_json,
)
from experiment51_trace_runtime import position_adapter_receipt
from screen_experiment51_repositories import enumerate_frame


def run(input_path: Path) -> dict:
    payload = read_json(input_path)
    identity = payload.get("identity_sha256")
    unsigned = {k: v for k, v in payload.items() if k != "identity_sha256"}
    if identity != json_sha256(unsigned):
        raise ValueError("enumeration input identity changed")
    if payload.get("mechanical_fix_id") != MECHANICAL_FIX_ID:
        raise ValueError("wrong Exp51 enumeration mechanical fix")
    if payload.get("scientific_candidate_tactics_permitted") != 0:
        raise ValueError("enumeration worker requires an empty scientific candidate surface")

    project = Path(payload["project"]).resolve()
    framep = Path(payload["frame_output"]).resolve()
    receiptp = Path(payload["receipt_output"]).resolve()
    if not project.is_dir():
        raise FileNotFoundError(project)

    frame, exclusions = enumerate_frame(project, payload["slug"], payload["commit"])
    adapter = position_adapter_receipt()
    parser_execution = adapter.get("parser_execution", {})
    if not (
        adapter.get("schema") == payload.get("position_adapter_schema")
        and adapter.get("parser_compatibility_schema")
        == payload.get("parser_compatibility_schema")
        and adapter.get("installed_parser_files_unchanged") is True
        and adapter.get("counters", {}).get("v427_byteIdx", 0) > 0
        and adapter.get("counters", {}).get("rejected") == 0
        and adapter.get("section_adapter", {}).get("counters", {}).get("rejected") == 0
        and adapter.get("section_adapter", {}).get("header_counters", {}).get("rejected") == 0
        and adapter.get("crlf_adapter", {}).get("counters", {}).get("rejected") == 0
        and adapter.get("crlf_adapter", {}).get("accepted")
        == "standard-CRLF-normalized-to-LF-byte-width"
        and adapter.get("crlf_adapter", {}).get("byte_index_semantics")
        == "Lean-v4.27-LF-normalized-source-buffer"
        and adapter.get("crlf_adapter", {}).get("checkout_modified") is False
        and parser_execution.get("profile") == payload.get("parser_execution_profile")
        and parser_execution.get("num_procs") == 2
        and parser_execution.get("num_workers") == 1
        and parser_execution.get("ray_initialized") is False
        and parser_execution.get("adapter_process_pid") == os.getpid()
    ):
        raise ValueError(f"Lean 4.27 parser-compatibility/topology gate failed: {adapter}")
    atomic_jsonl_dump(frame, framep)
    receipt = {
        "version": 1,
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
        "trace_reuse_ledger_sha256": payload.get("trace_reuse_ledger_sha256"),
        "scientific_candidate_tactics_executed": 0,
    }
    atomic_json_dump(receipt, receiptp)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(Path(args.input))
