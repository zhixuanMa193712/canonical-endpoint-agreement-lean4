"""Static no-Lean tests for the prospective confirmation design."""
from __future__ import annotations

import unittest

from experiment56_protocol import *


class ProspectiveStaticTests(unittest.TestCase):
    def test_design_size(self) -> None:
        self.assertEqual(REPOSITORIES_REQUIRED, 38)
        self.assertEqual(ROOTS_PER_REPOSITORY, 16)
        self.assertEqual(TOTAL_ROOTS, 608)

    def test_repository_priority(self) -> None:
        self.assertGreater(REPOSITORIES_REQUIRED, ROOTS_PER_REPOSITORY)

    def test_seeds_are_separate(self) -> None:
        self.assertEqual(len({MASTER_REPOSITORY_SEED, MASTER_ROOT_SEED, POWER_SEED, BOOTSTRAP_SEED}), 4)

    def test_source_locks(self) -> None:
        for record in [SOURCE_EXP51, *LOCKED_BACKENDS.values()]:
            self.assertEqual(len(record["sha256"]), 64)

    def test_selection_is_deterministic(self) -> None:
        self.assertEqual(selection_key(1, "a", "b"), selection_key(1, "a", "b"))
        self.assertNotEqual(selection_key(1, "a", "b"), selection_key(2, "a", "b"))

    def test_historical_exclusions_are_locked(self) -> None:
        self.assertEqual(len(HISTORICAL_SCIENTIFIC_REPOSITORIES), 20)
        self.assertEqual(len(FROZEN_GITHUB_QUERIES), 4)

    def test_candidate_panel_backend_is_locked(self) -> None:
        self.assertIn("protocol", LOCKED_BACKENDS)
        self.assertEqual(CANDIDATES_PER_ROOT, 23)


if __name__ == "__main__":
    unittest.main()
