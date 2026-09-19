"""Experiment 48: live-TacticInfo exact-state counterfactual equivalence.

Exp48 is a separately frozen successor after Exp47 mechanics qualification.
It keeps the already-frozen eight-repository frame, theorem samples, 23-tactic
alternative budget, discovery/confirmation split, and inferential gates.  The
only scientific execution change is the backend: every branch starts from the
same live Lean ``ContextInfo + TacticInfo.mctxBefore + goalsBefore`` while the
unchanged source file is being elaborated by exact Lean v4.27.0.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

PROTOCOL_VERSION = "experiment48-live-tacticinfo-counterfactual-equivalence-v1"
ARTIFACT_ROOT = Path("artifacts/v48/live_tacticinfo_counterfactual_equivalence")
SOURCE_EXP46_ROOT = Path("artifacts/v46/eight_repo_cross_repository_executable_effect_equivalence")
SOURCE_EXP46_CONFIG = SOURCE_EXP46_ROOT / "frozen/experiment46_config.json"
SOURCE_EXP47_PROBE = Path("artifacts/v47_diagnostics/live_tacticinfo_branch_probe_fix4/summary.json")
RAID_DATA_ROOT = Path("/home/music/mzz/MZX/raid/data")

TARGET_LEAN_VERSION = "v4.27.0"
TARGET_TOOLCHAIN = "leanprover/lean4:v4.27.0"
EXPECTED_REPOSITORIES = 8
DISCOVERY_REPOSITORIES = 4
CONFIRMATION_REPOSITORIES = 4
TARGET_FORMAL_THEOREMS_PER_REPO = 24
ALTERNATIVE_BUDGET = 23
SMOKE_REPOSITORIES = 2
MIN_EVALUABLE_THEOREMS_PER_CONFIRMATION_REPO = 12

BOOTSTRAP_SEED = 480048
BOOTSTRAP_REPLICATES = 10000

CONFIRMATION_GATE = {
    "repositories": 4,
    "minimum_evaluable_theorems_each": 12,
    "minimum_repositories_with_nonzero_primary": 3,
    "repo_bootstrap_95ci_primary_lower_strictly_positive": True,
    "minimum_distinct_cross_head_pairs": 3,
    "minimum_repositories_with_nonterminal_signal": 2,
}

STRONG_GO_DIAGNOSTICS = {
    "minimum_repositories_with_cross_family_signal": 2,
    "minimum_head_pairs_replicating_in_at_least_two_repositories": 2,
}

GENERATED_ID_RE = re.compile(r"(?:(?:\?m\.|_uniq\.|_let_match\.|_match\.)\d+|✝\d*)")
WS_RE = re.compile(r"[ \t]+")

FAMILY_BY_HEAD = {
    "rfl": "reflexive_closure",
    "assumption": "context_closure",
    "trivial": "context_closure",
    "contradiction": "context_closure",
    "solve_by_elim": "context_closure",
    "apply_assumption": "context_closure",
    "simp": "simplification",
    "simpa": "simplification",
    "simp_all": "simplification",
    "aesop": "automation",
    "aesop?": "automation",
    "norm_num": "arithmetic_normalization",
    "omega": "arithmetic_decision",
    "linarith": "linear_arithmetic",
    "nlinarith": "nonlinear_arithmetic",
    "ring": "ring_normalization",
    "ring_nf": "ring_normalization",
    "positivity": "positivity",
    "decide": "decision",
    "native_decide": "decision",
    "constructor": "structural",
    "left": "structural",
    "right": "structural",
    "ext": "extensionality",
    "fun_prop": "function_property",
    "exact?": "suggestion",
    "intro": "binder",
    "intros": "binder",
    "all_goals": "control",
    "first": "control",
    "rw": "rewriting",
    "change": "goal_restatement",
    "have": "local_derivation",
    "exact": "exact_term",
    "apply": "application",
    "refine": "application",
}


def file_sha256(path: str | Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(chunk_size), b""):
            h.update(block)
    return h.hexdigest()


def json_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_json_dump(value: Any, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def atomic_jsonl_dump(rows: Iterable[Mapping[str, Any]], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def exclusive_create_json(path: str | Path, value: Mapping[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(dict(value), f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def safe_slug(slug: str) -> str:
    return slug.replace("/", "__")


def normalize_goal_text(text: Any) -> str:
    s = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
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


def expected_alternatives(authored_tactic: str, library: Sequence[str], budget: int = ALTERNATIVE_BUDGET) -> list[str]:
    return [x for x in library if x != authored_tactic][:budget]


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
        raise ValueError("Exp48 code-lock metadata changed")
    for row in rows:
        p = Path(row["path"])
        if not p.is_file() or p.stat().st_size != int(row["bytes"]) or file_sha256(p) != row["sha256"]:
            raise ValueError(f"Exp48 locked source changed: {p}")
