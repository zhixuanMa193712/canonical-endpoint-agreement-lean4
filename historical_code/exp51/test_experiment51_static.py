"""Offline tests for Exp51 contracts.  These tests never invoke Lean."""
from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from experiment51_protocol import *
from freeze_experiment51 import PROBES52
from freeze_experiment51_recruitment import (
    is_fix4_position_parser_failure,
    is_fix8_section_parser_failure,
)
from analyze_experiment51 import analyze_view
from audit_experiment51 import root_indicator
from screen_experiment51_repositories import (
    clear_repository_trace_artifacts,
    recover_fix4_one,
    remove_verified_stale_extractor,
    source_inventory,
    source_line_ending_inventory,
)
from experiment51_trace_runtime import (
    classify_lean_line_endings,
    classify_v427_section_schema,
    decode_v427_position,
    install_v427_position_adapter,
    position_adapter_receipt,
)


class ProtocolTests(unittest.TestCase):
    def test_exp49_candidate_library_identity(self) -> None:
        self.assertEqual(json_sha256(ALTERNATIVE_LIBRARY),
                         "9eea3b178d414ad93cbefadb96fb93f271a26bcb255a723f9d604996a679ad78")
        self.assertEqual(len(ALTERNATIVE_LIBRARY), 32)

    def test_robust_view_is_outcome_independent(self) -> None:
        robust = select_candidate_view(ALTERNATIVE_LIBRARY, "L-mechanism-diverse")
        self.assertNotIn("aesop?", robust)
        self.assertNotIn("exact?", robust)
        self.assertNotIn("all_goals simp", robust)
        self.assertNotIn("all_goals aesop", robust)
        self.assertNotIn("first | rfl | assumption", robust)
        self.assertEqual(len([x for x in robust if genealogy_for(x)["group"] == "simp_engine"]), 1)

    def test_endpoint_payload_is_deterministic_and_strict(self) -> None:
        a = endpoint_payload("⊢ True", "(GOALS ...)", 1)
        b = endpoint_payload("⊢ True", "(GOALS ...)", 1)
        self.assertEqual(a, b)
        self.assertEqual(a["struct"]["value"]["schema"], STRICT_ENDPOINT_SCHEMA)
        self.assertFalse(a["struct"]["value"]["terminal"])

    def test_sampling_is_deterministic(self) -> None:
        rows = [{"file_path": f"F{i // 4}.lean", "full_name": f"T{i}",
                 "target_pos": i, "target_end_pos": i + 1, "theorem_id": str(i)}
                for i in range(80)]
        self.assertEqual(deterministic_sample(rows, "o/r"), deterministic_sample(rows, "o/r"))
        self.assertEqual(len(deterministic_sample(rows, "o/r")), ROOTS_PER_REPOSITORY)

    def test_candidate_frame_excludes_historical_repositories(self) -> None:
        frame = read_json(PACKAGE_ROOT / "repository_candidates.json")
        slugs = {x["slug"] for x in frame["candidates"]}
        self.assertFalse(slugs.intersection(frame["historical_scientific_exclusions"]))
        self.assertGreaterEqual(len(slugs), TARGET_REPOSITORIES)
        self.assertEqual(frame["version"], 2)
        self.assertEqual(len(slugs), len(frame["candidates"]))
        self.assertEqual(next(x["ref"] for x in frame["candidates"]
                              if x["slug"] == "AlexKontorovich/PrimeNumberTheoremAnd"),
                         "6757256")

    def test_exp52_is_frozen_with_bounded_probes(self) -> None:
        self.assertGreaterEqual(len(PROBES52), 8)
        self.assertLessEqual(len(PROBES52), 12)
        self.assertEqual(len(PROBES52), len(set(PROBES52)))

    def test_live_worker_uses_exact_tacticinfo_state(self) -> None:
        source = (PACKAGE_ROOT / "experiment51_live_worker.py").read_text(encoding="utf-8")
        for needle in ("ContextInfo", "mctxBefore", "goalsBefore", "runSyntax"):
            self.assertIn(needle, source)
        self.assertNotIn("requires at least one candidate", source)

    def test_screening_never_updates_dependencies(self) -> None:
        source = (PACKAGE_ROOT / "screen_experiment51_repositories.py").read_text(encoding="utf-8")
        self.assertNotIn('["lake", "update"]', source)
        self.assertIn('"scientific_candidate_tactics_executed": 0', source)

    def test_fix9_pins_runtime_and_disables_trace_reexecution(self) -> None:
        source = (PACKAGE_ROOT / "screen_experiment51_repositories.py").read_text(encoding="utf-8")
        runtime = (PACKAGE_ROOT / "experiment51_trace_runtime.py").read_text(encoding="utf-8")
        requirements = (PACKAGE_ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("lean-dojo==4.20.0", requirements)
        self.assertIn("UPSTREAM_EXTRACTOR_SHA256", runtime)
        self.assertIn("V427_EXTRACTOR_SHA256", runtime)
        self.assertIn("materialized v4.27 extractor hash mismatch", runtime)
        self.assertIn('root / "preflight/trace_runtime.json"', source)
        self.assertIn('"rev-parse", "--verify"', source)
        self.assertIn('["git", "switch", "--detach", resolved]', source)
        self.assertIn('shutil.copytree(lean_prefix, lean_package', source)
        self.assertIn("ThreadPoolExecutor", source)
        self.assertIn("start_new_session=True", source)
        self.assertIn("os.killpg", source)
        self.assertIn("ENUMERATION_WORKER", source)
        self.assertIn("enumerate_frame_isolated", source)
        self.assertIn("recover_fix4_one", source)
        self.assertEqual(QUALIFICATION_ENUMERATION_ISOLATION,
                         "one-fresh-python-process-per-repository")
        self.assertEqual(QUALIFICATION_REPOSITORY_WORKERS, 26)
        self.assertEqual(QUALIFICATION_THREADS_PER_REPOSITORY, 2)
        self.assertEqual(QUALIFICATION_GLOBAL_TRACE_PROCESS_CAP, 52)
        self.assertEqual(
            QUALIFICATION_REPOSITORY_WORKERS * QUALIFICATION_THREADS_PER_REPOSITORY,
            QUALIFICATION_GLOBAL_TRACE_PROCESS_CAP,
        )
        self.assertIn('"STOP: minimum repository, parser-compatibility', source)
        preflight = (PACKAGE_ROOT / "preflight_experiment51.py").read_text(encoding="utf-8")
        self.assertIn("screening preflight prohibited", preflight)

    def test_fix9_requires_all_preserved_zero_candidate_diagnostics(self) -> None:
        source = (PACKAGE_ROOT / "freeze_experiment51_recruitment.py").read_text(encoding="utf-8")
        self.assertIn("validate_fix0_diagnostic", source)
        self.assertIn("validate_fix1_diagnostic", source)
        self.assertIn("validate_fix2_diagnostic", source)
        self.assertIn("validate_fix3_diagnostic", source)
        self.assertIn("validate_fix4_diagnostic", source)
        self.assertIn("validate_fix5_diagnostic", source)
        self.assertIn("validate_fix6_diagnostic", source)
        self.assertIn("validate_fix7_diagnostic", source)
        self.assertIn("validate_fix8_diagnostic", source)
        self.assertIn('"experiment51-zero-candidate-recruitment-v1"', source)
        self.assertIn('"experiment51-zero-candidate-recruitment-fix1"', source)
        self.assertIn('summary.get("passed") == 0', source)
        self.assertIn('"superseded_exp51_fix0"', source)
        self.assertIn('"superseded_exp51_fix1"', source)
        self.assertIn('"superseded_exp51_fix2"', source)
        self.assertIn('"superseded_exp51_fix3"', source)
        self.assertIn('"superseded_exp51_fix4"', source)
        self.assertIn('"superseded_exp51_fix5"', source)
        self.assertIn('"superseded_exp51_fix6"', source)
        self.assertIn('"superseded_exp51_fix7"', source)
        self.assertIn('"superseded_exp51_fix8"', source)

    def test_fix9_capacity_gate_matches_recovery_workload(self) -> None:
        source = (PACKAGE_ROOT / "preflight_experiment51.py").read_text(encoding="utf-8")
        self.assertEqual(RECOVERY_CAPACITY_PROFILE, "four-python-parser-trace-reuse-v1")
        self.assertIn('"required_cpus": 8', source)
        self.assertIn('"required_memory_total_gb": 64', source)
        self.assertIn('"required_memory_available_gb": 32', source)
        self.assertIn('"required_disk_free_gb": 100', source)
        self.assertIn('"four isolated Python AST parsers; zero Lean trace processes"', source)

    def test_v427_position_adapter_is_strict(self) -> None:
        self.assertEqual(decode_v427_position({"byteIdx": 0}), 0)
        self.assertEqual(decode_v427_position({"byteIdx": 41}), 41)
        self.assertEqual(decode_v427_position(7), 7)
        for invalid in (
            {"byteIdx": -1}, {"byteIdx": True}, {"byteIdx": 2, "raw": 2},
            {"raw": 2}, -1, True, "2", None,
        ):
            with self.assertRaises((TypeError, ValueError)):
                decode_v427_position(invalid)

    def test_fix9_line_ending_whitelist_is_exact(self) -> None:
        self.assertEqual(classify_lean_line_endings(b"a\nb\n")["schema"], "lf-only")
        crlf = classify_lean_line_endings(b"a\r\nb\r\n")
        self.assertEqual(crlf["schema"], "standard-crlf")
        self.assertEqual(crlf["crlf_lines"], 2)
        for invalid in (b"a\rb", b"a\r\nb\n"):
            with self.assertRaises(TypeError):
                classify_lean_line_endings(invalid)

    def test_fix9_section_whitelist_accepts_only_observed_v427_shapes(self) -> None:
        def source_info(start: int, end: int) -> dict:
            return {"original": {
                "leading": "", "pos": {"byteIdx": start},
                "trailing": " ", "endPos": {"byteIdx": end},
            }}

        null = {"node": {"kind": "null", "info": "none", "args": []}}
        def atom_slot(*values: str) -> dict:
            return {"node": {"kind": "null", "info": "none", "args": [
                {"atom": {"val": value, "info": source_info(0, 1)}}
                for value in values
            ]}}

        prefix = [
            {"node": {
                "kind": "Lean.Parser.Command.sectionHeader", "info": "none",
                "args": [deepcopy(null) for _ in range(4)],
            }},
            {"atom": {"val": "section", "info": source_info(0, 7)}},
        ]
        unnamed = {
            "kind": "Lean.Parser.Command.section", "info": "none",
            "args": [*deepcopy(prefix), deepcopy(null)],
        }
        named = deepcopy(unnamed)
        named["args"][2]["node"]["args"] = [{"ident": {
            "val": "S", "rawVal": "S", "preresolved": [],
            "info": source_info(8, 9),
        }}]
        self.assertEqual(classify_v427_section_schema(unnamed),
                         "v427-unnamed-three-child")
        self.assertEqual(classify_v427_section_schema(named),
                         "v427-named-three-child")
        modifier_cases = {
            "v427-noncomputable-unnamed-three-child": (
                atom_slot(), atom_slot(), atom_slot("noncomputable"), atom_slot(),
            ),
            "v427-public-unnamed-three-child": (
                atom_slot(), atom_slot("public"), atom_slot(), atom_slot(),
            ),
            "v427-public-meta-unnamed-three-child": (
                atom_slot(), atom_slot("public"), atom_slot(), atom_slot("meta"),
            ),
            "v427-expose-public-unnamed-three-child": (
                atom_slot("@[", "expose", "]"), atom_slot("public"),
                atom_slot(), atom_slot(),
            ),
            "v427-expose-public-meta-unnamed-three-child": (
                atom_slot("@[", "expose", "]"), atom_slot("public"),
                atom_slot(), atom_slot("meta"),
            ),
        }
        for expected, slots in modifier_cases.items():
            modified = deepcopy(unnamed)
            modified["args"][0]["node"]["args"] = list(slots)
            self.assertEqual(classify_v427_section_schema(modified), expected)
        invalid = deepcopy(unnamed)
        invalid["args"][0]["node"]["args"][1] = atom_slot("private")
        with self.assertRaises(TypeError):
            classify_v427_section_schema(invalid)
        invalid = deepcopy(named)
        invalid["args"][0]["node"]["args"][2] = atom_slot("noncomputable")
        with self.assertRaises(TypeError):
            classify_v427_section_schema(invalid)
        invalid = deepcopy(named)
        invalid["args"][1]["atom"]["extra"] = True
        with self.assertRaises(TypeError):
            classify_v427_section_schema(invalid)
        invalid = deepcopy(named)
        invalid["args"][0]["node"]["args"].pop()
        with self.assertRaises(TypeError):
            classify_v427_section_schema(invalid)

    def test_fix9_fix2_adapter_normalizes_section_and_crlf_byte_width(self) -> None:
        if importlib.util.find_spec("lean_dojo") is None:
            self.skipTest("pinned lean-dojo distribution is not installed in this interpreter")
        install_v427_position_adapter()
        from lean_dojo.data_extraction.ast import CommandSectionNode
        from lean_dojo.data_extraction.lean import LeanFile, Pos

        def source_info(start: int, end: int) -> dict:
            return {"original": {
                "leading": "", "pos": {"byteIdx": start},
                "trailing": " ", "endPos": {"byteIdx": end},
            }}

        null = {"node": {"kind": "null", "info": "none", "args": []}}
        raw = {
            "kind": "Lean.Parser.Command.section", "info": "none",
            "args": [
                {"node": {
                    "kind": "Lean.Parser.Command.sectionHeader", "info": "none",
                    "args": [deepcopy(null) for _ in range(4)],
                }},
                {"atom": {"val": "section", "info": source_info(0, 7)}},
                {"node": {"kind": "null", "info": "none", "args": [
                    {"ident": {
                        "val": "S", "rawVal": "S", "preresolved": [],
                        "info": source_info(8, 9),
                    }},
                ]}},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / "A.lean"
            source.write_bytes(b"section S\r\n#check S\r\n")
            lean_file = LeanFile(root, Path("A.lean"))
            node = CommandSectionNode.from_data(raw, lean_file)
            self.assertEqual(node.name, "S")
            self.assertEqual(len(node.children), 2)
            self.assertEqual(lean_file.num_bytes, [10, 9])
            self.assertEqual(lean_file.code, ["section S", "#check S"])
            self.assertEqual(lean_file.convert_pos({"byteIdx": 10}), Pos(2, 1))
            modified = deepcopy(raw)
            modified["args"][2] = deepcopy(null)
            modified["args"][0]["node"]["args"] = [
                {"node": {"kind": "null", "info": "none", "args": [
                    {"atom": {"val": value, "info": source_info(0, 1)}}
                    for value in values
                ]}}
                for values in (("@[", "expose", "]"), ("public",), (), ("meta",))
            ]
            modified_node = CommandSectionNode.from_data(modified, lean_file)
            self.assertIsNone(modified_node.name)
            self.assertEqual(len(modified_node.children), 2)
            receipt = position_adapter_receipt()
            self.assertGreaterEqual(
                receipt["section_adapter"]["header_counters"]["expose_public_meta"],
                1,
            )

    def test_fix9_fix2_separates_checkout_and_traced_crlf_counts(self) -> None:
        self.assertEqual(
            PARSER_COMPATIBILITY_EXPECTED["traced_standard_crlf_files"], 5
        )
        self.assertEqual(
            PARSER_COMPATIBILITY_EXPECTED["traced_standard_crlf_lines"], 2470
        )
        self.assertEqual(CHECKOUT_LINE_ENDING_EXPECTED["standard_crlf_files"], 7)
        self.assertEqual(CHECKOUT_LINE_ENDING_EXPECTED["standard_crlf_lines"], 3460)
        self.assertEqual(
            sum(PARSER_COMPATIBILITY_EXPECTED[key] for key in (
                "plain_header_sections",
                "noncomputable_header_sections",
                "public_header_sections",
                "public_meta_header_sections",
                "expose_public_header_sections",
                "expose_public_meta_header_sections",
            )),
            742,
        )
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            (project / "A.lean").write_bytes(b"a\r\nb\r\n")
            (project / "B.lean").write_bytes(b"c\nd\n")
            inventory, _ = source_inventory(project)
            measurement = source_line_ending_inventory(project, inventory)
            self.assertEqual(measurement["source_files_scanned"], 2)
            self.assertEqual(measurement["standard_crlf_files"], 1)
            self.assertEqual(measurement["standard_crlf_lines"], 2)
            self.assertEqual(measurement["lf_only_files"], 1)
            self.assertEqual(measurement["line_ending_rejections"], 0)

    def test_fix4_parser_failure_signature_is_narrow(self) -> None:
        self.assertTrue(is_fix4_position_parser_failure(
            "lean_file.convert_pos(start) TypeError: '>' not supported between "
            "instances of 'int' and 'dict'"
        ))
        self.assertFalse(is_fix4_position_parser_failure("FileNotFoundError: /tmp/x"))
        self.assertFalse(is_fix4_position_parser_failure(
            "TypeError: not supported between instances of 'int' and 'dict'"
        ))

    def test_fix9_fix1_section_failure_signature_matches_archived_traceback(self) -> None:
        archived = (
            'File "/home/music/miniconda3/envs/leandojo_v2_env/lib/python3.11/'
            'site-packages/lean_dojo/data_extraction/ast.py", line 1480, in from_data\n'
            '    assert len(children) == 2\n'
            'AssertionError'
        )
        self.assertTrue(is_fix8_section_parser_failure(archived))
        self.assertFalse(is_fix8_section_parser_failure(
            "CommandSectionNode assert len(children) == 2 AssertionError"
        ))
        self.assertFalse(is_fix8_section_parser_failure(
            archived.replace("line 1480", "line 1481")
        ))

    def test_fix9_recovery_never_runs_build_or_trace(self) -> None:
        source = inspect.getsource(recover_fix4_one)
        self.assertNotIn("trace_project(", source)
        self.assertNotIn('"lake"', source)
        self.assertNotIn('"lean"', source)
        self.assertIn("validate_fix4_trace_reuse", source)
        self.assertIn("enumerate_frame_isolated", source)

    def test_fix9_freezes_single_parser_before_any_leandojo_import(self) -> None:
        runtime = (PACKAGE_ROOT / "experiment51_trace_runtime.py").read_text(encoding="utf-8")
        body = runtime.split("def import_traced_repo():", 1)[1]
        self.assertLess(body.index('os.environ["NUM_PROCS"] = "2"'),
                        body.index("install_v427_position_adapter()"))
        self.assertLess(body.index('os.environ["LOAD_USED_PACKAGES_ONLY"] = "1"'),
                        body.index("install_v427_position_adapter()"))
        self.assertIn("lean_dojo_constants.NUM_PROCS != 2", body)
        self.assertIn("traced_data.NUM_WORKERS != 1", body)
        self.assertEqual(PARSER_EXECUTION_PROFILE,
                         "single-process-in-memory-v427-adapter-no-ray-v1")

    def test_fix9_parser_gate_rejects_ray_or_cross_process_adapter(self) -> None:
        worker = (PACKAGE_ROOT / "experiment51_enumeration_worker.py").read_text(encoding="utf-8")
        preflight = (PACKAGE_ROOT / "preflight_experiment51.py").read_text(encoding="utf-8")
        for needle in (
            'parser_execution.get("num_workers") == 1',
            'parser_execution.get("ray_initialized") is False',
            'parser_execution.get("adapter_process_pid") == os.getpid()',
        ):
            self.assertIn(needle, worker)
        self.assertIn('parser_execution.get("adapter_process_pid") == worker.get("worker_pid")',
                      preflight)
        self.assertIn('"enumeration_worker_pid": worker["worker_pid"]', preflight)

    def test_fix9_recovery_mapping_and_minimum_gate_are_frozen(self) -> None:
        screen = (PACKAGE_ROOT / "screen_experiment51_repositories.py").read_text(encoding="utf-8")
        self.assertIn('"parser_execution_profile": PARSER_EXECUTION_PROFILE', screen)
        self.assertIn('"parser_compatibility_schema": V427_PARSER_COMPATIBILITY_SCHEMA', screen)
        self.assertIn('"parser_compatibility_expected": PARSER_COMPATIBILITY_EXPECTED', screen)
        self.assertIn('"checkout_line_endings_expected": CHECKOUT_LINE_ENDING_EXPECTED', screen)
        self.assertIn('passed >= MIN_REPOSITORIES', screen)
        self.assertEqual(PARSER_COMPATIBILITY_EXPECTED["section_nodes"], 742)
        self.assertEqual(PARSER_COMPATIBILITY_EXPECTED["traced_standard_crlf_lines"], 2470)
        self.assertEqual(CHECKOUT_LINE_ENDING_EXPECTED["standard_crlf_lines"], 3460)
        self.assertIn("checkout_line_endings_exact", screen)

    def test_fix9_replays_all_traces_and_exactly_controls_fix8_successes(self) -> None:
        screen = (PACKAGE_ROOT / "screen_experiment51_repositories.py").read_text(encoding="utf-8")
        preflight = (PACKAGE_ROOT / "preflight_experiment51.py").read_text(encoding="utf-8")
        self.assertEqual(FIX8_FRAME_CONTROLS, {
            "bergmannjg/Regex": 333,
            "dissensus-ai/lean-formalizations": 218,
        })
        self.assertIn("fix8_exact_frame_control", screen)
        self.assertIn('len(reusable_rows) == 15', screen)
        self.assertIn("PARSER_ADAPTER_PREFLIGHT_REPOSITORIES", preflight)
        self.assertIn('"AfonsoBitoque/LeanServer"',
                      (PACKAGE_ROOT / "experiment51_protocol.py").read_text(encoding="utf-8"))

    def test_fix9_export_preserves_fix8_diagnostic(self) -> None:
        source = (PACKAGE_ROOT / "export_experiment51_bundle.py").read_text(encoding="utf-8")
        self.assertIn('cfg["source"]["superseded_exp51_fix8"]', source)
        self.assertIn("source_controls/exp51_fix8/source_code_package.zip", source)

    def test_enumeration_worker_is_zero_candidate_and_fresh_process(self) -> None:
        worker = (PACKAGE_ROOT / "experiment51_enumeration_worker.py").read_text(encoding="utf-8")
        screen = (PACKAGE_ROOT / "screen_experiment51_repositories.py").read_text(encoding="utf-8")
        self.assertIn('"scientific_candidate_tactics_executed": 0', worker)
        self.assertIn("os.getpid()", worker)
        self.assertIn("run_cmd_isolated", screen)
        self.assertIn("input_identity_sha256", screen)

    def test_unknown_stale_extractor_is_never_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ExtractData.lean"
            path.write_text("user-authored or unknown content", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "refusing to remove non-frozen"):
                remove_verified_stale_extractor(path)
            self.assertTrue(path.is_file())

    def test_fresh_trace_cleanup_is_scoped_to_generated_ir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            astp = project / ".lake/build/ir/A.ast.json"
            depp = project / ".lake/build/ir/A.dep_paths"
            source = project / "A.lean"
            for path, text in ((astp, "{}"), (depp, "Init"), (source, "theorem a : True := by trivial")):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            receipt = clear_repository_trace_artifacts(project)
            self.assertEqual(receipt["removed_generated_files"], 2)
            self.assertFalse(astp.exists())
            self.assertFalse(depp.exists())
            self.assertTrue(source.exists())

    def test_independent_audit_does_not_import_main_analysis(self) -> None:
        source = (PACKAGE_ROOT / "audit_experiment51.py").read_text(encoding="utf-8")
        imports = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertNotIn("analyze_experiment51", imports)

    def test_export_requires_independent_audit_gate(self) -> None:
        source = (PACKAGE_ROOT / "export_experiment51_bundle.py").read_text(encoding="utf-8")
        self.assertIn('audit.get("audit_pass") is not True', source)
        self.assertIn('"independent_reconstruction_audit_pass": True', source)

    def test_root_indicator_requires_distinct_heads_and_noninitial_strict_endpoint(self) -> None:
        initial = {"struct": {"sha256": "initial"}}
        def branch(tactic: str, head: str, family: str, endpoint: str) -> dict:
            return {"tactic": tactic, "head": head, "family": family,
                    "executable": True, "terminal": False,
                    "endpoints": {"struct": {"sha256": endpoint}}}
        row = {"worker_ok": True, "candidate_order": ["simp", "simpa", "rfl"],
               "initial_endpoints": initial,
               "candidates": [branch("simp", "simp", "simplification", "shared"),
                              branch("simpa", "simpa", "simplification", "shared"),
                              branch("rfl", "rfl", "reflexive_closure", "initial")]}
        result = analyze_view(row, row["candidate_order"])
        self.assertTrue(result["Y"])
        self.assertTrue(result["Y_nonterminal"])
        self.assertFalse(result["Y_cross_family"])

    def test_independent_audit_indicator_matches_primary_analysis(self) -> None:
        row = {
            "worker_ok": True,
            "candidate_order": ["simp", "aesop", "rfl"],
            "initial_endpoints": {"struct": {"sha256": "initial"}},
            "candidates": [
                {"tactic": "simp", "head": "simp", "family": "simplification",
                 "executable": True, "terminal": False,
                 "endpoints": {"struct": {"sha256": "shared"}}},
                {"tactic": "aesop", "head": "aesop", "family": "automation",
                 "executable": True, "terminal": False,
                 "endpoints": {"struct": {"sha256": "shared"}}},
                {"tactic": "rfl", "head": "rfl", "family": "reflexive_closure",
                 "executable": False},
            ],
        }
        primary = analyze_view(row, row["candidate_order"])
        audited_y, audited_nonterminal, audited_pairs = root_indicator(
            row, row["candidate_order"]
        )
        self.assertEqual(audited_y, primary["Y"])
        self.assertEqual(audited_nonterminal, primary["Y_nonterminal"])
        self.assertEqual(audited_pairs,
                         {tuple(x) for x in primary["cross_head_pairs"]})


if __name__ == "__main__":
    unittest.main()
