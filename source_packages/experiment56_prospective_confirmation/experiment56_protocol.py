"""Locked design primitives for a prospective repository confirmation.

Experiment 56 is intentionally separate from the historical 96-root result.
It freezes the repository frame, every exclusion, and every root-selection key
before any scientific alternative is executed.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping


PACKAGE_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(os.environ.get("MZX_ROOT", PACKAGE_ROOT.parent)).resolve()
ARTIFACT_ROOT = WORKSPACE_ROOT / "artifacts/v56/prospective_confirmation"

VERSION = 1
PROTOCOL_VERSION = "experiment56-prospective-repository-confirmation-v1"
DESIGN_SCHEMA = "experiment56-prospective-design-v1"
TARGET_TOOLCHAIN = "leanprover/lean4:v4.27.0"
REPOSITORIES_REQUIRED = 38
ROOTS_PER_REPOSITORY = 16
TOTAL_ROOTS = REPOSITORIES_REQUIRED * ROOTS_PER_REPOSITORY
MIN_ELIGIBLE_ROOTS = ROOTS_PER_REPOSITORY
MASTER_REPOSITORY_SEED = 560051
MASTER_ROOT_SEED = 560052
POWER_SEED = 560053
BOOTSTRAP_SEED = 560054
POWER_REPLICATES = 100_000
BOOTSTRAP_REPLICATES = 20_000
PRIMARY_THRESHOLD = 0.20
MAX_CI_HALFWIDTH = 0.10
MIN_NONZERO_REPOSITORY_FRACTION = 0.75
SOURCE_OVERLAP_THRESHOLD = 0.20
CANDIDATES_PER_ROOT = 23

HISTORICAL_SCIENTIFIC_REPOSITORIES = {
    "teorth/pfr", "leanprover-community/physlib",
    "leanprover-community/sphere-eversion", "leanprover-community/flt-regular",
    "fpvandoorn/carleson", "ImperialCollegeLondon/FLT",
    "thefundamentaltheor3m/Sphere-Packing-Lean", "RemyDegenne/brownian-motion",
    "PatrickMassot/GlimpseOfLean", "AfonsoBitoque/LeanServer",
    "dissensus-ai/lean-formalizations", "leanprover-community/batteries",
    "bergmannjg/Regex", "Verified-zkEVM/VCVio", "leanprover-community/lean-auto",
    "YaelDillies/misc-yd", "MichaelStollBayreuth/LegendreQF", "verse-lab/Lentil",
    "AmosNico/validator", "spectra-research/asymptotic-tensor-rank-semicontinuity",
}

FROZEN_GITHUB_QUERIES = (
    "language:Lean fork:false archived:false stars:0..2",
    "language:Lean fork:false archived:false stars:3..9",
    "language:Lean fork:false archived:false stars:10..49",
    "language:Lean fork:false archived:false stars:>=50",
)

SOURCE_EXP51 = {
    "path": "experiment51_external_repository_replication_fix3_results.zip",
    "sha256": "f8c84a92ef4a7dc025a9f7918a0f16af91160acb112bb0578ee0bf431057511b",
}
LOCKED_BACKENDS = {
    "protocol": {
        "path": "experiment51_external_repository_replication/experiment51_protocol.py",
        "sha256": "6c8ded7b453d3f5bfe75fc916d9c990368f54b20e81e4d54915376d20a88655f",
    },
    "live_worker": {
        "path": "experiment51_external_repository_replication/experiment51_live_worker.py",
        "sha256": "c472171177c29f48d9b633887656287a7f75fc54e8707bafb8205a925eb9e0b0",
    },
    "screening": {
        "path": "experiment51_external_repository_replication/screen_experiment51_repositories.py",
        "sha256": "a76dede54b718122f63afc9682f2951b7768f783b3d98b0b73bc967cec08a47f",
    },
    "enumeration_worker": {
        "path": "experiment51_external_repository_replication/experiment51_enumeration_worker.py",
        "sha256": "e68c9f336ade2604ff90bb814f877a14e19f43b34f85626e934ae906c5834155",
    },
    "trace_runtime": {
        "path": "experiment51_external_repository_replication/experiment51_trace_runtime.py",
        "sha256": "45d99206470327a4933da05740d4553a90f96ac62b4bd42476037f2c6b73f5ee",
    },
}


def file_sha256(path: str | Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def json_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def selection_key(seed: int, *parts: object) -> str:
    return hashlib.sha256(
        (str(seed) + "\0" + "\0".join(str(x) for x in parts)).encode("utf-8")
    ).hexdigest()


def seal(value: dict[str, Any]) -> dict[str, Any]:
    value["record_sha256"] = json_sha256(
        {key: item for key, item in value.items() if key != "record_sha256"}
    )
    return value


def assert_sealed(value: Mapping[str, Any], label: str) -> None:
    expected = json_sha256({key: item for key, item in value.items() if key != "record_sha256"})
    if value.get("record_sha256") != expected:
        raise ValueError(f"{label} record hash changed")


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


def validate_locks() -> list[dict[str, Any]]:
    locks = {"exp51_archive": SOURCE_EXP51, **LOCKED_BACKENDS}
    rows = []
    for name, record in locks.items():
        path = (WORKSPACE_ROOT / record["path"]).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = file_sha256(path)
        if observed != record["sha256"]:
            raise ValueError(f"{name} SHA changed: {observed}")
        rows.append({"name": name, "path": str(path), "sha256": observed, "sha256_exact": True})
    return rows


def validate_implementation_locks(protocol: Mapping[str, Any]) -> None:
    rows = list(protocol.get("implementation_locks", []))
    if not rows:
        raise ValueError("prospective implementation lock is missing")
    for row in rows:
        path = PACKAGE_ROOT / str(row["path"])
        if (not path.is_file() or path.stat().st_size != int(row["bytes"])
                or file_sha256(path) != row["sha256"]):
            raise ValueError(f"prospective implementation changed: {path}")
