"""Freeze four search policies over the immutable Exp54 root panel."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import zipfile
from pathlib import Path

from experiment57_protocol import *


def candidate_rows(target: dict[str, Any], exp49_row: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    executions = [
        row for row in exp49_row["worker"]["executions"]
        if row.get("source") == "alternative"
    ]
    if len(executions) != CANDIDATES_PER_ROOT:
        raise ValueError("Exp49 candidate panel no longer has 23 alternatives")
    for position, execution in enumerate(executions):
        record = {
            "branch_id": json_sha256({
                "target": target["target_id"], "candidate_position": position,
                "tactic": execution["tactic"],
            })[:24],
            "candidate_position_frozen": position,
            "tactic": execution["tactic"], "head": execution["head"],
            "family": execution["family"],
            "expected_executable": execution.get("executable") is True,
        }
        if record["expected_executable"]:
            record.update({
                "endpoints": execution["endpoints"],
                "goal_count": execution["goal_count"],
                "terminal": execution["terminal"],
            })
        rows.append(record)
    return rows


def choose(policy: str, branches: list[dict[str, Any]], root_id: str) -> list[dict[str, Any]]:
    if policy == "full":
        return branches
    if policy == "effect_aware":
        key = lambda row: row["endpoints"]["struct"]["sha256"]
    elif policy == "head_dedup":
        key = lambda row: row["head"]
    elif policy == "fixed_budget_random":
        effect_count = len(choose("effect_aware", branches, root_id))
        seed = int(json_sha256([RANDOM_SEED, root_id])[:16], 16)
        indices = sorted(random.Random(seed).sample(range(len(branches)), effect_count))
        return [branches[index] for index in indices]
    else:
        raise ValueError(policy)
    seen = set()
    selected = []
    for row in branches:
        identity = key(row)
        if identity not in seen:
            seen.add(identity)
            selected.append(row)
    return selected


def freeze(root: Path) -> dict[str, Any]:
    if not SOURCE_ARCHIVE.is_file() or file_sha256(SOURCE_ARCHIVE) != SOURCE_ARCHIVE_SHA256:
        raise ValueError("Exp54 source archive missing or SHA changed")
    if (not SOURCE_EXP49_ARCHIVE.is_file()
            or file_sha256(SOURCE_EXP49_ARCHIVE) != SOURCE_EXP49_ARCHIVE_SHA256):
        raise ValueError("Exp49 source archive missing or SHA changed")
    with zipfile.ZipFile(SOURCE_ARCHIVE) as archive:
        source_design_raw = archive.read("artifacts/frozen/design.json")
        source_design = json.loads(source_design_raw)
        target_names = sorted(
            name for name in archive.namelist()
            if name.startswith("artifacts/frozen/targets/") and name.endswith(".json")
        )
        targets = [json.loads(archive.read(name)) for name in target_names]
    exp49 = zipfile.ZipFile(SOURCE_EXP49_ARCHIVE)
    if len(targets) != EXPECTED_ROOTS:
        raise ValueError("Exp54 target count changed")
    probes = list(source_design["probe_panel"])
    jobs = []
    target_meta = []
    for target in targets:
        assert_sealed(target, f"Exp54 target {target['target_id']}")
        target_path = root / "frozen/targets" / f"{target['target_id']}.json"
        atomic_json_dump(target, target_path)
        target_meta.append({
            "target_id": target["target_id"], "root_id": target["theorem_id"],
            "slug": target["slug"], "path": str(target_path),
            "sha256": file_sha256(target_path),
        })
        source_raw = exp49.read(target["archive_member"])
        if (len(source_raw) != target["archive_member_bytes"]
                or hashlib.sha256(source_raw).hexdigest() != target["archive_member_sha256"]):
            raise ValueError("Exp49 theorem record differs from the Exp54 target lock")
        exp49_row = json.loads(source_raw)
        candidates = candidate_rows(target, exp49_row)
        executable = [row for row in candidates if row["expected_executable"]]
        for policy in POLICIES:
            selected = choose(policy, executable, target["theorem_id"])
            job = {
                "job_id": json_sha256([target["target_id"], policy])[:24],
                "target_id": target["target_id"], "root_id": target["theorem_id"],
                "slug": target["slug"], "policy": policy,
                "candidate_panel": candidates,
                "candidate_order": [row["branch_id"] for row in candidates],
                "executable_candidate_order": [row["branch_id"] for row in executable],
                "selected_branches": selected,
                "selected_branch_ids": [row["branch_id"] for row in selected],
                "probe_order": probes,
                "max_process_calls": CANDIDATES_PER_ROOT + len(selected) * len(probes),
                "time_budget_seconds": ROOT_POLICY_TIME_BUDGET_SECONDS,
                "selection_uses_downstream_outcomes": False,
            }
            job["job_identity_sha256"] = json_sha256(job)
            jobs.append(job)
    exp49.close()
    jobs.sort(key=lambda row: (row["root_id"], POLICIES.index(row["policy"])))
    jobs_path = root / "frozen/jobs.jsonl"
    atomic_jsonl_dump(jobs, jobs_path)
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "implementation_locks": [
            {"path": path.name, "sha256": file_sha256(path), "bytes": path.stat().st_size}
            for path in sorted(PACKAGE_ROOT.glob("*.py"), key=lambda item: item.name)
        ],
        "source_exp54_archive": str(SOURCE_ARCHIVE),
        "source_exp54_archive_sha256": SOURCE_ARCHIVE_SHA256,
        "source_exp49_archive": str(SOURCE_EXP49_ARCHIVE),
        "source_exp49_archive_sha256": SOURCE_EXP49_ARCHIVE_SHA256,
        "source_exp54_design_sha256": hashlib.sha256(source_design_raw).hexdigest(),
        "roots": len(targets), "policies": list(POLICIES), "jobs": len(jobs),
        "targets": target_meta, "jobs_path": str(jobs_path),
        "jobs_sha256": file_sha256(jobs_path), "probe_order": probes,
        "candidate_order": "the complete Exp49 frozen 23-candidate order",
        "candidate_stage": (
            "all four policies independently execute all 23 candidates before "
            "applying the registered depth-two branch selector"
        ),
        "planned_candidate_process_calls": EXPECTED_JOBS * CANDIDATES_PER_ROOT,
        "planned_max_process_calls_by_policy": {
            policy: sum(job["max_process_calls"] for job in jobs if job["policy"] == policy)
            for policy in POLICIES
        },
        "planned_max_process_calls_total": sum(job["max_process_calls"] for job in jobs),
        "common_root_policy_time_budget_seconds": ROOT_POLICY_TIME_BUDGET_SECONDS,
        "cell_timeout_seconds": CELL_TIMEOUT_SECONDS,
        "stopping_rule": "stop at first terminal strict endpoint or common root-policy time budget",
        "primary_efficiency_metrics": ["Lean process calls", "expanded nodes"],
        "secondary_efficiency_metrics": ["wall-clock", "time-to-first-proof"],
        "coverage_metrics": ["solved roots", "unique canonical endpoints", "coverage loss versus full"],
        "wall_clock_role": "descriptive secondary outcome; one registered run without retry",
        "scientific_search_cells_executed_before_freeze": 0,
        "manual_replacement_count": 0,
        "next_step": "Run compile-only worker preflight, then sixteen root shards.",
    })
    atomic_json_dump(value, root / "frozen/design.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(freeze(Path(parse_args().artifact_root).resolve()), indent=2))
