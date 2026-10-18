#!/usr/bin/env python3
"""Round-2 offline analyses (no Lean execution).

Inputs: compact rows exported by export_compact_rows.py, the root-position
classification (classify_roots.py over SHA-verified source files), and the Exp62
transition logs.  Output: round2_analysis.json.
"""
import collections
import json
import math
import random
import re
import sys
from pathlib import Path

W = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
D = W / 'data'

GROUP = {"simp": "simp", "simpa": "simp", "simp_all": "simp", "aesop": "aesop", "aesop?": "aesop",
         "ring": "ring", "ring_nf": "ring"}
DIRECT = {"aesop?", "exact?"}
ENGINE = {"simp": "simplifier", "simpa": "simplifier", "simp_all": "simplifier", "norm_num": "simplifier",
          "aesop": "simplifier", "aesop?": "simplifier", "ring": "ring", "ring_nf": "ring",
          "exact?": "search", "solve_by_elim": "search", "decide": "decide", "native_decide": "decide"}
SELF_ATTRS = {"simp", "fun_prop", "ext", "aesop", "norm_num", "positivity", "grind"}


def head(t):
    s = t.strip()
    tok = re.split(r"[\s\[({|;]+", s, maxsplit=1)[0] if s else ""
    return tok or "<empty>"


def dedup(order):
    seen, out = set(), []
    for t in order:
        if t in DIRECT:
            continue
        g = GROUP.get(t, t)
        if g in seen:
            continue
        seen.add(g)
        out.append(t)
    return out


def load():
    cs = [json.loads(l) for l in open(D / 'case_series_rows.jsonl')]
    st = [json.loads(l) for l in open(D / 'strict_rows.jsonl')]
    pos = json.load(open(W / 'root_positions.json'))
    for r, p in zip(cs + st, pos):
        assert r['full_name'] == p['full_name']
        r['pos'] = p
    return cs, st


def witness_classes(cands, rep, label=head):
    cl = collections.defaultdict(list)
    for c in cands:
        if c['ok'] and not c['noop_' + rep]:
            cl[c[rep]].append(c)
    return cl


def pos_flags(cands, rep, label=head, require_visible=False):
    """Return (positive, nonterminal) under representation rep; pairs need different labels."""
    Y = NT = False
    for key, v in witness_classes(cands, rep).items():
        if require_visible:
            v = [c for c in v if not c['noop_text']]
        if len({label(c['tactic']) for c in v}) >= 2:
            Y = True
            if not v[0]['terminal']:
                NT = True
    return Y, NT


def table(rows, rep, view='full', label=head, exclude=(), require_visible=False, root_filter=None):
    Y = NT = n = 0
    for r in rows:
        if root_filter and not root_filter(r):
            continue
        n += 1
        order = [c['tactic'] for c in r['candidates'] if c['tactic'] not in exclude]
        by = {c['tactic']: c for c in r['candidates']}
        panel = [by[t] for t in (order if view == 'full' else dedup(order))]
        y, nt = pos_flags(panel, rep, label, require_visible)
        Y += y
        NT += nt
    return {'roots': n, 'positive': Y, 'nonterminal': NT, 'terminal_only': Y - NT}


def four_way(rows, rep):
    out = collections.defaultdict(collections.Counter)
    for r in rows:
        for c in r['candidates']:
            t = c['tactic']
            if not c['ok']:
                out[t]['failed'] += 1
            elif c['terminal']:
                out[t]['closed'] += 1
            elif c['noop_' + rep]:
                out[t]['unchanged'] += 1
            else:
                out[t]['changed_nonterminal'] += 1
    return {t: dict(v) for t, v in out.items()}


def macro_struct(rows, rep, panel_fn, reps=1000, seed=0):
    """Mean over repositories of positive-root rates, averaged over random panels."""
    rng = random.Random(seed)
    slugs = sorted({r['slug'] for r in rows})
    vals = []
    for _ in range(reps):
        per = collections.defaultdict(list)
        for r in rows:
            order = [c['tactic'] for c in r['candidates']]
            by = {c['tactic']: c for c in r['candidates']}
            panel = [by[t] for t in panel_fn(order, rng)]
            per[r['slug']].append(pos_flags(panel, rep)[0])
        vals.append(sum(sum(v) / len(v) for v in per.values()) / len(slugs))
    vals.sort()
    return {'mean': sum(vals) / len(vals), 'p2.5': vals[int(0.025 * len(vals))], 'p97.5': vals[int(0.975 * len(vals)) - 1]}


