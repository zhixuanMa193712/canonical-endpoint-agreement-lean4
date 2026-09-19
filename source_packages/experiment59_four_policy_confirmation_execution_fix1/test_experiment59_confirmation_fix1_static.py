"""Zero-Lean static checks for Exp59 confirmation operational Fix1."""
from __future__ import annotations

import ast
import json

from experiment59_confirmation_fix1_protocol import *


REQUIRED = {
    "experiment59_confirmation_fix1_protocol.py",
    "freeze_operational_anomaly_fix1.py",
    "finalize_experiment59_confirmation_fix1.py",
    "analyze_experiment59_confirmation_fix1.py",
    "audit_experiment59_confirmation_fix1.py",
    "export_experiment59_confirmation_fix1.py",
    "test_experiment59_confirmation_fix1_static.py",
    "build_experiment59_confirmation_fix1_package.py",
    "README_FIX1_SERVER.md",
    "EXP59_CONFIRMATION_OPERATIONAL_ANOMALY_FIX1.md",
}

# Hashes from the immutable source package manifest.  The copied source files
# are deliberately retained byte-for-byte so the execution-design
# implementation locks continue to validate on the server.
SOURCE_LOCKS = {
    "EXP59_CONFIRMATION_AMENDMENT.md": "2e7a85a3b1982b6eed8e698292358a45db227bd5a6e62ba04b3f7642fa1b159d",
    "README_SERVER.md": "7139d509c4ed4e2638947cf8e440366cbbd0213764449ded0ae423579cd49edf",
    "analyze_experiment59_confirmation.py": "e6a072a83c54b471717d56b3977b31dc5926e8eb8bc29e0a05a1491447ee5fe2",
    "audit_experiment59_confirmation.py": "68cd5ff5b2c44eae3843376e17f98ab8c4132faaa3fd76735ff6d9825694aa65",
    "build_experiment59_confirmation_package.py": "1bb5fcfcae88eea433c5715eac278518b43ad2111fe0f7ae17e838164081755a",
    "experiment59_confirmation_live_worker.py": "4ed511c669a0d06688b39ad1db79b82e10949a6f3e3dcde35e3cd43f3a6a059d",
    "experiment59_confirmation_protocol.py": "042b796924765a2d49229658dc8c8e58c74385f82e575b385c48050bfbb3b412",
    "export_experiment59_confirmation.py": "ff19718f536360e75b08f939b349668a678ebe39070f77493c1417d699664a05",
    "finalize_experiment59_confirmation.py": "f36c93ec53c847ecb1a7390a37d7c75fc5f169afb2b450749818928a9eb1b870",
    "freeze_experiment59_confirmation_execution.py": "ea47c072f1f279cd0a8cecac3994b73852603803791550add984b294421f91f9",
    "launch_experiment59_confirmation.py": "abcd0b4542af9a8e373fd4dedfce24ed49768217501ffd7128f3c4bc3426e93e",
    "monitor_experiment59_confirmation.py": "41905c763384f929c7a77dc94aa5180a1cc013e3c485a0cf838278fedc3f2400",
    "preflight_experiment59_confirmation.py": "251a374b8e77c9a5c63f45afb005acc37fd8846f1324a6be0c36cb6ddf0697fb",
    "run_experiment59_confirmation_shards.py": "424faad5975176adc36a161d1b75a3a1819930dc5da13c9434640227854bda23",
    "test_experiment59_confirmation_static.py": "dba0bf9bf4abf136129b9ef2fc2b8f6ed26eeecf3d36e3b05fd726bcd41c7ae6",
}


