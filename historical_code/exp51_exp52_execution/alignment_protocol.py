"""Shared protocol and integrity helpers for the pre-candidate Fix3 amendment.

Fix3 does not replace the already frozen Exp51 sample or Exp52 v0.1 design.
It adds a content-locked execution implementation before the first Exp51
scientific candidate is run.  The source Fix2 freeze remains immutable.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

PACKAGE_ROOT = Path(__file__).resolve().parent
SERVER_ROOT = Path(os.environ.get("MZX_ROOT", str(PACKAGE_ROOT.parent))).resolve()
BASE_PACKAGE_ROOT = SERVER_ROOT / "experiment51_external_repository_replication"
FIX2_PACKAGE_ROOT = SERVER_ROOT / "experiment51_exp52_scientific_freeze_alignment"
EXP52_DOCUMENT_ROOT = SERVER_ROOT / "experiment52_continuation_probe"

for _path in (BASE_PACKAGE_ROOT, FIX2_PACKAGE_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import experiment51_protocol as base  # noqa: E402
import experiment51_live_worker as base_worker  # noqa: E402
import analyze_experiment51 as base_analysis  # noqa: E402
from screen_experiment51_repositories import worker_input as base_worker_input  # noqa: E402
import experiment52_protocol as fix2  # noqa: E402

EXECUTION_ALIGNMENT_VERSION = (
    "experiment51-exp52-scientific-execution-alignment-fix3"
)
EXECUTION_FIX_ID = (
    "exp51-exp52-pre-candidate-fix3-safe-shards-evaluability-"
    "portable-doc-lock-complete-execution-stack"
)
AMENDMENT_SCHEMA = "exp51-exp52-pre-candidate-execution-amendment-v1"
EXP51_RUNNER_VERSION = "experiment51-safe-sharded-runner-fix3-v1"
EXP52_WORKER_VERSION = "experiment52-live-continuation-worker-fix3-v1"
EXP52_SELECTION_VERSION = "experiment52-frozen-pair-selection-fix3-v1"

SCIENTIFIC_ARTIFACT_RELATIVE = Path(
    "artifacts/v51/external_repository_replication_scientific"
)
SCIENTIFIC_ROOT = SERVER_ROOT / SCIENTIFIC_ARTIFACT_RELATIVE
SOURCE_CONFIG_RELATIVE = Path("frozen/experiment51_config.json")
SOURCE_TARGETS_RELATIVE = Path("frozen/targets.json")
SOURCE_EXP52_PROTOCOL_RELATIVE = Path("frozen/experiment52_protocol.json")
SOURCE_FREEZE_RECEIPT_RELATIVE = Path("frozen/freeze_receipt.json")
SOURCE_FREEZE_TRANSACTION_RELATIVE = Path("frozen/freeze_transaction.json")
AMENDMENT_RELATIVE = Path("frozen/execution_alignment_fix3.json")
AMENDMENT_RECEIPT_RELATIVE = Path("frozen/execution_alignment_fix3_receipt.json")
EXP51_PREFLIGHT_RELATIVE = Path("preflight/scientific_worker_compile_fix3.json")
EXP51_ENVIRONMENT_RELATIVE = Path("environment/receipt_fix3.json")

EXP51_SHARD_COUNT = 16
EXP52_SHARD_COUNT = 32
TARGET_ROOTS = 576
TARGET_REPOSITORIES = 12
ROOTS_PER_REPOSITORY = 48
CANDIDATES_PER_ROOT = 23
LEAN_TIMEOUT_SECONDS = 900

# User-reviewed Fix2 freeze anchors.  These prevent a merely self-consistent
# rewrite of the Fix2 receipt/config/protocol from becoming the source of this
# pre-candidate amendment.
FIX2_QUALIFICATION_CONFIG_SHA256 = (
    "d983bac8a2886f31520c3add1f7f2e165c3a99518ca3c629946c1a859bbd8b56"
)
FIX2_QUALIFICATION_SUMMARY_SHA256 = (
    "2e02f40fc9984b98b04a46ccb0598e1abf560aba15d1ac093e66b691e4a06614"
)
FIX2_EXP52_PROTOCOL_SHA256 = (
    "d6ec3926ab97f2b58efa466741b04d7c1e786f41de1a491282727ece368d84de"
)
FIX2_EXP52_DOCUMENT_BUNDLE_SHA256 = (
    "e34f20837ebb0286bf87b3ee5ee15286307317ff44ed159c555200ca28eb46c0"
)
FIX2_RETAINED_PROBES = 9


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def json_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def identity_sha256(value: Mapping[str, Any]) -> str:
    return json_sha256({
        key: item
        for key, item in value.items()
        if key not in {"created_utc", "identity_sha256"}
    })


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def atomic_json_dump(value: Any, path: str | Path) -> None:
    base.atomic_json_dump(value, path)


def atomic_jsonl_dump(rows: Iterable[Mapping[str, Any]], path: str | Path) -> None:
    base.atomic_jsonl_dump(rows, path)


def exclusive_create_json(path: str | Path, value: Mapping[str, Any]) -> None:
    base.exclusive_create_json(path, value)


def safe_slug(slug: str) -> str:
    return base.safe_slug(slug)


def portable_document_lock() -> dict[str, Any]:
    """Return a cross-machine content identity with no absolute paths."""
    rows = []
    for name, expected in fix2.PREREGISTRATION_DOCUMENTS.items():
        path = EXP52_DOCUMENT_ROOT / name
        if not path.is_file() or file_sha256(path) != expected:
            raise ValueError(f"Exp52 locked design document changed: {path}")
        rows.append({
            "name": name,
            "sha256": expected,
            "bytes": path.stat().st_size,
        })
    return {
        "schema": "exp52-portable-document-content-lock-v1",
        "files": rows,
        "bundle_sha256": json_sha256(rows),
    }


def package_code_sources() -> list[Path]:
    paths = sorted(PACKAGE_ROOT.glob("*.py"))
    for name in ("README_SERVER.md", "PACKAGE_MANIFEST.json"):
        path = PACKAGE_ROOT / name
        if path.is_file():
            paths.append(path)
    paths.extend(EXP52_DOCUMENT_ROOT / name for name in fix2.PREREGISTRATION_DOCUMENTS)
    unique: dict[Path, None] = {}
    for path in paths:
        unique[path.resolve()] = None
    return list(unique)


def package_code_lock() -> dict[str, Any]:
    return base.code_lock(package_code_sources())


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)


def _validate_targets(config: Mapping[str, Any], targets: Sequence[Mapping[str, Any]]) -> None:
    if not (
        len(targets) == TARGET_ROOTS
        and config.get("roots") == TARGET_ROOTS
        and config.get("repository_count") == TARGET_REPOSITORIES
        and config.get("roots_per_repository") == ROOTS_PER_REPOSITORY
        and config.get("candidate_budget") == CANDIDATES_PER_ROOT
    ):
        raise ValueError("Fix2 frozen Exp51 dimensions changed")
    theorem_ids = [str(row.get("theorem_id")) for row in targets]
    rids = [str(row.get("rid")) for row in targets]
    if len(set(theorem_ids)) != TARGET_ROOTS or len(set(rids)) != TARGET_ROOTS:
        raise ValueError("Fix2 targets contain duplicate identities")
    counts = Counter(str(row.get("slug")) for row in targets)
    expected_slugs = [str(row["slug"]) for row in config["repositories"]]
    if (
        set(counts) != set(expected_slugs)
        or any(counts[slug] != ROOTS_PER_REPOSITORY for slug in expected_slugs)
    ):
        raise ValueError("Fix2 target repository allocation changed")
    for row in targets:
        alternatives = list(row.get("alternatives", []))
        robust = base.select_candidate_view(alternatives, "L-mechanism-diverse")
        if not (
            len(alternatives) == CANDIDATES_PER_ROOT
            and alternatives == list(dict.fromkeys(alternatives))
            and robust == row.get("robust_alternatives")
        ):
            raise ValueError(f"frozen candidate panel changed: {row.get('theorem_id')}")


def _validate_copied_receipts(
    root: Path,
    receipt: Mapping[str, Any],
    expected_slugs: Sequence[str],
) -> None:
    rows = list(receipt.get("copied_build_receipts", []))
    if (
        len(rows) != TARGET_REPOSITORIES
        or [str(row.get("slug")) for row in rows] != list(expected_slugs)
        or len(set(expected_slugs)) != TARGET_REPOSITORIES
    ):
        raise ValueError("Fix2 copied build-receipt count changed")
    qualification_root = Path(receipt["qualification_root"]).resolve()
    for row in rows:
        slug = str(row["slug"])
        source = Path(row["source"]).resolve()
        copy = Path(row["copy"]).resolve()
        expected_name = f"{safe_slug(slug)}.json"
        expected_source = (
            qualification_root / "screening/build_trace" / expected_name
        ).resolve()
        expected_copy = (
            root / "screening/build_trace" / expected_name
        ).resolve()
        if not (
            source == expected_source
            and copy == expected_copy
            and source.is_file()
            and copy.is_file()
            and copy.is_relative_to(root)
            and file_sha256(source) == row["source_sha256"]
            and file_sha256(copy) == row["copy_sha256"]
            and row.get("exact") is True
            and row["source_sha256"] == row["copy_sha256"]
        ):
            raise ValueError(f"Fix2 copied build receipt changed: {row.get('slug')}")


def validate_source_bundle(
    root: str | Path = SCIENTIFIC_ROOT,
    *,
    require_pre_candidate: bool = False,
) -> dict[str, Any]:
    """Validate the immutable Fix2 freeze and optionally prove no candidate ran."""
    root = Path(root).resolve()
    paths = {
        "config": root / SOURCE_CONFIG_RELATIVE,
        "targets": root / SOURCE_TARGETS_RELATIVE,
        "protocol": root / SOURCE_EXP52_PROTOCOL_RELATIVE,
        "receipt": root / SOURCE_FREEZE_RECEIPT_RELATIVE,
        "transaction": root / SOURCE_FREEZE_TRANSACTION_RELATIVE,
    }
    for path in paths.values():
        _require_file(path)
    config = read_json(paths["config"])
    targets = read_json(paths["targets"])
    protocol = read_json(paths["protocol"])
    receipt = read_json(paths["receipt"])
    transaction = read_json(paths["transaction"])
    probe_surface_path = root / "preflight/exp52_probe_surface.json"
    _require_file(probe_surface_path)
    probe_surface = read_json(probe_surface_path)
    base.validate_code_lock(config["code_lock"])
    fix2.validate_protocol(protocol)
    portable = portable_document_lock()
    retained_panel = list(protocol.get("probe_surface", {}).get(
        "retained_panel", []
    ))
    source = config.get("source", {})
    qualification = source.get("extension2_qualification", {})
    protocol_documents = protocol.get("preregistration_documents", {})
    if not (
        config.get("protocol_version") == base.PROTOCOL_VERSION
        and config.get("alignment_version") == fix2.ALIGNMENT_VERSION
        and config.get("mechanical_fix_id") == fix2.ALIGNMENT_FIX_ID
        and config.get("identity_sha256") == identity_sha256(config)
        and config.get("exp52_freeze_required_before_execution") is True
        and receipt.get("alignment_version") == fix2.ALIGNMENT_VERSION
        and receipt.get("mechanical_fix_id") == fix2.ALIGNMENT_FIX_ID
        and receipt.get("config_sha256") == file_sha256(paths["config"])
        and receipt.get("targets_sha256") == file_sha256(paths["targets"])
        and receipt.get("exp52_protocol_sha256")
        == file_sha256(paths["protocol"])
        == FIX2_EXP52_PROTOCOL_SHA256
        and receipt.get("repositories") == TARGET_REPOSITORIES
        and receipt.get("roots") == TARGET_ROOTS
        and receipt.get("copied_build_receipts_exact") is True
        and receipt.get("qualification_config_sha256")
        == qualification.get("config_sha256")
        == FIX2_QUALIFICATION_CONFIG_SHA256
        and receipt.get("qualification_summary_sha256")
        == qualification.get("screening_summary_sha256")
        == source.get("screening_summary_sha256")
        == FIX2_QUALIFICATION_SUMMARY_SHA256
        and receipt.get("exp52_design_documents_bundle_sha256")
        == protocol_documents.get("bundle_sha256")
        == FIX2_EXP52_DOCUMENT_BUNDLE_SHA256
        and receipt.get("exp52_retained_probes")
        == len(retained_panel)
        == FIX2_RETAINED_PROBES
        and receipt.get("scientific_candidate_execution_before_freeze") is False
        and receipt.get("scientific_candidate_tactics_executed") == 0
        and transaction == {"completed": True, **receipt}
        and protocol.get("source_config_identity_sha256")
        == config.get("identity_sha256")
        and protocol.get("source_repositories")
        == [row["slug"] for row in config["repositories"]]
        and protocol.get("probe_surface", {}).get("receipt_sha256")
        == file_sha256(probe_surface_path)
        == source.get("exp52_probe_surface_sha256")
        and probe_surface.get("alignment_version") == fix2.ALIGNMENT_VERSION
        and probe_surface.get("mechanical_fix_id") == fix2.ALIGNMENT_FIX_ID
        and probe_surface.get("qualification_config_sha256")
        == FIX2_QUALIFICATION_CONFIG_SHA256
        and probe_surface.get("qualification_summary_sha256")
        == FIX2_QUALIFICATION_SUMMARY_SHA256
        and probe_surface.get("selected_repositories")
        == [row["slug"] for row in config["repositories"]]
        and probe_surface.get("staged_targets") == TARGET_ROOTS
        and probe_surface.get("staged_targets_sha256") == json_sha256(targets)
        and probe_surface.get("probe_surface_gate") is True
        and probe_surface.get("diagnostic_only") is True
        and probe_surface.get("theorem_sources_elaborated") == 0
        and probe_surface.get("candidate_tactics_executed") == 0
        and probe_surface.get("scientific_candidate_tactics_executed") == 0
        and retained_panel == probe_surface.get("retained_panel")
        and protocol.get("probe_surface", {}).get("retained_panel_sha256")
        == json_sha256(retained_panel)
        == probe_surface.get("retained_panel_sha256")
    ):
        raise ValueError("Fix2 frozen scientific bundle is not exact")
    _validate_targets(config, targets)
    _validate_copied_receipts(
        root,
        receipt,
        [str(row["slug"]) for row in config["repositories"]],
    )
    if portable["files"] != [
        {
            "name": Path(row["path"]).name,
            "sha256": row["sha256"],
            "bytes": row["bytes"],
        }
        for row in protocol["preregistration_documents"]["files"]
    ]:
        raise ValueError("Fix2 protocol document contents changed")
    if require_pre_candidate:
        forbidden = []
        for relative in (
            "environment", "smoke", "scientific", "analysis", "audit", "exp52"
        ):
            path = root / relative
            if path.exists() and any(item.is_file() for item in path.rglob("*")):
                forbidden.append(relative)
        if forbidden:
            raise ValueError(
                "pre-candidate Fix3 amendment is too late; outcome artifacts exist: "
                + ",".join(forbidden)
            )
        if (root / EXP51_PREFLIGHT_RELATIVE).exists():
            raise ValueError("Fix3 scientific preflight already exists before amendment")
        legacy_preflight = root / "preflight/scientific_worker_compile.json"
        if legacy_preflight.exists():
            raise ValueError(
                "legacy scientific worker preflight exists before Fix3 amendment"
            )
    return {
        "root": root,
        "paths": paths,
        "config": config,
        "targets": targets,
        "protocol": protocol,
        "receipt": receipt,
        "transaction": transaction,
        "portable_document_lock": portable,
        "config_sha256": file_sha256(paths["config"]),
        "targets_sha256": file_sha256(paths["targets"]),
        "protocol_sha256": file_sha256(paths["protocol"]),
        "receipt_sha256": file_sha256(paths["receipt"]),
        "transaction_sha256": file_sha256(paths["transaction"]),
    }


def shard_index(position: int, shard_count: int) -> int:
    if shard_count <= 0 or position < 0:
        raise ValueError("invalid deterministic shard arguments")
    return position % shard_count


def targets_for_shard(
    targets: Sequence[Mapping[str, Any]], shard: int, shard_count: int
) -> list[dict[str, Any]]:
    if not 0 <= shard < shard_count:
        raise ValueError("shard index outside frozen range")
    return [
        dict(row)
        for index, row in enumerate(targets)
        if shard_index(index, shard_count) == shard
    ]


def exp51_row_path(root: str | Path, target: Mapping[str, Any]) -> Path:
    root = Path(root)
    positions = targets_position_map(root)
    index = positions[str(target["theorem_id"])]
    shard = shard_index(index, EXP51_SHARD_COUNT)
    return (
        root
        / "scientific/shards"
        / f"shard-{shard:02d}"
        / "theorems"
        / safe_slug(str(target["slug"]))
        / f"{target['rid']}.json"
    )


def targets_position_map(root: str | Path) -> dict[str, int]:
    targets = read_json(Path(root) / SOURCE_TARGETS_RELATIVE)
    return {str(row["theorem_id"]): index for index, row in enumerate(targets)}


def validate_amendment(root: str | Path = SCIENTIFIC_ROOT) -> dict[str, Any]:
    root = Path(root).resolve()
    source = validate_source_bundle(root, require_pre_candidate=False)
    path = root / AMENDMENT_RELATIVE
    _require_file(path)
    value = read_json(path)
    if not (
        value.get("schema") == AMENDMENT_SCHEMA
        and value.get("alignment_version") == EXECUTION_ALIGNMENT_VERSION
        and value.get("mechanical_fix_id") == EXECUTION_FIX_ID
        and value.get("identity_sha256") == identity_sha256(value)
        and value.get("frozen_before_exp51_scientific_execution") is True
        and value.get("scientific_candidate_execution_before_amendment") is False
        and value.get("source_fix2", {}).get("alignment_version")
        == fix2.ALIGNMENT_VERSION
        and value.get("source_fix2", {}).get("mechanical_fix_id")
        == fix2.ALIGNMENT_FIX_ID
        and value.get("source_fix2", {}).get("config")
        == str(source["paths"]["config"])
        and value.get("source_fix2", {}).get("config_sha256")
        == source["config_sha256"]
        and value.get("source_fix2", {}).get("targets")
        == str(source["paths"]["targets"])
        and value.get("source_fix2", {}).get("targets_sha256")
        == source["targets_sha256"]
        and value.get("source_fix2", {}).get("exp52_protocol")
        == str(source["paths"]["protocol"])
        and value.get("source_fix2", {}).get("exp52_protocol_sha256")
        == source["protocol_sha256"]
        and value.get("source_fix2", {}).get("freeze_receipt")
        == str(source["paths"]["receipt"])
        and value.get("source_fix2", {}).get("freeze_receipt_sha256")
        == source["receipt_sha256"]
        and value.get("source_fix2", {}).get("freeze_transaction")
        == str(source["paths"]["transaction"])
        and value.get("source_fix2", {}).get("freeze_transaction_sha256")
        == source["transaction_sha256"]
        and value.get("source_fix2", {}).get("qualification_config_sha256")
        == source["receipt"].get("qualification_config_sha256")
        and value.get("source_fix2", {}).get("qualification_summary_sha256")
        == source["receipt"].get("qualification_summary_sha256")
        and value.get("source_fix2", {}).get("copied_build_receipts_exact")
        is True
        and value.get("source_fix2", {}).get(
            "exp52_design_documents_bundle_sha256"
        ) == source["receipt"].get("exp52_design_documents_bundle_sha256")
        and value.get("source_fix2", {}).get("exp52_retained_probes")
        == source["receipt"].get("exp52_retained_probes")
        and value.get("portable_exp52_document_lock")
        == source["portable_document_lock"]
        and value.get("exp51_execution", {}).get("shard_count")
        == EXP51_SHARD_COUNT
        and value.get("exp51_execution", {}).get("roots") == TARGET_ROOTS
        and value.get("exp51_execution", {}).get("candidates_per_evaluable_root")
        == CANDIDATES_PER_ROOT
        and value.get("exp51_execution", {}).get("resource_gate") == {
            "minimum_allowed_cpus": 16,
            "minimum_available_memory_gb": 64,
            "minimum_free_disk_gb": 50,
        }
        and value.get("exp52_execution", {}).get("shard_count")
        == EXP52_SHARD_COUNT
        and value.get("exp52_execution", {}).get("lean_timeout_seconds")
        == LEAN_TIMEOUT_SECONDS
    ):
        raise ValueError("Fix3 execution amendment differs from the frozen contract")
    base.validate_code_lock(value["code_lock"])
    expected_plan = [
        {
            "shard_index": shard,
            "target_count": len(
                targets_for_shard(source["targets"], shard, EXP51_SHARD_COUNT)
            ),
            "theorem_ids_sha256": json_sha256([
                row["theorem_id"]
                for row in targets_for_shard(
                    source["targets"], shard, EXP51_SHARD_COUNT
                )
            ]),
        }
        for shard in range(EXP51_SHARD_COUNT)
    ]
    if value.get("exp51_execution", {}).get("shard_plan") != expected_plan:
        raise ValueError("Fix3 deterministic Exp51 shard plan changed")
    return {**source, "amendment": value, "amendment_path": path,
            "amendment_sha256": file_sha256(path)}


def load_source_bundle(
    root: str | Path = SCIENTIFIC_ROOT,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    value = validate_amendment(root)
    return (
        value["config"],
        list(value["targets"]),
        value["protocol"],
        value["amendment"],
    )


def hydrate_text(entry: Mapping[str, Any]) -> str:
    path = Path(entry["path"])
    value = path.read_text(encoding="utf-8")
    if not (
        file_sha256(path) == entry["sha256"]
        and len(value.encode("utf-8")) == int(entry["bytes"])
    ):
        raise ValueError(f"content-store entry changed: {path}")
    return value


def endpoint_state(branch: Mapping[str, Any], kind: str = "struct") -> str:
    return hydrate_text(branch["endpoints"][kind]["state"])


def bin_index(value: int, edges: Sequence[int | str]) -> int:
    finite = [int(edge) for edge in edges if edge != "infinity"]
    if value < 0 or len(finite) < 2:
        raise ValueError("invalid feature-bin input")
    for index in range(len(finite) - 1):
        if finite[index] <= value < finite[index + 1]:
            return index
    return len(finite) - 1


def _balanced_segments(value: str, tag: str) -> list[str]:
    """Extract balanced S-expression segments beginning with ``(TAG ``."""
    marker = f"({tag} "
    out: list[str] = []
    start = 0
    while True:
        found = -1
        quoted = False
        escaped = False
        index = 0
        while index < len(value):
            char = value[index]
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif index >= start and value.startswith(marker, index):
                found = index
                break
            index += 1
        if found < 0:
            return out
        depth = 0
        quoted = False
        escaped = False
        for index in range(found, len(value)):
            char = value[index]
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    out.append(value[found:index + 1])
                    start = index + 1
                    break
        else:
            raise ValueError(f"unterminated strict endpoint segment: {tag}")


def strict_endpoint_features(branch: Mapping[str, Any]) -> tuple[int, int, int]:
    structural = endpoint_state(branch, "struct")
    goals = int(branch["goal_count"])
    local_count = len(_balanced_segments(structural, "LOCAL"))
    targets = _balanced_segments(structural, "TARGET")
    if len(targets) != goals:
        raise ValueError("strict endpoint target count differs from goal count")
    target_bytes = sum(
        len(item[len("(TARGET "):-1].encode("utf-8")) for item in targets
    )
    local_bin = bin_index(local_count, [0, 4, 8, 16, 32, "infinity"])
    target_bin = bin_index(
        target_bytes, [0, 256, 512, 1024, 2048, "infinity"]
    )
    return goals, local_bin, target_bin


def candidate_key(branch: Mapping[str, Any]) -> tuple[bytes, bytes, int]:
    return (
        str(branch["head"]).encode("utf-8"),
        str(branch["tactic"]).encode("utf-8"),
        int(branch["candidate_position_frozen"]),
    )


def ordered_pair(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    values = sorted((dict(left), dict(right)), key=candidate_key)
    return values[0], values[1]


def determinism_audit_count(n_repo: int) -> int:
    return math.ceil(0.10 * n_repo)
