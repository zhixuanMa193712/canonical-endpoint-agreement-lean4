"""Resumable server orchestrator for the complete frozen Exp49 protocol."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from experiment49_protocol import ARTIFACT_ROOT, PACKAGE_ROOT, SERVER_ROOT


def _run(script: str, *extra: str) -> None:
    cmd = [sys.executable, str(PACKAGE_ROOT / script), *extra]
    print("RUN", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def main(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    frozen = root / "frozen/experiment49_freeze_transaction.json"
    freeze_args = ["--output-dir", str(root)]
    if frozen.exists() or (root / "frozen/experiment49_freeze_claim.json").exists():
        freeze_args.append("--resume-freeze")
    _run("freeze_experiment49.py", *freeze_args)
    _run("preflight_experiment49.py", "--root", str(root),
         "--timeout", str(args.preflight_timeout))
    for phase in ("smoke", "validation"):
        if (root / phase / "execution_summary.json").exists():
            print(f"SKIP completed {phase}", flush=True)
            continue
        phase_args = ["--config", str(root / "frozen/experiment49_config.json"),
                      "--phase", phase, "--lean-timeout", str(args.lean_timeout)]
        if (root / f"experiment49_{phase}_claim.json").exists():
            phase_args.append("--resume")
        _run("run_experiment49.py", *phase_args)
    if not (root / "analysis/summary.json").exists():
        _run("experiment49_analysis.py", "--root", str(root))
    else:
        print("SKIP completed analysis", flush=True)
    output = Path(args.output).resolve()
    if not output.exists():
        _run("export_experiment49_bundle.py", "--root", str(root), "--output", str(output))
    else:
        print(f"SKIP existing export {output}", flush=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    p.add_argument("--preflight-timeout", type=int, default=300)
    p.add_argument("--lean-timeout", type=int, default=900)
    p.add_argument("--output", default=str(SERVER_ROOT / "exports/experiment49_candidate_endpoint_robustness_results.zip"))
    return p.parse_args()


if __name__ == "__main__":
    main(parse_args())
