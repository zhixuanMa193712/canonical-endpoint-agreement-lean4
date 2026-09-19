"""Qualify one Exp62 root by live witness replay and a one-step terminal screen."""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from experiment62_protocol import *
from experiment62_dojo import canonical_repo, load_lean_dojo, run_tactic, theorem_for


def lean_pid(dojo: Any) -> int | None:
    for name in ("proc", "_proc", "process", "_process"):
        process = getattr(dojo, name, None)
        pid = getattr(process, "pid", None)
        if isinstance(pid, int):
            return pid
    return None


def qualify(target: dict[str, Any], output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError("Exp62 qualification receipt overwrite is forbidden")
    started = time.monotonic()
    value: dict[str, Any] = {
        "schema": QUALIFICATION_SCHEMA,
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "target_id": target["target_id"],
        "role": target["role"],
        "stratum": target["stratum"],
        "theorem_id": target["theorem_id"],
        "target_record_sha256": target["record_sha256"],
        "candidate_panel_sha256": target["candidate_panel_sha256"],
        "worker_pid": os.getpid(),
        "attempt_ordinal": 1,
        "retry_permitted": False,
        "four_scientific_policies_executed": 0,
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
    }
    context = None
    try:
        api = load_lean_dojo()
        repo = canonical_repo(api)
        theorem = theorem_for(api, repo, target)
        context = api["Dojo"](theorem, timeout=TACTIC_TIMEOUT_SECONDS)
        dojo, initial = context.__enter__()
        initial_text = str(initial.pp)
        initial_key = endpoint_key(initial_text)
        expected_initial = target["authored_witness"][0]["state_before_text48_sha256"]
        initial_exact = initial_key == expected_initial

        root_rows = []
        root_terminal = False
        operational_failure = False
        for position, tactic in enumerate(target["candidate_panel"]):
            result = run_tactic(api, dojo, initial, tactic)
            row = {
                "candidate_position_frozen": position,
                "tactic": tactic,
                "head": tactic_head(tactic),
                "kind": result["kind"],
                "terminal": result.get("terminal") is True,
                "endpoint_key": result.get("endpoint_key"),
                "elapsed_seconds_descriptive": result.get("elapsed_seconds_descriptive"),
            }
            root_rows.append(row)
            root_terminal = root_terminal or row["terminal"]
            if result["kind"] in {"operational_exception", "unexpected_result"}:
                operational_failure = True
                break

        current = initial
        live_steps = []
        witness_ok = bool(initial_exact and not operational_failure)
        for step in target["authored_witness"]:
            if not witness_ok:
                break
            before_text = str(current.pp)
            before_key = endpoint_key(before_text)
            before_exact = before_key == step["state_before_text48_sha256"]
            if not before_exact:
                witness_ok = False
                live_steps.append({
                    "step_index": step["step_index"],
                    "tactic": step["tactic"],
                    "before_endpoint_key": before_key,
                    "before_recorded_text48_exact": False,
                    "kind": "recorded_state_mismatch",
                })
                break
            result = run_tactic(api, dojo, current, step["tactic"])
            live = {
                "step_index": step["step_index"],
                "tactic": step["tactic"],
                "before_state_sha256": json_sha256(before_text),
                "before_endpoint_key": before_key,
                "before_recorded_text48_exact": before_exact,
                "kind": result["kind"],
                "terminal": result.get("terminal") is True,
                "after_endpoint_key": result.get("endpoint_key"),
                "elapsed_seconds_descriptive": result.get("elapsed_seconds_descriptive"),
            }
            live_steps.append(live)
            final = int(step["step_index"]) == len(target["authored_witness"]) - 1
            if final:
                witness_ok = result["kind"] == "proof_finished"
            elif result["kind"] == "tactic_state":
                current = result["state_obj"]
                witness_ok = (
                    result.get("endpoint_key") == step["state_after_text48_sha256"]
                )
            else:
                witness_ok = False

        qualification_gate = bool(
            initial_exact
            and witness_ok
            and len(live_steps) == target["authored_witness_depth"]
            and not root_terminal
            and not operational_failure
        )
        value.update({
            "lean_process_pid": lean_pid(dojo),
            "initial_state_sha256": json_sha256(initial_text),
            "initial_endpoint_key": initial_key,
            "initial_recorded_text48_exact": initial_exact,
            "root_candidate_rows": root_rows,
            "root_candidate_calls": len(root_rows),
            "root_one_step_terminal_count": sum(row["terminal"] for row in root_rows),
            "root_one_step_terminal_gate": not root_terminal,
            "live_witness_steps": live_steps,
            "live_witness_depth": len(live_steps),
            "live_witness_replay_gate": witness_ok,
            "operational_failure": operational_failure,
            "qualification_gate": qualification_gate,
            "first_failed_gate": None if qualification_gate else (
                "initial_state_identity" if not initial_exact else
                "qualification_operational_failure" if operational_failure else
                "root_one_step_terminal" if root_terminal else
                "live_witness_replay"
            ),
        })
    except Exception as error:
        value.update({
            "operational_failure": True,
            "qualification_gate": False,
            "first_failed_gate": "dojo_initialization_or_worker",
            "error_type": type(error).__name__,
            "error_sha256": json_sha256(str(error)),
            "error_tail": str(error)[-4000:],
        })
    finally:
        if context is not None:
            try:
                context.__exit__(None, None, None)
            except Exception:
                pass
    value["wall_clock_seconds_descriptive"] = time.monotonic() - started
    atomic_json_dump(seal(value), output)
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    target = read_json(args.target)
    assert_sealed(target, "Exp62 qualification target")
    print(json.dumps(qualify(target, Path(args.output).resolve()), indent=2))
