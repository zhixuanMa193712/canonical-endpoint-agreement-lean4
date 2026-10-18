"""Classify root position and declaration attributes from the SHA-verified source files (no Lean).

Usage: python classify_roots.py <work dir containing data/ and src/>  -> root_positions.json
"""
import json,re,os,collections,sys
W=sys.argv[1] if len(sys.argv)>1 else '.'
DECL=re.compile(rb'^[ \t]*(?:@\[[^\n]*?\][ \t]*\n?[ \t]*)*(?:(?:private|protected|noncomputable|nonrec|unsafe|partial|scoped|local)[ \t]+)*(theorem|lemma|def|instance|example|abbrev|opaque)\b',re.M)
OPEN={ord('('):ord(')'),ord('['):ord(']'),ord('{'):ord('}')}
LANG=b'\xe2\x9f\xa8'; RANG=b'\xe2\x9f\xa9'  # angle brackets
def skip_ws_comments(b,i):
    while i<len(b):
        if b[i:i+1] in (b' ',b'\t',b'\n',b'\r'): i+=1
        elif b[i:i+2]==b'--': 
            j=b.find(b'\n',i); i=len(b) if j<0 else j+1
        elif b[i:i+2]==b'/-':
            depth=0
            while i<len(b):
                if b[i:i+2]==b'/-': depth+=1; i+=2
                elif b[i:i+2]==b'-/': depth-=1; i+=2
                else: i+=1
                if depth==0: break
        else: break
    return i
def body_start(b,ds,limit):
    # find first ':=' at bracket depth 0 after decl start (before limit)
    i=ds; depth=0
    while i<limit:
        c=b[i]
        if b[i:i+2]==b'--':
            j=b.find(b'\n',i); i=limit if j<0 else j+1; continue
        if b[i:i+2]==b'/-':
            i=skip_ws_comments(b,i); continue
        if c in OPEN: depth+=1
        elif c in (ord(')'),ord(']'),ord('}')): depth-=1
        elif b[i:i+3]==LANG: depth+=1; i+=3; continue
        elif b[i:i+3]==RANG: depth-=1; i+=3; continue
        if depth==0 and b[i:i+2]==b':=':
            j=skip_ws_comments(b,i+2)
            if b[j:j+2]==b'by' and (j+2>=len(b) or not (chr(b[j+2]).isalnum() or b[j+2] in b'_')):
                return ('by',skip_ws_comments(b,j+2))
            return ('term',j)
        if depth==0 and c==ord('|') and b[i-1:i] in (b'\n',b' ') and b[:i].rstrip(b' \t').endswith(b'\n'):
            return ('equations',i)
        i+=1
    return ('none',None)
def attrs_before(b,ds):
    # attribute blocks on the declaration line(s) and immediately preceding lines
    seg=b[max(0,ds-2000):ds]
    lines=seg.split(b'\n')
    acc=[]
    # declaration line itself may have @[...]
    for l in reversed(lines[:-1] if lines and lines[-1].strip()==b'' else lines):
        s=l.strip()
        if s.startswith(b'@['): acc.append(s); continue
        if s.startswith(b'/--') or s.endswith(b'-/') or s.startswith(b'--') or s==b'': 
            if s==b'' : break
            continue
        break
    return acc
def classify(r):
    p=f"{W}/src/{r['slug'].replace('/','__')}/{r['file_path']}"
    b=open(p,'rb').read(); pos=r['target_pos']
    ms=[m for m in DECL.finditer(b) if m.start()<=pos]
    if not ms: return {'decl':None}
    m=ms[-1]; ds=m.start()
    kind,bs=body_start(b,ds,pos)
    first = (kind=='by' and bs==pos)
    decl_text=b[ds:min(len(b),ds+400)]
    attr_inline=re.findall(rb'@\[([^\]]*)\]',b[ds:b.find(b'\n',ds) if b.find(b'\n',ds)>0 else ds+200])
    attr_prev=attrs_before(b,ds)
    attrs=[]
    for a in attr_inline+[re.sub(rb'^@\[|\]$',b'',x) for x in attr_prev]:
        # attributes given through `(attr := ...)`, e.g. @[to_additive (attr := simp)]
        for inner in re.findall(rb'attr\s*:=\s*([^)]*)',a):
            for part in inner.split(b','):
                t=part.strip().split()
                if t: attrs.append(t[0].decode('utf-8','ignore'))
        a=re.sub(rb'\([^)]*\)',b'',a)
        for part in a.split(b','):
            t=part.strip().split()
            if t: attrs.append(t[0].decode('utf-8','ignore'))
    attrs=[x for x in attrs if re.fullmatch(r'[A-Za-z_][\w.?!]*',x)]
    short=r['full_name'].split('.')[-1]
    ext_attr=re.findall(rb'^\s*attribute\s*\[([^\]]*)\]\s*([^\n]*)',b,re.M)
    for a,names in ext_attr:
        if short.encode() in names.split() or r['full_name'].encode() in names.split():
            for part in a.split(b','):
                t=part.strip().split()
                if t: attrs.append(t[0].decode('utf-8','ignore'))
    name_ok = short.encode() in decl_text
    return {'decl_kind':m.group(1).decode(),'body':kind,'first_tactic':first,'attrs':sorted(set(attrs)),'name_in_decl':name_ok}
out=[]
for f,study in [('case_series_rows.jsonl','case'),('strict_rows.jsonl','strict')]:
    for l in open(f'{W}/data/{f}'):
        r=json.loads(l); c=classify(r); c['study']=study; c['slug']=r['slug']; c['full_name']=r['full_name']; c['authored']=r['authored_tactic'][:60]
        out.append(c)
json.dump(out,open(f'{W}/root_positions.json','w'),ensure_ascii=False,indent=0)
for study in ['case','strict']:
    rs=[c for c in out if c['study']==study]
    print(study,len(rs),'first',sum(c.get('first_tactic',False) for c in rs),'body',collections.Counter(c.get('body') for c in rs),'name_ok',sum(c.get('name_in_decl',False) for c in rs))
    print('  attrs',collections.Counter(a for c in rs for a in c.get('attrs',[])).most_common(12))
