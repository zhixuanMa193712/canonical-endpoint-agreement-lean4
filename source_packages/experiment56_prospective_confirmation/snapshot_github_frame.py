"""Snapshot the prospective GitHub repository frame before qualification.

Requires ``GITHUB_TOKEN``. Raw search and repository responses are retained;
the script does not build, trace, elaborate, or execute any Lean source.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from experiment56_protocol import *


API = "https://api.github.com"


def request(path: str, token: str) -> tuple[bytes, dict[str, str]]:
    req = urllib.request.Request(
        API + path,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "MZX-Exp56-frame-snapshot"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read(), dict(response.headers)


def snapshot(root: Path, per_query: int, max_pages: int) -> dict[str, Any]:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("set GITHUB_TOKEN before candidate-frame snapshot")
    protocol = read_json(root / "frozen/protocol.json"); assert_sealed(protocol, "protocol")
    validate_implementation_locks(protocol)
    raw_root = root / "recruitment_snapshot/raw"
    candidates: dict[str, dict[str, Any]] = {}
    response_ledger = []
    for query_index, query in enumerate(FROZEN_GITHUB_QUERIES):
        for page in range(1, max_pages + 1):
            encoded = urllib.parse.urlencode({"q": query, "sort": "stars", "order": "desc",
                                              "per_page": per_query, "page": page})
            path = f"/search/repositories?{encoded}"
            raw, headers = request(path, token)
            raw_path = raw_root / f"query-{query_index:02d}-page-{page:02d}.json"
            raw_path.parent.mkdir(parents=True, exist_ok=True); raw_path.write_bytes(raw)
            data = json.loads(raw)
            response_ledger.append({
                "kind": "search", "query": query, "page": page, "api_path": path,
                "path": str(raw_path), "bytes": len(raw), "sha256": file_sha256(raw_path),
                "etag": headers.get("ETag"),
            })
            items = data.get("items", [])
            for item in items:
                candidates.setdefault(item["full_name"].lower(), item)
            if len(items) < per_query:
                break
            time.sleep(0.25)
    rows = []
    for index, item in enumerate(sorted(candidates.values(), key=lambda x: x["full_name"].lower()), 1):
        slug = item["full_name"]
        branch = item["default_branch"]
        commit_path = f"/repos/{slug}/commits/{urllib.parse.quote(branch, safe='')}"
        raw_commit, headers = request(commit_path, token)
        commit_file = raw_root / "commits" / f"{slug.replace('/', '__')}.json"
        commit_file.parent.mkdir(parents=True, exist_ok=True); commit_file.write_bytes(raw_commit)
        commit_data = json.loads(raw_commit)
        commit = commit_data["sha"]
        if len(commit) != 40:
            raise ValueError(f"non-exact GitHub commit for {slug}")
        response_ledger.append({
            "kind": "commit", "slug": slug, "api_path": commit_path,
            "path": str(commit_file), "bytes": len(raw_commit), "sha256": file_sha256(commit_file),
            "etag": headers.get("ETag"),
        })
        toolchain = None
        toolchain_sha = None
        toolchain_path = f"/repos/{slug}/contents/lean-toolchain?ref={commit}"
        try:
            raw_toolchain, headers = request(toolchain_path, token)
            toolchain_file = raw_root / "toolchains" / f"{slug.replace('/', '__')}.json"
            toolchain_file.parent.mkdir(parents=True, exist_ok=True); toolchain_file.write_bytes(raw_toolchain)
            toolchain_data = json.loads(raw_toolchain)
            content = base64.b64decode(toolchain_data.get("content", ""))
            toolchain = content.decode("utf-8", errors="replace").strip()
            toolchain_sha = hashlib.sha256(content).hexdigest()
            response_ledger.append({
                "kind": "toolchain", "slug": slug, "api_path": toolchain_path,
                "path": str(toolchain_file), "bytes": len(raw_toolchain),
                "sha256": file_sha256(toolchain_file), "etag": headers.get("ETag"),
            })
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            raw_missing = exc.read()
            missing_file = raw_root / "toolchains_missing" / f"{slug.replace('/', '__')}.json"
            missing_file.parent.mkdir(parents=True, exist_ok=True)
            missing_file.write_bytes(raw_missing)
            response_ledger.append({
                "kind": "toolchain_missing", "slug": slug, "api_path": toolchain_path,
                "status": 404, "path": str(missing_file), "bytes": len(raw_missing),
                "sha256": file_sha256(missing_file), "etag": exc.headers.get("ETag"),
            })
        historical = slug.lower() in {
            value.lower() for value in HISTORICAL_SCIENTIFIC_REPOSITORIES
        }
        prequalification_exclusion = None
        if historical:
            prequalification_exclusion = "historical_scientific_repository"
        elif toolchain != TARGET_TOOLCHAIN:
            prequalification_exclusion = "missing_or_non_v427_root_toolchain"
        record = {
            "slug": slug, "url": item["clone_url"], "commit": commit,
            "default_branch": branch, "domain": "unclassified",
            "snapshot_source": "GitHub REST API frozen stratified repository search",
            "github_repository_id": item["id"], "github_node_id": item["node_id"],
            "stars_at_snapshot": item["stargazers_count"],
            "pushed_at": item["pushed_at"], "created_at": item["created_at"],
            "lean_toolchain_observed": toolchain,
            "lean_toolchain_content_sha256": toolchain_sha,
            "prequalification_exclusion": prequalification_exclusion,
            "commit_response_sha256": file_sha256(commit_file),
        }
        record["snapshot_record_sha256"] = json_sha256(record)
        rows.append(record)
        print(f"EXP56-SNAPSHOT {index}/{len(candidates)} {slug}", flush=True)
        time.sleep(0.10)
    frame_path = root / "recruitment_snapshot/candidate_frame_input.jsonl"
    ledger_path = root / "recruitment_snapshot/response_ledger.jsonl"
    atomic_jsonl_dump(rows, frame_path); atomic_jsonl_dump(response_ledger, ledger_path)
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "queries": list(FROZEN_GITHUB_QUERIES), "repositories": len(rows),
        "prequalification_exclusions": sum(row["prequalification_exclusion"] is not None for row in rows),
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
    # At 100 repositories per page, three pages in each of four disjoint star
    # strata require at most about 2,400 follow-up API calls.  This remains
    # below the usual authenticated hourly limit while retaining a broad frame.
    parser.add_argument("--max-pages", type=int, default=3)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(snapshot(Path(args.artifact_root).resolve(), args.per_query, args.max_pages), indent=2))
