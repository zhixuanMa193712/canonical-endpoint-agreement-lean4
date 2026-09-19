"""Offline audit of the frozen extension frame against a Reservoir manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from experiment51_extension_protocol import (
    CANDIDATE_FRAME,
    RESERVOIR_EXACT_V427_PACKAGE_COUNT,
    RESERVOIR_MANIFEST_BYTES,
    RESERVOIR_MANIFEST_SHA256,
    TARGET_TOOLCHAIN,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(manifest_path: Path, frame_path: Path = CANDIDATE_FRAME) -> dict[str, Any]:
    if manifest_path.stat().st_size != RESERVOIR_MANIFEST_BYTES:
        raise ValueError("Reservoir manifest byte count changed")
    if sha256(manifest_path) != RESERVOIR_MANIFEST_SHA256:
        raise ValueError("Reservoir manifest SHA-256 changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    frame = json.loads(frame_path.read_text(encoding="utf-8"))
    packages = list(manifest.get("packages", []))
    by_name = {str(row["fullName"]).casefold(): row for row in packages}
    exact_v427 = sum(
        any(version.get("toolchain") == TARGET_TOOLCHAIN for version in package["versions"])
        for package in packages
    )
    if exact_v427 != RESERVOIR_EXACT_V427_PACKAGE_COUNT:
        raise ValueError("exact-v4.27 Reservoir population changed")

    rows = []
    for candidate in frame["candidates"]:
        package = by_name.get(str(candidate["reservoir_package"]).casefold())
        if package is None:
            raise ValueError(f"Reservoir package is absent: {candidate['slug']}")
        versions = [
            version for version in package["versions"]
            if version.get("revision") == candidate["ref"]
            and version.get("toolchain") == candidate["target_toolchain"]
            and version.get("date") == candidate["reservoir_version_date"]
            and version.get("tag") == candidate.get("reservoir_version_tag")
        ]
        source_names = {
            str(source.get("fullName", "")).casefold()
            for source in package.get("sources", [])
        }
        builds = [
            build for build in package.get("builds", [])
            if build.get("revision") == candidate["ref"]
            and build.get("toolchain") == candidate["target_toolchain"]
            and build.get("built") is True
        ]
        exact_build = bool(builds)
        archive_bytes = max(
            (int(build.get("archiveSize") or 0) for build in builds),
            default=0,
        )
        row = {
            "order": candidate["order"],
            "slug": candidate["slug"],
            "version_exact": len(versions) == 1,
            "github_source_exact": candidate["slug"].casefold() in source_names,
            "license_exact": package.get("license") == candidate["license"],
            "exact_unmodified_build_record": exact_build,
            "build_flag_exact": candidate["reservoir_exact_unmodified_build_record"]
            is exact_build,
            "build_archive_bytes_exact": candidate["reservoir_build_archive_bytes"]
            == archive_bytes,
        }
        row["candidate_gate"] = all(
            row[key] is True
            for key in (
                "version_exact",
                "github_source_exact",
                "license_exact",
                "build_flag_exact",
                "build_archive_bytes_exact",
            )
        )
        rows.append(row)
    result = {
        "version": 1,
        "audit_schema": "experiment51-extension1-reservoir-frame-audit-v1",
        "diagnostic_only": True,
        "network_access": False,
        "manifest": str(manifest_path.resolve()),
        "manifest_sha256": RESERVOIR_MANIFEST_SHA256,
        "manifest_bytes": RESERVOIR_MANIFEST_BYTES,
        "packages": len(packages),
        "packages_with_exact_v427_release": exact_v427,
        "candidates_checked": len(rows),
        "candidates_with_exact_unmodified_build_record": sum(
            row["exact_unmodified_build_record"] for row in rows
        ),
        "candidate_rows": rows,
        "frame_audit_gate": len(rows) == 28 and all(row["candidate_gate"] for row in rows),
        "scientific_candidate_tactics_executed": 0,
    }
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--frame", default=str(CANDIDATE_FRAME))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = audit(Path(args.manifest), Path(args.frame))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["frame_audit_gate"] else 2)
