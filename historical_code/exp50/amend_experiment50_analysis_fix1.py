"""Exp50 analysis-only mechanical fix for raw endpoint container schemas.

The original immutable analysis compared the SHA-256 of the complete raw
endpoint JSON object.  Exp49 used schema ``exp49-raw-endpoint-v1`` while the
separately written Exp50 recorder used ``exp50-raw-endpoint-v1``.  Consequently
identical raw state bytes and endpoint metadata produced different container
hashes.  This amendment independently verifies every raw state and metadata
field, preserves the original failed analysis, and writes only to
``analysis_fix1``.  It never invokes Lean and never rewrites execution rows.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from experiment50_protocol import *

FIX_ID = "exp50-analysis-fix1-raw-container-schema-separation"
ORIGINAL_COUNTS = {"exp49_endpoint": 514, "exp49_authored": 96, "exp49_initial": 96}
FILE_HASH_CACHE: dict[str, str] = {}


def fail(message: str) -> None:
    raise ValueError(message)


def state_ref_ok(ref: dict[str, Any], expected_state: str) -> bool:
    path = Path(ref["path"])
    expected_sha = text_sha256(expected_state)
    key = str(path)
    if path.is_file() and key not in FILE_HASH_CACHE:
        FILE_HASH_CACHE[key] = file_sha256(path)
    return (ref.get("sha256") == expected_sha and path.is_file()
            and FILE_HASH_CACHE.get(key) == expected_sha
            and path.stat().st_size == int(ref["bytes"]))


def metadata_without_schema(endpoint: dict[str, Any]) -> dict[str, Any]:
    return {k: endpoint[k] for k in ("goal_count", "terminal")}


def archived_endpoint_ref_ok(recorded: dict[str, Any], archived: dict[str, Any]) -> bool:
    value = archived["value"]
    metadata = {k: v for k, v in value.items() if k != "state"}
    return (json_sha256(value) == archived["sha256"]
            and recorded["sha256"] == archived["sha256"]
            and recorded["metadata"] == metadata
            and state_ref_ok(recorded["state"], str(value["state"])))


def validate_endpoint(m0: dict[str, Any], archived: dict[str, Any],
                      direct_raw: dict[str, Any]) -> dict[str, Any]:
    if m0.get("executable") is not True or archived.get("executable") is not True:
        fail("validate_endpoint requires two executable branches")
    m0eps, oldeps = m0["endpoints"], archived["endpoints"]
    old_raw = oldeps["raw"]
    old_value = old_raw["value"]
    if old_value.get("schema") != "exp49-raw-endpoint-v1":
        fail("unexpected archived Exp49 raw schema")
    if json_sha256(old_value) != old_raw["sha256"]:
        fail("archived Exp49 raw endpoint self-hash failed")
    if direct_raw["raw_state_sha256"] != text_sha256(str(old_value["state"])):
        fail("Exp49 theorem row and direct raw worker state differ")
    if not state_ref_ok(m0eps["raw"]["state"], str(old_value["state"])):
        fail("Exp50 raw state content differs")
    if metadata_without_schema(m0eps["raw"]["metadata"]) != metadata_without_schema(old_value):
        fail("Exp50 raw endpoint metadata differs")
    exp50_value = dict(old_value)
    exp50_value["schema"] = "exp50-raw-endpoint-v1"
    if json_sha256(exp50_value) != m0eps["raw"]["sha256"]:
        fail("Exp50 raw container hash is not explained solely by its schema label")
    if not archived_endpoint_ref_ok(m0eps["text48"], oldeps["text48"]):
        fail("text48 endpoint differs")
    if not archived_endpoint_ref_ok(m0eps["struct"], oldeps["struct"]):
        fail("strict endpoint differs")
    if direct_raw["strict_state_sha256"] != m0eps["struct"]["state"]["sha256"]:
        fail("direct strict state differs")
    if (int(direct_raw["goal_count"]) != int(m0["goal_count"])
            or bool(direct_raw["terminal"]) != bool(m0["terminal"])):
        fail("direct raw endpoint metadata differs")
    return {
        "archived_raw_container_sha256": old_raw["sha256"],
        "exp50_raw_container_sha256": m0eps["raw"]["sha256"],
        "raw_state_sha256": m0eps["raw"]["state"]["sha256"],
        "text48_sha256": m0eps["text48"]["sha256"],
        "strict_sha256": m0eps["struct"]["sha256"],
    }


def direct_branch(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "executable": raw.get("executable") is True,
        "raw_state_sha256": text_sha256(str(raw.get("stateAfter"))),
        "strict_state_sha256": text_sha256(str(raw.get("strictStateAfter"))),
        "goal_count": raw.get("goalCount"), "terminal": raw.get("terminal"),
    }


def validate_root(root: Path, target: dict[str, Any]) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    m0p = root / "M0/theorems" / safe_slug(target["slug"]) / f"{target['rid']}.json"
    for path, expected in (
        (target["source_exp49_row"], target["source_exp49_row_sha256"]),
        (target["source_exp49_raw"], target["source_exp49_raw_sha256"]),
    ):
        if not Path(path).is_file() or file_sha256(path) != expected:
            fail(f"locked Exp49 evidence changed: {path}")
    m0 = read_json(m0p)
    if m0.get("worker_ok") is not True or m0.get("candidate_order") != target["alternatives"]:
        fail(f"M0 row is not frozen/evaluable: {target['theorem_id']}")

    raw49 = read_json(target["source_exp49_raw"])
    direct_candidates = {x["tactic"]: direct_branch(x) for x in raw49["alternatives"]}
    direct_authored = direct_branch(raw49["authored"])
    direct_initial = {
        "raw_state_sha256": text_sha256(str(raw49["stateBefore"])),
        "strict_state_sha256": text_sha256(str(raw49["strictStateBefore"])),
        "goal_count": raw49["preGoalCount"], "terminal": raw49["preGoalCount"] == 0,
    }
    del raw49

    archived = read_json(target["source_exp49_row"])
    old_candidates = {x["tactic"]: x for x in archived["worker"]["executions"]
                      if x["source"] == "alternative"}
    old_authored = next(x for x in archived["worker"]["executions"] if x["source"] == "authored")
    new_candidates = {x["tactic"]: x for x in m0["candidates"]}
    if set(new_candidates) != set(old_candidates) or set(new_candidates) != set(direct_candidates):
        fail("candidate identity changed")

    executable = 0
    schema_pairs: list[tuple[Any, ...]] = []
    for tactic in target["alternatives"]:
        new, old, direct = new_candidates[tactic], old_candidates[tactic], direct_candidates[tactic]
        if (new.get("executable") is True) != (old.get("executable") is True):
            fail("candidate status differs")
        if (new.get("executable") is True) != direct["executable"]:
            fail("candidate direct-raw status differs")
        if new.get("executable") is True:
            result = validate_endpoint(new, old, direct)
            executable += 1
            schema_pairs.append((target["slug"], target["theorem_id"], tactic,
                                 "exp49_endpoint", result["archived_raw_container_sha256"],
                                 result["exp50_raw_container_sha256"]))

    authored_result = validate_endpoint(m0["authored"], old_authored, direct_authored)
    schema_pairs.append((target["slug"], target["theorem_id"], target["authored_tactic"],
                         "exp49_authored", authored_result["archived_raw_container_sha256"],
                         authored_result["exp50_raw_container_sha256"]))

    old_initial = archived["worker"]["initial_endpoints"]
    new_initial = m0["initial_endpoints"]
    old_raw_value = old_initial["raw"]["value"]
    if old_raw_value.get("schema") != "exp49-raw-endpoint-v1":
        fail("unexpected initial raw schema")
    if json_sha256(old_raw_value) != old_initial["raw"]["sha256"]:
        fail("archived initial raw self-hash failed")
    if not state_ref_ok(new_initial["raw"]["state"], str(old_raw_value["state"])):
        fail("initial raw state differs")
    if direct_initial["raw_state_sha256"] != new_initial["raw"]["state"]["sha256"]:
        fail("direct initial raw state differs")
    if direct_initial["strict_state_sha256"] != new_initial["struct"]["state"]["sha256"]:
        fail("direct initial strict state differs")
    if not archived_endpoint_ref_ok(new_initial["text48"], old_initial["text48"]):
        fail("initial text48 differs")
    if not archived_endpoint_ref_ok(new_initial["struct"], old_initial["struct"]):
        fail("initial strict endpoint differs")
    relabeled_initial = dict(old_raw_value)
    relabeled_initial["schema"] = "exp50-raw-endpoint-v1"
    if json_sha256(relabeled_initial) != new_initial["raw"]["sha256"]:
        fail("initial raw hash is not explained solely by schema")
    schema_pairs.append((target["slug"], target["theorem_id"], None, "exp49_initial",
                         old_initial["raw"]["sha256"], new_initial["raw"]["sha256"]))
    return ({"slug": target["slug"], "theorem_id": target["theorem_id"],
             "full_name": target["full_name"], "candidate_attempts": len(new_candidates),
             "executable_candidates": executable, "candidate_status_exact": True,
             "raw_state_and_metadata_exact": True, "text48_exact": True,
             "strict_exact": True, "authored_exact": True, "initial_exact": True,
             "schema_only_container_differences": executable + 2}, schema_pairs)


def ledger_pair(row: dict[str, Any]) -> tuple[Any, ...]:
    category = row["category"]
    if category in ("exp49_endpoint", "exp49_initial"):
        expected, observed = row["expected"]["raw"], row["observed"]["raw"]
    elif category == "exp49_authored":
        expected, observed = row["expected"][1]["raw"], row["observed"][1]["raw"]
    else:
        fail(f"unexpected original mismatch category: {category}")
    return (row["slug"], row["theorem_id"], row.get("tactic"), category, expected, observed)


def amend(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    cfgp = root / "frozen/experiment50_config.json"
    targetsp = root / "frozen/targets.json"
    original_summaryp = root / "analysis/summary.json"
    original_ledgerp = root / "analysis/mismatch_ledger.jsonl"
    for path in (cfgp, targetsp, original_summaryp, original_ledgerp):
        if not path.is_file():
            raise FileNotFoundError(path)
    cfg, targets, original = read_json(cfgp), read_json(targetsp), read_json(original_summaryp)
    validate_code_lock(cfg["code_lock"])
    if original.get("reexecution_pass") is not False or original.get("mismatch_count") != 706:
        fail("analysis-fix1 applies only to the preserved 706-mismatch original analysis")
    required_original_checks = {
        "M0_96_evaluable": True, "M0_exact_exp48_aggregates": True,
        "M1_M4_384_roots_exact_M0": True,
        "M5_96_roots_2208_processes_exact_M0": True,
        "manual_reconciliation_zero": True,
    }
    if any(original["checks"].get(k) is not v for k, v in required_original_checks.items()):
        fail("original non-raw checks did not pass")
    outdir = root / "analysis_fix1"
    summaryp = outdir / "summary.json"
    amendmentp = outdir / "amendment.json"
    script_sha = file_sha256(Path(__file__))
    if summaryp.exists():
        amendment = read_json(amendmentp)
        if amendment.get("fix_script_sha256") != script_sha:
            fail("analysis-fix1 script changed after amendment")
        value = read_json(summaryp)
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return value

    ledger = [json.loads(line) for line in original_ledgerp.read_text(encoding="utf-8").splitlines()
              if line.strip()]
    if Counter(x["category"] for x in ledger) != Counter(ORIGINAL_COUNTS):
        fail("original mismatch category inventory changed")

    root_rows, computed_pairs = [], []
    for index, target in enumerate(targets, 1):
        print(f"EXP50-ANALYSIS-FIX1 {index}/{len(targets)} {target['slug']} {target['full_name']}",
              flush=True)
        row, pairs = validate_root(root, target)
        root_rows.append(row)
        computed_pairs.extend(pairs)
    observed_pairs = [ledger_pair(x) for x in ledger]
    if Counter(observed_pairs) != Counter(computed_pairs):
        fail("original ledger is not exactly the independently reconstructed schema-only inventory")

    executable = sum(x["executable_candidates"] for x in root_rows)
    checks = {
        "original_analysis_preserved_and_hashed": True,
        "original_706_mismatches_exactly_reconstructed": len(computed_pairs) == 706,
        "original_mismatch_categories_exact": Counter(x[3] for x in computed_pairs) == Counter(ORIGINAL_COUNTS),
        "all_2208_candidate_statuses_exact": sum(x["candidate_attempts"] for x in root_rows) == 2208,
        "all_514_executable_raw_states_and_metadata_exact": executable == 514,
        "all_514_text48_endpoints_exact": executable == 514,
        "all_514_strict_endpoints_exact": executable == 514,
        "all_96_authored_endpoints_exact": len(root_rows) == 96,
        "all_96_initial_endpoints_exact": len(root_rows) == 96,
        "raw_container_difference_explained_only_by_schema_label": True,
        "M1_M4_exact_M0_preserved": original["checks"]["M1_M4_384_roots_exact_M0"],
        "M5_exact_M0_preserved": original["checks"]["M5_96_roots_2208_processes_exact_M0"],
        "Exp48_aggregate_reconstruction_preserved": original["checks"]["M0_exact_exp48_aggregates"],
        "manual_reconciliation_zero": original.get("manual_reconciliation_count") == 0,
    }
    corrected_checks = dict(original["checks"])
    corrected_checks.update({
        "M0_exact_exp48_status_text_and_theorem_rows": True,
        "M0_exact_exp49_raw_text_strict": True,
        "zero_mismatches": True,
    })
    agreements = json.loads(json.dumps(original["agreement_counts"]))
    agreements["M0_vs_archived_Exp49"]["raw_endpoint_equal"] = executable
    amendment = {
        "version": 1, "protocol_version": PROTOCOL_VERSION, "fix_id": FIX_ID,
        "fix_script": str(Path(__file__).resolve()), "fix_script_sha256": script_sha,
        "original_analysis_summary": str(original_summaryp),
        "original_analysis_summary_sha256": file_sha256(original_summaryp),
        "original_mismatch_ledger": str(original_ledgerp),
        "original_mismatch_ledger_sha256": file_sha256(original_ledgerp),
        "original_mismatch_count": 706,
        "mechanical_cause": "raw endpoint container schema tag differed: exp49-raw-endpoint-v1 versus exp50-raw-endpoint-v1",
        "correction": "compare raw ordered state bytes, goal_count, and terminal; validate each recorder's container self-hash separately",
        "execution_rows_modified": 0, "lean_processes_executed": 0,
        "scientific_values_modified": 0, "manual_reconciliation_count": 0,
        "checks": checks,
    }
    value = {
        "version": 1, "protocol_version": PROTOCOL_VERSION, "fix_id": FIX_ID,
        "study_role": original["study_role"],
        "analysis_status": "versioned mechanical analysis amendment",
        "original_failed_analysis_preserved": True,
        "original_mismatch_count": 706,
        "superseded_schema_only_container_hash_mismatches": 706,
        "mismatch_count": 0, "manual_reconciliation_count": 0,
        "roots": len(root_rows), "candidates_per_root": 23,
        "executable_candidates": executable,
        "raw_endpoint_content_definition": ["ordered raw state bytes", "goal_count", "terminal"],
        "raw_serializer_schema_tag_is_metadata_not_endpoint_content": True,
        "amendment_checks": checks, "checks": corrected_checks,
        "agreement_counts_content_based_raw": agreements,
        "root_level_complete_agreement": {"M0_source": 96, "M1": 96, "M2": 96,
                                            "M3": 96, "M4": 96, "M5": 96},
        "repository_level_complete_agreement": {slug: True for slug in cfg["repositories"]},
        "reconstructed_exp48": original["reconstructed_exp48"],
        "archived_exp48_confirmation_go_preserved": original["archived_exp48_confirmation_go_preserved"],
        "analysis_fix1_pass": all(checks.values()),
        "reexecution_pass": all(checks.values()) and all(corrected_checks.values()),
        "independence_limit": original["independence_limit"],
        "claim_boundary": cfg["claim_boundary"],
    }
    value["next_step"] = "Export the versioned Exp50 fix1 audit bundle." if value["reexecution_pass"] else "STOP."
    atomic_jsonl_dump(root_rows, outdir / "raw_content_comparisons.jsonl")
    atomic_jsonl_dump([], outdir / "mismatch_ledger.jsonl")
    atomic_json_dump(amendment, amendmentp)
    atomic_json_dump(value, summaryp)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ARTIFACT_ROOT))
    return p.parse_args()


if __name__ == "__main__":
    result = amend(parse_args())
    raise SystemExit(0 if result.get("reexecution_pass") else 2)
