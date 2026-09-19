"""Frozen protocol primitives for Experiment 50 independent re-execution.

Exp50 re-executes the exact Exp48/Exp49 96-root population.  It measures exact
execution reproducibility and order/process isolation, not prevalence in new
mathematical data.  This module is self-contained and imports no Exp48/Exp49
runner or analysis implementation.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

PACKAGE_ROOT = Path(__file__).resolve().parent
SERVER_ROOT = Path(os.environ.get("MZX_ROOT", PACKAGE_ROOT.parent)).resolve()
ARTIFACT_ROOT = SERVER_ROOT / "artifacts/v50/independent_reexecution"
SOURCE_EXP48_ROOT = SERVER_ROOT / "artifacts/v48/live_tacticinfo_counterfactual_equivalence"
SOURCE_EXP49_ROOT = SERVER_ROOT / "artifacts/v49/candidate_endpoint_robustness"
SOURCE_EXP48_CONFIG = SOURCE_EXP48_ROOT / "frozen/experiment48_config.json"
SOURCE_EXP48_SUMMARY = SOURCE_EXP48_ROOT / "confirmation_fix1/summary.json"
SOURCE_EXP49_CONFIG = SOURCE_EXP49_ROOT / "frozen/experiment49_config.json"
SOURCE_EXP49_VALIDATION = SOURCE_EXP49_ROOT / "validation/execution_summary.json"
SOURCE_EXP49_ANALYSIS = SOURCE_EXP49_ROOT / "analysis/summary.json"
RAID_DATA_ROOT = SERVER_ROOT / "raid/data"

PROTOCOL_VERSION = "experiment50-independent-end-to-end-reexecution-v1"
WORKER_SCHEMA = "experiment50-independent-worker-record-v1"
STRICT_ENDPOINT_SCHEMA = "exp49-strict-goal-structure-v1"
TARGET_LEAN_VERSION = "v4.27.0"
TARGET_TOOLCHAIN = "leanprover/lean4:v4.27.0"
ROOTS = 96
REPOSITORIES = 4
ROOTS_PER_REPOSITORY = 24
CANDIDATES_PER_ROOT = 23
ORDER_MODES = ("M0", "M1", "M2", "M3", "M4")
ALL_MODES = (*ORDER_MODES, "M5")
RANDOM_ORDER_SEEDS = {"M2": 500052, "M3": 500053, "M4": 500054}
SMOKE_ROOTS = 2
SMOKE_M5_CANDIDATES_PER_ROOT = 2
EXP48_BOOTSTRAP_SEED = 480048
EXP48_BOOTSTRAP_REPLICATES = 10000

GENERATED_ID_RE = re.compile(r"(?:(?:\?m\.|_uniq\.|_let_match\.|_match\.)\d+|✝\d*)")
WS_RE = re.compile(r"[ \t]+")
FAMILY_BY_HEAD = {
    "rfl": "reflexive_closure", "assumption": "context_closure",
    "trivial": "context_closure", "contradiction": "context_closure",
    "solve_by_elim": "context_closure", "apply_assumption": "context_closure",
    "simp": "simplification", "simpa": "simplification", "simp_all": "simplification",
    "aesop": "automation", "aesop?": "automation", "norm_num": "arithmetic_normalization",
    "omega": "arithmetic_decision", "linarith": "linear_arithmetic",
    "nlinarith": "nonlinear_arithmetic", "ring": "ring_normalization",
    "ring_nf": "ring_normalization", "positivity": "positivity", "decide": "decision",
    "native_decide": "decision", "constructor": "structural", "left": "structural",
    "right": "structural", "ext": "extensionality", "fun_prop": "function_property",
    "exact?": "suggestion", "intro": "binder", "intros": "binder",
    "all_goals": "control", "first": "control",
    "rw": "rewriting", "change": "goal_restatement", "have": "local_derivation",
    "exact": "exact_term", "apply": "application", "refine": "application",
}


def file_sha256(path: str | Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            h.update(block)
    return h.hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def json_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_json_dump(value: Any, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, p)


def atomic_jsonl_dump(rows: Iterable[Mapping[str, Any]], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, p)


def exclusive_create_json(path: str | Path, value: Mapping[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(dict(value), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def store_text(root: str | Path, category: str, value: str) -> dict[str, Any]:
    sha = text_sha256(value)
    p = Path(root) / "content_store" / category / sha[:2] / f"{sha}.txt"
    if p.exists():
        if p.read_text(encoding="utf-8") != value:
            raise ValueError(f"content-address collision: {p}")
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(value, encoding="utf-8")
        os.replace(tmp, p)
    return {"sha256": sha, "bytes": len(value.encode("utf-8")), "path": str(p)}


def normalize_goal_text(value: Any) -> str:
    s = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    s = GENERATED_ID_RE.sub("<GEN>", s)
    return "\n".join(WS_RE.sub(" ", line.strip()) for line in s.splitlines() if line.strip())


def tactic_head(tactic: str) -> str:
    s = tactic.strip()
    if not s:
        return "<empty>"
    token = re.split(r"[\s\[({|;]+", s, maxsplit=1)[0]
    return token or "<empty>"


def tactic_family(tactic: str) -> str:
    head = tactic_head(tactic)
    return FAMILY_BY_HEAD.get(head, f"other:{head}")


def safe_slug(slug: str) -> str:
    return slug.replace("/", "__")


def theorem_file_id(theorem: Mapping[str, Any]) -> str:
    tid = str(theorem.get("theorem_id") or "")
    return tid[:20] if tid else json_sha256(
        {"full_name": theorem["full_name"], "root": theorem["trace_root_state_sha256"]}
    )[:20]


def expected_alternatives(authored: str, library: Sequence[str], budget: int = CANDIDATES_PER_ROOT) -> list[str]:
    return [x for x in library if x != authored][:budget]


def stable_seed(*parts: Any, master: int) -> int:
    payload = json.dumps([master, *parts], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16], 16)


def candidate_order(mode: str, original: Sequence[str], slug: str,
                    theorem_id: str, full_name: str) -> list[str]:
    values = list(original)
    if mode == "M0":
        return values
    if mode == "M1":
        return list(reversed(values))
    if mode in RANDOM_ORDER_SEEDS:
        rng = random.Random(stable_seed(slug, theorem_id, full_name,
                                       master=RANDOM_ORDER_SEEDS[mode]))
        rng.shuffle(values)
        return values
    if mode == "M5":
        return values
    raise KeyError(mode)


def endpoint_payload(raw_state: str, strict_state: str, goal_count: int) -> dict[str, Any]:
    text_state = normalize_goal_text(raw_state)
    raw_endpoint = {"schema": "exp50-raw-endpoint-v1", "state": raw_state,
                    "goal_count": goal_count, "terminal": goal_count == 0}
    text49 = {"schema": "exp49-text48-endpoint-v1", "state": text_state,
              "goal_count": goal_count, "terminal": goal_count == 0}
    text48 = {"state": text_state, "goal_count": goal_count, "terminal": goal_count == 0}
    strict49 = {"schema": STRICT_ENDPOINT_SCHEMA, "state": strict_state,
                "goal_count": goal_count, "terminal": goal_count == 0}
    return {
        "raw": {"value": raw_endpoint, "sha256": json_sha256(raw_endpoint)},
        "text48": {"value": text49, "sha256": json_sha256(text49),
                   "exp48_legacy_sha256": json_sha256(text48)},
        "struct": {"value": strict49, "sha256": json_sha256(strict49)},
    }


def compact_endpoint(root: Path, endpoint: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for kind in ("raw", "text48", "struct"):
        entry = dict(endpoint[kind])
        value = dict(entry.pop("value"))
        state = str(value.pop("state"))
        out[kind] = {
            **entry,
            "state": store_text(root, f"endpoint_{kind}", state),
            "metadata": value,
        }
    return out


def code_lock(paths: Sequence[str | Path]) -> dict[str, Any]:
    rows = []
    for raw in paths:
        p = Path(raw).resolve()
        if not p.is_file():
            raise FileNotFoundError(p)
        rows.append({"path": str(p), "sha256": file_sha256(p), "bytes": p.stat().st_size})
    return {"files": rows, "bundle_sha256": json_sha256(rows)}


def validate_code_lock(lock: Mapping[str, Any]) -> None:
    rows = list(lock.get("files", []))
    if json_sha256(rows) != lock.get("bundle_sha256"):
        raise ValueError("Exp50 code-lock metadata changed")
    for row in rows:
        p = Path(row["path"])
        if not p.is_file() or p.stat().st_size != int(row["bytes"]) or file_sha256(p) != row["sha256"]:
            raise ValueError(f"Exp50 locked source changed: {p}")


def tail_text(value: Any, size: int) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value or "")[-size:]
