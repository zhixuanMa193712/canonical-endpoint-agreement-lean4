"""Static and source-diff tests for the pre-probe Exp52 Fix4 package."""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
SERVER_ROOT = PACKAGE.parent
sys.path.insert(0, str(PACKAGE))

import alignment_protocol as protocol  # noqa: E402
import experiment52_live_worker as worker  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    tests = 0

    check(
        protocol.EXECUTION_ALIGNMENT_VERSION
        == "experiment52-pre-probe-compile-compatibility-fix4",
        "wrong Fix4 alignment version",
    )
    check(
        protocol.EXECUTION_FIX_ID
        == "exp52-pre-probe-fix4-lean-exception-message-rendering",
        "wrong Fix4 mechanical identity",
    )
    tests += 1

    old_fragment = """                catch ex =>
                  pure (failedStep (toString ex))"""
    new_fragment = """                catch ex =>
                  let message ← liftM (m := BaseIO) ex.toMessageData.toString
                  pure (failedStep message)"""
    check(new_fragment in worker.LEAN_SOURCE, "fixed Exception renderer missing")
    check(old_fragment not in worker.LEAN_SOURCE, "unsupported renderer remains")
    reconstructed_fix3 = worker.LEAN_SOURCE.replace(new_fragment, old_fragment)
    check(
        hashlib.sha256(reconstructed_fix3.encode("utf-8")).hexdigest()
        == protocol.SOURCE_FIX3_EXP52_LEAN_SOURCE_SHA256,
        "Fix4 generated Lean source has changes outside the one locked site",
    )
    check(
        worker.LEAN_SOURCE_SHA256
        == protocol.FIX4_EXP52_LEAN_SOURCE_SHA256,
        "Fix4 generated Lean source anchor changed",
    )
    check(
        worker.LEAN_SOURCE.count("toMessageData.toString") == 1,
        "wrong number of Exception rendering changes",
    )
    tests += 1

    check(
        protocol.EXP52_FAILED_FIX3_PREFLIGHT_RELATIVE
        != protocol.EXP52_PREFLIGHT_RELATIVE,
        "Fix4 would overwrite the failed Fix3 preflight",
    )
    check(
        str(protocol.EXP52_FAILED_FIX3_PREFLIGHT_RELATIVE)
        == "exp52/preflight/worker_compile.json",
        "failed Fix3 preflight path changed",
    )
    check(
        str(protocol.EXP52_PREFLIGHT_RELATIVE)
        == "exp52/preflight/worker_compile_fix4.json",
        "Fix4 preflight path changed",
    )
    tests += 1

    for name in (
        "experiment52_live_worker.py", "preflight_exp52_execution.py",
        "run_exp52_shards.py", "finalize_exp52_execution.py",
        "analyze_exp52.py", "audit_exp52.py", "export_exp52_bundle.py",
        "freeze_exp52_compile_fix4.py", "alignment_protocol.py",
    ):
        ast.parse((PACKAGE / name).read_text(encoding="utf-8"), filename=name)
    tests += 1

    runner = (PACKAGE / "run_exp52_shards.py").read_text(encoding="utf-8")
    finalizer = (PACKAGE / "finalize_exp52_execution.py").read_text(
        encoding="utf-8"
    )
    preflight = (PACKAGE / "preflight_exp52_execution.py").read_text(
        encoding="utf-8"
    )
    check("EXP52_PREFLIGHT_RELATIVE" in runner, "runner does not require Fix4 preflight")
    check("EXP52_PREFLIGHT_RELATIVE" in finalizer, "finalizer does not bind Fix4 preflight")
    check("outp = root / EXP52_PREFLIGHT_RELATIVE" in preflight,
          "preflight does not preserve the old receipt")
    check("source_fix3_amendment_sha256" in runner,
          "runner does not distinguish selection lineage")
    tests += 1

    all_python = "\n".join(
        path.read_text(encoding="utf-8") for path in PACKAGE.glob("*.py")
        if path.name != Path(__file__).name
    )
    check("import experiment48" not in all_python, "Exp48 runner import found")
    check("import experiment49" not in all_python, "Exp49 runner import found")
    check("import experiment50" not in all_python, "Exp50 runner import found")
    tests += 1

    freeze = (PACKAGE / "freeze_exp52_compile_fix4.py").read_text(
        encoding="utf-8"
    )
    check("continuation_probes_executed_before_amendment\": 0" in freeze,
          "pre-probe boundary missing")
    check("probe_panel_changed\": False" in freeze, "probe panel boundary missing")
    check("statistics_changed\": False" in freeze, "statistics boundary missing")
    check("decision_thresholds_changed\": False" in freeze,
          "threshold boundary missing")
    tests += 1

    manifestp = PACKAGE / "PACKAGE_MANIFEST.json"
    if manifestp.is_file():
        manifest = json.loads(manifestp.read_text(encoding="utf-8"))
        entries = manifest["files"]
        check(
            manifest.get("files_sha256") == protocol.json_sha256(entries),
            "package manifest identity changed",
        )
        for entry in entries:
            path = PACKAGE / entry["path"]
            check(path.is_file(), f"missing package file: {path}")
            check(path.stat().st_size == entry["bytes"], f"size changed: {path}")
            check(sha256(path) == entry["sha256"], f"hash changed: {path}")
        tests += 1

    print(json.dumps({
        "version": 1,
        "package": protocol.EXECUTION_ALIGNMENT_VERSION,
        "tests": tests,
        "all_static_tests_passed": True,
        "fix3_lean_source_sha256": (
            protocol.SOURCE_FIX3_EXP52_LEAN_SOURCE_SHA256
        ),
        "fix4_lean_source_sha256": worker.LEAN_SOURCE_SHA256,
        "generated_lean_change_sites": 1,
        "lean_executed": False,
        "theorem_sources_elaborated": 0,
        "candidate_tactics_executed": 0,
        "continuation_probes_executed": 0,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