def rarefaction(rows, rep, label):
    productive = sorted({c['tactic'] for r in rows for c in r['candidates'] if c['ok']})
    removed_by_dedup = ['simpa', 'simp_all', 'aesop?', 'ring_nf', 'exact?']
    res = {'productive_programs': productive}
    res['random_k18'] = macro_struct(rows, rep, lambda o, g: g.sample(o, 18), 1000, 18)
    def matched(o, g):
        pool = [t for t in o if t in productive]
        drop = set(g.sample(pool, 5))
        return [t for t in o if t not in drop]
    res['drop5_random_productive'] = macro_struct(rows, rep, matched, 1000, 5)
    res['dedup'] = macro_struct(rows, rep, lambda o, g: dedup(o), 1, 0)
    res['full'] = macro_struct(rows, rep, lambda o, g: o, 1, 0)
    res['label'] = label
    return res


def pairs_table(rows, rep, view, nonterminal_only=True):
    cnt = collections.Counter()
    reps = collections.defaultdict(set)
    for r in rows:
        order = [c['tactic'] for c in r['candidates']]
        by = {c['tactic']: c for c in r['candidates']}
        panel = [by[t] for t in (order if view == 'full' else dedup(order))]
        ps = set()
        for key, v in witness_classes(panel, rep).items():
            if nonterminal_only and v[0]['terminal']:
                continue
            hs = sorted({head(c['tactic']) for c in v})
            for i in range(len(hs)):
                for j in range(i + 1, len(hs)):
                    ps.add(hs[i] + '/' + hs[j])
        for p in ps:
            cnt[p] += 1
            reps[p].add(r['slug'])
    return [(p, n, len(reps[p])) for p, n in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))]


def within_rep_bootstrap(rows, rep, view, reps=20000, seed=20260918):
    """Frame-conditional interval: keep the representatives fixed and resample roots within each."""
    per = collections.defaultdict(list)
    for r in rows:
        order = [c['tactic'] for c in r['candidates']]
        by = {c['tactic']: c for c in r['candidates']}
        panel = [by[t] for t in (order if view == 'full' else dedup(order))]
        per[r['slug']].append(pos_flags(panel, rep)[0])
    rng = random.Random(seed)
    slugs = sorted(per)
    vals = []
    for _ in range(reps):
        tot = 0.0
        for s in slugs:
            v = per[s]
            tot += sum(v[rng.randrange(len(v))] for _ in range(len(v))) / len(v)
        vals.append(tot / len(slugs))
    vals.sort()
    point = sum(sum(v) / len(v) for v in per.values()) / len(slugs)
    return {'estimate': point, 'p2.5': vals[int(0.025 * reps)], 'p97.5': vals[int(0.975 * reps) - 1],
            'replicates': reps, 'seed': seed}


def root_position_kinds(rows):
    return dict(collections.Counter((r['pos'].get('first_tactic', False), r['pos'].get('body')) for r in rows).items())


def dedup_pref(order, pref):
    """Deduplicated view that keeps `pref` as the representative of the simp group when present."""
    groups = collections.defaultdict(list)
    for t in order:
        if t not in DIRECT:
            groups[GROUP.get(t, t)].append(t)
    seen, out = set(), []
    for t in order:
        if t in DIRECT:
            continue
        g = GROUP.get(t, t)
        if g in seen:
            continue
        seen.add(g)
        out.append(pref if (g == 'simp' and pref in groups[g]) else groups[g][0])
    return out


def dedup_representative(rows, rep):
    res = {}
    for pref in ('simp', 'simpa', 'simp_all'):
        Y = NT = 0
        for r in rows:
            order = [c['tactic'] for c in r['candidates']]
            by = {c['tactic']: c for c in r['candidates']}
            y, nt = pos_flags([by[t] for t in dedup_pref(order, pref)], rep)
            Y += y
            NT += nt
        res[pref] = {'positive': Y, 'nonterminal': NT}
    return res


