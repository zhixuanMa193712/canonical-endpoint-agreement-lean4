"""Resolve one exact archival Lean-v4.27 commit for every frozen repository."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from experiment60_protocol import *


RAW = "https://raw.githubusercontent.com"
GITHUB = "https://github.com"
ATOM = {"atom": "http://www.w3.org/2005/Atom"}


def http_get(url: str, attempts: int = 5) -> tuple[bytes, int, dict[str, str]]:
    last: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(url, headers={
            "Accept": "application/atom+xml,text/plain,*/*",
            "User-Agent": "MZX-Exp60-archival-v427-snapshot",
        })
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read(), int(response.status), dict(response.headers)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return exc.read(), 404, dict(exc.headers)
            last = exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
        if attempt + 1 < attempts:
            time.sleep(min(30.0, 2.0 ** attempt))
    raise RuntimeError(f"archival HTTP retrieval failed: {url}: {last}")


def toolchain_at(slug: str, commit: str, raw_root: Path, label: str) -> tuple[str | None, dict[str, Any]]:
    url = f"{RAW}/{slug}/{commit}/lean-toolchain"
    raw, status, headers = http_get(url)
    path = raw_root / "toolchain_probes" / slug.replace("/", "__") / f"{label}-{commit}.txt"
    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    value = raw.decode("utf-8", errors="replace").strip() if status == 200 else None
    return value, {"kind": "toolchain_probe", "slug": slug, "commit": commit,
                   "label": label, "url": url, "status": status, "path": str(path),
                   "bytes": len(raw), "sha256": file_sha256(path), "etag": headers.get("ETag")}


def feed_commits(slug: str, branch: str, raw_root: Path) -> tuple[list[str], dict[str, Any]]:
    encoded_branch = urllib.parse.quote(branch, safe="")
    url = f"{GITHUB}/{slug}/commits/{encoded_branch}/lean-toolchain.atom"
    raw, status, headers = http_get(url)
    path = raw_root / "feeds" / f"{slug.replace('/', '__')}.atom"
    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    commits: list[str] = []
    if status == 200:
        root = ET.fromstring(raw)
        for entry in root.findall("atom:entry", ATOM)[:ARCHIVAL_FEED_MAX_ENTRIES]:
            identity = (entry.findtext("atom:id", default="", namespaces=ATOM) or "").strip()
            match = re.search(r"Commit/([0-9a-f]{40})$", identity)
            if not match:
                raise ValueError(f"unrecognized Atom commit identity for {slug}: {identity}")
            commits.append(match.group(1))
    return commits, {"kind": "lean_toolchain_atom_feed", "slug": slug, "branch": branch,
                     "url": url, "status": status, "path": str(path), "bytes": len(raw),
                     "sha256": file_sha256(path), "entries": len(commits),
                     "etag": headers.get("ETag")}


def tag_commits(row: dict[str, Any], raw_root: Path) -> tuple[list[tuple[str, str]], dict[str, Any]]:
    proc = subprocess.run(["git", "ls-remote", "--tags", row["url"]], text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=240)
    if proc.returncode != 0:
        raise RuntimeError(f"tag resolution failed for {row['slug']}: {proc.stderr[-2000:]}")
    direct: dict[str, str] = {}
    peeled: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        fields = line.split()
        if len(fields) != 2 or not re.fullmatch(r"[0-9a-f]{40}", fields[0]):
            continue
        ref = fields[1]
        if not ref.startswith("refs/tags/"):
            continue
        name = ref[len("refs/tags/"):]
        if name.endswith("^{}"):
            peeled[name[:-3]] = fields[0]
        else:
            direct[name] = fields[0]
    pattern = re.compile(ARCHIVAL_TAG_PATTERN, re.IGNORECASE)
    selected = sorted(((name, peeled.get(name, commit)) for name, commit in direct.items()
                       if pattern.fullmatch(name)), key=lambda item: item[0].lower())
    receipt_path = raw_root / "tags" / f"{row['slug'].replace('/', '__')}.json"
    receipt = {"slug": row["slug"], "command": ["git", "ls-remote", "--tags", row["url"]],
               "returncode": proc.returncode, "stdout_sha256": hashlib.sha256(proc.stdout.encode()).hexdigest(),
               "stderr_sha256": hashlib.sha256(proc.stderr.encode()).hexdigest(),
               "matching_tags": [{"tag": name, "commit": commit} for name, commit in selected]}
    atomic_json_dump(receipt, receipt_path)
    return selected, {"kind": "git_tag_receipt", "slug": row["slug"],
                      "path": str(receipt_path), "bytes": receipt_path.stat().st_size,
                      "sha256": file_sha256(receipt_path), "matching_tags": len(selected)}


def resolve_one(row: dict[str, Any], raw_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    slug = row["slug"]
    ledger: list[dict[str, Any]] = []
    historical = slug.lower() in {value.lower() for value in HISTORICAL_SCIENTIFIC_REPOSITORIES}
    selected_commit: str | None = None
    method: str | None = None
    method_detail: str | None = None
    observed: str | None = None
    observed_sha256: str | None = None
    if not historical and row.get("lean_toolchain_observed") == TARGET_TOOLCHAIN:
        selected_commit, method, method_detail = row["commit"], "frozen_head", row["default_branch"]
        observed = TARGET_TOOLCHAIN
        observed_sha256 = row.get("lean_toolchain_content_sha256")
    elif not historical:
        commits, feed_receipt = feed_commits(slug, row["default_branch"], raw_root)
        ledger.append(feed_receipt)
        for index, commit in enumerate(commits, 1):
            value, receipt = toolchain_at(slug, commit, raw_root, f"feed-{index:02d}")
            ledger.append(receipt)
            if value == TARGET_TOOLCHAIN:
                selected_commit, method, method_detail, observed = commit, "atom_feed", str(index), value
                observed_sha256 = receipt["sha256"]
                break
        if selected_commit is None:
            tags, tag_receipt = tag_commits(row, raw_root)
            ledger.append(tag_receipt)
            for index, (tag, commit) in enumerate(tags, 1):
                value, receipt = toolchain_at(slug, commit, raw_root, f"tag-{index:02d}")
                receipt["tag"] = tag; ledger.append(receipt)
                if value == TARGET_TOOLCHAIN:
                    selected_commit, method, method_detail, observed = commit, "exact_version_tag", tag, value
                    observed_sha256 = receipt["sha256"]
                    break
    if historical:
        exclusion = "historical_scientific_repository"
        output_commit = row["commit"]
    elif selected_commit is None:
        exclusion = "no_exact_v427_commit_in_frozen_archival_surface"
        output_commit = row["commit"]
    else:
        exclusion = None
        output_commit = selected_commit
    record = {
        "slug": slug, "url": row["url"], "commit": output_commit,
        "default_branch": row["default_branch"], "domain": row.get("domain", "unclassified"),
        "snapshot_source": "Exp60 frozen HEAD-plus-Atom-feed-plus-exact-tag archival discovery",
        "source_exp56_snapshot_record_sha256": row["snapshot_record_sha256"],
        "source_exp56_head_commit": row["commit"],
        "archival_selection_method": method,
        "archival_selection_detail": method_detail,
        "lean_toolchain_observed": observed,
        "lean_toolchain_content_sha256": observed_sha256,
        "prequalification_exclusion": exclusion,
        "commit_response_sha256": json_sha256(ledger),
    }
    record["snapshot_record_sha256"] = json_sha256(record)
    return record, ledger


def snapshot(root: Path, workers: int) -> dict[str, Any]:
    protocol_path = root / "frozen/protocol.json"
    protocol = read_json(protocol_path); assert_sealed(protocol, "Exp60 protocol")
    collector = protocol["archival_collector"]
    if collector["sha256"] != file_sha256(Path(__file__)):
        raise ValueError("archival collector changed after protocol freeze")
    source = protocol["source_universe"]
    source_path = Path(source["path"])
    if file_sha256(source_path) != source["sha256"]:
        raise ValueError("Exp56 source universe changed")
    output = root / "recruitment_snapshot/candidate_frame_input.jsonl"
    if output.exists():
        raise FileExistsError("Exp60 archival snapshot retry prohibited")
    source_rows = read_jsonl(source_path)
    if len(source_rows) != source["records"]:
        raise ValueError("Exp56 source-universe count changed")
    raw_root = root / "recruitment_snapshot/raw"
    resolved: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(resolve_one, row, raw_root): row for row in source_rows}
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            record, ledger = future.result()
            resolved.append((record, ledger))
            print(f"EXP60-ARCHIVAL {index}/{len(source_rows)} {record['slug']} "
                  f"eligible={int(record['prequalification_exclusion'] is None)}", flush=True)
    rows = sorted((row for row, _ in resolved), key=lambda row: row["slug"].lower())
    ledgers = sorted(({"slug": row["slug"], "records": ledger} for row, ledger in resolved),
                     key=lambda value: value["slug"].lower())
    ledger_path = root / "recruitment_snapshot/response_ledger.jsonl"
    atomic_jsonl_dump(rows, output); atomic_jsonl_dump(ledgers, ledger_path)
    eligible = sum(row["prequalification_exclusion"] is None for row in rows)
    value = seal({
        "version": 1, "protocol_version": PROTOCOL_VERSION_60,
        "source_repositories": len(rows), "exact_v427_nonhistorical_candidates": eligible,
        "prequalification_upper_bound_reaches_38": eligible >= REPOSITORIES_REQUIRED,
        "candidate_frame_input": str(output), "candidate_frame_input_sha256": file_sha256(output),
        "response_ledger": str(ledger_path), "response_ledger_sha256": file_sha256(ledger_path),
        "selection_method_counts": dict(sorted(__import__("collections").Counter(
            row.get("archival_selection_method") or "excluded" for row in rows).items())),
        "scientific_candidate_tactics_executed": 0,
        "next_step": "Freeze and qualify the complete frame." if eligible >= REPOSITORIES_REQUIRED
                     else "STOP: archival prequalification upper bound is below 38.",
    })
    atomic_json_dump(value, root / "recruitment_snapshot/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT_60))
    parser.add_argument("--workers", type=int, default=ARCHIVAL_WORKERS)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(snapshot(Path(args.artifact_root).resolve(), args.workers), indent=2))
