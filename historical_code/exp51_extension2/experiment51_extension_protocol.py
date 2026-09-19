"""Frozen protocol primitives for the second Exp51 repository-frame extension."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parent
SERVER_ROOT = Path(os.environ.get("MZX_ROOT", PACKAGE_ROOT.parent)).resolve()
WORKSPACE_ROOT = PACKAGE_ROOT.parent
for import_root in (WORKSPACE_ROOT, SERVER_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

PRIOR_PACKAGE_ROOT = SERVER_ROOT / "experiment51_repository_frame_extension"
BASE_PACKAGE_ROOT = SERVER_ROOT / "experiment51_external_repository_replication"

from experiment51_repository_frame_extension import (  # noqa: E402
    experiment51_extension_protocol as prior,
)

base = prior.base
EXTENSION_VERSION = "experiment51-zero-candidate-frame-extension2-v1"
MECHANICAL_FIX_ID = (
    "exp51-extension2-public-github-discovery-frame-fix1-screen-wrapper-export"
)
PROTOCOL_VERSION = base.PROTOCOL_VERSION
TARGET_TOOLCHAIN = base.TARGET_TOOLCHAIN
TARGET_LEAN_VERSION = base.TARGET_LEAN_VERSION
TARGET_REPOSITORIES = base.TARGET_REPOSITORIES
MIN_REPOSITORIES = base.MIN_REPOSITORIES
ROOTS_PER_REPOSITORY = base.ROOTS_PER_REPOSITORY
SOURCE_OVERLAP_THRESHOLD = 0.20

ARTIFACT_ROOT = SERVER_ROOT / "artifacts/v51/external_repository_replication_extension2"
CHECKOUT_ROOT = SERVER_ROOT / "external_repos/experiment51_extension2"
EXTENSION1_ARTIFACT_ROOT = (
    SERVER_ROOT / "artifacts/v51/external_repository_replication_extension1"
)
_export_bundle = (
    SERVER_ROOT / "exports/experiment51_repository_frame_extension1_nogo_results.zip"
)
_root_bundle = SERVER_ROOT / "experiment51_repository_frame_extension1_nogo_results.zip"
EXTENSION1_NOGO_BUNDLE = _export_bundle if _export_bundle.is_file() else _root_bundle
EXTENSION1_NOGO_BUNDLE_SHA256 = (
    "94101bccc3be5d7edff48b91824494a228f9a21fce2580f1353594eeab420473"
)
EXTENSION1_NOGO_BUNDLE_BYTES = 1_349_401
EXTENSION1_NOGO_EXPORT_SCHEMA = (
    "experiment51-extension1-zero-candidate-build-trace-nogo-export-v1"
)
EXTENSION1_NOGO_EXPORT_FIX_ID = (
    "exp51-extension1-nogo-export-fix1-predependency-failure-accounting"
)
EXTENSION1_DECISION_SHA256 = (
    "5dda73ea0acde9f0ee2c9d52c5e721d1af93519bb28505fcca59236e9847039f"
)

CANDIDATE_FRAME = PACKAGE_ROOT / "repository_extension_candidates.json"
CARRY_FORWARD_SLUGS = (
    "PatrickMassot/GlimpseOfLean",
    "AfonsoBitoque/LeanServer",
    "dissensus-ai/lean-formalizations",
    "leanprover-community/batteries",
    "bergmannjg/Regex",
    "Verified-zkEVM/VCVio",
    "leanprover-community/lean-auto",
    "YaelDillies/misc-yd",
    "MichaelStollBayreuth/LegendreQF",
    "verse-lab/Lentil",
    "AmosNico/validator",
)
OFFLINE_CONTROL_SLUGS = (
    "PatrickMassot/GlimpseOfLean",
    "AfonsoBitoque/LeanServer",
)

# Reduced from Extension1 because only seven new checkouts are scheduled and the
# server had 241 GB free after evidence-preserving cleanup.
REPOSITORY_WORKERS = 7
BUILD_SLOTS = 4
TRACE_SLOTS = 7
ENUMERATION_SLOTS = 4
THREADS_PER_TRACE = 2
GIT_TIMEOUT = 1800
BUILD_TIMEOUT = 7200
TRACE_TIMEOUT = 14400
ENUMERATION_TIMEOUT = 7200
REPLAY_TIMEOUT = 900
REQUIRED_CPUS = 16
REQUIRED_MEMORY_TOTAL_GB = 256
REQUIRED_MEMORY_AVAILABLE_GB = 192
REQUIRED_DISK_FREE_GB = 180

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
    extension2 = sorted(PACKAGE_ROOT.glob("*.py"))
    extension2 += [CANDIDATE_FRAME, PACKAGE_ROOT / "README_SERVER.md"]
    inherited_extension1 = [
        PRIOR_PACKAGE_ROOT / name
        for name in (
            "experiment51_extension_protocol.py",
            "freeze_experiment51_extension.py",
            "preflight_experiment51_extension.py",
            "screen_experiment51_extension.py",
            "experiment51_extension_enumeration_worker.py",
        )
    ]
    inherited_base = [
        BASE_PACKAGE_ROOT / "experiment51_protocol.py",
        BASE_PACKAGE_ROOT / "experiment51_trace_runtime.py",
        BASE_PACKAGE_ROOT / "screen_experiment51_repositories.py",
        BASE_PACKAGE_ROOT / "experiment51_live_worker.py",
    ]
    return extension2 + inherited_extension1 + inherited_base


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def validate_nogo_bundle() -> dict[str, Any]:
    """Validate every Extension1 No-Go member before it is used."""
    bundle = EXTENSION1_NOGO_BUNDLE
    if not bundle.is_file():
        raise FileNotFoundError(bundle)
    if bundle.stat().st_size != EXTENSION1_NOGO_BUNDLE_BYTES:
        raise ValueError("Extension1 No-Go bundle byte count changed")
    if file_sha256(bundle) != EXTENSION1_NOGO_BUNDLE_SHA256:
        raise ValueError("Extension1 No-Go bundle changed")
    with zipfile.ZipFile(bundle) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"Extension1 No-Go member failed CRC: {bad}")
        manifest = json.loads(archive.read("MANIFEST.json"))
        decision = json.loads(archive.read("artifacts/extension1_nogo/summary.json"))
        entries = list(manifest.get("entries", []))
        if len(entries) != 170:
            raise ValueError("Extension1 No-Go manifest entry count changed")
        for entry in entries:
            raw = archive.read(entry["path"])
            if not (
                len(raw) == int(entry["bytes"])
                and _sha256_bytes(raw) == entry["sha256"]
            ):
                raise ValueError(f"Extension1 No-Go manifest mismatch: {entry['path']}")
        if not (
            manifest.get("export_schema") == EXTENSION1_NOGO_EXPORT_SCHEMA
            and manifest.get("export_fix_id") == EXTENSION1_NOGO_EXPORT_FIX_ID
            and manifest.get("decision_label") == "repository_frame_extension1_no_go"
            and manifest.get("scientific_result") is False
            and manifest.get("scientific_candidate_tactics_executed") == 0
            and manifest.get("decision_sha256") == EXTENSION1_DECISION_SHA256
            and decision.get("decision_label") == "repository_frame_extension1_no_go"
            and decision.get("combined_build_trace_passes") == 11
            and decision.get("minimum_required") == MIN_REPOSITORIES
            and decision.get("current_frame_upper_bound") == 11
            and decision.get("current_frame_can_reach_minimum") is False
            and decision.get("authored_replay_executed") is False
            and decision.get("scientific_candidate_tactics_executed") == 0
        ):
            raise ValueError("wrong Extension1 No-Go decision")
        # Extension2 reuses these implementations.  Require the active copies to
        # be byte-identical to the code protected by the Extension1 export.
        for active in locked_sources():
            if active.parent not in (PRIOR_PACKAGE_ROOT, BASE_PACKAGE_ROOT):
                continue
            relative = active.relative_to(SERVER_ROOT).as_posix()
            member = f"locked_code/{relative}"
            if member not in archive.namelist():
                raise ValueError(f"Extension1 archive omitted inherited code: {relative}")
            if not active.is_file() or file_sha256(active) != _sha256_bytes(archive.read(member)):
                raise ValueError(f"active inherited source differs from Extension1 archive: {active}")
    return {
        "bundle": str(bundle),
        "bundle_sha256": EXTENSION1_NOGO_BUNDLE_SHA256,
        "bundle_bytes": EXTENSION1_NOGO_BUNDLE_BYTES,
        "manifest_entries": 170,
        "decision_sha256": EXTENSION1_DECISION_SHA256,
        "repositories_passed": 11,
        "minimum_required": MIN_REPOSITORIES,
        "current_frame_upper_bound": 11,
        "scientific_candidate_tactics_executed": 0,
    }


def validate_base_carry_forward() -> list[dict[str, Any]]:
    validate_nogo_bundle()
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(EXTENSION1_NOGO_BUNDLE) as archive:
        names = set(archive.namelist())
        for slug in CARRY_FORWARD_SLUGS:
            safe = safe_slug(slug)
            members = {
                "receipt": f"artifacts/screening/build_trace/{safe}.json",
                "frame": f"artifacts/screening/frames/{safe}.jsonl",
                "source_inventory": f"artifacts/screening/source_inventories/{safe}.jsonl",
            }
            if any(member not in names for member in members.values()):
                raise ValueError(f"Extension1 archive omitted carry evidence: {slug}")
            raw = {key: archive.read(member) for key, member in members.items()}
            receipt = json.loads(raw["receipt"])
            frame = [json.loads(line) for line in raw["frame"].splitlines() if line.strip()]
            inventory = [
                json.loads(line)
                for line in raw["source_inventory"].splitlines()
                if line.strip()
            ]
            if not (
                receipt.get("candidate", {}).get("slug") == slug
                and receipt.get("build_trace_gate") is True
                and receipt.get("scientific_candidate_tactics_executed") == 0
                and receipt.get("enumeration", {}).get("pre_replay_frame") == len(frame)
                and len(frame) >= ROOTS_PER_REPOSITORY
                and inventory
            ):
                raise ValueError(f"invalid Extension1 carry repository: {slug}")
            rows.append({
                "slug": slug,
                "candidate": receipt["candidate"],
                "commit": receipt["commit"],
                "git_root": receipt["git_root"],
                "project": receipt["project"],
                "pre_replay_frame": len(frame),
                "archive_members": members,
                "receipt_sha256": _sha256_bytes(raw["receipt"]),
                "frame_sha256": _sha256_bytes(raw["frame"]),
                "source_inventory_sha256": _sha256_bytes(raw["source_inventory"]),
                "archive_evidence_exact": True,
                "scientific_candidate_tactics_executed": 0,
            })
    return rows


def validate_active_carry_checkouts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recheck the eleven preserved checkouts without executing Lean."""
    from experiment51_external_repository_replication import (  # noqa: E402
        screen_experiment51_repositories as base_screen,
    )

    checked = []
    with zipfile.ZipFile(EXTENSION1_NOGO_BUNDLE) as archive:
        for row in rows:
            git_root = Path(row["git_root"]).resolve()
            project = Path(row["project"]).resolve()
            if not git_root.is_dir() or not project.is_dir():
                raise FileNotFoundError(f"preserved carry checkout is absent: {row['slug']}")
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=git_root, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300,
            )
            status = subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=git_root, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=300,
            )
            toolchain = (project / "lean-toolchain").read_text(encoding="utf-8").strip()
            inventory, _ = base_screen.source_inventory(project)
            expected = [
                json.loads(line)
                for line in archive.read(row["archive_members"]["source_inventory"]).splitlines()
                if line.strip()
            ]
            gate = bool(
                commit.returncode == 0
                and commit.stdout.strip() == row["commit"]
                and status.returncode == 0
                and not status.stdout.strip()
                and toolchain == TARGET_TOOLCHAIN
                and inventory == expected
            )
            if not gate:
                raise ValueError(f"preserved carry checkout changed: {row['slug']}")
            checked.append({
                "slug": row["slug"],
                "commit_exact": True,
                "tracked_checkout_clean": True,
                "toolchain_exact": True,
                "source_inventory_exact": True,
                "checkout_gate": True,
            })
    return checked


