#!/usr/bin/env python3
"""Offline reanalysis added in the round-1 revision (16 October 2026).

Recomputes, from archived execution rows only (no Lean execution), every
number that the revised manuscript adds:

* candidate outcomes per program (confirmation and strict external frame),
  failure categories, heartbeat exhaustion, and identical behaviour of
  aesop/aesop? and ring/ring_nf;
* decomposition of positive roots by panel (full / genealogy-deduplicated),
  representation (textual / structural) and witness kind (terminal only /
  nonterminal);
* effect of removing exact?; multiplicity of nonterminal endpoints;
  reproduction of the authored endpoint by panel programs;
* causes of the 76 confirmation pairs on which textual and structural
  comparison disagree;
* the prespecified Exp49 rarefaction (read, not recomputed);
* the Exp62 qualification flow, depth breakdown, depth-2 expansion counts,
  stop reasons, and exact / Wilson bounds.

Usage:
    python revision_r1_offline_reanalysis.py --root <folder with the archives> --out result.json

Inputs (read-only, opened as ZIP files; SHA-256 checked):
    experiment48_fix1_mac_analysis_bundle.zip
    experiment49_candidate_endpoint_robustness_results.zip
    experiment62_multistep_solvable_search_fix1_results.zip
    experiment64_strict_v427_external_replication_results.zip
"""
from __future__ import annotations

import argparse
import collections
import gc
import hashlib
import io
import json
import math
import re
import zipfile
from pathlib import Path

ARCHIVES = {
    "exp48": ("experiment48_fix1_mac_analysis_bundle.zip",
              "fb5b08d9b6ef73ec7530f06f9d4f28af26a9d23dd7a1dd89f21788774cd34fd3"),
    "exp49": ("experiment49_candidate_endpoint_robustness_results.zip",
              "f57f6938c5de6d32339f2ca9e8cb2789ceed1dd2263feb7155ee76b35caefdc2"),
    "exp62": ("experiment62_multistep_solvable_search_fix1_results.zip",
              "b2960650f01811d333f0ed4beea422c00d9149eb1f5eac7c55f1333a75230f57"),
    "exp64": ("experiment64_strict_v427_external_replication_results.zip",
              "2aaebc31501b5946a6dcfb7a279d2dda0cdd4cf20160f7e49ec63674e5411130"),
}

LIBRARY = ["rfl", "assumption", "trivial", "contradiction", "simp", "simpa", "simp_all",
           "aesop", "aesop?", "norm_num", "omega", "linarith", "nlinarith", "ring",
           "ring_nf", "positivity", "decide", "native_decide", "constructor", "ext",
           "fun_prop", "solve_by_elim", "exact?", "apply_assumption", "tauto", "left",
           "right", "intro", "intros", "all_goals simp", "all_goals aesop",
           "first | rfl | assumption"]
# Frozen Exp49 genealogy (groups with more than one executed member; others are singletons).
GROUP = {"simp": "simp_engine", "simpa": "simp_engine", "simp_all": "simp_engine",
         "all_goals simp": "simp_engine", "aesop": "aesop_engine", "aesop?": "aesop_engine",
         "all_goals aesop": "aesop_engine", "ring": "ring_engine", "ring_nf": "ring_engine",
         "intro": "intro_engine", "intros": "intro_engine"}
EXCLUDED_CLASSES = {"aesop?", "exact?", "all_goals simp", "all_goals aesop",
                    "first | rfl | assumption"}  # direct suggestions and control wrappers


def head(tactic: str) -> str:
    """Corrected lexical head rule (first token before whitespace or [ ( { | ;)."""
    s = tactic.strip()
    token = re.split(r"[\s\[({|;]+", s, maxsplit=1)[0] if s else ""
    return token or "<empty>"


def dedup_view(order: list[str]) -> list[str]:
    seen, out = set(), []
    for t in order:
        if t in EXCLUDED_CLASSES:
            continue
        g = GROUP.get(t, t)
        if g in seen:
            continue
        seen.add(g)
        out.append(t)
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def open_archives(root: Path) -> dict[str, zipfile.ZipFile]:
    out = {}
    for key, (name, digest) in ARCHIVES.items():
        p = root / name
        got = sha256(p)
        if got != digest:
            raise SystemExit(f"{name}: SHA-256 {got} differs from frozen {digest}")
        out[key] = zipfile.ZipFile(p)
    return out


def wilson_upper(k: int, n: int, z: float = 1.6448536269514722) -> float:
    p = k / n
    den = 1 + z * z / n
    centre = p + z * z / (2 * n)
    rad = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre + rad) / den


