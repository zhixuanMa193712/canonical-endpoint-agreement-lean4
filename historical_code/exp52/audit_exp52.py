"""Independent offline reconstruction audit for Exp52.

The audit deliberately does not import ``select_exp52_pairs`` or
``analyze_exp52``.  It regenerates witness/control choices from Exp51 rows,
reconstructs response categories and pair estimands from Exp52 side receipts,
and independently repeats the frozen bootstrap and decision logic.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Mapping, Sequence

from alignment_protocol import *  # noqa: F401,F403


AUDIT_SCHEMA = "experiment52-independent-row-reconstruction-audit-fix4-v1"
FAILURE_CATEGORIES = {
    "tactic_failure", "syntax_or_elaboration_failure", "timeout",
    "resource_failure", "worker_or_protocol_failure",
}


def _without_sha(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "record_sha256"}


def _valid_sha(value: Mapping[str, Any]) -> bool:
    return value.get("record_sha256") == json_sha256(_without_sha(value))


def _endpoint_hash(branch: Mapping[str, Any]) -> str:
    return str(branch["endpoints"]["struct"]["sha256"])


def _complete_endpoint_payload(branch: Mapping[str, Any]) -> dict[str, Any]:
    endpoints = branch.get("endpoints", branch)
    entry = endpoints["struct"]
    state = entry["state"]
    return {
        "endpoint_sha256": str(entry["sha256"]),
        "state": {
            "sha256": str(state["sha256"]),
            "bytes": int(state["bytes"]),
            "text": hydrate_text(state),
        },
        "metadata": dict(entry["metadata"]),
    }


def _strict_collision(
    branches: Sequence[Mapping[str, Any]], initial: Mapping[str, Any]
) -> bool:
    grouped: dict[str, set[str]] = defaultdict(set)
    for endpoint in [initial, *[
        branch for branch in branches if branch.get("executable") is True
    ]]:
        endpoints = endpoint.get("endpoints", endpoint)
        digest = str(endpoints["struct"]["sha256"])
        grouped[digest].add(json.dumps(
            _complete_endpoint_payload(endpoint), ensure_ascii=False,
            sort_keys=True, separators=(",", ":"),
        ))
    return any(len(payloads) != 1 for payloads in grouped.values())


def _identity(branch: Mapping[str, Any]) -> dict[str, Any]:
    tactic = str(branch["tactic"])
    genealogy = base.genealogy_for(tactic)
    return {
        "tactic": tactic,
        "head": str(branch["head"]),
        "family": str(branch["family"]),
        "candidate_index": int(branch["candidate_position_frozen"]),
        "genealogy_class": genealogy["class"],
        "genealogy_group": genealogy["group"],
        "candidate_record_sha256": str(branch["record_sha256"]),
        "endpoint": {
            "raw_sha256": branch["endpoints"]["raw"]["sha256"],
            "text48_sha256": branch["endpoints"]["text48"]["sha256"],
            "strict_sha256": branch["endpoints"]["struct"]["sha256"],
            "goal_count": int(branch["goal_count"]),
            "terminal": branch.get("terminal") is True,
        },
    }


def _pair_id(left: Mapping[str, Any], right: Mapping[str, Any],
             role: str, root_id: str) -> str:
    left, right = ordered_pair(left, right)
    value = {
        "role": role, "root_id": root_id,
        "left": _identity(left), "right": _identity(right),
        "internal_pair_key": [
            [{"utf8_hex": item.hex()} if isinstance(item, bytes) else item
             for item in candidate_key(left)],
            [{"utf8_hex": item.hex()} if isinstance(item, bytes) else item
             for item in candidate_key(right)],
        ],
    }
    return json_sha256(value)


def _mechanism_distinct(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return bool(
        left["head"] != right["head"]
        and base.genealogy_for(left["tactic"])["group"]
        != base.genealogy_for(right["tactic"])["group"]
    )


def _robust_candidates(
    row: Mapping[str, Any], target: Mapping[str, Any]
) -> list[dict[str, Any]]:
    robust = list(target["robust_alternatives"])
    selected = [dict(branch) for branch in row["candidates"]
                if branch["tactic"] in set(robust)]
    if [branch["tactic"] for branch in selected] != robust:
        raise ValueError("robust candidate order changed during audit")
    return selected


def _robust_branches(
    row: Mapping[str, Any], target: Mapping[str, Any]
) -> list[dict[str, Any]]:
    selected = _robust_candidates(row, target)
    initial = row["initial_endpoints"]["struct"]["sha256"]
    return [branch for branch in selected
            if branch.get("executable") is True
            and branch["endpoints"]["struct"]["sha256"] != initial
            and branch.get("terminal") is False
            and int(branch.get("goal_count", 0)) > 0
            and branch.get("record_sha256") == json_sha256(_without_sha(branch))]


def _select_pair_ids(row: Mapping[str, Any], target: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    root_id = str(target["theorem_id"])
    branches = _robust_branches(row, target)
    witnesses = []
    for left, right in itertools.combinations(branches, 2):
        if _mechanism_distinct(left, right) and _endpoint_hash(left) == _endpoint_hash(right):
            left, right = ordered_pair(left, right)
            witnesses.append((
                _endpoint_hash(left).encode("utf-8"), candidate_key(left),
                candidate_key(right), left, right,
            ))
    witnesses.sort(key=lambda item: item[:3])
    witness_ids = [_pair_id(item[3], item[4], "witness", root_id)
                   for item in witnesses]
    if not witnesses:
        return witness_ids, []
    witness = witnesses[0]
    witness_feature = strict_endpoint_features(witness[3])
    controls = []
    for left, right in itertools.combinations(branches, 2):
        if not _mechanism_distinct(left, right) or _endpoint_hash(left) == _endpoint_hash(right):
            continue
        left, right = ordered_pair(left, right)
        lf, rf = strict_endpoint_features(left), strict_endpoint_features(right)
        distance = (
            abs(lf[0] - witness_feature[0]) + abs(rf[0] - witness_feature[0]),
            abs(lf[1] - witness_feature[1]) + abs(rf[1] - witness_feature[1]),
            abs(lf[2] - witness_feature[2]) + abs(rf[2] - witness_feature[2]),
        )
        endpoints = tuple(sorted((_endpoint_hash(left), _endpoint_hash(right))))
        controls.append((*distance,
                         tuple(value.encode("utf-8") for value in endpoints),
                         candidate_key(left), candidate_key(right), left, right))
    controls.sort(key=lambda item: item[:6])
    return witness_ids, [
        _pair_id(item[6], item[7], "control", root_id) for item in controls
    ]


def _regenerate_root(
    row: Mapping[str, Any], target: Mapping[str, Any], config_sha256: str
) -> dict[str, Any]:
    if not (
        _valid_sha(row)
        and row.get("protocol_version") == base.PROTOCOL_VERSION
        and row.get("mode") == "scientific"
        and row.get("config_sha256") == config_sha256
        and row.get("theorem_id") == target["theorem_id"]
        and row.get("slug") == target["slug"]
        and row.get("source_file_sha256") == target["source_file_sha256"]
        and row.get("candidate_order") == target["alternatives"]
    ):
        raise ValueError(f"source Exp51 row identity changed: {target['theorem_id']}")
    if row.get("worker_ok") is not True:
        return {
            "status": "exp51_unevaluable", "witness_ids": [],
            "control_ids": [],
        }
    candidates = list(row.get("candidates", []))
    candidate_identity_exact = True
    for branch in candidates:
        tactic = str(branch.get("tactic", ""))
        try:
            index = list(target["alternatives"]).index(tactic)
        except ValueError:
            candidate_identity_exact = False
            continue
        candidate_identity_exact &= bool(
            branch.get("source") == "candidate"
            and branch.get("attempted") is True
            and branch.get("candidate_position_frozen") == index
            and branch.get("execution_order_index") == index
            and branch.get("head") == base.tactic_head(tactic)
            and branch.get("family") == base.tactic_family(tactic)
        )
    if not (
        len(candidates) == CANDIDATES_PER_ROOT
        and row.get("complete_candidate_order") is True
        and row.get("same_pre_state_all_branches") is True
        and row.get("authored_replay_ok") is True
        and all(_valid_sha(branch) for branch in candidates)
        and candidate_identity_exact
    ):
        raise ValueError(f"source Exp51 candidate rows changed: {target['theorem_id']}")
    robust = _robust_candidates(row, target)
    if _strict_collision(robust, row["initial_endpoints"]):
        return {
            "status": "invalid_strict_hash_collision", "witness_ids": [],
            "control_ids": [],
        }
    witness_ids, control_ids = _select_pair_ids(row, target)
    return {
        "status": "witness_selected" if witness_ids else "no_eligible_witness",
        "witness_ids": witness_ids,
        "control_ids": control_ids,
    }


def _audit_ids(selections: Sequence[Mapping[str, Any]]) -> set[str]:
    by_repo: dict[str, list[str]] = defaultdict(list)
    for row in selections:
        by_repo[row["slug"]].append(row["root_id"])
    output = set()
    for root_ids in by_repo.values():
        ordered = sorted(root_ids, key=lambda value: (
            hashlib.sha256(value.encode("utf-8")).digest(), value
        ))
        output.update(ordered[:determinism_audit_count(len(ordered))])
    return output


def _strict_next(row: Mapping[str, Any]) -> str | None:
    return (str(row.get("next_endpoints", {}).get("struct", {}).get("sha256"))
            if row.get("probe_status") == "success" else None)


def _content_reference_exact(value: Mapping[str, Any]) -> bool:
    try:
        path = Path(str(value["path"]))
        return bool(
            path.is_file() and file_sha256(path) == value["sha256"]
            and path.stat().st_size == int(value["bytes"])
        )
    except (KeyError, TypeError, ValueError, OSError):
        return False


def _compact_payload_exact(
    compact: Mapping[str, Any], payload: Mapping[str, Any]
) -> bool:
    for kind in ("raw", "text48", "struct"):
        observed, expected = compact.get(kind, {}), payload[kind]
        value = dict(expected["value"])
        state = str(value.pop("state"))
        reference = observed.get("state", {})
        if not (
            observed.get("sha256") == expected["sha256"]
            and observed.get("metadata") == value
            and _content_reference_exact(reference)
            and hydrate_text(reference) == state
        ):
            return False
    return True


def _checkpoint_exact(row: Mapping[str, Any]) -> bool:
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
        exact_matches = {"raw": True, "text48": True, "struct": True}
        if not (
            receipt_path.is_file()
            and file_sha256(receipt_path) == checkpoint["receipt_sha256"]
            and read_json(receipt_path) == receipt
            and _valid_sha(receipt)
            and receipt.get("schema") == CHECKPOINT_COMPACT_SCHEMA
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
            and receipt.get("prestate_match") == exact_matches
            and receipt.get("candidate_post_match") == exact_matches
            and receipt.get("candidate_goal_count")
            == row["expected_candidate_endpoint"]["goal_count"]
            and receipt.get("initial_endpoints") == row.get("initial_endpoints")
            and receipt.get("candidate_endpoints")
            == row.get("candidate_observed_endpoints")
        ):
            return False
        raw_reference = receipt["raw_checkpoint_content"]
        if not (
            _content_reference_exact(raw_reference)
            and raw_reference["sha256"] == receipt["raw_checkpoint_sha256"]
            and int(raw_reference["bytes"]) == receipt["raw_checkpoint_bytes"]
        ):
            return False
        raw = json.loads(
            Path(raw_reference["path"]).read_text(encoding="utf-8")
        )
        if not (
            raw.get("schema")
            == CHECKPOINT_RAW_SCHEMA
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
            _compact_payload_exact(receipt["initial_endpoints"], initial_payload)
            and _compact_payload_exact(
                receipt["candidate_endpoints"], candidate_payload
            )
        )
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
        return False


def _status(row: Mapping[str, Any]) -> str:
    if not (
        row.get("record_complete") is True
        and row.get("probe_attempted") is True
        and row.get("valid_reconstruction") is True
    ):
        return "invalid"
    if row.get("probe_status") == "success":
        return "success"
    if (
        row.get("probe_status") == "failure"
        and row.get("failure_category") in FAILURE_CATEGORIES
        and row.get("failure_category") != "worker_or_protocol_failure"
    ):
        return "failure"
    return "invalid"


def _category(left: Mapping[str, Any], right: Mapping[str, Any]) -> str:
    ls, rs = _status(left), _status(right)
    if "invalid" in {ls, rs}:
        return "invalid_reconstruction"
    if ls == rs == "success":
        return ("both_success_same_strict_endpoint"
                if _strict_next(left) == _strict_next(right)
                else "both_success_different_strict_endpoint")
    if ls == "success":
        return "left_success_only"
    if rs == "success":
        return "right_success_only"
    return ("both_fail_same_category"
            if left.get("failure_category") == right.get("failure_category")
            else "both_fail_different_category")


def _pair_metrics(rows: Sequence[Mapping[str, Any]], selections: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    sides: dict[tuple[str, str, str], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in rows:
        if row["repeat_kind"] == "primary":
            sides[(row["root_id"], row["pair_role"], row["probe"])][row["side"]] = row
    selection_by_root = {row["root_id"]: row for row in selections}
    output = []
    for root_id, selection in selection_by_root.items():
        roles = ["witness"] + (["control"] if selection.get("control") else [])
        for role in roles:
            categories = []
            valid = True
            attempted = True
            for probe in selection["probe_panel"]:
                pair = sides[(root_id, role, probe)]
                if set(pair) != {"left", "right"}:
                    raise ValueError("audit found incomplete paired response")
                valid &= (pair["left"].get("valid_reconstruction") is True
                          and pair["right"].get("valid_reconstruction") is True)
                attempted &= (pair["left"].get("probe_attempted") is True
                              and pair["right"].get("probe_attempted") is True)
                categories.append(_category(pair["left"], pair["right"]))
            informative = [value for value in categories if value in {
                "both_success_same_strict_endpoint", "both_success_different_strict_endpoint",
                "left_success_only", "right_success_only",
            }]
            denominator = len(informative)
            concordant = informative.count("both_success_same_strict_endpoint")
            asymmetric = sum(value in {"left_success_only", "right_success_only"}
                             for value in informative)
            discordant = sum(value in {
                "both_success_different_strict_endpoint", "left_success_only",
                "right_success_only",
            } for value in informative)
            output.append({
                "root_id": root_id, "theorem_id": selection["theorem_id"],
                "slug": selection["slug"], "pair_role": role,
                "pair_id": selection[role]["pair_id"],
                "valid_reconstruction": valid,
                "all_probes_attempted_both_sides": attempted,
                "informative_probe_count": denominator,
                "C": concordant / denominator if denominator else None,
                "A": asymmetric / denominator if denominator else None,
                "B": discordant / denominator if denominator else None,
                "D": discordant > 0,
                "categories": categories,
            })
    return output


def _bootstrap(rows: Sequence[Mapping[str, Any]], field: str,
               seed: int, replicates: int) -> list[float]:
    by_repo: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get(field) is not None:
            by_repo[row["slug"]].append(row)
    slugs = sorted(by_repo)
    if not slugs:
        return []
    rng, output = random.Random(seed), []
    for _ in range(replicates):
        repo_values = []
        for slug in [rng.choice(slugs) for _ in slugs]:
            source = by_repo[slug]
            sample = [rng.choice(source) for _ in source]
            repo_values.append(mean(float(row[field]) for row in sample))
        output.append(mean(repo_values))
    return output


def _q(values: Sequence[float], p: float) -> float | None:
    return base.quantile(list(values), p) if values else None


def audit(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    source = validate_amendment(root)
    config, targets, protocol, _amendment = load_source_bundle(root)
    selection_root, execution_root = root / "exp52/selection", root / "exp52/execution"
    analysis_root, audit_root = root / "exp52/analysis", root / "exp52/audit"
    paths = {
        "selection": selection_root / "summary.json",
        "roots": selection_root / "roots.jsonl",
        "pairs": selection_root / "eligible_pairs.jsonl",
        "witnesses": selection_root / "witnesses.jsonl",
        "audit_subset": selection_root / "audit_subset.jsonl",
        "plan": selection_root / "execution_cells.jsonl",
        "source_rows": selection_root / "source_exp51_rows.jsonl",
        "exp51_summary": root / "scientific/summary.json",
        "exp51_index": root / "scientific/row_index.jsonl",
        "execution": execution_root / "summary.json",
        "cells": execution_root / "cells.jsonl",
        "execution_index": execution_root / "row_index.jsonl",
        "analysis": analysis_root / "summary.json",
    }
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    root_ledger = read_jsonl(paths["roots"])
    pair_ledger = read_jsonl(paths["pairs"])
    selections = read_jsonl(paths["witnesses"])
    audit_subset = read_jsonl(paths["audit_subset"])
    plan = read_jsonl(paths["plan"])
    source_row_ledger = read_jsonl(paths["source_rows"])
    exp51_summary = read_json(paths["exp51_summary"])
    exp51_index = read_jsonl(paths["exp51_index"])
    cells = read_jsonl(paths["cells"])
    execution_index = read_jsonl(paths["execution_index"])
    reported = read_json(paths["analysis"])
    selection_summary = read_json(paths["selection"])
    execution_summary = read_json(paths["execution"])

    sha_rows_exact = all(_valid_sha(row) for rows in (
        root_ledger, pair_ledger, selections, audit_subset, plan, cells
    ) for row in rows)
    root_by_id = {row["root_id"]: row for row in root_ledger}
    selection_by_root = {row["root_id"]: row for row in selections}
    unique_ledgers = (
        len(root_by_id) == len(root_ledger)
        and len(selection_by_root) == len(selections)
    )
    regenerated_exact = unique_ledgers
    probe_filters_exact = True
    expected_selected_roots: set[str] = set()
    expected_pair_rows: list[tuple[str, str, int, str, bool]] = []
    source_rows_exact = bool(
        len(source_row_ledger) == len(exp51_index) == len(targets)
        and exp51_summary.get("execution_complete") is True
        and exp51_summary.get("execution_gate") is True
        and exp51_summary.get("roots_expected") == TARGET_ROOTS
        and exp51_summary.get("root_receipts") == TARGET_ROOTS
        and exp51_summary.get("roots_attempted") == TARGET_ROOTS
        and exp51_summary.get("config_sha256") == source["config_sha256"]
        and exp51_summary.get("targets_sha256") == source["targets_sha256"]
        and exp51_summary.get("amendment_sha256")
        == source["source_fix3_amendment_sha256"]
        and exp51_summary.get("row_index_sha256")
        == file_sha256(paths["exp51_index"])
        and Path(exp51_summary.get("row_index", "")).resolve()
        == paths["exp51_index"].resolve()
        and exp51_summary.get("scientific_retry_count") == 0
        and exp51_summary.get("manual_reconciliation_count") == 0
    )
    exp51_evaluable_reconstructed = 0
    exp51_candidate_attempts_reconstructed = 0
    for frozen_index, target in enumerate(targets):
        root_id = str(target["theorem_id"])
        rowp = exp51_row_path(root, target).resolve()
        root_row = root_by_id.get(root_id)
        if not rowp.is_file() or root_row is None:
            source_rows_exact = False
            regenerated_exact = False
            continue
        source_hash = file_sha256(rowp)
        source_entry = (
            source_row_ledger[frozen_index]
            if frozen_index < len(source_row_ledger) else {}
        )
        index_entry = (
            exp51_index[frozen_index]
            if frozen_index < len(exp51_index) else {}
        )
        shard = frozen_index % EXP51_SHARD_COUNT
        receiptp = (
            root / "scientific/shards" / f"shard-{shard:02d}"
            / "receipts" / safe_slug(str(target["slug"]))
            / f"{target['rid']}.json"
        ).resolve()
        receipt = read_json(receiptp) if receiptp.is_file() else {}
        worker = read_json(rowp)
        exp51_evaluable_reconstructed += int(worker.get("worker_ok") is True)
        exp51_candidate_attempts_reconstructed += len(
            worker.get("candidates", [])
        )
        regenerated = _regenerate_root(
            worker, target, source["config_sha256"]
        )
        witness_ids = regenerated["witness_ids"]
        control_ids = regenerated["control_ids"]
        status = regenerated["status"]
        source_rows_exact &= bool(
            root_row.get("frozen_target_index") == frozen_index
            and root_row.get("theorem_id") == target["theorem_id"]
            and root_row.get("rid") == target["rid"]
            and root_row.get("slug") == target["slug"]
            and Path(root_row.get("source_exp51_row", "")).resolve() == rowp
            and root_row.get("source_exp51_row_sha256") == source_hash
            and root_row.get("worker_ok") is (worker.get("worker_ok") is True)
            and source_entry.get("frozen_target_index") == frozen_index
            and source_entry.get("theorem_id") == target["theorem_id"]
            and Path(source_entry.get("path", "")).resolve() == rowp
            and source_entry.get("sha256") == source_hash
            and source_entry.get("bytes") == rowp.stat().st_size
            and index_entry.get("frozen_target_index") == frozen_index
            and index_entry.get("shard_index") == shard
            and index_entry.get("slug") == target["slug"]
            and index_entry.get("rid") == target["rid"]
            and index_entry.get("theorem_id") == target["theorem_id"]
            and Path(index_entry.get("row", "")).resolve() == rowp
            and index_entry.get("row_sha256") == source_hash
            and Path(index_entry.get("receipt", "")).resolve() == receiptp
            and index_entry.get("receipt_sha256")
            == (file_sha256(receiptp) if receiptp.is_file() else None)
            and index_entry.get("worker_ok")
            is (worker.get("worker_ok") is True)
            and index_entry.get("candidate_attempts")
            == len(worker.get("candidates", []))
            and receipt.get("amendment_sha256")
            == source["source_fix3_amendment_sha256"]
            and receipt.get("phase") == "scientific"
            and receipt.get("frozen_target_index") == frozen_index
            and receipt.get("theorem_id") == target["theorem_id"]
            and receipt.get("target_identity_sha256")
            == target["target_identity_sha256"]
            and Path(receipt.get("worker_row", "")).resolve() == rowp
            and receipt.get("worker_row_sha256") == source_hash
            and receipt.get("worker_ok")
            is (worker.get("worker_ok") is True)
            and receipt.get("candidate_attempts")
            == len(worker.get("candidates", []))
            and receipt.get("manual_reconciliation_count") == 0
        )
        regenerated_exact &= bool(
            root_row.get("selection_status") == status
            and root_row.get("eligible_witness_pairs") == len(witness_ids)
            and root_row.get("eligible_control_pairs") == len(control_ids)
        )
        for role, ids in (("witness", witness_ids), ("control", control_ids)):
            expected_pair_rows.extend(
                (root_id, role, index, pair_id, index == 0)
                for index, pair_id in enumerate(ids)
            )
        selection = selection_by_root.get(root_id)
        if status != "witness_selected":
            regenerated_exact &= selection is None
            continue
        expected_selected_roots.add(root_id)
        if selection is None:
            regenerated_exact = False
            continue
        selected_witness = witness_ids[0]
        selected_control = control_ids[0] if control_ids else None
        regenerated_exact &= bool(
            selection.get("frozen_target_index") == frozen_index
            and selection.get("source_exp51_row_sha256") == source_hash
            and selection["witness"]["pair_id"] == selected_witness
            and (
                selection["control"]["pair_id"]
                if selection.get("control") else None
            ) == selected_control
            and selection["eligible_witness_pair_count"] == len(witness_ids)
            and selection["eligible_control_pair_count"] == len(control_ids)
            and root_row.get("selected_witness_pair_id") == selected_witness
            and root_row.get("selected_control_pair_id") == selected_control
        )
        excluded = {
            selection["witness"][side]["tactic"]
            for side in ("left", "right")
        }
        if selection.get("control"):
            excluded.update(
                selection["control"][side]["tactic"]
                for side in ("left", "right")
            )
        expected_probes = [
            probe for probe in protocol["probe_surface"]["retained_panel"]
            if probe not in excluded
        ]
        probe_filters_exact &= bool(
            selection["probe_panel"] == expected_probes
            and selection["probe_panel_sha256"] == json_sha256(expected_probes)
            and root_row.get("probe_count") == len(expected_probes)
        )
    actual_pair_rows = [
        (
            row["root_id"], row["role"], row["selection_ordinal"],
            row["pair"]["pair_id"], row["selected"],
        ) for row in pair_ledger
    ]
    regenerated_exact &= bool(
        set(selection_by_root) == expected_selected_roots
        and actual_pair_rows == expected_pair_rows
    )
    source_rows_exact &= bool(
        exp51_summary.get("evaluable_roots")
        == exp51_evaluable_reconstructed
        and exp51_summary.get("unevaluable_roots")
        == TARGET_ROOTS - exp51_evaluable_reconstructed
        and exp51_summary.get("candidate_attempts_recorded")
        == exp51_candidate_attempts_reconstructed
        and exp51_summary.get(
            "candidate_attempts_expected_on_evaluable_roots"
        ) == exp51_evaluable_reconstructed * CANDIDATES_PER_ROOT
    )

    expected_audit = _audit_ids(selections)
    expected_audit_order = [
        row["root_id"] for row in selections if row["root_id"] in expected_audit
    ]
    audit_subset_exact = (
        [row["root_id"] for row in audit_subset] == expected_audit_order
        and {row["root_id"] for row in selections if row["determinism_audit_selected"]}
        == expected_audit
        and all(
            row.get("selection_key_sha256")
            == hashlib.sha256(row["root_id"].encode("utf-8")).hexdigest()
            and row.get("selection_record_sha256")
            == selection_by_root[row["root_id"]]["record_sha256"]
            for row in audit_subset
        )
    )
    expected_plan: list[dict[str, Any]] = []
    for selection in selections:
        primary_roles = ["witness"] + (
            ["control"] if selection.get("control") is not None else []
        )
        scheduling = [
            (role, side, probe, probe_index, "primary")
            for role in primary_roles
            for side in ("left", "right")
            for probe_index, probe in enumerate(selection["probe_panel"])
        ]
        if selection["root_id"] in expected_audit:
            scheduling.extend(
                ("witness", side, probe, probe_index, "determinism_audit")
                for side in ("left", "right")
                for probe_index, probe in enumerate(selection["probe_panel"])
            )
        for role, side, probe, probe_index, repeat_kind in scheduling:
            pair = selection[role]
            identity = {
                "root_id": selection["root_id"], "pair_role": role,
                "pair_id": pair["pair_id"], "side": side,
                "probe": probe, "probe_index": probe_index,
                "repeat_kind": repeat_kind,
            }
            expected = {
                "schema": "experiment52-frozen-execution-cell-plan-fix3-v1",
                "version": 1,
                "protocol_version": selection["protocol_version"],
                "amendment_sha256": source[
                    "source_fix3_amendment_sha256"
                ],
                "selection_record_sha256": selection["record_sha256"],
                "cell_id": json_sha256(identity),
                **identity,
                "theorem_id": selection["theorem_id"],
                "rid": selection["rid"], "slug": selection["slug"],
                "source_exp51_row": selection["source_exp51_row"],
                "source_exp51_row_sha256": selection["source_exp51_row_sha256"],
                "candidate": pair[side],
                "expected_pair_endpoint_relation": (
                    "same_strict_endpoint" if role == "witness"
                    else "different_strict_endpoints"
                ),
                "probe_panel_sha256": selection["probe_panel_sha256"],
                "fresh_process_required": True,
                "scientific_retry_permitted": False,
                "manual_reconciliation_count": 0,
            }
            expected["record_sha256"] = json_sha256(expected)
            expected_plan.append(expected)
    plan_ids_exact = bool(
        len(plan) == len(cells) == len(expected_plan)
        and [row["cell_id"] for row in plan]
        == [row["cell_id"] for row in cells]
    )
    plan_sha256 = file_sha256(paths["plan"])
    if len(plan) == len(cells) == len(expected_plan):
        for index, (item, observed, expected) in enumerate(
            zip(plan, cells, expected_plan)
        ):
            plan_ids_exact &= item == expected
            plan_ids_exact &= bool(
                observed.get("cell_index") == index
                and all(
                    observed.get(key) == item.get(key) for key in (
                        "cell_id", "root_id", "theorem_id", "rid", "slug",
                        "pair_id", "pair_role", "side", "probe",
                        "probe_index", "repeat_kind",
                    )
                )
                and observed.get("amendment_sha256")
                == source["amendment_sha256"]
                and observed.get("exp52_protocol_sha256")
                == source["protocol_sha256"]
                and observed.get("selection_ledger_sha256") == plan_sha256
                and observed.get("selection_record_sha256")
                == item["selection_record_sha256"]
                and observed.get("cell_plan_record_sha256")
                == item["record_sha256"]
                and observed.get("source_exp51_row")
                == item["source_exp51_row"]
                and observed.get("source_exp51_row_sha256")
                == item["source_exp51_row_sha256"]
                and observed.get("candidate_tactic")
                == item["candidate"]["tactic"]
                and observed.get("candidate_head")
                == item["candidate"]["head"]
                and observed.get("candidate_position_frozen")
                == item["candidate"]["candidate_index"]
                and observed.get("candidate_record_sha256")
                == item["candidate"]["candidate_record_sha256"]
                and observed.get("expected_candidate_endpoint")
                == item["candidate"]["endpoint"]
                and observed.get("record_complete") is True
                and observed.get("scientific_retry_permitted") is False
                and observed.get("manual_reconciliation_count") == 0
            )

    # Rebind the combined execution rows to every immutable shard input,
    # worker row, root receipt, and (when present) worker-launch receipt.  A
    # missing launch receipt is permitted only as the already-recorded
    # no-retry orchestration-failure case; it makes the scientific integrity
    # gates fail but must remain independently auditable.
    execution_receipts_exact = len(execution_index) == len(plan) == len(cells)
    for index, (item, observed) in enumerate(zip(plan, cells)):
        entry = execution_index[index] if index < len(execution_index) else {}
        shard = shard_index(index, EXP52_SHARD_COUNT)
        shard_root = (
            root / "exp52/execution/shards" / f"shard-{shard:02d}"
        ).resolve()
        rowp = (shard_root / "rows" / f"{item['cell_id']}.json").resolve()
        receiptp = (
            shard_root / "receipts" / f"{item['cell_id']}.json"
        ).resolve()
        inputp = (
            shard_root / "inputs" / f"{item['cell_id']}.json"
        ).resolve()
        if not (rowp.is_file() and receiptp.is_file() and inputp.is_file()):
            execution_receipts_exact = False
            continue
        shard_row = read_json(rowp)
        receipt = read_json(receiptp)
        cell_input = read_json(inputp)
        input_identity = json_sha256({
            key: value for key, value in cell_input.items()
            if key != "input_identity_sha256"
        })
        execution_receipts_exact &= bool(
            shard_row == observed
            and entry.get("cell_index") == index
            and entry.get("cell_id") == item["cell_id"]
            and entry.get("shard_index") == shard
            and Path(entry.get("row", "")).resolve() == rowp
            and entry.get("row_sha256") == file_sha256(rowp)
            and Path(entry.get("receipt", "")).resolve() == receiptp
            and entry.get("receipt_sha256") == file_sha256(receiptp)
            and Path(entry.get("input", "")).resolve() == inputp
            and entry.get("input_sha256") == file_sha256(inputp)
            and cell_input.get("cell_id") == item["cell_id"]
            and cell_input.get("cell_index") == index
            and cell_input.get("amendment_sha256")
            == source["amendment_sha256"]
            and cell_input.get("exp52_protocol_sha256")
            == source["protocol_sha256"]
            and cell_input.get("selection_ledger_sha256") == plan_sha256
            and cell_input.get("selection_record_sha256")
            == item["selection_record_sha256"]
            and cell_input.get("cell_plan_record_sha256")
            == item["record_sha256"]
            and cell_input.get("source_exp51_row")
            == item["source_exp51_row"]
            and cell_input.get("source_exp51_row_sha256")
            == item["source_exp51_row_sha256"]
            and cell_input.get("candidate_tactic")
            == item["candidate"]["tactic"]
            and cell_input.get("candidate_head")
            == item["candidate"]["head"]
            and cell_input.get("candidate_position_frozen")
            == item["candidate"]["candidate_index"]
            and cell_input.get("candidate_record_sha256")
            == item["candidate"]["candidate_record_sha256"]
            and cell_input.get("expected_candidate_endpoint")
            == item["candidate"]["endpoint"]
            and cell_input.get("fresh_process_required") is True
            and cell_input.get("attempts_permitted") == 1
            and cell_input.get("scientific_retry_permitted") is False
            and cell_input.get("manual_reconciliation_count") == 0
            and cell_input.get("input_identity_sha256") == input_identity
            and observed.get("input_identity_sha256") == input_identity
            and receipt.get("cell_index") == index
            and receipt.get("cell_id") == item["cell_id"]
            and receipt.get("amendment_sha256")
            == source["amendment_sha256"]
            and receipt.get("selection_ledger_sha256") == plan_sha256
            and Path(receipt.get("worker_row", "")).resolve() == rowp
            and receipt.get("worker_row_sha256") == file_sha256(rowp)
            and receipt.get("record_complete") is True
            and receipt.get("attempt_ordinal") == 1
            and receipt.get("fresh_lean_process")
            is (observed.get("process", {}).get("fresh_lean_process") is True)
            and receipt.get("scientific_retry_count") == 0
            and receipt.get("manual_reconciliation_count") == 0
            and _valid_sha(receipt)
        )
        launch_raw = receipt.get("worker_process_receipt")
        entry_launch_raw = entry.get("worker_process_receipt")
        if launch_raw is None or entry_launch_raw is None:
            execution_receipts_exact &= bool(
                launch_raw is None
                and entry_launch_raw is None
                and receipt.get("worker_process_receipt_sha256") is None
                and entry.get("worker_process_receipt_sha256") is None
                and receipt.get("worker_process_receipt_exact") is False
            )
            continue
        launchp = Path(str(launch_raw)).resolve()
        execution_receipts_exact &= bool(
            launchp == Path(str(entry_launch_raw)).resolve()
            and launchp.is_file()
            and launchp.is_relative_to(
                (shard_root / "worker_processes").resolve()
            )
            and receipt.get("worker_process_receipt_sha256")
            == file_sha256(launchp)
            and entry.get("worker_process_receipt_sha256")
            == file_sha256(launchp)
            and receipt.get("worker_process_receipt_exact") is True
        )
        if not launchp.is_file():
            continue
        launch = read_json(launchp)
        command = launch.get("command")
        expected_tail = [
            str(PACKAGE_ROOT / "experiment52_live_worker.py"),
            "--input", str(inputp), "--output", str(rowp),
            "--runtime-root", str(shard_root / "runtime"),
            "--timeout", str(LEAN_TIMEOUT_SECONDS),
        ]
        execution_receipts_exact &= bool(
            launch.get("schema")
            == PROCESS_LAUNCH_SCHEMA
            and launch.get("alignment_version")
            == EXECUTION_ALIGNMENT_VERSION
            and launch.get("mechanical_fix_id") == EXECUTION_FIX_ID
            and launch.get("amendment_sha256")
            == source["amendment_sha256"]
            and launch.get("selection_ledger_sha256") == plan_sha256
            and launch.get("cell_id") == item["cell_id"]
            and launch.get("cell_index") == index
            and Path(launch.get("input", "")).resolve() == inputp
            and launch.get("input_sha256") == file_sha256(inputp)
            and launch.get("input_identity_sha256") == input_identity
            and Path(launch.get("output", "")).resolve() == rowp
            and type(launch.get("worker_pid")) is int
            and int(launch["worker_pid"]) > 0
            and launch.get("fresh_session_requested") is True
            and launch.get("fresh_session_observed")
            is (
                launch.get("worker_process_group_id")
                == launch.get("worker_pid")
            )
            and launch.get("attempt_ordinal") == 1
            and launch.get("scientific_retry_permitted") is False
            and isinstance(command, list)
            and len(command) == len(expected_tail) + 1
            and command[1:] == expected_tail
            and launch.get("command_sha256") == json_sha256(command)
            and _valid_sha(launch)
        )

    metrics = _pair_metrics(cells, selections)
    witness_metrics = [row for row in metrics if row["pair_role"] == "witness"]
    valid = [row for row in witness_metrics if row["valid_reconstruction"]]
    informative = [row for row in valid if row["C"] is not None]
    by_root = defaultdict(dict)
    for row in metrics:
        by_root[row["root_id"]][row["pair_role"]] = row
    valid_paired_controls = []
    deltas = []
    for roles in by_root.values():
        witness, control = roles.get("witness"), roles.get("control")
        if (witness and control and witness["valid_reconstruction"]
                and control["valid_reconstruction"]):
            valid_paired_controls.append({
                "root_id": witness["root_id"], "slug": witness["slug"],
            })
        if (witness and control and witness["valid_reconstruction"]
                and control["valid_reconstruction"] and witness["C"] is not None
                and control["C"] is not None):
            deltas.append({
                "root_id": witness["root_id"], "slug": witness["slug"],
                "delta_C": witness["C"] - control["C"],
            })
    replicates, seed = protocol["bootstrap"]["replicates"], protocol["bootstrap"]["seed"]
    c_boot = _bootstrap(informative, "C", seed, replicates)
    a_boot = _bootstrap(informative, "A", seed + 1, replicates)
    b_boot = _bootstrap(informative, "B", seed + 2, replicates)
    d_boot = _bootstrap(valid, "D", seed + 3, replicates)
    delta_boot = _bootstrap(deltas, "delta_C", seed, replicates)
    selected_counts, valid_counts = Counter(row["slug"] for row in witness_metrics), Counter(row["slug"] for row in valid)
    valid_repos = set(valid_counts)
    control_repos = {row["slug"] for row in valid_paired_controls}
    delta_repos = {row["slug"] for row in deltas}
    informative_counts = Counter(row["slug"] for row in informative)
    overall_reconstruction = len(valid) / len(witness_metrics) if witness_metrics else 0.0
    overall_info = len(informative) / len(valid) if valid else 0.0
    per_reconstruction = {slug: valid_counts[slug] / count for slug, count in sorted(selected_counts.items())}
    per_info = {slug: informative_counts[slug] / valid_counts[slug] if valid_counts[slug] else 0.0
                for slug in sorted(selected_counts)}
    audit_primary, audit_repeat = {}, {}
    for row in cells:
        key = (row["root_id"], row["pair_role"], row["side"], row["probe"])
        if row["pair_role"] == "witness" and row["repeat_kind"] == "primary":
            audit_primary[key] = row
        elif row["repeat_kind"] == "determinism_audit":
            audit_repeat[key] = row
    mismatches = 0
    for key, repeat in audit_repeat.items():
        primary = audit_primary.get(key)
        fields = ("probe_status", "failure_category", "next_goal_count", "next_terminal")
        if primary is None or tuple(primary.get(field) for field in fields) + (_strict_next(primary),) != tuple(repeat.get(field) for field in fields) + (_strict_next(repeat),):
            mismatches += 1
    all_attempted = all(row["all_probes_attempted_both_sides"] for row in metrics if row["valid_reconstruction"])
    fresh_process_rows = sum(
        row.get("process", {}).get("fresh_lean_process") is True
        for row in cells
    )
    attempts_one = all(
        row.get("process", {}).get("attempt_ordinal") == 1 for row in cells
    )
    valid_rows_total = sum(
        row.get("valid_reconstruction") is True for row in cells
    )
    valid_checkpoint_rows = sum(
        row.get("valid_reconstruction") is True and _checkpoint_exact(row)
        for row in cells
    )
    failures = [row for row in cells if row.get("probe_status") != "success"]
    timeout_count = sum(
        row.get("failure_category") == "timeout" for row in cells
    )
    integrity = {
        "all_cells_used_fresh_lean_processes": (
            execution_summary.get("all_fresh_lean_processes") is True
            and fresh_process_rows == len(cells)
        ),
        "all_worker_process_launch_receipts_exact": (
            execution_summary.get("all_worker_process_launch_receipts_exact")
            is True
        ),
        "all_attempt_ordinals_one_and_no_retry": (
            execution_summary.get("all_attempt_ordinals_one") is True
            and execution_summary.get("scientific_retry_count") == 0
            and attempts_one
        ),
        "all_valid_rows_have_exact_candidate_checkpoint": (
            valid_checkpoint_rows == valid_rows_total
        ),
        "overall_reconstruction_at_least_0_95": overall_reconstruction >= 0.95,
        "per_repository_reconstruction_at_least_0_90": bool(selected_counts) and all(value >= 0.90 for value in per_reconstruction.values()),
        "all_retained_probes_attempted_both_sides": all_attempted,
        "zero_manual_reconciliation": (
            execution_summary.get("manual_reconciliation_count") == 0
            and all(row.get("manual_reconciliation_count") == 0 for row in cells)
        ),
        "all_invalid_and_timeout_rows_retained": (
            len(failures)
            == sum(row.get("probe_status") != "success" for row in cells)
            and timeout_count
            == sum(row.get("failure_category") == "timeout" for row in failures)
        ),
        "zero_determinism_audit_mismatches": mismatches == 0,
    }
    gates = protocol["gates"]
    information = {
        "minimum_200_valid_witness_roots": len(valid) >= gates["minimum_valid_witness_roots"],
        "minimum_12_witness_repositories": len(valid_repos) >= gates["minimum_witness_repositories"],
        "minimum_100_within_root_control_pairs": (
            len(valid_paired_controls)
            >= gates["minimum_within_root_control_pairs"]
        ),
        "minimum_8_control_repositories": len(control_repos) >= gates["minimum_control_repositories"],
        "overall_nonzero_information_at_least_0_80": overall_info >= gates["overall_nonzero_informative_denominator_fraction_at_least"],
        "per_repository_nonzero_information_at_least_0_50": bool(selected_counts) and all(value >= gates["per_repository_nonzero_informative_denominator_fraction_at_least"] for value in per_info.values()),
    }
    delta_repo = []
    for slug in sorted(delta_repos):
        values = [row["delta_C"] for row in deltas if row["slug"] == slug]
        delta_repo.append(mean(values))
    b_upper = _q(b_boot, 0.95)
    delta_ci = [_q(delta_boot, 0.025), _q(delta_boot, 0.975)] if delta_boot else None
    breadth = sum(value >= 0 for value in delta_repo) / len(delta_repo) if delta_repo else None
    support = {
        "witness_B_one_sided_95_upper_lt_0_05": b_upper is not None and b_upper < gates["total_informative_discordance_B_one_sided_95_upper_lt"],
        "delta_C_95_lower_gt_0": delta_ci is not None and delta_ci[0] > gates["delta_C_95_lower_gt"],
        "control_repository_nonnegative_fraction_at_least_0_75": breadth is not None and breadth >= gates["control_repositories_nonnegative_delta_fraction_at_least"],
    }
    precision = bool(b_boot and delta_boot and delta_repo)
    decision = ("invalid_execution" if not all(integrity.values()) else
                "continuation_inconclusive" if not all(information.values()) or not precision else
                "continuation_support" if all(support.values()) else "continuation_no_go")

    def repository_macro(
        values: Sequence[Mapping[str, Any]], field: str
    ) -> float | None:
        grouped: dict[str, list[float]] = defaultdict(list)
        for row in values:
            if row.get(field) is not None:
                grouped[row["slug"]].append(float(row[field]))
        repository_means = [mean(grouped[slug]) for slug in sorted(grouped)]
        return mean(repository_means) if repository_means else None

    response_counts = dict(sorted(Counter(
        category for metric in metrics for category in metric["categories"]
    ).items()))

    checks = {
        "all_row_hashes_exact": sha_rows_exact,
        "all_576_roots_accounted": (
            len(targets) == TARGET_ROOTS
            and len(root_ledger) == TARGET_ROOTS
            and set(root_by_id) == {str(row["theorem_id"]) for row in targets}
        ),
        "all_source_exp51_row_hashes_exact": source_rows_exact,
        "selection_summary_ledgers_exact": (
            selection_summary.get("alignment_version")
            == SOURCE_FIX3_ALIGNMENT_VERSION
            and selection_summary.get("mechanical_fix_id") == SOURCE_FIX3_FIX_ID
            and selection_summary.get("amendment_sha256")
            == source["source_fix3_amendment_sha256"]
            and selection_summary.get("roots_accounted") == TARGET_ROOTS
            and selection_summary.get("source_exp51_rows") == TARGET_ROOTS
            and selection_summary.get("selected_witness_roots")
            == len(selections)
            and selection_summary.get("roots_ledger_sha256")
            == file_sha256(paths["roots"])
            and selection_summary.get("eligible_pairs_ledger_sha256")
            == file_sha256(paths["pairs"])
            and selection_summary.get("witness_ledger_sha256")
            == file_sha256(paths["witnesses"])
            and selection_summary.get("source_exp51_row_ledger_sha256")
            == file_sha256(paths["source_rows"])
            and selection_summary.get(
                "source_exp51_scientific_summary_sha256"
            ) == file_sha256(paths["exp51_summary"])
            and selection_summary.get("source_exp51_row_index_sha256")
            == file_sha256(paths["exp51_index"])
            and selection_summary.get("source_exp51_row_receipts")
            == TARGET_ROOTS
        ),
        "execution_accounting_summary_exact": (
            execution_summary.get("execution_complete") is True
            and execution_summary.get("execution_gate") is True
            and execution_summary.get("cells_expected") == len(plan)
            and execution_summary.get("cells_recorded") == len(cells)
            and execution_summary.get("cells_sha256") == file_sha256(paths["cells"])
            and execution_summary.get("row_index_sha256")
            == file_sha256(paths["execution_index"])
            and len(execution_index) == len(cells)
            and execution_summary.get("amendment_sha256")
            == source["amendment_sha256"]
        ),
        "witness_control_selection_regenerated_exact": regenerated_exact,
        "exact_text_probe_filters_regenerated_exact": probe_filters_exact,
        "determinism_audit_subset_regenerated_exact": audit_subset_exact,
        "execution_cell_plan_and_rows_exact": plan_ids_exact,
        "execution_row_inputs_receipts_and_launches_exact": (
            execution_receipts_exact
        ),
        "selected_witness_counts_exact": reported.get("selected_witness_roots") == len(witness_metrics),
        "valid_witness_counts_exact": reported.get("valid_witness_roots") == len(valid),
        "repository_counts_exact": (
            reported.get("selected_witness_repositories")
            == len(selected_counts)
            and reported.get("valid_witness_repositories") == len(valid_repos)
            and reported.get("valid_control_repositories") == len(control_repos)
        ),
        "control_counts_exact": (
            reported.get("valid_within_root_control_pairs")
            == len(valid_paired_controls)
            and reported.get("informative_paired_control_deltas") == len(deltas)
        ),
        "primary_response_category_counts_exact": (
            reported.get("response_category_counts") == response_counts
        ),
        "reconstruction_fractions_exact": reported.get("overall_valid_reconstruction_fraction") == overall_reconstruction and reported.get("per_repository_valid_reconstruction_fraction") == per_reconstruction,
        "information_fractions_exact": reported.get("overall_nonzero_informative_denominator_fraction") == overall_info and reported.get("per_repository_nonzero_informative_denominator_fraction") == per_info,
        "repository_macro_estimands_exact": (
            reported.get("witness", {}).get("repository_macro_C")
            == repository_macro(informative, "C")
            and reported.get("witness", {}).get("repository_macro_A")
            == repository_macro(informative, "A")
            and reported.get("witness", {}).get("repository_macro_B")
            == repository_macro(informative, "B")
            and reported.get("witness", {}).get("repository_macro_D")
            == repository_macro(valid, "D")
            and reported.get("paired_control", {}).get("repository_macro_delta_C")
            == repository_macro(deltas, "delta_C")
            and reported.get("paired_control", {}).get(
                "repositories_nonnegative_delta_fraction"
            ) == breadth
        ),
        "C_bootstrap_exact": reported.get("witness", {}).get("C_bootstrap_95ci") == ([_q(c_boot, 0.025), _q(c_boot, 0.975)] if c_boot else None),
        "A_bootstrap_exact": reported.get("witness", {}).get("A_bootstrap_95ci") == ([_q(a_boot, 0.025), _q(a_boot, 0.975)] if a_boot else None) and reported.get("witness", {}).get("A_one_sided_95_upper") == _q(a_boot, 0.95),
        "B_bootstrap_and_upper_exact": reported.get("witness", {}).get("B_bootstrap_95ci") == ([_q(b_boot, 0.025), _q(b_boot, 0.975)] if b_boot else None) and reported.get("witness", {}).get("B_one_sided_95_upper") == b_upper,
        "D_bootstrap_exact": reported.get("witness", {}).get("D_bootstrap_95ci") == ([_q(d_boot, 0.025), _q(d_boot, 0.975)] if d_boot else None),
        "delta_bootstrap_exact": reported.get("paired_control", {}).get("delta_C_bootstrap_95ci") == delta_ci,
        "integrity_checks_exact": reported.get("integrity_checks") == integrity,
        "information_checks_exact": reported.get("information_checks") == information,
        "support_checks_exact": reported.get("support_checks") == support,
        "determinism_and_resource_counts_exact": (
            reported.get("determinism_audit_cells") == len(audit_repeat)
            and reported.get("determinism_audit_mismatch_count") == mismatches
            and reported.get("timeout_cells") == timeout_count
            and reported.get("fresh_lean_process_cells") == fresh_process_rows
            and reported.get("valid_candidate_checkpoint_cells")
            == valid_checkpoint_rows
        ),
        "decision_label_exact": reported.get("decision_label") == decision,
        "manual_reconciliation_zero": reported.get("manual_reconciliation_count") == 0,
    }
    value = {
        "version": 1, "schema": AUDIT_SCHEMA,
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "mechanical_fix_id": EXECUTION_FIX_ID,
        "amendment_sha256": source["amendment_sha256"],
        "selection_summary_sha256": file_sha256(paths["selection"]),
        "execution_summary_sha256": file_sha256(paths["execution"]),
        "analysis_sha256": file_sha256(paths["analysis"]),
        "roots_reconstructed": len(root_ledger),
        "witnesses_reconstructed": len(witness_metrics),
        "controls_reconstructed": len(valid_paired_controls),
        "informative_control_deltas_reconstructed": len(deltas),
        "cells_reconstructed": len(cells),
        "bootstrap_replicates_reconstructed": replicates,
        "manual_reconciliation_count": 0,
        "checks": checks,
        "audit_pass": all(checks.values()),
        "decision_label_preserved": decision,
        "claim_boundary": "audit validates Exp52 only and adds no scientific result",
        "next_step": "Export the immutable Exp52 bundle." if all(checks.values()) else "STOP; inspect immutable mismatch evidence.",
    }
    value["identity_sha256"] = identity_sha256(value)
    outp = audit_root / "summary.json"
    if outp.is_file() and read_json(outp) != value:
        raise ValueError("existing Exp52 audit differs from reconstruction")
    atomic_json_dump(value, outp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(SCIENTIFIC_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    result = audit(parse_args())
    raise SystemExit(0 if result.get("audit_pass") is True else 2)
