"""Protocol primitives for the frozen four-policy search benchmark."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping


PACKAGE_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(os.environ.get("MZX_ROOT", PACKAGE_ROOT.parent)).resolve()
ARTIFACT_ROOT = WORKSPACE_ROOT / "artifacts/v57/end_to_end_search_benchmark"
SOURCE_ARCHIVE = WORKSPACE_ROOT / "experiment54_effect_aware_depth2_fix3_results.zip"
SOURCE_ARCHIVE_SHA256 = "af8b69ff24808f635b73da14c33eece875281ede81a695f86b704366ab0a05b0"
SOURCE_EXP49_ARCHIVE = WORKSPACE_ROOT / "experiment49_candidate_endpoint_robustness_results.zip"
SOURCE_EXP49_ARCHIVE_SHA256 = "f57f6938c5de6d32339f2ca9e8cb2789ceed1dd2263feb7155ee76b35caefdc2"

VERSION = 1
PROTOCOL_VERSION = "experiment57-four-policy-depth2-search-benchmark-v1"
ROW_SCHEMA = "experiment57-search-cell-v1"
JOB_SCHEMA = "experiment57-root-policy-job-v1"
POLICIES = ("full", "effect_aware", "head_dedup", "fixed_budget_random")
RANDOM_SEED = 570051
ROOT_POLICY_TIME_BUDGET_SECONDS = 7200
CELL_TIMEOUT_SECONDS = 900
EXPECTED_ROOTS = 16
EXPECTED_POLICIES = 4
EXPECTED_JOBS = EXPECTED_ROOTS * EXPECTED_POLICIES
CANDIDATES_PER_ROOT = 23


def file_sha256(path: str | Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def json_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def seal(value: dict[str, Any]) -> dict[str, Any]:
    value["record_sha256"] = json_sha256(
        {key: item for key, item in value.items() if key != "record_sha256"}
    )
    return value


def assert_sealed(value: Mapping[str, Any], label: str) -> None:
    observed = value.get("record_sha256")
    expected = json_sha256({key: item for key, item in value.items() if key != "record_sha256"})
    if observed != expected:
        raise ValueError(f"{label} record SHA changed")


def atomic_json_dump(value: Any, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)


def atomic_jsonl_dump(rows: Iterable[Mapping[str, Any]], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)


def atomic_csv_dump(rows: list[Mapping[str, Any]], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    temporary = target.with_name(target.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def portable_checkout(archived: str) -> Path:
    marker = "/external_repos/"
    if marker in archived:
        return (WORKSPACE_ROOT / "external_repos" / archived.split(marker, 1)[1]).resolve()
    return Path(archived).resolve()


def load_design(root: Path = ARTIFACT_ROOT) -> dict[str, Any]:
    value = read_json(root / "frozen/design.json")
    assert_sealed(value, "Exp57 design")
    for row in value.get("implementation_locks", []):
        path = PACKAGE_ROOT / str(row["path"])
        if (not path.is_file() or path.stat().st_size != int(row["bytes"])
                or file_sha256(path) != row["sha256"]):
            raise ValueError(f"Exp57 implementation changed: {path}")
    return value
