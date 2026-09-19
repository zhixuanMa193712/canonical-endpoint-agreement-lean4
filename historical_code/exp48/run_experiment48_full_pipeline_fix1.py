"""Exp48 Fix1 pipeline: amendment -> preflight -> smoke -> discovery -> confirmation -> Mac bundle."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from experiment48_protocol import ARTIFACT_ROOT, read_json


def call(cmd: list[str]) -> None:
    print("$ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def main(args: argparse.Namespace) -> None:
    root = Path(args.root)
    amendment = root / "amendments/experiment48_preflight_fix1.json"
    if not amendment.is_file():
        call([sys.executable, "amend_experiment48_preflight_fix1.py"])

    preflight = root / "preflight_fix1/live_worker_compile.json"
    if not preflight.is_file():
        call([sys.executable, "preflight_experiment48_live_worker_fix1.py"])
    if read_json(preflight).get("compile_ok") is not True:
        print("STOP: Exp48 Fix1 live worker compile preflight failed; smoke was not executed.")
        return

    smoke = root / "smoke_fix1/summary.json"
    if not smoke.is_file():
        cmd = [sys.executable, "run_experiment48_live_tacticinfo_equivalence_fix1.py", "--phase", "smoke", "--lean-timeout", str(args.lean_timeout)]
        if (root / "experiment48_smoke_fix1_claim.json").exists():
            cmd.append("--resume")
        call(cmd)
    if read_json(smoke).get("protocol_smoke_ok") is not True:
        print("STOP: Exp48 Fix1 smoke did not pass; discovery/confirmation were not executed.")
        return

    discovery = root / "discovery_fix1/summary.json"
    if not discovery.is_file():
        cmd = [sys.executable, "run_experiment48_live_tacticinfo_equivalence_fix1.py", "--phase", "discovery", "--lean-timeout", str(args.lean_timeout)]
        if (root / "experiment48_discovery_fix1_claim.json").exists():
            cmd.append("--resume")
        call(cmd)

    confirmation = root / "confirmation_fix1/summary.json"
    if not confirmation.is_file():
        cmd = [sys.executable, "run_experiment48_live_tacticinfo_equivalence_fix1.py", "--phase", "confirmation", "--lean-timeout", str(args.lean_timeout)]
        if (root / "experiment48_confirmation_fix1_claim.json").exists():
            cmd.append("--resume")
        call(cmd)

    bundle = Path("artifacts/v48/experiment48_fix1_mac_analysis_bundle.zip")
    if not bundle.is_file():
        call([sys.executable, "export_experiment48_mac_bundle_fix1.py"])
    print(f"Exp48 Fix1 complete. Mac bundle: {bundle}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    p.add_argument("--lean-timeout", type=int, default=900)
    return p.parse_args()


if __name__ == "__main__":
    main(parse_args())
