#!/usr/bin/env python3
"""Tabulate the archived failure diagnostics of the strict frame by program (no Lean).

Reads Exp64 theorem rows and the diagnostic texts in the archive's content store, reduces each
message to a short normalized prefix, and counts prefixes by program; also flags messages that
point to the harness rather than the tactic (declaration name, auxiliary declarations, recursion
depth, heartbeats).

Usage: python failure_messages.py <path to experiment64 results zip>
"""
import collections
import json
import re
import sys
import zipfile

z = zipfile.ZipFile(sys.argv[1])
base = 'artifacts/v64/strict_v427_external_replication/'
diag = {n.rsplit('/', 1)[-1][:-4]: n for n in z.namelist() if '/content_store/diagnostic/' in n}
by_prog = collections.defaultdict(collections.Counter)
harness = collections.Counter()
missing = 0
HARNESS = [('declaration name', r'declName|declaration name|auxiliary declaration|mkAuxName'),
           ('recursion depth', r'maximum recursion depth'),
           ('heartbeats', r'heartbeats'),
           ('sorry', r'\bsorry\b')]


def norm(msg):
    m = msg.strip().splitlines()[0] if msg.strip() else ''
    m = re.sub(r'^.*?error:\s*', '', m)
    m = re.sub(r'`[^`]*`', '`_`', m)
    m = re.sub(r"'[^']*'", "'_'", m)
    m = re.sub(r'\d+', 'N', m)
    return m[:70]


for n in sorted(z.namelist()):
    if not (n.startswith(base + 'scientific/theorems/') and n.endswith('.json')):
        continue
    d = json.loads(z.read(n))
    for c in d['candidates']:
        if c['source'] != 'candidate' or c['executable']:
            continue
        dg = c.get('diagnostic')
        if not dg or dg['sha256'] not in diag:
            missing += 1
            continue
        txt = z.read(diag[dg['sha256']]).decode('utf-8', 'ignore')
        if 'unknown tactic' in txt:
            continue
        by_prog[c['tactic']][norm(txt)] += 1
        for label, pat in HARNESS:
            if re.search(pat, txt):
                harness[(label, c['tactic'])] += 1
out = {'execution_failures_without_diagnostic': missing,
       'by_program': {p: cnt.most_common(4) for p, cnt in sorted(by_prog.items())},
       'execution_failures_by_program': {p: sum(cnt.values()) for p, cnt in sorted(by_prog.items())},
       'harness_related': [[a, b, n] for (a, b), n in sorted(harness.items())]}
print(json.dumps(out, indent=1))
