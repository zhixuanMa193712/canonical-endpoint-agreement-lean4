"""Exhaustively snapshot public GitHub Lean repositories and exact current v4.27 HEADs."""
from __future__ import annotations

import argparse
import base64
import concurrent.futures
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from experiment63_protocol import *


class GitHub:
    def __init__(self) -> None:
        self.token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    def json(self, url: str, retries: int = 6) -> dict[str, Any]:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "Exp63-strict-v427"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                if exc.code == 403 and attempt + 1 < retries:
                    reset = int(exc.headers.get("X-RateLimit-Reset", "0") or 0)
                    time.sleep(max(2, min(120, reset - int(time.time()) + 2)))
                    continue
                raise
            except (urllib.error.URLError, TimeoutError):
                if attempt + 1 == retries:
                    raise
                time.sleep(2 ** attempt)
        raise AssertionError("unreachable")

    def raw(self, slug: str, ref: str, path: str) -> tuple[int, bytes]:
        url = "https://raw.githubusercontent.com/{}/{}/{}".format(
            slug, urllib.parse.quote(ref, safe=""), urllib.parse.quote(path, safe="/"))
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Exp63-strict-v427"})
                with urllib.request.urlopen(req, timeout=45) as response:
                    return response.status, response.read()
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    return 404, b""
                if attempt == 3:
                    raise
            except (urllib.error.URLError, TimeoutError):
                if attempt == 3:
                    raise
            time.sleep(2 ** attempt)
        raise AssertionError("unreachable")


def search_url(query: str, page: int = 1) -> str:
    params = urllib.parse.urlencode({
        "q": query, "per_page": SEARCH_PER_PAGE, "page": page,
        "sort": "created", "order": "asc",
    })
    return "https://api.github.com/search/repositories?" + params