def validate_candidate_frame() -> dict[str, Any]:
    frame = read_json(CANDIDATE_FRAME)
    candidates = list(frame.get("candidates", []))
    slugs = [str(row.get("slug", "")) for row in candidates]
    if frame.get("extension_version") != EXTENSION_VERSION or len(candidates) != 7:
        raise ValueError("wrong Extension2 candidate frame")
    if slugs != sorted(slugs, key=str.casefold):
        raise ValueError("Extension2 candidate order is not the frozen slug order")
    if any(not slug for slug in slugs) or len({slug.casefold() for slug in slugs}) != len(slugs):
        raise ValueError("Extension2 candidates are missing or duplicated")
    original = read_json(BASE_PACKAGE_ROOT / "repository_candidates.json")
    extension1 = read_json(PRIOR_PACKAGE_ROOT / "repository_extension_candidates.json")
    prohibited = {
        str(row["slug"]).casefold() for row in original["candidates"]
    } | {
        str(slug).casefold() for slug in original["historical_scientific_exclusions"]
    } | {
        str(row["slug"]).casefold() for row in extension1["candidates"]
    }
    if prohibited.intersection(slug.casefold() for slug in slugs):
        raise ValueError("Extension2 reuses an earlier repository")
    for index, row in enumerate(candidates, 1):
        if row.get("order") != index:
            raise ValueError("Extension2 candidate order changed")
        if not all(row.get(key) for key in (
            "slug", "url", "ref", "subdir", "domain", "license",
            "license_evidence", "toolchain_evidence",
        )):
            raise ValueError(f"incomplete Extension2 candidate: {row}")
        ref = str(row["ref"])
        if len(ref) != 40 or any(ch not in "0123456789abcdef" for ch in ref):
            raise ValueError(f"candidate ref is not a full commit: {row['slug']}")
        if row.get("target_toolchain") != TARGET_TOOLCHAIN:
            raise ValueError(f"candidate toolchain changed: {row['slug']}")
    if not (
        frame.get("scientific_candidate_tactics_permitted") == 0
        and frame.get("source_overlap_threshold") == SOURCE_OVERLAP_THRESHOLD
    ):
        raise ValueError("Extension2 candidate surface changed")
    return frame
