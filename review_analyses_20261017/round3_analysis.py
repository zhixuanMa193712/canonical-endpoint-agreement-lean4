#!/usr/bin/env python3
"""Round-3 offline analyses (no Lean execution).

Uses the same inputs as round2_analysis.py (compact rows in data/, root_positions.json,
strict_dependencies.json) and imports its helpers.  Output: round3_analysis.json.

Usage: python round3_analysis.py <work dir>
"""
import collections
import importlib.util
import json
import random
import sys
from pathlib import Path

W = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
spec = importlib.util.spec_from_file_location('r2', W / 'round2_analysis.py')
r2 = importlib.util.module_from_spec(spec)
sys.argv = [sys.argv[0], str(W)]
spec.loader.exec_module(r2)
D = W / 'data'

SIMP = {'simp', 'simpa', 'simp_all'}


def grouping(name):
    """Alternative implementation groupings; programs not listed form their own group."""
    g = {'simp': 'simplifier', 'simpa': 'simplifier', 'simp_all': 'simplifier', 'norm_num': 'simplifier',
         'aesop': 'simplifier', 'aesop?': 'simplifier', 'ring': 'ring', 'ring_nf': 'ring',
         'exact?': 'search', 'solve_by_elim': 'search', 'decide': 'decide', 'native_decide': 'decide'}
    if name in ('aesop_separate', 'both_separate'):
        g['aesop'] = g['aesop?'] = 'aesop'
    if name in ('norm_num_separate', 'both_separate'):
        g['norm_num'] = 'norm_num'
    if name == 'genealogy_plus_ring':  # genealogy groups only: simp family, Aesop pair, ring pair
        g = {'simp': 's', 'simpa': 's', 'simp_all': 's', 'aesop': 'a', 'aesop?': 'a', 'ring': 'r', 'ring_nf': 'r'}
    return lambda t: g.get(t, t)


VIEWS = {
    'full': lambda o: o,
    'no_question': lambda o: [t for t in o if not t.endswith('?')],
    'no_aesop': lambda o: [t for t in o if t != 'aesop'],
    'no_aesop_question': lambda o: [t for t in o if t != 'aesop?'],
    'no_aesop_pair': lambda o: [t for t in o if t not in ('aesop', 'aesop?')],
    'no_direct': lambda o: [t for t in o if t not in r2.DIRECT],
    'deduplicated': r2.dedup,
}


def view_table(rows, rep):
    out = {}
    for name, f in VIEWS.items():
        Y = NT = 0
        for r in rows:
            by = {c['tactic']: c for c in r['candidates']}
            y, nt = r2.pos_flags([by[t] for t in f([c['tactic'] for c in r['candidates']])], rep)
            Y += y
            NT += nt
        out[name] = {'positive': Y, 'nonterminal': NT}
    return out


def cluster_bootstrap(rows, rep, view, reps=20000, seed=20260918):
    per = collections.defaultdict(list)
    for r in rows:
        order = [c['tactic'] for c in r['candidates']]
        by = {c['tactic']: c for c in r['candidates']}
        panel = [by[t] for t in (order if view == 'full' else r2.dedup(order))]
        per[r['slug']].append(r2.pos_flags(panel, rep)[0])
    rates = [sum(v) / len(v) for _, v in sorted(per.items())]
    rng = random.Random(seed)
    vals = sorted(sum(rng.choice(rates) for _ in rates) / len(rates) for _ in range(reps))
    return {'p2.5': vals[int(0.025 * reps)], 'p97.5': vals[int(0.975 * reps) - 1], 'replicates': reps, 'seed': seed}


def strict_strata(st):
    dep = json.load(open(W / 'strict_dependencies.json'))
    out = {}
    for flag in (True, False):
        sel = [r for r in st if dep[r['slug']]['mathlib'] == flag]
        key = 'mathlib' if flag else 'no_mathlib'
        out[key] = {'representatives': len({r['slug'] for r in sel})}
        for rep in ('text', 'struct'):
            out[key][rep + '_full'] = r2.table(sel, rep)
            out[key][rep + '_dedup'] = r2.table(sel, rep, 'dedup')
    return out


