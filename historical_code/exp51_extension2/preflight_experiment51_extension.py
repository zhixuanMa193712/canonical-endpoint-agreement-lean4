"""Zero-candidate preflights for Exp51 repository-frame extension 2."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

from experiment51_extension_protocol import *
from experiment51_repository_frame_extension import (  # noqa: E402
    preflight_experiment51_extension as implementation,
)


def preflight(args):
    root = Path(args.root).resolve()
    _, _, config_sha = implementation.config_receipt(root)
    with contextlib.redirect_stdout(io.StringIO()):
        if args.stage == "environment":
            rows = validate_base_carry_forward()
            checked = validate_active_carry_checkouts(rows)
            value = implementation.environment_preflight(root, config_sha)
            value["active_carry_checkouts"] = checked
            value["all_active_carry_checkouts_exact"] = (
                len(checked) == len(CARRY_FORWARD_SLUGS)
            )
            value["environment_gate"] = bool(
                value.get("environment_gate") is True
                and value["all_active_carry_checkouts_exact"]
            )
            value["next_step"] = (
                "Carry forward eleven archive-exact zero-candidate qualification passes."
                if value["environment_gate"]
                else "STOP before carry-forward or new repository checkout."
            )
            outp = root / "preflight/environment.json"
        elif args.stage == "offline-parser-control":
            value = implementation.offline_parser_control(root, config_sha, args.timeout)
            value["next_step"] = (
                "Run frozen zero-candidate build/trace screening for all seven Extension2 repositories."
                if value.get("control_gate") is True
                else "STOP before any new repository trace."
            )
            outp = root / "preflight/offline_parser_control.json"
        else:
            value = implementation.screening_worker_preflight(
                root, config_sha, args.timeout
            )
            outp = root / "preflight/screening_worker_compile.json"
    atomic_json_dump(value, outp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


if __name__ == "__main__":
    result = preflight(implementation.parse_args())
    gate = (
        result.get("environment_gate")
        if result.get("stage") == "environment"
        else result.get("control_gate")
        if result.get("stage") == "offline-parser-control"
        else result.get("compile_ok")
    )
    raise SystemExit(0 if gate is True else 2)
