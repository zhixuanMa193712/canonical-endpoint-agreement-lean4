"""Freeze the outcome-blind Exp53 subset from the final Exp51 bundle."""
from __future__ import annotations

import argparse
import io
import json
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from exp53_protocol import *


CONFIG_MEMBER = "artifacts/frozen/experiment51_config.json"
TARGETS_MEMBER = "artifacts/frozen/targets.json"
ROW_INDEX_MEMBER = "artifacts/scientific/row_index.jsonl"


def member_json(zf: zipfile.ZipFile, name: str) -> Any:
    return json.loads(zf.read(name).decode("utf-8"))


def member_jsonl(zf: zipfile.ZipFile, name: str) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in zf.read(name).decode("utf-8").splitlines()
        if line.strip()
    ]


def target_key(row: dict[str, Any]) -> str:
    return json_sha256([
        row[key]
        for key in (
            "theorem_id", "source_file_sha256", "file_path",
            "target_pos", "target_end_pos",
        )
    ])


def freeze(source_archive: Path) -> dict[str, Any]:
    source_archive = source_archive.resolve()
    if file_sha256(source_archive) != SOURCE_EXP51_SHA256:
        raise ValueError("Exp51 source bundle SHA-256 mismatch")
    frozen_root = PACKAGE_ROOT / "frozen"
    references_root = frozen_root / "references"
    references_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source_archive) as zf:
        if zf.testzip() is not None:
            raise ValueError("Exp51 source bundle contains a corrupt member")
        config_bytes = zf.read(CONFIG_MEMBER)
        targets_bytes = zf.read(TARGETS_MEMBER)
        index_bytes = zf.read(ROW_INDEX_MEMBER)
        config = json.loads(config_bytes.decode("utf-8"))
        targets = json.loads(targets_bytes.decode("utf-8"))
        row_index = [
            json.loads(line)
            for line in index_bytes.decode("utf-8").splitlines()
            if line.strip()
        ]
        if not (
            config.get("protocol_version") == SOURCE_EXP51_PROTOCOL
            and len(targets) == 576
            and len(row_index) == 576
        ):
            raise ValueError("Exp51 source dimensions changed")
        repositories = sorted(
            config["repositories"], key=lambda row: row["slug"].encode("utf-8")
        )[:REPOSITORIES]
        selected_slugs = [row["slug"] for row in repositories]
        selected_targets: list[dict[str, Any]] = []
        for slug in selected_slugs:
            candidates = sorted(
                (row for row in targets if row["slug"] == slug), key=target_key
            )
            if len(candidates) != 48:
                raise ValueError(f"Exp51 root allocation changed: {slug}")
            selected_targets.extend(candidates[:ROOTS_PER_REPOSITORY])
        index_by_theorem = {row["theorem_id"]: row for row in row_index}
        references: list[dict[str, Any]] = []
        portable_targets: list[dict[str, Any]] = []
        for order, target in enumerate(selected_targets):
            index = index_by_theorem[target["theorem_id"]]
            member = (
                f"artifacts/scientific/shards/shard-{index['shard_index']:02d}/"
                f"theorems/{safe_slug(target['slug'])}/{target['rid']}.json"
            )
            source_row = member_json(zf, member)
            projection = row_projection(source_row)
            projection["reference_projection_sha256"] = json_sha256(projection)
            reference_rel = Path("frozen/references") / f"{target['rid']}.json"
            atomic_json_dump(projection, PACKAGE_ROOT / reference_rel)
            references.append({
                "order": order,
                "rid": target["rid"],
                "theorem_id": target["theorem_id"],
                "slug": target["slug"],
                "path": str(reference_rel),
                "sha256": file_sha256(PACKAGE_ROOT / reference_rel),
                "source_member": member,
                "source_member_sha256": bytes_sha256(zf.read(member)),
            })
            portable_targets.append({
                key: target[key]
                for key in (
                    "slug", "commit", "file_path", "full_name", "theorem_id",
                    "rid", "source_file_sha256", "trace_root_state",
                    "trace_root_state_sha256", "authored_tactic", "target_pos",
                    "target_end_pos", "ast_sha256", "alternatives",
                    "alternatives_sha256", "target_identity_sha256",
                )
            })
    subset = {
        "version": 1,
        "freeze_schema": FREEZE_SCHEMA,
        "protocol_version": PROTOCOL_VERSION,
        "source_exp51_bundle_sha256": SOURCE_EXP51_SHA256,
        "selection_rule": {
            "repositories": "first four by UTF-8 slug order",
            "roots": "first four per repository by portable source-identity hash",
            "candidate_outcomes_used": False,
        },
        "repositories": [
            {
                "slug": row["slug"],
                "commit": row["commit"],
                "clone_url": f"https://github.com/{row['slug']}.git",
            }
            for row in repositories
        ],
        "targets": portable_targets,
        "dimensions": {
            "repositories": REPOSITORIES,
            "roots_per_repository": ROOTS_PER_REPOSITORY,
            "roots": ROOTS,
            "candidates_per_root": CANDIDATES_PER_ROOT,
            "candidate_attempts": ROOTS * CANDIDATES_PER_ROOT,
        },
        "claim_boundary": [
            "cross-machine executable-content reproducibility on the frozen subset",
            "no prevalence, recurrence, continuation, or theorem-success inference",
            "Exp48, Exp51, and Exp52 scientific decisions remain unchanged",
        ],
    }
    subset_path = frozen_root / "subset.json"
    reference_index_path = frozen_root / "reference_index.json"
    atomic_json_dump(subset, subset_path)
    atomic_json_dump(references, reference_index_path)
    aborted_receipt = read_json(
        PACKAGE_ROOT / "frozen/aborted_parallel_launch_receipt.json"
    )
    receipt = {
        "version": 1,
        "freeze_schema": FREEZE_SCHEMA,
        "protocol_version": PROTOCOL_VERSION,
        "source_exp51_bundle": source_archive.name,
        "source_exp51_bundle_sha256": SOURCE_EXP51_SHA256,
        "source_config_sha256": bytes_sha256(config_bytes),
        "source_targets_sha256": bytes_sha256(targets_bytes),
        "source_row_index_sha256": bytes_sha256(index_bytes),
        "subset_sha256": file_sha256(subset_path),
        "reference_index_sha256": file_sha256(reference_index_path),
        "reference_rows": len(references),
        "repository_counts": dict(Counter(row["slug"] for row in portable_targets)),
        "code_lock": code_lock(),
        "scientific_candidate_tactics_executed": 0,
        "theorem_sources_elaborated": 0,
        "prior_aborted_scientific_launch": True,
        "prior_aborted_launch_receipt_sha256": file_sha256(
            PACKAGE_ROOT / "frozen/aborted_parallel_launch_receipt.json"
        ),
        "prior_aborted_rows_persisted": aborted_receipt["rows_persisted"],
        "prior_aborted_candidate_attempts_in_persisted_rows": aborted_receipt[
            "candidate_attempts_in_persisted_rows"
        ],
        "prior_aborted_comparison_analysis_executed": aborted_receipt[
            "comparison_analysis_executed"
        ],
        "freeze_gate": True,
        "next_step": "Transfer the frozen package to a second machine and prepare exact checkouts.",
    }
    receipt["identity_sha256"] = json_sha256(receipt)
    atomic_json_dump(receipt, frozen_root / "freeze_receipt.json")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-archive",
        default=str(PACKAGE_ROOT.parent / SOURCE_EXP51_BUNDLE),
    )
    return parser.parse_args()


if __name__ == "__main__":
    freeze(Path(parse_args().source_archive))