def check(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def run() -> dict:
    count = 0
    names = {path.name for path in PACKAGE_ROOT.iterdir() if path.is_file()}
    check(REQUIRED <= names, "Fix1 package incomplete")
    count += 1

    for path in PACKAGE_ROOT.glob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    count += 1

    for name, expected in SOURCE_LOCKS.items():
        check(file_sha256(PACKAGE_ROOT / name) == expected, f"source changed: {name}")
    count += 1

    check(FIX1_VERSION == 1, "Fix1 version changed")
    count += 1
    check(len(ANOMALY_LOCKS) == 3, "locked anomaly count changed")
    count += 1
    check(len(ANOMALY_BY_JOB) == 3 and len(ANOMALY_BY_CELL) == 3,
          "locked anomaly identity is not unique")
    count += 1
    check({row["policy"] for row in ANOMALY_LOCKS}
          == {"full", "effect_aware", "head_dedup"},
          "affected policies changed")
    count += 1
    check({row["job_id"] for row in ANOMALY_LOCKS} == {
        "53a8edc7136583763fd718e2",
        "683acceb2a8d879d8959d9cf",
        "bf36335f1908152b5bcc1a54",
    }, "locked job IDs changed")
    count += 1
    check({row["cell_id"] for row in ANOMALY_LOCKS} == {
        "6be77822b87c8eb2fed9ea3a",
        "3504b88c806e0f0cad101c81",
        "6518c20db28d368af653a7cf",
    }, "locked cell IDs changed")
    count += 1
    check(AFFECTED_TARGET_ID == "b3ef16b88207962858403285",
          "affected target changed")
    count += 1
    check(AFFECTED_CANDIDATE_TACTIC == "simp_all" and AFFECTED_PROBE == "omega",
          "affected tactic/probe changed")
    count += 1
    check(PANIC_STDERR_SHA256
          == "aade23fe7e645ed081eca9d66b8aad233ff8862aaa483cecda98bbb99db73f2d",
          "panic message hash changed")
    count += 1
    check(EXPECTED_ROOTS == 64 and EXPECTED_JOBS == 256,
          "registered sample size changed")
    count += 1
    check(POLICIES == ("full", "effect_aware", "head_dedup", "fixed_budget_random"),
          "registered policies changed")
    count += 1

    postexecution = [
        PACKAGE_ROOT / "freeze_operational_anomaly_fix1.py",
        PACKAGE_ROOT / "finalize_experiment59_confirmation_fix1.py",
        PACKAGE_ROOT / "analyze_experiment59_confirmation_fix1.py",
        PACKAGE_ROOT / "audit_experiment59_confirmation_fix1.py",
        PACKAGE_ROOT / "export_experiment59_confirmation_fix1.py",
    ]
    check(not any("subprocess" in path.read_text(encoding="utf-8")
                  for path in postexecution),
          "post-execution Fix1 must not launch a process")
    count += 1
    check(not any("execute_cell" in path.read_text(encoding="utf-8")
                  for path in postexecution),
          "post-execution Fix1 must not execute a cell")
    count += 1

    freeze = (PACKAGE_ROOT / "freeze_operational_anomaly_fix1.py").read_text()
    check("analysis_absent_before_amendment" in freeze
          and "original_receipts_rewritten\": False" in freeze,
          "amendment timing or immutability gate missing")
    count += 1
    analysis = (PACKAGE_ROOT / "analyze_experiment59_confirmation_fix1.py").read_text()
    check("registered_one_sided_95_upper\": None" in analysis
          and "registered_coverage_gate\": False" in analysis,
          "coverage fail-closed fields missing")
    count += 1
    check("nonregistered_complete_case_one_sided_95_upper" in analysis,
          "complete-case sensitivity label missing")
    count += 1
    check("efficiency_and_coverage_are_separate_estimands" in analysis,
          "efficiency and coverage are not separated")
    count += 1
    audit = (PACKAGE_ROOT / "audit_experiment59_confirmation_fix1.py").read_text()
    check("exact_three_locked_panics" in audit
          and "registered_coverage_remains_inconclusive" in audit,
          "independent anomaly audit incomplete")
    count += 1

    return {
        "version": FIX1_VERSION,
        "package": "experiment59-four-policy-confirmation-operational-fix1",
        "fix1_protocol_version": FIX1_PROTOCOL_VERSION,
        "mechanical_fix_id": FIX1_MECHANICAL_ID,
        "static_checks": count,
        "source_files_hash_locked": len(SOURCE_LOCKS),
        "locked_operational_anomaly_cells": 3,
        "coverage_unevaluable_roots": 1,
        "all_static_checks_passed": True,
        "lean_executed": False,
        "theorem_sources_elaborated": 0,
        "confirmation_cells_executed": 0,
        "continuation_probes_executed": 0,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
