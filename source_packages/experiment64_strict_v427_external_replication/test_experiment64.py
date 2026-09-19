from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import analyze_experiment64 as analysis
import audit_experiment64 as audit
import run_experiment64 as execution
from experiment64_protocol import (
    CANDIDATES_PER_ROOT,
    MEASUREMENT_ENGINE_PROTOCOL,
    PROTOCOL_VERSION,
    atomic_json_dump,
    file_sha256,
    json_sha256,
    read_json,
    safe_slug,
    seal,
    target_identity,
)


class Experiment64Tests(unittest.TestCase):
    def test_target_identity_is_path_independent(self) -> None:
        row = {
            "slug": "owner/repo", "commit": "a" * 40, "file_path": "A.lean",
            "full_name": "A.x", "theorem_id": "b" * 64, "rid": "b" * 20,
            "source_file_sha256": "c" * 64, "target_pos": 1, "target_end_pos": 2,
            "authored_tactic": "simp", "trace_root_state_sha256": "d" * 64,
            "trace_state_after_sha256": "e" * 64, "ast_record_index": 0,
            "ast_sha256": "f" * 64, "checkout": "/old", "ast_path": "/old/a.ast.json",
        }
        moved = dict(row, checkout="/new", ast_path="/new/a.ast.json")
        self.assertEqual(target_identity(row), target_identity(moved))

    def test_exact_cache_paths_are_commit_scoped(self) -> None:
        commit = "a" * 40
        paths = execution.exact_cache_paths({"slug": "owner/repo", "commit": commit})
        self.assertEqual(len(paths), 3)
        self.assertTrue(all(commit in path.name for path in paths))
        self.assertTrue(all("repo" in path.name for path in paths))

    def test_nontrivial_cross_head_endpoint_sets_y(self) -> None:
        initial = "i" * 64
        endpoint = "x" * 64
        worker = {
            "worker_ok": True,
            "candidate_order": ["simp", "aesop"],
            "initial_endpoints": {"struct": {"sha256": initial}},
            "candidates": [
                {"tactic": "simp", "head": "simp", "family": "simplification",
                 "executable": True, "terminal": False,
                 "endpoints": {"struct": {"sha256": endpoint}}},
                {"tactic": "aesop", "head": "aesop", "family": "automation",
                 "executable": True, "terminal": False,
                 "endpoints": {"struct": {"sha256": endpoint}}},
            ],
        }
        value = analysis.analyze_view(worker, ["simp", "aesop"])
        self.assertTrue(value["Y"])
        self.assertTrue(value["Y_nonterminal"])
        self.assertTrue(value["Y_cross_family"])

    def test_constants_match_frozen_measurement_engine(self) -> None:
        self.assertEqual(CANDIDATES_PER_ROOT, 23)
        self.assertEqual(
            MEASUREMENT_ENGINE_PROTOCOL,
            "experiment51-preregistered-external-repository-replication-v1",
        )

    @unittest.skipUnless(os.environ.get("EXP64_FROZEN_TEST_ROOT"), "requires a reconstructed freeze")
    def test_offline_analysis_and_independent_audit_with_missingness(self) -> None:
        source = Path(os.environ["EXP64_FROZEN_TEST_ROOT"])
        with tempfile.TemporaryDirectory(prefix="exp64-analysis-test-") as temporary:
            root = Path(temporary)
            shutil.copytree(source / "frozen", root / "frozen")
            protocolp = root / "frozen/protocol.json"
            config_sha = file_sha256(protocolp)
            targets = json.loads((root / "frozen/targets.json").read_text(encoding="utf-8"))
            # One fully evaluable root per repository and 15 explicitly missing roots
            # exercise complete-case estimates and frozen-frame worst-case bounds.
            for target in [row for row in targets if row["root_index_within_repository"] == 1]:
                candidates = [
                    {
                        "tactic": tactic,
                        "head": tactic.split()[0],
                        "family": "test",
                        "executable": False,
                    }
                    for tactic in target["alternatives"]
                ]
                worker = {
                    "version": 1,
                    "protocol_version": MEASUREMENT_ENGINE_PROTOCOL,
                    "mode": "exp64_scientific",
                    "config_sha256": config_sha,
                    "slug": target["slug"],
                    "commit": target["commit"],
                    "theorem_id": target["theorem_id"],
                    "source_file_sha256": target["source_file_sha256"],
                    "candidate_order": target["alternatives"],
                    "candidates": candidates,
                    "worker_ok": True,
                    "authored_replay_ok": True,
                    "same_pre_state_all_branches": True,
                    "initial_endpoints": {"struct": {"sha256": "0" * 64}},
                }
                worker["record_sha256"] = json_sha256(worker)
                atomic_json_dump(
                    worker,
                    root / "scientific/theorems" / safe_slug(target["slug"]) / f"{target['rid']}.json",
                )
            scientific = seal({
                "version": 1,
                "protocol_version": PROTOCOL_VERSION,
                "completed_repositories": 32,
            })
            atomic_json_dump(scientific, root / "scientific/summary.json")
            analyzed = analysis.analyze(argparse.Namespace(artifact_root=str(root)))
            self.assertEqual(analyzed["evaluable_roots"], 32)
            self.assertEqual(analyzed["primary"]["complete_case_macro_mean"], 0.0)
            self.assertEqual(analyzed["primary"]["frozen_frame_worst_case_bounds"], [0.0, 0.9375])
            audited = audit.run(root)
            self.assertTrue(audited["audit_passed"])


if __name__ == "__main__":
    unittest.main()
