"""Mechanically select frozen Exp52 witnesses, controls, and probe cells.

This is an offline transformation of the completed Exp51 Fix3 scientific rows.
It never invokes Lean.  The ordering and exclusions implement Sections 5--8
of ``EXP52_PREREGISTRATION.md`` and materialize a complete immutable execution
plan for the separate Exp52 live worker.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from alignment_protocol import *  # noqa: F401,F403


SELECTION_SCHEMA = "experiment52-frozen-pair-selection-fix3-v1"
ROOT_LEDGER_SCHEMA = "experiment52-root-selection-accounting-fix3-v1"
PAIR_LEDGER_SCHEMA = "experiment52-complete-eligible-pair-ledger-fix3-v1"
CELL_PLAN_SCHEMA = "experiment52-frozen-execution-cell-plan-fix3-v1"


def _record_sha(value: Mapping[str, Any]) -> str:
    return json_sha256({
        key: item for key, item in value.items() if key != "record_sha256"
    })


def _assert_record_sha(value: Mapping[str, Any], label: str) -> None:
    if value.get("record_sha256") != _record_sha(value):
        raise ValueError(f"record SHA changed: {label}")


def _json_key(value: Any) -> Any:
    """Convert byte-valued ordering keys into a portable JSON representation."""
    if isinstance(value, bytes):
        return {"utf8_hex": value.hex()}
    if isinstance(value, tuple):
        return [_json_key(item) for item in value]
    if isinstance(value, list):
        return [_json_key(item) for item in value]
    return value


def _endpoint_hash(branch: Mapping[str, Any], kind: str = "struct") -> str:
    endpoints = branch.get("endpoints", branch)
    return str(endpoints[kind]["sha256"])


def _endpoint_state_value(
    branch: Mapping[str, Any], kind: str = "struct"
) -> str:
    endpoints = branch.get("endpoints", branch)
    return hydrate_text(endpoints[kind]["state"])


def _complete_endpoint_payload(
    branch: Mapping[str, Any], kind: str = "struct"
) -> dict[str, Any]:
    """Hydrate the complete compact payload used to detect hash collisions."""
    endpoints = branch.get("endpoints", branch)
    entry = endpoints[kind]
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


def _endpoint_identity(branch: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "raw_sha256": _endpoint_hash(branch, "raw"),
        "text48_sha256": _endpoint_hash(branch, "text48"),
        "strict_sha256": _endpoint_hash(branch, "struct"),
        "goal_count": int(branch["goal_count"]),
        "terminal": branch.get("terminal") is True,
    }


def _candidate_identity(branch: Mapping[str, Any]) -> dict[str, Any]:
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
        "endpoint": _endpoint_identity(branch),
    }


def _pair_identity(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    role: str,
    root_id: str,
) -> dict[str, Any]:
    left, right = ordered_pair(left, right)
    value = {
        "role": role,
        "root_id": root_id,
        "left": _candidate_identity(left),
        "right": _candidate_identity(right),
        "internal_pair_key": _json_key((candidate_key(left), candidate_key(right))),
    }
    value["pair_id"] = json_sha256(value)
    return value


def _candidate_row_exact(
    branch: Mapping[str, Any], target: Mapping[str, Any]
) -> bool:
    tactic = str(branch.get("tactic", ""))
    try:
        expected_position = list(target["alternatives"]).index(tactic)
    except ValueError:
        return False
    return bool(
        branch.get("source") == "candidate"
        and branch.get("attempted") is True
        and branch.get("candidate_position_frozen") == expected_position
        and branch.get("execution_order_index") == expected_position
        and branch.get("head") == base.tactic_head(tactic)
        and branch.get("family") == base.tactic_family(tactic)
        and branch.get("record_sha256") == _record_sha(branch)
    )


def _validate_exp51_row(
    row: Mapping[str, Any],
    target: Mapping[str, Any],
    config_sha256: str,
) -> None:
    candidates = list(row.get("candidates", []))
    if not (
        row.get("protocol_version") == base.PROTOCOL_VERSION
        and row.get("mode") == "scientific"
        and row.get("config_sha256") == config_sha256
        and row.get("theorem_id") == target["theorem_id"]
        and row.get("slug") == target["slug"]
        and row.get("source_file_sha256") == target["source_file_sha256"]
        and row.get("candidate_order") == target["alternatives"]
        and row.get("record_sha256") == _record_sha(row)
    ):
        raise ValueError(f"Exp51 scientific row identity changed: {target['theorem_id']}")
    if row.get("worker_ok") is True and not (
        row.get("complete_candidate_order") is True
        and row.get("same_pre_state_all_branches") is True
        and row.get("authored_replay_ok") is True
        and len(candidates) == CANDIDATES_PER_ROOT
        and all(_candidate_row_exact(item, target) for item in candidates)
    ):
        raise ValueError(
            f"evaluable Exp51 row is incomplete: {target['theorem_id']}"
        )


def _strict_state_collision(
    branches: Iterable[Mapping[str, Any]],
    initial: Mapping[str, Any],
) -> bool:
    by_hash: dict[str, set[str]] = defaultdict(set)
    by_hash[_endpoint_hash(initial, "struct")].add(json.dumps(
        _complete_endpoint_payload(initial, "struct"),
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ))
    for branch in branches:
        if branch.get("executable") is True:
            by_hash[_endpoint_hash(branch, "struct")].add(json.dumps(
                _complete_endpoint_payload(branch, "struct"),
                ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            ))
    return any(len(values) != 1 for values in by_hash.values())


def _robust_branches(
    row: Mapping[str, Any], target: Mapping[str, Any]
) -> list[dict[str, Any]]:
    robust = list(target["robust_alternatives"])
    allowed = set(robust)
    selected = [
        dict(branch)
        for branch in row["candidates"]
        if branch["tactic"] in allowed
    ]
    if [branch["tactic"] for branch in selected] != robust:
        raise ValueError(
            f"L-mechanism-diverse order changed: {target['theorem_id']}"
        )
    return selected


def _eligible_branches(
    row: Mapping[str, Any], target: Mapping[str, Any]
) -> list[dict[str, Any]]:
    selected = _robust_branches(row, target)
    initial_sha = _endpoint_hash(row["initial_endpoints"], "struct")
    return [
        branch
        for branch in selected
        if branch.get("executable") is True
        and _endpoint_hash(branch, "struct") != initial_sha
        and branch.get("terminal") is False
        and int(branch.get("goal_count", 0)) > 0
    ]


def _distinct_mechanisms(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> bool:
    return bool(
        left["head"] != right["head"]
        and base.genealogy_for(str(left["tactic"]))["group"]
        != base.genealogy_for(str(right["tactic"]))["group"]
    )


def _witness_candidates(
    branches: list[dict[str, Any]], root_id: str
) -> list[dict[str, Any]]:
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for branch in branches:
        clusters[_endpoint_hash(branch)].append(branch)
    out = []
    for endpoint_sha, cluster in sorted(clusters.items()):
        for raw_left, raw_right in itertools.combinations(cluster, 2):
            if not _distinct_mechanisms(raw_left, raw_right):
                continue
            left, right = ordered_pair(raw_left, raw_right)
            features_left = strict_endpoint_features(left)
            features_right = strict_endpoint_features(right)
            if features_left != features_right:
                raise ValueError("equal strict endpoint has unequal feature vector")
            pair = _pair_identity(
                left, right, role="witness", root_id=root_id
            )
            pair.update({
                "strict_endpoint_sha256": endpoint_sha,
                "endpoint_features": list(features_left),
                "selection_order_key": _json_key((
                    endpoint_sha.encode("utf-8"),
                    candidate_key(left),
                    candidate_key(right),
                )),
            })
            out.append({"left_branch": left, "right_branch": right, "pair": pair})
    return sorted(
        out,
        key=lambda item: (
            item["pair"]["strict_endpoint_sha256"].encode("utf-8"),
            candidate_key(item["left_branch"]),
            candidate_key(item["right_branch"]),
        ),
    )


def _control_candidates(
    branches: list[dict[str, Any]],
    witness: Mapping[str, Any],
    root_id: str,
) -> list[dict[str, Any]]:
    witness_pair_id = witness["pair"]["pair_id"]
    witness_features = tuple(witness["pair"]["endpoint_features"])
    out = []
    for raw_left, raw_right in itertools.combinations(branches, 2):
        if not _distinct_mechanisms(raw_left, raw_right):
            continue
        if _endpoint_hash(raw_left) == _endpoint_hash(raw_right):
            continue
        left, right = ordered_pair(raw_left, raw_right)
        pair = _pair_identity(left, right, role="control", root_id=root_id)
        if pair["pair_id"] == witness_pair_id:
            continue
        left_features = strict_endpoint_features(left)
        right_features = strict_endpoint_features(right)
        distance = (
            abs(left_features[0] - witness_features[0])
            + abs(right_features[0] - witness_features[0]),
            abs(left_features[1] - witness_features[1])
            + abs(right_features[1] - witness_features[1]),
            abs(left_features[2] - witness_features[2])
            + abs(right_features[2] - witness_features[2]),
        )
        endpoint_hashes = tuple(sorted((_endpoint_hash(left), _endpoint_hash(right))))
        pair.update({
            "left_endpoint_features": list(left_features),
            "right_endpoint_features": list(right_features),
            "distance": list(distance),
            "sorted_endpoint_hashes": list(endpoint_hashes),
            "selection_order_key": _json_key((
                *distance,
                tuple(item.encode("utf-8") for item in endpoint_hashes),
                candidate_key(left),
                candidate_key(right),
            )),
        })
        out.append({"left_branch": left, "right_branch": right, "pair": pair})
    return sorted(
        out,
        key=lambda item: (
            *tuple(item["pair"]["distance"]),
            tuple(
                value.encode("utf-8")
                for value in item["pair"]["sorted_endpoint_hashes"]
            ),
            candidate_key(item["left_branch"]),
            candidate_key(item["right_branch"]),
        ),
    )


def _pair_ledger_row(
    *,
    root_id: str,
    theorem_id: str,
    slug: str,
    role: str,
    ordinal: int,
    selected: bool,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    row = {
        "schema": PAIR_LEDGER_SCHEMA,
        "version": 1,
        "root_id": root_id,
        "theorem_id": theorem_id,
        "slug": slug,
        "role": role,
        "selection_ordinal": ordinal,
        "selected": selected,
        "pair": value["pair"],
    }
    row["record_sha256"] = _record_sha(row)
    return row


def _audit_root_ids(witnesses: list[dict[str, Any]]) -> set[str]:
    by_repo: dict[str, list[str]] = defaultdict(list)
    for row in witnesses:
        by_repo[row["slug"]].append(row["root_id"])
    selected: set[str] = set()
    for slug, root_ids in sorted(by_repo.items()):
        ordered = sorted(
            root_ids,
            key=lambda value: (hashlib.sha256(value.encode("utf-8")).digest(), value),
        )
        selected.update(ordered[:determinism_audit_count(len(ordered))])
    return selected


def _cell(
    *,
    witness: Mapping[str, Any],
    pair_role: str,
    side: str,
    probe: str,
    probe_index: int,
    repeat_kind: str,
) -> dict[str, Any]:
    pair = witness[pair_role]
    candidate = pair[side]
    identity = {
        "root_id": witness["root_id"],
        "pair_role": pair_role,
        "pair_id": pair["pair_id"],
        "side": side,
        "probe": probe,
        "probe_index": probe_index,
        "repeat_kind": repeat_kind,
    }
    row = {
        "schema": CELL_PLAN_SCHEMA,
        "version": 1,
        "protocol_version": witness["protocol_version"],
        "amendment_sha256": witness["amendment_sha256"],
        "selection_record_sha256": witness["record_sha256"],
        "cell_id": json_sha256(identity),
        **identity,
        "theorem_id": witness["theorem_id"],
        "rid": witness["rid"],
        "slug": witness["slug"],
        "source_exp51_row": witness["source_exp51_row"],
        "source_exp51_row_sha256": witness["source_exp51_row_sha256"],
        "candidate": candidate,
        "expected_pair_endpoint_relation": (
            "same_strict_endpoint" if pair_role == "witness"
            else "different_strict_endpoints"
        ),
        "probe_panel_sha256": witness["probe_panel_sha256"],
        "fresh_process_required": True,
        "scientific_retry_permitted": False,
        "manual_reconciliation_count": 0,
    }
    row["record_sha256"] = _record_sha(row)
    return row


def _write_exact_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    if path.is_file():
        existing = read_jsonl(path)
        if existing != rows:
            raise ValueError(f"existing immutable ledger changed: {path}")
        return
    atomic_jsonl_dump(rows, path)


def _write_exact_json(value: Mapping[str, Any], path: Path) -> None:
    if path.is_file():
        if read_json(path) != value:
            raise ValueError(f"existing immutable JSON changed: {path}")
        return
    atomic_json_dump(value, path)


def _validate_exp51_lineage(
    root: Path,
    source: Mapping[str, Any],
    targets: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Bind every source theorem row to the finalized Exp51 index/receipt."""
    summaryp = root / "scientific/summary.json"
    indexp = root / "scientific/row_index.jsonl"
    if not summaryp.is_file() or not indexp.is_file():
        raise FileNotFoundError(summaryp if not summaryp.is_file() else indexp)
    summary = read_json(summaryp)
    index = read_jsonl(indexp)
    if not (
        summary.get("protocol_version") == base.PROTOCOL_VERSION
        and summary.get("alignment_version") == EXECUTION_ALIGNMENT_VERSION
        and summary.get("amendment_sha256") == source["amendment_sha256"]
        and summary.get("phase") == "scientific"
        and summary.get("config_sha256") == source["config_sha256"]
        and summary.get("targets_sha256") == source["targets_sha256"]
        and summary.get("shards_expected") == EXP51_SHARD_COUNT
        and summary.get("roots_expected") == TARGET_ROOTS
        and summary.get("root_receipts") == TARGET_ROOTS
        and summary.get("roots_attempted") == TARGET_ROOTS
        and summary.get("all_evaluable_rows_have_23_attempts") is True
        and summary.get("execution_complete") is True
        and summary.get("execution_gate") is True
        and summary.get("row_index_sha256") == file_sha256(indexp)
        and Path(summary.get("row_index", "")).resolve() == indexp.resolve()
        and summary.get("scientific_retry_count") == 0
        and summary.get("manual_reconciliation_count") == 0
        and len(index) == len(targets) == TARGET_ROOTS
    ):
        raise ValueError("Exp51 finalized scientific summary/index changed")
    evaluable = 0
    attempts = 0
    seen: set[str] = set()
    for frozen_index, (target, entry) in enumerate(zip(targets, index)):
        rowp = exp51_row_path(root, target).resolve()
        shard = frozen_index % EXP51_SHARD_COUNT
        receiptp = (
            root / "scientific/shards" / f"shard-{shard:02d}"
            / "receipts" / safe_slug(str(target["slug"]))
            / f"{target['rid']}.json"
        ).resolve()
        if not rowp.is_file() or not receiptp.is_file():
            raise FileNotFoundError(rowp if not rowp.is_file() else receiptp)
        row = read_json(rowp)
        receipt = read_json(receiptp)
        worker_ok = row.get("worker_ok") is True
        candidate_attempts = len(row.get("candidates", []))
        if not (
            entry.get("frozen_target_index") == frozen_index
            and entry.get("shard_index") == shard
            and entry.get("slug") == target["slug"]
            and entry.get("rid") == target["rid"]
            and entry.get("theorem_id") == target["theorem_id"]
            and Path(entry.get("row", "")).resolve() == rowp
            and entry.get("row_sha256") == file_sha256(rowp)
            and Path(entry.get("receipt", "")).resolve() == receiptp
            and entry.get("receipt_sha256") == file_sha256(receiptp)
            and entry.get("worker_ok") is worker_ok
            and entry.get("candidate_attempts") == candidate_attempts
            and receipt.get("amendment_sha256")
            == source["amendment_sha256"]
            and receipt.get("phase") == "scientific"
            and receipt.get("frozen_target_index") == frozen_index
            and receipt.get("theorem_id") == target["theorem_id"]
            and receipt.get("target_identity_sha256")
            == target["target_identity_sha256"]
            and Path(receipt.get("worker_row", "")).resolve() == rowp
            and receipt.get("worker_row_sha256") == file_sha256(rowp)
            and receipt.get("worker_ok") is worker_ok
            and receipt.get("candidate_attempts") == candidate_attempts
            and receipt.get("manual_reconciliation_count") == 0
            and str(target["theorem_id"]) not in seen
        ):
            raise ValueError(
                f"Exp51 finalized row lineage changed: {target['theorem_id']}"
            )
        seen.add(str(target["theorem_id"]))
        evaluable += int(worker_ok)
        attempts += candidate_attempts
    if not (
        summary.get("evaluable_roots") == evaluable
        and summary.get("unevaluable_roots") == TARGET_ROOTS - evaluable
        and summary.get("candidate_attempts_recorded") == attempts
        and summary.get("candidate_attempts_expected_on_evaluable_roots")
        == evaluable * CANDIDATES_PER_ROOT
    ):
        raise ValueError("Exp51 finalized aggregate lineage changed")
    return {
        "summary": str(summaryp), "summary_sha256": file_sha256(summaryp),
        "row_index": str(indexp), "row_index_sha256": file_sha256(indexp),
        "row_receipts": len(index), "evaluable_roots": evaluable,
        "candidate_attempts": attempts,
    }


