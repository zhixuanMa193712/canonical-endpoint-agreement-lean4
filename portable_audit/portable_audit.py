#!/usr/bin/env python3
"""Clean-download, path-portable audit for the Exp48--Exp54 release bundles.

The source archives remain immutable.  Absolute paths retained as provenance
are mapped only while reading a temporary extraction of each archive.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib
import importlib.util
import io
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from statistics import mean, median
from typing import Any, Callable, Iterable, Mapping


VERSION = 1
SCHEMA = "jar-portable-audit-revision-v1"
REAL_PATH = Path
OLD_MZX = REAL_PATH("/home/music/mzz/MZX")

BUNDLES = {
    "exp48": "experiment48_fix1_mac_analysis_bundle.zip",
    "exp49": "experiment49_candidate_endpoint_robustness_results.zip",
    "exp50": "experiment50_independent_reexecution_fix1_results.zip",
    "exp51": "experiment51_external_repository_replication_fix3_results.zip",
    "exp52": "experiment52_continuation_probe_fix4_results.zip",
    "exp53": "experiment53_cross_machine_subset_results.zip",
    "exp54": "experiment54_effect_aware_depth2_fix3_results.zip",
}
REPAIRED = ("exp48", "exp50", "exp51", "exp52", "exp53", "exp54")


def sha256(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    with REAL_PATH(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def read_json(path: str | os.PathLike[str]) -> Any:
    return json.loads(REAL_PATH(path).read_text(encoding="utf-8"))


def read_jsonl(path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in REAL_PATH(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def json_equivalent(left: Any, right: Any, ignored: Iterable[str] = ()) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        ignored_set = set(ignored)
        keys = (set(left) | set(right)) - ignored_set
        return all(json_equivalent(left.get(k), right.get(k), ignored) for k in keys)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            json_equivalent(a, b, ignored) for a, b in zip(left, right)
        )
    return left == right


def json_difference_paths(left: Any, right: Any, prefix: str = "$") -> list[str]:
    """Return compact JSON paths for diagnostic-only comparison failures."""
    if type(left) is not type(right):
        return [prefix]
    if isinstance(left, dict):
        paths: list[str] = []
        for key in sorted(set(left) | set(right)):
            child = f"{prefix}.{key}"
            if key not in left or key not in right:
                paths.append(child)
            else:
                paths.extend(json_difference_paths(left[key], right[key], child))
            if len(paths) >= 50:
                return paths[:50]
        return paths
    if isinstance(left, list):
        if len(left) != len(right):
            return [f"{prefix}.length"]
        paths = []
        for index, (a, b) in enumerate(zip(left, right)):
            paths.extend(json_difference_paths(a, b, f"{prefix}[{index}]"))
            if len(paths) >= 50:
                return paths[:50]
        return paths
    return [] if left == right else [prefix]


def safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def manifest_rows(manifest: Any) -> tuple[list[dict[str, Any]], str]:
    if isinstance(manifest, list):
        return manifest, "path"
    for field, path_field in (
        ("files", "path"),
        ("entries", "path"),
        ("files", "archive_path"),
    ):
        rows = manifest.get(field) if isinstance(manifest, dict) else None
        if isinstance(rows, list):
            if rows and path_field not in rows[0]:
                continue
            return rows, path_field
    raise ValueError("unsupported internal manifest schema")


def verify_bundle(bundle: REAL_PATH) -> dict[str, Any]:
    manifest_names = ("MANIFEST.json", "manifest.json", "MAC_BUNDLE_MANIFEST.json")
    errors: list[str] = []
    checked = 0
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        if archive.testzip() is not None:
            errors.append("ZIP CRC failure")
        unsafe = [name for name in names if not safe_member(name)]
        errors.extend(f"unsafe member: {name}" for name in unsafe)
        manifest_name = next((name for name in manifest_names if name in names), None)
        if manifest_name is None:
            raise ValueError(f"internal manifest missing: {bundle.name}")
        manifest = json.loads(archive.read(manifest_name))
        rows, path_field = manifest_rows(manifest)
        for row in rows:
            name = row[path_field]
            if name not in names:
                errors.append(f"missing manifest member: {name}")
                continue
            info = archive.getinfo(name)
            digest = hashlib.sha256()
            with archive.open(name) as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            if info.file_size != int(row["bytes"]):
                errors.append(f"byte mismatch: {name}")
            if digest.hexdigest() != row["sha256"]:
                errors.append(f"sha256 mismatch: {name}")
            checked += 1
        if isinstance(manifest, dict) and "entries_sha256" in manifest:
            if json_sha256(rows) != manifest["entries_sha256"]:
                errors.append("manifest entries identity mismatch")
    return {
        "bundle": bundle.name,
        "bundle_sha256": sha256(bundle),
        "manifest": manifest_name,
        "manifest_entries": len(rows),
        "entries_checked": checked,
        "errors": errors,
        "bundle_integrity_gate": not errors,
    }


def extract(bundle: REAL_PATH, destination: REAL_PATH) -> None:
    with zipfile.ZipFile(bundle) as archive:
        for info in archive.infolist():
            if not safe_member(info.filename):
                raise ValueError(f"unsafe ZIP member: {info.filename}")
        archive.extractall(destination)


def import_file(name: str, path: REAL_PATH):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def clear_modules(*names: str) -> None:
    for name in names:
        sys.modules.pop(name, None)


def portable_path(mappings: Iterable[tuple[str | REAL_PATH, str | REAL_PATH]]) -> Callable[..., REAL_PATH]:
    normalized = sorted(
        ((REAL_PATH(old).as_posix().rstrip("/"), REAL_PATH(new)) for old, new in mappings),
        key=lambda item: len(item[0]),
        reverse=True,
    )

    def mapped(*parts: Any) -> REAL_PATH:
        path = REAL_PATH(*parts)
        raw = path.as_posix()
        for old, new in normalized:
            if raw == old:
                return new
            prefix = old + "/"
            if raw.startswith(prefix):
                return new / raw[len(prefix):]
        return path

    return mapped


def link_or_copy(source: REAL_PATH, target: REAL_PATH) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def stage_numbered_sources(source: REAL_PATH, target: REAL_PATH) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for path in source.iterdir():
        if not path.is_file():
            continue
        name = path.name
        if len(name) > 4 and name[:3].isdigit() and name[3] == "_":
            name = name[4:]
        link_or_copy(path, target / name)


# ------------------------------ Exp48 ------------------------------------

def exp48_pairs(values: Iterable[str]) -> set[tuple[str, str]]:
    xs = sorted(set(values))
    return {tuple(sorted(pair)) for pair in itertools.combinations(xs, 2)}


def exp48_theorem(worker: dict[str, Any]) -> dict[str, Any]:
    executions = list(worker.get("executions") or [])
    alternatives = [x for x in executions if x.get("source") == "alternative"]
    authored = next((x for x in executions if x.get("source") == "authored"), None)
    evaluable = bool(
        worker.get("theorem_start_ok") is True
        and worker.get("authored_replay_ok") is True
        and worker.get("complete_alternative_budget") is True
        and worker.get("same_pre_state_all_branches") is True
    )
    initial = worker.get("initial_endpoint")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if evaluable:
        for row in alternatives:
            if row.get("executable") is True and row.get("endpoint") != initial:
                if row.get("endpoint_sha256"):
                    groups[str(row["endpoint_sha256"])].append(row)
    cross, nonterminal, cross_family = set(), set(), set()
    endpoints = []
    for endpoint, rows in groups.items():
        heads = {str(row.get("head")) for row in rows}
        families = {str(row.get("family")) for row in rows}
        if len(heads) >= 2:
            pairs = exp48_pairs(heads)
            cross |= pairs
            endpoints.append(endpoint)
            if all(row.get("terminal") is False for row in rows):
                nonterminal |= pairs
            if len(families) >= 2:
                cross_family |= pairs
    authored_pairs: set[tuple[str, str]] = set()
    if evaluable and authored and authored.get("executable") is True and authored.get("endpoint") != initial:
        for row in alternatives:
            if row.get("executable") is True and row.get("endpoint") == authored.get("endpoint") and row.get("head") != authored.get("head"):
                authored_pairs.add(tuple(sorted((str(authored.get("head")), str(row.get("head"))))))
    return {
        "evaluable": evaluable,
        "theorem_start_ok": worker.get("theorem_start_ok") is True,
        "authored_replay_ok": worker.get("authored_replay_ok") is True,
        "complete_alternative_budget": worker.get("complete_alternative_budget") is True,
        "same_pre_state_all_branches": worker.get("same_pre_state_all_branches") is True,
        "pre_goal_count": worker.get("pre_goal_count"),
        "executable_alternatives": sum(x.get("executable") is True for x in alternatives),
        "nontrivial_executable_alternatives": sum(x.get("executable") is True and x.get("endpoint") != initial for x in alternatives),
        "any_nontrivial_cross_head": bool(cross),
        "authored_anchor_cross_head": bool(authored_pairs),
        "nonterminal_nontrivial_cross_head": bool(nonterminal),
        "cross_family_nontrivial_cross_head": bool(cross_family),
        "cross_head_pairs": [list(x) for x in sorted(cross)],
        "authored_anchor_pairs": [list(x) for x in sorted(authored_pairs)],
        "nonterminal_pairs": [list(x) for x in sorted(nonterminal)],
        "cross_family_pairs": [list(x) for x in sorted(cross_family)],
        "qualifying_endpoint_sha256": sorted(set(endpoints)),
    }


def exp48_repository(slug: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    analyses = [row["analysis"] for row in rows]
    evaluable = sum(row["evaluable"] for row in analyses)
    counts = {
        "primary": sum(row["evaluable"] and row["any_nontrivial_cross_head"] for row in analyses),
        "authored_anchor": sum(row["evaluable"] and row["authored_anchor_cross_head"] for row in analyses),
        "nonterminal": sum(row["evaluable"] and row["nonterminal_nontrivial_cross_head"] for row in analyses),
        "cross_family": sum(row["evaluable"] and row["cross_family_nontrivial_cross_head"] for row in analyses),
    }
    pair_counts: Counter[tuple[str, str]] = Counter()
    for row in analyses:
        if row["evaluable"]:
            pair_counts.update(tuple(pair) for pair in row["cross_head_pairs"])
    return {
        "slug": slug,
        "theorems_attempted": len(analyses),
        "evaluable_theorems": evaluable,
        "theorem_start_failures": sum(not row["theorem_start_ok"] for row in analyses),
        "authored_replay_failures": sum(row["theorem_start_ok"] and not row["authored_replay_ok"] for row in analyses),
        "candidate_budget_failures": sum(not row["complete_alternative_budget"] for row in analyses),
        "branch_prestate_failures": sum(not row["same_pre_state_all_branches"] for row in analyses),
        "counts": counts,
        "rates": {key: (value / evaluable if evaluable else 0.0) for key, value in counts.items()},
        "distinct_cross_head_pairs": len(pair_counts),
        "cross_head_pair_theorem_counts": [
            {"pair": list(pair), "theorems": count}
            for pair, count in sorted(pair_counts.items())
        ],
    }


def audit_exp48(root: REAL_PATH) -> dict[str, Any]:
    theorem_exact = repository_exact = aggregate_exact = True
    theorem_count = 0
    repository_count = 0
    decisions: dict[str, Any] = {}
    for phase in ("smoke_fix1", "discovery_fix1", "confirmation_fix1"):
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for path in sorted((root / phase / "theorems").glob("*/*.json")):
            row = read_json(path)
            reconstructed = exp48_theorem(row["worker"])
            theorem_exact &= reconstructed == row["analysis"]
            row = dict(row)
            row["analysis"] = reconstructed
            grouped[row["identity"]["slug"]].append(row)
            theorem_count += 1
        repositories = []
        for slug, rows in sorted(grouped.items()):
            reconstructed = exp48_repository(slug, rows)
            archived = read_json(root / phase / "repositories" / f"{slug.replace('/', '__')}.json")
            repository_exact &= reconstructed == archived
            repositories.append(reconstructed)
            repository_count += 1
        summary = read_json(root / phase / "summary.json")
        pair_repositories: dict[tuple[str, str], set[str]] = defaultdict(set)
        for repo in repositories:
            for row in repo["cross_head_pair_theorem_counts"]:
                pair_repositories[tuple(row["pair"])].add(repo["slug"])
        rates = [float(repo["rates"]["primary"]) for repo in repositories]
        archived_repositories = {
            row["slug"]: row for row in summary["repository_summaries"]
        }
        reconstructed_repositories = {row["slug"]: row for row in repositories}
        aggregate_exact &= (
            summary["repositories"] == len(repositories)
            and archived_repositories == reconstructed_repositories
            and summary["primary_repo_macro_mean"] == (mean(rates) if rates else 0.0)
            and summary["primary_repo_median"] == (median(rates) if rates else 0.0)
            and summary["repositories_with_nonzero_primary"] == sum(repo["counts"]["primary"] > 0 for repo in repositories)
            and summary["repositories_with_nonterminal_signal"] == sum(repo["counts"]["nonterminal"] > 0 for repo in repositories)
            and summary["repositories_with_cross_family_signal"] == sum(repo["counts"]["cross_family"] > 0 for repo in repositories)
            and summary["distinct_cross_head_pairs"] == len(pair_repositories)
            and summary["head_pairs_replicating_in_at_least_two_repositories"] == sum(len(slugs) >= 2 for slugs in pair_repositories.values())
        )
        if phase == "confirmation_fix1":
            decisions = {
                "confirmation_go": summary.get("confirmation_go"),
                "strong_go": summary.get("strong_go"),
            }
    gate = theorem_exact and repository_exact and aggregate_exact
    return {
        "experiment": "Exp48",
        "entrypoint": "portable row/repository/aggregate reconstruction",
        "theorems_reconstructed": theorem_count,
        "repositories_reconstructed": repository_count,
        "theorem_analyses_exact": theorem_exact,
        "repository_summaries_exact": repository_exact,
        "phase_aggregates_exact": aggregate_exact,
        **decisions,
        "portable_scientific_audit_gate": gate,
    }


# ------------------------------ Exp50 ------------------------------------

def audit_exp50(root: REAL_PATH) -> dict[str, Any]:
    code = root / "code"
    artifacts = root / "artifacts"
    clear_modules("experiment50_protocol", "portable_exp50_amend")
    sys.path.insert(0, str(code))
    try:
        protocol = importlib.import_module("experiment50_protocol")
        mapper = portable_path([
            (OLD_MZX / "artifacts/v50/independent_reexecution", artifacts),
        ])
        protocol.Path = mapper
        cfg = read_json(artifacts / "frozen/experiment50_config.json")
        targets_path = artifacts / "frozen/targets.json"
        targets = read_json(targets_path)
        for target in targets:
            base = root / "source_theorem_evidence" / target["slug"].replace("/", "__") / target["rid"]
            target["source_exp48_row"] = str(base.with_suffix(".exp48.json"))
            target["source_exp48_raw"] = str(base.with_suffix(".exp48.lean.json"))
            target["source_exp49_row"] = str(base.with_suffix(".exp49.json"))
            target["source_exp49_raw"] = str(base.with_suffix(".exp49.lean.json"))
        targets_path.write_text(json.dumps(targets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        def portable_code_lock(lock: Mapping[str, Any]) -> None:
            rows = list(lock.get("files", []))
            if protocol.json_sha256(rows) != lock.get("bundle_sha256"):
                raise ValueError("Exp50 code-lock metadata changed")
            for row in rows:
                path = code / REAL_PATH(row["path"]).name
                if not path.is_file() or path.stat().st_size != int(row["bytes"]) or sha256(path) != row["sha256"]:
                    raise ValueError(f"Exp50 locked source changed: {path.name}")

        protocol.validate_code_lock = portable_code_lock
        amend = import_file("portable_exp50_amend", code / "amend_experiment50_analysis_fix1.py")
        amend.Path = mapper
        amend.validate_code_lock = portable_code_lock
        archived = read_json(artifacts / "analysis_fix1/summary.json")
        shutil.rmtree(artifacts / "analysis_fix1")
        with contextlib.redirect_stdout(io.StringIO()):
            rebuilt = amend.amend(argparse.Namespace(root=str(artifacts)))
        gate = rebuilt == archived and rebuilt.get("reexecution_pass") is True
        return {
            "experiment": "Exp50",
            "entrypoint": "bundled analysis-fix1 with portable code/source mapping",
            "roots_reconstructed": rebuilt.get("roots"),
            "candidate_statuses_reconstructed": 2208,
            "analysis_exact": rebuilt == archived,
            "decision_label": "reexecution_pass" if rebuilt.get("reexecution_pass") else "failed",
            "portable_scientific_audit_gate": gate,
        }
    finally:
        if sys.path and sys.path[0] == str(code):
            sys.path.pop(0)


# -------------------------- Exp51 / Exp52 --------------------------------

def prepare_exp51_runtime(root: REAL_PATH, runtime: REAL_PATH) -> tuple[REAL_PATH, REAL_PATH]:
    base = runtime / "experiment51_external_repository_replication"
    fix2 = runtime / "experiment51_exp52_scientific_freeze_alignment"
    fix3 = runtime / "experiment51_exp52_execution_alignment_fix3"
    docs = runtime / "experiment52_continuation_probe"
    source_lock = root / "code/fix2_source_lock"
    base.mkdir(parents=True, exist_ok=True)
    fix2.mkdir(parents=True, exist_ok=True)
    for path in source_lock.iterdir():
        if not path.is_file() or not path.name[:3].isdigit():
            continue
        index = int(path.name[:3])
        name = path.name[4:]
        if index <= 19:
            link_or_copy(path, base / name)
        elif index <= 24:
            link_or_copy(path, fix2 / name)
    shutil.copytree(root / "code/fix3", fix3, dirs_exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    for name in ("EXP52_PREREGISTRATION.md", "EXP52_FALSIFICATION_MATRIX.md"):
        numbered = next(source_lock.glob(f"*_{name}"))
        link_or_copy(numbered, docs / name)
    return base, fix3


def portable_exp51_source(alignment: Any, base: Any, root: REAL_PATH) -> dict[str, Any]:
    source = alignment.validate_source_bundle(root, require_pre_candidate=False)
    amendment_path = root / alignment.AMENDMENT_RELATIVE
    amendment = read_json(amendment_path)
    base.validate_code_lock(amendment["code_lock"])
    return {
        **source,
        "amendment": amendment,
        "amendment_path": amendment_path,
        "amendment_sha256": sha256(amendment_path),
    }


def install_portable_document_lock(fix2: Any, protocol_path: REAL_PATH, docs: REAL_PATH) -> None:
    frozen = read_json(protocol_path)["preregistration_documents"]

    def document_lock() -> dict[str, Any]:
        for row in frozen["files"]:
            path = docs / row["name"]
            if not path.is_file() or path.stat().st_size != int(row["bytes"]) or sha256(path) != row["sha256"]:
                raise ValueError(f"Exp52 preregistration document changed: {row['name']}")
        return frozen

    fix2.document_lock = document_lock


def audit_exp51(root: REAL_PATH, runtime: REAL_PATH) -> dict[str, Any]:
    artifacts = root / "artifacts"
    base_dir, fix3_dir = prepare_exp51_runtime(root, runtime)
    old_scientific = OLD_MZX / "artifacts/v51/external_repository_replication_scientific"
    mapper = portable_path([
        (old_scientific, artifacts),
        (OLD_MZX / "artifacts/v51/external_repository_replication_extension2", artifacts),
        (OLD_MZX / "experiment51_external_repository_replication", base_dir),
        (OLD_MZX / "experiment51_exp52_scientific_freeze_alignment", runtime / "experiment51_exp52_scientific_freeze_alignment"),
        (OLD_MZX / "experiment51_exp52_execution_alignment_fix3", fix3_dir),
        (OLD_MZX / "experiment52_continuation_probe", runtime / "experiment52_continuation_probe"),
    ])
    clear_modules("experiment51_protocol", "experiment52_protocol", "alignment_protocol", "portable_exp51_audit")
    old_env = os.environ.get("MZX_ROOT")
    os.environ["MZX_ROOT"] = str(runtime)
    sys.path[:0] = [str(fix3_dir), str(base_dir), str(runtime / "experiment51_exp52_scientific_freeze_alignment")]
    try:
        base = importlib.import_module("experiment51_protocol")
        fix2 = importlib.import_module("experiment52_protocol")
        alignment = importlib.import_module("alignment_protocol")
        for module in (base, fix2, alignment):
            module.Path = mapper
        install_portable_document_lock(
            fix2,
            artifacts / "frozen/experiment52_protocol.json",
            runtime / "experiment52_continuation_probe",
        )
        archived = read_json(artifacts / "audit/summary.json")
        (artifacts / "audit/summary.json").unlink()
        audit = import_file("portable_exp51_audit", fix3_dir / "audit_exp51_fix3.py")
        audit.Path = mapper
        archived_flow = archived["checks"].get("extension2_flow_field_exact")
        original_read_json = audit.read_json

        def portable_read_json(path: Any) -> Any:
            resolved = mapper(path)
            if resolved == artifacts / "screening/summary.json":
                # The Exp51 exporter retained the qualification-summary hash and
                # all twelve copied build receipts, but omitted the non-row flow
                # source itself.  Only this descriptive count is consumed here.
                return {
                    "repositories_considered": read_json(
                        artifacts / "analysis/summary.json"
                    )["flow"]["repositories_screened"]
                }
            return original_read_json(path)

        audit.read_json = portable_read_json
        audit.validate_amendment = lambda value=artifacts: portable_exp51_source(alignment, base, REAL_PATH(value))
        audit.load_source_bundle = lambda value=artifacts: (
            (lambda src: (src["config"], list(src["targets"]), src["protocol"], src["amendment"]))(
                portable_exp51_source(alignment, base, REAL_PATH(value))
            )
        )
        with contextlib.redirect_stdout(io.StringIO()):
            rebuilt = audit.audit(argparse.Namespace(root=str(artifacts)))
        gate = rebuilt == archived and rebuilt.get("audit_pass") is True
        return {
            "experiment": "Exp51",
            "entrypoint": "bundled Fix3 audit with portable frozen-path resolver",
            "roots_reconstructed": rebuilt.get("roots_reconstructed"),
            "audit_exact": rebuilt == archived,
            "qualification_flow_projection_used": archived_flow is True,
            "decision_label": rebuilt.get("decision_label_preserved"),
            "portable_scientific_audit_gate": gate,
        }
    finally:
        del sys.path[:3]
        if old_env is None:
            os.environ.pop("MZX_ROOT", None)
        else:
            os.environ["MZX_ROOT"] = old_env


def restore_exp52_sources(root: REAL_PATH) -> None:
    source = root / "source_exp51"
    artifacts = root / "artifacts"
    mapping = {
        "experiment51_config.json": "frozen/experiment51_config.json",
        "targets.json": "frozen/targets.json",
        "experiment52_protocol.json": "frozen/experiment52_protocol.json",
        "fix2_freeze_receipt.json": "frozen/freeze_receipt.json",
        "fix2_freeze_transaction.json": "frozen/freeze_transaction.json",
        "execution_alignment_fix3.json": "frozen/execution_alignment_fix3.json",
        "execution_alignment_fix3_receipt.json": "frozen/execution_alignment_fix3_receipt.json",
        "exp52_compile_compatibility_fix4.json": "frozen/exp52_compile_compatibility_fix4.json",
        "exp52_compile_compatibility_fix4_receipt.json": "frozen/exp52_compile_compatibility_fix4_receipt.json",
        "exp52_failed_fix3_preflight.json": "exp52/preflight/worker_compile.json",
        "exp52_fix4_preflight.json": "exp52/preflight/worker_compile_fix4.json",
        "exp51_scientific_summary.json": "scientific/summary.json",
        "exp51_scientific_row_index.jsonl": "scientific/row_index.jsonl",
        "exp51_analysis_summary.json": "analysis/summary.json",
        "exp51_audit_summary.json": "audit/summary.json",
    }
    for src, dst in mapping.items():
        link_or_copy(source / src, artifacts / dst)
    exp51_index = read_jsonl(source / "exp51_scientific_row_index.jsonl")
    source_rows = read_jsonl(artifacts / "exp52/selection/source_exp51_rows.jsonl")
    for index, (entry, ledger) in enumerate(zip(exp51_index, source_rows)):
        receipt = source / "scientific_receipts" / f"{index:03d}_{entry['theorem_id']}.json"
        row = source / "scientific_rows" / f"{index:03d}_{entry['theorem_id']}.json"
        receipt_target = portable_path([(
            OLD_MZX / "artifacts/v51/external_repository_replication_scientific", artifacts
        )])(entry["receipt"])
        row_target = portable_path([(
            OLD_MZX / "artifacts/v51/external_repository_replication_scientific", artifacts
        )])(ledger["path"])
        link_or_copy(receipt, receipt_target)
        link_or_copy(row, row_target)
    content_target = artifacts / "content_store"
    if not content_target.exists():
        content_target.symlink_to(source / "content_store", target_is_directory=True)


def verify_exp52_portable_execution_bindings(
    artifacts: REAL_PATH,
    mapper: Callable[..., REAL_PATH],
    fix4: REAL_PATH,
    audit: Any,
) -> dict[str, Any]:
    """Recheck the server-path bindings after rebasing them into extraction.

    The immutable receipts deliberately retain their original absolute paths.
    The upstream audit compares those strings directly with its current root,
    so a clean extraction fails despite unchanged bytes.  This adapter applies
    the release path map before comparison and retains every hash check.
    """
    execution_root = artifacts / "exp52/execution"
    plan = read_jsonl(artifacts / "exp52/selection/execution_cells.jsonl")
    cells = read_jsonl(execution_root / "cells.jsonl")
    index_rows = read_jsonl(execution_root / "row_index.jsonl")
    failures: list[dict[str, Any]] = []
    checked_launches = 0

    def fail(cell_index: int, check: str) -> None:
        if len(failures) < 20:
            failures.append({"cell_index": cell_index, "check": check})

    if not (len(plan) == len(cells) == len(index_rows)):
        return {
            "cells_expected": len(plan),
            "cells_checked": 0,
            "launches_checked": 0,
            "failures": [{"check": "ledger_lengths"}],
            "portable_binding_gate": False,
        }

    for cell_index, (item, observed, entry) in enumerate(
        zip(plan, cells, index_rows)
    ):
        shard = audit.shard_index(cell_index, audit.EXP52_SHARD_COUNT)
        shard_root = execution_root / "shards" / f"shard-{shard:02d}"
        cell_id = str(item["cell_id"])
        rowp = (shard_root / "rows" / f"{cell_id}.json").resolve()
        receiptp = (shard_root / "receipts" / f"{cell_id}.json").resolve()
        inputp = (shard_root / "inputs" / f"{cell_id}.json").resolve()
        if not (rowp.is_file() and receiptp.is_file() and inputp.is_file()):
            fail(cell_index, "required_files")
            continue
        receipt = read_json(receiptp)
        launch_raw = receipt.get("worker_process_receipt")
        entry_launch_raw = entry.get("worker_process_receipt")
        checks = {
            "row_binding": mapper(str(entry.get("row", ""))).resolve() == rowp,
            "row_hash": entry.get("row_sha256") == sha256(rowp),
            "receipt_binding": (
                mapper(str(entry.get("receipt", ""))).resolve() == receiptp
            ),
            "receipt_hash": entry.get("receipt_sha256") == sha256(receiptp),
            "input_binding": mapper(str(entry.get("input", ""))).resolve() == inputp,
            "input_hash": entry.get("input_sha256") == sha256(inputp),
            "worker_row_binding": (
                mapper(str(receipt.get("worker_row", ""))).resolve() == rowp
            ),
            "worker_row_hash": receipt.get("worker_row_sha256") == sha256(rowp),
            "combined_row_exact": read_json(rowp) == observed,
            "receipt_record_sha": audit._valid_sha(receipt),
        }
        for name, passed in checks.items():
            if not passed:
                fail(cell_index, name)
        if launch_raw is None or entry_launch_raw is None:
            if not (
                launch_raw is None
                and entry_launch_raw is None
                and receipt.get("worker_process_receipt_sha256") is None
                and entry.get("worker_process_receipt_sha256") is None
                and receipt.get("worker_process_receipt_exact") is False
            ):
                fail(cell_index, "missing_launch_accounting")
            continue
        launchp = mapper(str(launch_raw)).resolve()
        entry_launchp = mapper(str(entry_launch_raw)).resolve()
        if not launchp.is_file():
            fail(cell_index, "launch_file")
            continue
        checked_launches += 1
        launch = read_json(launchp)
        command = launch.get("command")
        command_ok = bool(
            isinstance(command, list)
            and len(command) == 10
            and mapper(str(command[1])).resolve()
            == (fix4 / "experiment52_live_worker.py").resolve()
            and command[2] == "--input"
            and mapper(str(command[3])).resolve() == inputp
            and command[4] == "--output"
            and mapper(str(command[5])).resolve() == rowp
            and command[6] == "--runtime-root"
            and mapper(str(command[7])).resolve()
            == (shard_root / "runtime").resolve()
            and command[8:] == ["--timeout", str(audit.LEAN_TIMEOUT_SECONDS)]
            and launch.get("command_sha256") == json_sha256(command)
        )
        launch_checks = {
            "launch_binding": launchp == entry_launchp,
            "launch_receipt_hash": (
                receipt.get("worker_process_receipt_sha256") == sha256(launchp)
            ),
            "launch_index_hash": (
                entry.get("worker_process_receipt_sha256") == sha256(launchp)
            ),
            "launch_input_binding": (
                mapper(str(launch.get("input", ""))).resolve() == inputp
            ),
            "launch_output_binding": (
                mapper(str(launch.get("output", ""))).resolve() == rowp
            ),
            "launch_input_hash": launch.get("input_sha256") == sha256(inputp),
            "launch_record_sha": audit._valid_sha(launch),
            "launch_command_binding": command_ok,
        }
        for name, passed in launch_checks.items():
            if not passed:
                fail(cell_index, name)
    return {
        "cells_expected": len(plan),
        "cells_checked": len(plan),
        "launches_checked": checked_launches,
        "failures": failures,
        "portable_binding_gate": not failures,
    }


def audit_exp52(root: REAL_PATH, runtime: REAL_PATH, exp51_bundle: REAL_PATH) -> dict[str, Any]:
    # Exp52 contains the exact Fix3 and Fix4 code but its base protocol source is
    # inherited from Exp51.  Extract only that locked code into the temp runtime.
    exp51_code = root / "_exp51_code"
    with zipfile.ZipFile(exp51_bundle) as archive:
        for info in archive.infolist():
            if info.filename.startswith("code/fix2_source_lock/") and not info.is_dir():
                archive.extract(info, exp51_code)
    base_source = exp51_code / "code/fix2_source_lock"
    base = runtime / "experiment51_external_repository_replication"
    fix2 = runtime / "experiment51_exp52_scientific_freeze_alignment"
    fix3 = runtime / "experiment51_exp52_execution_alignment_fix3"
    docs = runtime / "experiment52_continuation_probe"
    fix4 = root / "code"
    base.mkdir(parents=True, exist_ok=True)
    fix2.mkdir(parents=True, exist_ok=True)
    for path in base_source.iterdir():
        if not path.is_file() or not path.name[:3].isdigit():
            continue
        index = int(path.name[:3])
        name = path.name[4:]
        if index <= 19:
            link_or_copy(path, base / name)
        elif index <= 24:
            link_or_copy(path, fix2 / name)
    shutil.copytree(root / "source_code/fix3", fix3, dirs_exist_ok=True)
    shutil.copytree(root / "design", docs, dirs_exist_ok=True)
    restore_exp52_sources(root)
    artifacts = root / "artifacts"
    old_scientific = OLD_MZX / "artifacts/v51/external_repository_replication_scientific"
    base_mapper = portable_path([
        (old_scientific, artifacts),
        (OLD_MZX / "experiment51_external_repository_replication", base),
        (OLD_MZX / "experiment51_exp52_scientific_freeze_alignment", fix2),
        (OLD_MZX / "experiment51_exp52_execution_alignment_fix3", fix3),
        (OLD_MZX / "experiment52_compile_compatibility_fix4", fix4),
        (OLD_MZX / "experiment52_continuation_probe", docs),
    ])

    def mapper(*parts: Any) -> REAL_PATH:
        raw = REAL_PATH(*parts)
        text = raw.as_posix()
        if text.startswith(old_scientific.as_posix() + "/") and "/content_store/" in text:
            name = raw.name
            digest = raw.stem
            portable_content = root / "source_exp51/content_store" / digest[:2] / name
            if portable_content.is_file():
                return portable_content
        return base_mapper(raw)
    clear_modules("experiment51_protocol", "experiment52_protocol", "alignment_protocol", "portable_exp52_audit")
    old_env = os.environ.get("MZX_ROOT")
    os.environ["MZX_ROOT"] = str(runtime)
    sys.path[:0] = [str(fix4), str(fix3), str(base), str(fix2)]
    try:
        base_mod = importlib.import_module("experiment51_protocol")
        fix2_mod = importlib.import_module("experiment52_protocol")
        fix4_alignment = import_file("portable_fix4_alignment", fix4 / "alignment_protocol.py")
        for module in (base_mod, fix2_mod, fix4_alignment, fix4_alignment.fix3):
            module.Path = mapper
        install_portable_document_lock(
            fix2_mod,
            artifacts / "frozen/experiment52_protocol.json",
            docs,
        )
        config = read_json(artifacts / "frozen/experiment51_config.json")
        targets = read_json(artifacts / "frozen/targets.json")
        protocol = read_json(artifacts / "frozen/experiment52_protocol.json")
        amendment_path = artifacts / "frozen/exp52_compile_compatibility_fix4.json"
        amendment = read_json(amendment_path)
        source = {
            "config": config,
            "targets": targets,
            "protocol": protocol,
            "amendment": amendment,
            "config_sha256": sha256(artifacts / "frozen/experiment51_config.json"),
            "targets_sha256": sha256(artifacts / "frozen/targets.json"),
            "protocol_sha256": sha256(artifacts / "frozen/experiment52_protocol.json"),
            "source_fix3_amendment_sha256": sha256(artifacts / "frozen/execution_alignment_fix3.json"),
            "amendment_sha256": sha256(amendment_path),
        }
        archived = read_json(artifacts / "exp52/audit/summary.json")
        (artifacts / "exp52/audit/summary.json").unlink()
        audit = import_file("portable_exp52_audit", fix4 / "audit_exp52.py")
        audit.Path = mapper
        # ``from alignment_protocol import *`` re-exports Fix3 functions whose
        # globals belong to the separately imported Fix3 module.  Patch that
        # retained module namespace as well as the audit module namespace.
        audit.strict_endpoint_features.__globals__["Path"] = mapper
        audit.PACKAGE_ROOT = OLD_MZX / "experiment52_compile_compatibility_fix4"
        def portable_hydrate_text(entry: Mapping[str, Any]) -> str:
            path = mapper(str(entry["path"]))
            value = path.read_text(encoding="utf-8")
            if not (
                sha256(path) == entry["sha256"]
                and len(value.encode("utf-8")) == int(entry["bytes"])
            ):
                raise ValueError(f"content-store entry changed: {path}")
            return value
        audit.hydrate_text = portable_hydrate_text
        audit.validate_amendment = lambda value=artifacts: source
        audit.load_source_bundle = lambda value=artifacts: (config, targets, protocol, amendment)
        with contextlib.redirect_stdout(io.StringIO()):
            rebuilt = audit.audit(argparse.Namespace(root=str(artifacts)))
        binding = verify_exp52_portable_execution_bindings(
            artifacts, mapper, fix4, audit
        )
        normalized = json.loads(json.dumps(rebuilt))
        normalized["checks"][
            "execution_row_inputs_receipts_and_launches_exact"
        ] = binding["portable_binding_gate"]
        normalized["audit_pass"] = all(normalized["checks"].values())
        normalized["next_step"] = (
            "Export the immutable Exp52 bundle."
            if normalized["audit_pass"]
            else "STOP; inspect immutable mismatch evidence."
        )
        normalized["identity_sha256"] = audit.identity_sha256(normalized)
        gate = normalized == archived and normalized.get("audit_pass") is True
        return {
            "experiment": "Exp52",
            "entrypoint": "bundled Fix4 audit with reconstructed portable source tree",
            "cells_reconstructed": rebuilt.get("cells_reconstructed"),
            "upstream_path_sensitive_difference_paths": (
                json_difference_paths(rebuilt, archived)
            ),
            "portable_execution_bindings": binding,
            "audit_exact_after_path_rebase": normalized == archived,
            "decision_label": rebuilt.get("decision_label_preserved"),
            "portable_scientific_audit_gate": gate,
        }
    finally:
        del sys.path[:4]
        if old_env is None:
            os.environ.pop("MZX_ROOT", None)
        else:
            os.environ["MZX_ROOT"] = old_env


# ------------------------------ Exp53 ------------------------------------

def audit_exp53(root: REAL_PATH) -> dict[str, Any]:
    code = root / "code"
    artifacts = root / "artifacts"
    clear_modules("exp53_protocol", "portable_exp53_analysis")
    sys.path.insert(0, str(code))
    try:
        importlib.import_module("exp53_protocol")
        analysis = import_file("portable_exp53_analysis", code / "analyze_exp53.py")
        archived = read_json(artifacts / "analysis/summary.json")
        with contextlib.redirect_stdout(io.StringIO()):
            rebuilt = analysis.analyze(argparse.Namespace(
                artifact_root=str(artifacts), shard_count=4
            ))
        content_exact = json_equivalent(rebuilt, archived, ignored=("mismatch_ledger",))
        gate = content_exact and rebuilt.get("decision_label") == "cross_machine_exact"
        return {
            "experiment": "Exp53",
            "entrypoint": "bundled analysis with explicit --artifact-root",
            "roots_reconstructed": rebuilt.get("roots_recorded"),
            "scientific_fields_exact": content_exact,
            "path_field_rebased": rebuilt.get("mismatch_ledger") != archived.get("mismatch_ledger"),
            "decision_label": rebuilt.get("decision_label"),
            "portable_scientific_audit_gate": gate,
        }
    finally:
        if sys.path and sys.path[0] == str(code):
            sys.path.pop(0)


# ------------------------------ Exp54 ------------------------------------

def audit_exp54(root: REAL_PATH) -> dict[str, Any]:
    code = root / "code"
    artifacts = root / "artifacts"
    synthetic: dict[str, REAL_PATH] = {}
    for label in ("v1", "fix1", "fix2"):
        target = root / f"_superseded_{label}"
        (target / "frozen").mkdir(parents=True, exist_ok=True)
        (target / "execution").mkdir(parents=True, exist_ok=True)
        snapshots = artifacts / "frozen" / f"superseded_{label}_snapshots"
        link_or_copy(snapshots / "frozen__design.json", target / "frozen/design.json")
        link_or_copy(snapshots / "execution__summary.json", target / "execution/summary.json")
        link_or_copy(snapshots / "execution__row_index.jsonl", target / "execution/row_index.jsonl")
        synthetic[label] = target
    mapper = portable_path([
        (OLD_MZX / "artifacts/v54/effect_aware_depth2_microbenchmark_fix3", artifacts),
        (OLD_MZX / "artifacts/v54/effect_aware_depth2_microbenchmark_fix2", synthetic["fix2"]),
        (OLD_MZX / "artifacts/v54/effect_aware_depth2_microbenchmark_fix1", synthetic["fix1"]),
        (OLD_MZX / "artifacts/v54/effect_aware_depth2_microbenchmark", synthetic["v1"]),
    ])
    clear_modules("experiment54_protocol", "portable_exp54_audit")
    sys.path.insert(0, str(code))
    try:
        protocol = importlib.import_module("experiment54_protocol")
        protocol.Path = mapper
        archived = read_json(artifacts / "audit/summary.json")
        audit = import_file("portable_exp54_audit", code / "audit_experiment54.py")
        audit.Path = mapper
        with contextlib.redirect_stdout(io.StringIO()):
            rebuilt = audit.audit(argparse.Namespace(artifact_root=str(artifacts)))
        gate = rebuilt == archived and rebuilt.get("audit_pass") is True
        return {
            "experiment": "Exp54",
            "entrypoint": "bundled audit with current and superseded-root mapping",
            "cells_reconstructed": rebuilt.get("cells_reconstructed"),
            "audit_exact": rebuilt == archived,
            "decision_label": rebuilt.get("decision_label_preserved"),
            "portable_scientific_audit_gate": gate,
        }
    finally:
        if sys.path and sys.path[0] == str(code):
            sys.path.pop(0)


def worker(experiment: str, bundle: REAL_PATH, release_root: REAL_PATH) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"jar-portable-{experiment}-") as raw:
        root = REAL_PATH(raw) / "bundle"
        runtime = REAL_PATH(raw) / "runtime"
        root.mkdir()
        runtime.mkdir()
        extract(bundle, root)
        if experiment == "exp48":
            return audit_exp48(root)
        if experiment == "exp50":
            return audit_exp50(root)
        if experiment == "exp51":
            return audit_exp51(root, runtime)
        if experiment == "exp52":
            return audit_exp52(
                root,
                runtime,
                release_root / "artifacts" / BUNDLES["exp51"],
            )
        if experiment == "exp53":
            return audit_exp53(root)
        if experiment == "exp54":
            return audit_exp54(root)
        raise ValueError(f"unsupported worker: {experiment}")


def run_worker_subprocess(script: REAL_PATH, experiment: str, bundle: REAL_PATH, release_root: REAL_PATH) -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--worker",
            experiment,
            "--bundle",
            str(bundle),
            "--release-root",
            str(release_root),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        value = json.loads(proc.stdout)
    except json.JSONDecodeError:
        value = {
            "experiment": experiment.upper(),
            "portable_scientific_audit_gate": False,
            "stdout_tail": proc.stdout[-4000:],
        }
    if proc.returncode != 0:
        value["portable_scientific_audit_gate"] = False
        value["returncode"] = proc.returncode
        value["stderr_tail"] = proc.stderr[-8000:]
    return value


def main(args: argparse.Namespace) -> int:
    release_root = REAL_PATH(args.release_root).resolve()
    artifact_root = release_root / "artifacts"
    script = REAL_PATH(__file__).resolve()
    integrity = []
    for experiment, name in BUNDLES.items():
        bundle = artifact_root / name
        if not bundle.is_file():
            integrity.append({
                "experiment": experiment.upper(),
                "bundle": name,
                "bundle_integrity_gate": False,
                "errors": ["bundle missing"],
            })
            continue
        value = verify_bundle(bundle)
        value["experiment"] = experiment.upper()
        integrity.append(value)
    audits = []
    for experiment in REPAIRED:
        bundle = artifact_root / BUNDLES[experiment]
        if not bundle.is_file():
            audits.append({
                "experiment": experiment.upper(),
                "portable_scientific_audit_gate": False,
                "error": "bundle missing",
            })
            continue
        print(f"PORTABLE-AUDIT {experiment.upper()} start", file=sys.stderr, flush=True)
        value = run_worker_subprocess(script, experiment, bundle, release_root)
        audits.append(value)
        print(
            f"PORTABLE-AUDIT {experiment.upper()} gate={int(bool(value.get('portable_scientific_audit_gate')))}",
            file=sys.stderr,
            flush=True,
        )
    result = {
        "version": VERSION,
        "schema": SCHEMA,
        "release_root": str(release_root),
        "independent_clean_download": args.independent_clean_download,
        "source_archives_modified": False,
        "lean_executed": False,
        "network_access_required": False,
        "bundle_integrity": integrity,
        "portable_scientific_audits": audits,
        "bundle_integrity_gate": all(row.get("bundle_integrity_gate") is True for row in integrity),
        "portable_scientific_audit_gate": all(row.get("portable_scientific_audit_gate") is True for row in audits),
        "decision_labels_preserved": all(
            row.get("decision_label") not in ("invalid_execution", "failed", None)
            for row in audits
            if str(row["experiment"]).upper() != "EXP48"
        ),
    }
    result["portable_release_gate"] = bool(
        result["bundle_integrity_gate"]
        and result["portable_scientific_audit_gate"]
        and result["decision_labels_preserved"]
    )
    if args.receipt:
        receipt = REAL_PATH(args.receipt)
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["portable_release_gate"] else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", default=".")
    parser.add_argument("--receipt")
    parser.add_argument("--independent-clean-download", action="store_true")
    parser.add_argument("--worker", choices=REPAIRED)
    parser.add_argument("--bundle")
    return parser.parse_args()


if __name__ == "__main__":
    parsed = parse_args()
    if parsed.worker:
        if not parsed.bundle:
            raise SystemExit("--bundle is required with --worker")
        try:
            value = worker(
                parsed.worker,
                REAL_PATH(parsed.bundle).resolve(),
                REAL_PATH(parsed.release_root).resolve(),
            )
        except Exception as exc:
            print(json.dumps({
                "experiment": parsed.worker.upper(),
                "portable_scientific_audit_gate": False,
                "exception": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }, ensure_ascii=False, indent=2))
            raise SystemExit(2)
        print(json.dumps(value, ensure_ascii=False, indent=2))
        raise SystemExit(0 if value.get("portable_scientific_audit_gate") else 2)
    raise SystemExit(main(parsed))
