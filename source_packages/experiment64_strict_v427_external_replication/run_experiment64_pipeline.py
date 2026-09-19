"""Run the complete freeze -> execute -> analyze -> audit -> export Exp64 pipeline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiment64_protocol import *
import analyze_experiment64
import audit_experiment64
import export_experiment64
import freeze_experiment64
import run_experiment64


def run(args: argparse.Namespace) -> dict:
    root = Path(args.artifact_root).resolve()
    source = Path(args.source_exp63_root).resolve()
    output = Path(args.output).resolve()
    print("EXP64-PHASE freeze", flush=True)
    freeze_experiment64.run(root, source)
    print("EXP64-PHASE scientific", flush=True)
    execution_args = argparse.Namespace(
        artifact_root=str(root), git_timeout=args.git_timeout,
        build_timeout=args.build_timeout, trace_timeout=args.trace_timeout,
        enumeration_timeout=args.enumeration_timeout, lean_timeout=args.lean_timeout,
        threads=args.threads,
    )
    run_experiment64.run(execution_args)
    print("EXP64-PHASE analysis", flush=True)
    analyze_experiment64.analyze(argparse.Namespace(artifact_root=str(root)))
    print("EXP64-PHASE audit", flush=True)
    audit_experiment64.run(root)
    print("EXP64-PHASE export", flush=True)
    return export_experiment64.run(root, output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    parser.add_argument("--source-exp63-root", default=str(SOURCE_EXP63_ROOT))
    parser.add_argument(
        "--output",
        default=str(MZX_ROOT / "exports/experiment64_strict_v427_external_replication_results.zip"),
    )
    parser.add_argument("--git-timeout", type=int, default=1800)
    parser.add_argument("--build-timeout", type=int, default=14400)
    parser.add_argument("--trace-timeout", type=int, default=14400)
    parser.add_argument("--enumeration-timeout", type=int, default=7200)
    parser.add_argument("--lean-timeout", type=int, default=1200)
    parser.add_argument("--threads", type=int, default=2)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), ensure_ascii=False, indent=2))
