"""Freeze a downstream-unseen, paired Exp54 depth-2 microbenchmark."""
from __future__ import annotations

import argparse
import itertools
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from experiment54_protocol import *


def validate_superseded_v1() -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Lock the complete failed v1 attempt before the Fix1 design is written."""
    source = superseded_v1_root().resolve()
    design_path = source / "frozen/design.json"
    summary_path = source / "execution/summary.json"
    index_path = source / "execution/row_index.jsonl"
    for path in (design_path, summary_path, index_path):
        if not path.is_file():
            raise FileNotFoundError(f"missing superseded Exp54 v1 evidence: {path}")
    design = read_json(design_path)
    if not (
        design.get("protocol_version") == PROTOCOL_VERSION
        and design.get("record_sha256") == record_sha(design)
    ):
        raise ValueError("superseded Exp54 v1 design changed")
    source_code = server_root() / "experiment54_effect_aware_depth2_microbenchmark"
    observed_code = {
        name: file_sha256(source_code / name)
        for name in design.get("code_lock", {})
        if (source_code / name).is_file()
    }
    if observed_code != design.get("code_lock"):
        raise ValueError("superseded Exp54 v1 source code is unavailable or changed")
    summary = read_json(summary_path)
    if not (
        summary.get("cells_recorded") == EXPECTED_CELLS
        and summary.get("full_cells_recorded") == EXPECTED_FULL_CELLS
        and summary.get("dedup_cells_recorded") == EXPECTED_DEDUP_CELLS
        and summary.get("valid_reconstruction_cells") == 344
        and summary.get("fresh_lean_process_cells") == 889
        and summary.get("probe_status_counts") == {
            "success": 56,
            "invalid_reconstruction": 545,
            "failure": 288,
            "worker_failure": 7,
        }
        and summary.get("execution_gate") is True
        and summary.get("execution_integrity_gate") is False
        and summary.get("scientific_retry_count") == 0
        and summary.get("manual_reconciliation_count") == 0
        and summary.get("row_index_sha256") == file_sha256(index_path)
    ):
        raise ValueError("superseded Exp54 v1 failure signature changed")
    source_rows = read_jsonl(index_path)
    if len(source_rows) != EXPECTED_CELLS:
        raise ValueError("superseded Exp54 v1 row accounting changed")
    ledger = []
    for item in source_rows:
        row_path = Path(item["path"])
        if not row_path.is_file() or file_sha256(row_path) != item["sha256"]:
            raise ValueError("superseded Exp54 v1 row changed")
        raw_path = (
            row_path.parent.parent / "runtime/lean_raw" / f"{item['cell_id']}.json"
        )
        if not raw_path.is_file():
            raise ValueError("superseded Exp54 v1 raw Lean output is missing")
        ledger.append({
            "cell_id": item["cell_id"],
            "row_sha256": item["sha256"],
            "raw_lean_sha256": file_sha256(raw_path),
        })
    receipt = {
        "artifact_root": str(source),
        "design_sha256": file_sha256(design_path),
        "execution_summary_sha256": file_sha256(summary_path),
        "row_index_sha256": file_sha256(index_path),
        "row_and_raw_ledger_sha256": json_sha256(ledger),
        "cells_recorded": EXPECTED_CELLS,
        "raw_lean_outputs_found": EXPECTED_CELLS,
        "valid_reconstruction_cells": 344,
        "invalid_reconstruction_cells": 545,
        "worker_failure_cells": 7,
        "execution_integrity_gate": False,
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
        "preserved_as_failed_execution": True,
    }
    return receipt, ledger


def validate_superseded_fix1() -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Lock the complete failed Fix1 attempt before Fix2 is frozen."""
    source = superseded_fix1_root().resolve()
    design_path = source / "frozen/design.json"
    summary_path = source / "execution/summary.json"
    index_path = source / "execution/row_index.jsonl"
    for path in (design_path, summary_path, index_path):
        if not path.is_file():
            raise FileNotFoundError(f"missing superseded Exp54 Fix1 evidence: {path}")
    design = read_json(design_path)
    if not (
        design.get("protocol_version") == PROTOCOL_VERSION
        and design.get("execution_version")
        == "experiment54-effect-aware-depth2-microbenchmark-fix1"
        and design.get("mechanical_fix_id")
        == "exp54-fix1-exp49-text48-context-heartbeat-and-null-result-handling"
        and design.get("record_sha256") == record_sha(design)
    ):
        raise ValueError("superseded Exp54 Fix1 design changed")
    source_code = server_root() / "experiment54_effect_aware_depth2_microbenchmark_fix1"
    observed_code = {
        name: file_sha256(source_code / name)
        for name in design.get("code_lock", {})
        if (source_code / name).is_file()
    }
    if observed_code != design.get("code_lock"):
        raise ValueError("superseded Exp54 Fix1 source code is unavailable or changed")
    summary = read_json(summary_path)
    if not (
        summary.get("cells_recorded") == EXPECTED_CELLS
        and summary.get("full_cells_recorded") == EXPECTED_FULL_CELLS
        and summary.get("dedup_cells_recorded") == EXPECTED_DEDUP_CELLS
        and summary.get("valid_reconstruction_cells") == 889
        and summary.get("fresh_lean_process_cells") == 896
        and summary.get("probe_status_counts") == {
            "success": 129,
            "failure": 760,
            "candidate_reconstruction_failure": 7,
        }
        and summary.get("failure_category_counts") == {
            "tactic_failure": 760,
            "candidate_execution_failure": 7,
        }
        and summary.get("execution_gate") is True
        and summary.get("execution_integrity_gate") is False
        and summary.get("scientific_retry_count") == 0
        and summary.get("manual_reconciliation_count") == 0
        and summary.get("row_index_sha256") == file_sha256(index_path)
    ):
        raise ValueError("superseded Exp54 Fix1 failure signature changed")
    source_rows = read_jsonl(index_path)
    if len(source_rows) != EXPECTED_CELLS:
        raise ValueError("superseded Exp54 Fix1 row accounting changed")
    ledger = []
    for item in source_rows:
        row_path = Path(item["path"])
        if not row_path.is_file() or file_sha256(row_path) != item["sha256"]:
            raise ValueError("superseded Exp54 Fix1 row changed")
        raw_path = (
            row_path.parent.parent / "runtime/lean_raw" / f"{item['cell_id']}.json"
        )
        if not raw_path.is_file():
            raise ValueError("superseded Exp54 Fix1 raw Lean output is missing")
        ledger.append({
            "cell_id": item["cell_id"],
            "row_sha256": item["sha256"],
            "raw_lean_sha256": file_sha256(raw_path),
        })
    receipt = {
        "artifact_root": str(source),
        "design_sha256": file_sha256(design_path),
        "execution_summary_sha256": file_sha256(summary_path),
        "row_index_sha256": file_sha256(index_path),
        "row_and_raw_ledger_sha256": json_sha256(ledger),
        "cells_recorded": EXPECTED_CELLS,
        "raw_lean_outputs_found": EXPECTED_CELLS,
        "valid_reconstruction_cells": 889,
        "candidate_reconstruction_failure_cells": 7,
        "execution_integrity_gate": False,
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
        "preserved_as_failed_execution": True,
    }
    return receipt, ledger


