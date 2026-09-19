"""Zero-scientific-candidate build, trace, enumeration, and authored replay screening."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import threading
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from experiment51_protocol import *
from experiment51_trace_runtime import (
    V427_EXTRACTOR_SHA256,
    classify_lean_line_endings,
    import_traced_repo,
    write_extractor,
)

WORKER = PACKAGE_ROOT / "experiment51_live_worker.py"
ENUMERATION_WORKER = PACKAGE_ROOT / "experiment51_enumeration_worker.py"
EXCLUDED_PARTS = {".git", ".lake", "lake-packages", "build", "vendor", "vendored",
                  "generated", "benchmark", "benchmarks", "deps", "dependencies",
                  "test", "tests"}
INCOMPLETE_PROOF_RE = re.compile(r"(^|\W)(sorry|admit)(\W|$)")


def run_cmd(cmd: list[str], cwd: Path, timeout: int, check: bool = False) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed {cmd}:\n{proc.stderr[-12000:]}")
    return proc


def run_cmd_isolated(cmd: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    """Run one process group so a repository timeout cannot leak Lean children."""
    proc = subprocess.Popen(
        cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            stdout, stderr = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
        raise TimeoutError(
            f"isolated command timed out after {timeout}s: {cmd}; "
            f"stdout={stdout[-2000:]!r}; stderr={stderr[-4000:]!r}"
        ) from exc
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)


def locate_ast(project: Path, file_path: str) -> Path:
    rel = Path(file_path).with_suffix(".ast.json")
    for path in (project / ".lake/build/ir" / rel, project / "build/ir" / rel):
        if path.is_file():
            return path.resolve()
    raise FileNotFoundError(f"no ast.json for {file_path}")


def raw_pos(value: Any) -> int:
    if isinstance(value, bool):
        raise TypeError(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    if isinstance(value, dict):
        for key in ("byteIdx", "raw", "byte", "offset", "value", "pos"):
            if key in value:
                return raw_pos(value[key])
    if isinstance(value, (list, tuple)) and len(value) == 1:
        return raw_pos(value[0])
    raise TypeError(f"unsupported raw position: {value!r}")


def field(row: dict[str, Any], *names: str) -> Any:
    return next((row[x] for x in names if x in row), None)


def norm_tactic(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def source_slice(source: str, start: int, end: int) -> str:
    raw = source.encode("utf-8")
    return raw[start:end].decode("utf-8")


def resolve_edge(ast_path: Path, source_path: Path, state: str, tactic: str) -> dict[str, Any]:
    ast = read_json(ast_path)
    rows = ast.get("tactics") if isinstance(ast, dict) else None
    if not isinstance(rows, list):
        raise ValueError("missing tactics array")
    source = source_path.read_text(encoding="utf-8")
    state_norm, tactic_norm = normalize_goal_text(state), norm_tactic(tactic)
    state_matches, exact = [], []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        before = field(row, "stateBefore", "state_before")
        if normalize_goal_text(before) != state_norm:
            continue
        start = raw_pos(field(row, "pos", "startPos", "start_pos"))
        end = raw_pos(field(row, "endPos", "end_pos", "tailPos"))
        text = source_slice(source, start, end)
        item = {"record_index": index, "target_pos": start, "target_end_pos": end,
                "source_tactic": text, "state_after": str(field(row, "stateAfter", "state_after"))}
        state_matches.append(item)
        if norm_tactic(text) == tactic_norm:
            exact.append(item)
    if len(exact) != 1:
        raise ValueError(f"ambiguous edge state={len(state_matches)} exact={len(exact)}")
    return exact[0]


def excluded_source(path: Path) -> bool:
    lowered = {x.lower() for x in path.parts}
    return bool(lowered.intersection(EXCLUDED_PARTS))


def git_root(path: Path, timeout: int) -> Path:
    proc = run_cmd(["git", "rev-parse", "--show-toplevel"], path, timeout, True)
    return Path(proc.stdout.strip()).resolve()


def clone_checkout(candidate: dict[str, Any], timeout: int) -> tuple[Path, Path, str]:
    checkout = SCREEN_CHECKOUT_ROOT / safe_slug(candidate["slug"])
    if not checkout.exists():
        checkout.parent.mkdir(parents=True, exist_ok=True)
        run_cmd(["git", "clone", "--filter=blob:none", candidate["url"], str(checkout)],
                SERVER_ROOT, timeout, True)
    root = git_root(checkout, timeout)
    origin = run_cmd(["git", "remote", "get-url", "origin"], root, timeout, True).stdout.strip()
    if origin.rstrip("/").removesuffix(".git").lower() != candidate["url"].rstrip("/").removesuffix(".git").lower():
        raise ValueError(f"origin mismatch: {origin}")
    fetch = run_cmd(["git", "fetch", "origin", candidate["ref"]], root, timeout)
    if fetch.returncode != 0:
        run_cmd(["git", "fetch", "--tags", "origin"], root, timeout, True)
    resolved = None
    for revision in (f"{candidate['ref']}^{{commit}}",
                     f"origin/{candidate['ref']}^{{commit}}", "FETCH_HEAD^{commit}"):
        probe = run_cmd(["git", "rev-parse", "--verify", revision], root, timeout)
        if probe.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", probe.stdout.strip()):
            resolved = probe.stdout.strip()
            break
    if resolved is None:
        raise ValueError(f"cannot resolve candidate ref to an exact commit: {candidate['ref']}")
    switch = run_cmd(["git", "switch", "--detach", resolved], root, timeout)
    if switch.returncode != 0:
        run_cmd(["git", "checkout", "--detach", resolved], root, timeout, True)
    commit = run_cmd(["git", "rev-parse", "HEAD"], root, timeout, True).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("non-exact resolved commit")
    subdir = candidate.get("subdir", ".")
    project = (root / subdir).resolve()
    if not project.is_dir():
        raise FileNotFoundError(project)
    return root, project, commit


def license_files(root: Path) -> list[str]:
    return sorted(p.name for p in root.iterdir() if p.is_file()
                  and p.name.lower().startswith(("license", "licence", "copying")))


def source_inventory(project: Path) -> tuple[list[dict[str, Any]], set[str]]:
    rows = []
    hashes: set[str] = set()
    for path in sorted(project.rglob("*.lean")):
        rel = path.relative_to(project)
        if excluded_source(rel):
            continue
        sha = file_sha256(path)
        source = path.read_text(encoding="utf-8", errors="strict")
        normalized_sha = text_sha256(re.sub(r"\s+", "", source))
        rows.append({"path": rel.as_posix(), "sha256": sha,
                     "normalized_whitespace_free_sha256": normalized_sha,
                     "bytes": path.stat().st_size})
        hashes.add(normalized_sha)
    return rows, hashes


def source_line_ending_inventory(
    project: Path, inventory: list[dict[str, Any]],
) -> dict[str, int]:
    """Measure line endings over the already hash-validated repository sources."""
    lf_only_files = 0
    standard_crlf_files = 0
    standard_crlf_lines = 0
    for row in inventory:
        path = (project / row["path"]).resolve()
        if not path.is_relative_to(project.resolve()) or not path.is_file():
            raise ValueError(f"source line-ending path escaped inventory: {path}")
        if file_sha256(path) != row["sha256"]:
            raise ValueError(f"source changed before line-ending measurement: {path}")
        measurement = classify_lean_line_endings(path.read_bytes())
        if measurement["schema"] == "standard-crlf":
            standard_crlf_files += 1
            standard_crlf_lines += int(measurement["crlf_lines"])
        else:
            lf_only_files += 1
    return {
        "source_files_scanned": len(inventory),
        "lf_only_files": lf_only_files,
        "standard_crlf_files": standard_crlf_files,
        "standard_crlf_lines": standard_crlf_lines,
        "line_ending_rejections": 0,
    }


def clear_repository_trace_artifacts(project: Path) -> dict[str, Any]:
    paths: list[Path] = []
    for base in (project / ".lake/build/ir", project / "build/ir"):
        if not base.is_dir():
            continue
        paths.extend(base.rglob("*.ast.json"))
        paths.extend(base.rglob("*.dep_paths"))
    paths = sorted(set(path.resolve() for path in paths))
    ledger = []
    for path in paths:
        if not path.is_relative_to(project.resolve()):
            raise ValueError(f"trace cleanup escaped project: {path}")
        ledger.append({
            "path": path.relative_to(project).as_posix(),
            "sha256": file_sha256(path), "bytes": path.stat().st_size,
        })
    for path in paths:
        path.unlink()
    return {
        "removed_generated_files": len(ledger),
        "removed_generated_ledger_sha256": json_sha256(ledger),
    }


def remove_verified_stale_extractor(path: Path) -> dict[str, Any]:
    """Remove only a prior generated extractor with the exact frozen content."""
    if path.is_symlink():
        raise ValueError(f"refusing stale extractor symlink: {path}")
    if not path.exists():
        return {"present": False, "removed": False, "sha256": None}
    if not path.is_file():
        raise ValueError(f"stale extractor path is not a regular file: {path}")
    digest = file_sha256(path)
    if digest != V427_EXTRACTOR_SHA256:
        raise ValueError(f"refusing to remove non-frozen ExtractData.lean: {path} sha256={digest}")
    path.unlink()
    return {"present": True, "removed": True, "sha256": digest}


def trace_project(project: Path, timeout: int, threads: int,
                  preparation_slots: threading.Semaphore) -> dict[str, Any]:
    prefix_proc = run_cmd(["lake", "env", "lean", "--print-prefix"], project, 300, True)
    lean_prefix = Path(prefix_proc.stdout.strip()).resolve()
    if not (lean_prefix / "src").is_dir() or not (lean_prefix / "lib").is_dir():
        raise FileNotFoundError(f"invalid Lean prefix for extraction: {lean_prefix}")
    with preparation_slots:
        cleanup = clear_repository_trace_artifacts(project)
        lean_package = project / ".lake/packages/lean4"
        shutil.copytree(lean_prefix, lean_package, dirs_exist_ok=True)
        # LeanDojo's processAllFiles subprocess command is intentionally hard-coded
        # to this basename, so the temporary copy must keep it exactly.
        local = project / "ExtractData.lean"
        stale_extractor = remove_verified_stale_extractor(local)
        runtime = write_extractor(local)
    try:
        proc = run_cmd_isolated(
            ["lake", "env", "lean", "--threads", str(threads), "--run",
             local.name, "noDeps"], project, timeout,
        )
    finally:
        local.unlink(missing_ok=True)
    asts = list(project.glob(".lake/build/ir/**/*.ast.json"))
    asts += list(project.glob("build/ir/**/*.ast.json"))
    return {"returncode": proc.returncode, "stdout_tail": proc.stdout[-8000:],
            "stderr_tail": proc.stderr[-12000:], "ast_files": len(asts),
            "trace_ok": proc.returncode == 0 and bool(asts),
            "trace_runtime": runtime,
            "fresh_trace_cleanup": cleanup,
            "stale_extractor_recovery": stale_extractor,
            "extractor_sha256": runtime["v427_extractor_sha256"],
            "lean_prefix": str(lean_prefix),
            "lean_prefix_copied_to": str(lean_package)}


def enumerate_frame(project: Path, slug: str, commit: str) -> tuple[list[dict[str, Any]], Counter[str]]:
    TracedRepo = import_traced_repo()
    traced = TracedRepo.from_traced_files(project, build_deps=False)
    rows: list[dict[str, Any]] = []
    excluded: Counter[str] = Counter()
    seen_names: set[str] = set()
    theorems = sorted(traced.get_traced_theorems(), key=lambda t: (str(t.file_path), t.theorem.full_name))
    for theorem in theorems:
        full_name = str(theorem.theorem.full_name)
        file_path = Path(theorem.file_path)
        if theorem.repo != traced.repo:
            excluded["dependency_theorem"] += 1
            continue
        if full_name in seen_names:
            excluded["duplicate_theorem_name"] += 1
            continue
        seen_names.add(full_name)
        if excluded_source(file_path):
            excluded["non_repository_authored_path"] += 1
            continue
        sourcep = (project / file_path).resolve()
        header = sourcep.read_text(encoding="utf-8", errors="replace")[:4096].lower()
        if any(marker in header for marker in ("automatically generated", "generated by", "do not edit")):
            excluded["generated_source_header"] += 1
            continue
        try:
            proof = theorem.get_tactic_proof()
        except Exception:
            proof = None
        if not proof:
            excluded["not_tactic_proof"] += 1
            continue
        if INCOMPLETE_PROOF_RE.search(proof):
            excluded["incomplete_proof_marker"] += 1
            continue
        try:
            tactics = theorem.get_traced_tactics()
        except Exception:
            excluded["trace_tactic_parse_failure"] += 1
            continue
        tactics = [x for x in tactics if x.state_before != "no goals" and "·" not in x.tactic]
        if not tactics:
            excluded["no_unambiguous_authored_tactic"] += 1
            continue
        tactic = tactics[0]
        try:
            astp = locate_ast(project, file_path.as_posix())
            edge = resolve_edge(astp, sourcep, tactic.state_before, tactic.tactic)
        except Exception:
            excluded["ambiguous_or_missing_ast_edge"] += 1
            continue
        identity = {"slug": slug, "commit": commit, "file_path": file_path.as_posix(),
                    "full_name": full_name, "target_pos": edge["target_pos"],
                    "target_end_pos": edge["target_end_pos"]}
        theorem_id = json_sha256(identity)
        rows.append({
            **identity, "theorem_id": theorem_id, "rid": theorem_id[:20],
            "checkout": str(project), "source_file_sha256": file_sha256(sourcep),
            "ast_path": str(astp), "ast_sha256": file_sha256(astp),
            "ast_record_index": edge["record_index"],
            "authored_tactic": tactic.tactic,
            "trace_root_state": tactic.state_before,
            "trace_root_state_sha256": text_sha256(normalize_goal_text(tactic.state_before)),
            "trace_state_after_sha256": text_sha256(normalize_goal_text(tactic.state_after)),
        })
    rows.sort(key=lambda x: (x["file_path"], x["full_name"], x["target_pos"], x["theorem_id"]))
    return rows, excluded


def enumerate_frame_isolated(project: Path, slug: str, commit: str, root: Path,
                             framep: Path, timeout: int,
                             trace_reuse_ledger_sha256: str | None = None
                             ) -> tuple[list[dict[str, Any]], Counter[str], dict[str, Any]]:
    """Run LeanDojo parsing in a fresh process because it mutates process-global state."""
    inputp = root / "screening/enumeration_inputs" / f"{safe_slug(slug)}.json"
    receiptp = root / "screening/enumeration_receipts" / f"{safe_slug(slug)}.json"
    payload = {
        "version": 1,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "project": str(project),
        "slug": slug,
        "commit": commit,
        "frame_output": str(framep),
        "receipt_output": str(receiptp),
        "position_adapter_schema": V427_POSITION_ADAPTER_SCHEMA,
        "parser_compatibility_schema": V427_PARSER_COMPATIBILITY_SCHEMA,
        "parser_execution_profile": PARSER_EXECUTION_PROFILE,
        "trace_reuse_ledger_sha256": trace_reuse_ledger_sha256,
        "scientific_candidate_tactics_permitted": 0,
    }
    payload["identity_sha256"] = json_sha256(payload)
    atomic_json_dump(payload, inputp)
    proc = run_cmd_isolated(
        [sys.executable, str(ENUMERATION_WORKER), "--input", str(inputp)],
        PACKAGE_ROOT,
        timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"isolated enumeration failed returncode={proc.returncode}; "
            f"stdout={proc.stdout[-4000:]!r}; stderr={proc.stderr[-12000:]!r}"
        )
    if not receiptp.is_file() or not framep.is_file():
        raise FileNotFoundError(f"isolated enumeration omitted outputs for {slug}")
    receipt = read_json(receiptp)
    if not (
        receipt.get("worker_ok") is True
        and receipt.get("input_identity_sha256") == payload["identity_sha256"]
        and receipt.get("slug") == slug
        and receipt.get("commit") == commit
        and receipt.get("frame_sha256") == file_sha256(framep)
        and receipt.get("scientific_candidate_tactics_executed") == 0
        and receipt.get("position_adapter", {}).get("schema") == V427_POSITION_ADAPTER_SCHEMA
        and receipt.get("position_adapter", {}).get("parser_compatibility_schema")
        == V427_PARSER_COMPATIBILITY_SCHEMA
        and receipt.get("position_adapter", {}).get("installed_parser_files_unchanged") is True
        and receipt.get("position_adapter", {}).get("counters", {}).get("v427_byteIdx", 0) > 0
        and receipt.get("position_adapter", {}).get("counters", {}).get("rejected") == 0
        and receipt.get("position_adapter", {}).get("section_adapter", {})
        .get("counters", {}).get("rejected") == 0
        and receipt.get("position_adapter", {}).get("section_adapter", {})
        .get("header_counters", {}).get("rejected") == 0
        and receipt.get("position_adapter", {}).get("crlf_adapter", {})
        .get("counters", {}).get("rejected") == 0
        and receipt.get("position_adapter", {}).get("crlf_adapter", {}).get("accepted")
        == "standard-CRLF-normalized-to-LF-byte-width"
        and receipt.get("position_adapter", {}).get("crlf_adapter", {})
        .get("byte_index_semantics") == "Lean-v4.27-LF-normalized-source-buffer"
        and receipt.get("position_adapter", {}).get("crlf_adapter", {})
        .get("checkout_modified") is False
        and receipt.get("position_adapter", {}).get("parser_execution", {}).get("profile")
        == PARSER_EXECUTION_PROFILE
        and receipt.get("position_adapter", {}).get("parser_execution", {}).get("num_procs") == 2
        and receipt.get("position_adapter", {}).get("parser_execution", {}).get("num_workers") == 1
        and receipt.get("position_adapter", {}).get("parser_execution", {}).get("ray_initialized") is False
        and receipt.get("position_adapter", {}).get("parser_execution", {}).get("adapter_process_pid")
        == receipt.get("worker_pid")
        and receipt.get("trace_reuse_ledger_sha256") == trace_reuse_ledger_sha256
    ):
        raise ValueError(f"isolated enumeration receipt failed validation for {slug}")
    frame = read_jsonl(framep)
    if receipt.get("pre_replay_frame") != len(frame):
        raise ValueError(f"isolated enumeration count differs for {slug}")
    exclusions = Counter({str(k): int(v) for k, v in receipt.get("exclusions", {}).items()})
    return frame, exclusions, receipt


def build_trace_one(candidate: dict[str, Any], args: argparse.Namespace, root: Path,
                    build_slots: threading.Semaphore,
                    trace_slots: threading.Semaphore,
                    enumeration_slots: threading.Semaphore) -> dict[str, Any]:
    slug = candidate["slug"]
    outp = root / "screening/build_trace" / f"{safe_slug(slug)}.json"
    framep = root / "screening/frames" / f"{safe_slug(slug)}.jsonl"
    if outp.exists():
        value = read_json(outp)
        if value.get("candidate") != candidate:
            raise ValueError(f"candidate changed for {slug}")
        return value
    value: dict[str, Any] = {"version": 1, "candidate": candidate,
                             "scientific_candidate_tactics_executed": 0}
    first_failed_gate = "checkout"
    try:
        with build_slots:
            gitroot, project, commit = clone_checkout(candidate, args.git_timeout)
            value.update({"git_root": str(gitroot), "project": str(project), "commit": commit})
            toolchainp = project / "lean-toolchain"
            toolchain = toolchainp.read_text(encoding="utf-8").strip() if toolchainp.is_file() else None
            value["toolchain"] = toolchain
            if toolchain != TARGET_TOOLCHAIN:
                first_failed_gate = "exact_toolchain"
                raise ValueError(f"requires {TARGET_TOOLCHAIN}, found {toolchain}")
            licenses = license_files(gitroot)
            value["license_files"] = licenses
            if not licenses:
                first_failed_gate = "archival_license"
                raise ValueError("no root license file")
            try:
                cache = run_cmd(["lake", "exe", "cache", "get"], project, args.build_timeout)
                value["cache_get"] = {"returncode": cache.returncode,
                                      "stderr_tail": cache.stderr[-4000:]}
            except Exception as exc:
                value["cache_get"] = {"returncode": None, "non_gate_error": type(exc).__name__,
                                      "stderr_tail": str(exc)[-4000:]}
            build = run_cmd(["lake", "build"], project, args.build_timeout)
            value["build"] = {"returncode": build.returncode, "stdout_tail": build.stdout[-6000:],
                              "stderr_tail": build.stderr[-12000:]}
            if build.returncode != 0:
                first_failed_gate = "unmodified_build"
                raise RuntimeError("lake build failed")
            version = run_cmd(["lake", "env", "lean", "--version"], project, 300)
            version_text = (version.stdout + "\n" + version.stderr).strip()
            value["lean_version"] = version_text
            if version.returncode != 0 or "version 4.27.0" not in version_text:
                first_failed_gate = "lean_version"
                raise ValueError(version_text)
            inventory, hashes = source_inventory(project)
            value["source_inventory"] = {"files": len(inventory),
                                         "inventory_sha256": json_sha256(inventory),
                                         "unique_source_hashes": len(hashes)}
            atomic_jsonl_dump(inventory, root / "screening/source_inventories" / f"{safe_slug(slug)}.jsonl")
        first_failed_gate = "trace"
        print(f"EXP51-STAGE {slug} trace-start threads={args.threads}", flush=True)
        with trace_slots:
            trace = trace_project(project, args.trace_timeout, args.threads, build_slots)
        value["trace"] = trace
        if not trace["trace_ok"]:
            raise RuntimeError("LeanDojo trace failed")
        print(f"EXP51-STAGE {slug} trace-done ast_files={trace['ast_files']}", flush=True)
        first_failed_gate = "root_enumeration"
        with enumeration_slots:
            frame, exclusions, enumeration_receipt = enumerate_frame_isolated(
                project, slug, commit, root, framep, args.enumeration_timeout,
            )
        value["enumeration"] = {"theorems_seen": len(frame) + sum(exclusions.values()),
                                "pre_replay_frame": len(frame),
                                "exclusions": dict(sorted(exclusions.items())),
                                "frame_sha256": file_sha256(framep),
                                "process_isolation": QUALIFICATION_ENUMERATION_ISOLATION,
                                "worker_receipt_sha256": file_sha256(
                                    root / "screening/enumeration_receipts" / f"{safe_slug(slug)}.json"
                                ),
                                "worker_pid": enumeration_receipt["worker_pid"]}
        if len(frame) < ROOTS_PER_REPOSITORY:
            first_failed_gate = "minimum_pre_replay_frame"
            raise ValueError(f"only {len(frame)} trace-qualified theorem roots")
        status = run_cmd(["git", "status", "--porcelain", "--untracked-files=no"], gitroot, 300)
        value["tracked_checkout_clean_after_trace"] = status.returncode == 0 and not status.stdout.strip()
        if not value["tracked_checkout_clean_after_trace"]:
            first_failed_gate = "unchanged_checkout"
            raise ValueError(status.stdout)
        first_failed_gate = None
        value["build_trace_gate"] = True
    except Exception as exc:
        value["build_trace_gate"] = False
        value["error"] = {"type": type(exc).__name__, "message": str(exc)[-12000:]}
    value["first_failed_gate"] = first_failed_gate
    atomic_json_dump(value, outp)
    return value


def trace_artifact_ledger(project: Path) -> list[dict[str, Any]]:
    project = project.resolve()
    paths: list[Path] = []
    for base in (project / ".lake/build/ir", project / "build/ir"):
        if base.is_dir():
            paths.extend(base.rglob("*.ast.json"))
    resolved = sorted(set(path.resolve() for path in paths))
    ledger = []
    for path in resolved:
        if not path.is_relative_to(project):
            raise ValueError(f"trace artifact escaped checkout: {path}")
        ledger.append({
            "path": path.relative_to(project).as_posix(),
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        })
    return ledger


def validate_fix4_trace_reuse(candidate: dict[str, Any], root: Path) -> dict[str, Any]:
    slug = candidate["slug"]
    safe = safe_slug(slug)
    source_receiptp = SOURCE_FIX4_ROOT / "screening/build_trace" / f"{safe}.json"
    source_inventoryp = SOURCE_FIX4_ROOT / "screening/source_inventories" / f"{safe}.jsonl"
    source = read_json(source_receiptp)
    trace = source.get("trace", {})
    if not (
        source.get("candidate") == candidate
        and source.get("first_failed_gate") == "root_enumeration"
        and source.get("scientific_candidate_tactics_executed") == 0
        and trace.get("trace_ok") is True
        and trace.get("returncode") == 0
        and trace.get("extractor_sha256") == V427_EXTRACTOR_SHA256
        and trace.get("trace_runtime", {}).get("lean_dojo_source_ledger_exact") is True
        and source_inventoryp.is_file()
    ):
        raise ValueError(f"fix4 receipt is not a reusable zero-candidate trace: {slug}")

    project = Path(source["project"]).resolve()
    gitroot = Path(source["git_root"]).resolve()
    commit = run_cmd(["git", "rev-parse", "HEAD"], gitroot, 300, True).stdout.strip()
    if commit != source.get("commit"):
        raise ValueError(f"fix4 checkout commit changed: {slug}")
    toolchainp = project / "lean-toolchain"
    if not toolchainp.is_file() or toolchainp.read_text(encoding="utf-8").strip() != TARGET_TOOLCHAIN:
        raise ValueError(f"fix4 checkout toolchain changed: {slug}")
    status = run_cmd(["git", "status", "--porcelain", "--untracked-files=no"], gitroot, 300, True)
    if status.stdout.strip():
        raise ValueError(f"fix4 tracked checkout changed: {slug}: {status.stdout}")

    archived_inventory = read_jsonl(source_inventoryp)
    current_inventory, current_hashes = source_inventory(project)
    inventory_meta = source.get("source_inventory", {})
    if not (
        current_inventory == archived_inventory
        and len(current_inventory) == inventory_meta.get("files")
        and len(current_hashes) == inventory_meta.get("unique_source_hashes")
        and json_sha256(current_inventory) == inventory_meta.get("inventory_sha256")
    ):
        raise ValueError(f"fix4 repository source inventory changed: {slug}")
    source_line_endings = source_line_ending_inventory(project, current_inventory)
    active_inventoryp = root / "screening/source_inventories" / f"{safe}.jsonl"
    atomic_jsonl_dump(current_inventory, active_inventoryp)

    ast_ledger = trace_artifact_ledger(project)
    if len(ast_ledger) != trace.get("ast_files") or not ast_ledger:
        raise ValueError(
            f"fix4 trace artifact count changed: {slug}; "
            f"expected={trace.get('ast_files')} observed={len(ast_ledger)}"
        )
    ledgerp = root / "screening/reused_trace_ledgers" / f"{safe}.jsonl"
    atomic_jsonl_dump(ast_ledger, ledgerp)
    return {
        "schema": TRACE_REUSE_SCHEMA,
        "source_fix4_receipt": str(source_receiptp),
        "source_fix4_receipt_sha256": file_sha256(source_receiptp),
        "source_fix4_inventory": str(source_inventoryp),
        "source_fix4_inventory_sha256": file_sha256(source_inventoryp),
        "active_inventory": str(active_inventoryp),
        "active_inventory_sha256": file_sha256(active_inventoryp),
        "commit_exact": True,
        "toolchain_exact": True,
        "tracked_checkout_clean": True,
        "source_inventory_exact": True,
        "source_line_endings": source_line_endings,
        "trace_runtime_exact": True,
        "trace_execution_repeated": False,
        "ast_files": len(ast_ledger),
        "ast_ledger": str(ledgerp),
        "ast_ledger_sha256": file_sha256(ledgerp),
    }


def recover_fix4_one(candidate: dict[str, Any], args: argparse.Namespace,
                     root: Path) -> dict[str, Any]:
    slug = candidate["slug"]
    safe = safe_slug(slug)
    outp = root / "screening/build_trace" / f"{safe}.json"
    if outp.is_file():
        value = read_json(outp)
        if value.get("candidate") != candidate:
            raise ValueError(f"recovered candidate changed for {slug}")
        return value
    sourcep = SOURCE_FIX4_ROOT / "screening/build_trace" / f"{safe}.json"
    source = read_json(sourcep)
    if source.get("candidate") != candidate or source.get("scientific_candidate_tactics_executed") != 0:
        raise ValueError(f"invalid fix4 source receipt for {slug}")
    if source.get("first_failed_gate") != "root_enumeration":
        value = dict(source)
        value["mechanical_fix_id"] = MECHANICAL_FIX_ID
        value["recovery"] = {
            "schema": TRACE_REUSE_SCHEMA,
            "carried_forward_qualification_failure": True,
            "source_fix4_receipt": str(sourcep),
            "source_fix4_receipt_sha256": file_sha256(sourcep),
            "trace_or_build_repeated": False,
            "scientific_candidate_tactics_executed": 0,
        }
        atomic_json_dump(value, outp)
        return value

    value = dict(source)
    value.pop("error", None)
    value["mechanical_fix_id"] = MECHANICAL_FIX_ID
    first_failed_gate = "trace_reuse_validation"
    try:
        reuse = validate_fix4_trace_reuse(candidate, root)
        value["trace_reuse"] = reuse
        first_failed_gate = "root_enumeration"
        project = Path(source["project"]).resolve()
        framep = root / "screening/frames" / f"{safe}.jsonl"
        print(f"EXP51-RECOVERY {slug} enumeration-start", flush=True)
        frame, exclusions, enumeration_receipt = enumerate_frame_isolated(
            project, slug, source["commit"], root, framep,
            args.enumeration_timeout, reuse["ast_ledger_sha256"],
        )
        print(
            f"EXP51-RECOVERY {slug} enumeration-done roots={len(frame)} "
            f"byteIdx={enumeration_receipt['position_adapter']['counters']['v427_byteIdx']}",
            flush=True,
        )
        value["enumeration"] = {
            "theorems_seen": len(frame) + sum(exclusions.values()),
            "pre_replay_frame": len(frame),
            "exclusions": dict(sorted(exclusions.items())),
            "frame_sha256": file_sha256(framep),
            "process_isolation": QUALIFICATION_ENUMERATION_ISOLATION,
            "position_adapter_schema": V427_POSITION_ADAPTER_SCHEMA,
            "parser_compatibility_schema": V427_PARSER_COMPATIBILITY_SCHEMA,
            "parser_compatibility_expected": PARSER_COMPATIBILITY_EXPECTED,
            "checkout_line_endings_expected": CHECKOUT_LINE_ENDING_EXPECTED,
            "parser_execution_profile": PARSER_EXECUTION_PROFILE,
            "worker_receipt_sha256": file_sha256(
                root / "screening/enumeration_receipts" / f"{safe}.json"
            ),
            "worker_pid": enumeration_receipt["worker_pid"],
            "trace_reuse_ledger_sha256": reuse["ast_ledger_sha256"],
        }
        if slug in FIX8_FRAME_CONTROLS:
            expectedp = SOURCE_FIX8_ROOT / "screening/frames" / f"{safe}.jsonl"
            if not expectedp.is_file():
                first_failed_gate = "fix8_exact_frame_control"
                raise FileNotFoundError(expectedp)
            expected = read_jsonl(expectedp)
            exact = bool(
                len(expected) == FIX8_FRAME_CONTROLS[slug]
                and frame == expected
                and file_sha256(framep) == file_sha256(expectedp)
            )
            value["fix8_frame_control"] = {
                "expected_frame": str(expectedp),
                "expected_frame_sha256": file_sha256(expectedp),
                "observed_frame_sha256": file_sha256(framep),
                "expected_roots": FIX8_FRAME_CONTROLS[slug],
                "observed_roots": len(frame),
                "exact": exact,
            }
            if not exact:
                first_failed_gate = "fix8_exact_frame_control"
                raise ValueError(f"fix9 frame differs from protected fix8 success: {slug}")
        if len(frame) < ROOTS_PER_REPOSITORY:
            first_failed_gate = "minimum_pre_replay_frame"
            raise ValueError(f"only {len(frame)} trace-qualified theorem roots")
        first_failed_gate = None
        value["build_trace_gate"] = True
    except Exception as exc:
        value["build_trace_gate"] = False
        value["error"] = {"type": type(exc).__name__, "message": str(exc)[-12000:]}
    value["first_failed_gate"] = first_failed_gate
    value["scientific_candidate_tactics_executed"] = 0
    atomic_json_dump(value, outp)
    return value


def worker_input(root: Path, target: dict[str, Any], cfg_sha: str,
                 candidates: list[str], mode: str) -> dict[str, Any]:
    positions = [target.get("alternatives", candidates).index(x) for x in candidates]
    value = {
        "version": 1, "protocol_version": PROTOCOL_VERSION, "mode": mode,
        "config_sha256": cfg_sha, "environment_receipt_sha256": "screening-zero-candidate",
        "artifact_root": str(root), "project": target["checkout"], "slug": target["slug"],
        "commit": target["commit"], "file_path": target["file_path"],
        "full_name": target["full_name"], "theorem_id": target["theorem_id"],
        "source_file_sha256": target["source_file_sha256"],
        "trace_root_state": target["trace_root_state"],
        "trace_root_state_sha256": target["trace_root_state_sha256"],
        "authored_tactic": target["authored_tactic"],
        "target_pos": target["target_pos"], "target_end_pos": target["target_end_pos"],
        "ast_sha256": target["ast_sha256"], "candidates": candidates,
        "candidates_sha256": json_sha256(candidates),
        "candidate_positions_frozen": positions,
    }
    value["execution_record_id"] = json_sha256({
        "protocol": PROTOCOL_VERSION, "mode": mode, "theorem_id": target["theorem_id"],
        "candidates": candidates})
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def replay_one(candidate: dict[str, Any], args: argparse.Namespace, root: Path,
               cfg_sha: str) -> dict[str, Any]:
    slug = candidate["slug"]
    build = read_json(root / "screening/build_trace" / f"{safe_slug(slug)}.json")
    summaryp = root / "screening/replay" / f"{safe_slug(slug)}.json"
    if summaryp.exists():
        return read_json(summaryp)
    value: dict[str, Any] = {"version": 1, "slug": slug, "commit": build.get("commit"),
                             "scientific_candidate_tactics_executed": 0}
    if build.get("build_trace_gate") is not True:
        value.update({"authored_replay_gate": False,
                      "first_failed_gate": build.get("first_failed_gate") or "build_trace"})
        atomic_json_dump(value, summaryp)
        return value
    preflight = read_json(root / "preflight/screening_worker_compile.json")
    if preflight.get("compile_ok") is not True:
        raise ValueError("screening worker preflight did not pass")
    framep = root / "screening/frames" / f"{safe_slug(slug)}.jsonl"
    frame = read_jsonl(framep)
    replay_rows = []
    failure_counts: Counter[str] = Counter()
    for index, target in enumerate(frame, 1):
        outp = root / "screening/authored_rows" / safe_slug(slug) / f"{target['rid']}.json"
        inp = worker_input(root, target, cfg_sha, [], "screening_authored_only")
        inputp = root / "screening/authored_inputs" / safe_slug(slug) / f"{target['rid']}.json"
        if not outp.exists():
            atomic_json_dump(inp, inputp)
            proc = run_cmd([sys.executable, str(WORKER), "--input", str(inputp),
                            "--output", str(outp), "--generated-dir", str(root / "generated"),
                            "--timeout", str(args.replay_timeout)], PACKAGE_ROOT,
                           args.replay_timeout + 120)
            if not outp.exists():
                raise RuntimeError(f"authored worker failed without row: {proc.stderr[-8000:]}")
        row = read_json(outp)
        ok = row.get("worker_ok") is True and len(row.get("candidates", [])) == 0
        if not ok:
            failure_counts[row.get("error_type", "authored_gate")] += 1
        replay_rows.append({**target, "screening_worker_row": str(outp),
                            "screening_worker_row_sha256": file_sha256(outp),
                            "authored_replay_ok": ok,
                            "pre_goal_count": row.get("pre_goal_count")})
        print(f"EXP51-SCREEN {slug} {index}/{len(frame)} authored_ok={int(ok)}", flush=True)
    eligible = [x for x in replay_rows if x["authored_replay_ok"]]
    eligiblep = root / "screening/eligible_frames" / f"{safe_slug(slug)}.jsonl"
    atomic_jsonl_dump(eligible, eligiblep)
    value.update({
        "roots_replayed": len(replay_rows), "eligible_roots": len(eligible),
        "failure_counts": dict(sorted(failure_counts.items())),
        "eligible_frame": str(eligiblep), "eligible_frame_sha256": file_sha256(eligiblep),
        "authored_replay_gate": len(eligible) >= ROOTS_PER_REPOSITORY,
        "first_failed_gate": None if len(eligible) >= ROOTS_PER_REPOSITORY else "minimum_replay_valid_roots",
    })
    atomic_json_dump(value, summaryp)
    return value


def overlap(a: set[str], b: set[str]) -> float:
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def finalize_screening(candidates: list[dict[str, Any]], root: Path, cfg_sha: str) -> dict[str, Any]:
    summaries = []
    hash_sets: dict[str, set[str]] = {}
    for candidate in candidates:
        slug = candidate["slug"]
        replay = read_json(root / "screening/replay" / f"{safe_slug(slug)}.json")
        build = read_json(root / "screening/build_trace" / f"{safe_slug(slug)}.json")
        summaries.append({"slug": slug, "commit": build.get("commit"),
                          "build_trace_gate": build.get("build_trace_gate") is True,
                          "authored_replay_gate": replay.get("authored_replay_gate") is True,
                          "eligible_roots": replay.get("eligible_roots", 0),
                          "first_failed_gate": replay.get("first_failed_gate") or build.get("first_failed_gate")})
        invp = root / "screening/source_inventories" / f"{safe_slug(slug)}.jsonl"
        hash_sets[slug] = {x["normalized_whitespace_free_sha256"] for x in read_jsonl(invp)} if invp.is_file() else set()
    threshold = float(read_json(PACKAGE_ROOT / "repository_candidates.json")["source_overlap_threshold"])
    lineage_rows = []
    blocked: set[str] = set()
    eligible_order = [x["slug"] for x in summaries if x["authored_replay_gate"]]
    for i, left in enumerate(eligible_order):
        for right in eligible_order[i + 1:]:
            score = overlap(hash_sets[left], hash_sets[right])
            same = score >= threshold
            lineage_rows.append({"left": left, "right": right, "overlap": score,
                                 "threshold": threshold, "same_lineage": same})
            if same:
                blocked.add(right)
    representatives = [x for x in eligible_order if x not in blocked]
    selected = representatives[:TARGET_REPOSITORIES]
    backups = representatives[TARGET_REPOSITORIES:]
    value = {
        "version": 1, "recruitment_version": RECRUITMENT_VERSION,
        "protocol_version": PROTOCOL_VERSION, "recruitment_config_sha256": cfg_sha,
        "scientific_candidate_tactics_executed": 0,
        "candidates_screened": len(candidates), "repository_ledger": summaries,
        "lineage_pairs": lineage_rows, "lineage_representatives": representatives,
        "selected_repositories": selected,
        "ordered_backups": backups,
        "selected_count": len(selected), "minimum_required": MIN_REPOSITORIES,
        "screening_gate": len(selected) >= MIN_REPOSITORIES,
        "next_step": ("Freeze Exp51 and Exp52 before scientific execution."
                      if len(selected) >= MIN_REPOSITORIES else
                      "STOP: insufficient_repository_frame; recruit and preregister a new frame extension."),
    }
    atomic_json_dump(value, root / "screening/summary.json")
    atomic_jsonl_dump(lineage_rows, root / "screening/lineage_table.jsonl")
    return value


def main(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    cfgp = root / "recruitment_frozen/recruitment_config.json"
    cfg = read_json(cfgp)
    validate_code_lock(cfg["code_lock"])
    cfg_sha = file_sha256(cfgp)
    frame = read_json(cfg["candidate_frame"])
    if file_sha256(cfg["candidate_frame"]) != cfg["candidate_frame_sha256"]:
        raise ValueError("candidate frame changed")
    candidates = list(frame["candidates"])
    if args.phase == "recover-enumeration":
        recovery = cfg.get("qualification_recovery", {})
        expected_recovery = {
            "source": "preserved-exp51-fix4",
            "trace_reuse_schema": TRACE_REUSE_SCHEMA,
            "position_adapter_schema": V427_POSITION_ADAPTER_SCHEMA,
            "parser_compatibility_schema": V427_PARSER_COMPATIBILITY_SCHEMA,
            "parser_compatibility_expected": PARSER_COMPATIBILITY_EXPECTED,
            "checkout_line_endings_expected": CHECKOUT_LINE_ENDING_EXPECTED,
            "parser_execution_profile": PARSER_EXECUTION_PROFILE,
            "enumeration_workers": RECOVERY_ENUMERATION_WORKERS,
            "enumeration_timeout_seconds": RECOVERY_ENUMERATION_TIMEOUT,
            "capacity_profile": RECOVERY_CAPACITY_PROFILE,
            "trace_execution_permitted": False,
            "scientific_candidate_tactics_permitted": 0,
        }
        if recovery != expected_recovery:
            raise ValueError("frozen fix9 recovery contract changed")
        if not (
            args.enumeration_workers == RECOVERY_ENUMERATION_WORKERS
            and args.enumeration_timeout == RECOVERY_ENUMERATION_TIMEOUT
        ):
            raise ValueError("CLI differs from frozen Exp51 fix9 recovery schedule")
        runtimep = root / "preflight/trace_runtime.json"
        adapterp = root / "preflight/parser_adapter.json"
        if not runtimep.is_file():
            raise ValueError("STOP: pinned trace-runtime preflight receipt is absent")
        if not adapterp.is_file():
            raise ValueError("STOP: parser-adapter preflight receipt is absent")
        runtime = read_json(runtimep)
        adapter = read_json(adapterp)
        if (runtime.get("runtime_ok") is not True
                or runtime.get("qualification_resources", {}).get("parallel_capacity_ok") is not True
                or runtime.get("qualification_resources", {}).get("capacity_profile")
                != RECOVERY_CAPACITY_PROFILE
                or runtime.get("config_sha256") != cfg_sha
                or runtime.get("candidate_tactics_executed") != 0):
            raise ValueError("STOP: pinned trace-runtime preflight has not passed")
        if not (
            adapter.get("adapter_ok") is True
            and adapter.get("config_sha256") == cfg_sha
            and adapter.get("parser_compatibility_schema") == V427_PARSER_COMPATIBILITY_SCHEMA
            and adapter.get("repositories") == list(PARSER_ADAPTER_PREFLIGHT_REPOSITORIES)
            and adapter.get("fix8_success_frames_exact") is True
            and len(adapter.get("compatibility_smokes", []))
            == len(PARSER_ADAPTER_PREFLIGHT_REPOSITORIES)
            and all(row.get("smoke_gate") is True
                    for row in adapter.get("compatibility_smokes", []))
            and adapter.get("candidate_tactics_executed") == 0
            and adapter.get("trace_executed") is False
        ):
            raise ValueError("STOP: parser-adapter preflight has not passed")
        rows: list[dict[str, Any] | None] = [None] * len(candidates)
        for i, candidate in enumerate(candidates, 1):
            print(f"EXP51-RECOVERY-QUEUED {i}/{len(candidates)} {candidate['slug']}", flush=True)
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.enumeration_workers,
            thread_name_prefix="exp51-recovery",
        ) as executor:
            futures = {
                executor.submit(recover_fix4_one, candidate, args, root):
                (index, candidate["slug"])
                for index, candidate in enumerate(candidates)
            }
            for future in concurrent.futures.as_completed(futures):
                index, slug = futures[future]
                row = future.result()
                rows[index] = row
                print(
                    f"EXP51-RECOVERY-DONE {index + 1}/{len(candidates)} {slug} "
                    f"gate={int(row.get('build_trace_gate') is True)} "
                    f"failed={row.get('first_failed_gate')}", flush=True,
                )
        if any(row is None for row in rows):
            raise RuntimeError("parallel recovery returned an incomplete result vector")
        completed_rows = [row for row in rows if row is not None]
        passed = sum(x.get("build_trace_gate") is True for x in completed_rows)
        fix8_controls_exact = bool(all(
            next(
                row for row in completed_rows
                if row.get("candidate", {}).get("slug") == slug
            ).get("fix8_frame_control", {}).get("exact") is True
            for slug in FIX8_FRAME_CONTROLS
        ))
        reusable_rows = [
            row for row in completed_rows
            if row.get("trace_reuse", {}).get("trace_execution_repeated") is False
        ]
        compatibility_receipts = []
        for row in reusable_rows:
            slug = row["candidate"]["slug"]
            receiptp = root / "screening/enumeration_receipts" / f"{safe_slug(slug)}.json"
            if receiptp.is_file():
                compatibility_receipts.append(read_json(receiptp))
        adapters = [row.get("position_adapter", {}) for row in compatibility_receipts]
        observed_compatibility = {
            "repositories": len(compatibility_receipts),
            "section_nodes": sum(
                adapter.get("section_adapter", {}).get("counters", {}).get(
                    "v427_named_three_child", 0
                )
                + adapter.get("section_adapter", {}).get("counters", {}).get(
                    "v427_unnamed_three_child", 0
                )
                for adapter in adapters
            ),
            "named_sections": sum(
                adapter.get("section_adapter", {}).get("counters", {}).get(
                    "v427_named_three_child", 0
                )
                for adapter in adapters
            ),
            "unnamed_sections": sum(
                adapter.get("section_adapter", {}).get("counters", {}).get(
                    "v427_unnamed_three_child", 0
                )
                for adapter in adapters
            ),
            "legacy_sections": sum(
                adapter.get("section_adapter", {}).get("counters", {}).get(
                    "legacy_two_child", 0
                )
                for adapter in adapters
            ),
            "plain_header_sections": sum(
                adapter.get("section_adapter", {}).get("header_counters", {}).get(
                    "plain", 0
                )
                for adapter in adapters
            ),
            "noncomputable_header_sections": sum(
                adapter.get("section_adapter", {}).get("header_counters", {}).get(
                    "noncomputable", 0
                )
                for adapter in adapters
            ),
            "public_header_sections": sum(
                adapter.get("section_adapter", {}).get("header_counters", {}).get(
                    "public", 0
                )
                for adapter in adapters
            ),
            "public_meta_header_sections": sum(
                adapter.get("section_adapter", {}).get("header_counters", {}).get(
                    "public_meta", 0
                )
                for adapter in adapters
            ),
            "expose_public_header_sections": sum(
                adapter.get("section_adapter", {}).get("header_counters", {}).get(
                    "expose_public", 0
                )
                for adapter in adapters
            ),
            "expose_public_meta_header_sections": sum(
                adapter.get("section_adapter", {}).get("header_counters", {}).get(
                    "expose_public_meta", 0
                )
                for adapter in adapters
            ),
            "traced_standard_crlf_files": sum(
                adapter.get("crlf_adapter", {}).get("counters", {}).get(
                    "standard_crlf_files", 0
                )
                for adapter in adapters
            ),
            "traced_standard_crlf_lines": sum(
                adapter.get("crlf_adapter", {}).get("counters", {}).get(
                    "standard_crlf_lines", 0
                )
                for adapter in adapters
            ),
            "position_rejections": sum(
                adapter.get("counters", {}).get("rejected", 0) for adapter in adapters
            ),
            "section_rejections": sum(
                adapter.get("section_adapter", {}).get("counters", {}).get("rejected", 0)
                for adapter in adapters
            ),
            "header_rejections": sum(
                adapter.get("section_adapter", {}).get("header_counters", {}).get(
                    "rejected", 0
                )
                for adapter in adapters
            ),
            "crlf_rejections": sum(
                adapter.get("crlf_adapter", {}).get("counters", {}).get("rejected", 0)
                for adapter in adapters
            ),
        }
        expected_compatibility = expected_recovery["parser_compatibility_expected"]
        observed_checkout_line_endings = {
            "repositories": len(reusable_rows),
            "standard_crlf_files": sum(
                row.get("trace_reuse", {}).get("source_line_endings", {}).get(
                    "standard_crlf_files", 0
                )
                for row in reusable_rows
            ),
            "standard_crlf_lines": sum(
                row.get("trace_reuse", {}).get("source_line_endings", {}).get(
                    "standard_crlf_lines", 0
                )
                for row in reusable_rows
            ),
            "line_ending_rejections": sum(
                row.get("trace_reuse", {}).get("source_line_endings", {}).get(
                    "line_ending_rejections", 0
                )
                for row in reusable_rows
            ),
        }
        expected_checkout_line_endings = expected_recovery[
            "checkout_line_endings_expected"
        ]
        checkout_line_endings_exact = bool(
            len(reusable_rows) == 15
            and observed_checkout_line_endings == expected_checkout_line_endings
        )
        parser_compatibility_exact = bool(
            len(reusable_rows) == 15
            and observed_compatibility == expected_compatibility
            and all(
                adapter.get("parser_compatibility_schema")
                == V427_PARSER_COMPATIBILITY_SCHEMA
                and adapter.get("installed_parser_files_unchanged") is True
                and adapter.get("crlf_adapter", {}).get("accepted")
                == "standard-CRLF-normalized-to-LF-byte-width"
                and adapter.get("crlf_adapter", {}).get("byte_index_semantics")
                == "Lean-v4.27-LF-normalized-source-buffer"
                and adapter.get("crlf_adapter", {}).get("checkout_modified") is False
                for adapter in adapters
            )
        )
        value = {"version": 1, "phase": "recover-enumeration", "candidates": len(completed_rows),
                 "passed": passed,
                 "minimum_required": MIN_REPOSITORIES,
                 "fix8_success_frames_exact": fix8_controls_exact,
                 "reused_trace_repositories": sum(
                     x.get("trace_reuse", {}).get("trace_execution_repeated") is False
                     for x in completed_rows
                 ),
                 "trace_executed": False,
                 "scientific_candidate_tactics_executed": 0,
                 "mechanical_fix_id": MECHANICAL_FIX_ID,
                 "qualification_recovery": expected_recovery,
                 "parser_compatibility_measurement": {
                     "descriptive_only": True,
                     "expected_from_frozen_parser_qualification": expected_compatibility,
                     "observed": observed_compatibility,
                     "exact": parser_compatibility_exact,
                 },
                 "checkout_line_ending_measurement": {
                     "descriptive_only": True,
                     "expected_from_complete_fix4_source_inventories":
                     expected_checkout_line_endings,
                     "observed": observed_checkout_line_endings,
                     "exact": checkout_line_endings_exact,
                 },
                 "recovery_gate": (
                     passed >= MIN_REPOSITORIES
                     and fix8_controls_exact
                     and parser_compatibility_exact
                     and checkout_line_endings_exact
                 )}
        value["next_step"] = (
            "Run screening worker compile-only preflight."
            if value["recovery_gate"] else
            "STOP: minimum repository, parser-compatibility, or fix8 exact-frame gate failed."
        )
        atomic_json_dump(value, root / "screening/build_trace_summary.json")
    else:
        preflightp = root / "preflight/screening_worker_compile.json"
        if not preflightp.is_file():
            raise ValueError("STOP: screening compile-only preflight receipt is absent")
        if read_json(preflightp).get("compile_ok") is not True:
            raise ValueError("screening compile-only preflight has not passed")
        for i, candidate in enumerate(candidates, 1):
            print(f"EXP51-AUTHORED-REPLAY {i}/{len(candidates)} {candidate['slug']}", flush=True)
            replay_one(candidate, args, root, cfg_sha)
        value = finalize_screening(candidates, root, cfg_sha)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    p.add_argument("--phase", choices=("recover-enumeration", "authored-replay"), required=True)
    p.add_argument("--enumeration-workers", type=int, default=RECOVERY_ENUMERATION_WORKERS)
    p.add_argument("--enumeration-timeout", type=int, default=RECOVERY_ENUMERATION_TIMEOUT)
    p.add_argument("--replay-timeout", type=int, default=900)
    return p.parse_args()


if __name__ == "__main__":
    parsed = parse_args()
    result = main(parsed)
    if parsed.phase == "recover-enumeration" and result.get("recovery_gate") is not True:
        raise SystemExit(2)
    if parsed.phase == "authored-replay" and result.get("screening_gate") is not True:
        raise SystemExit(2)
