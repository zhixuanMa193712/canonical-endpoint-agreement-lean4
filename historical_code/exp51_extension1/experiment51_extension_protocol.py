"""Frozen protocol primitives for the first Exp51 repository-frame extension."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parent
SERVER_ROOT = Path(os.environ.get("MZX_ROOT", PACKAGE_ROOT.parent)).resolve()
BASE_PACKAGE_ROOT = SERVER_ROOT / "experiment51_external_repository_replication"
if str(BASE_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(BASE_PACKAGE_ROOT))

import experiment51_protocol as base  # noqa: E402

EXTENSION_VERSION = "experiment51-zero-candidate-frame-extension1-v1"
MECHANICAL_FIX_ID = "exp51-extension1-offline-dependency-enumeration-v1"
PROTOCOL_VERSION = base.PROTOCOL_VERSION
TARGET_TOOLCHAIN = base.TARGET_TOOLCHAIN
TARGET_LEAN_VERSION = base.TARGET_LEAN_VERSION
TARGET_REPOSITORIES = base.TARGET_REPOSITORIES
MIN_REPOSITORIES = base.MIN_REPOSITORIES
ROOTS_PER_REPOSITORY = base.ROOTS_PER_REPOSITORY
SOURCE_OVERLAP_THRESHOLD = 0.20

ARTIFACT_ROOT = SERVER_ROOT / "artifacts/v51/external_repository_replication_extension1"
CHECKOUT_ROOT = SERVER_ROOT / "external_repos/experiment51_extension1"
BASE_ARTIFACT_ROOT = SERVER_ROOT / "artifacts/v51/external_repository_replication"
NO_GO_BUNDLE = (
    SERVER_ROOT / "exports/experiment51_recruitment_nogo_fix9_fix3_results.zip"
)
NO_GO_BUNDLE_SHA256 = "5f3ef5ee40609015d20954e6e34fdfd6c53f30263545dcbcfc9ebe0bddf9b683"
NO_GO_EXPORT_SCHEMA = "experiment51-zero-candidate-recruitment-nogo-export-v1"

RESERVOIR_MANIFEST_URL = "https://reservoir.lean-lang.org/index/manifest.json"
RESERVOIR_MANIFEST_SHA256 = "6fc63f1fe2d35902ae10d66683af2cdd5bad998a832f4b8f7f23eca0604451b0"
RESERVOIR_MANIFEST_BYTES = 68_834_667
RESERVOIR_EXACT_V427_PACKAGE_COUNT = 79

CANDIDATE_FRAME = PACKAGE_ROOT / "repository_extension_candidates.json"
CARRY_FORWARD_SLUGS = (
    "PatrickMassot/GlimpseOfLean",
    "AfonsoBitoque/LeanServer",
    "dissensus-ai/lean-formalizations",
    "leanprover-community/batteries",
    "bergmannjg/Regex",
    "Verified-zkEVM/VCVio",
    "leanprover-community/lean-auto",
)
OFFLINE_CONTROL_SLUGS = (
    "PatrickMassot/GlimpseOfLean",
    "AfonsoBitoque/LeanServer",
)

REPOSITORY_WORKERS = 16
BUILD_SLOTS = 8
TRACE_SLOTS = 16
ENUMERATION_SLOTS = 8
THREADS_PER_TRACE = 2
GIT_TIMEOUT = 1800
BUILD_TIMEOUT = 7200
TRACE_TIMEOUT = 14400
ENUMERATION_TIMEOUT = 7200
REPLAY_TIMEOUT = 900
REQUIRED_CPUS = 32
REQUIRED_MEMORY_TOTAL_GB = 256
REQUIRED_MEMORY_AVAILABLE_GB = 192
REQUIRED_DISK_FREE_GB = 250

read_json = base.read_json
read_jsonl = lambda path: [
    json.loads(line)
    for line in Path(path).read_text(encoding="utf-8").splitlines()
    if line.strip()
]
atomic_json_dump = base.atomic_json_dump
atomic_jsonl_dump = base.atomic_jsonl_dump
exclusive_create_json = base.exclusive_create_json
file_sha256 = base.file_sha256
json_sha256 = base.json_sha256
code_lock = base.code_lock
validate_code_lock = base.validate_code_lock
safe_slug = base.safe_slug


def locked_sources() -> list[Path]:
    extension = sorted(PACKAGE_ROOT.glob("*.py"))
    extension += [CANDIDATE_FRAME, PACKAGE_ROOT / "README_SERVER.md"]
    inherited = [
        BASE_PACKAGE_ROOT / "experiment51_protocol.py",
        BASE_PACKAGE_ROOT / "experiment51_trace_runtime.py",
        BASE_PACKAGE_ROOT / "screen_experiment51_repositories.py",
        BASE_PACKAGE_ROOT / "experiment51_live_worker.py",
    ]
    return extension + inherited


def validate_nogo_bundle() -> dict[str, Any]:
    if not NO_GO_BUNDLE.is_file():
        raise FileNotFoundError(NO_GO_BUNDLE)
    if file_sha256(NO_GO_BUNDLE) != NO_GO_BUNDLE_SHA256:
        raise ValueError("Exp51 recruitment No-Go bundle changed")
    with zipfile.ZipFile(NO_GO_BUNDLE) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"No-Go bundle member failed CRC: {bad}")
        manifest = json.loads(archive.read("MANIFEST.json"))
        decision = json.loads(
            archive.read("artifacts/recruitment_nogo/summary.json")
        )
    if not (
        manifest.get("export_schema") == NO_GO_EXPORT_SCHEMA
        and manifest.get("decision_label") == "recruitment_no_go"
        and manifest.get("scientific_result") is False
        and manifest.get("scientific_candidate_tactics_executed") == 0
        and decision.get("repositories_passed") == 7
        and decision.get("minimum_required") == MIN_REPOSITORIES
        and decision.get("current_frame_upper_bound") == 9
        and decision.get("current_frame_can_reach_minimum") is False
        and decision.get("scientific_candidate_tactics_executed") == 0
    ):
        raise ValueError("wrong Exp51 recruitment No-Go decision")
    return {
        "bundle": str(NO_GO_BUNDLE),
        "bundle_sha256": NO_GO_BUNDLE_SHA256,
        "manifest_entries": len(manifest.get("entries", [])),
        "decision_sha256": manifest.get("decision_sha256"),
        "repositories_passed": 7,
        "current_frame_upper_bound": 9,
        "scientific_candidate_tactics_executed": 0,
    }


def validate_base_carry_forward() -> list[dict[str, Any]]:
    configp = BASE_ARTIFACT_ROOT / "recruitment_frozen/recruitment_config.json"
    recoveryp = BASE_ARTIFACT_ROOT / "screening/build_trace_summary.json"
    config = read_json(configp)
    recovery = read_json(recoveryp)
    if not (
        recovery.get("phase") == "recover-enumeration"
        and recovery.get("passed") == 7
        and recovery.get("recovery_gate") is False
        and recovery.get("trace_executed") is False
        and recovery.get("scientific_candidate_tactics_executed") == 0
    ):
        raise ValueError("active Exp51 base recruitment no longer matches the No-Go")
    rows = []
    with zipfile.ZipFile(NO_GO_BUNDLE) as archive:
        names = set(archive.namelist())
        archived_config_bytes = archive.read(
            "artifacts/recruitment_frozen/recruitment_config.json"
        )
        archived_recovery_bytes = archive.read(
            "artifacts/screening/build_trace_summary.json"
        )
        if not (
            hashlib.sha256(configp.read_bytes()).hexdigest()
            == hashlib.sha256(archived_config_bytes).hexdigest()
            and hashlib.sha256(recoveryp.read_bytes()).hexdigest()
            == hashlib.sha256(archived_recovery_bytes).hexdigest()
            and config == json.loads(archived_config_bytes)
            and recovery == json.loads(archived_recovery_bytes)
        ):
            raise ValueError("active base recruitment control differs from No-Go archive")
        locked = list(config.get("code_lock", {}).get("files", []))
        if json_sha256(locked) != config.get("code_lock", {}).get("bundle_sha256"):
            raise ValueError("archived base code-lock metadata changed")
        locked_names = [Path(row["path"]).name for row in locked]
        if len(set(locked_names)) != len(locked_names):
            raise ValueError("archived base code lock has ambiguous basenames")
        for entry, name in zip(locked, locked_names):
            active = BASE_PACKAGE_ROOT / name
            if not (
                active.is_file()
                and active.stat().st_size == int(entry["bytes"])
                and file_sha256(active) == entry["sha256"]
            ):
                raise ValueError(f"archived Exp51 base source changed: {active}")
        for slug in CARRY_FORWARD_SLUGS:
            safe = safe_slug(slug)
            receiptp = BASE_ARTIFACT_ROOT / "screening/build_trace" / f"{safe}.json"
            framep = BASE_ARTIFACT_ROOT / "screening/frames" / f"{safe}.jsonl"
            inventoryp = BASE_ARTIFACT_ROOT / "screening/source_inventories" / f"{safe}.jsonl"
            archive_members = {
                "receipt": f"artifacts/screening/build_trace/{safe}.json",
                "frame": f"artifacts/screening/frames/{safe}.jsonl",
                "source_inventory": f"artifacts/screening/source_inventories/{safe}.jsonl",
            }
            if any(member not in names for member in archive_members.values()):
                raise ValueError(f"No-Go archive omitted carry-forward evidence: {slug}")
            active_paths = {
                "receipt": receiptp,
                "frame": framep,
                "source_inventory": inventoryp,
            }
            archive_hashes = {
                key: hashlib.sha256(archive.read(member)).hexdigest()
                for key, member in archive_members.items()
            }
            if any(
                not path.is_file() or file_sha256(path) != archive_hashes[key]
                for key, path in active_paths.items()
            ):
                raise ValueError(f"active carry-forward evidence differs from No-Go archive: {slug}")
            receipt = read_json(receiptp)
            frame = read_jsonl(framep)
            if not (
                receipt.get("candidate", {}).get("slug") == slug
                and receipt.get("build_trace_gate") is True
                and receipt.get("scientific_candidate_tactics_executed") == 0
                and receipt.get("enumeration", {}).get("pre_replay_frame") == len(frame)
                and len(frame) >= ROOTS_PER_REPOSITORY
            ):
                raise ValueError(f"invalid Exp51 carry-forward repository: {slug}")
            rows.append({
                "slug": slug,
                "candidate": receipt["candidate"],
                "commit": receipt["commit"],
                "receipt": str(receiptp),
                "receipt_sha256": archive_hashes["receipt"],
                "frame": str(framep),
                "frame_sha256": archive_hashes["frame"],
                "pre_replay_frame": len(frame),
                "source_inventory": str(inventoryp),
                "source_inventory_sha256": archive_hashes["source_inventory"],
                "archive_members": archive_members,
                "archive_evidence_exact": True,
                "scientific_candidate_tactics_executed": 0,
            })
    return rows


def validate_candidate_frame() -> dict[str, Any]:
    frame = read_json(CANDIDATE_FRAME)
    candidates = list(frame.get("candidates", []))
    slugs = [row.get("slug") for row in candidates]
    if frame.get("extension_version") != EXTENSION_VERSION or len(candidates) != 28:
        raise ValueError("wrong Exp51 extension candidate frame")
    if any(not slug for slug in slugs) or len({str(x).casefold() for x in slugs}) != len(slugs):
        raise ValueError("extension candidates are missing or duplicated")
    old = read_json(BASE_PACKAGE_ROOT / "repository_candidates.json")
    prohibited = {
        str(row["slug"]).casefold() for row in old["candidates"]
    } | {str(slug).casefold() for slug in old["historical_scientific_exclusions"]}
    if prohibited.intersection(str(slug).casefold() for slug in slugs):
        raise ValueError("extension reuses a prior candidate or scientific repository")
    for index, row in enumerate(candidates, 1):
        if row.get("order") != index:
            raise ValueError("extension candidate order changed")
        if not all(row.get(key) for key in (
            "slug", "url", "ref", "domain", "license", "reservoir_package",
            "reservoir_version_date",
        )):
            raise ValueError(f"incomplete extension candidate: {row}")
        ref = str(row["ref"])
        if len(ref) != 40 or any(ch not in "0123456789abcdef" for ch in ref):
            raise ValueError(f"candidate ref is not a full commit: {row['slug']}")
        if row.get("target_toolchain") != TARGET_TOOLCHAIN:
            raise ValueError(f"candidate toolchain changed: {row['slug']}")
    return frame
