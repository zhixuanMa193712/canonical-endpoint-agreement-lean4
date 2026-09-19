"""Execute one frozen Exp62 search policy in one fresh LeanDojo session."""
from __future__ import annotations

import argparse
import collections
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from experiment62_protocol import *
from experiment62_dojo import canonical_repo, load_lean_dojo, run_tactic, theorem_for


@dataclass
class SearchNode:
    state_obj: Any
    state_text: str
    endpoint: str
    path: list[str]
    ancestor_endpoints: frozenset[str]


def lean_pid(dojo: Any) -> int | None:
    for name in ("proc", "_proc", "process", "_process"):
        process = getattr(dojo, name, None)
        pid = getattr(process, "pid", None)
        if isinstance(pid, int):
            return pid
    return None


def run_search(inp: dict[str, Any], output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError("Exp62 policy receipt overwrite is forbidden")
    job = inp["job"]
    target = inp["target"]
    if (
        inp.get("input_identity_sha256")
        != json_sha256({k: v for k, v in inp.items() if k != "input_identity_sha256"})
        or job.get("job_identity_sha256")
        != json_sha256({k: v for k, v in job.items() if k != "job_identity_sha256"})
        or job.get("target_id") != target.get("target_id")
        or job.get("candidate_panel_sha256") != target.get("candidate_panel_sha256")
    ):
        raise ValueError("Exp62 policy worker input changed")
    started = time.monotonic()
    value: dict[str, Any] = {
        "schema": JOB_SCHEMA,
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "phase": job["phase"],
        "job": job,
        "job_id": job["job_id"],
        "target_id": target["target_id"],
        "theorem_id": target["theorem_id"],
        "stratum": target["stratum"],
        "policy": job["policy"],
        "input_identity_sha256": inp["input_identity_sha256"],
        "worker_pid": os.getpid(),
        "attempt_ordinal": 1,
        "retry_permitted": False,
        "witness_injection_disclosed": True,
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
    }
    context = None
    search_started: float | None = None
    initialization_finished: float | None = None
    search_finished: float | None = None
    proof_elapsed: float | None = None
    counters = {
        "expanded_nodes": 0,
        "tactic_invocations": 0,
        "successful_nonterminal_transitions": 0,
        "lean_rejections": 0,
        "tactic_timeouts": 0,
        "selected_children": 0,
        "effect_collisions_observed": 0,
        "head_collisions_observed": 0,
        "cycle_children_rejected": 0,
        "witness_injections": 0,
        "maximum_queue_size": 1,
    }
    endpoint_set: set[str] = set()
    transition_rows: list[dict[str, Any]] = []
    solved = False
    proof: list[str] | None = None
    operational_failure = False
    budget_exhausted = False
    stop_reason = "queue_exhausted"
    try:
        api = load_lean_dojo()
        repo = canonical_repo(api)
        theorem = theorem_for(api, repo, target)
        context = api["Dojo"](theorem, timeout=job["tactic_timeout_seconds"])
        dojo, initial = context.__enter__()
        initial_text = str(initial.pp)
        initial_endpoint = endpoint_key(initial_text)
        if initial_endpoint != target["live_initial_endpoint_key"]:
            raise ValueError("Exp62 live initial endpoint changed after qualification")
        initialization_finished = time.monotonic()
        search_started = initialization_finished
        queue: collections.deque[SearchNode] = collections.deque([
            SearchNode(initial, initial_text, initial_endpoint, [], frozenset({initial_endpoint}))
        ])
        endpoint_set.add(initial_endpoint)
        while queue:
            elapsed = time.monotonic() - search_started
            if elapsed >= job["policy_timeout_seconds"]:
                stop_reason = "policy_timeout"
                budget_exhausted = True
                break
            if counters["expanded_nodes"] >= job["maximum_expanded_nodes"]:
                stop_reason = "maximum_expanded_nodes"
                budget_exhausted = True
                break
            node = queue.popleft()
            if len(node.path) >= job["maximum_search_depth"]:
                continue
            counters["expanded_nodes"] += 1
            next_witness = target["live_witness_next_tactic_by_endpoint"].get(node.endpoint)
            if next_witness is not None:
                counters["witness_injections"] += 1
            candidates = ordered_candidates(target["candidate_panel"], next_witness)
            children: list[dict[str, Any]] = []
            runtime_states: dict[int, Any] = {}
            for candidate_position, tactic in enumerate(candidates):
                if counters["tactic_invocations"] >= job["maximum_tactic_invocations"]:
                    stop_reason = "maximum_tactic_invocations"
                    budget_exhausted = True
                    break
                if time.monotonic() - search_started >= job["policy_timeout_seconds"]:
                    stop_reason = "policy_timeout"
                    budget_exhausted = True
                    break
                counters["tactic_invocations"] += 1
                result = run_tactic(api, dojo, node.state_obj, tactic)
                transition = {
                    "expanded_node_ordinal": counters["expanded_nodes"],
                    "parent_depth": len(node.path),
                    "parent_endpoint_key": node.endpoint,
                    "candidate_position_executed": candidate_position,
                    "tactic": tactic,
                    "head": tactic_head(tactic),
                    "registered_next_witness": tactic == next_witness,
                    "kind": result["kind"],
                    "terminal": result.get("terminal") is True,
                    "endpoint_key": result.get("endpoint_key"),
                    "elapsed_seconds_descriptive": result.get("elapsed_seconds_descriptive"),
                }
                transition_rows.append(transition)
                if result["kind"] == "proof_finished":
                    solved = True
                    proof = node.path + [tactic]
                    proof_elapsed = time.monotonic() - search_started
                    stop_reason = "proved"
                    break
                if result["kind"] == "tactic_state":
                    counters["successful_nonterminal_transitions"] += 1
                    child_endpoint = str(result["endpoint_key"])
                    endpoint_set.add(child_endpoint)
                    child = {
                        "child_index": len(children),
                        "tactic": tactic,
                        "head": tactic_head(tactic),
                        "endpoint_key": child_endpoint,
                        "state_text_sha256": result["state_sha256"],
                    }
                    runtime_states[len(children)] = result["state_obj"]
                    children.append(child)
                elif result["kind"] == "lean_rejection":
                    counters["lean_rejections"] += 1
                elif result["kind"] == "tactic_timeout":
                    counters["tactic_timeouts"] += 1
                else:
                    operational_failure = True
                    stop_reason = "operational_failure_during_tactic"
                    value.update({
                        "operational_error_kind": result["kind"],
                        "operational_error_type": result.get("error_type"),
                        "operational_error_sha256": result.get("error_sha256"),
                        "operational_error_tail": result.get("error_tail"),
                    })
                    break
            if solved or operational_failure or budget_exhausted:
                break
            effect_count = len(choose_children(
                "effect_aware", children, target["target_id"], node.endpoint
            ))
            head_count = len(choose_children(
                "head_dedup", children, target["target_id"], node.endpoint
            ))
            counters["effect_collisions_observed"] += len(children) - effect_count
            counters["head_collisions_observed"] += len(children) - head_count
            selected = choose_children(job["policy"], children, target["target_id"], node.endpoint)
            counters["selected_children"] += len(selected)
            for child in selected:
                endpoint = str(child["endpoint_key"])
                if endpoint in node.ancestor_endpoints:
                    counters["cycle_children_rejected"] += 1
                    continue
                child_index = int(child["child_index"])
                state_obj = runtime_states[child_index]
                state_text = str(state_obj.pp)
                queue.append(SearchNode(
                    state_obj=state_obj,
                    state_text=state_text,
                    endpoint=endpoint,
                    path=node.path + [str(child["tactic"])],
                    ancestor_endpoints=node.ancestor_endpoints | {endpoint},
                ))
            counters["maximum_queue_size"] = max(counters["maximum_queue_size"], len(queue))
        value.update({
            "lean_process_pid": lean_pid(dojo),
            "initial_endpoint_key": initial_endpoint,
        })
    except Exception as error:
        operational_failure = True
        stop_reason = "dojo_initialization_or_worker_exception"
        value.update({
            "operational_error_type": type(error).__name__,
            "operational_error_sha256": json_sha256(str(error)),
            "operational_error_tail": str(error)[-4000:],
        })
    finally:
        if search_started is not None:
            search_finished = time.monotonic()
        if context is not None:
            try:
                context.__exit__(None, None, None)
            except Exception:
                pass
    elapsed = time.monotonic() - started
    search_elapsed = (
        search_finished - search_started
        if search_started is not None and search_finished is not None else None
    )
    value.update(counters)
    value.update({
        "solved": solved,
        "proof": proof,
        "proof_length": len(proof) if proof is not None else None,
        "multi_step_solved": proof is not None and len(proof) >= MIN_WITNESS_DEPTH,
        "time_to_first_proof_seconds_descriptive": proof_elapsed,
        "search_wall_clock_seconds_descriptive": search_elapsed,
        "environment_initialization_seconds_descriptive": (
            initialization_finished - started
            if initialization_finished is not None else None
        ),
        "wall_clock_seconds_descriptive": elapsed,
        "budget_exhausted": budget_exhausted,
        "operational_failure": operational_failure,
        "coverage_evaluable": not operational_failure,
        "efficiency_evaluable": not operational_failure,
        "stop_reason": stop_reason,
        "unique_observed_endpoint_keys": sorted(endpoint_set),
        "unique_observed_endpoint_count": len(endpoint_set),
        "transition_rows": transition_rows,
        "all_tactic_invocations_actual": len(transition_rows) == counters["tactic_invocations"],
        "fresh_policy_worker_process": True,
        "fresh_lean_session_process": value.get("lean_process_pid") is not None,
    })
    atomic_json_dump(seal(value), output)
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    inp = read_json(args.input)
    print(json.dumps(run_search(inp, Path(args.output).resolve()), indent=2))