# ------------------------------------------------------------------ multistep
def multistep():
    jobs = [json.loads(l) for l in open(D / 'multistep_jobs.jsonl')]
    by = collections.defaultdict(dict)
    for j in jobs:
        by[j['target_id']][j['policy']] = j
    LIM_INV, LIM_NODES, LIM_DEPTH = 768, 32, 6

    def key_map(js):
        """key -> ordered transitions of the first expansion seen with that key."""
        m = {}
        for j in js:
            nodes = collections.OrderedDict()
            for t in j['transitions']:
                nodes.setdefault(t['expanded_node_ordinal'], []).append(t)
            for ordn, ts in nodes.items():
                k = ts[0]['parent_endpoint_key']
                complete = (ts[-1]['kind'] == 'proof_finished') or True
                if k not in m or len(ts) > len(m[k]):
                    m[k] = ts
        return m

    def simulate(root_key, m, mode, panel_size):
        """mode: full | sibling | global.  Returns (solved, invocations, nodes, status)."""
        queue = collections.deque([(root_key, 0, frozenset([root_key]))])
        seen = {root_key}
        inv = nodes = 0
        while queue:
            if nodes >= LIM_NODES:
                return False, inv, nodes, 'node_limit'
            k, depth, anc = queue.popleft()
            if depth >= LIM_DEPTH:
                continue
            nodes += 1
            if k not in m:
                return None, inv, nodes, 'unobserved'
            ts = m[k]
            children = []
            for t in ts:
                if inv >= LIM_INV:
                    return False, inv, nodes, 'budget'
                inv += 1
                if t['kind'] == 'proof_finished':
                    return True, inv, nodes, 'proved'
                if t['kind'] == 'tactic_state':
                    children.append(t['endpoint_key'])
            if len(ts) < panel_size and inv < LIM_INV:
                return None, inv, nodes, 'truncated_log'
            sib = set()
            for ck in children:
                if mode in ('sibling', 'global'):
                    if ck in sib:
                        continue
                    sib.add(ck)
                if ck in anc:
                    continue
                if mode == 'global':
                    if ck in seen:
                        continue
                    seen.add(ck)
                queue.append((ck, depth + 1, anc | {ck}))
        return False, inv, nodes, 'queue_exhausted'

    frame = {json.loads(l)['target_id']: json.loads(l) for l in open(D / 'multistep_frame.jsonl')}
    # the 24 generic programs are the programs common to every frozen panel
    generic24 = set.intersection(*(set(f['candidate_panel']) for f in frame.values()))
    assert len(generic24) == 24
    out = collections.Counter()
    per_root = []
    collisions_pairs = collections.Counter()
    key_checks = collections.Counter()
    authored_pruned = collections.Counter()
    complete_pairs = collections.Counter()
    complete_kind = collections.Counter()
    for tid, pol in by.items():
        full, ea = pol['full'], pol['effect_aware']
        panel_size = len(frame[tid]['candidate_panel'])
        m_all = key_map([pol[p] for p in pol])
        m_full = key_map([full])
        root = full['initial_endpoint_key']
        sims = {}
        for mode, mp in (('full', m_full), ('sibling', m_full), ('global', m_all)):
            sims[mode] = simulate(root, mp, mode, panel_size)
        rec = {'target_id': tid, 'stratum': full['stratum'],
               'actual_full': (full['solved'], full['tactic_invocations']),
               'actual_ea': (ea['solved'], ea['tactic_invocations']),
               'actual_head': (pol['head_dedup']['solved'], pol['head_dedup']['tactic_invocations']),
               'sim': {k: list(v) for k, v in sims.items()}}
        per_root.append(rec)
        out['full_reproduced'] += (sims['full'][0] == full['solved'] and sims['full'][1] == full['tactic_invocations'])
        out['sibling_reproduces_ea'] += (sims['sibling'][0] == ea['solved'] and sims['sibling'][1] == ea['tactic_invocations'])
        # collisions by program pair at EA-expanded nodes, and authored-step children pruned
        nodes = collections.OrderedDict()
        for t in ea['transitions']:
            nodes.setdefault(t['expanded_node_ordinal'], []).append(t)
        for ordn, ts in nodes.items():
            first_by_key = {}
            for t in ts:
                if t['kind'] != 'tactic_state':
                    continue
                k = t['endpoint_key']
                if k in first_by_key:
                    a, b = sorted([head(first_by_key[k]['tactic']), head(t['tactic'])])
                    collisions_pairs[a + '/' + b] += 1
                    if t.get('registered_next_witness'):
                        authored_pruned['authored_child_pruned'] += 1
                else:
                    first_by_key[k] = t
            if len(ts) == panel_size:  # completely expanded nodes only
                fb = {}
                for t in ts:
                    if t['kind'] != 'tactic_state':
                        continue
                    k = t['endpoint_key']
                    if k in fb:
                        a, b = sorted([head(fb[k]['tactic']), head(t['tactic'])])
                        complete_pairs[a + '/' + b] += 1
                        complete_kind['total'] += 1
                        complete_kind['generic_generic'] += (fb[k]['tactic'] in generic24 and t['tactic'] in generic24)
                        complete_kind['discarded_is_registered_next_step'] += bool(t.get('registered_next_witness'))
                    else:
                        fb[k] = t
        # key adequacy: in full logs, nodes expanded more than once with the same key
        fnodes = collections.defaultdict(list)
        for t in full['transitions']:
            fnodes[t['expanded_node_ordinal']].append(t)
        bykey = collections.defaultdict(list)
        for ordn, ts in fnodes.items():
            if len(ts) == panel_size:  # complete expansions only
                bykey[ts[0]['parent_endpoint_key']].append(tuple((t['tactic'], t['kind'], t['endpoint_key']) for t in ts))
        for k, exps in bykey.items():
            if len(exps) > 1:
                key_checks['keys_expanded_more_than_once'] += 1
                key_checks['identical_outcomes'] += all(e == exps[0] for e in exps)
    agg = collections.defaultdict(lambda: collections.Counter())
    for rec in per_root:
        for mode, (s, inv, n, status) in rec['sim'].items():
            agg[mode]['status_' + status] += 1
            if s is not None:
                agg[mode]['solved'] += bool(s)
                agg[mode]['invocations'] += inv
                agg[mode]['simulable'] += 1
    # paired comparison on roots where global simulation is complete
    comp = collections.Counter()
    for rec in per_root:
        g = rec['sim']['global']
        if g[0] is None:
            continue
        comp['roots'] += 1
        comp['full_inv'] += rec['actual_full'][1]
        comp['ea_inv'] += rec['actual_ea'][1]
        comp['global_inv'] += g[1]
        comp['full_solved'] += rec['actual_full'][0]
        comp['ea_solved'] += rec['actual_ea'][0]
        comp['global_solved'] += g[0]
        comp['global_lt_ea'] += g[1] < rec['actual_ea'][1]
    head_losses = sum(1 for rec in per_root if rec['actual_full'][0] and not rec['actual_head'][0])
    head_gains = sum(1 for rec in per_root if rec['actual_head'][0] and not rec['actual_full'][0])
    expanded = {p: sum(by[t][p]['expanded_nodes'] for t in by) for p in ('full', 'effect_aware')}
    return {'validation': dict(out), 'simulation': {k: dict(v) for k, v in agg.items()},
            'paired_global_vs_actual': dict(comp), 'collisions_by_pair': collisions_pairs.most_common(15),
            'collisions_total': sum(collisions_pairs.values()), 'authored_child_pruned': dict(authored_pruned),
            'collisions_complete_nodes': dict(complete_kind), 'collisions_complete_by_pair': complete_pairs.most_common(15),
            'key_adequacy_full_logs': dict(key_checks), 'head_dedup_losses_vs_full': head_losses,
            'head_dedup_gains_vs_full': head_gains, 'expanded_nodes': expanded, 'per_root': per_root}