def within_rep_parse(st):
    def all_parse(r):
        return all(c.get('failure') != 'parse' for c in r['candidates'])
    by = collections.defaultdict(lambda: {'all': [], 'fail': []})
    for r in st:
        order = [c['tactic'] for c in r['candidates']]
        y, nt = r2.pos_flags(r['candidates'], 'struct')
        by[r['slug']]['all' if all_parse(r) else 'fail'].append((y, nt))
    both = {s: v for s, v in by.items() if v['all'] and v['fail']}
    agg = {'representatives_with_both_strata': len(both)}
    for k in ('all', 'fail'):
        agg[k + '_roots'] = sum(len(v[k]) for v in both.values())
        agg[k + '_positive'] = sum(y for v in both.values() for y, _ in v[k])
        agg[k + '_nonterminal'] = sum(nt for v in both.values() for _, nt in v[k])
    return agg


def case_parse_failures(cs):
    cnt = collections.Counter()
    roots = set()
    for r in cs:
        for c in r['candidates']:
            if not c['ok'] and 'unknown tactic' in (c.get('error') or ''):
                cnt[c['tactic']] += 1
                roots.add(r['full_name'])
    return {'by_tactic': dict(cnt), 'roots': len(roots)}


def coactivity(rows, rep):
    """Cross-group pairs that both reach a changed nonterminal endpoint at the same root."""
    lab = grouping('implementation')
    pairs = collections.Counter()
    agree = collections.Counter()
    roots_coactive = roots_agree = 0
    for r in rows:
        act = [c for c in r['candidates'] if c['ok'] and not c['terminal'] and not c['noop_' + rep]]
        co = ag = False
        for i in range(len(act)):
            for j in range(i + 1, len(act)):
                a, b = act[i], act[j]
                if lab(a['tactic']) == lab(b['tactic']):
                    continue
                key = '/'.join(sorted([a['tactic'], b['tactic']]))
                pairs[key] += 1
                co = True
                if a[rep] == b[rep]:
                    agree[key] += 1
                    ag = True
        roots_coactive += co
        roots_agree += ag
    return {'roots_with_coactive_cross_group_pair': roots_coactive, 'roots_with_cross_group_agreement': roots_agree,
            'coactive_pairs': sum(pairs.values()), 'agreeing_pairs': sum(agree.values()),
            'top_coactive': sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0]))[:10], 'agreeing': sorted(agree.items(), key=lambda kv: (-kv[1], kv[0]))[:10]}


# ------------------------------------------------------------------ multistep

