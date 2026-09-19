"""Protocol helpers for Experiment 53 cross-machine subset re-execution."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping


PACKAGE_ROOT = Path(__file__).resolve().parent
PROTOCOL_VERSION = "experiment53-cross-machine-subset-reexecution-v1"
FREEZE_SCHEMA = "experiment53-portable-subset-freeze-v1"
REFERENCE_SCHEMA = "experiment53-exp51-reference-projection-v1"
RESULT_SCHEMA = "experiment53-cross-machine-comparison-v1"
SOURCE_EXP51_BUNDLE = "experiment51_external_repository_replication_fix3_results.zip"
SOURCE_EXP51_SHA256 = "f8c84a92ef4a7dc025a9f7918a0f16af91160acb112bb0578ee0bf431057511b"
SOURCE_EXP51_PROTOCOL = "experiment51-preregistered-external-repository-replication-v1"
TARGET_LEAN_VERSION = "v4.27.0"
SOURCE_MACHINE_HOSTNAME = "gpuserver01"
TARGET_MACHINE_SYSTEM = "Darwin"
REPOSITORIES = 4
ROOTS_PER_REPOSITORY = 4
CANDIDATES_PER_ROOT = 23
ROOTS = REPOSITORIES * ROOTS_PER_REPOSITORY
DEFAULT_SHARDS = 4
DEFAULT_TIMEOUT = 900


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def json_sha256(value: Any) -> str:
    return bytes_sha256(json_bytes(value))


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def atomic_json_dump(value: Any, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=target.name + ".", dir=str(target.parent))
    tmp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()


def atomic_jsonl_dump(rows: Iterable[Mapping[str, Any]], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=target.name + ".", dir=str(target.parent))
    tmp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True))
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()


def safe_slug(slug: str) -> str:
    return slug.replace("/", "__")


def endpoint_projection(endpoints: Any) -> Any:
    if not isinstance(endpoints, dict):
        return None
    projected: dict[str, Any] = {}
    for kind in ("raw", "text48", "struct"):
        entry = endpoints.get(kind)
        if not isinstance(entry, dict):
            projected[kind] = None
            continue
        state = entry.get("state")
        projected[kind] = {
            "sha256": entry.get("sha256"),
            "state": {
                "sha256": state.get("sha256") if isinstance(state, dict) else None,
                "bytes": state.get("bytes") if isinstance(state, dict) else None,
            },
            "metadata": entry.get("metadata"),
        }
    return projected


def attempt_projection(attempt: Any) -> Any:
    if not isinstance(attempt, dict):
        return None
    value = {
        "tactic": attempt.get("tactic"),
        "head": attempt.get("head"),
        "family": attempt.get("family"),
        "executable": attempt.get("executable"),
        "failure_category": attempt.get("failure_category"),
        "goal_count": attempt.get("goal_count"),
        "terminal": attempt.get("terminal"),
        "pre_text_sha256": attempt.get("pre_text_sha256"),
        "pre_struct_sha256": attempt.get("pre_struct_sha256"),
        "endpoints": endpoint_projection(attempt.get("endpoints")),
    }
    return value


def row_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return the registered cross-machine content, excluding paths and timing."""
    return {
        "schema": REFERENCE_SCHEMA,
        "slug": row.get("slug"),
        "commit": row.get("commit"),
        "file_path": row.get("file_path"),
        "full_name": row.get("full_name"),
        "theorem_id": row.get("theorem_id"),
        "source_file_sha256": row.get("source_file_sha256"),
        "ast_sha256": row.get("ast_sha256"),
        "target_pos": row.get("target_pos"),
        "target_end_pos": row.get("target_end_pos"),
        "target_found": row.get("target_found"),
        "trace_root_match": row.get("trace_root_match"),
        "worker_ok": row.get("worker_ok"),
        "authored_replay_ok": row.get("authored_replay_ok"),
        "same_pre_state_all_branches": row.get("same_pre_state_all_branches"),
        "live_tacticinfo_prestate_identity": row.get(
            "live_tacticinfo_prestate_identity"
        ),
        "candidate_order": row.get("candidate_order"),
        "initial_endpoints": endpoint_projection(row.get("initial_endpoints")),
        "authored": attempt_projection(row.get("authored")),
        "original_authored_endpoints": endpoint_projection(
            row.get("original_authored_endpoints")
        ),
        "candidates": [attempt_projection(item) for item in row.get("candidates", [])],
    }