def partition_query(api: GitHub, base: str, start: dt.date, end: dt.date,
                    cells: list[dict[str, Any]]) -> None:
    query = f"{base} created:{start.isoformat()}..{end.isoformat()}"
    first = api.json(search_url(query))
    count = int(first.get("total_count", 0))
    if count <= SEARCH_LEAF_LIMIT:
        cells.append({"query": query, "start": start.isoformat(), "end": end.isoformat(),
                      "total_count": count, "first_page": first})
        return
    if start == end:
        raise RuntimeError(f"GitHub cell still exceeds {SEARCH_LEAF_LIMIT}: {query} count={count}")
    midpoint = start + dt.timedelta(days=(end - start).days // 2)
    partition_query(api, base, start, midpoint, cells)
    partition_query(api, base, midpoint + dt.timedelta(days=1), end, cells)


def discover(api: GitHub, root: Path) -> list[dict[str, Any]]:
    snapshotp = root / "discovery/github_repository_snapshot.jsonl"
    if snapshotp.is_file():
        return read_jsonl(snapshotp)
    cells: list[dict[str, Any]] = []
    today = dt.datetime.now(dt.timezone.utc).date()
    for base in GITHUB_STAR_QUERIES:
        partition_query(api, base, dt.date(2008, 1, 1), today, cells)
    repositories: dict[int, dict[str, Any]] = {}
    public_cells = []
    for index, cell in enumerate(cells, 1):
        pages = (cell["total_count"] + SEARCH_PER_PAGE - 1) // SEARCH_PER_PAGE
        items: list[dict[str, Any]] = []
        for page in range(1, pages + 1):
            data = cell.pop("first_page") if page == 1 and "first_page" in cell else api.json(search_url(cell["query"], page))
            items.extend(data.get("items", []))
        if len(items) != cell["total_count"]:
            raise ValueError(f"incomplete GitHub cell {cell['query']}: {len(items)} != {cell['total_count']}")
        public_cells.append({**cell, "pages": pages, "observed_items": len(items)})
        for item in items:
            repositories[int(item["id"])] = {
                "github_id": int(item["id"]), "slug": item["full_name"],
                "url": item["clone_url"], "default_branch": item.get("default_branch") or "main",
                "fork": bool(item.get("fork")), "archived": bool(item.get("archived")),
                "private": bool(item.get("private")), "stars": int(item.get("stargazers_count", 0)),
                "created_at": item.get("created_at"), "updated_at": item.get("updated_at"),
            }
        print(f"EXP63-DISCOVERY-CELL {index}/{len(cells)} items={len(items)} unique={len(repositories)}", flush=True)
    rows = sorted(repositories.values(), key=lambda row: (row["slug"].lower(), row["github_id"]))
    atomic_jsonl_dump(rows, snapshotp)
    atomic_jsonl_dump(public_cells, root / "discovery/github_search_cells.jsonl")
    return rows


def probe_one(api: GitHub, row: dict[str, Any], receipts: Path) -> dict[str, Any]:
    outp = receipts / f"{safe_slug(row['slug'])}.json"
    if outp.is_file():
        return read_json(outp)
    result: dict[str, Any] = {
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "repository": row, "strict_surface_gate": False,
        "first_failed_gate": None, "scientific_candidate_tactics_executed": 0,
    }
    try:
        if row["slug"].lower() in HISTORICAL_SCIENTIFIC_REPOSITORIES_LOWER:
            result["first_failed_gate"] = "historical_scientific_repository"
            raise ValueError("historical scientific repository exclusion")
        if row["fork"] or row["archived"] or row["private"]:
            result["first_failed_gate"] = "public_nonfork_nonarchived"
            raise ValueError("repository status changed")
        status, content = api.raw(row["slug"], row["default_branch"], "lean-toolchain")
        toolchain = content.decode("utf-8", errors="replace").strip() if status == 200 else None
        result["branch_toolchain"] = toolchain
        if toolchain != TARGET_TOOLCHAIN:
            result["first_failed_gate"] = "exact_current_root_toolchain"
            raise ValueError(f"current root toolchain is {toolchain!r}")
        commit_data = api.json(
            f"https://api.github.com/repos/{row['slug']}/commits/" +
            urllib.parse.quote(row["default_branch"], safe=""))
        commit = str(commit_data["sha"])
        if not __import__("re").fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("non-content-addressed HEAD")
        status, exact_content = api.raw(row["slug"], commit, "lean-toolchain")
        if status != 200 or exact_content.decode("utf-8", errors="replace").strip() != TARGET_TOOLCHAIN:
            raise ValueError("HEAD changed during toolchain probe")
        licenses = []
        for name in ROOT_LICENSE_NAMES:
            if api.raw(row["slug"], commit, name)[0] == 200:
                licenses.append(name)
        if not licenses:
            result["first_failed_gate"] = "root_license"
            raise ValueError("no root license")
        lakefiles = [name for name in ROOT_LAKEFILE_NAMES if api.raw(row["slug"], commit, name)[0] == 200]
        if not lakefiles:
            result["first_failed_gate"] = "root_lakefile"
            raise ValueError("no root lakefile")
        result.update({
            "commit": commit, "licenses": licenses, "lakefiles": lakefiles,
            "strict_surface_gate": True, "first_failed_gate": None,
        })
    except Exception as exc:
        result["error"] = {"type": type(exc).__name__, "message": str(exc)[-4000:]}
        if result["first_failed_gate"] is None:
            result["first_failed_gate"] = "operational_probe"
    result = seal(result)
    atomic_json_dump(result, outp)
    return result


def run(root: Path, workers: int) -> dict[str, Any]:
    protocol = read_json(root / "frozen/protocol.json")
    assert_sealed(protocol, "Exp63 protocol")
    validate_locks(protocol)
    api = GitHub()
    rows = discover(api, root)
    receipts = root / "discovery/probe_receipts"
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(probe_one, api, row, receipts) for row in rows]
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            results.append(future.result())
            if index % 100 == 0 or index == len(futures):
                print(f"EXP63-PROBE {index}/{len(futures)} strict={sum(x['strict_surface_gate'] for x in results)}", flush=True)
    strict = []
    gates: dict[str, int] = {}
    for receipt in results:
        gate = str(receipt.get("first_failed_gate"))
        gates[gate] = gates.get(gate, 0) + 1
        if receipt["strict_surface_gate"]:
            repo = receipt["repository"]
            strict.append({
                **repo, "commit": receipt["commit"], "ref": receipt["commit"], "subdir": ".",
                "domain": "unclassified", "snapshot_source": "Exp63 complete GitHub current-HEAD snapshot",
                "lean_toolchain_observed": TARGET_TOOLCHAIN,
                "surface_receipt_sha256": receipt["record_sha256"],
                "snapshot_record_sha256": json_sha256({"repository": repo, "commit": receipt["commit"]}),
            })
    strict.sort(key=lambda row: selection_key(FRAME_ORDER_SEED, row["slug"], row["commit"]))
    atomic_jsonl_dump(strict, root / "discovery/v427_surface.jsonl")
    summary = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "github_repository_rows": len(rows), "strict_current_v427_surface": len(strict),
        "probe_gate_counts": dict(sorted(gates.items())),
        "search_cells": len(read_jsonl(root / "discovery/github_search_cells.jsonl")),
        "repository_snapshot_sha256": file_sha256(root / "discovery/github_repository_snapshot.jsonl"),
        "strict_surface_sha256": file_sha256(root / "discovery/v427_surface.jsonl"),
        "complete_github_search": True, "scientific_candidate_tactics_executed": 0,
    })
    atomic_json_dump(summary, root / "discovery/summary.json")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--workers", type=int, default=SEARCH_WORKERS)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run(Path(args.artifact_root).resolve(), args.workers), indent=2))
