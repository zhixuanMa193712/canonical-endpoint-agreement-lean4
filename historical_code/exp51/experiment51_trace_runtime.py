"""Pinned zero-candidate tracing runtime for Exp51 recruitment fix9 fix3.

LeanDojo 4.20.0 supplies the Python AST parser.  Its packaged Lean extractor
predates Lean v4.27, so this module applies the already archived v4.27 adapter
as eight deterministic textual transformations.  Both the upstream input and
the materialized output are content-addressed; no unverified extractor is run.
Strict in-memory adapters cover only the frozen v4.27 position, section, and
standard-CRLF schemas.  CRLF source is represented with Lean's observed
LF-normalized byte-index semantics.  The adapters never edit the installed
parser or a repository.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import sys
from copy import deepcopy
from functools import wraps
from pathlib import Path
from typing import Any

from experiment51_protocol import (
    V427_PARSER_COMPATIBILITY_SCHEMA,
    V427_POSITION_ADAPTER_SCHEMA,
)

LEAN_DOJO_DISTRIBUTION = "lean-dojo"
LEAN_DOJO_VERSION = "4.20.0"
UPSTREAM_EXTRACTOR_SHA256 = "c3bd988d2e14e05b89dceee8e551b278d191383ed3c74c14d4d1754b0a38d610"
V427_EXTRACTOR_SHA256 = "b50bebdef8adde06d1f6948edc0ac52f67dd8b40045df72290a1f225049ffc50"
LEAN_DOJO_SOURCE_LEDGER_SHA256 = "25413fc650b9990018db1657f6e03b75cf26245de2c72f872de7e8f3fe7d4953"
LEAN_PY_SHA256 = "7b2e2905e733ec674bf704536087b0acfb2ba6e4b6f43f114fd98eb51e1a3d47"
AST_PY_SHA256 = "d8aee2af9cae0a35732a25e49c20adaf41bef265c60bd8c297445db03f866edc"
_POSITION_ADAPTER_STATE: dict[str, Any] | None = None


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


TRANSFORMS = [
    (
        "instance : ToJson Substring where\n"
        "  toJson s := toJson s.toString\n\n"
        "instance : ToJson String.Pos where\n"
        "  toJson n := toJson n.1\n\n"
        "deriving instance ToJson for SourceInfo",
        "instance : ToJson Substring.Raw where\n"
        "  toJson s := toJson s.toString\n\n"
        "instance : ToJson String.Pos.Raw where\n"
        "  toJson n := toJson n.1\n\n"
        "deriving instance Lean.ToJson for String.Pos.Raw\n"
        "deriving instance ToJson for SourceInfo",
    ),
    (
        "  pos: String.Pos      -- Start position of the tactic.\n"
        "  endPos: String.Pos   -- End position of the tactic.",
        "  pos: String.Pos.Raw      -- Start position of the tactic.\n"
        "  endPos: String.Pos.Raw   -- End position of the tactic.",
    ),
    ("    return (← fmt).pretty.trim\n",
     "    return (← fmt).pretty.trimAscii.toString\n"),
    (
        "  if let some p := relativeTo path leanLib then\n"
        "    path := packagesDir / \"lean4/src/lean\" / p\n"
        "  assert! ← path.pathExists",
        "  if let some p := relativeTo path leanLib then\n"
        "    path := packagesDir / \"lean4/src/lean\" / p\n\n"
        "  let cwd ← IO.currentDir\n"
        "  if path.isAbsolute then\n"
        "    match relativeTo path cwd with\n"
        "    | some relativePath => path := relativePath\n"
        "    | none => pure ()\n\n"
        "  assert! ← path.pathExists",
    ),
    (
        "  while defPath.startsWith \"./\" do\n"
        "    defPath := defPath.drop 2\n",
        "  while defPath.startsWith \"./\" do\n"
        "    defPath := defPath.drop 2 |>.toString\n",
    ),
    (
        "def getImports (header: TSyntax `Lean.Parser.Module.header) : IO String := do\n"
        "  -- Similar to `lean --deps` in Lean 3.\n"
        "  let mut s := \"\"\n\n"
        "  for dep in headerToImports header do\n"
        "    -- let oleanPath ← findOLean dep.module\n"
        "    let leanPath ← Path.findLean dep.module\n"
        "    s := s ++ \"\\n\" ++ leanPath.toString\n"
        "    /-\n"
        "    if oleanPath.isRelative then\n"
        "      let leanPath := Path.toSrcDir! oleanPath \"lean\"\n"
        "      assert! ← leanPath.pathExists\n"
        "      s := s ++ \"\\n\" ++ leanPath.toString\n"
        "    else if ¬(oleanPath.toString.endsWith \"/lib/lean/Init.olean\") then\n"
        "      let mut p := (Path.packagesDir / \"lean4\").toString ++ FilePath.pathSeparator.toString\n"
        "      let mut found := false\n"
        "      for c in (oleanPath.withExtension \"lean\").components do\n"
        "        if c == \"lib\" then\n"
        "          found := true\n"
        "          p := p ++ \"src\"\n"
        "          continue\n"
        "        if found then\n"
        "          p := p ++ FilePath.pathSeparator.toString ++ c\n"
        "      p := p.replace \"/lean4/src/lean/Lake\" \"/lean4/src/lean/lake/Lake\"\n"
        "      assert! ← FilePath.mk p |>.pathExists\n"
        "      s := s ++ \"\\n\" ++ p\n"
        "  -/\n\n"
        "  return s.trim\n\n\n",
        "",
    ),
    (
        "  IO.FS.writeFile dep_path (← getImports header)\n",
        "  let mut s := \"\"\n\n"
        "  for dep in headerToImports header do\n"
        "    let leanPath ← Path.findLean dep.module\n"
        "    s := s ++ \"\\n\" ++ leanPath.toString\n"
        "  IO.FS.writeFile dep_path s.trimAscii.toString\n\n",
    ),
    (
        "    println! \"Extracting data at {cwd}\"\n\n",
        "    \n",
    ),
]


def _installed_paths() -> tuple[Path, Path]:
    try:
        version = importlib.metadata.version(LEAN_DOJO_DISTRIBUTION)
    except importlib.metadata.PackageNotFoundError as exc:
        raise FileNotFoundError(
            "lean-dojo==4.20.0 is absent; run: python -m pip install -r "
            "experiment51_external_repository_replication/requirements.txt"
        ) from exc
    if version != LEAN_DOJO_VERSION:
        raise ValueError(f"requires lean-dojo=={LEAN_DOJO_VERSION}, found {version}")
    spec = importlib.util.find_spec("lean_dojo")
    if spec is None or not spec.origin:
        raise FileNotFoundError("lean-dojo distribution exists but lean_dojo is not importable")
    package = Path(spec.origin).resolve().parent
    upstream = package / "data_extraction/ExtractData.lean"
    if not upstream.is_file():
        raise FileNotFoundError(upstream)
    return package, upstream


def materialized_extractor() -> tuple[str, dict[str, Any]]:
    package, upstream = _installed_paths()
    source = upstream.read_text(encoding="utf-8")
    if _sha256_text(source) != UPSTREAM_EXTRACTOR_SHA256:
        raise ValueError("lean-dojo 4.20.0 extractor content differs from the frozen input")
    for index, (old, new) in enumerate(TRANSFORMS, 1):
        count = source.count(old)
        if count != 1:
            raise ValueError(f"v4.27 extractor transform {index} matched {count} times")
        source = source.replace(old, new)
    # The archived adapter has one blank line at these three splice points.
    for old, new in (
        ("open Traversal\n\n\n/--", "open Traversal\n\n/--"),
        ("s.trimAscii.toString\n\n\n\nend LeanDojo",
         "s.trimAscii.toString\n\n\nend LeanDojo"),
    ):
        if source.count(old) != 1:
            raise ValueError("v4.27 extractor whitespace normalization failed")
        source = source.replace(old, new)
    digest = _sha256_text(source)
    if digest != V427_EXTRACTOR_SHA256:
        raise ValueError(f"materialized v4.27 extractor hash mismatch: {digest}")
    parser_files = sorted(
        path for path in package.rglob("*")
        if path.is_file() and path.suffix in {".py", ".lean"}
    )
    source_ledger = [
        {
            "path": path.relative_to(package).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
        for path in parser_files
    ]
    ledger_sha256 = hashlib.sha256(json.dumps(
        source_ledger, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    if ledger_sha256 != LEAN_DOJO_SOURCE_LEDGER_SHA256:
        raise ValueError(f"lean-dojo 4.20.0 source ledger differs: {ledger_sha256}")
    receipt = {
        "runtime_version": "exp51-trace-runtime-lean-dojo-4.20.0-v427-adapter-v3",
        "lean_dojo_version": LEAN_DOJO_VERSION,
        "lean_dojo_package": str(package),
        "upstream_extractor": str(upstream),
        "upstream_extractor_sha256": UPSTREAM_EXTRACTOR_SHA256,
        "v427_extractor_sha256": V427_EXTRACTOR_SHA256,
        "lean_dojo_source_files": len(source_ledger),
        "lean_dojo_source_ledger_sha256": ledger_sha256,
        "lean_dojo_source_ledger_exact": True,
        "parser_files": source_ledger,
    }
    return source, receipt


def write_extractor(path: Path) -> dict[str, Any]:
    source, receipt = materialized_extractor()
    path.write_text(source, encoding="utf-8")
    if hashlib.sha256(path.read_bytes()).hexdigest() != V427_EXTRACTOR_SHA256:
        raise ValueError("written v4.27 extractor changed")
    return receipt


def decode_v427_position(value: Any, counters: dict[str, int] | None = None) -> int:
    """Decode only the frozen Lean 4.27 String.Pos.Raw JSON representation."""
    if type(value) is int:
        if value < 0:
            raise ValueError(f"negative Lean source position: {value}")
        if counters is not None:
            counters["legacy_integer"] += 1
        return value
    if isinstance(value, dict) and set(value) == {"byteIdx"}:
        byte_idx = value["byteIdx"]
        if type(byte_idx) is not int or byte_idx < 0:
            raise TypeError(f"invalid Lean 4.27 byteIdx position: {value!r}")
        if counters is not None:
            counters["v427_byteIdx"] += 1
        return byte_idx
    if counters is not None:
        counters["rejected"] += 1
    raise TypeError(f"unsupported Lean source position schema: {value!r}")


def classify_lean_line_endings(raw: bytes) -> dict[str, int | str]:
    """Accept only LF-only bytes or a uniform, standard CRLF byte stream."""
    crlf = raw.count(b"\r\n")
    bare_cr = raw.count(b"\r") - crlf
    bare_lf = raw.count(b"\n") - crlf
    if bare_cr:
        raise TypeError(f"unsupported bare carriage-return source schema: bare_cr={bare_cr}")
    if crlf and bare_lf:
        raise TypeError(
            "unsupported mixed LF/CRLF source schema: "
            f"crlf={crlf} bare_lf={bare_lf}"
        )
    return {
        "schema": "standard-crlf" if crlf else "lf-only",
        "crlf_lines": crlf,
        "bare_lf_lines": bare_lf,
        "bare_cr": bare_cr,
    }


def _exact_raw_position(value: Any) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == {"byteIdx"}
        and type(value["byteIdx"]) is int
        and value["byteIdx"] >= 0
    )


def _exact_original_source_info(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"original"}:
        return False
    original = value["original"]
    return bool(
        isinstance(original, dict)
        and set(original) == {"leading", "pos", "trailing", "endPos"}
        and isinstance(original["leading"], str)
        and isinstance(original["trailing"], str)
        and _exact_raw_position(original["pos"])
        and _exact_raw_position(original["endPos"])
    )


def _exact_null_wrapper(value: Any, child_count: int) -> bool:
    if not isinstance(value, dict) or set(value) != {"node"}:
        return False
    node = value["node"]
    return bool(
        isinstance(node, dict)
        and set(node) == {"kind", "info", "args"}
        and node["kind"] == "null"
        and node["info"] == "none"
        and isinstance(node["args"], list)
        and len(node["args"]) == child_count
    )


def _exact_null_atom_values(value: Any) -> tuple[str, ...] | None:
    """Return exact atom values from one null header slot, or reject it."""
    if not isinstance(value, dict) or set(value) != {"node"}:
        return None
    node = value["node"]
    if not (
        isinstance(node, dict)
        and set(node) == {"kind", "info", "args"}
        and node["kind"] == "null"
        and node["info"] == "none"
        and isinstance(node["args"], list)
    ):
        return None
    values: list[str] = []
    for child in node["args"]:
        if not (
            isinstance(child, dict)
            and set(child) == {"atom"}
            and isinstance(child["atom"], dict)
            and set(child["atom"]) == {"val", "info"}
            and isinstance(child["atom"]["val"], str)
            and _exact_original_source_info(child["atom"]["info"])
        ):
            return None
        values.append(child["atom"]["val"])
    return tuple(values)


_V427_SECTION_HEADER_PATTERNS: dict[str, tuple[tuple[str, ...], ...]] = {
    "plain": ((), (), (), ()),
    "noncomputable": ((), (), ("noncomputable",), ()),
    "public": ((), ("public",), (), ()),
    "public-meta": ((), ("public",), (), ("meta",)),
    "expose-public": (("@[", "expose", "]"), ("public",), (), ()),
    "expose-public-meta": (
        ("@[", "expose", "]"), ("public",), (), ("meta",),
    ),
}


def classify_v427_section_schema(node_data: Any) -> str:
    """Classify the seven exact three-child layouts observed in 742 nodes."""
    if not isinstance(node_data, dict):
        raise TypeError("Lean section payload is not a dictionary")
    args = node_data.get("args")
    if isinstance(args, list) and len(args) == 2:
        return "legacy-two-child"
    valid_prefix = bool(
        set(node_data) == {"kind", "info", "args"}
        and node_data["kind"] == "Lean.Parser.Command.section"
        and node_data["info"] == "none"
        and isinstance(args, list)
        and len(args) == 3
        and isinstance(args[0], dict)
        and set(args[0]) == {"node"}
        and isinstance(args[0]["node"], dict)
        and set(args[0]["node"]) == {"kind", "info", "args"}
        and args[0]["node"]["kind"] == "Lean.Parser.Command.sectionHeader"
        and args[0]["node"]["info"] == "none"
        and isinstance(args[0]["node"]["args"], list)
        and len(args[0]["node"]["args"]) == 4
        and isinstance(args[1], dict)
        and set(args[1]) == {"atom"}
        and isinstance(args[1]["atom"], dict)
        and set(args[1]["atom"]) == {"val", "info"}
        and args[1]["atom"]["val"] == "section"
        and _exact_original_source_info(args[1]["atom"]["info"])
        and isinstance(args[2], dict)
        and _exact_null_wrapper(args[2], len(args[2].get("node", {}).get("args", [])))
        and len(args[2]["node"]["args"]) in {0, 1}
    )
    if not valid_prefix:
        raise TypeError("unsupported Lean 4.27 section raw schema")
    header_values = tuple(
        _exact_null_atom_values(item) for item in args[0]["node"]["args"]
    )
    if any(value is None for value in header_values):
        raise TypeError("unsupported Lean 4.27 section-header slot schema")
    header_pattern = next(
        (name for name, pattern in _V427_SECTION_HEADER_PATTERNS.items()
         if header_values == pattern),
        None,
    )
    if header_pattern is None:
        raise TypeError("unsupported Lean 4.27 section-header modifier combination")
    optional_children = args[2]["node"]["args"]
    if not optional_children:
        name_schema = "unnamed"
    else:
        optional = optional_children[0]
        valid_ident = bool(
            isinstance(optional, dict)
            and set(optional) == {"ident"}
            and isinstance(optional["ident"], dict)
            and set(optional["ident"]) == {"val", "rawVal", "preresolved", "info"}
            and optional["ident"]["preresolved"] == []
            and isinstance(optional["ident"]["val"], str)
            and isinstance(optional["ident"]["rawVal"], str)
            and _exact_original_source_info(optional["ident"]["info"])
        )
        if not valid_ident:
            raise TypeError("unsupported Lean 4.27 named-section identifier schema")
        name_schema = "named"
    if header_pattern != "plain" and name_schema != "unnamed":
        raise TypeError("modified named section was absent from the frozen 742-node frame")
    if header_pattern == "plain":
        return f"v427-{name_schema}-three-child"
    return f"v427-{header_pattern}-{name_schema}-three-child"


def install_v427_position_adapter() -> dict[str, Any]:
    """Patch the pinned parser in memory; never edit the installed distribution."""
    global _POSITION_ADAPTER_STATE
    if _POSITION_ADAPTER_STATE is not None:
        return position_adapter_receipt()
    package, _ = _installed_paths()
    # Revalidate the complete distribution ledger as well as the two files that
    # define source-position parsing before changing behavior in memory.
    materialized_extractor()
    lean_py = package / "data_extraction/lean.py"
    ast_py = package / "data_extraction/ast.py"
    observed_hashes = {
        "lean.py": hashlib.sha256(lean_py.read_bytes()).hexdigest(),
        "ast.py": hashlib.sha256(ast_py.read_bytes()).hexdigest(),
    }
    if observed_hashes != {"lean.py": LEAN_PY_SHA256, "ast.py": AST_PY_SHA256}:
        raise ValueError(f"pinned LeanDojo parser files changed: {observed_hashes}")

    from lean_dojo.data_extraction import ast as ast_module  # type: ignore
    from lean_dojo.data_extraction.ast import (  # type: ignore
        AtomNode,
        CommandSectionNode,
        IdentNode,
        NullNode,
        OtherNode,
    )
    from lean_dojo.data_extraction.lean import LeanFile  # type: ignore

    original_convert_pos = LeanFile.convert_pos
    original_post_init = LeanFile.__post_init__
    original_section_from_data = CommandSectionNode.from_data.__func__
    if getattr(original_convert_pos, "_exp51_v427_position_adapter", False):
        raise RuntimeError("position adapter was installed outside the frozen Exp51 installer")
    if getattr(original_post_init, "_exp51_v427_crlf_adapter", False):
        raise RuntimeError("CRLF adapter was installed outside the frozen Exp51 installer")
    if getattr(original_section_from_data, "_exp51_v427_section_adapter", False):
        raise RuntimeError("section adapter was installed outside the frozen Exp51 installer")
    position_counters = {"legacy_integer": 0, "v427_byteIdx": 0, "rejected": 0}
    crlf_counters = {
        "legacy_lf_files": 0,
        "standard_crlf_files": 0,
        "standard_crlf_lines": 0,
        "rejected": 0,
    }
    section_counters = {
        "legacy_two_child": 0,
        "v427_named_three_child": 0,
        "v427_unnamed_three_child": 0,
        "rejected": 0,
    }
    section_header_counters = {
        "plain": 0,
        "noncomputable": 0,
        "public": 0,
        "public_meta": 0,
        "expose_public": 0,
        "expose_public_meta": 0,
        "rejected": 0,
    }

    @wraps(original_convert_pos)
    def convert_pos_v427(self: Any, byte_idx: Any) -> Any:
        return original_convert_pos(self, decode_v427_position(byte_idx, position_counters))

    @wraps(original_post_init)
    def post_init_v427_crlf(self: Any) -> None:
        raw = self.abs_path.read_bytes()
        try:
            line_endings = classify_lean_line_endings(raw)
        except (TypeError, ValueError):
            crlf_counters["rejected"] += 1
            raise
        crlf_lines = int(line_endings["crlf_lines"])
        if crlf_lines == 0:
            crlf_counters["legacy_lf_files"] += 1
            return original_post_init(self)

        if not self.root_dir.is_absolute() or self.path.suffix != ".lean" or self.path.is_absolute():
            crlf_counters["rejected"] += 1
            raise ValueError(f"invalid LeanFile identity for CRLF adapter: {self.path}")
        code = []
        endwith_newline = None
        num_bytes = []
        observed_crlf_lines = 0
        with self.abs_path.open("rb") as handle:
            for line in handle:
                if line.endswith(b"\r\n"):
                    observed_crlf_lines += 1
                    endwith_newline = True
                    line = line[:-2]
                elif line.endswith(b"\n"):
                    # classify_lean_line_endings rejects mixed LF/CRLF, so this
                    # branch is unreachable for an accepted CRLF file.
                    crlf_counters["rejected"] += 1
                    raise TypeError(f"mixed newline stream in {self.abs_path}")
                elif b"\r" in line:
                    crlf_counters["rejected"] += 1
                    raise TypeError(f"nonstandard carriage return in {self.abs_path}")
                else:
                    endwith_newline = False
                if b"\r" in line:
                    crlf_counters["rejected"] += 1
                    raise TypeError(f"carriage return survived normalization in {self.abs_path}")
                code.append(line.decode("utf-8"))
                # Lean v4.27 String.Pos.Raw byteIdx was empirically qualified
                # against Lean's LF-normalized source buffer: CRLF contributes
                # one newline byte, not the checkout's two physical bytes.
                num_bytes.append(len(line) + 1)
        if observed_crlf_lines != crlf_lines:
            crlf_counters["rejected"] += 1
            raise ValueError(f"CRLF recount changed for {self.abs_path}")
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "endwith_newline", endwith_newline)
        object.__setattr__(self, "num_bytes", num_bytes)
        crlf_counters["standard_crlf_files"] += 1
        crlf_counters["standard_crlf_lines"] += crlf_lines

    @wraps(original_section_from_data)
    def section_from_data_v427(cls: Any, node_data: dict[str, Any], lean_file: Any) -> Any:
        try:
            schema = classify_v427_section_schema(node_data)
        except (TypeError, ValueError):
            section_counters["rejected"] += 1
            raise
        if schema == "legacy-two-child":
            section_counters["legacy_two_child"] += 1
            return original_section_from_data(cls, node_data, lean_file)

        children = ast_module._parse_children(node_data, lean_file)
        if not (
            len(children) == 3
            and isinstance(children[0], OtherNode)
            and children[0].kind == "Lean.Parser.Command.sectionHeader"
            and len(children[0].children) == 4
            and all(isinstance(item, NullNode) for item in children[0].children)
            and isinstance(children[1], AtomNode)
            and children[1].val == "section"
            and isinstance(children[2], NullNode)
            and len(children[2].children) in {0, 1}
        ):
            section_counters["rejected"] += 1
            raise TypeError("parsed Lean 4.27 section structure differs from its raw whitelist")
        parsed_header_values = tuple(
            tuple(item.val for item in slot.children if isinstance(item, AtomNode))
            for slot in children[0].children
        )
        if any(
            any(not isinstance(item, AtomNode) for item in slot.children)
            for slot in children[0].children
        ):
            section_counters["rejected"] += 1
            section_header_counters["rejected"] += 1
            raise TypeError("parsed section-header slot gained a non-atom child")
        schema_to_header = {
            "v427-named-three-child": "plain",
            "v427-unnamed-three-child": "plain",
            "v427-noncomputable-unnamed-three-child": "noncomputable",
            "v427-public-unnamed-three-child": "public",
            "v427-public-meta-unnamed-three-child": "public-meta",
            "v427-expose-public-unnamed-three-child": "expose-public",
            "v427-expose-public-meta-unnamed-three-child": "expose-public-meta",
        }
        header_schema = schema_to_header.get(schema)
        if (
            header_schema is None
            or parsed_header_values != _V427_SECTION_HEADER_PATTERNS[header_schema]
        ):
            section_counters["rejected"] += 1
            section_header_counters["rejected"] += 1
            raise TypeError("parsed section-header modifiers differ from the raw whitelist")
        section_header_counters[header_schema.replace("-", "_")] += 1
        if schema == "v427-named-three-child":
            if len(children[2].children) != 1:
                section_counters["rejected"] += 1
                raise TypeError("named Lean 4.27 section lost its identifier")
            if not isinstance(children[2].children[0], IdentNode):
                section_counters["rejected"] += 1
                raise TypeError("named Lean 4.27 section did not contain an identifier")
            name = children[2].children[0].val
            section_counters["v427_named_three_child"] += 1
        else:
            if children[2].children:
                section_counters["rejected"] += 1
                raise TypeError("unnamed Lean 4.27 section gained an identifier")
            name = None
            section_counters["v427_unnamed_three_child"] += 1
        # Header modifiers affect Lean elaboration, which already produced the
        # frozen trace.  LeanDojo uses CommandSectionNode only for section-name
        # nesting, so normalize the qualified v4.27 header wrapper to its exact
        # two-child representation without modifying source or trace data.
        normalized_children = children[1:]
        if not (
            len(normalized_children) == 2
            and isinstance(normalized_children[0], AtomNode)
            and isinstance(normalized_children[1], NullNode)
        ):
            section_counters["rejected"] += 1
            raise TypeError("Lean 4.27 section normalization did not produce two children")
        return cls(lean_file, None, None, normalized_children, name)

    setattr(convert_pos_v427, "_exp51_v427_position_adapter", True)
    setattr(post_init_v427_crlf, "_exp51_v427_crlf_adapter", True)
    setattr(section_from_data_v427, "_exp51_v427_section_adapter", True)
    LeanFile.convert_pos = convert_pos_v427
    LeanFile.__post_init__ = post_init_v427_crlf
    CommandSectionNode.from_data = classmethod(section_from_data_v427)
    _POSITION_ADAPTER_STATE = {
        "schema": V427_POSITION_ADAPTER_SCHEMA,
        "parser_compatibility_schema": V427_PARSER_COMPATIBILITY_SCHEMA,
        "in_memory_only": True,
        "accepted_structured_shape": {"byteIdx": "nonnegative-int"},
        "installed_parser_files_unchanged": True,
        "parser_file_sha256": observed_hashes,
        "source_ledger_sha256": LEAN_DOJO_SOURCE_LEDGER_SHA256,
        "counters": position_counters,
        "section_adapter": {
            "accepted": [
                "legacy-two-child",
                "v427-plain-named",
                "v427-plain-unnamed",
                "v427-noncomputable-unnamed",
                "v427-public-unnamed",
                "v427-public-meta-unnamed",
                "v427-expose-public-unnamed",
                "v427-expose-public-meta-unnamed",
            ],
            "counters": section_counters,
            "header_counters": section_header_counters,
        },
        "crlf_adapter": {
            "accepted": "standard-CRLF-normalized-to-LF-byte-width",
            "byte_index_semantics": "Lean-v4.27-LF-normalized-source-buffer",
            "checkout_modified": False,
            "counters": crlf_counters,
        },
    }
    return position_adapter_receipt()


def position_adapter_receipt() -> dict[str, Any]:
    if _POSITION_ADAPTER_STATE is None:
        raise RuntimeError("Lean 4.27 position adapter is not installed")
    receipt = deepcopy(_POSITION_ADAPTER_STATE)
    if "lean_dojo.data_extraction.traced_data" in sys.modules:
        import ray  # type: ignore
        from lean_dojo import constants as lean_dojo_constants  # type: ignore
        from lean_dojo.data_extraction import traced_data  # type: ignore

        receipt["parser_execution"] = {
            "profile": "single-process-in-memory-v427-adapter-no-ray-v1",
            "num_procs": lean_dojo_constants.NUM_PROCS,
            "num_workers": traced_data.NUM_WORKERS,
            "ray_initialized": ray.is_initialized(),
            "adapter_process_pid": os.getpid(),
        }
    return receipt


def import_traced_repo():
    # LeanDojo computes NUM_WORKERS while importing its package.  These values
    # must therefore be fixed before *any* lean_dojo import, including the
    # LeanFile import performed by the in-memory position adapter.  NUM_PROCS=2
    # gives NUM_WORKERS=1, which selects TracedRepo's local sequential parser
    # branch and keeps the adapter in the process that consumes every position.
    imported = sorted(name for name in sys.modules if name == "lean_dojo" or name.startswith("lean_dojo."))
    if imported:
        raise RuntimeError(f"LeanDojo was imported before the frozen parser topology: {imported[:8]}")
    os.environ["NUM_PROCS"] = "2"
    os.environ["LOAD_USED_PACKAGES_ONLY"] = "1"

    # Revalidate the complete pinned source ledger immediately before importing
    # the parser, even though tracing already performed the same check.
    materialized_extractor()
    install_v427_position_adapter()
    from lean_dojo import constants as lean_dojo_constants  # type: ignore
    from lean_dojo.data_extraction import traced_data  # type: ignore

    if lean_dojo_constants.NUM_PROCS != 2 or traced_data.NUM_WORKERS != 1:
        raise RuntimeError(
            "frozen single-process parser topology was not installed: "
            f"NUM_PROCS={lean_dojo_constants.NUM_PROCS} "
            f"NUM_WORKERS={traced_data.NUM_WORKERS}"
        )
    TracedRepo = traced_data.TracedRepo
    return TracedRepo
