"""Primitives for the frozen Exp59 four-policy pilot and power plan."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping


PACKAGE_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(os.environ.get("MZX_ROOT", PACKAGE_ROOT.parent)).resolve()
SOURCE_PACKAGE_ROOT = WORKSPACE_ROOT / "experiment59_expansion_only_hard_root_efficiency_confirmation"
ARTIFACT_ROOT = WORKSPACE_ROOT / "artifacts/v59/expansion_only_hard_root_efficiency_confirmation"
CHECKOUT_ROOT = WORKSPACE_ROOT / "external_repos/experiment58_external_benchmarks"
BACKEND_ROOT = WORKSPACE_ROOT / "experiment54_effect_aware_depth2_microbenchmark_fix3"

VERSION = 1
SOURCE_PROTOCOL_VERSION = "experiment59-expansion-only-hard-root-efficiency-confirmation-v1"
PILOT_PROTOCOL_VERSION = "experiment59-expansion-only-four-policy-pilot-v1"
MECHANICAL_FIX_ID = "exp59-four-policy-pilot-fresh-process-call-accounting-v1"
ROW_SCHEMA = "experiment59-pilot-search-cell-v1"
JOB_SCHEMA = "experiment59-pilot-root-policy-job-v1"
TARGET_TOOLCHAIN = "leanprover/lean4:v4.27.0"

EXPECTED_SCREENING_SUMMARY_RECORD_SHA256 = "96ef54df49716b1037d84ae383b790d6fde86800fb4fc3325a371a61cec80331"
EXPECTED_ELIGIBILITY_LEDGER_SHA256 = "5751d162a0d8a68537b2f0d2b36d8d0ff64cd55085eb1257ae1b2aadb297730b"
EXPECTED_PILOT_ROOTS_SHA256 = "a83631e3bbbdafae66f527f5e9bd613819fd2a09aace3531008b14ffde2260ab"
EXPECTED_SCREENING_ROOTS = 658
EXPECTED_ELIGIBLE_ROOTS = 459
EXPECTED_PILOT_ROOTS = 32
CANDIDATES_PER_ROOT = 21
EXPECTED_POLICIES = 4
EXPECTED_JOBS = EXPECTED_PILOT_ROOTS * EXPECTED_POLICIES

POLICIES = ("full", "effect_aware", "head_dedup", "fixed_budget_random")
PROBE_PANEL = (
    "rfl", "assumption", "simp", "simp_all", "omega", "constructor", "intro", "solve_by_elim",
)
RANDOM_POLICY_SEED = 590055
POWER_SEED = 590056
ANALYSIS_BOOTSTRAP_SEED = 590057
ROOT_POLICY_TIME_BUDGET_SECONDS = 7200
CELL_TIMEOUT_SECONDS = 900
COVERAGE_NONINFERIORITY_MARGIN = 0.05
POWER_TARGET = 0.90
POWER_REPLICATES = 20_000
ONE_SIDED_Z = 1.6448536269514722
CONFIRMATION_TOTAL_N_GRID = (48, 64, 80, 96, 112, 128)
BACKEND_WORKER_SHA256 = "b1afb706e280b2204299e19568d48a40b9070ace2654c20c445dc59393e72f04"
BACKEND_PROTOCOL_SHA256 = "2ec6d7487592e9d3540e8576a63f2873e85d7415df8ace3fee9202001e8d863e"


def file_sha256(path: str | Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def seal(value: dict[str, Any]) -> dict[str, Any]:
    value["record_sha256"] = json_sha256({key: item for key, item in value.items() if key != "record_sha256"})
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
        fields.extend(key for key in row if key not in fields)
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


def load_source() -> tuple[Any, Any]:
    if str(SOURCE_PACKAGE_ROOT) not in sys.path:
        sys.path.insert(0, str(SOURCE_PACKAGE_ROOT))
    import experiment59_protocol as source_protocol
    import experiment59_candidate_worker as source_worker
    protocol = source_protocol.load_protocol(ARTIFACT_ROOT)
    if protocol.get("protocol_version") != SOURCE_PROTOCOL_VERSION:
        raise ValueError("source Exp59 protocol changed")
    return source_protocol, source_worker


def validate_backend() -> tuple[Path, Path]:
    worker = BACKEND_ROOT / "experiment54_live_worker.py"
    protocol = BACKEND_ROOT / "experiment54_protocol.py"
    if not worker.is_file() or file_sha256(worker) != BACKEND_WORKER_SHA256:
        raise ValueError("locked depth-two worker changed")
    if not protocol.is_file() or file_sha256(protocol) != BACKEND_PROTOCOL_SHA256:
        raise ValueError("locked depth-two protocol changed")
    return worker, protocol


def load_backend() -> Any:
    validate_backend()
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    import experiment54_live_worker as backend
    return backend


def choose(policy: str, branches: list[dict[str, Any]], target_id: str) -> list[dict[str, Any]]:
    if policy == "full":
        return list(branches)
    if policy == "effect_aware":
        key = lambda row: row["endpoints"]["struct"]["sha256"]
    elif policy == "head_dedup":
        key = lambda row: row["head"]
    elif policy == "fixed_budget_random":
        budget = len(choose("effect_aware", branches, target_id))
        seed = int(json_sha256([RANDOM_POLICY_SEED, target_id])[:16], 16)
        indices = sorted(random.Random(seed).sample(range(len(branches)), budget))
        return [branches[index] for index in indices]
    else:
        raise ValueError(policy)
    selected = []
    seen = set()
    for row in branches:
        identity = key(row)
        if identity not in seen:
            seen.add(identity)
            selected.append(row)
    return selected


def load_design(root: Path = ARTIFACT_ROOT) -> dict[str, Any]:
    value = read_json(root / "pilot/frozen/design.json")
    assert_sealed(value, "Exp59 pilot design")
    if value.get("pilot_protocol_version") != PILOT_PROTOCOL_VERSION:
        raise ValueError("wrong Exp59 pilot protocol")
    for row in value.get("implementation_locks", []):
        path = PACKAGE_ROOT / row["path"]
        if not path.is_file() or path.stat().st_size != row["bytes"] or file_sha256(path) != row["sha256"]:
            raise ValueError(f"Exp59 pilot implementation changed: {path}")
    return value
