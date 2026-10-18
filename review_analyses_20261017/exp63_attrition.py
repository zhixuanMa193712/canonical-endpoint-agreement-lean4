#!/usr/bin/env python3
"""Attrition in the strict-frame recruitment (Exp63), read from the archived receipts; no Lean.

For the 87 repositories that reached the static gate, report the static-gate result, the
qualification classification and first failed gate of the 52 frozen candidates, and simple
covariates recorded before qualification (stars, statically counted tactic roots, Lean source
files, checkout size, creation date).  Prints JSON.

Usage: python exp63_attrition.py <path to experiment63_strict_v427_recruitment_results.zip>
"""
import collections
import json
import statistics
import sys
import zipfile

z = zipfile.ZipFile(sys.argv[1])
base = 'artifacts/v63/strict_v427_recruitment/'
static, qual = {}, {}
for n in z.namelist():
    if n.startswith(base + 'static/receipts/') and n.endswith('.json'):
        d = json.loads(z.read(n))
        c = d['candidate']
        sf = d.get('source_files')
        static[c['slug']] = {'static_gate': d.get('first_failed_gate'), 'stars': c.get('stars'),
                             'static_tactic_roots': d.get('static_tactic_roots'),
                             'checkout_bytes': d.get('checkout_allocated_bytes'),
                             'lean_files': len(sf) if isinstance(sf, list) else sf,
                             'created': (c.get('created_at') or '')[:10]}
    elif n.startswith(base + 'qualification/repositories/') and n.endswith('.json'):
        d = json.loads(z.read(n))
        qual[d['candidate']['slug']] = {'classification': d.get('classification'),
                                       'first_failed_gate': d.get('first_failed_gate')}
groups = collections.defaultdict(list)
for slug, v in static.items():
    g = qual[slug]['classification'] if slug in qual else ('static_gate_failed' if v['static_gate'] else 'static_pass')
    groups[g].append(v)


def med(key, vs):
    xs = [v[key] for v in vs if isinstance(v[key], (int, float))]
    return statistics.median(xs) if xs else None


summary = {g: {'repositories': len(vs), 'median_stars': med('stars', vs),
               'median_static_tactic_roots': med('static_tactic_roots', vs),
               'median_lean_files': med('lean_files', vs),
               'median_checkout_mb': round(med('checkout_bytes', vs) / 1e6, 1),
               'median_created': sorted(v['created'] for v in vs)[len(vs) // 2]}
           for g, vs in sorted(groups.items())}
gates = collections.Counter((q['classification'], q['first_failed_gate']) for q in qual.values())
not_qualified = [{'slug': s, **qual[s], **static.get(s, {})} for s in sorted(qual) if qual[s]['classification'] != 'qualified']
print(json.dumps({'summary_by_outcome': summary,
                  'qualification_gates': [{'classification': a, 'first_failed_gate': b, 'repositories': n}
                                          for (a, b), n in gates.most_common()],
                  'not_qualified': not_qualified}, indent=1))