def package_code_paths() -> list[Path]:
    paths = sorted(PACKAGE_ROOT.glob("*.py"))
    paths.extend(sorted(PACKAGE_ROOT.glob("*.md")))
    amendment = PACKAGE_ROOT / "frozen/FREEZE_AMENDMENT.md"
    if amendment.is_file():
        paths.append(amendment)
    paths.extend(sorted((PACKAGE_ROOT / "frozen").glob("aborted_parallel_launch_*.json")))
    paths.extend(sorted((PACKAGE_ROOT / "vendor").glob("*.py")))
    return [path for path in paths if path.name != "PACKAGE_MANIFEST.json"]


def code_lock() -> list[dict[str, Any]]:
    return [
        {
            "path": str(path.relative_to(PACKAGE_ROOT)),
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in package_code_paths()
    ]


def validate_frozen() -> tuple[dict[str, Any], dict[str, Any]]:
    receipt_path = PACKAGE_ROOT / "frozen/freeze_receipt.json"
    subset_path = PACKAGE_ROOT / "frozen/subset.json"
    if not receipt_path.is_file() or not subset_path.is_file():
        raise FileNotFoundError("Exp53 frozen files are missing")
    receipt = read_json(receipt_path)
    subset = read_json(subset_path)
    if not (
        receipt.get("protocol_version") == PROTOCOL_VERSION
        and receipt.get("freeze_schema") == FREEZE_SCHEMA
        and receipt.get("source_exp51_bundle_sha256") == SOURCE_EXP51_SHA256
        and receipt.get("subset_sha256") == file_sha256(subset_path)
        and subset.get("protocol_version") == PROTOCOL_VERSION
        and len(subset.get("repositories", [])) == REPOSITORIES
        and len(subset.get("targets", [])) == ROOTS
    ):
        raise ValueError("Exp53 frozen identity changed")
    if receipt.get("code_lock") != code_lock():
        raise ValueError("Exp53 code lock changed")
    reference_index = read_json(PACKAGE_ROOT / "frozen/reference_index.json")
    if receipt.get("reference_index_sha256") != file_sha256(
        PACKAGE_ROOT / "frozen/reference_index.json"
    ):
        raise ValueError("Exp53 reference index changed")
    for entry in reference_index:
        path = PACKAGE_ROOT / entry["path"]
        if not path.is_file() or file_sha256(path) != entry["sha256"]:
            raise ValueError(f"Exp53 reference row changed: {path}")
    return subset, receipt


def checkout_map(path: str | Path) -> dict[str, Path]:
    raw = read_json(path)
    mapping = raw.get("repositories", raw)
    if not isinstance(mapping, dict):
        raise ValueError("checkout map must be a mapping")
    return {str(slug): Path(value).resolve() for slug, value in mapping.items()}


def machine_receipt() -> dict[str, Any]:
    system = platform.system()
    hostname = platform.node()
    return {
        "platform": platform.platform(),
        "system": system,
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "hostname": hostname,
        "source_machine_hostname": SOURCE_MACHINE_HOSTNAME,
        "hostname_distinct_from_source": hostname.split(".")[0]
        != SOURCE_MACHINE_HOSTNAME,
        "target_machine_system": TARGET_MACHINE_SYSTEM,
        "target_machine_system_ok": system == TARGET_MACHINE_SYSTEM,
    }
