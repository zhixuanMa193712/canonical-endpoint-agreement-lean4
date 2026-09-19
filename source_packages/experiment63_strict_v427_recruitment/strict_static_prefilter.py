"""Clone exact current commits and apply a conservative source-only v4.27 prefilter."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import signal
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

from experiment63_protocol import *


DECL_RE = re.compile(r"(?m)^\s*(?:private\s+|protected\s+|noncomputable\s+)*(?:theorem|lemma)\s+([A-Za-z0-9_'.]+)")
INCOMPLETE_RE = re.compile(r"(^|\W)(?:sorry|admit)(\W|$)")


def strip_comments(source: str) -> str:
    output: list[str] = []
    i, depth, string = 0, 0, False
    while i < len(source):
        if depth:
            if source.startswith("/-", i):
                depth += 1; output.extend("  "); i += 2
            elif source.startswith("-/", i):
                depth -= 1; output.extend("  "); i += 2
            else:
                output.append("\n" if source[i] == "\n" else " "); i += 1
        elif string:
            output.append(source[i])
            if source[i] == '"' and (i == 0 or source[i - 1] != "\\"):
                string = False
            i += 1
        elif source.startswith("/-", i):
            depth = 1; output.extend("  "); i += 2
        elif source.startswith("--", i):
            end = source.find("\n", i)
            if end < 0:
                output.extend(" " * (len(source) - i)); break
            output.extend(" " * (end - i)); i = end
        else:
            output.append(source[i])
            if source[i] == '"':
                string = True
            i += 1
    return "".join(output)


def eligible_path(relative: Path) -> bool:
    return not {part.lower() for part in relative.parts}.intersection(EXCLUDED_SOURCE_PARTS)


def static_roots(source: str) -> list[dict[str, Any]]:
    clean = strip_comments(source)
    matches = list(DECL_RE.finditer(clean))
    roots = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(clean)
        segment = clean[match.start():end]
        if re.search(r":=\s*by(?:\s|$)", segment) and not INCOMPLETE_RE.search(segment):
            roots.append({"name": match.group(1), "offset": match.start()})
    return roots


def monitored(cmd: list[str], cwd: Path, checkout: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    proc = subprocess.Popen(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True)
    started = time.monotonic()
    reason = None
    while proc.poll() is None:
        if time.monotonic() - started > timeout:
            reason = "static_timeout"
        elif allocated_bytes(checkout) > STATIC_CHECKOUT_LIMIT_BYTES:
            reason = "static_disk_budget"
        elif shutil.disk_usage(MZX_ROOT).free < GLOBAL_FREE_DISK_FLOOR_BYTES:
            reason = "global_disk_floor"
        if reason:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(20)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
            break
        time.sleep(1)
    stdout, stderr = proc.communicate()
    if reason:
        raise RuntimeError(reason)
    if allocated_bytes(checkout) > STATIC_CHECKOUT_LIMIT_BYTES:
        raise RuntimeError("static_disk_budget")
    if shutil.disk_usage(MZX_ROOT).free < GLOBAL_FREE_DISK_FLOOR_BYTES:
        raise RuntimeError("global_disk_floor")
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)


def safe_cleanup(path: Path) -> dict[str, Any]:
    resolved = ensure_scoped_path(path, STATIC_CHECKOUT_ROOT)
    before = allocated_bytes(resolved)
    if resolved.is_symlink():
        raise ValueError(f"refusing symlink cleanup: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    return {"path": str(resolved), "allocated_bytes_before": before, "removed": not resolved.exists()}


def clone(candidate: dict[str, Any], checkout: Path, timeout: int) -> None:
    checkout.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for attempt in range(3):
        safe_cleanup(checkout)
        commands = [
            ["git", "clone", "--filter=blob:none", "--no-checkout", candidate["url"], str(checkout)],
            ["git", "-C", str(checkout), "fetch", "--depth=1", "origin", candidate["commit"]],
            ["git", "-C", str(checkout), "checkout", "--detach", candidate["commit"]],
        ]
        try:
            for command in commands:
                result = monitored(command, MZX_ROOT, checkout, timeout)
                if result.returncode:
                    raise RuntimeError(result.stderr[-4000:])
            return
        except Exception as exc:
            last = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"clone failed after three attempts: {last}")


def inspect_one(candidate: dict[str, Any], root: Path, timeout: int) -> dict[str, Any]:
    safe = safe_slug(candidate["slug"])
    outp = root / "static/receipts" / f"{safe}.json"
    if outp.is_file():
        return read_json(outp)
    checkout = STATIC_CHECKOUT_ROOT / safe
    value: dict[str, Any] = {
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "candidate": candidate, "strict_static_gate": False,
        "first_failed_gate": "static_checkout", "scientific_candidate_tactics_executed": 0,
    }
    try:
        clone(candidate, checkout, timeout)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=checkout, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=True).stdout.strip()
        if head != candidate["commit"]:
            raise ValueError("exact commit mismatch")
        toolchainp = checkout / "lean-toolchain"
        toolchain = toolchainp.read_text(encoding="utf-8").strip() if toolchainp.is_file() else None
        value["toolchain"] = toolchain
        if toolchain != TARGET_TOOLCHAIN:
            value["first_failed_gate"] = "exact_root_toolchain"
            raise ValueError(f"found {toolchain!r}")
        licenses = [name for name in ROOT_LICENSE_NAMES if (checkout / name).is_file()]
        lakefiles = [name for name in ROOT_LAKEFILE_NAMES if (checkout / name).is_file()]
        if not licenses:
            value["first_failed_gate"] = "root_license"; raise ValueError("no root license")
        if not lakefiles:
            value["first_failed_gate"] = "root_lakefile"; raise ValueError("no root lakefile")
        inventory, roots = [], []
        for path in sorted(checkout.rglob("*.lean")):
            relative = path.relative_to(checkout)
            if not eligible_path(relative):
                continue
            source = path.read_text(encoding="utf-8", errors="replace")
            header = source[:4096].lower()
            if any(mark in header for mark in ("automatically generated", "generated by", "do not edit")):
                continue
            digest = file_sha256(path)
            found = static_roots(source)
            inventory.append({
                "path": relative.as_posix(), "bytes": path.stat().st_size,
                "sha256": digest, "normalized_whitespace_free_sha256": text_sha256(re.sub(r"\s+", "", source)),
                "static_tactic_roots": len(found),
            })
            roots.extend({"path": relative.as_posix(), **row} for row in found)
        atomic_jsonl_dump(inventory, root / "static/source_inventories" / f"{safe}.jsonl")
        atomic_jsonl_dump(roots, root / "static/root_estimates" / f"{safe}.jsonl")
        value.update({
            "licenses": licenses, "lakefiles": lakefiles,
            "source_files": len(inventory), "static_tactic_roots": len(roots),
            "source_inventory_sha256": file_sha256(root / "static/source_inventories" / f"{safe}.jsonl"),
            "static_root_estimate_sha256": file_sha256(root / "static/root_estimates" / f"{safe}.jsonl"),
            "checkout_allocated_bytes": allocated_bytes(checkout),
        })
        if len(roots) < MIN_STATIC_TACTIC_ROOTS:
            value["first_failed_gate"] = "minimum_static_tactic_roots"
            raise ValueError(f"only {len(roots)} conservative source roots")
        value["strict_static_gate"] = True
        value["first_failed_gate"] = None
    except Exception as exc:
        value["error"] = {"type": type(exc).__name__, "message": str(exc)[-8000:]}
        if value["first_failed_gate"] == "static_checkout" and OPERATIONAL_ERROR_RE.search(str(exc)):
            value["classification"] = "operationally_unresolved"
        else:
            value["classification"] = "strict_static_ineligible"
    finally:
        value["checkout_cleanup"] = safe_cleanup(checkout)
    value = seal(value)
    atomic_json_dump(value, outp)
    print(f"EXP63-STATIC {candidate['slug']} gate={int(value['strict_static_gate'])} roots={value.get('static_tactic_roots', 0)} failed={value['first_failed_gate']}", flush=True)
    return value


def run(root: Path, workers: int, timeout: int) -> dict[str, Any]:
    protocol = read_json(root / "frozen/protocol.json")
    assert_sealed(protocol, "Exp63 protocol"); validate_locks(protocol)
    discovery = read_json(root / "discovery/summary.json")
    assert_sealed(discovery, "Exp63 discovery")
    candidates = read_jsonl(root / "discovery/v427_surface.jsonl")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(inspect_one, row, root, timeout) for row in candidates]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    eligible, failures = [], Counter()
    for receipt in results:
        failures[str(receipt.get("first_failed_gate"))] += 1
        if receipt["strict_static_gate"]:
            candidate = dict(receipt["candidate"])
            candidate.update({
                "static_tactic_roots": receipt["static_tactic_roots"],
                "static_receipt_sha256": receipt["record_sha256"],
                "source_inventory_sha256": receipt["source_inventory_sha256"],
            })
            eligible.append(candidate)
    eligible.sort(key=lambda row: selection_key(FRAME_ORDER_SEED, row["slug"], row["commit"]))
    atomic_jsonl_dump(eligible, root / "static/strict_candidates_unfrozen.jsonl")
    summary = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "surface_candidates": len(candidates), "completed_receipts": len(results),
        "strict_static_passes": len(eligible), "gate_counts": dict(sorted(failures.items())),
        "strict_candidate_frame_sha256": file_sha256(root / "static/strict_candidates_unfrozen.jsonl"),
        "static_checkouts_retained": 0, "scientific_candidate_tactics_executed": 0,
    })
    atomic_json_dump(summary, root / "static/summary.json")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--workers", type=int, default=STATIC_WORKERS)
    parser.add_argument("--git-timeout", type=int, default=1800)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run(Path(args.artifact_root).resolve(), args.workers, args.git_timeout), indent=2))
