"""Pure-Python/static protection tests for Exp51 frame extension 2."""
from __future__ import annotations

import hashlib
import json
import os
import re
import unittest
import zipfile
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
WORKSPACE = PACKAGE.parent
BASE = WORKSPACE / "experiment51_external_repository_replication"
EXTENSION1 = WORKSPACE / "experiment51_repository_frame_extension"
FRAME = PACKAGE / "repository_extension_candidates.json"
_export_nogo = (
    WORKSPACE / "exports/experiment51_repository_frame_extension1_nogo_results.zip"
)
_root_nogo = WORKSPACE / "experiment51_repository_frame_extension1_nogo_results.zip"
NOGO = _export_nogo if _export_nogo.is_file() else _root_nogo
NOGO_SHA256 = "94101bccc3be5d7edff48b91824494a228f9a21fce2580f1353594eeab420473"
CARRY = (
    "PatrickMassot/GlimpseOfLean",
    "AfonsoBitoque/LeanServer",
    "dissensus-ai/lean-formalizations",
    "leanprover-community/batteries",
    "bergmannjg/Regex",
    "Verified-zkEVM/VCVio",
    "leanprover-community/lean-auto",
    "YaelDillies/misc-yd",
    "MichaelStollBayreuth/LegendreQF",
    "verse-lab/Lentil",
    "AmosNico/validator",
)


def text(name: str) -> str:
    return (PACKAGE / name).read_text(encoding="utf-8")


