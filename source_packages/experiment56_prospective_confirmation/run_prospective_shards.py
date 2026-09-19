"""Execute one frozen Exp56 repository shard in fresh Lean processes."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from experiment56_protocol import *


sys.path.insert(0, str(WORKSPACE_ROOT / "experiment51_external_repository_replication"))
import screen_experiment51_repositories as backend  # type: ignore


def run(root: Path, shard_index: int, timeout: int) -> dict[str, Any]:
    selection = read_json(root / "frozen/selection_receipt.json")
    assert_sealed(selection, "selection receipt")
    if selection.get("selection_gate") is not True:
        raise ValueError("prospective selection gate did not pass")
    protocol = read_json(root / "frozen/protocol.json"); assert_sealed(protocol, "protocol")
    validate_implementation_locks(protocol)
    targets = read_jsonl(root / "frozen/selected_roots.jsonl")
    repositories = sorted(
        {row["slug"] for row in targets},
        key=lambda slug: next(row["repository_selection_rank"] for row in targets if row["slug"] == slug),
    )
    if not 0 <= shard_index < len(repositories):
        raise ValueError("shard index outside frozen repository range")
    slug = repositories[shard_index]
    selected = [row for row in targets if row["slug"] == slug]
    rows = []
    for index, target in enumerate(selected, 1):
        safe = backend.safe_slug(slug)
        output = root / "scientific/theorems" / safe / f"{target['rid']}.json"
        if output.exists():
            raise FileExistsError("prospective scientific retry prohibited")
        inp = backend.worker_input(
            root, target, protocol["record_sha256"], list(target["alternatives"]), "scientific"
        )
        input_path = root / "scientific/inputs" / safe / f"{target['rid']}.json"
        backend.atomic_json_dump(inp, input_path)
        proc = subprocess.run(
            [sys.executable, str(backend.WORKER), "--input", str(input_path),
             "--output", str(output), "--generated-dir", str(root / "generated"),
             "--timeout", str(timeout)],
            cwd=backend.PACKAGE_ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=timeout + 120,
        )
        if not output.is_file():
            raise RuntimeError(f"scientific worker lacked receipt: {proc.stderr[-6000:]}")
        row = backend.read_json(output)
        if row.get("record_sha256") != json_sha256({k: v for k, v in row.items() if k != "record_sha256"}):
            raise ValueError("scientific row hash changed")
        rows.append(row)
        print(f"EXP56-SCIENTIFIC {shard_index:02d} {index}/{len(selected)} {target['full_name']} ok={int(row.get('worker_ok') is True)}", flush=True)
    value = seal({
        "version": VERSION, "protocol_version": PROTOCOL_VERSION,
        "shard_index": shard_index, "slug": slug,
        "roots_expected": len(selected), "root_receipts": len(rows),
        "evaluable_roots": sum(row.get("worker_ok") is True for row in rows),
        "candidate_attempts": sum(len(row.get("candidates", [])) for row in rows),
        "all_attempts_once": True, "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
    })
    atomic_json_dump(value, root / "scientific/shards" / f"shard-{shard_index:02d}.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--timeout", type=int, default=900)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run(Path(args.artifact_root).resolve(), args.shard_index, args.timeout), indent=2))
