"""Protocol helpers for infrastructure-recovered Exp60 qualification."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent.parent /
                       "experiment60_archival_v427_confirmation"))
from experiment60_protocol import *


PACKAGE_ROOT_61 = Path(__file__).resolve().parent
WORKSPACE_ROOT_61 = Path(os.environ.get("MZX_ROOT", PACKAGE_ROOT_61.parent)).resolve()
ARTIFACT_ROOT_61 = WORKSPACE_ROOT_61 / "artifacts/v61/archival_v427_infrastructure_recovery"
SOURCE_ARTIFACT_ROOT_60 = WORKSPACE_ROOT_61 / "artifacts/v60/archival_v427_confirmation"
SOURCE_ARCHIVE_60 = WORKSPACE_ROOT_61 / "exports/experiment60_recruitment_shortfall_results.zip"
SOURCE_ARCHIVE_60_SHA256 = "8f27596cc31e0fdc98b0e6822d5a142b99486160b6a4abb3425778691d4ed3d7"
PROTOCOL_VERSION_61 = "experiment61-archival-v427-infrastructure-recovery-v1"
RECOVERY_ID = "experiment61-exp60-disk-exhaustion-recovery-v1"
CHECKOUT_ROOT_61 = WORKSPACE_ROOT_61 / "external_repos/experiment61_archival_recovery"
FREE_DISK_FLOOR_BYTES = 100 * 1024 ** 3
RECOVERY_BATCH_SIZE = 4
RECOVERY_REPOSITORY_WORKERS = 4
RECOVERY_BUILD_SLOTS = 2
RECOVERY_TRACE_SLOTS = 4
RECOVERY_ENUMERATION_SLOTS = 2

IMPLEMENTATION_FILES_61 = (
    "experiment61_protocol.py",
    "freeze_experiment61_recovery.py",
    "run_experiment61_recovery.py",
    "finalize_experiment61_shortfall.py",
    "audit_experiment61_shortfall.py",
)


def implementation_locks_61() -> list[dict[str, Any]]:
    rows = []
    for name in IMPLEMENTATION_FILES_61:
        path = PACKAGE_ROOT_61 / name
        if not path.is_file():
            raise FileNotFoundError(path)
        rows.append({"path": name, "bytes": path.stat().st_size,
                     "sha256": file_sha256(path)})
    return rows


def validate_implementation_locks_61(protocol: Mapping[str, Any]) -> None:
    observed = implementation_locks_61()
    if protocol.get("implementation_locks") != observed:
        raise ValueError("Exp61 implementation lock changed")


def backend_candidate_61(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": row["slug"], "url": row["url"], "ref": row["commit"],
        "commit": row["commit"], "domain": row.get("domain", "unclassified"),
        "subdir": row.get("subdir", "."),
        "snapshot_source": row["snapshot_source"],
        "snapshot_record_sha256": row["snapshot_record_sha256"],
    }


def safe_slug_61(slug: str) -> str:
    return slug.replace("/", "__")


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_bytes(source.read_bytes())
    os.replace(temporary, destination)
