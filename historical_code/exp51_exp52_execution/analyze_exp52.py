"""Offline preregistered analysis of Exp52 continuation cell receipts.

The script joins the two independently executed sides of every frozen cell,
constructs the seven-category response taxonomy, computes root-pair estimands,
and applies the frozen hierarchical bootstrap and decision order.  It never
imports or invokes Lean.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence

from alignment_protocol import *  # noqa: F401,F403


ANALYSIS_SCHEMA = "experiment52-bounded-continuation-analysis-fix3-v1"
RESPONSE_SCHEMA = "experiment52-paired-probe-response-fix3-v1"
PAIR_METRIC_SCHEMA = "experiment52-root-pair-estimand-fix3-v1"
ALLOWED_FAILURES = {
    "tactic_failure",
    "syntax_or_elaboration_failure",
    "timeout",
    "resource_failure",
    "worker_or_protocol_failure",
}
RESPONSE_CATEGORIES = {
    "both_success_same_strict_endpoint",
    "both_success_different_strict_endpoint",
    "left_success_only",
    "right_success_only",
    "both_fail_same_category",
    "both_fail_different_category",
    "invalid_reconstruction",
}


def _record_sha(value: Mapping[str, Any]) -> str:
    return json_sha256({
        key: item for key, item in value.items() if key != "record_sha256"
    })


def _assert_record(value: Mapping[str, Any], label: str) -> None:
    if value.get("record_sha256") != _record_sha(value):
        raise ValueError(f"record SHA changed: {label}")


def _resolve(root: Path, raw: str | Path) -> Path:
    path = Path(raw)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _strict_sha(row: Mapping[str, Any]) -> str | None:
    if row.get("probe_status") != "success":
        return None
    return str(row.get("next_endpoints", {}).get("struct", {}).get("sha256"))


def _content_reference_exact(value: Mapping[str, Any]) -> bool:
    try:
        path = Path(str(value["path"]))
        return bool(
            path.is_file()
            and file_sha256(path) == value["sha256"]
            and path.stat().st_size == int(value["bytes"])
        )
    except (KeyError, TypeError, ValueError, OSError):
        return False


def _compact_matches_payload(
    compact: Mapping[str, Any], payload: Mapping[str, Any]
) -> bool:
    for kind in ("raw", "text48", "struct"):
        observed = compact.get(kind, {})
        expected = payload[kind]
        value = dict(expected["value"])
        state = str(value.pop("state"))
        state_ref = observed.get("state", {})
        if not (
            observed.get("sha256") == expected["sha256"]
            and observed.get("metadata") == value
            and _content_reference_exact(state_ref)
            and hydrate_text(state_ref) == state
        ):
            return False
    return True


def _checkpoint_exact(row: Mapping[str, Any]) -> bool:
    """Validate the immutable pre-probe reconstruction checkpoint."""
    if row.get("valid_reconstruction") is not True:
        return True
    if row.get("failure_category") == "worker_or_protocol_failure":
        return False
    checkpoint = row.get("candidate_checkpoint")
    if not isinstance(checkpoint, dict):
        return False
    receipt = checkpoint.get("receipt")
    if not isinstance(receipt, dict):
        return False
    try:
        receipt_path = Path(str(checkpoint["receipt_path"]))
        if not (
            receipt_path.is_file()
            and file_sha256(receipt_path) == checkpoint["receipt_sha256"]
            and read_json(receipt_path) == receipt
            and receipt.get("record_sha256") == _record_sha(receipt)
            and receipt.get("cell_id") == row["cell_id"]
            and receipt.get("input_identity_sha256")
            == row["input_identity_sha256"]
            and receipt.get("source_exp51_row_sha256")
            == row["source_exp51_row_sha256"]
            and receipt.get("candidate_record_sha256")
            == row["candidate_record_sha256"]
            and receipt.get("lean_exact_match") is True
            and receipt.get("probe_invocation_next") is True
            and receipt.get("valid_reconstruction") is True
            and receipt.get("prestate_match")
            == {"raw": True, "text48": True, "struct": True}
            and receipt.get("candidate_post_match")
            == {"raw": True, "text48": True, "struct": True}
            and receipt.get("candidate_goal_count")
            == row["expected_candidate_endpoint"]["goal_count"]
            and receipt.get("initial_endpoints") == row.get("initial_endpoints")
            and receipt.get("candidate_endpoints")
            == row.get("candidate_observed_endpoints")
        ):
            return False
        raw_ref = receipt["raw_checkpoint_content"]
        if not (
            _content_reference_exact(raw_ref)
            and raw_ref["sha256"] == receipt["raw_checkpoint_sha256"]
            and int(raw_ref["bytes"]) == receipt["raw_checkpoint_bytes"]
        ):
            return False
        raw = json.loads(Path(raw_ref["path"]).read_text(encoding="utf-8"))
        if not (
            raw.get("schema")
            == "experiment52-candidate-checkpoint-raw-fix3-v1"
            and raw.get("reconstructionMatched") is True
            and raw.get("probeInvocationNext") is True
            and int(raw.get("preGoalCount", 0)) == 1
        ):
            return False
        initial_payload = base.endpoint_payload(
            str(raw["beforeText"]), str(raw["beforeStruct"]),
            int(raw["preGoalCount"]),
        )
        candidate_payload = base.endpoint_payload(
            str(raw["candidateText"]), str(raw["candidateStruct"]),
            int(raw["candidateGoalCount"]),
        )
        return bool(
            _compact_matches_payload(receipt["initial_endpoints"], initial_payload)
            and _compact_matches_payload(
                receipt["candidate_endpoints"], candidate_payload
            )
        )
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
        return False


def _side_state(row: Mapping[str, Any]) -> str:
    """Return success, failure, or invalid for response classification."""
    if not (
        row.get("record_complete") is True
        and row.get("probe_attempted") is True
        and row.get("valid_reconstruction") is True
    ):
        return "invalid"
    status = row.get("probe_status")
    if status == "success":
        return "success"
    if (
        status == "failure"
        and row.get("failure_category") in ALLOWED_FAILURES
        and row.get("failure_category") != "worker_or_protocol_failure"
    ):
        # A checkpointed timeout is retained as failure, but a process failure
        # without an exact reconstructed candidate endpoint is invalid.
        return "failure"
    return "invalid"


def response_category(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> str:
    left_state, right_state = _side_state(left), _side_state(right)
    if "invalid" in {left_state, right_state}:
        return "invalid_reconstruction"
    if left_state == right_state == "success":
        return (
            "both_success_same_strict_endpoint"
            if _strict_sha(left) == _strict_sha(right)
            else "both_success_different_strict_endpoint"
        )
    if left_state == "success":
        return "left_success_only"
    if right_state == "success":
        return "right_success_only"
    return (
        "both_fail_same_category"
        if left.get("failure_category") == right.get("failure_category")
        else "both_fail_different_category"
    )


def _response_row(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> dict[str, Any]:
    category = response_category(left, right)
    if category not in RESPONSE_CATEGORIES:
        raise AssertionError(category)
    informative = category in {
        "both_success_same_strict_endpoint",
        "both_success_different_strict_endpoint",
        "left_success_only",
        "right_success_only",
    }
    row = {
        "schema": RESPONSE_SCHEMA,
        "version": 1,
        "root_id": left["root_id"],
        "theorem_id": left["theorem_id"],
        "slug": left["slug"],
        "pair_role": left["pair_role"],
        "pair_id": left["pair_id"],
        "probe": left["probe"],
        "probe_index": left["probe_index"],
        "repeat_kind": left["repeat_kind"],
        "left_cell_id": left["cell_id"],
        "right_cell_id": right["cell_id"],
        "left_record_sha256": left["record_sha256"],
        "right_record_sha256": right["record_sha256"],
        "left_status": left.get("probe_status"),
        "right_status": right.get("probe_status"),
        "left_failure_category": left.get("failure_category"),
        "right_failure_category": right.get("failure_category"),
        "left_next_strict_sha256": _strict_sha(left),
        "right_next_strict_sha256": _strict_sha(right),
        "left_next_goal_count": left.get("next_goal_count"),
        "right_next_goal_count": right.get("next_goal_count"),
        "left_next_terminal": left.get("next_terminal"),
        "right_next_terminal": right.get("next_terminal"),
        "left_valid_reconstruction": left.get("valid_reconstruction") is True,
        "right_valid_reconstruction": right.get("valid_reconstruction") is True,
        "both_sides_probe_attempted": (
            left.get("probe_attempted") is True
            and right.get("probe_attempted") is True
        ),
        "category": category,
        "informative": informative,
        "concordant_success": (
            category == "both_success_same_strict_endpoint"
        ),
        "asymmetric_success": category in {
            "left_success_only", "right_success_only"
        },
        "informative_discordance": category in {
            "both_success_different_strict_endpoint",
            "left_success_only",
            "right_success_only",
        },
        "manual_reconciliation_count": 0,
    }
    row["record_sha256"] = _record_sha(row)
    return row


def join_responses(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], dict[str, Mapping[str, Any]]] = (
        defaultdict(dict)
    )
    for row in rows:
        key = (
            str(row["root_id"]), str(row["pair_role"]),
            str(row["probe"]), str(row["repeat_kind"]),
        )
        side = str(row["side"])
        if side not in {"left", "right"} or side in grouped[key]:
            raise ValueError(f"duplicate/invalid Exp52 side: {key}/{side}")
        grouped[key][side] = row
    out = []
    for key, sides in grouped.items():
        if set(sides) != {"left", "right"}:
            raise ValueError(f"Exp52 paired cell is incomplete: {key}")
        left, right = sides["left"], sides["right"]
        for field in (
            "root_id", "theorem_id", "slug", "pair_role", "pair_id",
            "probe", "probe_index", "repeat_kind", "amendment_sha256",
            "exp52_protocol_sha256", "selection_ledger_sha256",
        ):
            if left.get(field) != right.get(field):
                raise ValueError(f"Exp52 side identity mismatch: {key}/{field}")
        out.append(_response_row(left, right))
    return sorted(
        out,
        key=lambda row: (
            row["root_id"], 0 if row["repeat_kind"] == "primary" else 1,
            0 if row["pair_role"] == "witness" else 1,
            row["probe_index"], row["probe"],
        ),
    )


def _pair_metric(
    selection: Mapping[str, Any],
    role: str,
    responses: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    pair = selection[role]
    expected = list(selection["probe_panel"])
    ordered = sorted(responses, key=lambda row: row["probe_index"])
    if [row["probe"] for row in ordered] != expected:
        raise ValueError(
            f"executed probes differ from frozen selection: {selection['root_id']}/{role}"
        )
    informative = sum(row["informative"] for row in ordered)
    concordant = sum(row["concordant_success"] for row in ordered)
    asymmetric = sum(row["asymmetric_success"] for row in ordered)
    discordant = sum(row["informative_discordance"] for row in ordered)
    valid_reconstruction = all(
        row["left_valid_reconstruction"]
        and row["right_valid_reconstruction"] for row in ordered
    )
    attempted = all(row["both_sides_probe_attempted"] for row in ordered)
    value = {
        "schema": PAIR_METRIC_SCHEMA,
        "version": 1,
        "root_id": selection["root_id"],
        "theorem_id": selection["theorem_id"],
        "slug": selection["slug"],
        "pair_role": role,
        "pair_id": pair["pair_id"],
        "selection_record_sha256": selection["record_sha256"],
        "probes_expected": len(expected),
        "probes_observed": len(ordered),
        "all_probes_attempted_both_sides": attempted,
        "valid_reconstruction": valid_reconstruction,
        "informative_probe_count": informative,
        "concordant_success_count": concordant,
        "asymmetric_success_count": asymmetric,
        "informative_discordance_count": discordant,
        "C": concordant / informative if informative else None,
        "A": asymmetric / informative if informative else None,
        "B": discordant / informative if informative else None,
        "D": discordant > 0,
        "zero_information": informative == 0,
        "response_category_counts": dict(sorted(Counter(
            row["category"] for row in ordered
        ).items())),
        "manual_reconciliation_count": 0,
    }
    value["record_sha256"] = _record_sha(value)
    return value


def build_pair_metrics(
    selections: Sequence[Mapping[str, Any]],
    responses: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in responses:
        if row["repeat_kind"] == "primary":
            by_key[(row["root_id"], row["pair_role"])].append(row)
    out = []
    for selection in selections:
        out.append(_pair_metric(
            selection, "witness", by_key[(selection["root_id"], "witness")]
        ))
        if selection.get("control") is not None:
            out.append(_pair_metric(
                selection, "control", by_key[(selection["root_id"], "control")]
            ))
    return out


def _comparison_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("probe_status"), row.get("failure_category"),
        _strict_sha(row), row.get("next_goal_count"), row.get("next_terminal"),
    )


def determinism_comparisons(
    rows: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    primary, audit = {}, {}
    for row in rows:
        key = (
            row["root_id"], row["pair_role"], row["side"], row["probe"]
        )
        if row["repeat_kind"] == "primary" and row["pair_role"] == "witness":
            primary[key] = row
        elif row["repeat_kind"] == "determinism_audit":
            if row["pair_role"] != "witness":
                raise ValueError("determinism audit contains a control cell")
            audit[key] = row
    out = []
    for key, repeated in sorted(audit.items()):
        original = primary.get(key)
        if original is None:
            raise ValueError(f"audit repeat lacks primary cell: {key}")
        exact = _comparison_key(original) == _comparison_key(repeated)
        row = {
            "version": 1,
            "root_id": key[0], "pair_role": key[1],
            "side": key[2], "probe": key[3],
            "primary_cell_id": original["cell_id"],
            "audit_cell_id": repeated["cell_id"],
            "primary_outcome": list(_comparison_key(original)),
            "audit_outcome": list(_comparison_key(repeated)),
            "exact": exact,
        }
        row["record_sha256"] = _record_sha(row)
        out.append(row)
    return out


def _quantile(values: Sequence[float], probability: float) -> float | None:
    return base.quantile(list(values), probability) if values else None


def _hierarchical_bootstrap(
    rows: Sequence[Mapping[str, Any]],
    field: str,
    *,
    seed: int,
    replicates: int,
) -> list[float]:
    by_repo: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        value = row.get(field)
        if value is not None:
            by_repo[str(row["slug"])].append(row)
    slugs = sorted(by_repo)
    if not slugs:
        return []
    rng = random.Random(seed)
    output = []
    for _ in range(replicates):
        sampled_slugs = [rng.choice(slugs) for _ in slugs]
        repo_means = []
        for slug in sampled_slugs:
            source = by_repo[slug]
            sampled = [rng.choice(source) for _ in source]
            repo_means.append(mean(float(row[field]) for row in sampled))
        output.append(mean(repo_means))
    return output


def _paired_delta_rows(metrics: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_root: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in metrics:
        by_root[row["root_id"]][row["pair_role"]] = row
    out = []
    for root_id, roles in sorted(by_root.items()):
        witness, control = roles.get("witness"), roles.get("control")
        if not witness or not control:
            continue
        if not (
            witness["valid_reconstruction"] and control["valid_reconstruction"]
            and witness["C"] is not None and control["C"] is not None
        ):
            continue
        out.append({
            "root_id": root_id,
            "theorem_id": witness["theorem_id"],
            "slug": witness["slug"],
            "witness_pair_id": witness["pair_id"],
            "control_pair_id": control["pair_id"],
            "witness_C": witness["C"],
            "control_C": control["C"],
            "delta_C": witness["C"] - control["C"],
        })
    return out


def _valid_paired_control_rows(
    metrics: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_root: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in metrics:
        by_root[row["root_id"]][row["pair_role"]] = row
    output = []
    for root_id, roles in sorted(by_root.items()):
        witness, control = roles.get("witness"), roles.get("control")
        if not witness or not control:
            continue
        if witness["valid_reconstruction"] and control["valid_reconstruction"]:
            output.append({
                "root_id": root_id,
                "theorem_id": witness["theorem_id"],
                "slug": witness["slug"],
                "witness_pair_id": witness["pair_id"],
                "control_pair_id": control["pair_id"],
                "witness_informative": witness["C"] is not None,
                "control_informative": control["C"] is not None,
            })
    return output


def _repository_rows(
    witnesses: Sequence[Mapping[str, Any]],
    deltas: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    slugs = sorted({str(row["slug"]) for row in witnesses})
    out = []
    for slug in slugs:
        ws = [row for row in witnesses if row["slug"] == slug]
        valid = [row for row in ws if row["valid_reconstruction"]]
        informative = [row for row in valid if row["C"] is not None]
        ds = [row for row in deltas if row["slug"] == slug]
        out.append({
            "slug": slug,
            "selected_witnesses": len(ws),
            "valid_witnesses": len(valid),
            "valid_reconstruction_fraction": len(valid) / len(ws) if ws else 0.0,
            "nonzero_informative_witnesses": len(informative),
            "nonzero_informative_fraction": (
                len(informative) / len(valid) if valid else 0.0
            ),
            "C_mean": mean(row["C"] for row in informative) if informative else None,
            "A_mean": mean(row["A"] for row in informative) if informative else None,
            "B_mean": mean(row["B"] for row in informative) if informative else None,
            "D_mean": mean(int(row["D"]) for row in valid) if valid else None,
            "paired_control_roots": len(ds),
            "delta_C_mean": mean(row["delta_C"] for row in ds) if ds else None,
        })
    return out


def _macro(repository_rows: Sequence[Mapping[str, Any]], field: str) -> float | None:
    values = [float(row[field]) for row in repository_rows if row.get(field) is not None]
    return mean(values) if values else None


def _descriptive_subset(
    witness_rows: Sequence[Mapping[str, Any]],
    delta_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    repositories = _repository_rows(witness_rows, delta_rows)
    valid = [row for row in witness_rows if row["valid_reconstruction"]]
    informative = [row for row in valid if row["C"] is not None]
    delta_repositories = [
        row["delta_C_mean"] for row in repositories
        if row["delta_C_mean"] is not None
    ]
    return {
        "witness_roots": len(witness_rows),
        "valid_witness_roots": len(valid),
        "informative_witness_roots": len(informative),
        "repositories": len({row["slug"] for row in witness_rows}),
        "repository_macro_C": _macro(repositories, "C_mean"),
        "repository_macro_A": _macro(repositories, "A_mean"),
        "repository_macro_B": _macro(repositories, "B_mean"),
        "repository_macro_D": _macro(repositories, "D_mean"),
        "paired_control_roots": len(delta_rows),
        "paired_control_repositories": len(delta_repositories),
        "repository_macro_delta_C": _macro(repositories, "delta_C_mean"),
        "control_repositories_nonnegative_fraction": (
            sum(value >= 0 for value in delta_repositories)
            / len(delta_repositories) if delta_repositories else None
        ),
        "root_pooled_C_descriptive": (
            mean(float(row["C"]) for row in informative)
            if informative else None
        ),
    }


def _leave_one_repository_out(
    witness_rows: Sequence[Mapping[str, Any]],
    delta_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output = []
    for omitted in sorted({str(row["slug"]) for row in witness_rows}):
        retained_witnesses = [
            row for row in witness_rows if row["slug"] != omitted
        ]
        retained_deltas = [row for row in delta_rows if row["slug"] != omitted]
        output.append({
            "omitted_repository": omitted,
            **_descriptive_subset(retained_witnesses, retained_deltas),
        })
    return output


def _leave_one_mechanism_out(
    selections: Sequence[Mapping[str, Any]],
    witness_rows: Sequence[Mapping[str, Any]],
    delta_rows: Sequence[Mapping[str, Any]],
    field: str,
) -> list[dict[str, Any]]:
    roots_by_value: dict[str, set[str]] = defaultdict(set)
    for selection in selections:
        for side in ("left", "right"):
            roots_by_value[str(selection["witness"][side][field])].add(
                selection["root_id"]
            )
    output = []
    for value in sorted(roots_by_value):
        omitted_roots = roots_by_value[value]
        retained_witnesses = [
            row for row in witness_rows if row["root_id"] not in omitted_roots
        ]
        retained_deltas = [
            row for row in delta_rows if row["root_id"] not in omitted_roots
        ]
        output.append({
            "omitted_value": value,
            "omitted_root_count": len(omitted_roots),
            **_descriptive_subset(retained_witnesses, retained_deltas),
        })
    return output


def _write_exact_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    if path.is_file():
        if read_jsonl(path) != rows:
            raise ValueError(f"existing analysis ledger changed: {path}")
        return
    atomic_jsonl_dump(rows, path)


def _write_exact_json(value: Mapping[str, Any], path: Path) -> None:
    if path.is_file():
        if read_json(path) != value:
            raise ValueError(f"existing analysis JSON changed: {path}")
        return
    atomic_json_dump(value, path)


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    source = validate_amendment(root)
    _config, _targets, protocol, _amendment = load_source_bundle(root)
    selection_root = root / "exp52/selection"
    execution_root = root / "exp52/execution"
    analysis_root = root / "exp52/analysis"
    selection_summaryp = selection_root / "summary.json"
    witnessp = selection_root / "witnesses.jsonl"
    planp = selection_root / "execution_cells.jsonl"
    execution_summaryp = execution_root / "summary.json"
    cellsp = execution_root / "cells.jsonl"
    for path in (
        selection_summaryp, witnessp, planp, execution_summaryp, cellsp
    ):
        if not path.is_file():
            raise FileNotFoundError(path)
    selection_summary = read_json(selection_summaryp)
    selections = read_jsonl(witnessp)
    plan = read_jsonl(planp)
    execution_summary = read_json(execution_summaryp)
    rows = read_jsonl(cellsp)
    for selection in selections:
        _assert_record(selection, f"selection/{selection.get('root_id')}")
    for cell in plan:
        _assert_record(cell, f"plan/{cell.get('cell_id')}")
    for row in rows:
        _assert_record(row, f"execution/{row.get('cell_id')}")
    planned_ids = [row["cell_id"] for row in plan]
    observed_ids = [row["cell_id"] for row in rows]
    if len(set(planned_ids)) != len(planned_ids) or observed_ids != planned_ids:
        raise ValueError("Exp52 finalized cells differ from the frozen execution plan")
    if not (
        selection_summary.get("selection_complete") is True
        and selection_summary.get("amendment_sha256") == source["amendment_sha256"]
        and selection_summary.get("exp52_protocol_sha256") == source["protocol_sha256"]
        and selection_summary.get("witness_ledger_sha256") == file_sha256(witnessp)
        and selection_summary.get("execution_cell_plan_sha256") == file_sha256(planp)
        and execution_summary.get("execution_complete") is True
        and execution_summary.get("execution_gate") is True
        and execution_summary.get("amendment_sha256") == source["amendment_sha256"]
        and execution_summary.get("cells_expected") == len(plan)
        and execution_summary.get("cells_recorded") == len(rows)
        and execution_summary.get("cells_sha256") == file_sha256(cellsp)
        and execution_summary.get("manual_reconciliation_count") == 0
    ):
        raise ValueError("Exp52 selection/execution summary gate is not exact")

    responses = join_responses(rows)
    metrics = build_pair_metrics(selections, responses)
    comparisons = determinism_comparisons(rows)
    witness_metrics = [row for row in metrics if row["pair_role"] == "witness"]
    valid_witnesses = [row for row in witness_metrics if row["valid_reconstruction"]]
    informative_witnesses = [row for row in valid_witnesses if row["C"] is not None]
    deltas = _paired_delta_rows(metrics)
    valid_paired_controls = _valid_paired_control_rows(metrics)
    repositories = _repository_rows(witness_metrics, deltas)
    selection_by_root = {row["root_id"]: row for row in selections}
    exact_goal_root_ids = {
        row["root_id"] for row in selections
        if row.get("control") is not None
        and row["control"]["left_endpoint_features"][0]
        == row["witness"]["endpoint_features"][0]
        and row["control"]["right_endpoint_features"][0]
        == row["witness"]["endpoint_features"][0]
    }
    exact_goal_deltas = [
        row for row in deltas if row["root_id"] in exact_goal_root_ids
    ]
    exact_goal_witness_metrics = [
        row for row in witness_metrics if row["root_id"] in exact_goal_root_ids
    ]
    control_distance_rows = [{
        "root_id": row["root_id"],
        "theorem_id": row["theorem_id"],
        "slug": row["slug"],
        "witness_pair_id": row["witness"]["pair_id"],
        "control_pair_id": row["control"]["pair_id"],
        "distance": row["control"]["distance"],
        "witness_endpoint_features": row["witness"]["endpoint_features"],
        "control_left_endpoint_features": row["control"]["left_endpoint_features"],
        "control_right_endpoint_features": row["control"]["right_endpoint_features"],
        "exact_goal_count_control": row["root_id"] in exact_goal_root_ids,
    } for row in selections if row.get("control") is not None]
    source_endpoint_rows = [{
        "root_id": row["root_id"],
        "theorem_id": row["theorem_id"],
        "slug": row["slug"],
        "witness_pair_id": row["witness"]["pair_id"],
        "raw_equal": (
            row["witness"]["left"]["endpoint"]["raw_sha256"]
            == row["witness"]["right"]["endpoint"]["raw_sha256"]
        ),
        "text48_equal": (
            row["witness"]["left"]["endpoint"]["text48_sha256"]
            == row["witness"]["right"]["endpoint"]["text48_sha256"]
        ),
        "strict_equal": (
            row["witness"]["left"]["endpoint"]["strict_sha256"]
            == row["witness"]["right"]["endpoint"]["strict_sha256"]
        ),
    } for row in selections]
    leave_one_repository = _leave_one_repository_out(
        witness_metrics, deltas
    )
    leave_one_head = _leave_one_mechanism_out(
        selections, witness_metrics, deltas, "head"
    )
    leave_one_group = _leave_one_mechanism_out(
        selections, witness_metrics, deltas, "genealogy_group"
    )
    bootstrap_cfg = protocol["bootstrap"]
    replicates = int(bootstrap_cfg["replicates"])
    seed = int(bootstrap_cfg["seed"])
    c_boot = _hierarchical_bootstrap(
        informative_witnesses, "C", seed=seed, replicates=replicates
    )
    a_boot = _hierarchical_bootstrap(
        informative_witnesses, "A", seed=seed + 1, replicates=replicates
    )
    b_boot = _hierarchical_bootstrap(
        informative_witnesses, "B", seed=seed + 2, replicates=replicates
    )
    d_boot = _hierarchical_bootstrap(
        valid_witnesses, "D", seed=seed + 3, replicates=replicates
    )
    delta_boot = _hierarchical_bootstrap(
        deltas, "delta_C", seed=seed, replicates=replicates
    )
    exact_goal_delta_boot = _hierarchical_bootstrap(
        exact_goal_deltas, "delta_C", seed=seed, replicates=replicates
    )

    selected_by_repo = Counter(row["slug"] for row in witness_metrics)
    valid_by_repo = Counter(row["slug"] for row in valid_witnesses)
    overall_reconstruction = (
        len(valid_witnesses) / len(witness_metrics) if witness_metrics else 0.0
    )
    per_repo_reconstruction = {
        slug: valid_by_repo[slug] / count
        for slug, count in sorted(selected_by_repo.items())
    }
    valid_repos = {row["slug"] for row in valid_witnesses}
    control_repos = {row["slug"] for row in valid_paired_controls}
    overall_information = (
        len(informative_witnesses) / len(valid_witnesses)
        if valid_witnesses else 0.0
    )
    per_repo_information = {
        row["slug"]: row["nonzero_informative_fraction"] for row in repositories
    }
    failures = [
        {
            "cell_id": row["cell_id"], "root_id": row["root_id"],
            "slug": row["slug"], "pair_role": row["pair_role"],
            "side": row["side"], "probe": row["probe"],
            "repeat_kind": row["repeat_kind"],
            "valid_reconstruction": row.get("valid_reconstruction") is True,
            "probe_status": row.get("probe_status"),
            "failure_category": row.get("failure_category"),
            "record_sha256": row["record_sha256"],
        }
        for row in rows if row.get("probe_status") != "success"
    ]
    timeout_count = sum(
        row.get("failure_category") == "timeout" for row in rows
    )
    fresh_process_rows = sum(
        row.get("process", {}).get("fresh_lean_process") is True
        for row in rows
    )
    attempt_ordinals_one = all(
        row.get("process", {}).get("attempt_ordinal") == 1 for row in rows
    )
    valid_checkpoint_rows = sum(
        row.get("valid_reconstruction") is True and _checkpoint_exact(row)
        for row in rows
    )
    valid_rows_total = sum(
        row.get("valid_reconstruction") is True for row in rows
    )
    integrity = {
        "all_cells_used_fresh_lean_processes": (
            execution_summary.get("all_fresh_lean_processes") is True
            and fresh_process_rows == len(rows)
        ),
        "all_worker_process_launch_receipts_exact": (
            execution_summary.get("all_worker_process_launch_receipts_exact")
            is True
        ),
        "all_attempt_ordinals_one_and_no_retry": (
            execution_summary.get("all_attempt_ordinals_one") is True
            and execution_summary.get("scientific_retry_count") == 0
            and attempt_ordinals_one
        ),
        "all_valid_rows_have_exact_candidate_checkpoint": (
            valid_checkpoint_rows == valid_rows_total
        ),
        "overall_reconstruction_at_least_0_95": overall_reconstruction >= 0.95,
        "per_repository_reconstruction_at_least_0_90": bool(repositories) and all(
            value >= 0.90 for value in per_repo_reconstruction.values()
        ),
        "all_retained_probes_attempted_both_sides": all(
            row["all_probes_attempted_both_sides"] for row in metrics
            if row["valid_reconstruction"]
        ),
        "zero_manual_reconciliation": (
            execution_summary.get("manual_reconciliation_count") == 0
            and all(row.get("manual_reconciliation_count") == 0 for row in rows)
        ),
        "all_invalid_and_timeout_rows_retained": (
            len(failures) == sum(row.get("probe_status") != "success" for row in rows)
            and timeout_count == sum(
                row["failure_category"] == "timeout" for row in failures
            )
        ),
        "zero_determinism_audit_mismatches": all(
            row["exact"] for row in comparisons
        ),
    }
    gates = protocol["gates"]
    information = {
        "minimum_200_valid_witness_roots": (
            len(valid_witnesses) >= gates["minimum_valid_witness_roots"]
        ),
        "minimum_12_witness_repositories": (
            len(valid_repos) >= gates["minimum_witness_repositories"]
        ),
        "minimum_100_within_root_control_pairs": (
            len(valid_paired_controls)
            >= gates["minimum_within_root_control_pairs"]
        ),
        "minimum_8_control_repositories": (
            len(control_repos) >= gates["minimum_control_repositories"]
        ),
        "overall_nonzero_information_at_least_0_80": (
            overall_information
            >= gates["overall_nonzero_informative_denominator_fraction_at_least"]
        ),
        "per_repository_nonzero_information_at_least_0_50": bool(repositories) and all(
            value
            >= gates["per_repository_nonzero_informative_denominator_fraction_at_least"]
            for value in per_repo_information.values()
        ),
    }
    b_upper = _quantile(b_boot, 0.95)
    delta_interval = (
        [_quantile(delta_boot, 0.025), _quantile(delta_boot, 0.975)]
        if delta_boot else None
    )
    delta_repo_values = [
        row["delta_C_mean"] for row in repositories
        if row["delta_C_mean"] is not None
    ]
    nonnegative_fraction = (
        sum(value >= 0 for value in delta_repo_values) / len(delta_repo_values)
        if delta_repo_values else None
    )
    support = {
        "witness_B_one_sided_95_upper_lt_0_05": (
            b_upper is not None
            and b_upper
            < gates["total_informative_discordance_B_one_sided_95_upper_lt"]
        ),
        "delta_C_95_lower_gt_0": (
            delta_interval is not None
            and delta_interval[0] is not None
            and delta_interval[0] > gates["delta_C_95_lower_gt"]
        ),
        "control_repository_nonnegative_fraction_at_least_0_75": (
            nonnegative_fraction is not None
            and nonnegative_fraction
            >= gates["control_repositories_nonnegative_delta_fraction_at_least"]
        ),
    }
    precision_evaluable = bool(b_boot and delta_boot and delta_repo_values)
    if not all(integrity.values()):
        decision = "invalid_execution"
    elif not all(information.values()) or not precision_evaluable:
        decision = "continuation_inconclusive"
    elif all(support.values()):
        decision = "continuation_support"
    else:
        decision = "continuation_no_go"

    paired_response_path = analysis_root / "response_cells.jsonl"
    metrics_path = analysis_root / "pair_metrics.jsonl"
    delta_path = analysis_root / "paired_control_deltas.jsonl"
    valid_control_path = analysis_root / "valid_paired_controls.jsonl"
    repository_path = analysis_root / "repositories.jsonl"
    audit_path = analysis_root / "determinism_comparisons.jsonl"
    failure_path = analysis_root / "failure_ledger.jsonl"
    zero_path = analysis_root / "zero_information_pairs.jsonl"
    leave_repo_path = analysis_root / "leave_one_repository_out.jsonl"
    leave_head_path = analysis_root / "leave_one_head_out.jsonl"
    leave_group_path = analysis_root / "leave_one_genealogy_group_out.jsonl"
    exact_goal_path = analysis_root / "exact_goal_count_control_deltas.jsonl"
    control_distance_path = analysis_root / "control_distance_ledger.jsonl"
    source_endpoint_path = analysis_root / "source_endpoint_equality.jsonl"
    for values, path in (
        (responses, paired_response_path), (metrics, metrics_path),
        (deltas, delta_path), (valid_paired_controls, valid_control_path),
        (repositories, repository_path),
        (comparisons, audit_path), (failures, failure_path),
        ([row for row in metrics if row["zero_information"]], zero_path),
        (leave_one_repository, leave_repo_path),
        (leave_one_head, leave_head_path),
        (leave_one_group, leave_group_path),
        (exact_goal_deltas, exact_goal_path),
        (control_distance_rows, control_distance_path),
        (source_endpoint_rows, source_endpoint_path),
    ):
        _write_exact_jsonl(values, path)

    category_counts = dict(sorted(Counter(
        row["category"] for row in responses if row["repeat_kind"] == "primary"
    ).items()))
    summary = {
        "version": 1,
        "schema": ANALYSIS_SCHEMA,
        "protocol_version": protocol["protocol_version"],
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "mechanical_fix_id": EXECUTION_FIX_ID,
        "amendment_sha256": source["amendment_sha256"],
        "exp52_protocol_sha256": source["protocol_sha256"],
        "selection_summary_sha256": file_sha256(selection_summaryp),
        "execution_summary_sha256": file_sha256(execution_summaryp),
        "execution_cells_sha256": file_sha256(cellsp),
        "selected_witness_roots": len(witness_metrics),
        "selected_witness_repositories": len(selected_by_repo),
        "valid_witness_roots": len(valid_witnesses),
        "valid_witness_repositories": len(valid_repos),
        "valid_within_root_control_pairs": len(valid_paired_controls),
        "valid_control_repositories": len(control_repos),
        "informative_paired_control_deltas": len(deltas),
        "overall_valid_reconstruction_fraction": overall_reconstruction,
        "per_repository_valid_reconstruction_fraction": per_repo_reconstruction,
        "overall_nonzero_informative_denominator_fraction": overall_information,
        "per_repository_nonzero_informative_denominator_fraction": per_repo_information,
        "response_category_counts": category_counts,
        "witness": {
            "repository_macro_C": _macro(repositories, "C_mean"),
            "repository_macro_A": _macro(repositories, "A_mean"),
            "repository_macro_B": _macro(repositories, "B_mean"),
            "repository_macro_D": _macro(repositories, "D_mean"),
            "C_bootstrap_95ci": [
                _quantile(c_boot, 0.025), _quantile(c_boot, 0.975)
            ] if c_boot else None,
            "A_bootstrap_95ci": [
                _quantile(a_boot, 0.025), _quantile(a_boot, 0.975)
            ] if a_boot else None,
            "A_one_sided_95_upper": _quantile(a_boot, 0.95),
            "B_bootstrap_95ci": [
                _quantile(b_boot, 0.025), _quantile(b_boot, 0.975)
            ] if b_boot else None,
            "B_one_sided_95_upper": b_upper,
            "D_bootstrap_95ci": [
                _quantile(d_boot, 0.025), _quantile(d_boot, 0.975)
            ] if d_boot else None,
        },
        "paired_control": {
            "repository_macro_delta_C": _macro(repositories, "delta_C_mean"),
            "delta_C_bootstrap_95ci": delta_interval,
            "repositories_nonnegative_delta_fraction": nonnegative_fraction,
        },
        "root_pooled_descriptive": {
            "C": (
                mean(float(row["C"]) for row in informative_witnesses)
                if informative_witnesses else None
            ),
            "A": (
                mean(float(row["A"]) for row in informative_witnesses)
                if informative_witnesses else None
            ),
            "B": (
                mean(float(row["B"]) for row in informative_witnesses)
                if informative_witnesses else None
            ),
            "D": (
                mean(float(row["D"]) for row in valid_witnesses)
                if valid_witnesses else None
            ),
            "not_primary": True,
        },
        "informative_denominator_distribution": {
            "counts": dict(sorted(Counter(
                str(row["informative_probe_count"])
                for row in witness_metrics
            ).items(), key=lambda item: int(item[0]))),
            "minimum": min(
                (row["informative_probe_count"] for row in witness_metrics),
                default=None,
            ),
            "median": _quantile(
                [float(row["informative_probe_count"]) for row in witness_metrics],
                0.5,
            ),
            "maximum": max(
                (row["informative_probe_count"] for row in witness_metrics),
                default=None,
            ),
        },
        "exact_goal_count_control_sensitivity": {
            "eligible_selected_controls": len(exact_goal_root_ids),
            "valid_informative_paired_roots": len(exact_goal_deltas),
            "repositories": len({row["slug"] for row in exact_goal_deltas}),
            "repository_macro_delta_C": _descriptive_subset(
                exact_goal_witness_metrics, exact_goal_deltas
            )["repository_macro_delta_C"],
            "delta_C_bootstrap_95ci": [
                _quantile(exact_goal_delta_boot, 0.025),
                _quantile(exact_goal_delta_boot, 0.975),
            ] if exact_goal_delta_boot else None,
            "secondary_not_decision_changing": True,
        },
        "bootstrap": {
            "levels": ["repository", "root"],
            "replicates": replicates,
            "seed": seed,
            "interval": "percentile_95",
        },
        "integrity_checks": integrity,
        "information_checks": information,
        "support_checks": support,
        "precision_evaluable": precision_evaluable,
        "determinism_audit_cells": len(comparisons),
        "determinism_audit_mismatch_count": sum(
            not row["exact"] for row in comparisons
        ),
        "timeout_cells": timeout_count,
        "fresh_lean_process_cells": fresh_process_rows,
        "valid_candidate_checkpoint_cells": valid_checkpoint_rows,
        "manual_reconciliation_count": 0,
        "decision_label": decision,
        "response_cells_sha256": file_sha256(paired_response_path),
        "pair_metrics_sha256": file_sha256(metrics_path),
        "paired_control_deltas_sha256": file_sha256(delta_path),
        "valid_paired_controls_sha256": file_sha256(valid_control_path),
        "repositories_sha256": file_sha256(repository_path),
        "determinism_comparisons_sha256": file_sha256(audit_path),
        "failure_ledger_sha256": file_sha256(failure_path),
        "zero_information_pairs_sha256": file_sha256(zero_path),
        "leave_one_repository_out_sha256": file_sha256(leave_repo_path),
        "leave_one_head_out_sha256": file_sha256(leave_head_path),
        "leave_one_genealogy_group_out_sha256": file_sha256(leave_group_path),
        "exact_goal_count_control_deltas_sha256": file_sha256(exact_goal_path),
        "control_distance_ledger_sha256": file_sha256(control_distance_path),
        "source_endpoint_equality_sha256": file_sha256(source_endpoint_path),
        "claim_boundary": protocol["claim_boundary"],
        "next_step": "Run independent Exp52 row-level reconstruction audit.",
    }
    summary["identity_sha256"] = identity_sha256(summary)
    _write_exact_json(summary, analysis_root / "summary.json")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(SCIENTIFIC_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    analyze(parse_args())
