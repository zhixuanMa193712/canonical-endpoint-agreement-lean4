"""No-Lean static tests for the Exp58 pre-continuation package."""
from __future__ import annotations

import inspect
import unittest

import enumerate_experiment58_targets as enumeration
import experiment58_candidate_worker as candidate_worker
import apply_experiment58_fix2 as fix2
import freeze_experiment58 as freezer
import plan_experiment58_power as power
from experiment58_protocol import *


class Experiment58StaticTests(unittest.TestCase):
    def test_exact_external_commits(self) -> None:
        self.assertEqual(set(DATASETS), {"minif2f", "putnambench"})
        self.assertTrue(all(len(row["commit"]) == 40 for row in DATASETS.values()))
        self.assertTrue(all(row["license"] == "Apache-2.0" for row in DATASETS.values()))

    def test_locked_panels_match_exp57(self) -> None:
        candidates, probes, hashes = freezer.load_locked_panels()
        self.assertEqual(tuple(candidates), CANDIDATE_PANEL)
        self.assertEqual(tuple(probes), PROBE_PANEL)
        self.assertTrue(all(len(value) == 64 for value in hashes.values()))

    def test_source_and_vendor_hashes(self) -> None:
        self.assertEqual(file_sha256(SOURCE_EXP57_ARCHIVE), SOURCE_EXP57_ARCHIVE_SHA256)
        self.assertEqual(len(validate_vendor()), 2)

    def test_screening_frame_size(self) -> None:
        self.assertEqual(SCREENING_ROOTS_TOTAL, 512)
        self.assertEqual(SCREENING_ROOTS_PER_DATASET, 256)
        self.assertGreater(CONFIRMATION_FRAME_PER_DATASET, PILOT_FRAME_PER_DATASET)

    def test_hard_root_eligibility(self) -> None:
        self.assertEqual(CANDIDATES_PER_ROOT, 23)
        self.assertGreaterEqual(MIN_EXECUTABLE_NONTERMINAL, 4)
        self.assertGreaterEqual(MIN_EFFECT_CLASS_SIZE, 2)
        prepare = __import__("prepare_experiment58_benchmarks")
        self.assertIn("and build and", inspect.getsource(prepare.prepare_one))
        self.assertIn('command(["lake", "build"]', inspect.getsource(prepare.prepare_one))
        self.assertNotIn('["lake", "build", "-j"', inspect.getsource(prepare.prepare_one))

    def test_fix2_is_pre_scientific(self) -> None:
        self.assertEqual(MECHANICAL_FIX_ID, "exp58-pre-continuation-root-path-and-accounting-fix2")
        source = inspect.getsource(__import__("freeze_experiment58").freeze)
        self.assertIn("scientific_execution_before_fix1", source)
        self.assertIn("unknown short option '-j'", source)
        amendment = inspect.getsource(fix2.apply)
        self.assertIn("candidate_only_tactics_executed_before_fix2", amendment)
        self.assertIn("failed_execution_preserved_in_place", amendment)

    def test_fix2_stages_exact_source_inside_project(self) -> None:
        source = inspect.getsource(candidate_worker.run)
        self.assertIn('.lake/exp58_measurement_sources', source)
        self.assertIn('staged_source.write_bytes(source.read_bytes())', source)
        self.assertIn('"staged_source_content_exact"', source)
        self.assertIn('"first_failed_gate": "timeout" if timed_out else "worker"', source)

    def test_fix2_accounting_is_fail_closed(self) -> None:
        runner = inspect.getsource(__import__("run_experiment58_candidate_screening").run)
        finalizer = inspect.getsource(__import__("finalize_experiment58_candidate_screening").run)
        self.assertIn('row.get("worker_ok") is True', runner)
        self.assertIn('row.get("candidate_accounting_exact") is True', runner)
        self.assertIn('candidate receipt failed operational gate', finalizer)
        self.assertIn('candidate eligibility/failure label mismatch', finalizer)

    def test_official_and_hash_partitions_are_disjoint(self) -> None:
        self.assertEqual(DATASETS["minif2f"]["upstream_partition"]["pilot"], "MiniF2F/Valid.lean")
        self.assertEqual(DATASETS["minif2f"]["upstream_partition"]["confirmation"], "MiniF2F/Test.lean")
        self.assertEqual(MINIF2F_EXPECTED_THEOREMS, {"pilot": 256, "confirmation": 244})
        self.assertNotEqual(PARTITION_SEED, FRAME_SEED)

    def test_no_confirmation_n_before_pilot(self) -> None:
        self.assertIn("paired_root_metrics.jsonl", inspect.getsource(power.run))
        self.assertIn("must not be invented", inspect.getsource(power.run))

    def test_candidate_worker_has_no_probe_argument(self) -> None:
        source = inspect.getsource(candidate_worker.run)
        self.assertNotIn("probeText", source)
        self.assertIn("*CANDIDATE_PANEL", source)
        self.assertIn('"continuation_probes_executed": 0', source)

    def test_power_unit_and_noninferiority(self) -> None:
        self.assertLessEqual(power.wilson_upper(0, 64), COVERAGE_NONINFERIORITY_MARGIN)
        self.assertEqual(COVERAGE_NONINFERIORITY_MARGIN, 0.05)

    def test_putnam_release_is_fail_closed(self) -> None:
        self.assertIn("do not redistribute", DATASETS["putnambench"]["public_result_policy"])

    def test_measurement_transform_regexes(self) -> None:
        self.assertIsNotNone(enumeration.BY_SORRY.search("theorem x : True := by\n  sorry"))
        self.assertIsNotNone(enumeration.DIRECT_SORRY.search("theorem x : True := sorry"))

    def test_four_policies_and_separate_estimands(self) -> None:
        self.assertEqual(POLICIES, ("full", "effect_aware", "head_dedup", "fixed_budget_random"))
        self.assertEqual(len(set((PARTITION_SEED, FRAME_SEED, PILOT_SELECTION_SEED,
                                  CONFIRMATION_SELECTION_SEED, RANDOM_POLICY_SEED, POWER_SEED))), 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
