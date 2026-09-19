"""Pure-Python/static verification for the Exp51/52 Fix3 package.

This test imports definitions and inspects frozen source text only.  It does
not invoke Lean, elaborate theorem sources, or execute a candidate/probe.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import alignment_protocol as protocol
import analyze_exp52
import audit_exp52
import experiment52_live_worker
import run_exp52_shards
import select_exp52_pairs


PACKAGE_ROOT = Path(__file__).resolve().parent
SERVER_ROOT = PACKAGE_ROOT.parent


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_constants_and_portable_document_lock() -> None:
    assert protocol.EXP51_SHARD_COUNT == 16
    assert protocol.EXP52_SHARD_COUNT == 32
    assert protocol.TARGET_REPOSITORIES == 12
    assert protocol.TARGET_ROOTS == 576
    assert protocol.ROOTS_PER_REPOSITORY == 48
    assert protocol.CANDIDATES_PER_ROOT == 23
    assert protocol.LEAN_TIMEOUT_SECONDS == 900
    lock = protocol.portable_document_lock()
    assert lock["schema"] == "exp52-portable-document-content-lock-v1"
    assert len(lock["files"]) == 2
    assert lock["bundle_sha256"] == protocol.json_sha256(lock["files"])


def test_exp51_shards_are_disjoint_and_complete() -> None:
    targets = [{"theorem_id": f"root-{index}"} for index in range(576)]
    assignments = [
        protocol.targets_for_shard(targets, shard, 16) for shard in range(16)
    ]
    assert all(len(rows) == 36 for rows in assignments)
    flattened = [row["theorem_id"] for rows in assignments for row in rows]
    assert len(flattened) == len(set(flattened)) == 576
    assert set(flattened) == {row["theorem_id"] for row in targets}


def test_exp52_shard_function_is_total() -> None:
    for cell_count in (0, 1, 31, 32, 33, 576, 20736):
        buckets = [[] for _ in range(protocol.EXP52_SHARD_COUNT)]
        for index in range(cell_count):
            buckets[protocol.shard_index(index, protocol.EXP52_SHARD_COUNT)].append(
                index
            )
        flattened = [index for bucket in buckets for index in bucket]
        assert len(flattened) == len(set(flattened)) == cell_count
        assert set(flattened) == set(range(cell_count))


def test_utf8_pair_order_and_audit_size() -> None:
    left = {"head": "zeta", "tactic": "simp", "candidate_position_frozen": 3}
    right = {"head": "aesop", "tactic": "aesop", "candidate_position_frozen": 8}
    ordered_left, ordered_right = protocol.ordered_pair(left, right)
    assert protocol.candidate_key(ordered_left) < protocol.candidate_key(ordered_right)
    assert {ordered_left["head"], ordered_right["head"]} == {"zeta", "aesop"}
    assert protocol.determinism_audit_count(1) == 1
    assert protocol.determinism_audit_count(10) == 1
    assert protocol.determinism_audit_count(11) == 2


def _endpoint(path: Path, endpoint_sha: str) -> dict:
    payload = path.read_bytes()
    return {
        "sha256": endpoint_sha,
        "metadata": {"goal_count": 1, "terminal": False},
        "state": {
            "path": str(path),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        },
    }


def test_collision_check_uses_full_strict_payload() -> None:
    with tempfile.TemporaryDirectory(prefix="exp52-fix3-static-") as raw:
        root = Path(raw)
        one, two = root / "one.txt", root / "two.txt"
        one.write_text("(GOAL 0 (TARGET one))", encoding="utf-8")
        two.write_text("(GOAL 0 (TARGET two))", encoding="utf-8")
        initial = {"struct": _endpoint(one, "same-endpoint-hash")}
        branch = {
            "executable": True,
            "endpoints": {"struct": _endpoint(two, "same-endpoint-hash")},
        }
        assert select_exp52_pairs._strict_state_collision([branch], initial)
        assert audit_exp52._strict_collision([branch], initial)


def test_failure_requires_valid_reconstruction() -> None:
    invalid = {
        "record_complete": True,
        "probe_attempted": True,
        "valid_reconstruction": False,
        "probe_status": "failure",
        "failure_category": "timeout",
    }
    valid = {**invalid, "valid_reconstruction": True}
    assert analyze_exp52._side_state(invalid) == "invalid"
    assert analyze_exp52._side_state(valid) == "failure"
    assert audit_exp52._status(invalid) == "invalid"
    assert audit_exp52._status(valid) == "failure"


def test_worker_and_runner_safety_contracts() -> None:
    lean = experiment52_live_worker.LEAN_SOURCE
    assert hashlib.sha256(lean.encode("utf-8")).hexdigest() == (
        experiment52_live_worker.LEAN_SOURCE_SHA256
    )
    for fragment in (
        "structure CandidateCheckpoint",
        "reconstructionMatched",
        "probeInvocationNext",
        "liftM (m := IO)",
        "TacticInfo",
        "mctxBefore",
        "goalsBefore",
    ):
        assert fragment in lean
    assert "liftIO" not in lean
    assert lean.count("let some start := ti.stx.getPos? true") == 1
    runner = (PACKAGE_ROOT / "run_exp52_shards.py").read_text(encoding="utf-8")
    assert "scientific_retry_permitted" in runner
    assert "_worker_still_active" in runner
    assert "_active_worker_pids_for_command" in runner
    assert "shard_completion_gate" in runner
    assert "shard_execution_integrity_gate" in runner
    assert run_exp52_shards.WORKER.resolve() == (
        PACKAGE_ROOT / "experiment52_live_worker.py"
    ).resolve()


def test_independent_audits_do_not_import_primary_analysis() -> None:
    exp51_audit = (PACKAGE_ROOT / "audit_exp51_fix3.py").read_text(
        encoding="utf-8"
    )
    exp52_audit = (PACKAGE_ROOT / "audit_exp52.py").read_text(
        encoding="utf-8"
    )
    assert "import base_analysis" not in exp51_audit
    assert "import select_exp52_pairs" not in exp52_audit
    assert "import analyze_exp52" not in exp52_audit
    assert "all_576_roots_accounted" in exp52_audit
    assert "execution_cell_plan_and_rows_exact" in exp52_audit
    assert "execution_row_inputs_receipts_and_launches_exact" in exp52_audit
    assert '"execution_index": execution_root / "row_index.jsonl"' in exp52_audit


def test_exp52_preflight_has_launch_resource_gate() -> None:
    source = (PACKAGE_ROOT / "preflight_exp52_execution.py").read_text(
        encoding="utf-8"
    )
    assert "MINIMUM_AVAILABLE_MEMORY_GB = 64" in source
    assert "MINIMUM_FREE_DISK_GB = 50" in source
    assert '"launch_resources": resources' in source
    assert 'resources["resource_gate"] is True' in source


def test_manifest_exact() -> None:
    path = PACKAGE_ROOT / "PACKAGE_MANIFEST.json"
    assert path.is_file(), "PACKAGE_MANIFEST.json is absent"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["schema"] == "exp51-exp52-fix3-package-manifest-v1"
    rows = manifest["files"]
    assert len({row["path"] for row in rows}) == len(rows)
    expected = {
        item.relative_to(SERVER_ROOT).as_posix()
        for item in PACKAGE_ROOT.glob("*.py")
    }
    expected.add((PACKAGE_ROOT / "README_SERVER.md").relative_to(SERVER_ROOT).as_posix())
    expected.update(
        (protocol.EXP52_DOCUMENT_ROOT / name).relative_to(SERVER_ROOT).as_posix()
        for name in protocol.fix2.PREREGISTRATION_DOCUMENTS
    )
    assert {row["path"] for row in rows} == expected
    for row in rows:
        target = SERVER_ROOT / row["path"]
        assert target.is_file()
        assert target.stat().st_size == row["bytes"]
        assert sha256(target) == row["sha256"]
    assert manifest["files_sha256"] == protocol.json_sha256(rows)


def main() -> None:
    tests = [
        value for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(json.dumps({
        "version": 1,
        "package": protocol.EXECUTION_ALIGNMENT_VERSION,
        "tests": len(tests),
        "all_static_tests_passed": True,
        "lean_executed": False,
        "theorem_sources_elaborated": 0,
        "scientific_candidate_tactics_executed": 0,
        "continuation_probes_executed": 0,
    }, indent=2))


if __name__ == "__main__":
    main()
