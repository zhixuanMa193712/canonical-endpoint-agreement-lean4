#!/usr/bin/env python3
"""Count textual endpoint records that contain the pretty-printer's elision mark (U+22EF) (no Lean).

Case series: Exp49 re-execution rows (text48 values stored inline).
Strict frame: Exp64 rows; text48 states read from the archive's content store.
For successful candidates that change the state and leave a goal, report how many textual
records contain the mark, how many textual witness classes (two or more lexical heads, changed,
nonterminal) have such a record, and how many positive roots depend only on such classes.

Usage: python ellipsis_scan.py <folder with the archives>
"""
import gc
import io
import json
import re
import sys
import zipfile
from pathlib import Path

MARK = '⋯'
root = Path(sys.argv[1])


def head(t):
    s = t.strip()
    tok = re.split(r"[\s\[({|;]+", s, maxsplit=1)[0] if s else ""
    return tok or "<empty>"


def summarize(per_root):
    out = {'roots': 0, 'changed_nonterminal_records': 0, 'with_mark': 0, 'witness_classes_nonterminal': 0,
           'witness_classes_with_mark': 0, 'nonterminal_positive_roots': 0, 'roots_only_via_marked_classes': 0}
    for recs in per_root:
        out['roots'] += 1
        classes = {}
        for tac, sha, state in recs:
            out['changed_nonterminal_records'] += 1
            out['with_mark'] += MARK in state
            classes.setdefault(sha, (set(), state))[0].add(head(tac))
        wit = [(hs, st) for hs, st in classes.values() if len(hs) >= 2]
        out['witness_classes_nonterminal'] += len(wit)
        out['witness_classes_with_mark'] += sum(MARK in st for _, st in wit)
        if wit:
            out['nonterminal_positive_roots'] += 1
            if all(MARK in st for _, st in wit):
                out['roots_only_via_marked_classes'] += 1
    return out


case = []
z = zipfile.ZipFile(root / 'experiment49_candidate_endpoint_robustness_results.zip')
for n in sorted(z.namelist()):
    if not re.match(r'artifacts/validation/theorems/.+\.json$', n):
        continue
    with z.open(n) as raw, io.TextIOWrapper(raw, encoding='utf-8') as fh:
        d = json.load(fh)
    recs = []
    for e in d['worker']['executions']:
        if e['source'] == 'authored' or not e['executable'] or e.get('terminal'):
            continue
        if (e.get('no_op') or {}).get('text48'):
            continue
        t = e['endpoints']['text48']
        recs.append((e['tactic'], t['sha256'], t['value']['state']))
    case.append(recs)
    del d
    gc.collect()

strict = []
z = zipfile.ZipFile(root / 'experiment64_strict_v427_external_replication_results.zip')
names = set(z.namelist())
base = 'artifacts/v64/strict_v427_external_replication/'
for n in sorted(names):
    if not (n.startswith(base + 'scientific/theorems/') and n.endswith('.json')):
        continue
    d = json.loads(z.read(n))
    recs = []
    for c in d['candidates']:
        if c['source'] != 'candidate' or not c['executable'] or c.get('terminal'):
            continue
        if (c.get('no_op') or {}).get('text48'):
            continue
        t = c['endpoints']['text48']
        p = t['state']['path']
        member = base + p.split('/strict_v427_external_replication/', 1)[1]
        state = z.read(member).decode('utf-8')
        recs.append((c['tactic'], t['sha256'], state))
    strict.append(recs)
print(json.dumps({'case_series_text': summarize(case), 'strict_text': summarize(strict)}, indent=1))
