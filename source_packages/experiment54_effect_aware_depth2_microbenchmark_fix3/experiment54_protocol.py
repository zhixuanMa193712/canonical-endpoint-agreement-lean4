"""Shared immutable protocol helpers for the Exp54 depth-2 microbenchmark."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping


VERSION = 1
PROTOCOL_VERSION = "experiment54-effect-aware-depth2-microbenchmark-v1"
EXECUTION_VERSION = "experiment54-effect-aware-depth2-microbenchmark-fix3"
MECHANICAL_FIX_ID = (
    "exp54-fix3-runtime-heartbeat-exception-boundary"
)
FREEZE_SCHEMA = "experiment54-frozen-depth2-design-v1"
CELL_SCHEMA = "experiment54-depth2-cell-plan-v1"
ROW_SCHEMA = "experiment54-depth2-cell-result-v1"
SOURCE_EXP49_SHA256 = "f57f6938c5de6d32339f2ca9e8cb2789ceed1dd2263feb7155ee76b35caefdc2"
SOURCE_EXP49_PROTOCOL = "experiment49-candidate-endpoint-robustness-v1"
SOURCE_EXP49_MEMBER_LIMIT_BYTES = 20 * 1024 * 1024
ROOTS_PER_REPOSITORY = 4
PROBES = [
    "rfl",
    "assumption",
    "simp",
    "simp_all",
    "omega",
    "constructor",
    "intro",
    "solve_by_elim",
]
REPOSITORIES = [
    "fpvandoorn/carleson",
    "ImperialCollegeLondon/FLT",
    "thefundamentaltheor3m/Sphere-Packing-Lean",
    "RemyDegenne/brownian-motion",
]
SHARD_COUNT = 16
LEAN_TIMEOUT_SECONDS = 900
COUNTERFACTUAL_MAX_HEARTBEATS = 2_000_000
EXPECTED_ROOTS = len(REPOSITORIES) * ROOTS_PER_REPOSITORY
EXPECTED_PAIRS = EXPECTED_ROOTS * 2
EXPECTED_FULL_CELLS = EXPECTED_PAIRS * 2 * len(PROBES)
EXPECTED_DEDUP_CELLS = (
    EXPECTED_ROOTS * len(PROBES)
    + EXPECTED_ROOTS * 2 * len(PROBES)
)
EXPECTED_CELLS = EXPECTED_FULL_CELLS + EXPECTED_DEDUP_CELLS


def server_root() -> Path:
    return Path(os.environ.get(
        "MZX_ROOT", Path(__file__).resolve().parents[1]
    )).resolve()


def artifact_root() -> Path:
    return server_root() / "artifacts/v54/effect_aware_depth2_microbenchmark_fix3"


def superseded_v1_root() -> Path:
    return server_root() / "artifacts/v54/effect_aware_depth2_microbenchmark"


def superseded_fix1_root() -> Path:
    return server_root() / "artifacts/v54/effect_aware_depth2_microbenchmark_fix1"


def superseded_fix2_root() -> Path:
    return server_root() / "artifacts/v54/effect_aware_depth2_microbenchmark_fix2"


def source_archive() -> Path:
    return server_root() / "experiment49_candidate_endpoint_robustness_results.zip"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def json_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def atomic_json_dump(value: Any, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=target.name + ".", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def atomic_jsonl_dump(rows: Iterable[Mapping[str, Any]], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=target.name + ".", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(canonical_bytes(row).decode("utf-8") + "\n")
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def exclusive_json_dump(value: Any, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")


def safe_slug(slug: str) -> str:
    return slug.replace("/", "__")


def record_sha(value: Mapping[str, Any]) -> str:
    return json_sha256({k: v for k, v in value.items() if k != "record_sha256"})


def seal(value: dict[str, Any]) -> dict[str, Any]:
    value["record_sha256"] = record_sha(value)
    return value


def assert_sealed(value: Mapping[str, Any], label: str) -> None:
    if value.get("record_sha256") != record_sha(value):
        raise ValueError(f"record SHA changed: {label}")


GENERATED_ID_RE = re.compile(
    r"(?:(?:\?m\.|_uniq\.|_let_match\.|_match\.)\d+|✝\d*)"
)
WS_RE = re.compile(r"[ \t]+")


def normalize_goal_text(value: Any) -> str:
    """Use the byte-for-byte Exp49/Exp48 text endpoint normalizer."""
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    text = GENERATED_ID_RE.sub("<GEN>", text)
    return "\n".join(
        WS_RE.sub(" ", line.strip())
        for line in text.splitlines()
        if line.strip()
    )


def endpoint_value(state: Any, goal_count: int, kind: str) -> dict[str, Any]:
    rendered = normalize_goal_text(state) if kind == "text48" else str(state)
    return {
        "schema": (
            "exp49-strict-goal-structure-v1" if kind == "struct"
            else f"exp49-{kind}-endpoint-v1"
        ),
        "state": rendered,
        "goal_count": int(goal_count),
        "terminal": int(goal_count) == 0,
    }


def endpoint_map(raw_state: str, strict_state: str, goal_count: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for kind, state in (
        ("raw", raw_state), ("text48", raw_state), ("struct", strict_state)
    ):
        value = endpoint_value(state, goal_count, kind)
        out[kind] = {"sha256": json_sha256(value), "value": value}
    return out


def compact_endpoint(root: Path, endpoint: Mapping[str, Any]) -> dict[str, Any]:
    value = endpoint["value"]
    state = str(value["state"])
    state_bytes = state.encode("utf-8")
    state_sha = bytes_sha256(state_bytes)
    path = root / "content" / state_sha[:2] / f"{state_sha}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if file_sha256(path) != state_sha:
            raise ValueError("content-addressed endpoint collision")
    else:
        path.write_bytes(state_bytes)
    return {
        "sha256": endpoint["sha256"],
        "schema": value["schema"],
        "goal_count": int(value["goal_count"]),
        "terminal": value["terminal"] is True,
        "state": {
            "sha256": state_sha,
            "bytes": len(state_bytes),
            "path": str(path),
        },
    }


def outcome_signature(row: Mapping[str, Any]) -> dict[str, Any]:
    value = {
        "probe_status": row.get("probe_status"),
        "failure_category": row.get("failure_category"),
    }
    if row.get("probe_status") == "success":
        endpoint = row["probe_endpoint"]
        value.update({
            "raw_sha256": endpoint["raw"]["sha256"],
            "text48_sha256": endpoint["text48"]["sha256"],
            "strict_sha256": endpoint["struct"]["sha256"],
            "goal_count": endpoint["struct"]["goal_count"],
            "terminal": endpoint["struct"]["terminal"],
        })
    return value


def code_sources() -> list[Path]:
    here = Path(__file__).resolve().parent
    return sorted(
        p for p in here.iterdir()
        if p.is_file() and (p.suffix == ".py" or p.suffix == ".md")
        and p.name != "PACKAGE_MANIFEST.json"
    )


def code_lock() -> dict[str, str]:
    return {p.name: file_sha256(p) for p in code_sources()}


def validate_code_lock(frozen: Mapping[str, Any]) -> None:
    expected = dict(frozen.get("code_lock", {}))
    current = code_lock()
    if current != expected:
        changed = sorted(set(current) | set(expected))
        raise ValueError(f"Exp54 code lock changed: {changed}")


def load_freeze(root: Path | None = None) -> dict[str, Any]:
    base = (root or artifact_root()).resolve()
    value = read_json(base / "frozen/design.json")
    if not (
        value.get("schema") == FREEZE_SCHEMA
        and value.get("protocol_version") == PROTOCOL_VERSION
        and value.get("execution_version") == EXECUTION_VERSION
        and value.get("mechanical_fix_id") == MECHANICAL_FIX_ID
        and value.get("record_sha256") == record_sha(value)
    ):
        raise ValueError("wrong or changed Exp54 freeze")
    validate_code_lock(value)
    return value


def repository_checkout(slug: str) -> Path:
    return (
        server_root()
        / "external_repos/experiment44r8_exact_v4_27_0_checkout_dependency_fix1/formal"
        / safe_slug(slug)
    ).resolve()


def exact_binomial_zero_upper(n: int, alpha: float = 0.05) -> float | None:
    if n <= 0:
        return None
    return 1.0 - alpha ** (1.0 / n)