def multistep():
    jobs = [json.loads(l) for l in open(D / 'multistep_jobs.jsonl')]
    frame = {json.loads(l)['target_id']: json.loads(l) for l in open(D / 'multistep_frame.jsonl')}
    generic24 = set.intersection(*(set(f['candidate_panel']) for f in frame.values()))
    by = collections.defaultdict(dict)
    for j in jobs:
        by[j['target_id']][j['policy']] = j
    LIM_INV, LIM_NODES, LIM_DEPTH = 768, 32, 6

    def nodes_of(job):
        nodes = collections.OrderedDict()
        for t in job['transitions']:
            nodes.setdefault(t['expanded_node_ordinal'], []).append(t)
        return nodes

    out = {}
    # (1) collision types at completely expanded nodes of endpoint selection
    ctype = collections.Counter()
    pair_nonparent = collections.Counter()
    supplied = collections.Counter()
    for tid, pol in by.items():
        ps = len(frame[tid]['candidate_panel'])
        order = frame[tid]['candidate_panel']
        for ts in nodes_of(pol['effect_aware']).values():
            if len(ts) != ps:
                continue
            parent = ts[0]['parent_endpoint_key']
            first = {}
            for t in ts:
                if t['kind'] != 'tactic_state':
                    continue
                k = t['endpoint_key']
                if k in first:
                    a = first[k]
                    if k == parent:
                        ctype['equal_to_parent'] += 1
                    else:
                        ctype['new_state'] += 1
                        x, y = sorted([r2.head(a['tactic']), r2.head(t['tactic'])])
                        pair_nonparent[x + '/' + y] += 1
                    if a['tactic'] not in generic24 or t['tactic'] not in generic24:
                        supplied['collisions_with_supplied_step'] += 1
                        if a['registered_next_witness']:
                            supplied['supplied_kept'] += 1
                            # would the supplied step precede the duplicate in hash order without promotion?
                            if order.index(a['tactic']) < order.index(t['tactic']):
                                supplied['kept_also_in_hash_order'] += 1
                            else:
                                supplied['kept_only_through_rank_four'] += 1
                        if t['registered_next_witness']:
                            supplied['supplied_discarded'] += 1
                else:
                    first[k] = t
    out['collision_types'] = dict(ctype)
    out['collision_pairs_new_state'] = pair_nonparent.most_common(15)
    out['supplied_step_collisions'] = dict(supplied)

    # (2) where full expansion spent its extra work: expanded nodes inside subtrees rooted at a sibling duplicate
    def keymap(job):
        m = {}
        for ts in nodes_of(job).values():
            k = ts[0]['parent_endpoint_key']
            if k not in m or len(ts) > len(m[k]):
                m[k] = ts
        return m

    def simulate(root, m, mode, panel_size, drop=frozenset(), attribute=False):
        queue = collections.deque([(root, 0, frozenset([root]), None)])
        seen = {root}
        inv = nodes = 0
        spent = collections.Counter()
        while queue:
            if nodes >= LIM_NODES:
                return False, inv, nodes, 'node_limit', spent
            k, depth, anc, origin = queue.popleft()
            if depth >= LIM_DEPTH:
                continue
            nodes += 1
            if k not in m:
                return None, inv, nodes, 'unobserved', spent
            ts = [t for t in m[k] if t['tactic'] not in drop]
            if drop:  # re-apply the rank-four rule for a recognized supplied step
                w = [i for i, t in enumerate(ts) if t['registered_next_witness']]
                if w and w[0] != 3 and len(ts) > 3:
                    t = ts.pop(w[0])
                    ts.insert(3, t)
            if len(m[k]) < panel_size:
                ts_full = False
            else:
                ts_full = True
            children = []
            for t in ts:
                if inv >= LIM_INV:
                    return False, inv, nodes, 'budget', spent
                inv += 1
                if origin:
                    spent[origin] += 1
                if t['kind'] == 'proof_finished':
                    return True, inv, nodes, 'proved', spent
                if t['kind'] == 'tactic_state':
                    children.append((t['endpoint_key'], r2.head(t['tactic'])))
            if not ts_full and inv < LIM_INV:
                return None, inv, nodes, 'truncated_log', spent
            sib = {}
            for ck, h in children:
                dup_origin = None
                if ck in sib:
                    if mode in ('sibling', 'global'):
                        continue
                    dup_origin = '/'.join(sorted([sib[ck], h]))
                else:
                    sib[ck] = h
                if ck in anc:
                    continue
                if mode == 'global':
                    if ck in seen:
                        continue
                    seen.add(ck)
                queue.append((ck, depth + 1, anc | {ck}, origin or (dup_origin if attribute else None)))
        return False, inv, nodes, 'queue_exhausted', spent

    attrib = collections.Counter()
    reduced = collections.Counter()
    drop_generic = {'ring_nf', 'aesop (config := { maxRuleApplications := 16 })', 'constructor <;> try assumption'}
    incomplete = []
    for tid, pol in by.items():
        full = pol['full']
        ps = len(frame[tid]['candidate_panel'])
        m_full = keymap(full)
        m_all = {}
        for p in pol.values():
            for k, v in keymap(p).items():
                if k not in m_all or len(v) > len(m_all[k]):
                    m_all[k] = v
        root = full['initial_endpoint_key']
        s, inv, n, status, spent = simulate(root, m_full, 'full', ps, attribute=True)
        if s is not None and s == full['solved'] and inv == full['tactic_invocations']:
            attrib['roots_reproduced'] += 1
            for k, v in spent.items():
                attrib[k] += v
        g = simulate(root, m_all, 'global', ps)
        if g[0] is None:
            incomplete.append({'target_id': tid, 'stratum': full['stratum'], 'status': g[3],
                               'invocations_before_stop': g[1], 'nodes_before_stop': g[2],
                               'full': [full['solved'], full['tactic_invocations']],
                               'endpoint_selection': [pol['effect_aware']['solved'], pol['effect_aware']['tactic_invocations']]})
        drop = frozenset(t for t in drop_generic if t not in frame[tid]['authored_witness_tactics'])
        rf = simulate(root, m_full, 'full', ps, drop=drop)
        rs = simulate(root, m_full, 'sibling', ps, drop=drop)
        if rf[0] is not None and rs[0] is not None:
            reduced['roots'] += 1
            reduced['full_solved'] += bool(rf[0])
            reduced['sibling_solved'] += bool(rs[0])
            reduced['full_invocations'] += rf[1]
            reduced['sibling_invocations'] += rs[1]
            reduced['full_nodes'] += rf[2]
            reduced['sibling_nodes'] += rs[2]
            reduced['orig_full_invocations'] += full['tactic_invocations']
            reduced['orig_sibling_invocations'] += pol['effect_aware']['tactic_invocations']
            reduced['losses'] += bool(rf[0]) and not bool(rs[0])
    out['full_expansion_invocations_in_duplicate_subtrees'] = dict(attrib)
    out['reduced_generic_panel_replay'] = dict(reduced)
    out['reduced_generic_panel_dropped'] = sorted(drop_generic)
    out['global_replay_incomplete_roots'] = incomplete
    return out


