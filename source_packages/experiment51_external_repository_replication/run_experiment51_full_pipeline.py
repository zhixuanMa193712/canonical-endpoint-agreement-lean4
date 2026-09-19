"""Run the resumable Exp51 pipeline in its protected order."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from experiment51_protocol import ARTIFACT_ROOT, PACKAGE_ROOT


def call(script: str, extra: list[str]) -> None:
    cmd = [sys.executable, str(PACKAGE_ROOT / script), *extra]
    print("RUN", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=PACKAGE_ROOT, check=True)


def main(args: argparse.Namespace) -> None:
    root = str(Path(args.root).resolve())
    call("freeze_experiment51_recruitment.py", ["--output-dir", root])
    call("preflight_experiment51.py", ["--root", root, "--stage", "trace-runtime"])
    call("preflight_experiment51.py", ["--root", root, "--stage", "parser-adapter",
                                      "--timeout", str(args.enumeration_timeout)])
    call("screen_experiment51_repositories.py", ["--root", root,
         "--phase", "recover-enumeration",
         "--enumeration-workers", str(args.enumeration_workers),
         "--enumeration-timeout", str(args.enumeration_timeout)])
    call("preflight_experiment51.py", ["--root", root, "--stage", "screening",
                                      "--timeout", str(args.preflight_timeout)])
    call("screen_experiment51_repositories.py", ["--root", root, "--phase", "authored-replay",
         "--replay-timeout", str(args.lean_timeout)])
    call("freeze_experiment51.py", ["--root", root])
    call("preflight_experiment51.py", ["--root", root, "--stage", "scientific",
                                      "--timeout", str(args.preflight_timeout)])
    call("capture_experiment51_environment.py", ["--root", root,
                                                  "--timeout", str(args.preflight_timeout)])
    for phase in ("smoke", "scientific"):
        call("run_experiment51.py", ["--root", root, "--phase", phase,
                                     "--lean-timeout", str(args.lean_timeout)])
    call("analyze_experiment51.py", ["--root", root])
    call("audit_experiment51.py", ["--root", root])
    if not args.no_export:
        extra = ["--root", root]
        if args.output:
            extra += ["--output", args.output]
        call("export_experiment51_bundle.py", extra)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    p.add_argument("--enumeration-workers", type=int, default=4)
    p.add_argument("--enumeration-timeout", type=int, default=7200)
    p.add_argument("--preflight-timeout", type=int, default=300)
    p.add_argument("--lean-timeout", type=int, default=900)
    p.add_argument("--output")
    p.add_argument("--no-export", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    main(parse_args())