def clopper_pearson_upper_zero(n: int, alpha: float = 0.05) -> float:
    return 1 - alpha ** (1 / n)


class Executions:
    """Uniform view of one root: candidate rows with status, endpoints, no-op flags."""

    def __init__(self, cands, authored, slug, file_path):
        self.cands = cands          # list of dicts: tactic, ok, terminal, ep{rep}, noop{rep}
        self.authored = authored    # dict with terminal, ep{rep}
        self.slug = slug
        self.file_path = file_path


def positive(cands, rep, nonterminal_only=False):
    classes = collections.defaultdict(set)
    for c in cands:
        if c["ok"] and not c["noop"][rep]:
            if nonterminal_only and c["terminal"]:
                continue
            classes[c["ep"][rep]].add(head(c["tactic"]))
    return any(len(v) >= 2 for v in classes.values())


def pairs(cands, rep):
    classes = collections.defaultdict(set)
    for c in cands:
        if c["ok"] and not c["noop"][rep]:
            classes[c["ep"][rep]].add(head(c["tactic"]))
    out = set()
    for v in classes.values():
        v = sorted(v)
        for i in range(len(v)):
            for j in range(i + 1, len(v)):
                out.add((v[i], v[j]))
    return out


def summarize(roots: list[Executions], reps: list[str]) -> dict:
    res: dict = {"roots": len(roots)}
    att, suc, nt, alias = (collections.Counter(), collections.Counter(),
                           collections.Counter(), collections.Counter())
    for r in roots:
        by = {c["tactic"]: c for c in r.cands}
        for c in r.cands:
            att[c["tactic"]] += 1
            if c["ok"]:
                suc[c["tactic"]] += 1
                if not c["terminal"] and not c["noop"][reps[-1]]:
                    nt[c["tactic"]] += 1
        for a, b in (("aesop", "aesop?"), ("ring", "ring_nf")):
            if a in by and b in by:
                ca, cb = by[a], by[b]
                same = ca["ok"] == cb["ok"] and all(
                    (not ca["ok"]) or ca["ep"][rep] == cb["ep"][rep] for rep in reps)
                alias[f"{a}|{b}|{'same' if same else 'different'}"] += 1
    res["candidate_outcomes"] = {t: {"attempts": att[t], "successes": suc[t],
                                     "nonterminal_changed_successes": nt[t]}
                                 for t in LIBRARY if att[t]}
    res["attempts"] = sum(att.values())
    res["successes"] = sum(suc.values())
    res["alias_comparison"] = dict(alias)
    for rep in reps:
        for view in ("full", "dedup"):
            Y = NT = T_ONLY = 0
            reps_nt = set()
            exec_nt = classes_nt = 0
            pair_counter = collections.Counter()
            no_exact = 0
            for r in roots:
                order = [c["tactic"] for c in r.cands]
                by = {c["tactic"]: c for c in r.cands}
                panel = [by[t] for t in (order if view == "full" else dedup_view(order))]
                y = positive(panel, rep)
                ntw = positive(panel, rep, nonterminal_only=True)
                Y += y
                NT += ntw
                T_ONLY += y and not ntw
                if ntw:
                    reps_nt.add(r.slug)
                if view == "full":
                    no_exact += positive([c for c in panel if c["tactic"] != "exact?"], rep)
                ntc = [c for c in panel if c["ok"] and not c["terminal"] and not c["noop"][rep]]
                exec_nt += len(ntc)
                classes_nt += len({c["ep"][rep] for c in ntc})
                for p in pairs(panel, rep):
                    pair_counter["/".join(p)] += 1
            key = f"{rep}_{view}"
            res[key] = {"positive": Y, "nonterminal": NT, "terminal_only": T_ONLY,
                        "repositories_with_nonterminal": len(reps_nt),
                        "nonterminal_successful_executions": exec_nt,
                        "distinct_nonterminal_endpoints": classes_nt,
                        "executions_per_endpoint": round(exec_nt / classes_nt, 3) if classes_nt else None,
                        "distinct_head_pairs": len(pair_counter),
                        "top_pairs": pair_counter.most_common(8)}
            if view == "full":
                res[key]["positive_without_exact?"] = no_exact
    # authored endpoint reproduction (last representation in reps)
    rep = reps[-1]
    any_hit = nt_auth = nt_hit = term_auth = 0
    for r in roots:
        hit = any(c["ok"] and c["ep"][rep] == r.authored["ep"][rep] for c in r.cands)
        any_hit += hit
        if r.authored["terminal"]:
            term_auth += 1
        else:
            nt_auth += 1
            nt_hit += hit
    res["authored_endpoint"] = {"representation": rep, "reproduced_by_some_candidate": any_hit,
                                "authored_terminal_roots": term_auth,
                                "authored_nonterminal_roots": nt_auth,
                                "nonterminal_authored_reproduced": nt_hit}
    res["source_files"] = len({(r.slug, r.file_path) for r in roots})
    return res