def main():
    cs, st = r2.load()
    R = {}
    R['alternative_groupings'] = {}
    for gname in ('implementation', 'aesop_separate', 'norm_num_separate', 'both_separate'):
        lab = grouping(gname)
        for nm, rows in (('case_series', cs), ('strict', st)):
            for rep in ('text', 'struct'):
                R['alternative_groupings'][f'{gname}|{nm}|{rep}'] = {
                    'full': r2.table(rows, rep, 'full', label=lab), 'dedup': r2.table(rows, rep, 'dedup', label=lab)}
    R['coactivity'] = {f'{nm}|{rep}': coactivity(rows, rep) for nm, rows in (('case_series', cs), ('strict', st)) for rep in ('text', 'struct')}
    R['strict_views'] = {rep: view_table(st, rep) for rep in ('text', 'struct')}
    R['strict_cluster_only_bootstrap'] = {v: cluster_bootstrap(st, 'struct', v) for v in ('full', 'dedup')}
    R['strict_mathlib_strata'] = strict_strata(st)
    R['strict_within_rep_parse'] = within_rep_parse(st)
    R['case_parse_failures'] = case_parse_failures(cs)
    R['representatives'] = {
        'non_first_roots': len({r['slug'] for r in st if not r['pos'].get('first_tactic', False)}),
        'attribute_roots': len({r['slug'] for r in st if set(r['pos'].get('attrs', [])) & r2.SELF_ATTRS}),
    }
    R['attributes_found'] = {nm: collections.Counter(a for r in rows for a in r['pos'].get('attrs', [])).most_common()
                             for nm, rows in (('case_series', cs), ('strict', st))}
    R['multistep'] = multistep()
    json.dump(R, open(W / 'round3_analysis.json', 'w'), indent=1, default=list)
    print(json.dumps({k: v for k, v in R.items() if k != 'alternative_groupings'}, indent=1, default=list)[:6000])
    for k, v in R['alternative_groupings'].items():
        print(k, v['full']['nonterminal'], v['dedup']['nonterminal'])


if __name__ == '__main__':
    main()
