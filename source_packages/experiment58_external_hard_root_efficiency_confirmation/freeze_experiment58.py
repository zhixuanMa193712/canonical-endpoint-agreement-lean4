"""Freeze external sources, panels, estimands, partitions, and fail-closed gates."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from experiment58_protocol import *


def load_locked_panels() -> tuple[list[str], list[str], dict[str, str]]:
    if not SOURCE_EXP57_ARCHIVE.is_file() or file_sha256(SOURCE_EXP57_ARCHIVE) != SOURCE_EXP57_ARCHIVE_SHA256:
        raise ValueError("Exp57 source archive missing or SHA changed")
    with zipfile.ZipFile(SOURCE_EXP57_ARCHIVE) as archive:
        design_raw = archive.read(EXP57_FROZEN_DESIGN_MEMBER)
        jobs_raw = archive.read(EXP57_FROZEN_JOBS_MEMBER)
    design = json.loads(design_raw)
    jobs = [json.loads(line) for line in jobs_raw.decode("utf-8").splitlines() if line.strip()]
    orders = {tuple(row["tactic"] for row in job["candidate_panel"]) for job in jobs}
    if orders != {CANDIDATE_PANEL}:
        raise ValueError("Exp57 candidate order differs from the registered 23-candidate panel")
    probes = list(design["probe_order"])
    if tuple(probes) != PROBE_PANEL:
        raise ValueError("Exp57 probe order differs from the registered eight-probe panel")
    return list(CANDIDATE_PANEL), probes, {
        "design_member_sha256": hashlib.sha256(design_raw).hexdigest(),
        "jobs_member_sha256": hashlib.sha256(jobs_raw).hexdigest(),
    }


def freeze(root: Path) -> dict[str, Any]:
    candidates, probes, member_hashes = load_locked_panels()
    vendor = validate_vendor()
    previous_lineage = None
    previous_protocol_path = root / "frozen/protocol.json"
    failed_environment_path = root / "preflight/benchmark_environment.json"
    if previous_protocol_path.is_file():
        previous_protocol_sha = file_sha256(previous_protocol_path)
        previous_protocol = read_json(previous_protocol_path)
        assert_sealed(previous_protocol, "superseded Exp58 protocol")
        if previous_protocol.get("mechanical_fix_id") != "exp58-pre-continuation-candidate-only-freeze-v1":
            raise ValueError("existing Exp58 protocol is not the protected pre-Fix1 freeze")
        if not failed_environment_path.is_file():
            raise FileNotFoundError("Fix1 requires the preserved failed build receipt")
        failed_environment_sha = file_sha256(failed_environment_path)
        failed_environment = read_json(failed_environment_path)
        assert_sealed(failed_environment, "failed build environment")
        failures = [row.get("build", {}) for row in failed_environment.get("datasets", [])]
        if not (
            failed_environment.get("environment_gate") is False
            and failed_environment.get("candidate_only_tactics_executed") == 0
            and failed_environment.get("continuation_probes_executed") == 0
            and len(failures) == len(DATASETS)
            and all(item.get("requested") is True and item.get("returncode") == 1
                    and "unknown short option '-j'" in str(item.get("stderr_tail", ""))
                    for item in failures)
        ):
            raise ValueError("existing environment receipt is not the protected Lake -j compatibility failure")
        archived_protocol = root / "frozen/superseded_protocol_build_cli_fix0.json"
        archived_environment = root / "preflight/superseded_environment_build_cli_fix0.json"
        atomic_json_dump(previous_protocol, archived_protocol)
        atomic_json_dump(failed_environment, archived_environment)
        previous_lineage = {
            "superseded_protocol": str(archived_protocol),
            "superseded_protocol_original_file_sha256": previous_protocol_sha,
            "superseded_protocol_record_sha256": previous_protocol["record_sha256"],
            "failed_environment": str(archived_environment),
            "failed_environment_original_file_sha256": failed_environment_sha,
            "failed_environment_record_sha256": failed_environment["record_sha256"],
            "failure_signature": "lake build -j <jobs>: unknown short option '-j'",
            "scientific_execution_before_fix1": False,
        }
    implementation = []
    for path in sorted(PACKAGE_ROOT.glob("*.py"), key=lambda item: item.name):
        implementation.append({"path": path.name, "sha256": file_sha256(path), "bytes": path.stat().st_size})
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "mechanical_fix_lineage": previous_lineage,
        "candidate_screening_execution_root": str(CANDIDATE_SCREENING_EXECUTION_ROOT),
        "purpose": "prospective external hard-root confirmation of actual depth-two call savings",
        "implementation_locks": implementation,
        "vendor_locks": vendor,
        "source_exp57_archive": str(SOURCE_EXP57_ARCHIVE),
        "source_exp57_archive_sha256": SOURCE_EXP57_ARCHIVE_SHA256,
        "source_exp57_members": member_hashes,
        "datasets": DATASETS,
        "target_toolchain": TARGET_TOOLCHAIN,
        "candidate_panel": candidates,
        "candidate_panel_sha256": json_sha256(candidates),
        "probe_panel": probes,
        "probe_panel_sha256": json_sha256(probes),
        "policies": list(POLICIES),
        "source_frame": {
            "pilot_per_dataset": PILOT_FRAME_PER_DATASET,
            "confirmation_per_dataset": CONFIRMATION_FRAME_PER_DATASET,
            "screening_roots_total": SCREENING_ROOTS_TOTAL,
            "minif2f_partition": "official Valid for pilot and Test for confirmation",
            "putnambench_partition": "sha256(PARTITION_SEED, source identity) modulo 4; bucket 0 pilot",
            "within_partition_order": "sha256(FRAME_SEED, dataset, role, source identity)",
            "manual_replacement": False,
        },
        "candidate_only_eligibility": {
            "exact_commit_toolchain_source_and_worker_hashes": True,
            "unmodified_lake_build_required": True,
            "all_23_candidates_accounted": True,
            "terminal_candidate_count": 0,
            "minimum_executable_nonterminal_candidates": MIN_EXECUTABLE_NONTERMINAL,
            "minimum_strict_endpoint_class_size": MIN_EFFECT_CLASS_SIZE,
            "continuation_probe_count": 0,
        },
        "pilot": {
            "selection": f"first {PILOT_ROOTS_PER_DATASET} eligible roots per dataset by frozen key",
            "independent_unit": "root/problem",
            "paired_unit": "four policies evaluated within each root",
            "used_only_for": "sample-size planning and engineering feasibility, never confirmation estimates",
        },
        "registered_estimands": {
            "primary_efficiency": "paired full-minus-effect-aware Lean process calls per root",
            "secondary_efficiency": ["paired expanded-node difference", "time-to-first-proof", "wall-clock"],
            "coverage_noninferiority": {
                "event": "full solves and effect-aware does not solve within the identical budget",
                "one_sided_margin": COVERAGE_NONINFERIORITY_MARGIN,
            },
            "coverage_and_efficiency_are_separate": True,
        },
        "power_rule": {
            "candidate_total_n_grid": list(CONFIRMATION_TOTAL_N_GRID),
            "balanced_by_dataset": True,
            "replicates": POWER_REPLICATES,
            "seed": POWER_SEED,
            "efficiency_power_target": POWER_TARGET,
            "coverage_noninferiority_power_target": POWER_TARGET,
            "no_final_n_before_pilot": True,
        },
        "public_release_policy": {
            "minif2f": DATASETS["minif2f"]["public_result_policy"],
            "putnambench": DATASETS["putnambench"]["public_result_policy"],
            "putnambench_successful_proof_mapping_export_gate": False,
        },
        "candidate_only_tactics_executed_before_freeze": 0,
        "continuation_probes_executed_before_freeze": 0,
        "scientific_search_cells_executed_before_freeze": 0,
        "next_step": "Prepare exact benchmark checkouts and run compile-only worker preflight.",
    })
    atomic_json_dump(value, root / "frozen/protocol.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(freeze(Path(parse_args().artifact_root).resolve()), indent=2))
