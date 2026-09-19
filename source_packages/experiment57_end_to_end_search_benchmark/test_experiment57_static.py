"""No-Lean static tests for Experiment 57."""
from __future__ import annotations

import unittest

from experiment57_protocol import *


class SearchBenchmarkStaticTests(unittest.TestCase):
    def test_four_registered_policies(self) -> None:
        self.assertEqual(POLICIES, ("full", "effect_aware", "head_dedup", "fixed_budget_random"))

    def test_job_count(self) -> None:
        self.assertEqual(EXPECTED_JOBS, 64)

    def test_common_budget(self) -> None:
        self.assertGreater(ROOT_POLICY_TIME_BUDGET_SECONDS, CELL_TIMEOUT_SECONDS)

    def test_source_sha(self) -> None:
        self.assertEqual(len(SOURCE_ARCHIVE_SHA256), 64)
        self.assertEqual(len(SOURCE_EXP49_ARCHIVE_SHA256), 64)

    def test_full_candidate_frontier(self) -> None:
        self.assertEqual(CANDIDATES_PER_ROOT, 23)


if __name__ == "__main__":
    unittest.main()
