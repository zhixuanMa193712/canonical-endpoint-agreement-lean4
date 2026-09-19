"""Protocol primitives for Experiment 51 external repository replication.

The module separates zero-candidate repository screening from the frozen
scientific execution.  Exp51 measures state-conditioned one-step executable
effects in new repositories; it never treats the result as global tactic
equivalence or proof-strategy equivalence.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

PACKAGE_ROOT = Path(__file__).resolve().parent
SERVER_ROOT = Path(os.environ.get("MZX_ROOT", PACKAGE_ROOT.parent)).resolve()
ARTIFACT_ROOT = SERVER_ROOT / "artifacts/v51/external_repository_replication"
SOURCE_FIX0_ROOT = Path(os.environ.get(
    "MZX_EXP51_FIX0_ROOT",
    SERVER_ROOT / "artifacts/v51/external_repository_replication_preflight_failed_fix0_archive_20260822",
)).resolve()
SOURCE_FIX1_ROOT = Path(os.environ.get(
    "MZX_EXP51_FIX1_ROOT",
    SERVER_ROOT / "artifacts/v51/external_repository_replication_preflight_failed_fix1_archive_20260822",
)).resolve()
SOURCE_FIX2_ROOT = Path(os.environ.get(
    "MZX_EXP51_FIX2_ROOT",
    SERVER_ROOT / "artifacts/v51/external_repository_replication_preflight_failed_fix2_archive_20260822",
)).resolve()
SOURCE_FIX3_ROOT = Path(os.environ.get(
    "MZX_EXP51_FIX3_ROOT",
    SERVER_ROOT / "artifacts/v51/external_repository_replication_preflight_failed_fix3_archive_20260822",
)).resolve()
SOURCE_FIX4_ROOT = Path(os.environ.get(
    "MZX_EXP51_FIX4_ROOT",
    SERVER_ROOT / "artifacts/v51/external_repository_replication_preflight_failed_fix4_archive_20260823",
)).resolve()
SOURCE_FIX4_PACKAGE = Path(os.environ.get(
    "MZX_EXP51_FIX4_PACKAGE",
    SERVER_ROOT / "experiment51_external_repository_replication_fix4_python_only.zip",
)).resolve()
SOURCE_FIX4_PACKAGE_SHA256 = "42a5ef95e5c4a4eb212772013745dc995dd47d4b67a4c75dfe3f4f0a8512942c"
SOURCE_FIX5_ROOT = Path(os.environ.get(
    "MZX_EXP51_FIX5_ROOT",
    SERVER_ROOT / "artifacts/v51/external_repository_replication_preflight_failed_fix5_archive_20260823",
)).resolve()
SOURCE_FIX5_PACKAGE = Path(os.environ.get(
    "MZX_EXP51_FIX5_PACKAGE",
    SERVER_ROOT / "experiment51_external_repository_replication_fix5_python_only.zip",
)).resolve()
SOURCE_FIX5_PACKAGE_SHA256 = "b5af49ef672a339828457bc017ed2261d505777e6fac9cfa973121b38dacfa36"
SOURCE_FIX6_ROOT = Path(os.environ.get(
    "MZX_EXP51_FIX6_ROOT",
    SERVER_ROOT / "artifacts/v51/external_repository_replication_preflight_failed_fix6_archive_20260823",
)).resolve()
SOURCE_FIX6_PACKAGE = Path(os.environ.get(
    "MZX_EXP51_FIX6_PACKAGE",
    SERVER_ROOT / "experiment51_external_repository_replication_fix6_python_only.zip",
)).resolve()
SOURCE_FIX6_PACKAGE_SHA256 = "aeb2ee52bb6a8418989975ad0a0bd19b15b356138ac9b84064559eac16b9fcd2"
SOURCE_FIX7_ROOT = Path(os.environ.get(
    "MZX_EXP51_FIX7_ROOT",
    SERVER_ROOT / "artifacts/v51/external_repository_replication_preflight_failed_fix7_archive_20260823",
)).resolve()
SOURCE_FIX7_PACKAGE = Path(os.environ.get(
    "MZX_EXP51_FIX7_PACKAGE",
    SERVER_ROOT / "experiment51_external_repository_replication_fix7_python_only.zip",
)).resolve()
SOURCE_FIX7_PACKAGE_SHA256 = "af053f5f91bb2452f0d6bb7716f84ce879de484a17308aacf9d6601feaa897aa"
SOURCE_FIX8_ROOT = Path(os.environ.get(
    "MZX_EXP51_FIX8_ROOT",
    SERVER_ROOT / "artifacts/v51/external_repository_replication_recruitment_incomplete_fix8_archive_20260823",
)).resolve()
SOURCE_FIX8_PACKAGE = Path(os.environ.get(
    "MZX_EXP51_FIX8_PACKAGE",
    SERVER_ROOT / "experiment51_external_repository_replication_fix8_python_only.zip",
)).resolve()
SOURCE_FIX8_PACKAGE_SHA256 = "af592254cb03a200f5412e478f88754dbc1df96f3d97b16979668a3a6f94e0ac"
SCREEN_CHECKOUT_ROOT = SERVER_ROOT / "external_repos/experiment51_screen"
SOURCE_EXP49_ROOT = SERVER_ROOT / "artifacts/v49/candidate_endpoint_robustness"
SOURCE_EXP50_ROOT = SERVER_ROOT / "artifacts/v50/independent_reexecution"
SOURCE_EXP49_CONFIG = SOURCE_EXP49_ROOT / "frozen/experiment49_config.json"
SOURCE_EXP49_ANALYSIS = SOURCE_EXP49_ROOT / "analysis/summary.json"
SOURCE_EXP50_SUMMARY = SOURCE_EXP50_ROOT / "analysis_fix1/summary.json"
SOURCE_EXP50_EXPORT = SOURCE_EXP50_ROOT / "export_fix1/receipt.json"
RAID_DATA_ROOT = SERVER_ROOT / "raid/data"

PROTOCOL_VERSION = "experiment51-preregistered-external-repository-replication-v1"
RECRUITMENT_VERSION = "experiment51-zero-candidate-recruitment-fix9"
MECHANICAL_FIX_ID = "exp51-recruitment-fix9-fix3-exact-section-header-modifiers"
TRACE_RUNTIME_VERSION = "exp51-trace-runtime-lean-dojo-4.20.0-v427-adapter-v3"
WORKER_SCHEMA = "experiment51-live-tacticinfo-worker-record-v1"
STRICT_ENDPOINT_SCHEMA = "exp49-strict-goal-structure-v1"
TARGET_LEAN_VERSION = "v4.27.0"
TARGET_TOOLCHAIN = "leanprover/lean4:v4.27.0"
TARGET_REPOSITORIES = 16
MIN_REPOSITORIES = 12
ROOTS_PER_REPOSITORY = 48
CANDIDATES_PER_ROOT = 23
MASTER_SAMPLE_SEED = 510051
BOOTSTRAP_SEED = 510151
BOOTSTRAP_REPLICATES = 20_000
PRIMARY_DELTA = 0.20
ROBUST_DELTA = 0.10
MAX_CI_HALFWIDTH = 0.10
MIN_OVERALL_EVALUABILITY = 0.95
MIN_REPOSITORY_EVALUABILITY = 0.90
QUALIFICATION_REPOSITORY_WORKERS = 26
QUALIFICATION_THREADS_PER_REPOSITORY = 2
QUALIFICATION_BUILD_WORKERS = 4
QUALIFICATION_ENUMERATION_WORKERS = 4
QUALIFICATION_GLOBAL_TRACE_PROCESS_CAP = 52
QUALIFICATION_ENUMERATION_ISOLATION = "one-fresh-python-process-per-repository"
QUALIFICATION_ENUMERATION_TIMEOUT = 7200
V427_POSITION_ADAPTER_SCHEMA = "lean-v4.27-string-pos-raw-byteIdx-v1"
V427_PARSER_COMPATIBILITY_SCHEMA = (
    "lean-v4.27-exact-sectionHeader-modifiers-standard-crlf-v3"
)
TRACE_REUSE_SCHEMA = "exp51-fix4-content-addressed-trace-reuse-v1"
PARSER_COMPATIBILITY_EXPECTED = {
    "repositories": 15,
    "section_nodes": 742,
    "named_sections": 380,
    "unnamed_sections": 362,
    "legacy_sections": 0,
    "plain_header_sections": 451,
    "noncomputable_header_sections": 4,
    "public_header_sections": 135,
    "public_meta_header_sections": 43,
    "expose_public_header_sections": 107,
    "expose_public_meta_header_sections": 2,
    # Five of the seven checkout CRLF files have reused AST artifacts and are
    # consequently instantiated by LeanDojo's parser.  The other two remain
    # covered by the separate complete-source inventory gate below.
    "traced_standard_crlf_files": 5,
    "traced_standard_crlf_lines": 2470,
    "position_rejections": 0,
    "section_rejections": 0,
    "header_rejections": 0,
    "crlf_rejections": 0,
}
CHECKOUT_LINE_ENDING_EXPECTED = {
    "repositories": 15,
    "standard_crlf_files": 7,
    "standard_crlf_lines": 3460,
    "line_ending_rejections": 0,
}
FIX8_FRAME_CONTROLS = {
    "bergmannjg/Regex": 333,
    "dissensus-ai/lean-formalizations": 218,
}
PARSER_ADAPTER_PREFLIGHT_REPOSITORIES = (
    "AfonsoBitoque/LeanServer",
    "PatrickMassot/GlimpseOfLean",
    "bergmannjg/Regex",
    "dissensus-ai/lean-formalizations",
)
RECOVERY_ENUMERATION_WORKERS = 4
RECOVERY_ENUMERATION_TIMEOUT = 7200
RECOVERY_CAPACITY_PROFILE = "four-python-parser-trace-reuse-v1"
PARSER_EXECUTION_PROFILE = "single-process-in-memory-v427-adapter-no-ray-v1"

ALTERNATIVE_LIBRARY = [
    "rfl", "assumption", "trivial", "contradiction", "simp", "simpa",
    "simp_all", "aesop", "aesop?", "norm_num", "omega", "linarith",
    "nlinarith", "ring", "ring_nf", "positivity", "decide",
    "native_decide", "constructor", "ext", "fun_prop", "solve_by_elim",
    "exact?", "apply_assumption", "tauto", "left", "right", "intro",
    "intros", "all_goals simp", "all_goals aesop",
    "first | rfl | assumption",
]

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

GENERATED_ID_RE = re.compile(r"(?:(?:\\?m\\.|_uniq\\.|_let_match\\.|_match\\.)\\d+|✝\\d*)")
WS_RE = re.compile(r"[ \\t]+")


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
        tmp = p.with_name(p.name + f".{os.getpid()}.{uuid.uuid4().hex}.tmp")
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
    return re.split(r"[\\s\\[({|;]+", s, maxsplit=1)[0] or "<empty>"


def tactic_family(tactic: str) -> str:
    head = tactic_head(tactic)
    return FAMILY_BY_HEAD.get(head, f"other:{head}")


def safe_slug(slug: str) -> str:
    return slug.replace("/", "__")


def stable_seed(*parts: Any, master: int = MASTER_SAMPLE_SEED) -> int:
    raw = json.dumps([master, *parts], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return int(hashlib.sha256(raw.encode()).hexdigest()[:16], 16)


def expected_alternatives(authored: str) -> list[str]:
    return [x for x in ALTERNATIVE_LIBRARY if x != authored][:CANDIDATES_PER_ROOT]


def genealogy_for(tactic: str) -> dict[str, str]:
    return dict(CANDIDATE_GENEALOGY.get(tactic, CANDIDATE_GENEALOGY.get(
        tactic_head(tactic), {"class": "unresolved", "group": f"unresolved:{tactic_head(tactic)}"})))


def select_candidate_view(alternatives: Sequence[str], view: str) -> list[str]:
    if view == "L0":
        return list(alternatives)
    if view != "L-mechanism-diverse":
        raise KeyError(view)
    out: list[str] = []
    seen: set[str] = set()
    for tactic in alternatives:
        meta = genealogy_for(tactic)
        if meta["class"] in {"direct_suggestion", "direct_control_wrapper"}:
            continue
        if meta["group"] not in seen:
            seen.add(meta["group"])
            out.append(tactic)
    return out


def endpoint_payload(raw_state: str, strict_state: str, goal_count: int) -> dict[str, Any]:
    text_state = normalize_goal_text(raw_state)
    raw = {"schema": "exp51-raw-endpoint-v1", "state": raw_state,
           "goal_count": goal_count, "terminal": goal_count == 0}
    text = {"schema": "exp49-text48-endpoint-v1", "state": text_state,
            "goal_count": goal_count, "terminal": goal_count == 0}
    struct = {"schema": STRICT_ENDPOINT_SCHEMA, "state": strict_state,
              "goal_count": goal_count, "terminal": goal_count == 0}
    return {kind: {"value": value, "sha256": json_sha256(value)}
            for kind, value in (("raw", raw), ("text48", text), ("struct", struct))}


def compact_endpoint(root: Path, endpoint: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for kind in ("raw", "text48", "struct"):
        entry = dict(endpoint[kind])
        value = dict(entry.pop("value"))
        state = str(value.pop("state"))
        out[kind] = {**entry, "state": store_text(root, f"endpoint_{kind}", state),
                     "metadata": value}
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
        raise ValueError("Exp51 code-lock metadata changed")
    for row in rows:
        p = Path(row["path"])
        if not p.is_file() or p.stat().st_size != int(row["bytes"]) or file_sha256(p) != row["sha256"]:
            raise ValueError(f"Exp51 locked source changed: {p}")


def tail_text(value: Any, size: int) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value or "")[-size:]


def quantile(values: Sequence[float], p: float) -> float:
    if not values:
        return 0.0
    xs = sorted(float(x) for x in values)
    index = min(len(xs) - 1, max(0, int(p * len(xs))))
    return xs[index]


def deterministic_sample(rows: Sequence[Mapping[str, Any]], slug: str,
                         count: int = ROOTS_PER_REPOSITORY) -> list[dict[str, Any]]:
    ordered = sorted((dict(x) for x in rows), key=lambda x: (
        x["file_path"], x["full_name"], x["target_pos"], x["target_end_pos"], x["theorem_id"]))
    rng = random.Random(stable_seed(slug, "root-sample"))
    indices = sorted(rng.sample(range(len(ordered)), count))
    return [ordered[i] for i in indices]
