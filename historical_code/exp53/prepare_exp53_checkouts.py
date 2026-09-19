"""Materialize and optionally build exact Exp53 checkouts on machine two."""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from exp53_protocol import *


def command(args: list[str], cwd: Path | None = None, timeout: int = 7200) -> str:
    proc = subprocess.run(
        args, cwd=cwd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"command failed: {args}\nstdout={proc.stdout[-4000:]}\n"
            f"stderr={proc.stderr[-8000:]}"
        )
    return (proc.stdout + "\n" + proc.stderr).strip()


def network_command_with_retries(
    args: list[str], cwd: Path, timeout: int, attempts: int = 3,
) -> tuple[str, int]:
    """Retry only dependency-network acquisition, never scientific execution."""
    failures: list[str] = []
    for attempt in range(1, attempts + 1):
        try:
            return command(args, cwd, timeout), attempt
        except RuntimeError as error:
            failures.append(str(error))
            if attempt == attempts:
                raise RuntimeError(
                    f"network command failed after {attempts} attempts\n"
                    + "\n--- retry boundary ---\n".join(failures)
                ) from error
            time.sleep(5 * attempt)
    raise AssertionError("unreachable retry state")


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    subset, receipt = validate_frozen()
    checkout_root = Path(args.checkout_root).resolve()
    checkout_root.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    for repo in subset["repositories"]:
        slug, commit = repo["slug"], repo["commit"]
        project = checkout_root / safe_slug(slug)
        if not project.exists():
            command(["git", "clone", "--filter=blob:none", "--no-checkout", repo["clone_url"], str(project)])
        elif not (project / ".git").is_dir():
            raise ValueError(f"existing checkout path is not a Git repository: {project}")
        command(["git", "fetch", "--depth", "1", "origin", commit], project)
        command(["git", "checkout", "--detach", commit], project)
        head = command(["git", "rev-parse", "HEAD"], project).splitlines()[0]
        if head != commit:
            raise ValueError(f"checkout commit mismatch: {slug}")
        manifest_path = project / "lake-manifest.json"
        manifest_present_before = manifest_path.is_file()
        if manifest_present_before:
            manifest = read_json(manifest_path)
            has_mathlib = any(
                row.get("name") == "mathlib"
                for row in manifest.get("packages", [])
            )
            mathlib_detection = "lake-manifest.json"
        else:
            configuration_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in (project / "lakefile.lean", project / "lakefile.toml")
                if path.is_file()
            )
            has_mathlib = "mathlib" in configuration_text.lower()
            mathlib_detection = "frozen-lakefile" if has_mathlib else "not-detected"
        cache_bootstrap_attempts = 0
        if args.build and has_mathlib:
            _, cache_bootstrap_attempts = network_command_with_retries(
                ["lake", "exe", "cache", "get"],
                project,
                args.build_timeout,
            )
        if args.build:
            command(["lake", "build"], project, args.build_timeout)
        manifest_sha256_after = (
            file_sha256(manifest_path) if manifest_path.is_file() else None
        )
        targets = [row for row in subset["targets"] if row["slug"] == slug]
        source_hashes_exact = all(
            (project / row["file_path"]).is_file()
            and file_sha256(project / row["file_path"]) == row["source_file_sha256"]
            for row in targets
        )
        if not source_hashes_exact:
            raise ValueError(f"selected source hash mismatch: {slug}")
        status = command(["git", "status", "--porcelain", "--untracked-files=no"], project)
        mapping[slug] = str(project)
        rows.append({
            "slug": slug,
            "commit": commit,
            "project": str(project),
            "source_hashes_exact": True,
            "tracked_checkout_clean": status == "",
            "build_requested": bool(args.build),
            "mathlib_cache_bootstrap": bool(args.build and has_mathlib),
            "mathlib_cache_bootstrap_attempts": cache_bootstrap_attempts,
            "mathlib_detection": mathlib_detection,
            "lake_manifest_present_before": manifest_present_before,
            "lake_manifest_sha256_after": manifest_sha256_after,
        })
    artifact_root = Path(args.artifact_root).resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)
    map_path = artifact_root / "environment/checkout_map.json"
    atomic_json_dump({"repositories": mapping}, map_path)
    value = {
        "version": 1,
        "protocol_version": PROTOCOL_VERSION,
        "freeze_identity_sha256": receipt["identity_sha256"],
        "machine": machine_receipt(),
        "repositories": rows,
        "checkout_map": str(map_path),
        "checkout_map_sha256": file_sha256(map_path),
        "preparation_gate": all(row["source_hashes_exact"] for row in rows),
        "next_step": "Run compile-only Exp53 preflight.",
    }
    atomic_json_dump(value, artifact_root / "environment/preparation.json")
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout-root", default="external_repos/experiment53_machine2")
    parser.add_argument("--artifact-root", default="artifacts/v53/cross_machine_subset")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--build-timeout", type=int, default=14400)
    return parser.parse_args()


if __name__ == "__main__":
    value = prepare(parse_args())
    raise SystemExit(0 if value["preparation_gate"] else 2)
