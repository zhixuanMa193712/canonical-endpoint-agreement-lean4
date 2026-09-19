"""Offline audit of the frozen Extension2 discovery frame."""
from __future__ import annotations

import json

from experiment51_extension_protocol import *


def audit() -> dict:
    frame = validate_candidate_frame()
    rows = []
    for candidate in frame["candidates"]:
        row = {
            "order": candidate["order"],
            "slug": candidate["slug"],
            "full_commit": len(candidate["ref"]) == 40,
            "exact_final_v427": candidate["target_toolchain"] == TARGET_TOOLCHAIN,
            "project_subdir_frozen": bool(candidate["subdir"]),
            "root_license_evidence_frozen": candidate["license_evidence"] == "LICENSE",
            "scientific_candidate_tactics_permitted": 0,
        }
        row["candidate_gate"] = all(
            row[key] is True
            for key in (
                "full_commit", "exact_final_v427", "project_subdir_frozen",
                "root_license_evidence_frozen",
            )
        )
        rows.append(row)
    result = {
        "version": 1,
        "audit_schema": "experiment51-extension2-discovery-frame-audit-v1",
        "diagnostic_only": True,
        "network_access": False,
        "candidate_frame": str(CANDIDATE_FRAME),
        "candidate_frame_sha256": file_sha256(CANDIDATE_FRAME),
        "candidates_checked": len(rows),
        "candidate_rows": rows,
        "frame_audit_gate": len(rows) == 7 and all(row["candidate_gate"] for row in rows),
        "scientific_candidate_tactics_executed": 0,
    }
    return result


if __name__ == "__main__":
    result = audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["frame_audit_gate"] else 2)
