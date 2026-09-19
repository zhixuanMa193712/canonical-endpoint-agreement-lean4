"""Freeze the untouched Exp62 candidate frame without executing Lean tactics."""
from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path
from typing import Any

from experiment62_protocol import *


def shortest_authored_witness(row: dict[str, Any]) -> list[dict[str, Any]] | None:
    traces = list(row.get("traced_tactics") or [])
    if not traces or not isinstance(traces[0].get("state_before"), str):
        return None
    edges: dict[str, list[tuple[str, str]]] = {}
    for trace in traces:
        tactic = str(trace.get("tactic") or "")
        before = trace.get("state_before")
        after = trace.get("state_after")
        if (
            forbidden_tactic(tactic)
            or not isinstance(before, str)
            or not isinstance(after, str)
        ):
            continue
        edges.setdefault(before, []).append((after, tactic))
    start = str(traces[0]["state_before"])
    queue: deque[tuple[str, list[dict[str, Any]]]] = deque([(start, [])])
    seen = {start}
    while queue:
        state, path = queue.popleft()
        if len(path) >= MAX_WITNESS_DEPTH:
            continue
        for after, tactic in edges.get(state, []):
            step = {
                "step_index": len(path),
                "tactic": tactic,
                "tactic_head": tactic_head(tactic),
                "state_before_sha256": json_sha256(state),
                "state_before_text48_sha256": endpoint_key(state),
                "state_after_sha256": json_sha256(after),
                "state_after_text48_sha256": endpoint_key(after),
                "recorded_terminal": after.strip() == "no goals",
            }
            candidate = path + [step]
            if after.strip() == "no goals":
                return candidate
            if after not in seen:
                seen.add(after)
                queue.append((after, candidate))
    return None


