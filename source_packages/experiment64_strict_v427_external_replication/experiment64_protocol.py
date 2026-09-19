"""Protocol primitives for the strict 32-repository external replication."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PACKAGE_ROOT = Path(__file__).resolve().parent
MZX_ROOT = Path(os.environ.get("MZX_ROOT", PACKAGE_ROOT.parent)).resolve()
ARTIFACT_ROOT = MZX_ROOT / "artifacts/v64/strict_v427_external_replication"
SOURCE_EXP63_ROOT = MZX_ROOT / "artifacts/v63/strict_v427_recruitment"
CHECKOUT_ROOT = MZX_ROOT / "external_repos/experiment64_scientific"
LEAN_DOJO_CACHE_ROOT = Path(os.environ.get(
    "LEAN_DOJO_CACHE_ROOT", str(Path.home() / ".cache/lean_dojo")
)).resolve()

VERSION = 1
PROTOCOL_VERSION = "experiment64-strict-v427-32-repository-replication-v1"
MEASUREMENT_ENGINE_PROTOCOL = "experiment51-preregistered-external-repository-replication-v1"
TARGET_TOOLCHAIN = "leanprover/lean4:v4.27.0"
REPOSITORY_COUNT = 32
ROOTS_PER_REPOSITORY = 16
CANDIDATES_PER_ROOT = 23
ROOT_SELECTION_SEED = 640064
BOOTSTRAP_SEED = 640164
BOOTSTRAP_REPLICATES = 20_000
MAX_OPERATIONAL_REPOSITORY_ATTEMPTS = 2
GLOBAL_FREE_DISK_FLOOR_BYTES = 150 * 1024**3
PER_REPOSITORY_DISK_LIMIT_BYTES = 100 * 1024**3

CLAIM_BOUNDARY = (
    "The estimands describe immediate candidate-relative endpoint agreement for the "
    "prospectively frozen 32-repository strict-Lean-v4.27 frame. They are not "
    "ecosystem-wide prevalence estimates and do not establish whole-proof tactic equivalence."
)

PACKAGE_FILES = (
    "experiment64_protocol.py",
    "freeze_experiment64.py",
    "run_experiment64.py",
    "analyze_experiment64.py",
    "audit_experiment64.py",
    "export_experiment64.py",
    "run_experiment64_pipeline.py",
    "run_experiment64_server_safe.sh",
    "test_experiment64.py",
    "README_SERVER.md",
)

SOURCE_DEPENDENCIES = {
    "experiment63_strict_v427_recruitment/experiment63_protocol.py":
        "214ad70fb44760524188742323cafd24694878bac96b77d8b1c9cbe15fa11961",
    "experiment63_strict_v427_recruitment/experiment63_qualification_worker.py":
        "e6f220233846c739c6871c26bb8771035a5934537bba23d1ab31cc2a13acf738",
    "experiment51_external_repository_replication/experiment51_protocol.py":
        "6c8ded7b453d3f5bfe75fc916d9c990368f54b20e81e4d54915376d20a88655f",
    "experiment51_external_repository_replication/experiment51_trace_runtime.py":
        "45d99206470327a4933da05740d4553a90f96ac62b4bd42476037f2c6b73f5ee",
    "experiment51_external_repository_replication/screen_experiment51_repositories.py":
        "a76dede54b718122f63afc9682f2951b7768f783b3d98b0b73bc967cec08a47f",
    "experiment51_external_repository_replication/experiment51_enumeration_worker.py":
        "e68c9f336ade2604ff90bb814f877a14e19f43b34f85626e934ae906c5834155",
    "experiment51_external_repository_replication/experiment51_live_worker.py":
        "c472171177c29f48d9b633887656287a7f75fc54e8707bafb8205a925eb9e0b0",
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
        (str(seed) + "\0" + "\0".join(str(part) for part in parts)).encode("utf-8")
    ).hexdigest()


def seal(value: dict[str, Any]) -> dict[str, Any]:
    value["record_sha256"] = json_sha256(
        {key: item for key, item in value.items() if key != "record_sha256"}
    )
    return value


def assert_sealed(value: Mapping[str, Any], label: str) -> None:
    expected = json_sha256(
        {key: item for key, item in value.items() if key != "record_sha256"}
    )
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


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def safe_slug(slug: str) -> str:
    value = slug.replace("/", "__")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+", value):
        raise ValueError(f"unsafe GitHub slug: {slug}")
    return value


def quantile(values: Sequence[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = min(len(ordered) - 1, max(0, int(p * len(ordered))))
    return ordered[index]


def implementation_locks() -> list[dict[str, Any]]:
    rows = []
    for name in PACKAGE_FILES:
        path = PACKAGE_ROOT / name
        if not path.is_file():
            raise FileNotFoundError(path)
        rows.append({"path": name, "bytes": path.stat().st_size, "sha256": file_sha256(path)})
    return rows


def source_locks() -> list[dict[str, Any]]:
    rows = []
    for relative, expected in SOURCE_DEPENDENCIES.items():
        path = MZX_ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = file_sha256(path)
        if observed != expected:
            raise ValueError(f"required dependency changed: {relative} sha256={observed}")
        rows.append({"path": relative, "bytes": path.stat().st_size, "sha256": observed})
    return rows


def validate_locks(protocol: Mapping[str, Any]) -> None:
    if list(protocol.get("implementation_locks", [])) != implementation_locks():
        raise ValueError("Exp64 implementation changed after freeze")
    if list(protocol.get("source_locks", [])) != source_locks():
        raise ValueError("Exp64 source dependency changed after freeze")


def ensure_scoped_path(path: Path, root: Path) -> Path:
    resolved_root = root.resolve()
    resolved = path.resolve(strict=False)
    if resolved == resolved_root or not resolved.is_relative_to(resolved_root):
        raise ValueError(f"path escaped scoped root: {resolved}")
    return resolved


def target_identity(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "slug", "commit", "file_path", "full_name", "theorem_id", "rid",
        "source_file_sha256", "target_pos", "target_end_pos", "authored_tactic",
        "trace_root_state_sha256", "trace_state_after_sha256", "ast_record_index",
        "ast_sha256",
    )
    return {key: row.get(key) for key in keys}
