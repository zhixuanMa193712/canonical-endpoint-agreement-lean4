"""Protocol primitives for strict, disk-bounded Lean-v4.27 recruitment."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


PACKAGE_ROOT = Path(__file__).resolve().parent
MZX_ROOT = Path(os.environ.get("MZX_ROOT", PACKAGE_ROOT.parent)).resolve()
ARTIFACT_ROOT = MZX_ROOT / "artifacts/v63/strict_v427_recruitment"
SOURCE61_ROOT = MZX_ROOT / "artifacts/v61/archival_v427_infrastructure_recovery"
CHECKOUT_ROOT = MZX_ROOT / "external_repos/experiment63_qualification"
STATIC_CHECKOUT_ROOT = MZX_ROOT / "external_repos/experiment63_static_prefilter"

VERSION = 1
PROTOCOL_VERSION = "experiment63-strict-current-v427-recruitment-v1"
TARGET_TOOLCHAIN = "leanprover/lean4:v4.27.0"
TARGET_REPOSITORIES = 38
MIN_STATIC_TACTIC_ROOTS = 16
MIN_TRACE_ROOTS = 16
MAX_AUTHORED_REPLAY_ROOTS = 24
SOURCE_OVERLAP_THRESHOLD = 0.20
FRAME_ORDER_SEED = 630001
REPLAY_ROOT_SEED = 630002

# Resource rules are deliberately conservative.  Qualification is serial, so
# the observed filesystem-free delta belongs to one Exp63 checkout unless an
# unrelated process writes concurrently; the pipeline therefore waits for
# Exp62 by default.
GLOBAL_FREE_DISK_FLOOR_BYTES = 150 * 1024**3
PER_REPOSITORY_DISK_LIMIT_BYTES = 100 * 1024**3
STATIC_CHECKOUT_LIMIT_BYTES = 2 * 1024**3
SEARCH_LEAF_LIMIT = 900
SEARCH_PER_PAGE = 100
SEARCH_WORKERS = 48
STATIC_WORKERS = 4

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
HISTORICAL_SCIENTIFIC_REPOSITORIES_LOWER = {
    value.lower() for value in HISTORICAL_SCIENTIFIC_REPOSITORIES
}

GITHUB_STAR_QUERIES = (
    "language:Lean fork:false archived:false stars:0..2",
    "language:Lean fork:false archived:false stars:3..9",
    "language:Lean fork:false archived:false stars:10..49",
    "language:Lean fork:false archived:false stars:>=50",
)
ROOT_LICENSE_NAMES = (
    "LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "LICENCE.md",
    "LICENCE.txt", "COPYING", "COPYING.md",
)
ROOT_LAKEFILE_NAMES = ("lakefile.toml", "lakefile.lean")
EXCLUDED_SOURCE_PARTS = {
    ".git", ".lake", "lake-packages", "build", "vendor", "vendored",
    "generated", "benchmark", "benchmarks", "deps", "dependencies",
    "test", "tests", "examples", "example",
}

OPERATIONAL_ERROR_RE = re.compile(
    r"no space left on device|errno 28|timed out|timeout|temporary failure|"
    r"connection reset|connection refused|could not resolve|name resolution|"
    r"network is unreachable|tls|ssl|http(?:s)? error|remote end hung up|"
    r"early eof|external command ['\"]git['\"] exited with code 128|"
    r"modified named section was absent|parser_compatibility|AssertionError|"
    r"isolated enumeration failed|LeanDojo trace failed|0 ast|zero ast|"
    r"resource limit|disk budget|worker failed without|broken pipe",
    re.IGNORECASE,
)

PACKAGE_FILES = (
    "experiment63_protocol.py",
    "freeze_experiment63.py",
    "snapshot_strict_v427_frame.py",
    "strict_static_prefilter.py",
    "freeze_experiment63_frame.py",
    "experiment63_qualification_worker.py",
    "run_experiment63.py",
    "audit_experiment63.py",
    "test_experiment63_static.py",
    "run_experiment63_server_safe.sh",
    "README_SERVER.md",
)
SOURCE_DEPENDENCIES = (
    "experiment51_external_repository_replication/experiment51_protocol.py",
    "experiment51_external_repository_replication/experiment51_trace_runtime.py",
    "experiment51_external_repository_replication/screen_experiment51_repositories.py",
    "experiment51_external_repository_replication/experiment51_enumeration_worker.py",
    "experiment51_external_repository_replication/experiment51_live_worker.py",
)
EXPECTED_SOURCE_SHA256 = {
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


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
    for relative in SOURCE_DEPENDENCIES:
        path = MZX_ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        digest = file_sha256(path)
        if digest != EXPECTED_SOURCE_SHA256[relative]:
            raise ValueError(f"required Exp51 source dependency changed: {relative} sha256={digest}")
        rows.append({"path": relative, "bytes": path.stat().st_size, "sha256": digest})
    return rows


def validate_locks(protocol: Mapping[str, Any]) -> None:
    if list(protocol.get("implementation_locks", [])) != implementation_locks():
        raise ValueError("Exp63 implementation changed after freeze")
    if list(protocol.get("source_locks", [])) != source_locks():
        raise ValueError("Exp63 source dependency changed after freeze")


def error_text(receipt: Mapping[str, Any]) -> str:
    pieces = [str(receipt.get("error", {}).get("message", ""))]
    for section in ("build", "trace", "cache_get"):
        row = receipt.get(section)
        if isinstance(row, Mapping):
            pieces.extend((str(row.get("stdout_tail", "")), str(row.get("stderr_tail", ""))))
    return "\n".join(pieces)


def classify_build_trace_receipt(receipt: Mapping[str, Any] | None) -> tuple[str, str]:
    """Return (status, reason) without converting infrastructure failures to hard failures."""
    if receipt is None:
        return "operationally_unresolved", "missing_receipt"
    if receipt.get("build_trace_gate") is True:
        return "build_trace_pass", "passed"
    gate = str(receipt.get("first_failed_gate") or "missing_gate")
    message = error_text(receipt)
    if OPERATIONAL_ERROR_RE.search(message):
        return "operationally_unresolved", f"operational_{gate}"
    if gate in {"checkout", "trace", "root_enumeration"}:
        return "operationally_unresolved", f"operational_{gate}"
    if gate == "unmodified_build" and re.search(
        r"external command ['\"]git['\"]|fatal:|clone|fetch|checkout revision",
        message, re.IGNORECASE,
    ):
        return "operationally_unresolved", "operational_dependency_fetch"
    if gate in {
        "archival_license", "minimum_pre_replay_frame", "exact_toolchain",
        "lean_version", "unmodified_build", "unchanged_checkout",
    }:
        return "definitive_ineligible", gate
    return "operationally_unresolved", f"unclassified_{gate}"


def allocated_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for candidate in [path, *path.rglob("*")]:
        try:
            stat = candidate.lstat()
        except FileNotFoundError:
            continue
        total += int(getattr(stat, "st_blocks", 0)) * 512
    return total


def ensure_scoped_path(path: Path, root: Path) -> Path:
    resolved_root = root.resolve()
    resolved = path.resolve(strict=False)
    if resolved == resolved_root or not resolved.is_relative_to(resolved_root):
        raise ValueError(f"path escaped scoped root: {resolved}")
    return resolved