def main():
    cs, st = load()
    R = {}
    for name, rows in (('case_series', cs), ('strict', st)):
        S = R.setdefault(name, {})
        S['roots'] = len(rows)
        S['first_tactic_roots'] = sum(r['pos'].get('first_tactic', False) for r in rows)
        S['attr_roots'] = sum(bool(set(r['pos'].get('attrs', [])) & SELF_ATTRS) for r in rows)
        for first in (True, False):
            sel = [r for r in rows if r['pos'].get('first_tactic', False) == first]
            k = 'first' if first else 'internal'
            S[f'{k}_roots'] = len(sel)
            S[f'{k}_exact_success'] = sum(c['ok'] for r in sel for c in r['candidates'] if c['tactic'] == 'exact?')
            S[f'{k}_exact_attempts'] = sum(1 for r in sel for c in r['candidates'] if c['tactic'] == 'exact?')
            S[f'{k}_authored_terminal'] = sum(r['authored']['terminal'] for r in sel)
            for rep in ('text', 'struct'):
                S[f'{k}_{rep}_full'] = table(sel, rep)
        S['root_position_kinds'] = {f'{k[0]}|{k[1]}': v for k, v in root_position_kinds(rows).items()}
        S['four_way_text'] = four_way(rows, 'text')
        S['four_way_struct'] = four_way(rows, 'struct')
        for rep in ('text', 'struct'):
            S[f'{rep}_full'] = table(rows, rep)
            S[f'{rep}_dedup'] = table(rows, rep, 'dedup')
            S[f'{rep}_engine_full'] = table(rows, rep, 'full', label=lambda t: ENGINE.get(t, t))
            S[f'{rep}_engine_dedup'] = table(rows, rep, 'dedup', label=lambda t: ENGINE.get(t, t))
            S[f'{rep}_conservative_full'] = table(rows, rep, 'full', exclude=('exact?',),
                                                  root_filter=lambda r: not (set(r['pos'].get('attrs', [])) & SELF_ATTRS))
            S[f'{rep}_conservative_dedup'] = table(rows, rep, 'dedup', exclude=('exact?',),
                                                   root_filter=lambda r: not (set(r['pos'].get('attrs', [])) & SELF_ATTRS))
            S[f'{rep}_internal_only_full'] = table(rows, rep, root_filter=lambda r: not r['pos'].get('first_tactic', False))
        S['dedup_simp_representative_text'] = dedup_representative(rows, 'text')
        S['dedup_simp_representative_struct'] = dedup_representative(rows, 'struct')
        S['struct_visible_full'] = table(rows, 'struct', require_visible=True)
        S['struct_visible_dedup'] = table(rows, 'struct', 'dedup', require_visible=True)
        S['nonterminal_pairs_struct_dedup'] = pairs_table(rows, 'struct', 'dedup')[:15]
        S['nonterminal_pairs_text_dedup'] = pairs_table(rows, 'text', 'dedup')[:15]
        S['nonterminal_pairs_struct_full'] = pairs_table(rows, 'struct', 'full')[:15]
        if name == 'strict':
            def all_parse(r):
                return all(c.get('failure') != 'parse' for c in r['candidates'])
            S['all_23_parse_roots'] = sum(all_parse(r) for r in st)
            S['all_parse_reps'] = len({r['slug'] for r in st if all_parse(r)})
            for rep in ('text', 'struct'):
                S[f'{rep}_full_all_parse'] = table(st, rep, root_filter=all_parse)
                S[f'{rep}_dedup_all_parse'] = table(st, rep, 'dedup', root_filter=all_parse)
                S[f'{rep}_full_parse_failures'] = table(st, rep, root_filter=lambda r: not all_parse(r))
                S[f'{rep}_dedup_parse_failures'] = table(st, rep, 'dedup', root_filter=lambda r: not all_parse(r))
            S['frame_conditional_struct_full'] = within_rep_bootstrap(st, 'struct', 'full')
            S['frame_conditional_struct_dedup'] = within_rep_bootstrap(st, 'struct', 'dedup')
            S['ring_pair_roots_text_unchanged'] = sum(
                1 for r in st
                if any(c['tactic'] == 'ring' and c['ok'] and not c['terminal'] and not c['noop_struct'] and c['noop_text'] for c in r['candidates']))
        S['rarefaction_struct'] = rarefaction(rows, 'struct', 'struct')
        S['rarefaction_text'] = rarefaction(rows, 'text', 'text')
    R['multistep'] = multistep()
    json.dump(R, open(W / 'round2_analysis.json', 'w'), indent=1, default=list)


if __name__ == '__main__':
    main()