def build_frame(benchmark: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if file_sha256(benchmark) != BENCHMARK_SHA256:
        raise ValueError("LeanDojo Benchmark 4 random/test identity changed")
    rows = json.loads(benchmark.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or len(rows) != BENCHMARK_ROWS:
        raise ValueError("unexpected benchmark row count")
    eligible: dict[str, list[dict[str, Any]]] = {stratum: [] for stratum in STRATA}
    for source_index, row in enumerate(rows):
        if row.get("url") != REPO_URL or row.get("commit") != REPO_COMMIT:
            raise ValueError("benchmark repository identity changed")
        witness = shortest_authored_witness(row)
        if witness is None or not MIN_WITNESS_DEPTH <= len(witness) <= MAX_WITNESS_DEPTH:
            continue
        stratum = "authored_depth_2" if len(witness) == 2 else "authored_depth_3_to_6"
        theorem_id = f"{row['file_path']}::{row['full_name']}"
        target_id = json_sha256([REPO_COMMIT, theorem_id])[:24]
        tactics = [step["tactic"] for step in witness]
        panel = candidate_panel(target_id, tactics)
        record = {
            "version": VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "target_id": target_id,
            "theorem_id": theorem_id,
            "repo_url": REPO_URL,
            "repo_commit": REPO_COMMIT,
            "file_path": row["file_path"],
            "full_name": row["full_name"],
            "benchmark_source_index": source_index,
            "benchmark_row_sha256": json_sha256(row),
            "authored_witness": witness,
            "authored_witness_tactics": tactics,
            "authored_witness_depth": len(witness),
            "stratum": stratum,
            "candidate_panel": panel,
            "candidate_panel_sha256": json_sha256(panel),
            "frame_selection_key": selection_key(FRAME_SEED, stratum, target_id),
            "qualification_executes_four_scientific_policies": False,
            "target_specific_witness_disclosed_to_all_policies": True,
        }
        eligible[stratum].append(record)

    frame: list[dict[str, Any]] = []
    for stratum in STRATA:
        ordered = sorted(eligible[stratum], key=lambda row: row["frame_selection_key"])
        required = PILOT_FRAME_PER_STRATUM + CONFIRMATION_FRAME_PER_STRATUM
        if len(ordered) < required:
            raise ValueError(f"insufficient offline eligible roots in {stratum}")
        for index, record in enumerate(ordered[:required]):
            role = "pilot" if index < PILOT_FRAME_PER_STRATUM else "confirmation"
            role_index = index if role == "pilot" else index - PILOT_FRAME_PER_STRATUM
            record.update({
                "role": role,
                "role_rank_within_stratum": role_index + 1,
                "scientific_policy_execution_before_initial_freeze": 0,
            })
            frame.append(seal(record))
    counts = {stratum: len(eligible[stratum]) for stratum in STRATA}
    return (
        sorted(frame, key=lambda row: (
            row["role"], row["stratum"], row["role_rank_within_stratum"]
        )),
        counts,
    )


def freeze(workspace: Path) -> dict[str, Any]:
    frozen = PACKAGE_ROOT / "frozen"
    frozen.mkdir(parents=True, exist_ok=True)
    benchmark = workspace / BENCHMARK_RELATIVE
    frame, eligible_counts = build_frame(benchmark)
    frame_path = frozen / "candidate_frame.jsonl"
    atomic_jsonl_dump(frame, frame_path)
    implementations = [
        path for path in sorted(PACKAGE_ROOT.glob("*.py"), key=lambda item: item.name)
        if path.name != "__pycache__"
    ]
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "design_type": "prospective_two-stage_witness_injected_multistep_search",
        "benchmark": str(BENCHMARK_RELATIVE),
        "benchmark_sha256": BENCHMARK_SHA256,
        "benchmark_rows": BENCHMARK_ROWS,
        "benchmark_partition": "random/test",
        "offline_eligible_roots": sum(eligible_counts.values()),
        "offline_eligible_by_stratum": eligible_counts,
        "repository_url": REPO_URL,
        "repository_commit": REPO_COMMIT,
        "candidate_frame_path": "frozen/candidate_frame.jsonl",
        "candidate_frame_rows": len(frame),
        "candidate_frame_sha256": file_sha256(frame_path),
        "roles": {
            role: sum(row["role"] == role for row in frame)
            for role in ("pilot", "confirmation")
        },
        "strata": {
            stratum: sum(row["stratum"] == stratum for row in frame)
            for stratum in STRATA
        },
        "implementation_locks": [
            {"path": path.name, "bytes": path.stat().st_size, "sha256": file_sha256(path)}
            for path in implementations
        ],
        "offline_eligibility": {
            "minimum_authored_witness_depth": MIN_WITNESS_DEPTH,
            "maximum_authored_witness_depth": MAX_WITNESS_DEPTH,
            "forbidden_tactics": ["sorry", "admit"],
            "shortest_path_over_recorded_state_transition_graph": True,
            "lean_tactics_executed": 0,
        },
        "qualification": {
            "fresh_live_authored_witness_replay": True,
            "root_candidate_panel_one_step_terminal_exclusion": True,
            "four_scientific_policies_executed": False,
            "selection_rule": (
                "within each role and authored-depth stratum, select the first frozen-rank "
                "roots passing live witness replay and the no-one-step-terminal gate"
            ),
        },
        "pilot": {
            "roots": EXPECTED_PILOT_ROOTS,
            "roots_per_stratum": PILOT_ROOTS_PER_STRATUM,
            "go_gate": (
                "all 16 roots policy-complete and at least 12 full-policy proofs have "
                "two or more external tactic invocations"
            ),
            "budget_tuning_after_pilot": False,
        },
        "confirmation": {
            "roots": EXPECTED_CONFIRMATION_ROOTS,
            "roots_per_stratum": CONFIRMATION_ROOTS_PER_STRATUM,
            "policies": list(POLICIES),
            "policy_order": "target-hash cyclic Latin order; policies sequential within root",
            "maximum_search_depth": MAX_SEARCH_DEPTH,
            "maximum_expanded_nodes": MAX_EXPANDED_NODES,
            "maximum_tactic_invocations": MAX_TACTIC_INVOCATIONS,
            "policy_timeout_seconds": POLICY_TIMEOUT_SECONDS,
            "coverage_noninferiority_margin": COVERAGE_NONINFERIORITY_MARGIN,
            "minimum_full_multistep_solves_information_gate": MIN_CONFIRMATION_FULL_MULTISTEP_SOLVES,
            "operational_missing_coverage_rule": "worst-case loss imputation",
        },
        "primary_estimands": [
            "root-level solve rate and multi-step solve rate by policy",
            "effect-aware loss fraction relative to full with one-sided Wilson upper bound",
            "paired full-minus-effect-aware Lean tactic-invocation count",
        ],
        "secondary_estimands": [
            "expanded nodes", "time-to-first-proof", "wall-clock", "endpoint coverage"
        ],
        "effect_endpoint_canonicalizer": "text48_v1",
        "claim_boundary": [
            "real LeanDojo interaction over theorem roots from random/test",
            "every eligible root has an independently replayed authored multi-step witness",
            "the witness action set is disclosed to every policy to remove candidate acquisition as a bottleneck",
            "this is a controlled search-policy evaluation, not autonomous tactic generation",
            "text48 endpoint identity is not proof-term or semantic state identity",
        ],
        "scientific_policy_jobs_executed_before_freeze": 0,
        "next_step": "Install the frozen design on the server and run environment preflight.",
    })
    atomic_json_dump(value, frozen / "initial_protocol.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=str(WORKSPACE_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(freeze(Path(args.workspace).resolve()), indent=2))