def select(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    source = validate_amendment(root)
    config, targets, protocol, amendment = load_source_bundle(root)
    config_sha = source["config_sha256"]
    amendment_sha = source["amendment_sha256"]
    retained_probes = list(protocol["probe_surface"]["retained_panel"])
    exp51_lineage = _validate_exp51_lineage(root, source, targets)
    selection_root = root / "exp52/selection"

    root_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    witnesses: list[dict[str, Any]] = []
    invalid_counts: Counter[str] = Counter()
    source_row_ledger: list[dict[str, Any]] = []

    for frozen_index, target in enumerate(targets):
        rowp = exp51_row_path(root, target).resolve()
        if not rowp.is_file():
            raise FileNotFoundError(rowp)
        row = read_json(rowp)
        _validate_exp51_row(row, target, config_sha)
        source_row_ledger.append({
            "frozen_target_index": frozen_index,
            "theorem_id": target["theorem_id"],
            "path": str(rowp),
            "sha256": file_sha256(rowp),
            "bytes": rowp.stat().st_size,
        })
        root_id = str(target["theorem_id"])
        accounting: dict[str, Any] = {
            "schema": ROOT_LEDGER_SCHEMA,
            "version": 1,
            "frozen_target_index": frozen_index,
            "root_id": root_id,
            "theorem_id": target["theorem_id"],
            "rid": target["rid"],
            "slug": target["slug"],
            "source_exp51_row": str(rowp),
            "source_exp51_row_sha256": file_sha256(rowp),
            "worker_ok": row.get("worker_ok") is True,
        }
        if row.get("worker_ok") is not True:
            accounting.update({
                "selection_status": "exp51_unevaluable",
                "eligible_witness_pairs": 0,
                "eligible_control_pairs": 0,
            })
            invalid_counts["exp51_unevaluable"] += 1
        else:
            robust_branches = _robust_branches(row, target)
            if _strict_state_collision(
                robust_branches, row["initial_endpoints"]
            ):
                accounting.update({
                    "selection_status": "invalid_strict_hash_collision",
                    "eligible_witness_pairs": 0,
                    "eligible_control_pairs": 0,
                })
                invalid_counts["invalid_strict_hash_collision"] += 1
            else:
                branches = _eligible_branches(row, target)
                witness_values = _witness_candidates(branches, root_id)
                for ordinal, item in enumerate(witness_values):
                    pair_rows.append(_pair_ledger_row(
                        root_id=root_id, theorem_id=target["theorem_id"],
                        slug=target["slug"], role="witness", ordinal=ordinal,
                        selected=ordinal == 0, value=item,
                    ))
                if not witness_values:
                    accounting.update({
                        "selection_status": "no_eligible_witness",
                        "eligible_witness_pairs": 0,
                        "eligible_control_pairs": 0,
                    })
                    invalid_counts["no_eligible_witness"] += 1
                else:
                    selected_witness = witness_values[0]
                    controls = _control_candidates(
                        branches, selected_witness, root_id
                    )
                    for ordinal, item in enumerate(controls):
                        pair_rows.append(_pair_ledger_row(
                            root_id=root_id, theorem_id=target["theorem_id"],
                            slug=target["slug"], role="control", ordinal=ordinal,
                            selected=ordinal == 0, value=item,
                        ))
                    witness_pair = selected_witness["pair"]
                    control_pair = controls[0]["pair"] if controls else None
                    excluded = {
                        witness_pair["left"]["tactic"],
                        witness_pair["right"]["tactic"],
                    }
                    if control_pair is not None:
                        excluded.update({
                            control_pair["left"]["tactic"],
                            control_pair["right"]["tactic"],
                        })
                    probe_panel = [
                        probe for probe in retained_probes if probe not in excluded
                    ]
                    value: dict[str, Any] = {
                        "schema": SELECTION_SCHEMA,
                        "version": 1,
                        "selection_version": EXP52_SELECTION_VERSION,
                        "protocol_version": protocol["protocol_version"],
                        "design_lock_version": protocol["design_lock_version"],
                        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
                        "amendment_sha256": amendment_sha,
                        "exp51_config_sha256": config_sha,
                        "exp52_protocol_sha256": source["protocol_sha256"],
                        "frozen_target_index": frozen_index,
                        "root_id": root_id,
                        "theorem_id": target["theorem_id"],
                        "rid": target["rid"],
                        "slug": target["slug"],
                        "source_exp51_row": str(rowp),
                        "source_exp51_row_sha256": file_sha256(rowp),
                        "initial_endpoint": {
                            kind: row["initial_endpoints"][kind]["sha256"]
                            for kind in ("raw", "text48", "struct")
                        },
                        "robust_panel": list(target["robust_alternatives"]),
                        "robust_panel_sha256": json_sha256(
                            target["robust_alternatives"]
                        ),
                        "witness": witness_pair,
                        "control": control_pair,
                        "has_within_root_control": control_pair is not None,
                        "eligible_witness_pair_count": len(witness_values),
                        "eligible_control_pair_count": len(controls),
                        "retained_global_probe_panel": retained_probes,
                        "excluded_exact_pair_tactic_texts": sorted(
                            excluded, key=lambda item: item.encode("utf-8")
                        ),
                        "probe_panel": probe_panel,
                        "probe_panel_sha256": json_sha256(probe_panel),
                        "manual_replacement_count": 0,
                        "manual_reconciliation_count": 0,
                    }
                    value["record_sha256"] = _record_sha(value)
                    witnesses.append(value)
                    accounting.update({
                        "selection_status": "witness_selected",
                        "eligible_witness_pairs": len(witness_values),
                        "eligible_control_pairs": len(controls),
                        "selected_witness_pair_id": witness_pair["pair_id"],
                        "selected_control_pair_id": (
                            control_pair["pair_id"] if control_pair else None
                        ),
                        "probe_count": len(probe_panel),
                    })
        accounting["record_sha256"] = _record_sha(accounting)
        root_rows.append(accounting)

    audit_ids = _audit_root_ids(witnesses)
    revised_witnesses = []
    for value in witnesses:
        value = dict(value)
        value["determinism_audit_selected"] = value["root_id"] in audit_ids
        value["record_sha256"] = _record_sha(value)
        revised_witnesses.append(value)
    witnesses = revised_witnesses

    audit_rows = []
    for value in witnesses:
        if value["determinism_audit_selected"]:
            row = {
                "version": 1,
                "selection_version": EXP52_SELECTION_VERSION,
                "root_id": value["root_id"],
                "theorem_id": value["theorem_id"],
                "slug": value["slug"],
                "witness_pair_id": value["witness"]["pair_id"],
                "selection_record_sha256": value["record_sha256"],
                "selection_key_sha256": hashlib.sha256(
                    value["root_id"].encode("utf-8")
                ).hexdigest(),
            }
            row["record_sha256"] = _record_sha(row)
            audit_rows.append(row)

    cells = []
    for witness in witnesses:
        roles = ["witness"]
        if witness["control"] is not None:
            roles.append("control")
        for pair_role in roles:
            for side in ("left", "right"):
                for probe_index, probe in enumerate(witness["probe_panel"]):
                    cells.append(_cell(
                        witness=witness, pair_role=pair_role, side=side,
                        probe=probe, probe_index=probe_index,
                        repeat_kind="primary",
                    ))
        if witness["determinism_audit_selected"]:
            for side in ("left", "right"):
                for probe_index, probe in enumerate(witness["probe_panel"]):
                    cells.append(_cell(
                        witness=witness, pair_role="witness", side=side,
                        probe=probe, probe_index=probe_index,
                        repeat_kind="determinism_audit",
                    ))

    roots_path = selection_root / "roots.jsonl"
    pairs_path = selection_root / "eligible_pairs.jsonl"
    witnesses_path = selection_root / "witnesses.jsonl"
    audits_path = selection_root / "audit_subset.jsonl"
    cells_path = selection_root / "execution_cells.jsonl"
    source_rows_path = selection_root / "source_exp51_rows.jsonl"
    for rows, path in (
        (root_rows, roots_path), (pair_rows, pairs_path),
        (witnesses, witnesses_path), (audit_rows, audits_path),
        (cells, cells_path), (source_row_ledger, source_rows_path),
    ):
        _write_exact_jsonl(rows, path)

    witness_repo_counts = Counter(row["slug"] for row in witnesses)
    control_repo_counts = Counter(
        row["slug"] for row in witnesses if row["control"] is not None
    )
    summary = {
        "version": 1,
        "selection_version": EXP52_SELECTION_VERSION,
        "schema": SELECTION_SCHEMA,
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "mechanical_fix_id": EXECUTION_FIX_ID,
        "amendment_sha256": amendment_sha,
        "exp51_config_sha256": config_sha,
        "exp51_targets_sha256": source["targets_sha256"],
        "exp52_protocol_sha256": source["protocol_sha256"],
        "source_exp51_scientific_summary": exp51_lineage["summary"],
        "source_exp51_scientific_summary_sha256": (
            exp51_lineage["summary_sha256"]
        ),
        "source_exp51_row_index": exp51_lineage["row_index"],
        "source_exp51_row_index_sha256": exp51_lineage["row_index_sha256"],
        "source_exp51_row_receipts": exp51_lineage["row_receipts"],
        "roots_accounted": len(root_rows),
        "source_exp51_rows": len(source_row_ledger),
        "selected_witness_roots": len(witnesses),
        "selected_witness_repositories": len(witness_repo_counts),
        "within_root_control_pairs": sum(
            row["control"] is not None for row in witnesses
        ),
        "control_repositories": len(control_repo_counts),
        "determinism_audit_roots": len(audit_rows),
        "execution_cells": len(cells),
        "primary_execution_cells": sum(
            row["repeat_kind"] == "primary" for row in cells
        ),
        "determinism_audit_cells": sum(
            row["repeat_kind"] == "determinism_audit" for row in cells
        ),
        "root_status_counts": dict(Counter(
            row["selection_status"] for row in root_rows
        )),
        "witness_roots_per_repository": dict(sorted(witness_repo_counts.items())),
        "control_roots_per_repository": dict(sorted(control_repo_counts.items())),
        "retained_global_probe_panel": retained_probes,
        "retained_global_probe_panel_sha256": json_sha256(retained_probes),
        "roots_ledger": roots_path.relative_to(root).as_posix(),
        "roots_ledger_sha256": file_sha256(roots_path),
        "eligible_pairs_ledger": pairs_path.relative_to(root).as_posix(),
        "eligible_pairs_ledger_sha256": file_sha256(pairs_path),
        "witness_ledger": witnesses_path.relative_to(root).as_posix(),
        "witness_ledger_sha256": file_sha256(witnesses_path),
        "audit_subset_ledger": audits_path.relative_to(root).as_posix(),
        "audit_subset_ledger_sha256": file_sha256(audits_path),
        "execution_cell_plan": cells_path.relative_to(root).as_posix(),
        "execution_cell_plan_sha256": file_sha256(cells_path),
        "source_exp51_row_ledger": source_rows_path.relative_to(root).as_posix(),
        "source_exp51_row_ledger_sha256": file_sha256(source_rows_path),
        "manual_replacement_count": 0,
        "manual_reconciliation_count": 0,
        "selection_complete": len(root_rows) == TARGET_ROOTS,
        "next_step": "Run compile-only Exp52 worker preflight.",
    }
    summary["identity_sha256"] = identity_sha256(summary)
    _write_exact_json(summary, selection_root / "summary.json")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(SCIENTIFIC_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    value = select(parse_args())
    raise SystemExit(0 if value.get("selection_complete") is True else 2)
