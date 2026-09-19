"""Export completed isolated Exp48 Fix1 results for MacBook/Codex."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from experiment48_protocol import ARTIFACT_ROOT, atomic_json_dump, file_sha256, read_json

FIX_ID = "experiment48-live-worker-filepath-v427-fix1"


def export(args: argparse.Namespace) -> Path:
    root = Path(args.root).resolve()
    confirmation = root / "confirmation_fix1/summary.json"
    if not confirmation.is_file():
        raise FileNotFoundError("Exp48 Fix1 confirmation is not complete")
    conf = read_json(confirmation)
    if conf.get("scientific_metrics_authoritative") is not True or conf.get("fix_id") != FIX_ID:
        raise ValueError("Exp48 Fix1 confirmation summary is not authoritative")
    include: list[Path] = []
    for rel in (
        "frozen/experiment48_config.json",
        "frozen/experiment48_freeze_receipt.json",
        "amendments/experiment48_preflight_fix1.json",
        "preflight/live_worker_compile.json",
        "preflight_fix1/live_worker_compile.json",
        "smoke_fix1/summary.json",
        "discovery_fix1/summary.json",
        "confirmation_fix1/summary.json",
        "smoke_fix1/repo_summaries.jsonl",
        "discovery_fix1/repo_summaries.jsonl",
        "confirmation_fix1/repo_summaries.jsonl",
    ):
        p = root / rel
        if p.is_file():
            include.append(p)
    for phase in ("smoke_fix1", "discovery_fix1", "confirmation_fix1"):
        include.extend(sorted((root / phase / "repositories").glob("*.json")))
        include.extend(sorted((root / phase / "theorems").glob("*/*.json")))
    cfg = read_json(root / "frozen/experiment48_config.json")
    probe_path = Path(cfg["source_live_tacticinfo_qualification"])
    if probe_path.is_file():
        include.append(probe_path)

    outp = Path(args.output).resolve()
    outp.parent.mkdir(parents=True, exist_ok=True)
    manifest = []
    with zipfile.ZipFile(outp, "w", zipfile.ZIP_DEFLATED) as z:
        for p in include:
            if p == probe_path:
                arc = "provenance/live_tacticinfo_qualification_summary.json"
            else:
                arc = p.relative_to(root).as_posix()
            z.write(p, arc)
            manifest.append({"path": arc, "sha256": file_sha256(p), "bytes": p.stat().st_size})
        z.writestr("MAC_BUNDLE_MANIFEST.json", (
            json.dumps({
                "version": 1,
                "experiment": "Exp48 Live TacticInfo Counterfactual Equivalence",
                "mechanical_fix": FIX_ID,
                "confirmation_go": conf.get("confirmation_go"),
                "strong_go": conf.get("strong_go"),
                "files": manifest,
            }, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"))
    atomic_json_dump({
        "bundle": str(outp),
        "bundle_sha256": file_sha256(outp),
        "file_count": len(manifest) + 1,
        "fix_id": FIX_ID,
        "confirmation_go": conf.get("confirmation_go"),
        "strong_go": conf.get("strong_go"),
    }, root.parent / "experiment48_fix1_mac_bundle_receipt.json")
    print(json.dumps({"bundle": str(outp), "sha256": file_sha256(outp), "files": len(manifest) + 1}, indent=2))
    return outp


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    p.add_argument("--output", default="artifacts/v48/experiment48_fix1_mac_analysis_bundle.zip")
    return p.parse_args()


if __name__ == "__main__":
    export(parse_args())
