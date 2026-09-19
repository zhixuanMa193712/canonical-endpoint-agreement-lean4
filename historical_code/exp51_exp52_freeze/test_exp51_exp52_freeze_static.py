"""Offline tests for the Exp51/Exp52 freeze alignment; never invoke Lean."""
from __future__ import annotations

import ast
import unittest

from experiment52_protocol import (
    ALIGNMENT_FIX_ID,
    ALIGNMENT_VERSION,
    DOCUMENT_ROOT,
    EXP52_DESIGN_LOCK_VERSION,
    EXP52_PROTOCOL_VERSION,
    PACKAGE_ROOT,
    PREREGISTRATION_DOCUMENTS,
    PROBE_POOL,
    build_exp52_protocol,
    document_lock,
    file_sha256,
    json_sha256,
    retained_probe_panel,
    validate_protocol,
)
from preflight_exp52_probe_surface import lean_module_name, source_for


class AlignmentStaticTests(unittest.TestCase):
    def test_01_python_sources_parse_without_running_lean(self) -> None:
        sources = sorted(PACKAGE_ROOT.glob("*.py"))
        self.assertGreaterEqual(len(sources), 4)
        for path in sources:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        self.assertFalse(list(PACKAGE_ROOT.glob("*.lean")))

    def test_02_preregistration_documents_are_exact(self) -> None:
        lock = document_lock()
        self.assertEqual(len(lock["files"]), 2)
        self.assertEqual(lock["bundle_sha256"], json_sha256(lock["files"]))
        for name, digest in PREREGISTRATION_DOCUMENTS.items():
            self.assertEqual(file_sha256(DOCUMENT_ROOT / name), digest)

    def test_03_probe_panel_is_frozen_and_mechanically_filtered(self) -> None:
        self.assertEqual(
            ALIGNMENT_VERSION,
            "experiment51-exp52-scientific-freeze-alignment-fix2",
        )
        self.assertIn("fix2-monadic-tactic-quotation", ALIGNMENT_FIX_ID)
        self.assertEqual(len(PROBE_POOL), 12)
        self.assertEqual(len(PROBE_POOL), len(set(PROBE_POOL)))
        available = [probe for probe in PROBE_POOL if probe not in {"aesop", "omega"}]
        self.assertEqual(retained_probe_panel(reversed(available)), available)
        with self.assertRaises(ValueError):
            retained_probe_panel([*available, "unfrozen_probe"])

    def test_04_protocol_matches_v01_claim_boundary_and_gates(self) -> None:
        value = build_exp52_protocol(
            created_utc="2026-08-24T00:00:00+00:00",
            source_config_identity_sha256="0" * 64,
            selected_repositories=[f"owner/repo-{index}" for index in range(12)],
            probe_surface_receipt="/frozen/exp52_probe_surface.json",
            probe_surface_receipt_sha256="1" * 64,
            available_probes=PROBE_POOL,
        )
        validate_protocol(value)
        self.assertEqual(value["protocol_version"], EXP52_PROTOCOL_VERSION)
        self.assertEqual(value["design_lock_version"], EXP52_DESIGN_LOCK_VERSION)
        self.assertEqual(value["alignment_version"], ALIGNMENT_VERSION)
        self.assertEqual(value["mechanical_fix_id"], ALIGNMENT_FIX_ID)
        wrong_alignment = dict(value)
        wrong_alignment["alignment_version"] = (
            "experiment51-exp52-scientific-freeze-alignment-fix1"
        )
        wrong_alignment["identity_sha256"] = json_sha256({
            key: item
            for key, item in wrong_alignment.items()
            if key not in {"created_utc", "identity_sha256"}
        })
        with self.assertRaises(ValueError):
            validate_protocol(wrong_alignment)
        self.assertEqual(value["primary_control_rule"]["scope"], "within_root_only")
        self.assertFalse(value["primary_control_rule"]["repository_local_fallback"])
        self.assertEqual(
            value["gates"]["minimum_within_root_control_pairs"], 100
        )
        self.assertEqual(
            value["gates"][
                "total_informative_discordance_B_one_sided_95_upper_lt"
            ],
            0.05,
        )
        self.assertEqual(
            value["execution"]["determinism_audit"]["required_mismatches"], 0
        )
        self.assertIn("both-fail cells are reported and never positive agreement",
                      value["probe_contract"])

    def test_05_module_quoting_is_deterministic(self) -> None:
        self.assertEqual(lean_module_name("Foo/Bar.lean"), "Foo.Bar")
        self.assertEqual(
            lean_module_name("formal-conjectures/Result.lean"),
            "«formal-conjectures».Result",
        )
        for invalid in ("/Foo.lean", "../Foo.lean", "Foo.txt"):
            with self.assertRaises(ValueError):
                lean_module_name(invalid)
        source = source_for("Foo.Bar", ["rfl", "first | rfl | assumption"])
        self.assertIn("import Foo.Bar", source)
        self.assertIn("Lean.MacroM (Lean.TSyntax `tactic)", source)
        self.assertIn("`(tactic| rfl)", source)
        self.assertIn("`(tactic| first | rfl | assumption)", source)
        self.assertNotIn(": Lean.Syntax :=", source)
        self.assertNotIn("run_tac", source)

    def test_06_bridge_does_not_overwrite_protected_extension2(self) -> None:
        freeze = (PACKAGE_ROOT / "freeze_experiment51_scientific.py").read_text(
            encoding="utf-8"
        )
        preflight = (PACKAGE_ROOT / "preflight_exp52_probe_surface.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("external_repository_replication_scientific", (
            PACKAGE_ROOT / "experiment52_protocol.py"
        ).read_text(encoding="utf-8"))
        self.assertIn("validate_extension2_qualification", freeze)
        self.assertIn("legacy_freeze.build_targets", freeze)
        self.assertIn("scientific_candidate_tactics_executed\": 0", freeze)
        self.assertNotIn("legacy_freeze.exp52_protocol", freeze)
        self.assertIn("candidate_tactics_executed\": 0", preflight)
        self.assertIn("theorem_sources_elaborated\": 0", preflight)
        self.assertIn(
            'value.get("alignment_version") == ALIGNMENT_VERSION', preflight
        )
        self.assertIn(
            'value.get("mechanical_fix_id") == ALIGNMENT_FIX_ID', preflight
        )
        self.assertIn("ThreadPoolExecutor", preflight)
        self.assertIn("subprocess.TimeoutExpired", preflight)
        self.assertNotIn("runSyntax", preflight)

    def test_07_falsification_matrix_contains_nine_attacks(self) -> None:
        matrix = (DOCUMENT_ROOT / "EXP52_FALSIFICATION_MATRIX.md").read_text(
            encoding="utf-8"
        )
        import re
        self.assertEqual(len(re.findall(r"^\| \*\*H[1-9]\*\* \|", matrix, re.MULTILINE)), 9)
        for phrase in (
            "Probe degeneracy",
            "Repository concentration",
            "Reconstruction or process artifact",
            "Pair-selection multiplicity",
            "Resource-censoring asymmetry",
        ):
            self.assertIn(phrase, matrix)


if __name__ == "__main__":
    unittest.main(verbosity=2)
