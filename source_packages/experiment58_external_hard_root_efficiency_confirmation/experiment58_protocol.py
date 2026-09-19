"""Immutable primitives for the external hard-root efficiency confirmation."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


PACKAGE_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(os.environ.get("MZX_ROOT", PACKAGE_ROOT.parent)).resolve()
ARTIFACT_ROOT = WORKSPACE_ROOT / "artifacts/v58/external_hard_root_efficiency_confirmation"
CHECKOUT_ROOT = WORKSPACE_ROOT / "external_repos/experiment58_external_benchmarks"

VERSION = 1
PROTOCOL_VERSION = "experiment58-external-hard-root-efficiency-confirmation-v1"
MECHANICAL_FIX_ID = "exp58-pre-continuation-root-path-and-accounting-fix2"
TARGET_TOOLCHAIN = "leanprover/lean4:v4.27.0"
CANDIDATE_SCREENING_EXECUTION_ROOT = Path("screening/root_path_fix2")

SOURCE_EXP57_ARCHIVE = WORKSPACE_ROOT / "experiment57_end_to_end_search_benchmark_results.zip"
SOURCE_EXP57_ARCHIVE_SHA256 = "da9da92de0dfd4a7426f1bd2284e9a862d95ae9f56f15fd9d1dbc2fffad4cbf0"
EXP57_FROZEN_DESIGN_MEMBER = "artifacts/frozen/design.json"
EXP57_FROZEN_JOBS_MEMBER = "artifacts/frozen/jobs.jsonl"

VENDOR_PROTOCOL_SHA256 = "9faf4cd691a69238eba240cdd61d2ea05e48c11f5aad1a667142f7d89e136e55"
VENDOR_WORKER_SHA256 = "ae9fadc6b4b71712ec01cb2f027f77e0b72b77c737a8a97b46298d61a0190205"

DATASETS: dict[str, dict[str, Any]] = {
    "minif2f": {
        "url": "https://github.com/google-deepmind/miniF2F.git",
        "commit": "f0a20e14c1eeccd859d51bb4c2b3ee487889c303",
        "project_subdir": ".",
        "toolchain_path": "lean-toolchain",
        "toolchain_sha256": "d55ca0039a5479db5b38919d005b2c427b89b3be4f0184a20f2f4eae931f5bdb",
        "license_path": "LICENSE",
        "license_sha256": "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
        "license": "Apache-2.0",
        "upstream_partition": {"pilot": "MiniF2F/Valid.lean", "confirmation": "MiniF2F/Test.lean"},
        "public_result_policy": "target-level rows and aggregate results may be redistributed with attribution",
    },
    "putnambench": {
        "url": "https://github.com/trishullab/PutnamBench.git",
        "commit": "34eba93650f2fa803ca6aae6dfd2c9f22d46c00d",
        "project_subdir": "lean4",
        "toolchain_path": "lean4/lean-toolchain",
        "toolchain_sha256": "e695e6e5d8e7a8be4d6cf159dfb995847993d26c6cc450353a86f387279025b9",
        "license_path": "lean4/LICENSE",
        "license_sha256": "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
        "license": "Apache-2.0",
        "upstream_partition": None,
        "public_result_policy": (
            "aggregate results only; do not redistribute target-to-successful-tactic mappings "
            "or generated proofs without maintainer approval"
        ),
    },
}
MINIF2F_EXPECTED_THEOREMS = {"pilot": 256, "confirmation": 244}

CANDIDATE_PANEL = (
    "rfl", "assumption", "trivial", "contradiction", "simp", "simpa", "simp_all",
    "aesop", "aesop?", "norm_num", "omega", "linarith", "nlinarith", "ring",
    "ring_nf", "positivity", "decide", "native_decide", "constructor", "ext",
    "fun_prop", "solve_by_elim", "exact?",
)
PROBE_PANEL = (
    "rfl", "assumption", "simp", "simp_all", "omega", "constructor", "intro",
    "solve_by_elim",
)
POLICIES = ("full", "effect_aware", "head_dedup", "fixed_budget_random")
CANDIDATES_PER_ROOT = len(CANDIDATE_PANEL)

PILOT_FRAME_PER_DATASET = 64
CONFIRMATION_FRAME_PER_DATASET = 192
SCREENING_ROOTS_PER_DATASET = PILOT_FRAME_PER_DATASET + CONFIRMATION_FRAME_PER_DATASET
SCREENING_ROOTS_TOTAL = 2 * SCREENING_ROOTS_PER_DATASET
MIN_EXECUTABLE_NONTERMINAL = 4
MIN_EFFECT_CLASS_SIZE = 2
MIN_PILOT_ELIGIBLE_PER_DATASET = 16
MIN_CONFIRMATION_POOL_PER_DATASET = 64
PILOT_ROOTS_PER_DATASET = 16

PARTITION_SEED = 580051
FRAME_SEED = 580052
PILOT_SELECTION_SEED = 580053
CONFIRMATION_SELECTION_SEED = 580054
RANDOM_POLICY_SEED = 580055
POWER_SEED = 580056
POWER_REPLICATES = 20_000
POWER_TARGET = 0.90
EFFICIENCY_ONE_SIDED_Z = 1.6448536269514722
COVERAGE_NONINFERIORITY_MARGIN = 0.05
CONFIRMATION_TOTAL_N_GRID = (48, 64, 80, 96, 112, 128)

GENERATED_ID_RE = re.compile(r"(?:(?:\?m\.|_uniq\.|_let_match\.|_match\.)\d+|✝\d*)")
WS_RE = re.compile(r"[ \t]+")


def file_sha256(path: str | Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def json_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def selection_key(seed: int, *parts: object) -> str:
    raw = str(seed) + "\0" + "\0".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
        for key in row:
            if key not in fields:
                fields.append(key)
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


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "__", value)


def tactic_head(tactic: str) -> str:
    token = re.split(r"[\s\[({|;]+", tactic.strip(), maxsplit=1)[0]
    return token or "<empty>"


def normalize_goal_text(text: Any) -> str:
    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    value = GENERATED_ID_RE.sub("<GEN>", value)
    return "\n".join(WS_RE.sub(" ", line.strip()) for line in value.splitlines() if line.strip())


def project_path(dataset: str, checkout_root: Path = CHECKOUT_ROOT) -> Path:
    spec = DATASETS[dataset]
    base = checkout_root / dataset
    subdir = str(spec["project_subdir"])
    return base if subdir == "." else base / subdir


def vendor_paths() -> tuple[Path, Path]:
    candidates = [
        PACKAGE_ROOT / "vendor",
        WORKSPACE_ROOT / "server_packages/experiment49_candidate_endpoint_robustness",
        WORKSPACE_ROOT / "publication_release/github_repository/experiments/exp49",
    ]
    for root in candidates:
        protocol = root / "experiment49_protocol.py"
        worker = root / "experiment49_strict_worker.py"
        if protocol.is_file() and worker.is_file():
            return protocol, worker
    raise FileNotFoundError("locked Exp49 strict-endpoint vendor sources are unavailable")


def validate_vendor() -> list[dict[str, Any]]:
    protocol, worker = vendor_paths()
    rows = []
    for label, path, expected in (
        ("exp49_protocol", protocol, VENDOR_PROTOCOL_SHA256),
        ("exp49_strict_worker", worker, VENDOR_WORKER_SHA256),
    ):
        observed = file_sha256(path)
        if observed != expected:
            raise ValueError(f"{label} SHA changed: {observed}")
        rows.append({"name": label, "path": str(path), "sha256": observed, "sha256_exact": True})
    return rows


def load_protocol(root: Path = ARTIFACT_ROOT) -> dict[str, Any]:
    value = read_json(root / "frozen/protocol.json")
    assert_sealed(value, "Exp58 protocol")
    for row in value.get("implementation_locks", []):
        path = PACKAGE_ROOT / str(row["path"])
        if not path.is_file() or path.stat().st_size != int(row["bytes"]) or file_sha256(path) != row["sha256"]:
            raise ValueError(f"Exp58 implementation changed: {path}")
    return value
