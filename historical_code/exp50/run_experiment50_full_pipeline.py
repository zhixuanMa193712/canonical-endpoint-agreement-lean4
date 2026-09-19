"""Run the resumable Exp50 pipeline in its frozen order."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from experiment50_protocol import ARTIFACT_ROOT, PACKAGE_ROOT


def call(script: str, extra: list[str]) -> None:
    cmd = [sys.executable, str(PACKAGE_ROOT / script), *extra]
    print("RUN", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=PACKAGE_ROOT, check=True)


def main(args: argparse.Namespace) -> None:
    root = str(Path(args.root).resolve())
    call("freeze_experiment50.py", ["--output-dir", root])
    call("preflight_experiment50.py", ["--root", root, "--timeout", str(args.preflight_timeout)])
    call("capture_experiment50_environment.py", ["--root", root, "--timeout", str(args.preflight_timeout)])
    for phase in ("smoke", "M0", "orders", "M5"):
        call("run_experiment50.py", ["--root", root, "--phase", phase,
                                     "--lean-timeout", str(args.lean_timeout)])
    call("analyze_experiment50.py", ["--root", root])
    if not args.no_export:
        extra = ["--root", root]
        if args.output:
            extra += ["--output", args.output]
        call("export_experiment50_bundle.py", extra)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    p.add_argument("--preflight-timeout", type=int, default=300)
    p.add_argument("--lean-timeout", type=int, default=900)
    p.add_argument("--output")
    p.add_argument("--no-export", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    main(parse_args())
