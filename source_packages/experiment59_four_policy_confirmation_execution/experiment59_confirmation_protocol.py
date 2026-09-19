"""Locked helpers for the disjoint Exp59 four-policy confirmation."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping


PACKAGE_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(os.environ.get("MZX_ROOT", PACKAGE_ROOT.parent)).resolve()
SOURCE_PACKAGE_ROOT = WORKSPACE_ROOT / "experiment59_four_policy_pilot_execution"
ARTIFACT_ROOT = WORKSPACE_ROOT / "artifacts/v59/expansion_only_hard_root_efficiency_confirmation"
CHECKOUT_ROOT = WORKSPACE_ROOT / "external_repos/experiment58_external_benchmarks"

VERSION = 1
SOURCE_PILOT_PROTOCOL_VERSION = "experiment59-expansion-only-four-policy-pilot-v1"
CONFIRMATION_PROTOCOL_VERSION = "experiment59-expansion-only-four-policy-confirmation-v1"
MECHANICAL_FIX_ID = "exp59-four-policy-confirmation-execution-v1"
ROW_SCHEMA = "experiment59-confirmation-search-cell-v1"
JOB_SCHEMA = "experiment59-confirmation-root-policy-job-v1"
EXPECTED_SELECTION_DESIGN_RECORD_SHA256 = "70043de8a1c6db3abf94687d5166f25468ae95c8fba3495079c77cbd8668a114"
EXPECTED_SELECTED_ROOTS_SHA256 = "cbfc4569e5869e74b8f72e4ee5f4ce6f1def6d23fdde274ef15e224a169d6bb6"
EXPECTED_SELECTION_AUDIT_SHA256 = "2c341eeed3b5e8729f2861cac867918c53faa2bff2fbe66717510c8f631b745b"
EXPECTED_ROOTS = 64
ROOTS_PER_DATASET = 32
CANDIDATES_PER_ROOT = 21
POLICIES = ("full", "effect_aware", "head_dedup", "fixed_budget_random")
EXPECTED_JOBS = EXPECTED_ROOTS * len(POLICIES)
PROBE_PANEL = (
    "rfl", "assumption", "simp", "simp_all", "omega", "constructor", "intro", "solve_by_elim",
)
ROOT_POLICY_TIME_BUDGET_SECONDS = 7200
CELL_TIMEOUT_SECONDS = 900
COVERAGE_NONINFERIORITY_MARGIN = 0.05
ONE_SIDED_Z = 1.6448536269514722
BOOTSTRAP_REPLICATES = 20_000
BOOTSTRAP_SEED = 590058


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
    value["record_sha256"] = json_sha256({k: v for k, v in value.items() if k != "record_sha256"})
    return value


def assert_sealed(value: Mapping[str, Any], label: str) -> None:
    expected = json_sha256({k: v for k, v in value.items() if k != "record_sha256"})
    if value.get("record_sha256") != expected:
        raise ValueError(f"{label} record hash changed")


def atomic_json_dump(value: Any, path: str | Path) -> None:
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, target)


def atomic_jsonl_dump(rows: Iterable[Mapping[str, Any]], path: str | Path) -> None:
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, target)


def atomic_csv_dump(rows: list[Mapping[str, Any]], path: str | Path) -> None:
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        fields.extend(key for key in row if key not in fields)
    temporary = target.with_name(target.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, target)


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def load_pilot() -> Any:
    if str(SOURCE_PACKAGE_ROOT) not in sys.path:
        sys.path.insert(0, str(SOURCE_PACKAGE_ROOT))
    import experiment59_pilot_protocol as pilot
    design = pilot.load_design(ARTIFACT_ROOT)
    if design.get("pilot_protocol_version") != SOURCE_PILOT_PROTOCOL_VERSION:
        raise ValueError("source pilot protocol changed")
    return pilot


def load_selection() -> tuple[Any, dict[str, Any]]:
    pilot = load_pilot()
    path = ARTIFACT_ROOT / "confirmation/frozen/design.json"
    value = pilot.read_json(path); pilot.assert_sealed(value, "confirmation selection")
    if not (
        value.get("record_sha256") == EXPECTED_SELECTION_DESIGN_RECORD_SHA256
        and value.get("confirmation_protocol_version") == CONFIRMATION_PROTOCOL_VERSION
        and value.get("confirmation_roots") == EXPECTED_ROOTS
        and value.get("roots_per_dataset") == ROOTS_PER_DATASET
        and value.get("selected_roots_sha256") == EXPECTED_SELECTED_ROOTS_SHA256
        and value.get("selection_audit_sha256") == EXPECTED_SELECTION_AUDIT_SHA256
        and value.get("pilot_and_confirmation_disjoint") is True
        and value.get("manual_replacement_count") == 0
        and value.get("confirmation_continuation_probes_executed_before_freeze") == 0
        and value.get("confirmation_freeze_gate") is True
    ):
        raise ValueError("confirmation selection is not the protected frozen design")
    return pilot, value


def choose(policy: str, branches: list[dict[str, Any]], target_id: str) -> list[dict[str, Any]]:
    return load_pilot().choose(policy, branches, target_id)


def load_execution_design(root: Path = ARTIFACT_ROOT) -> dict[str, Any]:
    value = read_json(root / "confirmation/frozen/execution_design.json")
    assert_sealed(value, "confirmation execution design")
    if value.get("confirmation_protocol_version") != CONFIRMATION_PROTOCOL_VERSION:
        raise ValueError("wrong confirmation execution protocol")
    for row in value.get("implementation_locks", []):
        path = PACKAGE_ROOT / row["path"]
        if not path.is_file() or path.stat().st_size != row["bytes"] or file_sha256(path) != row["sha256"]:
            raise ValueError(f"confirmation implementation changed: {path}")
    return value


def wilson_upper(failures: int, n: int, z: float = ONE_SIDED_Z) -> float:
    if n <= 0:
        return 1.0
    p = failures / n; denominator = 1 + z * z / n
    center = p + z * z / (2 * n)
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (center + radius) / denominator
