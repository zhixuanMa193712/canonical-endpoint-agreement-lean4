"""Static and archive-only tests; never invoke Lean."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from experiment54_live_worker import LEAN_SOURCE, LEAN_SOURCE_SHA256
from experiment54_protocol import *


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run(args: argparse.Namespace) -> dict[str, object]:
    checks = 0
    check(
        EXECUTION_VERSION == "experiment54-effect-aware-depth2-microbenchmark-fix3",
        "Fix3 execution version",
    ); checks += 1
    check(
        MECHANICAL_FIX_ID
        == "exp54-fix3-runtime-heartbeat-exception-boundary",
        "Fix3 identity",
    ); checks += 1
    check(EXPECTED_ROOTS == 16, "root count"); checks += 1
    check(EXPECTED_PAIRS == 32, "pair count"); checks += 1
    check(EXPECTED_FULL_CELLS == 512, "full calls"); checks += 1
    check(EXPECTED_DEDUP_CELLS == 384, "dedup calls"); checks += 1
    check(EXPECTED_CELLS == 896, "total calls"); checks += 1
    check(len(PROBES) == 8 and len(set(PROBES)) == 8, "probe panel"); checks += 1
    check(hashlib.sha256(LEAN_SOURCE.encode()).hexdigest() == LEAN_SOURCE_SHA256,
          "Lean source SHA"); checks += 1
    check("ContextInfo" in LEAN_SOURCE and "mctxBefore" in LEAN_SOURCE
          and "goalsBefore" in LEAN_SOURCE, "live state mechanism"); checks += 1
    check("candidateRaw == expectedRaw" in LEAN_SOURCE
          and "candidateStruct == expectedStruct" in LEAN_SOURCE,
          "exact candidate checkpoint"); checks += 1
    check("Tactic.evalTactic probeStx" in LEAN_SOURCE, "downstream probe"); checks += 1
    check(
        "ctx.options.setNat `maxHeartbeats 2000000" in LEAN_SOURCE,
        "ContextInfo heartbeat option override",
    ); checks += 1
    check(
        "let probeResult : Step ← tryCatchRuntimeEx" in LEAN_SOURCE
        and "(withCurrHeartbeats do" in LEAN_SOURCE,
        "isolated downstream probe heartbeat budget",
    ); checks += 1
    check(
        "ex.toMessageData.toString" not in LEAN_SOURCE
        and 'pure (failedStep "tactic execution failed")' in LEAN_SOURCE,
        "heartbeat-safe probe exception recording",
    ); checks += 1
    check(
        "CoreM deliberately lets resource-limit exceptions escape" in LEAN_SOURCE
        and "catch _ =>" not in LEAN_SOURCE,
        "runtime heartbeat exception boundary",
    ); checks += 1
    check(
        normalize_goal_text("  x   : Nat\n\n⊢ ?m.123 = x✝7  ")
        == "x : Nat\n⊢ <GEN> = x<GEN>",
        "exact Exp49 text normalization",
    ); checks += 1
    worker_source = (
        Path(__file__).resolve().parent / "experiment54_live_worker.py"
    ).read_text(encoding="utf-8")
    check(
        'int(candidate_raw.get("goalCount", -1))' not in worker_source
        and "candidate_ready = bool(" in worker_source,
        "null-safe candidate result handling",
    ); checks += 1
    check(file_sha256(args.source_archive) == SOURCE_EXP49_SHA256,
          "source Exp49 archive SHA"); checks += 1
    design_path = Path(args.artifact_root) / "frozen/design.json"
    if design_path.is_file():
        frozen = load_freeze(Path(args.artifact_root))
        cells = read_jsonl(frozen["cells_path"])
        pairs = read_jsonl(frozen["pairs_path"])
        check(len(cells) == EXPECTED_CELLS, "frozen cell accounting"); checks += 1
        check(len(pairs) == EXPECTED_PAIRS, "frozen pair accounting"); checks += 1
        check(sum(c["policy"] == "full" for c in cells) == 512,
              "frozen full cells"); checks += 1
        check(sum(c["policy"] == "dedup" for c in cells) == 384,
              "frozen dedup cells"); checks += 1
        for pair in pairs:
            left = pair["left_branch"]["endpoints"]["struct"]["sha256"]
            right = pair["right_branch"]["endpoints"]["struct"]["sha256"]
            check((left == right) == (pair["role"] == "witness"),
                  "pair role endpoint relation")
        checks += 1
    value = {
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "execution_version": EXECUTION_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "static_checks": checks,
        "all_static_checks_passed": True,
        "lean_executed": False,
        "theorem_sources_elaborated": 0,
        "scientific_candidates_executed": 0,
        "downstream_probes_executed": 0,
    }
    print(json.dumps(value, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--artifact-root", default=str(artifact_root()))
    p.add_argument("--source-archive", default=str(source_archive()))
    return p.parse_args()


if __name__ == "__main__":
    run(parse_args())