def load_exp48(z: zipfile.ZipFile) -> list[Executions]:
    roots = []
    for n in sorted(z.namelist()):
        if not re.match(r"confirmation_fix1/theorems/.+\.json$", n):
            continue
        d = json.loads(z.read(n))
        cands, authored = [], None
        for e in d["worker"]["executions"]:
            ok = str(e["executable"]) == "True"
            row = {"tactic": e["tactic"], "ok": ok, "terminal": str(e.get("terminal")) == "True",
                   "ep": {"text": e.get("endpoint_sha256")},
                   "noop": {"text": str(e.get("no_op")) == "True"},
                   "error": e.get("error", "")}
            if e["source"] == "authored":
                authored = row
            else:
                cands.append(row)
        roots.append(Executions(cands, authored, d["identity"]["slug"], d["selection"]["file_path"]))
    return roots


def load_exp64(z: zipfile.ZipFile) -> tuple[list[Executions], dict]:
    base = "artifacts/v64/strict_v427_external_replication/"
    timeout_diag = set()
    for n in z.namelist():
        if n.startswith(base + "content_store/diagnostic/") and not n.endswith("/"):
            s = z.read(n).decode("utf-8", "ignore").lower()
            if "heartbeat" in s or "timeout" in s:
                timeout_diag.add(Path(n).name.split(".")[0])
    roots, fail = [], collections.Counter()
    parse_by_tactic, hb_roots, hb_cands = collections.Counter(), set(), 0
    parse_repos = set()
    for n in sorted(z.namelist()):
        if not re.match(re.escape(base) + r"scientific/theorems/.+\.json$", n):
            continue
        d = json.loads(z.read(n))
        cands = []
        for c in d["candidates"]:
            if c["source"] != "candidate":
                continue
            ok = bool(c["executable"])
            if not ok:
                fail[c.get("failure_category")] += 1
                if c.get("failure_category") == "parse":
                    parse_by_tactic[c["tactic"]] += 1
                    parse_repos.add(d["slug"])
                diag = c.get("diagnostic") or {}
                if diag.get("sha256") in timeout_diag:
                    hb_cands += 1
                    hb_roots.add(d["theorem_id"])
            eps = c.get("endpoints") or {}
            cands.append({"tactic": c["tactic"], "ok": ok, "terminal": bool(c.get("terminal")),
                          "ep": {"text": (eps.get("text48") or {}).get("sha256"),
                                 "struct": (eps.get("struct") or {}).get("sha256")},
                          "noop": {"text": bool((c.get("no_op") or {}).get("text48")),
                                   "struct": bool((c.get("no_op") or {}).get("struct"))}})
        a = d["authored"]
        authored = {"terminal": bool(a.get("terminal")),
                    "ep": {"text": a["endpoints"]["text48"]["sha256"],
                           "struct": a["endpoints"]["struct"]["sha256"]}}
        roots.append(Executions(cands, authored, d["slug"], d["file_path"]))
    extra = {"failure_categories": dict(fail), "parse_failures_by_tactic": dict(parse_by_tactic),
             "parse_failure_repositories": len(parse_repos),
             "heartbeat_exhaustion_candidates": hb_cands, "heartbeat_exhaustion_roots": len(hb_roots)}
    return roots, extra


def exp49_discordance(z: zipfile.ZipFile) -> dict:
    sup = re.compile(r"\binst<GEN>[\u00b9\u00b2\u00b3\u2070-\u2079]*")
    named = re.compile(r"\binst(_\d+)?\b")
    out = collections.Counter()
    for n in sorted(z.namelist()):
        if not re.match(r"artifacts/validation/theorems/.+\.json$", n):
            continue
        # Some rows exceed 1 GB; parse from a text stream to avoid an extra bytes copy.
        with z.open(n) as raw, io.TextIOWrapper(raw, encoding="utf-8") as fh:
            d = json.load(fh)
        ex = [e for e in d["worker"]["executions"] if e["source"] != "authored" and e["executable"]]
        for i in range(len(ex)):
            for j in range(i + 1, len(ex)):
                a, b = ex[i], ex[j]
                if a["head"] == b["head"]:
                    continue
                def match(rep):
                    return (a["endpoints"][rep]["sha256"] == b["endpoints"][rep]["sha256"]
                            and not a["no_op"][rep] and not b["no_op"][rep])
                tm, sm = match("text48"), match("struct")
                if sm and not tm:
                    ta = a["endpoints"]["text48"]["value"]["state"]
                    tb = b["endpoints"]["text48"]["value"]["state"]
                    if ta == tb:
                        out["structure_only_printed_state_unchanged_from_start"] += 1
                    elif named.sub("INST", sup.sub("INST", ta)) == named.sub("INST", sup.sub("INST", tb)):
                        out["structure_only_instance_names_only"] += 1
                    else:
                        out["structure_only_other"] += 1
                elif tm and not sm:
                    out["text_only"] += 1
        a = b = None
        del d, ex
        gc.collect()
    return dict(out)