class Extension2StaticTests(unittest.TestCase):
    def test_01_extension1_archive_is_complete_and_zero_candidate(self) -> None:
        self.assertTrue(NOGO.is_file())
        self.assertEqual(NOGO.stat().st_size, 1_349_401)
        self.assertEqual(hashlib.sha256(NOGO.read_bytes()).hexdigest(), NOGO_SHA256)
        with zipfile.ZipFile(NOGO) as archive:
            self.assertIsNone(archive.testzip())
            manifest = json.loads(archive.read("MANIFEST.json"))
            decision = json.loads(
                archive.read("artifacts/extension1_nogo/summary.json")
            )
            self.assertEqual(len(manifest["entries"]), 170)
            for entry in manifest["entries"]:
                value = archive.read(entry["path"])
                self.assertEqual(len(value), entry["bytes"])
                self.assertEqual(hashlib.sha256(value).hexdigest(), entry["sha256"])
            self.assertEqual(
                manifest["export_schema"],
                "experiment51-extension1-zero-candidate-build-trace-nogo-export-v1",
            )
            self.assertEqual(
                manifest["export_fix_id"],
                "exp51-extension1-nogo-export-fix1-predependency-failure-accounting",
            )
            self.assertFalse(manifest["scientific_result"])
            self.assertEqual(decision["combined_build_trace_passes"], 11)
            self.assertEqual(decision["minimum_required"], 12)
            self.assertFalse(decision["authored_replay_executed"])
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

    def test_02_frame_is_ordered_exact_and_nonoverlapping(self) -> None:
        frame = json.loads(FRAME.read_text(encoding="utf-8"))
        original = json.loads(
            (BASE / "repository_candidates.json").read_text(encoding="utf-8")
        )
        extension1 = json.loads(
            (EXTENSION1 / "repository_extension_candidates.json").read_text(
                encoding="utf-8"
            )
        )
        candidates = frame["candidates"]
        self.assertEqual(len(candidates), 7)
        self.assertEqual([row["order"] for row in candidates], list(range(1, 8)))
        slugs = [row["slug"] for row in candidates]
        self.assertEqual(slugs, sorted(slugs, key=str.casefold))
        prohibited = {
            row["slug"].casefold() for row in original["candidates"]
        } | {
            slug.casefold() for slug in original["historical_scientific_exclusions"]
        } | {
            row["slug"].casefold() for row in extension1["candidates"]
        }
        self.assertFalse(prohibited.intersection(slug.casefold() for slug in slugs))
        for row in candidates:
            self.assertRegex(row["ref"], r"^[0-9a-f]{40}$")
            self.assertEqual(row["target_toolchain"], "leanprover/lean4:v4.27.0")
            self.assertTrue(row["url"].startswith("https://github.com/"))
            self.assertTrue(row["subdir"])
            self.assertEqual(row["license_evidence"], "LICENSE")
        self.assertEqual(frame["scientific_candidate_tactics_permitted"], 0)
        self.assertEqual(frame["source_overlap_threshold"], 0.2)

    def test_03_zero_candidate_and_twelve_repository_stop_gates(self) -> None:
        freeze = text("freeze_experiment51_extension.py")
        screen = text("screen_experiment51_extension.py")
        preflight = text("preflight_experiment51_extension.py")
        protocol = text("experiment51_extension_protocol.py")
        readme = text("README_SERVER.md")
        inherited_preflight = (
            EXTENSION1 / "preflight_experiment51_extension.py"
        ).read_text(encoding="utf-8")
        self.assertIn("eleven zero-candidate qualification passes", freeze)
        self.assertIn('"scientific_candidate_tactics_executed": 0', screen)
        self.assertIn('"candidate_tactics_executed": 0', inherited_preflight)
        self.assertIn("MIN_REPOSITORIES = base.MIN_REPOSITORIES", protocol)
        self.assertNotRegex(protocol, r"MIN_REPOSITORIES\s*=\s*(?:[0-9]|1[01])\b")
        self.assertNotIn("--phase authored-replay", readme)
        self.assertNotIn("--phase scientific", readme)
        self.assertIn("STOP", readme)

    def test_04_archive_carry_and_active_checkout_gates_are_static(self) -> None:
        protocol = text("experiment51_extension_protocol.py")
        screen = text("screen_experiment51_extension.py")
        self.assertIn("for entry in entries:", protocol)
        self.assertIn("validate_active_carry_checkouts", protocol)
        self.assertIn("source_inventory(project)", protocol)
        self.assertIn('"tracked_checkout_clean": True', protocol)
        self.assertIn("EXTENSION1_NOGO_BUNDLE_SHA256", screen)
        self.assertIn('"active_checkout_revalidated": True', screen)

    def test_05_locked_inherited_mechanism_and_claim_boundary(self) -> None:
        protocol = text("experiment51_extension_protocol.py")
        freeze = text("freeze_experiment51_extension.py")
        readme = text("README_SERVER.md")
        inherited_freeze = (
            EXTENSION1 / "freeze_experiment51_extension.py"
        ).read_text(encoding="utf-8")
        for inherited in (
            "experiment51_extension_enumeration_worker.py",
            "screen_experiment51_extension.py",
            "experiment51_protocol.py",
            "experiment51_trace_runtime.py",
            "screen_experiment51_repositories.py",
            "experiment51_live_worker.py",
        ):
            self.assertIn(inherited, protocol)
        self.assertIn('"code_lock": code_lock(locked_sources())', inherited_freeze)
        self.assertIn("Experiment 48 remains", readme)
        self.assertIn("repository qualification", readme)
        for phrase in (
            "supports tactic interchangeability",
            "supports proof-strategy equivalence",
            "improved theorem proving result",
        ):
            self.assertNotIn(phrase, readme)

    def test_06_wrappers_bind_extension2_protocol_before_prior_code(self) -> None:
        for name in (
            "freeze_experiment51_extension.py",
            "preflight_experiment51_extension.py",
            "screen_experiment51_extension.py",
            "experiment51_extension_enumeration_worker.py",
        ):
            source = text(name)
            protocol_pos = source.index("from experiment51_extension_protocol import")
            implementation_pos = source.index("from experiment51_repository_frame_extension import")
            self.assertLess(protocol_pos, implementation_pos)
        screen = text("screen_experiment51_extension.py")
        self.assertIn(
            "enumerate_isolated = implementation.enumerate_isolated",
            screen,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
