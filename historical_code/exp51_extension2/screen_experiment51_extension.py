"""Run the frozen zero-scientific-candidate Exp51 frame extension 2."""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from experiment51_extension_protocol import *
from experiment51_repository_frame_extension import (  # noqa: E402
    screen_experiment51_extension as implementation,
)

# The locked Extension1 preflight imports this public name from the active
# screen module.  Re-export it explicitly while keeping the implementation
# byte-identical to the protected Extension1 code.
enumerate_isolated = implementation.enumerate_isolated


def _atomic_bytes(value: bytes, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_bytes(value)
    temporary.replace(target)


def carry_forward(root: Path, config_sha: str) -> dict:
    _, configp, observed_sha = implementation.extension_config(root)
    if observed_sha != config_sha:
        raise ValueError("Extension2 config identity changed")
    rows = validate_base_carry_forward()
    checked = validate_active_carry_checkouts(rows)
    ledger = []
    with zipfile.ZipFile(EXTENSION1_NOGO_BUNDLE) as archive:
        for source in rows:
            slug = source["slug"]
            safe = safe_slug(slug)
            receipt = json.loads(archive.read(source["archive_members"]["receipt"]))
            receipt["extension_carry_forward"] = {
                "extension_version": EXTENSION_VERSION,
                "extension_config_sha256": config_sha,
                "source_bundle": str(EXTENSION1_NOGO_BUNDLE),
                "source_bundle_sha256": EXTENSION1_NOGO_BUNDLE_SHA256,
                "source_receipt_member": source["archive_members"]["receipt"],
                "source_receipt_sha256": source["receipt_sha256"],
                "source_frame_sha256": source["frame_sha256"],
                "source_inventory_sha256": source["source_inventory_sha256"],
                "active_checkout_revalidated": True,
                "scientific_candidate_tactics_executed": 0,
            }
            out_receipt = root / "screening/build_trace" / f"{safe}.json"
            out_frame = root / "screening/frames" / f"{safe}.jsonl"
            out_inventory = root / "screening/source_inventories" / f"{safe}.jsonl"
            atomic_json_dump(receipt, out_receipt)
            _atomic_bytes(archive.read(source["archive_members"]["frame"]), out_frame)
            _atomic_bytes(
                archive.read(source["archive_members"]["source_inventory"]),
                out_inventory,
            )
            if file_sha256(out_frame) != source["frame_sha256"]:
                raise ValueError(f"carried frame changed: {slug}")
            if file_sha256(out_inventory) != source["source_inventory_sha256"]:
                raise ValueError(f"carried inventory changed: {slug}")
            ledger.append({
                "slug": slug,
                "source_receipt_sha256": source["receipt_sha256"],
                "active_receipt_sha256": file_sha256(out_receipt),
                "frame_sha256": file_sha256(out_frame),
                "source_inventory_sha256": file_sha256(out_inventory),
                "pre_replay_frame": source["pre_replay_frame"],
                "active_checkout_gate": True,
            })
    result = {
        "version": 1,
        "extension_version": EXTENSION_VERSION,
        "config": str(configp),
        "config_sha256": config_sha,
        "repositories": len(ledger),
        "repository_ledger": ledger,
        "active_checkout_ledger": checked,
        "all_build_trace_gates_preserved": True,
        "all_active_checkouts_revalidated": len(checked) == len(CARRY_FORWARD_SLUGS),
        "trace_executed": False,
        "theorem_sources_elaborated": 0,
        "scientific_candidate_tactics_executed": 0,
        "carry_forward_gate": (
            len(ledger) == len(CARRY_FORWARD_SLUGS)
            and len(checked) == len(CARRY_FORWARD_SLUGS)
        ),
        "next_step": "Run the two frozen offline parser controls.",
    }
    atomic_json_dump(result, root / "screening/carry_forward_summary.json")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


_extension1_finalize = implementation.finalize


def finalize(root: Path, config: dict, config_sha: str, candidates: list[dict]) -> dict:
    result = _extension1_finalize(root, config, config_sha, candidates)
    for row in result["repository_ledger"]:
        if row.get("source") == "extension1":
            row["source"] = "extension2"
    atomic_json_dump(result, root / "screening/summary.json")
    return result


implementation.carry_forward = carry_forward
implementation.finalize = finalize


if __name__ == "__main__":
    parsed = implementation.parse_args()
    result = implementation.main(parsed)
    gate = (
        result.get("carry_forward_gate")
        if parsed.phase == "carry-forward"
        else result.get("build_trace_gate")
        if parsed.phase == "build-trace"
        else result.get("screening_gate")
    )
    raise SystemExit(0 if gate is True else 2)
