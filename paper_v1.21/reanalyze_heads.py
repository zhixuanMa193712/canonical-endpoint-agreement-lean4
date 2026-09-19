"""Post-outcome lexical-label correction; never runs Lean or edits source archives."""
from pathlib import Path
import ast, collections, hashlib, itertools, json, re, zipfile
import numpy as np

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
OUT = ROOT / 'analysis'
OUT.mkdir(exist_ok=True)
tree = ast.parse((PROJECT/'experiment51_external_repository_replication/experiment51_protocol.py').read_text())
constants = {}
for node in tree.body:
    name = node.targets[0].id if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) else node.target.id if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) else None
    if name in {'CANDIDATE_GENEALOGY','FAMILY_BY_HEAD'}:
        constants[name] = ast.literal_eval(node.value)

def head(t):
    return re.split(r'[\s\[({|;]+', t.strip(), maxsplit=1)[0] or '<empty>'

def view(w, allowed, corrected):
    branches = [r for r in w['candidates'] if r['tactic'] in allowed and r.get('executable') is True]
    initial = w['initial_endpoints']['struct']['sha256']
    groups = collections.defaultdict(list)
    for b in branches:
        groups[b['endpoints']['struct']['sha256']].append(b)
    pairs, cross, nonterm = set(), False, False
    pair_count = 0
    for endpoint, bs in groups.items():
        if endpoint == initial: continue
        for a,b in itertools.combinations(bs,2):
            ha,hb = (head(a['tactic']),head(b['tactic'])) if corrected else (a['head'],b['head'])
            if ha == hb: continue
            pair_count += 1
            pairs.add(tuple(sorted((ha,hb))))
            fa,fb = (constants['FAMILY_BY_HEAD'].get(h,'other:'+h) for h in (ha,hb)) if corrected else (a['family'],b['family'])
            cross |= fa != fb
            nonterm |= a.get('terminal') is False and b.get('terminal') is False
    return dict(Y=bool(pairs), cross=cross, nonterminal=nonterm, pairs=sorted(pairs), pair_count=pair_count,
                successful=len(branches), endpoint_classes=len(groups), duplicate_successful=len(branches)-len(groups))

def robust(tactics):
    seen=set(); result=[]
    for t in tactics:
        g=constants['CANDIDATE_GENEALOGY'][t]
        if g['class'] in {'direct_suggestion','direct_control_wrapper'} or g['group'] in seen: continue
        seen.add(g['group']);result.append(t)
    return result

def summarize(rows, key):
    slugs=sorted({r['slug'] for r in rows})
    arr=np.array([[int(r[key]['Y']) for r in rows if r['slug']==s] for s in slugs])
    rng=np.random.default_rng(20260918)
    vals=[]
    for _ in range(20000):
        chosen=rng.integers(0,len(slugs),len(slugs))
        roots=rng.integers(0,arr.shape[1],arr.shape)
        vals.append(float(arr[chosen[:,None],roots].mean()))
    rates=arr.mean(axis=1)
    pair_repos=collections.defaultdict(set)
    for r in rows:
        for p in r[key]['pairs']: pair_repos[tuple(p)].add(r['slug'])
    filemeans=[]
    for s in slugs:
        fs=collections.defaultdict(list)
        for r in rows:
            if r['slug']==s:fs[r['file']].append(r[key]['Y'])
        filemeans.append(float(np.mean([np.mean(v) for v in fs.values()])))
    return dict(positives=int(arr.sum()),mean=float(arr.mean()),ci=np.quantile(vals,[.025,.975]).tolist(),
      median_repository=float(np.median(rates)),range=[float(rates.min()),float(rates.max())],
      nonzero_repositories=int(sum(rates>0)),cross=sum(r[key]['cross'] for r in rows),nonterminal=sum(r[key]['nonterminal'] for r in rows),
      cross_repositories=sum(any(r[key]['cross'] for r in rows if r['slug']==s) for s in slugs),
      nonterminal_repositories=sum(any(r[key]['nonterminal'] for r in rows if r['slug']==s) for s in slugs),
      distinct_pairs=len(pair_repos),recurring_pairs=sum(len(v)>=2 for v in pair_repos.values()),
      equal_file_mean=float(np.mean(filemeans)),loo_range=[float(min((rates.sum()-x)/(len(rates)-1) for x in rates)),float(max((rates.sum()-x)/(len(rates)-1) for x in rates))],
      distributions={k:dict(zip(['min','q1','median','q3','max'],np.quantile([r[key][k] for r in rows],[0,.25,.5,.75,1]).tolist())) for k in ['successful','endpoint_classes','pair_count','duplicate_successful']})

