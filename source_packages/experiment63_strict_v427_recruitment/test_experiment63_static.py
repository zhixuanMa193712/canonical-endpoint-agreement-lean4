"""Fast offline tests for Exp63's preregistered adjudication and static gate."""
from __future__ import annotations

import unittest

from experiment63_protocol import classify_build_trace_receipt, selection_key
from strict_static_prefilter import static_roots, strip_comments


class StaticRootTests(unittest.TestCase):
    def test_nested_comments_and_line_comments_do_not_create_roots(self) -> None:
        source = """
/- theorem falseA : True := by trivial /- lemma falseB : True := by trivial -/ -/
-- theorem falseC : True := by trivial
theorem realA : True := by
  trivial
"""
        roots = static_roots(source)
        self.assertEqual([row["name"] for row in roots], ["realA"])

    def test_incomplete_and_term_proofs_are_conservatively_excluded(self) -> None:
        source = """
theorem incomplete : True := by sorry
lemma termProof : True := True.intro
protected theorem complete : True := by exact True.intro
"""
        self.assertEqual([row["name"] for row in static_roots(source)], ["complete"])

    def test_comment_stripping_preserves_offsets(self) -> None:
        source = "theorem x : True := by trivial -- comment\n"
        self.assertEqual(len(strip_comments(source)), len(source))


class AdjudicationTests(unittest.TestCase):
    def test_no_space_is_operational(self) -> None:
        receipt = {"build_trace_gate": False, "first_failed_gate": "checkout",
                   "error": {"message": "OSError: [Errno 28] No space left on device"}}
        self.assertEqual(classify_build_trace_receipt(receipt)[0], "operationally_unresolved")

    def test_parser_enumeration_is_operational(self) -> None:
        receipt = {"build_trace_gate": False, "first_failed_gate": "root_enumeration",
                   "error": {"message": "modified named section was absent"}}
        self.assertEqual(classify_build_trace_receipt(receipt)[0], "operationally_unresolved")

    def test_real_build_failure_is_definitive(self) -> None:
        receipt = {"build_trace_gate": False, "first_failed_gate": "unmodified_build",
                   "error": {"message": "lake build failed"},
                   "build": {"stderr_tail": "type mismatch"}}
        self.assertEqual(classify_build_trace_receipt(receipt),
                         ("definitive_ineligible", "unmodified_build"))

    def test_dependency_fetch_build_failure_is_operational(self) -> None:
        receipt = {"build_trace_gate": False, "first_failed_gate": "unmodified_build",
                   "error": {"message": "external command 'git' exited with code 128"}}
        self.assertEqual(classify_build_trace_receipt(receipt)[0], "operationally_unresolved")

    def test_selection_key_is_deterministic(self) -> None:
        self.assertEqual(selection_key(1, "a", "b"), selection_key(1, "a", "b"))
        self.assertNotEqual(selection_key(1, "a", "b"), selection_key(2, "a", "b"))


if __name__ == "__main__":
    unittest.main()
