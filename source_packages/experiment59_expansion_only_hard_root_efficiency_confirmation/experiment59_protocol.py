"""Locked primitives for the disjoint expansion-only hard-root confirmation."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping


PACKAGE_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(os.environ.get("MZX_ROOT", PACKAGE_ROOT.parent)).resolve()
EXP58_PACKAGE_ROOT = WORKSPACE_ROOT / "experiment58_external_hard_root_efficiency_confirmation"
EXP58_ARTIFACT_ROOT = WORKSPACE_ROOT / "artifacts/v58/external_hard_root_efficiency_confirmation"
ARTIFACT_ROOT = WORKSPACE_ROOT / "artifacts/v59/expansion_only_hard_root_efficiency_confirmation"
CHECKOUT_ROOT = WORKSPACE_ROOT / "external_repos/experiment58_external_benchmarks"

VERSION = 1
PROTOCOL_VERSION = "experiment59-expansion-only-hard-root-efficiency-confirmation-v1"
MECHANICAL_FIX_ID = "exp59-pre-candidate-disjoint-direct-suggestion-separation-v1"
EXP58_NOGO_SCHEMA = "experiment58-candidate-panel-recruitment-nogo-v1"
EXP58_NOGO_LABEL = "candidate_panel_recruitment_no_go"
TARGET_TOOLCHAIN = "leanprover/lean4:v4.27.0"

REMOVED_DIRECT_SUGGESTIONS = ("aesop?", "exact?")
EXPECTED_EXP58_SCREENING_ROOTS = 512
EXPECTED_EXP58_OPERATIONAL_ROOTS = 511
EXPECTED_EXP58_CANDIDATE_ATTEMPTS = 11_753
EXPECTED_EXP58_TIMEOUT_TARGET_ID = "bdc87192ddab4efca8622f66"
EXPECTED_COMPLETE_SOURCE_TARGETS = 1_170
EXPECTED_UNUSED_SOURCE_TARGETS = 658
EXPECTED_UNUSED_BY_DATASET = {"minif2f": 242, "putnambench": 416}

PILOT_SOURCE_ROOTS_PER_DATASET = 64
EXPECTED_CONFIRMATION_SOURCE_ROOTS = {"minif2f": 178, "putnambench": 352}
MIN_EXECUTABLE_NONTERMINAL = 4
MIN_EFFECT_CLASS_SIZE = 2
MIN_PILOT_ELIGIBLE_PER_DATASET = 16
MIN_CONFIRMATION_POOL_PER_DATASET = 64
PILOT_ROOTS_PER_DATASET = 16
SHARD_COUNT = 32

ROLE_ASSIGNMENT_SEED = 590051
PILOT_SELECTION_SEED = 590052
CONFIRMATION_SELECTION_SEED = 590053
GENERATED_ID_RE = re.compile(r"(?:(?:\?m\.|_uniq\.|_let_match\.|_match\.)\d+|✝\d*)")
WS_RE = re.compile(r"[ \t]+")


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


def selection_key(seed: int, *parts: object) -> str:
    return hashlib.sha256((str(seed) + "\0" + "\0".join(map(str, parts))).encode()).hexdigest()


def seal(value: dict[str, Any]) -> dict[str, Any]:
    value["record_sha256"] = json_sha256({k: v for k, v in value.items() if k != "record_sha256"})
    return value


def assert_sealed(value: Mapping[str, Any], label: str) -> None:
    expected = json_sha256({k: v for k, v in value.items() if k != "record_sha256"})
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


def normalize_goal_text(text: Any) -> str:
    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    value = GENERATED_ID_RE.sub("<GEN>", value)
    return "\n".join(WS_RE.sub(" ", line.strip()) for line in value.splitlines() if line.strip())


def tactic_head(tactic: str) -> str:
    token = re.split(r"[\s\[({|;]+", tactic.strip(), maxsplit=1)[0]
    return token or "<empty>"


def load_exp58_modules() -> tuple[Any, Any, Any]:
    required = (
        EXP58_PACKAGE_ROOT / "experiment58_protocol.py",
        EXP58_PACKAGE_ROOT / "enumerate_experiment58_targets.py",
        EXP58_PACKAGE_ROOT / "experiment58_candidate_worker.py",
    )
    if not all(path.is_file() for path in required):
        raise FileNotFoundError("the protected Exp58 package is unavailable")
    if str(EXP58_PACKAGE_ROOT) not in sys.path:
        sys.path.insert(0, str(EXP58_PACKAGE_ROOT))
    import experiment58_protocol as exp58
    import enumerate_experiment58_targets as exp58_enumeration
    import experiment58_candidate_worker as exp58_worker
    exp58.load_protocol(EXP58_ARTIFACT_ROOT)
    return exp58, exp58_enumeration, exp58_worker


def load_genealogy(exp58: Any) -> tuple[dict[str, dict[str, str]], Path, str]:
    protocol_path, _ = exp58.vendor_paths()
    spec = importlib.util.spec_from_file_location("experiment59_exp49_protocol", protocol_path)
    if spec is None or spec.loader is None:
        raise ImportError(protocol_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    genealogy = dict(module.CANDIDATE_GENEALOGY)
    return genealogy, protocol_path, file_sha256(protocol_path)


def expansion_panel(exp58: Any) -> tuple[str, ...]:
    genealogy, _, _ = load_genealogy(exp58)
    removed = tuple(
        tactic for tactic in exp58.CANDIDATE_PANEL
        if genealogy.get(tactic, {}).get("class") == "direct_suggestion"
    )
    if removed != REMOVED_DIRECT_SUGGESTIONS:
        raise ValueError(f"pre-existing direct-suggestion taxonomy changed: {removed}")
    panel = tuple(tactic for tactic in exp58.CANDIDATE_PANEL if tactic not in removed)
    if len(panel) != 21:
        raise ValueError("expansion-only panel must contain exactly 21 candidates")
    return panel


def project_path(dataset: str, checkout_root: Path, exp58: Any) -> Path:
    return exp58.project_path(dataset, checkout_root)


def load_protocol(root: Path = ARTIFACT_ROOT) -> dict[str, Any]:
    value = read_json(root / "frozen/protocol.json")
    assert_sealed(value, "Exp59 protocol")
    if value.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("wrong Exp59 protocol")
    for row in value.get("implementation_locks", []):
        path = PACKAGE_ROOT / row["path"]
        if not path.is_file() or path.stat().st_size != row["bytes"] or file_sha256(path) != row["sha256"]:
            raise ValueError(f"Exp59 implementation changed: {path}")
    return value
