"""Pure-Python/static protection tests for Exp51 frame extension 1."""
from __future__ import annotations

import hashlib
import json
import re
import unittest
import zipfile
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
WORKSPACE = PACKAGE.parent
BASE = WORKSPACE / "experiment51_external_repository_replication"
FRAME = PACKAGE / "repository_extension_candidates.json"
NO_GO = WORKSPACE / "experiment51_recruitment_nogo_fix9_fix3_results.zip"
NO_GO_SHA256 = "5f3ef5ee40609015d20954e6e34fdfd6c53f30263545dcbcfc9ebe0bddf9b683"
CARRY = (
    "PatrickMassot/GlimpseOfLean",
    "AfonsoBitoque/LeanServer",
    "dissensus-ai/lean-formalizations",
    "leanprover-community/batteries",
    "bergmannjg/Regex",
    "Verified-zkEVM/VCVio",
    "leanprover-community/lean-auto",
)


def text(name: str) -> str:
    return (PACKAGE / name).read_text(encoding="utf-8")


class ExtensionStaticTests(unittest.TestCase):
    def test_01_nogo_archive_and_carry_evidence(self) -> None:
        self.assertTrue(NO_GO.is_file())
        self.assertEqual(hashlib.sha256(NO_GO.read_bytes()).hexdigest(), NO_GO_SHA256)
        with zipfile.ZipFile(NO_GO) as archive:
            self.assertIsNone(archive.testzip())
            manifest = json.loads(archive.read("MANIFEST.json"))
            decision = json.loads(
                archive.read("artifacts/recruitment_nogo/summary.json")
            )
            self.assertEqual(
                manifest["export_schema"],
                "experiment51-zero-candidate-recruitment-nogo-export-v1",
            )
            self.assertEqual(decision["decision_label"], "recruitment_no_go")
            self.assertFalse(decision["scientific_result"])
            self.assertEqual(decision["repositories_passed"], 7)
            self.assertEqual(decision["minimum_required"], 12)
            self.assertEqual(decision["current_frame_upper_bound"], 9)
            self.assertFalse(decision["current_frame_can_reach_minimum"])
            self.assertEqual(decision["scientific_candidate_tactics_executed"], 0)
            names = set(archive.namelist())
            for slug in CARRY:
                safe = slug.replace("/", "__")
                for member in (
                    f"artifacts/screening/build_trace/{safe}.json",
                    f"artifacts/screening/frames/{safe}.jsonl",
                    f"artifacts/screening/source_inventories/{safe}.jsonl",
                ):
                    self.assertIn(member, names)

    def test_02_frozen_candidate_frame(self) -> None:
        frame = json.loads(FRAME.read_text(encoding="utf-8"))
        old = json.loads(
            (BASE / "repository_candidates.json").read_text(encoding="utf-8")
        )
        candidates = frame["candidates"]
        self.assertEqual(len(candidates), 28)
        self.assertEqual([row["order"] for row in candidates], list(range(1, 29)))
        slugs = [row["slug"] for row in candidates]
        self.assertEqual(len({slug.casefold() for slug in slugs}), 28)
        prohibited = {
            row["slug"].casefold() for row in old["candidates"]
        } | {
            slug.casefold() for slug in old["historical_scientific_exclusions"]
        }
        self.assertFalse(prohibited.intersection(slug.casefold() for slug in slugs))
        for row in candidates:
            self.assertRegex(row["ref"], r"^[0-9a-f]{40}$")
            self.assertEqual(row["target_toolchain"], "leanprover/lean4:v4.27.0")
            self.assertTrue(row["url"].startswith("https://github.com/"))
            self.assertTrue(row["license"])
        self.assertEqual(frame["scientific_candidate_tactics_permitted"], 0)
        self.assertEqual(frame["source_overlap_threshold"], 0.2)
        self.assertEqual(
            frame["source_registry"]["sha256"],
            "6fc63f1fe2d35902ae10d66683af2cdd5bad998a832f4b8f7f23eca0604451b0",
        )

    def test_03_zero_candidate_and_stop_gates_are_static(self) -> None:
        freeze = text("freeze_experiment51_extension.py")
        screen = text("screen_experiment51_extension.py")
        preflight = text("preflight_experiment51_extension.py")
        protocol = text("experiment51_extension_protocol.py")
        inherited_screen = (
            BASE / "screen_experiment51_repositories.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"scientific_candidate_tactics_permitted": 0', freeze)
        self.assertIn('"scientific_candidate_tactics_executed": 0', screen)
        self.assertIn('"candidate_tactics_executed": 0', preflight)
        self.assertIn("MIN_REPOSITORIES = base.MIN_REPOSITORIES", protocol)
        self.assertNotRegex(protocol, r"MIN_REPOSITORIES\s*=\s*(?:[0-9]|1[01])\b")
        self.assertIn(
            'worker_input(root, target, cfg_sha, [], "screening_authored_only")',
            inherited_screen,
        )
        self.assertNotIn("run_experiment51.py", screen)
        self.assertNotIn("--phase scientific", text("README_SERVER.md"))

    def test_04_offline_adapter_is_narrow_and_audited(self) -> None:
        worker = text("experiment51_extension_enumeration_worker.py")
        preflight = text("preflight_experiment51_extension.py")
        self.assertIn("def get_dependencies_offline", worker)
        self.assertIn("return {}", worker)
        self.assertIn("GitHub API access is forbidden", worker)
        self.assertIn('offline.get("dependency_queries_suppressed") == 1', worker)
        self.assertIn('offline.get("github_api_attempts") == 0', worker)
        self.assertIn("installed_lean_dojo_files_modified", worker)
        self.assertIn("repository_checkout_modified", worker)
        self.assertIn("roots == read_jsonl(expectedp)", preflight)
        self.assertIn("file_sha256(observedp) == file_sha256(expectedp)", preflight)
        self.assertIn('"trace_executed": False', preflight)

    def test_05_failure_receipts_and_accounting_are_protected(self) -> None:
        worker = text("experiment51_extension_enumeration_worker.py")
        screen = text("screen_experiment51_extension.py")
        self.assertIn("except BaseException as exc:", worker)
        self.assertIn('"worker_ok": False', worker)
        self.assertIn("atomic_json_dump(failure, receiptp)", worker)
        self.assertIn("receipt_accounting_exact = len(parser_rows) == trace_qualified", screen)
        self.assertIn("and receipt_accounting_exact", screen)
        self.assertIn("and github_api_attempts == 0", screen)

    def test_06_code_lock_and_claim_boundary(self) -> None:
        protocol = text("experiment51_extension_protocol.py")
        freeze = text("freeze_experiment51_extension.py")
        readme = text("README_SERVER.md")
        for inherited in (
            "experiment51_protocol.py",
            "experiment51_trace_runtime.py",
            "screen_experiment51_repositories.py",
            "experiment51_live_worker.py",
        ):
            self.assertIn(inherited, protocol)
        self.assertIn('"code_lock": code_lock(locked_sources())', freeze)
        self.assertIn("Experiment 48 remains", freeze)
        self.assertIn("qualification evidence only", readme)
        forbidden_claims = (
            "supports tactic interchangeability",
            "supports proof-strategy equivalence",
            "improved theorem proving result",
        )
        for phrase in forbidden_claims:
            self.assertNotIn(phrase, readme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
