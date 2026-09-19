"""Clone exact external benchmark commits, verify licenses/toolchains, and optionally build."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from experiment58_protocol import *


def command(cmd: list[str], cwd: Path | None = None, timeout: int = 3600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def prepare_one(dataset: str, checkout_root: Path, build: bool, jobs: int, timeout: int) -> dict[str, Any]:
    spec = DATASETS[dataset]
    checkout = checkout_root / dataset
    if not checkout.exists():
        proc = command(["git", "clone", "--filter=blob:none", str(spec["url"]), str(checkout)], timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(f"clone failed for {dataset}: {proc.stderr[-4000:]}")
    if not (checkout / ".git").is_dir():
        raise ValueError(f"existing checkout is not a git repository: {checkout}")
    remote = command(["git", "remote", "get-url", "origin"], checkout).stdout.strip()
    if remote.rstrip("/").removesuffix(".git") != str(spec["url"]).rstrip("/").removesuffix(".git"):
        raise ValueError(f"unexpected origin for {dataset}: {remote}")
    checkout_proc = command(["git", "checkout", "--detach", str(spec["commit"])], checkout, timeout)
    if checkout_proc.returncode != 0:
        fetch = command(["git", "fetch", "--depth", "1", "origin", str(spec["commit"])], checkout, timeout)
        if fetch.returncode != 0:
            raise RuntimeError(f"fetch failed for {dataset}: {fetch.stderr[-4000:]}")
        checkout_proc = command(["git", "checkout", "--detach", str(spec["commit"])], checkout, timeout)
    if checkout_proc.returncode != 0:
        raise RuntimeError(f"checkout failed for {dataset}: {checkout_proc.stderr[-4000:]}")
    observed_commit = command(["git", "rev-parse", "HEAD"], checkout).stdout.strip()
    status = command(["git", "status", "--porcelain", "--untracked-files=no"], checkout).stdout
    toolchain = checkout / str(spec["toolchain_path"])
    license_path = checkout / str(spec["license_path"])
    toolchain_text = toolchain.read_text(encoding="utf-8").strip()
    project = project_path(dataset, checkout_root)
    build_result: dict[str, Any] = {"requested": build, "returncode": None}
    if build:
        # Lake 5.0 (Lean v4.27.0) has no -j/--jobs build option.  Its build
        # graph is scheduled natively; retain the requested value as resource
        # intent without passing an unsupported scientific command argument.
        proc = command(["lake", "build"], project, timeout)
        build_result.update({
            "returncode": proc.returncode,
            "requested_build_jobs": jobs,
            "scheduler": "lake-5-native-build-graph",
            "command": ["lake", "build"],
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-8000:],
        })
    return {
        "dataset": dataset, "url": spec["url"], "checkout": str(checkout),
        "project": str(project), "commit_expected": spec["commit"],
        "commit_observed": observed_commit, "commit_exact": observed_commit == spec["commit"],
        "tracked_checkout_clean": status == "", "toolchain": toolchain_text,
        "toolchain_exact": toolchain_text == TARGET_TOOLCHAIN,
        "toolchain_sha256": file_sha256(toolchain),
        "toolchain_sha256_exact": file_sha256(toolchain) == spec["toolchain_sha256"],
        "license": spec["license"], "license_path": str(license_path),
        "license_sha256": file_sha256(license_path),
        "license_sha256_exact": file_sha256(license_path) == spec["license_sha256"],
        "build": build_result,
        "dataset_gate": bool(
            observed_commit == spec["commit"] and status == "" and toolchain_text == TARGET_TOOLCHAIN
            and file_sha256(toolchain) == spec["toolchain_sha256"]
            and file_sha256(license_path) == spec["license_sha256"]
            and build and build_result["returncode"] == 0
        ),
    }


def run(root: Path, checkout_root: Path, build: bool, jobs: int, timeout: int) -> dict[str, Any]:
    load_protocol(root)
    rows = [prepare_one(dataset, checkout_root, build, jobs, timeout) for dataset in sorted(DATASETS)]
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "datasets": rows, "environment_gate": all(row["dataset_gate"] for row in rows),
        "build_required": True,
        "candidate_only_tactics_executed": 0, "continuation_probes_executed": 0,
        "next_step": "Enumerate and hash the complete external target frame." if all(row["dataset_gate"] for row in rows)
        else "STOP: checkout, license, toolchain, or build gate failed.",
    })
    atomic_json_dump(value, root / "preflight/benchmark_environment.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--checkout-root", default=str(CHECKOUT_ROOT))
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--build-jobs", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=14400)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run(Path(args.artifact_root).resolve(), Path(args.checkout_root).resolve(),
                         args.build, args.build_jobs, args.timeout), indent=2))
