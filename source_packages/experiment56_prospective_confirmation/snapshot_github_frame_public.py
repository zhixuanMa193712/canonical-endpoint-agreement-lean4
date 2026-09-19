"""Snapshot the frozen GitHub frame without an authentication token.

Search responses come from the public GitHub REST endpoint.  Exact default-
branch commits are resolved with public Git smart-HTTP, and root
``lean-toolchain`` bytes are fetched from content-addressed raw URLs.  Every
response or command receipt is retained.  No repository is built, traced, or
scientifically evaluated here.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from experiment56_protocol import *


API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
AMENDMENT_ID = "experiment56-public-collection-transport-v1"


def http_get(url: str, *, accept: str, attempts: int = 5) -> tuple[bytes, dict[str, str], int]:
    last: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(
            url,
            headers={"Accept": accept, "X-GitHub-Api-Version": "2022-11-28",
                     "User-Agent": "MZX-Exp56-public-frame-snapshot"},
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read(), dict(response.headers), int(response.status)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return exc.read(), dict(exc.headers), 404
            last = exc
            reset = exc.headers.get("X-RateLimit-Reset")
            if exc.code in (403, 429) and reset:
                delay = max(1.0, int(reset) - time.time() + 2.0)
            else:
                delay = min(30.0, 2.0 ** attempt)
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            delay = min(30.0, 2.0 ** attempt)
        if attempt + 1 < attempts:
            time.sleep(delay)
    raise RuntimeError(f"public HTTP retrieval failed: {url}: {last}")


def resolve_candidate(item: dict[str, Any], raw_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    slug = str(item["full_name"])
    branch = str(item["default_branch"])
    clone_url = str(item["clone_url"])
    proc = subprocess.run(
        ["git", "ls-remote", "--refs", clone_url, f"refs/heads/{branch}"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180,
    )
    lines = [line.split() for line in proc.stdout.splitlines() if line.strip()]
    if proc.returncode != 0 or len(lines) != 1 or len(lines[0]) != 2:
        raise RuntimeError(f"cannot resolve exact default-branch commit for {slug}: {proc.stderr[-2000:]}")
    commit, refname = lines[0]
    if len(commit) != 40 or refname != f"refs/heads/{branch}":
        raise ValueError(f"non-exact public Git resolution for {slug}")
    safe = slug.replace("/", "__")
    git_receipt_path = raw_root / "git_ls_remote" / f"{safe}.json"
    git_receipt = {
        "slug": slug, "clone_url": clone_url, "default_branch": branch,
        "command": ["git", "ls-remote", "--refs", clone_url, f"refs/heads/{branch}"],
        "returncode": proc.returncode, "stdout": proc.stdout,
        "stderr_sha256": hashlib.sha256(proc.stderr.encode()).hexdigest(),
        "resolved_commit": commit,
    }
    atomic_json_dump(git_receipt, git_receipt_path)
    toolchain_url = f"{RAW}/{slug}/{commit}/lean-toolchain"
    toolchain_raw, headers, status = http_get(toolchain_url, accept="text/plain")
    toolchain_dir = "toolchains" if status == 200 else "toolchains_missing"
    toolchain_path = raw_root / toolchain_dir / f"{safe}.txt"
    toolchain_path.parent.mkdir(parents=True, exist_ok=True)
    toolchain_path.write_bytes(toolchain_raw)
    toolchain = toolchain_raw.decode("utf-8", errors="replace").strip() if status == 200 else None
    historical = slug.lower() in {value.lower() for value in HISTORICAL_SCIENTIFIC_REPOSITORIES}
    if historical:
        exclusion = "historical_scientific_repository"
    elif toolchain != TARGET_TOOLCHAIN:
        exclusion = "missing_or_non_v427_root_toolchain"
    else:
        exclusion = None
    record = {
        "slug": slug, "url": clone_url, "commit": commit,
        "default_branch": branch, "domain": "unclassified",
        "snapshot_source": "GitHub REST frozen search plus public Git smart-HTTP commit resolution",
        "github_repository_id": item["id"], "github_node_id": item["node_id"],
        "stars_at_snapshot": item["stargazers_count"],
        "pushed_at": item["pushed_at"], "created_at": item["created_at"],
        "lean_toolchain_observed": toolchain,
        "lean_toolchain_content_sha256": hashlib.sha256(toolchain_raw).hexdigest() if status == 200 else None,
        "prequalification_exclusion": exclusion,
        "commit_response_sha256": file_sha256(git_receipt_path),
    }
    record["snapshot_record_sha256"] = json_sha256(record)
    ledger = [
        {"kind": "git_ls_remote", "slug": slug, "path": str(git_receipt_path),
         "bytes": git_receipt_path.stat().st_size, "sha256": file_sha256(git_receipt_path)},
        {"kind": "toolchain" if status == 200 else "toolchain_missing", "slug": slug,
         "url": toolchain_url, "status": status, "path": str(toolchain_path),
         "bytes": len(toolchain_raw), "sha256": file_sha256(toolchain_path),
         "etag": headers.get("ETag")},
    ]
    return record, ledger


def snapshot(root: Path, per_query: int, max_pages: int, workers: int) -> dict[str, Any]:
    protocol_path = root / "frozen/protocol.json"
    protocol = read_json(protocol_path); assert_sealed(protocol, "protocol")
    validate_implementation_locks(protocol)
    amendment_path = root / "frozen/public_collection_amendment.json"
    amendment = read_json(amendment_path); assert_sealed(amendment, "public collection amendment")
    if amendment.get("amendment_id") != AMENDMENT_ID:
        raise ValueError("wrong public collection amendment")
    if amendment.get("collector_sha256") != file_sha256(Path(__file__)):
        raise ValueError("public collector changed after amendment freeze")
    if amendment.get("base_protocol_sha256") != file_sha256(protocol_path):
        raise ValueError("base protocol changed after amendment freeze")
    if max_pages != amendment.get("search_pages_per_query"):
        raise ValueError("search page count differs from frozen amendment")
    if (root / "recruitment_snapshot/candidate_frame_input.jsonl").exists():
        raise FileExistsError("prospective candidate snapshot retry prohibited")
    raw_root = root / "recruitment_snapshot/raw_public"
    candidates: dict[str, dict[str, Any]] = {}
    response_ledger: list[dict[str, Any]] = []
    for query_index, query in enumerate(FROZEN_GITHUB_QUERIES):
        for page in range(1, max_pages + 1):
            encoded = urllib.parse.urlencode({"q": query, "sort": "stars", "order": "desc",
                                              "per_page": per_query, "page": page})
            url = f"{API}/search/repositories?{encoded}"
            raw, headers, status = http_get(url, accept="application/vnd.github+json")
            if status != 200:
                raise RuntimeError(f"GitHub search returned {status}: {query} page {page}")
            raw_path = raw_root / f"query-{query_index:02d}-page-{page:02d}.json"
            raw_path.parent.mkdir(parents=True, exist_ok=True); raw_path.write_bytes(raw)
            data = json.loads(raw)
            response_ledger.append({
                "kind": "search", "query": query, "page": page, "url": url,
                "status": status, "path": str(raw_path), "bytes": len(raw),
                "sha256": file_sha256(raw_path), "etag": headers.get("ETag"),
            })
            items = list(data.get("items", []))
            for item in items:
                candidates.setdefault(str(item["full_name"]).lower(), item)
            print(f"EXP56-PUBLIC-SEARCH query={query_index} page={page} items={len(items)}", flush=True)
            if len(items) < per_query:
                break
    ordered_items = sorted(candidates.values(), key=lambda row: str(row["full_name"]).lower())
    resolved: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(resolve_candidate, item, raw_root): item for item in ordered_items}
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            row = future.result()
            resolved.append(row)
            print(f"EXP56-PUBLIC-RESOLVE {index}/{len(ordered_items)} {row[0]['slug']}", flush=True)
    rows = sorted((row for row, _ in resolved), key=lambda row: row["slug"].lower())
    for _, ledger_rows in resolved:
        response_ledger.extend(ledger_rows)
    response_ledger.sort(key=lambda row: (row["kind"], row.get("slug", ""), row.get("query", ""), row.get("page", 0)))
    frame_path = root / "recruitment_snapshot/candidate_frame_input.jsonl"
    ledger_path = root / "recruitment_snapshot/response_ledger.jsonl"
    atomic_jsonl_dump(rows, frame_path); atomic_jsonl_dump(response_ledger, ledger_path)
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "collection_amendment_id": AMENDMENT_ID,
        "collection_amendment_sha256": file_sha256(amendment_path),
        "queries": list(FROZEN_GITHUB_QUERIES), "pages_per_query": max_pages,
        "repositories": len(rows),
        "prequalification_exclusions": sum(row["prequalification_exclusion"] is not None for row in rows),
        "exact_v427_nonhistorical_candidates": sum(row["prequalification_exclusion"] is None for row in rows),
        "candidate_frame_input": str(frame_path), "candidate_frame_input_sha256": file_sha256(frame_path),
        "response_ledger": str(ledger_path), "response_ledger_sha256": file_sha256(ledger_path),
        "raw_responses_retained": len(response_ledger),
        "scientific_candidate_tactics_executed": 0,
        "next_step": "Freeze candidate_frame_input.jsonl without editing it.",
    })
    atomic_json_dump(value, root / "recruitment_snapshot/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--per-query", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--workers", type=int, default=24)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(snapshot(Path(args.artifact_root).resolve(), args.per_query,
                              args.max_pages, args.workers), indent=2))