def exp62(z: zipfile.ZipFile) -> dict:
    base = "artifacts/v62/multistep_solvable_search_fix1/"
    frame = {json.loads(l)["target_id"]: json.loads(l)
             for l in z.read(base + "frozen/candidate_frame.jsonl").decode().splitlines() if l.strip()}
    rows = [json.loads(l) for l in
            z.read(base + "confirmation/analysis/paired_root_metrics.jsonl").decode().splitlines() if l.strip()]
    fails = collections.Counter()
    for n in z.namelist():
        if n.startswith(base + "qualification/receipts/") and n.endswith(".json"):
            d = json.loads(z.read(n))
            if not d["qualification_gate"]:
                fails[d["first_failed_gate"]] += 1
    by_depth = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        dep = frame[r["target_id"]]["authored_witness_depth"]
        c = by_depth[dep]
        c["roots"] += 1
        c["full_invocations"] += r["full_tactic_invocations"]
        c["endpoint_invocations"] += r["effect_aware_tactic_invocations"]
        c["full_solved"] += r["full_solved"]
        c["endpoint_solved"] += r["effect_aware_solved"]
    d2 = [r for r in rows if r["stratum"] == "authored_depth_2"]
    policies = ["full", "effect_aware", "head_dedup", "fixed_budget_random"]
    stop = {}
    for p in policies:
        stop[p] = {"budget_768": sum(r[f"{p}_tactic_invocations"] >= 768 for r in rows),
                   "unsolved": sum(not r[f"{p}_solved"] for r in rows),
                   "max_wall_clock_seconds": round(max(r[f"{p}_wall_clock_seconds"] for r in rows), 1)}
    deep = [r for r in rows if r["stratum"] != "authored_depth_2"]
    return {
        "qualification_failures_by_gate": dict(fails),
        "confirmation_depths": {str(k): dict(v) for k, v in sorted(by_depth.items())},
        "depth2_expanded_nodes_full": dict(collections.Counter(r["full_expanded_nodes"] for r in d2)),
        "depth2_expanded_nodes_endpoint": dict(collections.Counter(r["effect_aware_expanded_nodes"] for r in d2)),
        "source_files": len({frame[r["target_id"]]["file_path"] for r in rows}),
        "panel_sizes": dict(collections.Counter(len(frame[r["target_id"]]["candidate_panel"]) for r in rows)),
        "stop": stop,
        "losses": {"all": 0, "deep": sum(r["full_solved"] and not r["effect_aware_solved"] for r in deep)},
        "bounds": {"wilson_0_of_64": wilson_upper(0, 64), "clopper_pearson_0_of_64": clopper_pearson_upper_zero(64),
                   "wilson_0_of_32": wilson_upper(0, 32), "clopper_pearson_0_of_32": clopper_pearson_upper_zero(32)},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    zs = open_archives(args.root)
    conf = load_exp48(zs["exp48"])
    result = {"inputs": {k: {"file": v[0], "sha256": v[1]} for k, v in ARCHIVES.items()}}
    c = summarize(conf, ["text"])
    c["parse_failures_unknown_tactic"] = sum(
        1 for r in conf for x in r.cands if not x["ok"] and "unknown tactic" in x["error"])
    c["heartbeat_or_timeout_messages"] = sum(
        1 for r in conf for x in r.cands if not x["ok"] and
        ("heartbeat" in x["error"].lower() or "timeout" in x["error"].lower()))
    result["confirmation"] = c
    strict, extra = load_exp64(zs["exp64"])
    s = summarize(strict, ["text", "struct"])
    s.update(extra)
    result["strict_frame"] = s
    result["confirmation_discordant_pairs"] = exp49_discordance(zs["exp49"])
    summ = json.loads(zs["exp49"].read("artifacts/analysis/summary.json"))
    result["exp49_rarefaction_struct"] = summ["rarefaction_struct"]
    result["exp49_dedup_struct_macros"] = summ["macros"]["L-mechanism-diverse"]["struct"]
    result["multistep"] = exp62(zs["exp62"])
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
