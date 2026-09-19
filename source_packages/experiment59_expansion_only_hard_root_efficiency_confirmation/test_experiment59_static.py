"""No-Lean static checks for the Exp58-to-Exp59 transition package."""
from __future__ import annotations

import inspect
import sys
import unittest

from experiment59_protocol import *

if str(EXP58_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(EXP58_PACKAGE_ROOT))
import experiment58_protocol as exp58

import finalize_exp58_recruitment_nogo as exp58_nogo
import finalize_experiment59_candidate_screening as finalizer
import freeze_experiment59 as freezer
import run_experiment59_candidate_screening as runner
import experiment59_candidate_worker as worker


class Experiment59StaticTests(unittest.TestCase):
    def test_exp58_no_go_contract_is_exact(self) -> None:
        self.assertEqual(sum(exp58_nogo.EXPECTED_REGISTERED_COUNTS.values()), 512)
        self.assertEqual(sum(exp58_nogo.EXPECTED_WITHOUT_EXACT_COUNTS.values()), 512)
        self.assertEqual(sum(exp58_nogo.EXPECTED_WITHOUT_SUGGESTIONS_COUNTS.values()), 512)
        self.assertEqual(EXPECTED_EXP58_TIMEOUT_TARGET_ID, "bdc87192ddab4efca8622f66")
        source = inspect.getsource(exp58_nogo.derive)
        self.assertIn("unresolved receipts could change", source)
        self.assertIn("continuation_probes_executed", source)

    def test_panel_removal_uses_pre_existing_genealogy(self) -> None:
        panel = expansion_panel(exp58)
        self.assertEqual(len(panel), 21)
        self.assertEqual(REMOVED_DIRECT_SUGGESTIONS, ("aesop?", "exact?"))
        self.assertEqual(tuple(x for x in exp58.CANDIDATE_PANEL if x not in panel), REMOVED_DIRECT_SUGGESTIONS)
        genealogy, _, _ = load_genealogy(exp58)
        self.assertTrue(all(genealogy[name]["class"] == "direct_suggestion" for name in REMOVED_DIRECT_SUGGESTIONS))
        self.assertEqual(panel, tuple(x for x in exp58.CANDIDATE_PANEL if x not in REMOVED_DIRECT_SUGGESTIONS))

    def test_all_unused_roots_are_prospectively_accounted(self) -> None:
        self.assertEqual(EXPECTED_COMPLETE_SOURCE_TARGETS, 1170)
        self.assertEqual(EXPECTED_EXP58_SCREENING_ROOTS, 512)
        self.assertEqual(EXPECTED_UNUSED_SOURCE_TARGETS, 658)
        self.assertEqual(sum(EXPECTED_UNUSED_BY_DATASET.values()), 658)
        self.assertEqual(EXPECTED_UNUSED_BY_DATASET["minif2f"] - PILOT_SOURCE_ROOTS_PER_DATASET, 178)
        self.assertEqual(EXPECTED_UNUSED_BY_DATASET["putnambench"] - PILOT_SOURCE_ROOTS_PER_DATASET, 352)
        source = inspect.getsource(freezer.freeze)
        self.assertIn("old_ids &", source)
        self.assertIn("all_unused_exp58_source_roots_included", source)
        self.assertIn("removal_decided_before_any_exp59_execution", source)

    def test_worker_is_candidate_only(self) -> None:
        source = inspect.getsource(worker.run)
        self.assertNotIn("probeText", source)
        self.assertIn("*panel", source)
        self.assertIn('"continuation_probes_executed": 0', source)
        self.assertIn("forbids candidate receipt overwrite and retry", source)

    def test_failures_are_retained_without_retry(self) -> None:
        self.assertIn("valid_retained_failure", inspect.getsource(runner.run))
        self.assertIn("operational_failures_retained", inspect.getsource(runner.run))
        final_source = inspect.getsource(finalizer.run)
        self.assertIn("valid_retained_failure", final_source)
        self.assertIn('row.get("scientific_retry_count") != 0', final_source)

    def test_recruitment_quotas_are_not_lowered(self) -> None:
        self.assertEqual(MIN_PILOT_ELIGIBLE_PER_DATASET, 16)
        self.assertEqual(MIN_CONFIRMATION_POOL_PER_DATASET, 64)
        self.assertEqual(PILOT_ROOTS_PER_DATASET, 16)
        self.assertIn("do not lower quotas", inspect.getsource(finalizer.run))

    def test_exp58_sensitivity_does_not_rescue_exp58(self) -> None:
        self.assertEqual(exp58_nogo.EXPECTED_REGISTERED_COUNTS["eligible"], 4)
        self.assertEqual(exp58_nogo.EXPECTED_WITHOUT_EXACT_COUNTS["eligible"], 364)
        self.assertEqual(exp58_nogo.EXPECTED_WITHOUT_SUGGESTIONS_COUNTS["eligible"], 339)
        source = inspect.getsource(exp58_nogo.derive)
        self.assertIn('"post_execution_sensitivity_only": True', source)
        self.assertIn('"changes_exp58_decision": False', source)

    def test_fixed_shard_count(self) -> None:
        self.assertEqual(SHARD_COUNT, 32)
        self.assertIn("shard-count is frozen", inspect.getsource(runner.parse_args))


if __name__ == "__main__":
    unittest.main(verbosity=2)
