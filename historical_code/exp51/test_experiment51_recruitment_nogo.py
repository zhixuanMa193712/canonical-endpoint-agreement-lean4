"""Pure-Python tests for the Exp51 recruitment No-Go exporter."""
from __future__ import annotations

import unittest

from experiment51_protocol import (
    MECHANICAL_FIX_ID,
    MIN_REPOSITORIES,
    PROTOCOL_VERSION,
    RECRUITMENT_VERSION,
)
from export_experiment51_recruitment_nogo import derive_decision


def config() -> dict:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "recruitment_version": RECRUITMENT_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "scientific_candidate_tactics_permitted": 0,
        "minimum_repositories": MIN_REPOSITORIES,
        "candidate_count": 26,
    }


def recovery() -> dict:
    return {
        "phase": "recover-enumeration",
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "trace_executed": False,
        "scientific_candidate_tactics_executed": 0,
        "fix8_success_frames_exact": True,
        "checkout_line_ending_measurement": {"exact": True},
        "recovery_gate": False,
        "candidates": 26,
        "passed": 7,
        "parser_compatibility_measurement": {
            "expected_from_frozen_parser_qualification": {"repositories": 15},
            "observed": {"repositories": 13},
            "exact": False,
        },
    }


def rows() -> list[dict]:
    out = []
    for index in range(26):
        if index < 7:
            gate, passed = None, True
        elif index < 13:
            gate, passed = "minimum_pre_replay_frame", False
        elif index < 15:
            gate, passed = "root_enumeration", False
        else:
            gate, passed = "trace", False
        row = {
            "candidate": {"slug": f"owner/repo-{index:02d}"},
            "build_trace_gate": passed,
            "first_failed_gate": gate,
            "scientific_candidate_tactics_executed": 0,
        }
        if gate == "minimum_pre_replay_frame":
            row["enumeration"] = {"pre_replay_frame": index}
        if gate == "root_enumeration":
            row["error"] = {"type": "RuntimeError", "message": "mechanical"}
        out.append(row)
    return out


class RecruitmentNoGoTests(unittest.TestCase):
    def test_derives_strict_frame_level_nogo(self) -> None:
        value = derive_decision(config(), recovery(), rows())
        self.assertEqual(value["decision_label"], "recruitment_no_go")
        self.assertFalse(value["scientific_result"])
        self.assertEqual(value["repositories_passed"], 7)
        self.assertEqual(value["current_frame_upper_bound"], 9)
        self.assertFalse(value["current_frame_can_reach_minimum"])
        self.assertEqual(value["scientific_candidate_tactics_executed"], 0)

    def test_rejects_any_candidate_execution(self) -> None:
        bad = rows()
        bad[0]["scientific_candidate_tactics_executed"] = 1
        with self.assertRaisesRegex(ValueError, "scientific candidates"):
            derive_decision(config(), recovery(), bad)

    def test_rejects_premature_nogo_when_upper_bound_can_reach_minimum(self) -> None:
        bad = rows()
        for index in range(15, 20):
            bad[index]["first_failed_gate"] = "root_enumeration"
        with self.assertRaisesRegex(ValueError, "could still reach"):
            derive_decision(config(), recovery(), bad)

    def test_rejects_changed_minimum(self) -> None:
        bad = config()
        bad["minimum_repositories"] = 7
        with self.assertRaisesRegex(ValueError, "minimum changed"):
            derive_decision(bad, recovery(), rows())


if __name__ == "__main__":
    unittest.main()
