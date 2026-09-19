"""Static and synthetic policy tests for the frozen Exp62 package."""
from __future__ import annotations

import unittest

from experiment62_protocol import *


class Exp62StaticTests(unittest.TestCase):
    def test_initial_freeze(self) -> None:
        protocol = load_initial_protocol()
        frame = read_jsonl(PACKAGE_ROOT / "frozen/candidate_frame.jsonl")
        self.assertEqual(protocol["candidate_frame_rows"], EXPECTED_FRAME_ROWS)
        self.assertEqual(len(frame), EXPECTED_FRAME_ROWS)
        self.assertEqual(len({row["target_id"] for row in frame}), len(frame))
        for row in frame:
            assert_sealed(row, row["target_id"])
            self.assertGreaterEqual(row["authored_witness_depth"], MIN_WITNESS_DEPTH)
            self.assertLessEqual(row["authored_witness_depth"], MAX_WITNESS_DEPTH)
            self.assertFalse(any(forbidden_tactic(tactic) for tactic in row["authored_witness_tactics"]))
            self.assertTrue(set(row["authored_witness_tactics"]) <= set(row["candidate_panel"]))
            self.assertEqual(row["candidate_panel_sha256"], json_sha256(row["candidate_panel"]))
        for stratum in STRATA:
            self.assertEqual(sum(row["role"] == "pilot" and row["stratum"] == stratum for row in frame), PILOT_FRAME_PER_STRATUM)
            self.assertEqual(sum(row["role"] == "confirmation" and row["stratum"] == stratum for row in frame), CONFIRMATION_FRAME_PER_STRATUM)

    def test_policy_selection(self) -> None:
        children = [
            {"tactic": "simp", "head": "simp", "endpoint_key": "A"},
            {"tactic": "simp only", "head": "simp", "endpoint_key": "A"},
            {"tactic": "aesop", "head": "aesop", "endpoint_key": "B"},
            {"tactic": "rfl", "head": "rfl", "endpoint_key": "B"},
        ]
        self.assertEqual(len(choose_children("full", children, "t", "n")), 4)
        self.assertEqual(len(choose_children("effect_aware", children, "t", "n")), 2)
        self.assertEqual(len(choose_children("head_dedup", children, "t", "n")), 3)
        random_a = choose_children("fixed_budget_random", children, "t", "n")
        random_b = choose_children("fixed_budget_random", children, "t", "n")
        self.assertEqual(random_a, random_b)
        self.assertEqual(len(random_a), 2)

    def test_witness_priority_and_noninferiority_resolution(self) -> None:
        panel = ["a", "b", "c", "d", "e"]
        self.assertEqual(ordered_candidates(panel, "e")[WITNESS_INSERT_INDEX], "e")
        self.assertLessEqual(
            wilson_upper(0, EXPECTED_CONFIRMATION_ROOTS),
            COVERAGE_NONINFERIORITY_MARGIN,
        )
        self.assertGreater(
            wilson_upper(1, EXPECTED_CONFIRMATION_ROOTS),
            COVERAGE_NONINFERIORITY_MARGIN,
        )

    def test_policy_orders_are_permutations(self) -> None:
        frame = read_jsonl(PACKAGE_ROOT / "frozen/candidate_frame.jsonl")
        for row in frame:
            self.assertEqual(set(policy_order(row["target_id"])), set(POLICIES))


if __name__ == "__main__":
    unittest.main(verbosity=2)
