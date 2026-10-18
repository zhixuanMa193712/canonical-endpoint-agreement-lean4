#!/usr/bin/env python3
"""Export compact per-root records from the archived execution bundles (read-only).

For every case-series root (Exp49 re-execution rows, which carry raw, textual and
structural endpoints) and every strict-frame root (Exp64 scientific rows and inputs),
write one JSON line with the root identity, source location, and for each candidate:
tactic, success, terminal flag, endpoint digests and no-op flags.  For Exp62, write the
per-job transition logs.  No Lean execution.

Usage: python export_compact_rows.py --root <folder with the archives> --out <dir>
"""
import argparse
import io
import json
import re
import zipfile
from pathlib import Path


def stream_json(z, name):
    with z.open(name) as raw, io.TextIOWrapper(raw, encoding="utf-8") as fh:
        return json.load(fh)


def exp49(z, out):
    with (out / "case_series_rows.jsonl").open("w", encoding="utf-8") as f:
        for n in sorted(z.namelist()):
            if not re.match(r"artifacts/validation/theorems/.+\.json$", n):
                continue
            d = stream_json(z, n)
            w = d["worker"]
            cands, authored = [], None
            for e in w["executions"]:
                eps = e.get("endpoints") or {}
                row = {"tactic": e["tactic"], "ok": bool(e["executable"]),
                       "terminal": bool(e.get("terminal")),
                       "text": (eps.get("text48") or {}).get("sha256"),
                       "struct": (eps.get("struct") or {}).get("sha256"),
                       "noop_text": bool((e.get("no_op") or {}).get("text48")),
                       "noop_struct": bool((e.get("no_op") or {}).get("struct")),
                       "error": (e.get("error") or "")[:300]}
                if e["source"] == "authored":
                    authored = row
                else:
                    cands.append(row)
            rec = {"study": "case_series", "slug": d["identity"]["slug"],
                   "commit": d["identity"]["commit"], "file_path": d["selection"]["file_path"],
                   "source_file_sha256": d["identity"]["source_file_sha256"],
                   "full_name": d["identity"]["full_name"],
                   "target_pos": w.get("target_pos"), "target_end_pos": w.get("target_end_pos"),
                   "authored_tactic": d["selection"]["authored_tactic"],
                   "pre_state": d["selection"].get("trace_root_state"),
                   "authored": authored, "candidates": cands}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            del d, w


def exp64(z, out):
    base = "artifacts/v64/strict_v427_external_replication/scientific/"
    inputs = {}
    for n in z.namelist():
        if n.startswith(base + "inputs/") and n.endswith(".json"):
            d = json.loads(z.read(n))
            inputs[d["theorem_id"]] = d
    with (out / "strict_rows.jsonl").open("w", encoding="utf-8") as f:
        for n in sorted(z.namelist()):
            if not re.match(re.escape(base) + r"theorems/.+\.json$", n):
                continue
            d = json.loads(z.read(n))
            inp = inputs[d["theorem_id"]]
            cands = []
            for c in d["candidates"]:
                if c["source"] != "candidate":
                    continue
                eps = c.get("endpoints") or {}
                cands.append({"tactic": c["tactic"], "ok": bool(c["executable"]),
                              "terminal": bool(c.get("terminal")),
                              "failure": c.get("failure_category"),
                              "text": (eps.get("text48") or {}).get("sha256"),
                              "struct": (eps.get("struct") or {}).get("sha256"),
                              "noop_text": bool((c.get("no_op") or {}).get("text48")),
                              "noop_struct": bool((c.get("no_op") or {}).get("struct"))})
            a = d["authored"]
            rec = {"study": "strict", "slug": d["slug"], "commit": d["commit"],
                   "file_path": d["file_path"], "source_file_sha256": inp["source_file_sha256"],
                   "full_name": inp["full_name"], "theorem_id": d["theorem_id"],
                   "target_pos": inp["target_pos"], "target_end_pos": inp["target_end_pos"],
                   "authored_tactic": inp["authored_tactic"], "pre_state": inp["trace_root_state"],
                   "authored": {"terminal": bool(a.get("terminal")),
                                "text": a["endpoints"]["text48"]["sha256"],
                                "struct": a["endpoints"]["struct"]["sha256"]},
                   "candidates": cands}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def exp62(z, out):
    base = "artifacts/v62/multistep_solvable_search_fix1/"
    with (out / "multistep_jobs.jsonl").open("w", encoding="utf-8") as f:
        for n in sorted(z.namelist()):
            if not (n.startswith(base + "confirmation/execution/jobs/") and n.endswith(".json")):
                continue
            d = json.loads(z.read(n))
            keep = {k: d.get(k) for k in ("job_id", "policy", "target_id", "theorem_id", "stratum",
                                          "solved", "stop_reason", "tactic_invocations",
                                          "expanded_nodes", "proof", "effect_collisions_observed",
                                          "initial_endpoint_key")}
            keep["transitions"] = [{k: t.get(k) for k in (
                "expanded_node_ordinal", "parent_depth", "parent_endpoint_key",
                "candidate_position_executed", "tactic", "head", "registered_next_witness",
                "kind", "terminal", "endpoint_key")} for t in d.get("transition_rows", [])]
            f.write(json.dumps(keep, ensure_ascii=False) + "\n")
    frame = z.read(base + "frozen/candidate_frame.jsonl")
    (out / "multistep_frame.jsonl").write_bytes(frame)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    exp49(zipfile.ZipFile(a.root / "experiment49_candidate_endpoint_robustness_results.zip"), a.out)
    exp64(zipfile.ZipFile(a.root / "experiment64_strict_v427_external_replication_results.zip"), a.out)
    exp62(zipfile.ZipFile(a.root / "experiment62_multistep_solvable_search_fix1_results.zip"), a.out)


if __name__ == "__main__":
    main()
