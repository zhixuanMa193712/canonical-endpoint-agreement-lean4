"""Exp48 preflight Fix1 worker.

Mechanical pre-science patch only:
the frozen Exp48 Lean source used the unavailable Lean-v4.27 constant
`System.FilePath.toAbsolute`.  The already qualified Exp47 Fix4 runner passed
the source FilePath directly.  This wrapper preserves every other byte of the
frozen Exp48 Lean worker source and changes exactly that one expression.

The original frozen experiment48_live_tacticinfo_worker.py is never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json

import experiment48_live_tacticinfo_worker as frozen

FIX_ID = "experiment48-live-worker-filepath-v427-fix1"
OLD_FRAGMENT = "processFile (← System.FilePath.toAbsolute ⟨path⟩) p e ⟨output⟩ candidates"
NEW_FRAGMENT = "processFile ⟨path⟩ p e ⟨output⟩ candidates"

if frozen.LEAN_SOURCE.count(OLD_FRAGMENT) != 1:
    raise RuntimeError("Exp48 Fix1 expected exactly one frozen FilePath.toAbsolute call")

LEAN_SOURCE = frozen.LEAN_SOURCE.replace(OLD_FRAGMENT, NEW_FRAGMENT, 1)
if OLD_FRAGMENT in LEAN_SOURCE:
    raise RuntimeError("Exp48 Fix1 failed to remove frozen unsupported FilePath call")
if LEAN_SOURCE.count(NEW_FRAGMENT) != 1:
    raise RuntimeError("Exp48 Fix1 replacement is not unique")

LEAN_SOURCE_SHA256 = hashlib.sha256(LEAN_SOURCE.encode("utf-8")).hexdigest()
LEAN_FILE_NAME = "Experiment48LiveTacticInfoWorkerFix1.lean"
WORKER_VERSION = frozen.WORKER_VERSION + "-filepath-v427-fix1"


def source_delta_contract() -> dict[str, object]:
    """Machine-auditable proof that only one literal fragment changed."""
    restored = LEAN_SOURCE.replace(NEW_FRAGMENT, OLD_FRAGMENT, 1)
    return {
        "fix_id": FIX_ID,
        "old_fragment_count_frozen": frozen.LEAN_SOURCE.count(OLD_FRAGMENT),
        "new_fragment_count_fixed": LEAN_SOURCE.count(NEW_FRAGMENT),
        "old_fragment_absent_fixed": OLD_FRAGMENT not in LEAN_SOURCE,
        "reverse_replacement_exact_frozen": restored == frozen.LEAN_SOURCE,
        "frozen_lean_source_sha256": frozen.LEAN_SOURCE_SHA256,
        "fixed_lean_source_sha256": LEAN_SOURCE_SHA256,
    }


def run(args: argparse.Namespace) -> dict:
    # Patch only the in-memory constants used by frozen.run().  The frozen file
    # remains unchanged, so its code-lock continues to validate.
    old_source = frozen.LEAN_SOURCE
    old_sha = frozen.LEAN_SOURCE_SHA256
    old_name = frozen.LEAN_FILE_NAME
    old_version = frozen.WORKER_VERSION
    try:
        frozen.LEAN_SOURCE = LEAN_SOURCE
        frozen.LEAN_SOURCE_SHA256 = LEAN_SOURCE_SHA256
        frozen.LEAN_FILE_NAME = LEAN_FILE_NAME
        frozen.WORKER_VERSION = WORKER_VERSION
        value = frozen.run(args)
        value["mechanical_fix"] = source_delta_contract()
        # Re-write through the frozen protocol helper so the persisted worker
        # row includes the amendment identity.
        frozen.atomic_json_dump(value, args.output)
        return value
    finally:
        frozen.LEAN_SOURCE = old_source
        frozen.LEAN_SOURCE_SHA256 = old_sha
        frozen.LEAN_FILE_NAME = old_name
        frozen.WORKER_VERSION = old_version


def parse_args() -> argparse.Namespace:
    return frozen.parse_args()


if __name__ == "__main__":
    result = run(parse_args())
    print(json.dumps({
        "worker_ok": result.get("worker_ok"),
        "theorem_start_ok": result.get("theorem_start_ok"),
        "authored_replay_ok": result.get("authored_replay_ok"),
        "complete_alternative_budget": result.get("complete_alternative_budget"),
        "full_name": result.get("full_name"),
        "mechanical_fix": FIX_ID,
    }, ensure_ascii=False))
