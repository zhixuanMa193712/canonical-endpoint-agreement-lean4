"""Immutable primitives for the Exp62 solvable multi-step search evaluation."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PACKAGE_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(os.environ.get("MZX_ROOT", PACKAGE_ROOT.parent)).resolve()
ARTIFACT_ROOT = WORKSPACE_ROOT / "artifacts/v62/multistep_solvable_search_fix1"

VERSION = 1
PROTOCOL_VERSION = "experiment62-witness-injected-multistep-search-fix1-v1"
QUALIFICATION_SCHEMA = "experiment62-solvability-qualification-v1"
JOB_SCHEMA = "experiment62-policy-search-job-v1"

REPO_URL = "https://github.com/leanprover-community/mathlib4"
REPO_COMMIT = "29dcec074de168ac2bf835a77ef68bbe069194c5"
BENCHMARK_RELATIVE = Path("leandojo_benchmark_4/random/test.json")
BENCHMARK_SHA256 = "9f84ac4cbd5ea9031ab335d172e7a5b1873e4ac773721e60cb1a4cc5b4e2a0ae"
BENCHMARK_ROWS = 2_000

POLICIES = ("full", "effect_aware", "head_dedup", "fixed_budget_random")
STRATA = ("authored_depth_2", "authored_depth_3_to_6")
PILOT_FRAME_PER_STRATUM = 32
CONFIRMATION_FRAME_PER_STRATUM = 64
PILOT_ROOTS_PER_STRATUM = 8
CONFIRMATION_ROOTS_PER_STRATUM = 32
EXPECTED_FRAME_ROWS = 2 * (PILOT_FRAME_PER_STRATUM + CONFIRMATION_FRAME_PER_STRATUM)
EXPECTED_PILOT_ROOTS = 2 * PILOT_ROOTS_PER_STRATUM
EXPECTED_CONFIRMATION_ROOTS = 2 * CONFIRMATION_ROOTS_PER_STRATUM

MIN_WITNESS_DEPTH = 2
MAX_WITNESS_DEPTH = 6
WITNESS_INSERT_INDEX = 3  # the registered next step is rank four when recognized
MAX_TACTIC_TEXT_BYTES = 2_000
TACTIC_TIMEOUT_SECONDS = 30
QUALIFICATION_TIMEOUT_SECONDS = 1_800
POLICY_TIMEOUT_SECONDS = 240
# The original infrastructure pilot used POLICY_TIMEOUT_SECONDS + 180 as the
# outer process lifetime.  Three workers were terminated while LeanDojo was
# still opening a theorem, before any receipt could be written.  Fix1 keeps the
# 240-second scientific search budget unchanged but excludes repository/theorem
# initialization from it and registers a separate operational envelope.
DOJO_INITIALIZATION_TIMEOUT_SECONDS = 1_800
WORKER_FINALIZATION_GRACE_SECONDS = 120
POLICY_WORKER_OUTER_TIMEOUT_SECONDS = (
    DOJO_INITIALIZATION_TIMEOUT_SECONDS
    + POLICY_TIMEOUT_SECONDS
    + WORKER_FINALIZATION_GRACE_SECONDS
)
MAX_SEARCH_DEPTH = 6
MAX_EXPANDED_NODES = 32
MAX_TACTIC_INVOCATIONS = 768

FRAME_SEED = 620051
CANDIDATE_ORDER_SEED = 620052
POLICY_ORDER_SEED = 620053
RANDOM_POLICY_SEED = 620054
BOOTSTRAP_SEED = 620055
BOOTSTRAP_REPLICATES = 20_000
ONE_SIDED_Z = 1.6448536269514722
COVERAGE_NONINFERIORITY_MARGIN = 0.05
MIN_CONFIRMATION_FULL_MULTISTEP_SOLVES = 48
MIN_EFFICIENCY_COMPLETE_PAIRS = 60

# These programs are deliberately generic and fixed before any Exp62 Lean
# execution.  The root-specific authored witness tactics are added to them.
GENERIC_CANDIDATE_PANEL = (
    "rfl",
    "assumption",
    "solve_by_elim",
    "trivial",
    "contradiction",
    "simp",
    "simp only",
    "simp_all",
    "simpa",
    "aesop (config := { maxRuleApplications := 16 })",
    "aesop (config := { maxRuleApplications := 32 })",
    "norm_num",
    "omega",
    "linarith",
    "nlinarith",
    "ring",
    "ring_nf",
    "positivity",
    "constructor",
    "constructor <;> try assumption",
    "intro",
    "intro h",
    "ext",
    "fun_prop",
)

GENERATED_ID_RE = re.compile(
    r"(?:(?:\?m\.|_uniq\.|_let_match\.|_match\.)\d+|✝\d*)"
)
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
    raw = str(seed) + "\0" + "\0".join(map(str, parts))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
        raise ValueError(f"{label} record SHA changed")


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
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def normalize_goal_text(text: Any) -> str:
    """The registered text48-style endpoint key used for effect-aware pruning."""
    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    value = GENERATED_ID_RE.sub("<GEN>", value)
    return "\n".join(
        WS_RE.sub(" ", line.strip()) for line in value.splitlines() if line.strip()
    )


def endpoint_key(text: Any) -> str:
    return json_sha256({"canonicalizer": "text48_v1", "state": normalize_goal_text(text)})


def tactic_head(tactic: str) -> str:
    token = re.split(r"[\s\[({|;]+", tactic.strip(), maxsplit=1)[0]
    return token or "<empty>"


def forbidden_tactic(tactic: str) -> bool:
    lowered = tactic.lower()
    return (
        not tactic.strip()
        or len(tactic.encode("utf-8")) > MAX_TACTIC_TEXT_BYTES
        or "sorry" in lowered
        or "admit" in lowered
    )


def candidate_panel(target_id: str, witness_tactics: Sequence[str]) -> list[str]:
    unique = set(GENERIC_CANDIDATE_PANEL)
    unique.update(tactic for tactic in witness_tactics if not forbidden_tactic(tactic))
    return sorted(
        unique,
        key=lambda tactic: (
            selection_key(CANDIDATE_ORDER_SEED, target_id, tactic), tactic
        ),
    )


def ordered_candidates(
    panel: Sequence[str], next_witness_tactic: str | None
) -> list[str]:
    ordered = list(panel)
    if next_witness_tactic is None or next_witness_tactic not in ordered:
        return ordered
    ordered.remove(next_witness_tactic)
    ordered.insert(min(WITNESS_INSERT_INDEX, len(ordered)), next_witness_tactic)
    return ordered


def policy_order(target_id: str) -> list[str]:
    # A deterministic cyclic Latin square balances order exactly when each
    # four-root block is complete and nearly exactly otherwise.
    offset = int(selection_key(POLICY_ORDER_SEED, target_id)[:16], 16) % len(POLICIES)
    return [POLICIES[(offset + index) % len(POLICIES)] for index in range(len(POLICIES))]


def choose_children(
    policy: str,
    children: Sequence[Mapping[str, Any]],
    target_id: str,
    node_identity: str,
) -> list[Mapping[str, Any]]:
    rows = list(children)
    if policy == "full":
        return rows
    if policy == "effect_aware":
        key = lambda row: row["endpoint_key"]
    elif policy == "head_dedup":
        key = lambda row: row["head"]
    elif policy == "fixed_budget_random":
        effect_count = len(
            choose_children("effect_aware", rows, target_id, node_identity)
        )
        ranked = sorted(
            enumerate(rows),
            key=lambda pair: selection_key(
                RANDOM_POLICY_SEED,
                target_id,
                node_identity,
                pair[0],
                pair[1]["tactic"],
            ),
        )
        keep = {index for index, _ in ranked[:effect_count]}
        return [row for index, row in enumerate(rows) if index in keep]
    else:
        raise ValueError(f"unknown policy: {policy}")
    seen: set[str] = set()
    selected: list[Mapping[str, Any]] = []
    for row in rows:
        identity = str(key(row))
        if identity not in seen:
            seen.add(identity)
            selected.append(row)
    return selected


def wilson_upper(successes: int, n: int, z: float = ONE_SIDED_Z) -> float:
    if n <= 0:
        raise ValueError("Wilson interval requires a positive denominator")
    p = successes / n
    denominator = 1.0 + z * z / n
    center = p + z * z / (2.0 * n)
    radius = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))
    return (center + radius) / denominator


def validate_implementation_locks(protocol: Mapping[str, Any]) -> None:
    for row in protocol.get("implementation_locks", []):
        path = PACKAGE_ROOT / str(row["path"])
        if (
            not path.is_file()
            or path.stat().st_size != int(row["bytes"])
            or file_sha256(path) != row["sha256"]
        ):
            raise ValueError(f"Exp62 implementation changed: {path}")


def load_initial_protocol() -> dict[str, Any]:
    path = PACKAGE_ROOT / "frozen/initial_protocol.json"
    value = read_json(path)
    assert_sealed(value, "Exp62 initial protocol")
    if value.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("wrong Exp62 protocol version")
    validate_implementation_locks(value)
    frame = PACKAGE_ROOT / "frozen/candidate_frame.jsonl"
    if (
        not frame.is_file()
        or file_sha256(frame) != value.get("candidate_frame_sha256")
    ):
        raise ValueError("Exp62 candidate frame changed")
    return value


def load_installed_protocol(root: Path = ARTIFACT_ROOT) -> dict[str, Any]:
    value = read_json(root / "frozen/initial_protocol.json")
    assert_sealed(value, "installed Exp62 protocol")
    validate_implementation_locks(value)
    frame = root / "frozen/candidate_frame.jsonl"
    if file_sha256(frame) != value.get("candidate_frame_sha256"):
        raise ValueError("installed Exp62 candidate frame changed")
    return value
