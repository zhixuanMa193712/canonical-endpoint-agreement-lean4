#!/usr/bin/env python3
"""Mathlib and Aesop dependence of the strict-frame representatives (static; no Lean).

Reads lake-manifest.json and the lakefile at the pinned commit of each representative
(fetched by fetch_sources.py, which adds these files to the sparse checkout) and records
whether the package graph contains `mathlib` and `aesop`.

Usage: python scan_dependencies.py <work dir with data/ and src/>  -> strict_dependencies.json
"""
import json
import re
import sys
from pathlib import Path

W = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
slugs = sorted({json.loads(l)['slug'] for l in open(W / 'data' / 'strict_rows.jsonl')})
out = {}
for slug in slugs:
    d = W / 'src' / slug.replace('/', '__')
    files = sorted(p.name for p in d.iterdir() if p.name in ('lake-manifest.json', 'lakefile.toml', 'lakefile.lean'))
    names = set()
    if (d / 'lake-manifest.json').exists():
        man = json.loads((d / 'lake-manifest.json').read_text())
        names |= {p.get('name', '').lower() for p in man.get('packages', [])}
    for lf in ('lakefile.toml', 'lakefile.lean'):
        if (d / lf).exists():
            txt = (d / lf).read_text().lower()
            names |= set(re.findall(r'(?:require\s+"?|name\s*=\s*")([\w-]+)', txt))
    out[slug] = {'mathlib': 'mathlib' in names, 'aesop': 'aesop' in names, 'files': files}
json.dump(out, open(W / 'strict_dependencies.json', 'w'), indent=0)
print(sum(v['mathlib'] for v in out.values()), 'of', len(out), 'depend on Mathlib;',
      sum(v['aesop'] for v in out.values()), 'on Aesop')
print('without Mathlib:', [s for s, v in out.items() if not v['mathlib']])