def validate_superseded_fix2() -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Lock the complete failed Fix2 attempt before Fix3 is frozen."""
    source = superseded_fix2_root().resolve()
    design_path = source / "frozen/design.json"
    summary_path = source / "execution/summary.json"
    index_path = source / "execution/row_index.jsonl"
    for path in (design_path, summary_path, index_path):
        if not path.is_file():
            raise FileNotFoundError(f"missing superseded Exp54 Fix2 evidence: {path}")
    design = read_json(design_path)
    if not (
        design.get("protocol_version") == PROTOCOL_VERSION
        and design.get("execution_version")
        == "experiment54-effect-aware-depth2-microbenchmark-fix2"
        and design.get("mechanical_fix_id")
        == "exp54-fix2-heartbeat-exhausted-lazy-exception-recording"
        and design.get("record_sha256") == record_sha(design)
    ):
        raise ValueError("superseded Exp54 Fix2 design changed")
    source_code = server_root() / "experiment54_effect_aware_depth2_microbenchmark_fix2"
    observed_code = {
        name: file_sha256(source_code / name)
        for name in design.get("code_lock", {})
        if (source_code / name).is_file()
    }
    if observed_code != design.get("code_lock"):
        raise ValueError("superseded Exp54 Fix2 source code is unavailable or changed")
    summary = read_json(summary_path)
    if not (
        summary.get("cells_recorded") == EXPECTED_CELLS
        and summary.get("full_cells_recorded") == EXPECTED_FULL_CELLS
        and summary.get("dedup_cells_recorded") == EXPECTED_DEDUP_CELLS
        and summary.get("valid_reconstruction_cells") == 889
        and summary.get("fresh_lean_process_cells") == 896
        and summary.get("probe_status_counts") == {
            "success": 129,
            "failure": 760,
            "candidate_reconstruction_failure": 7,
        }
        and summary.get("failure_category_counts") == {
            "tactic_failure": 760,
            "candidate_execution_failure": 7,
        }
        and summary.get("execution_gate") is True
        and summary.get("execution_integrity_gate") is False
        and summary.get("scientific_retry_count") == 0
        and summary.get("manual_reconciliation_count") == 0
        and summary.get("row_index_sha256") == file_sha256(index_path)
    ):
        raise ValueError("superseded Exp54 Fix2 failure signature changed")
    source_rows = read_jsonl(index_path)
    if len(source_rows) != EXPECTED_CELLS:
        raise ValueError("superseded Exp54 Fix2 row accounting changed")
    ledger = []
    for item in source_rows:
        row_path = Path(item["path"])
        if not row_path.is_file() or file_sha256(row_path) != item["sha256"]:
            raise ValueError("superseded Exp54 Fix2 row changed")
        raw_path = (
            row_path.parent.parent / "runtime/lean_raw" / f"{item['cell_id']}.json"
        )
        if not raw_path.is_file():
            raise ValueError("superseded Exp54 Fix2 raw Lean output is missing")
        ledger.append({
            "cell_id": item["cell_id"],
            "row_sha256": item["sha256"],
            "raw_lean_sha256": file_sha256(raw_path),
        })
    receipt = {
        "artifact_root": str(source),
        "design_sha256": file_sha256(design_path),
        "execution_summary_sha256": file_sha256(summary_path),
        "row_index_sha256": file_sha256(index_path),
        "row_and_raw_ledger_sha256": json_sha256(ledger),
        "cells_recorded": EXPECTED_CELLS,
        "raw_lean_outputs_found": EXPECTED_CELLS,
        "valid_reconstruction_cells": 889,
        "candidate_reconstruction_failure_cells": 7,
        "execution_integrity_gate": False,
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
        "preserved_as_failed_execution": True,
    }
    return receipt, ledger


def branch_key(branch: Mapping[str, Any]) -> tuple[int, bytes]:
    return (
        int(branch["candidate_position_frozen"]),
        str(branch["tactic"]).encode("utf-8"),
    )


def ordered_pair(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        (dict(left), dict(right))
        if branch_key(left) <= branch_key(right)
        else (dict(right), dict(left))
    )


def compact_branch(row: Mapping[str, Any], position: int) -> dict[str, Any]:
    return {
        "source": "alternative",
        "candidate_position_frozen": position,
        "tactic": row["tactic"],
        "head": row["head"],
        "family": row["family"],
        "executable": row.get("executable") is True,
        "terminal": row.get("terminal") is True,
        "goal_count": int(row.get("goal_count", 0)),
        "endpoints": row.get("endpoints"),
    }


def pair_record(
    *, root_id: str, slug: str, role: str,
    left: Mapping[str, Any], right: Mapping[str, Any],
) -> dict[str, Any]:
    left, right = ordered_pair(left, right)
    identity = {
        "target_id": root_id[:20],
        "root_id": root_id,
        "slug": slug,
        "role": role,
        "left": {
            "candidate_position_frozen": left["candidate_position_frozen"],
            "tactic": left["tactic"],
            "head": left["head"],
            "strict_endpoint_sha256": left["endpoints"]["struct"]["sha256"],
        },
        "right": {
            "candidate_position_frozen": right["candidate_position_frozen"],
            "tactic": right["tactic"],
            "head": right["head"],
            "strict_endpoint_sha256": right["endpoints"]["struct"]["sha256"],
        },
    }
    return seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "pair_id": json_sha256(identity),
        **identity,
        "representative_side": "left",
        "selection_rule": (
            "lowest frozen candidate-position tuple after role eligibility"
        ),
        "left_branch": left,
        "right_branch": right,
    })


def root_candidate(
    *, raw: bytes, member: zipfile.ZipInfo,
) -> dict[str, Any] | None:
    row = json.loads(raw)
    identity = row["identity"]
    analysis = row["analysis"]
    worker = row["worker"]
    selection = row["selection"]
    if not (
        identity.get("protocol_version") == SOURCE_EXP49_PROTOCOL
        and identity.get("phase") == "validation"
        and analysis.get("evaluable") is True
        and worker.get("worker_ok") is True
        and worker.get("pre_goal_count") == 1
        and worker.get("same_pre_state_struct_all_branches") is True
        and worker.get("same_pre_state_text_all_branches") is True
    ):
        return None
    alternatives = list(selection["alternatives"])
    by_tactic = {
        e["tactic"]: e for e in worker["executions"]
        if e.get("source") == "alternative"
    }
    if set(by_tactic) != set(alternatives):
        raise ValueError(f"Exp49 candidate matrix changed: {identity['theorem_id']}")
    initial_sha = worker["initial_endpoints"]["struct"]["sha256"]
    branches = []
    for position, tactic in enumerate(alternatives):
        branch = compact_branch(by_tactic[tactic], position)
        if (
            branch["executable"]
            and not branch["terminal"]
            and branch["goal_count"] > 0
            and branch["endpoints"]["struct"]["sha256"] != initial_sha
        ):
            branches.append(branch)
    witnesses = []
    controls = []
    for a0, b0 in itertools.combinations(branches, 2):
        if a0["head"] == b0["head"]:
            continue
        a, b = ordered_pair(a0, b0)
        same = (
            a["endpoints"]["struct"]["sha256"]
            == b["endpoints"]["struct"]["sha256"]
        )
        key = (
            a["endpoints"]["struct"]["sha256"],
            b["endpoints"]["struct"]["sha256"],
            branch_key(a), branch_key(b),
        )
        (witnesses if same else controls).append((key, a, b))
    if not witnesses or not controls:
        return None
    witnesses.sort(key=lambda item: item[0])
    controls.sort(key=lambda item: item[0])
    root_id = str(identity["theorem_id"])
    slug = str(identity["slug"])
    witness = pair_record(
        root_id=root_id, slug=slug, role="witness",
        left=witnesses[0][1], right=witnesses[0][2],
    )
    control = pair_record(
        root_id=root_id, slug=slug, role="control",
        left=controls[0][1], right=controls[0][2],
    )
    return {
        "archive_member": member.filename,
        "archive_member_bytes": member.file_size,
        "archive_member_sha256": bytes_sha256(raw),
        "identity": identity,
        "selection": {
            key: selection[key] for key in (
                "theorem_id", "full_name", "file_path", "module", "start", "end",
                "source_file_sha256", "trace_root_state_sha256", "authored_tactic",
            )
        },
        "target_pos": int(worker["target_pos"]),
        "target_end_pos": int(worker["target_end_pos"]),
        "initial_endpoints": worker["initial_endpoints"],
        "witness": witness,
        "control": control,
        "eligible_witness_pairs": len(witnesses),
        "eligible_control_pairs": len(controls),
    }


def cell_record(
    *, cell_index: int, target_id: str, pair: Mapping[str, Any],
    policy: str, side: str, probe: str, probe_index: int,
) -> dict[str, Any]:
    identity = {
        "target_id": target_id,
        "root_id": pair["root_id"],
        "slug": pair["slug"],
        "pair_id": pair["pair_id"],
        "pair_role": pair["role"],
        "policy": policy,
        "side": side,
        "probe": probe,
        "probe_index": probe_index,
    }
    return seal({
        "schema": CELL_SCHEMA,
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "cell_index": cell_index,
        "cell_id": json_sha256(identity)[:24],
        "shard_index": cell_index % SHARD_COUNT,
        **identity,
    })


def freeze(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.artifact_root).resolve()
    archive = Path(args.source_archive).resolve()
    design_path = root / "frozen/design.json"
    if design_path.is_file():
        design = load_freeze(root)
        print(json.dumps(design["freeze_receipt"], indent=2))
        return design["freeze_receipt"]
    superseded, superseded_ledger = validate_superseded_v1()
    snapshot_root = root / "frozen/superseded_v1_snapshots"
    snapshots = {}
    for label, relative in (
        ("design", "frozen/design.json"),
        ("execution_summary", "execution/summary.json"),
        ("row_index", "execution/row_index.jsonl"),
    ):
        source_path = superseded_v1_root() / relative
        snapshot_path = snapshot_root / relative.replace("/", "__")
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_bytes(source_path.read_bytes())
        snapshots[label] = {
            "path": str(snapshot_path),
            "bytes": snapshot_path.stat().st_size,
            "sha256": file_sha256(snapshot_path),
        }
    superseded["exact_snapshots"] = snapshots
    superseded_ledger_path = root / "frozen/superseded_v1_row_raw_ledger.jsonl"
    atomic_jsonl_dump(superseded_ledger, superseded_ledger_path)
    superseded.update({
        "row_and_raw_ledger_path": str(superseded_ledger_path),
        "row_and_raw_ledger_file_sha256": file_sha256(superseded_ledger_path),
    })
    superseded_receipt_path = root / "frozen/superseded_v1_failure_receipt.json"
    atomic_json_dump(superseded, superseded_receipt_path)
    superseded["failure_receipt_path"] = str(superseded_receipt_path)
    superseded["failure_receipt_sha256"] = file_sha256(superseded_receipt_path)
    superseded_fix1, superseded_fix1_ledger = validate_superseded_fix1()
    fix1_snapshot_root = root / "frozen/superseded_fix1_snapshots"
    fix1_snapshots = {}
    for label, relative in (
        ("design", "frozen/design.json"),
        ("execution_summary", "execution/summary.json"),
        ("row_index", "execution/row_index.jsonl"),
    ):
        source_path = superseded_fix1_root() / relative
        snapshot_path = fix1_snapshot_root / relative.replace("/", "__")
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_bytes(source_path.read_bytes())
        fix1_snapshots[label] = {
            "path": str(snapshot_path),
            "bytes": snapshot_path.stat().st_size,
            "sha256": file_sha256(snapshot_path),
        }
    superseded_fix1["exact_snapshots"] = fix1_snapshots
    fix1_ledger_path = root / "frozen/superseded_fix1_row_raw_ledger.jsonl"
    atomic_jsonl_dump(superseded_fix1_ledger, fix1_ledger_path)
    superseded_fix1.update({
        "row_and_raw_ledger_path": str(fix1_ledger_path),
        "row_and_raw_ledger_file_sha256": file_sha256(fix1_ledger_path),
    })
    fix1_receipt_path = root / "frozen/superseded_fix1_failure_receipt.json"
    atomic_json_dump(superseded_fix1, fix1_receipt_path)
    superseded_fix1["failure_receipt_path"] = str(fix1_receipt_path)
    superseded_fix1["failure_receipt_sha256"] = file_sha256(fix1_receipt_path)
    superseded_fix2, superseded_fix2_ledger = validate_superseded_fix2()
    fix2_snapshot_root = root / "frozen/superseded_fix2_snapshots"
    fix2_snapshots = {}
    for label, relative in (
        ("design", "frozen/design.json"),
        ("execution_summary", "execution/summary.json"),
        ("row_index", "execution/row_index.jsonl"),
    ):
        source_path = superseded_fix2_root() / relative
        snapshot_path = fix2_snapshot_root / relative.replace("/", "__")
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_bytes(source_path.read_bytes())
        fix2_snapshots[label] = {
            "path": str(snapshot_path),
            "bytes": snapshot_path.stat().st_size,
            "sha256": file_sha256(snapshot_path),
        }
    superseded_fix2["exact_snapshots"] = fix2_snapshots
    fix2_ledger_path = root / "frozen/superseded_fix2_row_raw_ledger.jsonl"
    atomic_jsonl_dump(superseded_fix2_ledger, fix2_ledger_path)
    superseded_fix2.update({
        "row_and_raw_ledger_path": str(fix2_ledger_path),
        "row_and_raw_ledger_file_sha256": file_sha256(fix2_ledger_path),
    })
    fix2_receipt_path = root / "frozen/superseded_fix2_failure_receipt.json"
    atomic_json_dump(superseded_fix2, fix2_receipt_path)
    superseded_fix2["failure_receipt_path"] = str(fix2_receipt_path)
    superseded_fix2["failure_receipt_sha256"] = file_sha256(fix2_receipt_path)
    if not archive.is_file() or file_sha256(archive) != SOURCE_EXP49_SHA256:
        raise ValueError("Exp49 source archive missing or SHA changed")
    by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exclusion_counts = Counter()
    with zipfile.ZipFile(archive) as zf:
        config_raw = zf.read("artifacts/frozen/experiment49_config.json")
        config = json.loads(config_raw)
        if config.get("protocol_version") != SOURCE_EXP49_PROTOCOL:
            raise ValueError("wrong Exp49 source protocol")
        repo_config = {r["slug"]: r for r in config["repositories"]}
        members = sorted(
            (
                info for info in zf.infolist()
                if info.filename.startswith("artifacts/validation/theorems/")
                and info.filename.endswith(".json")
            ),
            key=lambda info: info.filename,
        )
        for member in members:
            if member.file_size > SOURCE_EXP49_MEMBER_LIMIT_BYTES:
                exclusion_counts["archive_member_above_20MiB_portability_gate"] += 1
                continue
            value = root_candidate(raw=zf.read(member), member=member)
            if value is None:
                exclusion_counts["no_within_root_witness_and_control"] += 1
                continue
            slug = value["identity"]["slug"]
            if slug in REPOSITORIES:
                by_repo[slug].append(value)
    selected: list[dict[str, Any]] = []
    eligibility: list[dict[str, Any]] = []
    for slug in REPOSITORIES:
        candidates = sorted(
            by_repo[slug],
            key=lambda row: (
                row["archive_member_bytes"], row["identity"]["theorem_id"]
            ),
        )
        eligibility.append({
            "slug": slug,
            "eligible_roots": len(candidates),
            "selected_roots": min(len(candidates), ROOTS_PER_REPOSITORY),
        })
        if len(candidates) < ROOTS_PER_REPOSITORY:
            raise ValueError(f"Exp54 sample quota unavailable for {slug}")
        selected.extend(candidates[:ROOTS_PER_REPOSITORY])
    targets: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    for ordinal, item in enumerate(selected):
        slug = item["identity"]["slug"]
        target_id = item["identity"]["theorem_id"][:20]
        target = seal({
            "version": VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "target_id": target_id,
            "selection_ordinal": ordinal,
            "slug": slug,
            "commit": item["identity"]["commit"],
            "theorem_id": item["identity"]["theorem_id"],
            "full_name": item["identity"]["full_name"],
            "file_path": item["selection"]["file_path"],
            "source_file_sha256": item["identity"]["source_file_sha256"],
            "target_pos": item["target_pos"],
            "target_end_pos": item["target_end_pos"],
            "checkout": str(repository_checkout(slug)),
            "archive_member": item["archive_member"],
            "archive_member_bytes": item["archive_member_bytes"],
            "archive_member_sha256": item["archive_member_sha256"],
            "initial_endpoints": item["initial_endpoints"],
            "pairs": {
                "witness": item["witness"],
                "control": item["control"],
            },
            "eligible_witness_pairs": item["eligible_witness_pairs"],
            "eligible_control_pairs": item["eligible_control_pairs"],
            "exp49_repository_config": {
                "commit": repo_config[slug]["commit"],
                "selected_file_sha256": repo_config[slug]["selected_file_sha256"],
            },
        })
        atomic_json_dump(target, root / "frozen/targets" / f"{target_id}.json")
        targets.append({
            "target_id": target_id,
            "slug": slug,
            "theorem_id": target["theorem_id"],
            "path": str(root / "frozen/targets" / f"{target_id}.json"),
            "sha256": file_sha256(root / "frozen/targets" / f"{target_id}.json"),
            "record_sha256": target["record_sha256"],
        })
        for role in ("witness", "control"):
            pair = dict(target["pairs"][role])
            pairs.append(pair)
    cells: list[dict[str, Any]] = []
    for pair in pairs:
        for policy in ("full", "dedup"):
            sides = ["left", "right"]
            if policy == "dedup" and pair["role"] == "witness":
                sides = [pair["representative_side"]]
            for side in sides:
                for probe_index, probe in enumerate(PROBES):
                    cells.append(cell_record(
                        cell_index=len(cells), target_id=pair["target_id"],
                        pair=pair, policy=policy, side=side,
                        probe=probe, probe_index=probe_index,
                    ))
    if not (
        len(targets) == EXPECTED_ROOTS
        and len(pairs) == EXPECTED_PAIRS
        and sum(c["policy"] == "full" for c in cells) == EXPECTED_FULL_CELLS
        and sum(c["policy"] == "dedup" for c in cells) == EXPECTED_DEDUP_CELLS
        and len(cells) == EXPECTED_CELLS
    ):
        raise ValueError("Exp54 frozen accounting changed")
    source = superseded_v1_root()
    source_pairs = read_jsonl(source / "frozen/pairs.jsonl")
    source_cells = read_jsonl(source / "frozen/cells.jsonl")
    if pairs != source_pairs or cells != source_cells:
        raise ValueError("Fix3 changed the v1 frozen Exp54 scientific plan")
    fix1_pairs = read_jsonl(superseded_fix1_root() / "frozen/pairs.jsonl")
    fix1_cells = read_jsonl(superseded_fix1_root() / "frozen/cells.jsonl")
    if pairs != fix1_pairs or cells != fix1_cells:
        raise ValueError("Fix3 changed the Fix1 frozen Exp54 scientific plan")
    fix2_pairs = read_jsonl(superseded_fix2_root() / "frozen/pairs.jsonl")
    fix2_cells = read_jsonl(superseded_fix2_root() / "frozen/cells.jsonl")
    if pairs != fix2_pairs or cells != fix2_cells:
        raise ValueError("Fix3 changed the Fix2 frozen Exp54 scientific plan")
    for target in targets:
        source_target = source / "frozen/targets" / f"{target['target_id']}.json"
        fix1_target = (
            superseded_fix1_root()
            / "frozen/targets"
            / f"{target['target_id']}.json"
        )
        fix2_target = (
            superseded_fix2_root()
            / "frozen/targets"
            / f"{target['target_id']}.json"
        )
        current_target = Path(target["path"])
        if not (
            source_target.is_file()
            and fix1_target.is_file()
            and fix2_target.is_file()
            and source_target.read_bytes() == current_target.read_bytes()
            and fix1_target.read_bytes() == current_target.read_bytes()
            and fix2_target.read_bytes() == current_target.read_bytes()
        ):
            raise ValueError("Fix3 changed a frozen Exp54 target")
    atomic_jsonl_dump(pairs, root / "frozen/pairs.jsonl")
    atomic_jsonl_dump(cells, root / "frozen/cells.jsonl")
    design = {
        "schema": FREEZE_SCHEMA,
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "execution_version": EXECUTION_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "study_role": (
            "small downstream microbenchmark; it does not establish global tactic "
            "interchangeability or general theorem-proving improvement"
        ),
        "source_exp49_archive": str(archive),
        "source_exp49_archive_sha256": SOURCE_EXP49_SHA256,
        "source_exp49_config_sha256": bytes_sha256(config_raw),
        "superseded_v1": superseded,
        "superseded_fix1": superseded_fix1,
        "superseded_fix2": superseded_fix2,
        "scientific_plan_exactly_carried_forward_from_v1": True,
        "scientific_plan_exactly_carried_forward_from_fix1": True,
        "scientific_plan_exactly_carried_forward_from_fix2": True,
        "source_view": "L0",
        "selection_rules": {
            "root_eligibility": (
                "single-goal evaluable Exp49 root with at least one noninitial "
                "nonterminal cross-head equal-strict-endpoint pair and one "
                "different-strict-endpoint pair"
            ),
            "portability_gate_max_member_bytes": SOURCE_EXP49_MEMBER_LIMIT_BYTES,
            "root_order": "archive member bytes ascending, then theorem_id",
            "pair_order": "strict endpoint hashes, then frozen candidate positions",
            "dedup_representative": "left branch in frozen candidate-position order",
            "downstream_outcomes_used_for_selection": False,
        },
        "repositories": list(REPOSITORIES),
        "roots_per_repository": ROOTS_PER_REPOSITORY,
        "roots": EXPECTED_ROOTS,
        "pairs": EXPECTED_PAIRS,
        "witness_pairs": EXPECTED_ROOTS,
        "control_pairs": EXPECTED_ROOTS,
        "probe_panel": list(PROBES),
        "probe_panel_sha256": json_sha256(PROBES),
        "full_cells": EXPECTED_FULL_CELLS,
        "dedup_cells": EXPECTED_DEDUP_CELLS,
        "cells": EXPECTED_CELLS,
        "shards": SHARD_COUNT,
        "lean_timeout_seconds": LEAN_TIMEOUT_SECONDS,
        "counterfactual_max_heartbeats": COUNTERFACTUAL_MAX_HEARTBEATS,
        "candidate_and_probe_heartbeat_budgets_isolated": True,
        "eligibility": eligibility,
        "exclusion_counts": dict(exclusion_counts),
        "targets": targets,
        "pairs_path": str(root / "frozen/pairs.jsonl"),
        "pairs_sha256": file_sha256(root / "frozen/pairs.jsonl"),
        "cells_path": str(root / "frozen/cells.jsonl"),
        "cells_sha256": file_sha256(root / "frozen/cells.jsonl"),
        "code_lock": code_lock(),
        "scientific_downstream_probes_executed_before_freeze": 0,
        "prior_failed_v1_scientific_cells_preserved": EXPECTED_CELLS,
        "prior_failed_fix1_scientific_cells_preserved": EXPECTED_CELLS,
        "prior_failed_fix2_scientific_cells_preserved": EXPECTED_CELLS,
    }
    design["freeze_receipt"] = {
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "execution_version": EXECUTION_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "repositories": len(REPOSITORIES),
        "roots": EXPECTED_ROOTS,
        "witness_pairs": EXPECTED_ROOTS,
        "control_pairs": EXPECTED_ROOTS,
        "full_cells": EXPECTED_FULL_CELLS,
        "dedup_cells": EXPECTED_DEDUP_CELLS,
        "planned_call_reduction": EXPECTED_FULL_CELLS - EXPECTED_DEDUP_CELLS,
        "planned_call_reduction_fraction": (
            (EXPECTED_FULL_CELLS - EXPECTED_DEDUP_CELLS) / EXPECTED_FULL_CELLS
        ),
        "scientific_plan_exactly_carried_forward_from_v1": True,
        "scientific_plan_exactly_carried_forward_from_fix1": True,
        "scientific_plan_exactly_carried_forward_from_fix2": True,
        "superseded_v1_cells_preserved": EXPECTED_CELLS,
        "superseded_fix1_cells_preserved": EXPECTED_CELLS,
        "superseded_fix2_cells_preserved": EXPECTED_CELLS,
        "fix3_scientific_downstream_probes_executed": 0,
        "scientific_downstream_probes_executed": 0,
        "next_step": "Run compile-only Exp54 preflight.",
    }
    seal(design)
    atomic_json_dump(design, design_path)
    print(json.dumps(design["freeze_receipt"], ensure_ascii=False, indent=2))
    return design["freeze_receipt"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--artifact-root", default=str(artifact_root()))
    p.add_argument("--source-archive", default=str(source_archive()))
    return p.parse_args()


if __name__ == "__main__":
    freeze(parse_args())