def run(number, filename):
    archive=PROJECT/filename
    expected={64:'2aaebc31501b5946a6dcfb7a279d2dda0cdd4cf20160f7e49ec63674e5411130',51:'f8c84a92ef4a7dc025a9f7918a0f16af91160acb112bb0578ee0bf431057511b'}
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected[number]
    with zipfile.ZipFile(archive) as z:
        analysis_name=next(n for n in z.namelist() if n.endswith('/analysis/theorem_rows.jsonl'))
        source_rows=[json.loads(s) for s in z.read(analysis_name).splitlines()]
        wanted={r['theorem_id'] for r in source_rows}
        workers={}
        for n in z.namelist():
            if '/scientific/' not in n or '/theorems/' not in n or not n.endswith('.json'):continue
            w=json.loads(z.read(n))
            if w.get('theorem_id') in wanted and w.get('worker_ok') is True:
                if w['theorem_id'] in workers:
                    assert workers[w['theorem_id']]['candidates']==w['candidates']
                workers[w['theorem_id']]=w
        assert len(workers)==len(wanted)
        source_by_id={r['theorem_id']:r for r in source_rows}
        rows=[]; changed=collections.Counter()
        for rid,w in sorted(workers.items()):
            for b in w['candidates']:
                if b['head']!=head(b['tactic']):changed[(b['tactic'],b['head'],head(b['tactic']))]+=1
            row=dict(theorem_id=rid,slug=w['slug'],file=w['file_path'])
            for key,allowed in [('full',w['candidate_order']),('diverse',robust(w['candidate_order']))]:
                row[key]=view(w,allowed,True);row['archived_'+key]=view(w,allowed,False)
                archive_key='L0' if key=='full' else 'L-mechanism-diverse'
                assert row['archived_'+key]['Y']==source_by_id[rid][archive_key]['Y']
                # Independent direct pair predicate, separate from grouping implementation.
                bs=[b for b in w['candidates'] if b['tactic'] in allowed and b.get('executable') is True]
                direct=any(head(a['tactic'])!=head(b['tactic']) and a['endpoints']['struct']['sha256']==b['endpoints']['struct']['sha256']!=w['initial_endpoints']['struct']['sha256'] for a,b in itertools.combinations(bs,2))
                assert direct==row[key]['Y']
            rows.append(row)
    assert len(rows)=={64:512,51:576}[number]
    result=dict(archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),roots=len(rows),
        numpy_version=np.__version__,protocol_constants_sha256=hashlib.sha256(json.dumps(constants,sort_keys=True).encode()).hexdigest(),
        correction='post-outcome lexical relabeling of stored executions; no new Lean calls',
        bootstrap='NumPy PCG64 seed 20260918; 20000 two-level repository/root resamples; linear percentile',
        full=summarize(rows,'full'),diverse=summarize(rows,'diverse'),
        archived_positives={key:sum(r['archived_'+key]['Y'] for r in rows) for key in ['full','diverse']},
        changed_labels=[dict(tactic=t,archived=h,corrected=c,rows=n) for (t,h,c),n in sorted(changed.items())])
    (OUT/f'exp{number}_corrected_rows.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    (OUT/f'exp{number}_correction.json').write_text(json.dumps(result,indent=2))
    print(number,json.dumps(result,indent=2))

def cluster_sensitivity():
    with zipfile.ZipFile(PROJECT/'experiment62_multistep_solvable_search_fix1_results.zip') as z:
        name=next(n for n in z.namelist() if n.endswith('confirmation/analysis/paired_root_metrics.jsonl'))
        rows=[json.loads(s) for s in z.read(name).splitlines()]
    rng=np.random.default_rng(20260918)
    groups={}
    for r in rows:
        groups.setdefault(r['stratum'],{}).setdefault(r['theorem_id'].split('::')[0],[]).append(r['effect_aware_call_saving'])
    all_files=sorted({f for fs in groups.values() for f in fs})
    values=[]
    for _ in range(20000):
        selected=collections.Counter(rng.choice(all_files,len(all_files)))
        means=[]
        for files in groups.values():
            sample=[x for f,n in selected.items() for _ in range(n) for x in files.get(f,[])]
            assert sample
            means.append(float(np.mean(sample)))
        values.append(float(np.mean(means)))
    result=dict(status='post-outcome descriptive sensitivity',bootstrap='20000 resamples of all 63 source files; both roots in the shared file retained together across strata; stratum means equally weighted; PCG64 seed 20260918',
        unique_files=len(all_files),
        files_by_stratum={k:len(v) for k,v in groups.items()},ci=np.quantile(values,[.025,.975]).tolist(),mean=float(np.mean([r['effect_aware_call_saving'] for r in rows])),
        loss_note='All observed losses are zero; an ordinary nonparametric cluster bootstrap is degenerate and cannot establish a zero upper risk bound.')
    (OUT/'multistep_file_cluster.json').write_text(json.dumps(result,indent=2))

if __name__=='__main__':
    assert [head(t) for t in ['simp','aesop?','all_goals simp','first | rfl | assumption']]==['simp','aesop?','all_goals','first']
    run(64,'experiment64_strict_v427_external_replication_results.zip')
    run(51,'experiment51_external_repository_replication_fix3_results.zip')
    cluster_sensitivity()
