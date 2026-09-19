"""Shared protocol and immutable helpers for Experiment 49.

Exp49 is a post-hoc candidate-robustness and endpoint construct-validity
study over the exact 96 Exp48 confirmation roots.  It never writes inside the
Exp48 artifact tree.  The server package is expected at
``/home/music/mzz/MZX/experiment49_candidate_endpoint_robustness`` beside the
original Exp48 source files and ``artifacts`` directory.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

PACKAGE_ROOT = Path(__file__).resolve().parent
SERVER_ROOT = Path(os.environ.get("MZX_ROOT", PACKAGE_ROOT.parent)).resolve()

PROTOCOL_VERSION = "experiment49-candidate-endpoint-robustness-v1"
MECHANICAL_FIX_ID = "exp49-preflight-fix1-lean-do-layout"
STRICT_ENDPOINT_SCHEMA = "exp49-strict-goal-structure-v1"
ARTIFACT_ROOT = SERVER_ROOT / "artifacts/v49/candidate_endpoint_robustness"
SOURCE_EXP48_ROOT = SERVER_ROOT / "artifacts/v48/live_tacticinfo_counterfactual_equivalence"
SOURCE_EXP48_CONFIG = SOURCE_EXP48_ROOT / "frozen/experiment48_config.json"
SOURCE_EXP48_CONFIRMATION = SOURCE_EXP48_ROOT / "confirmation_fix1/summary.json"
RAID_DATA_ROOT = SERVER_ROOT / "raid/data"

TARGET_LEAN_VERSION = "v4.27.0"
TARGET_TOOLCHAIN = "leanprover/lean4:v4.27.0"
CONFIRMATION_REPOSITORIES = 4
ROOTS_PER_REPOSITORY = 24
ALTERNATIVE_BUDGET = 23

RAREFACTION_BUDGETS = (4, 8, 12, 16, 23)
RAREFACTION_REPLICATES = 1000
RAREFACTION_SEED = 490049
BOOTSTRAP_REPLICATES = 10000
BOOTSTRAP_SEED = 490149

CANDIDATE_VIEWS = (
    "L0",
    "L-no-question",
    "L-no-aesop",
    "L-no-aesop-question",
    "L-no-aesop-pair",
    "L-no-direct-wrapper",
    "L-mechanism-diverse",
)
ENDPOINT_KINDS = ("raw", "text48", "struct")

SOURCE_EXP48_PROTOCOL_VERSION = "experiment48-live-tacticinfo-counterfactual-equivalence-v1"
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
    "all_goals": "control", "first": "control", "rw": "rewriting",
    "change": "goal_restatement", "have": "local_derivation", "exact": "exact_term",
    "apply": "application", "refine": "application",
}

# The grouping is intentionally conservative.  Only obvious suggestion/control
# wrappers and tactics sharing a documented engine are collapsed.  Everything
# else receives its own implementation group.  This file is frozen before the
# validation run; frequencies never enter the mapping.
CANDIDATE_GENEALOGY: dict[str, dict[str, str]] = {
    "rfl": {"class": "distinct_entry", "group": "rfl"},
    "assumption": {"class": "distinct_entry", "group": "assumption"},
    "trivial": {"class": "distinct_entry", "group": "trivial"},
    "contradiction": {"class": "distinct_entry", "group": "contradiction"},
    "simp": {"class": "shared_core", "group": "simp_engine"},
    "simpa": {"class": "shared_core", "group": "simp_engine"},
    "simp_all": {"class": "shared_core", "group": "simp_engine"},
    "aesop": {"class": "shared_core", "group": "aesop_engine"},
    "aesop?": {"class": "direct_suggestion", "group": "aesop_engine"},
    "norm_num": {"class": "distinct_entry", "group": "norm_num"},
    "omega": {"class": "distinct_entry", "group": "omega"},
    "linarith": {"class": "distinct_entry", "group": "linarith"},
    "nlinarith": {"class": "distinct_entry", "group": "nlinarith"},
    "ring": {"class": "shared_core", "group": "ring_engine"},
    "ring_nf": {"class": "shared_core", "group": "ring_engine"},
    "positivity": {"class": "distinct_entry", "group": "positivity"},
    "decide": {"class": "distinct_entry", "group": "decide"},
    "native_decide": {"class": "distinct_entry", "group": "native_decide"},
    "constructor": {"class": "distinct_entry", "group": "constructor"},
    "ext": {"class": "distinct_entry", "group": "ext"},
    "fun_prop": {"class": "distinct_entry", "group": "fun_prop"},
    "solve_by_elim": {"class": "distinct_entry", "group": "solve_by_elim"},
    "exact?": {"class": "direct_suggestion", "group": "exact_suggestion"},
    "apply_assumption": {"class": "distinct_entry", "group": "apply_assumption"},
    "tauto": {"class": "distinct_entry", "group": "tauto"},
    "left": {"class": "distinct_entry", "group": "left"},
    "right": {"class": "distinct_entry", "group": "right"},
    "intro": {"class": "shared_core", "group": "intro_engine"},
    "intros": {"class": "shared_core", "group": "intro_engine"},
    "all_goals simp": {"class": "direct_control_wrapper", "group": "simp_engine"},
    "all_goals aesop": {"class": "direct_control_wrapper", "group": "aesop_engine"},
    "first | rfl | assumption": {"class": "direct_control_wrapper", "group": "first_rfl_assumption"},
}

ROBUSTNESS_GATE = {
    "primary_view": "L-mechanism-diverse",
    "green_min_repositories_with_primary": 3,
    "green_min_repositories_with_nonterminal": 2,
    "amber_min_repositories_with_primary": 2,
}


def file_sha256(path: str | Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
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


def expected_alternatives(authored_tactic: str, library: Sequence[str],
                          budget: int = ALTERNATIVE_BUDGET) -> list[str]:
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
        raise ValueError("Exp49 code-lock metadata changed")
    for row in rows:
        p = Path(row["path"])
        if not p.is_file() or p.stat().st_size != int(row["bytes"]) or file_sha256(p) != row["sha256"]:
            raise ValueError(f"Exp49 locked source changed: {p}")


def endpoint_sha(endpoint: Mapping[str, Any] | None) -> str | None:
    return json_sha256(endpoint) if endpoint is not None else None


def genealogy_for(tactic: str) -> dict[str, str]:
    if tactic in CANDIDATE_GENEALOGY:
        return dict(CANDIDATE_GENEALOGY[tactic])
    head = tactic_head(tactic)
    if head in CANDIDATE_GENEALOGY:
        return dict(CANDIDATE_GENEALOGY[head])
    return {"class": "unresolved", "group": f"unresolved:{head}"}


def select_candidate_view(alternatives: Sequence[str], view: str) -> list[str]:
    xs = list(alternatives)
    if view == "L0":
        return xs
    if view == "L-no-question":
        return [x for x in xs if not tactic_head(x).endswith("?")]
    if view == "L-no-aesop":
        return [x for x in xs if tactic_head(x) != "aesop"]
    if view == "L-no-aesop-question":
        return [x for x in xs if tactic_head(x) != "aesop?"]
    if view == "L-no-aesop-pair":
        return [x for x in xs if tactic_head(x) not in {"aesop", "aesop?"}]
    if view == "L-no-direct-wrapper":
        return [
            x for x in xs
            if genealogy_for(x)["class"] not in {"direct_suggestion", "direct_control_wrapper"}
        ]
    if view == "L-mechanism-diverse":
        out: list[str] = []
        seen: set[str] = set()
        for x in xs:
            meta = genealogy_for(x)
            if meta["class"] in {"direct_suggestion", "direct_control_wrapper"}:
                continue
            group = meta["group"]
            if group not in seen:
                seen.add(group)
                out.append(x)
        return out
    raise KeyError(f"unknown candidate view: {view}")


def candidate_view_contract(library: Sequence[str]) -> dict[str, Any]:
    missing = [x for x in library if x not in CANDIDATE_GENEALOGY]
    if missing:
        raise ValueError(f"candidate genealogy is incomplete: {missing}")
    value = {
        "views": list(CANDIDATE_VIEWS),
        "genealogy": CANDIDATE_GENEALOGY,
        "robustness_gate": ROBUSTNESS_GATE,
        "library": list(library),
        "library_sha256": json_sha256(list(library)),
    }
    value["contract_sha256"] = json_sha256(value)
    return value


def validate_source_exp48(cfg: Mapping[str, Any], summary: Mapping[str, Any]) -> None:
    if cfg.get("protocol_version") != SOURCE_EXP48_PROTOCOL_VERSION:
        raise ValueError("Exp49 requires the exact Exp48 protocol config")
    if cfg.get("target_lean_version") != TARGET_LEAN_VERSION:
        raise ValueError("Exp49 requires Lean v4.27.0")
    if cfg.get("target_toolchain") != TARGET_TOOLCHAIN:
        raise ValueError("Exp49 requires the exact Lean v4.27.0 toolchain anchor")
    if int(cfg.get("alternative_budget", -1)) != ALTERNATIVE_BUDGET:
        raise ValueError("Exp49 requires the Exp48 23-alternative budget")
    split = cfg.get("repository_split") or {}
    if len(split.get("confirmation", [])) != CONFIRMATION_REPOSITORIES:
        raise ValueError("Exp49 requires four Exp48 confirmation repositories")
    if summary.get("phase") != "confirmation" or summary.get("scientific_metrics_authoritative") is not True:
        raise ValueError("Exp49 requires the authoritative Exp48 confirmation summary")
    if summary.get("confirmation_go") is not True:
        raise ValueError("Exp49 source Exp48 confirmation is not the archived Go result")
    if int(summary.get("repositories", -1)) != CONFIRMATION_REPOSITORIES:
        raise ValueError("Exp49 requires the four-repository Exp48 confirmation")
    if summary.get("candidate_library_sha256") != cfg.get("candidate_library_sha256"):
        raise ValueError("Exp48 source candidate-library hash mismatch")


def stable_seed(*parts: Any, master: int = RAREFACTION_SEED) -> int:
    payload = json.dumps([master, *parts], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16], 16)


def quantile(sorted_values: Sequence[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    idx = int(p * len(sorted_values))
    idx = max(0, min(len(sorted_values) - 1, idx))
    return float(sorted_values[idx])
