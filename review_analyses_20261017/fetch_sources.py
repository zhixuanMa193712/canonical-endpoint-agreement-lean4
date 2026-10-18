"""Sparse-fetch the sampled source files at the pinned commits and verify their SHA-256 values.

Usage: python fetch_sources.py <work dir containing data/>  -> src/<owner>__<repo>/...
"""
import json,subprocess,collections,hashlib,os,sys
W=sys.argv[1] if len(sys.argv)>1 else '.'
rows=[json.loads(l) for f in ['case_series_rows.jsonl','strict_rows.jsonl'] for l in open(f'{W}/data/{f}')]
need=collections.defaultdict(set)
for r in rows: need[(r['slug'],r['commit'])].add(r['file_path'])
res={}
for (slug,commit),paths in sorted(need.items()):
    d=f"{W}/src/{slug.replace('/','__')}"
    ok=all(os.path.exists(f'{d}/{p}') for p in paths)
    if not ok:
        os.makedirs(d,exist_ok=True)
        def g(*a): return subprocess.run(['git','-C',d,*a],capture_output=True,text=True,timeout=600)
        if not os.path.exists(d+'/.git'):
            g('init','-q'); g('remote','add','origin',f'https://github.com/{slug}.git')
        g('config','core.sparseCheckout','true')
        extra=['lake-manifest.json','lakefile.toml','lakefile.lean']  # read by scan_dependencies.py
        open(d+'/.git/info/sparse-checkout','w').write('\n'.join('/'+p for p in sorted(paths)+extra)+'\n')
        r1=g('fetch','-q','--depth','1','--filter=blob:none','origin',commit)
        r2=g('checkout','-q','FETCH_HEAD')
        if r1.returncode or r2.returncode: print('FAIL',slug,r1.stderr[-300:],r2.stderr[-300:]); res[slug]='fail'; continue
    res[slug]='ok'
    print('ok',slug,len(paths),flush=True)
# verify hashes
bad=0
for r in rows:
    p=f"{W}/src/{r['slug'].replace('/','__')}/{r['file_path']}"
    if not os.path.exists(p): bad+=1; continue
    h=hashlib.sha256(open(p,'rb').read()).hexdigest()
    if h!=r['source_file_sha256']: bad+=1; print('HASH MISMATCH',r['slug'],r['file_path'])
print('rows',len(rows),'missing or mismatched',bad)
