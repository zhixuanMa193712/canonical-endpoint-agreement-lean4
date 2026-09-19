"""Corrected paired repository frequencies; all 32 repositories, no exclusions.

Contract: show within-repository candidate-view contrast and heterogeneity.
Single paired-dot panel; 16 frozen roots per repository, no per-repo interval.
Python/matplotlib; PDF/SVG and PNG, 5.6 by 7.4 inches, minimum text 8 pt.
Full slugs and aggregate resampling intervals are in Supplement S20.
"""
from pathlib import Path
import collections, csv, json
import matplotlib as mpl
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
mpl.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Helvetica','DejaVu Sans'],'font.size':8,'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'legend.frameon':False})
rows=[json.loads(x) for x in (ROOT/'analysis/exp64_corrected_rows.jsonl').read_text().splitlines()]
groups=collections.defaultdict(list)
for r in rows:groups[r['slug']].append(r)
data=[dict(repository=s,full=100*sum(r['full']['Y'] for r in rs)/len(rs),diverse=100*sum(r['diverse']['Y'] for r in rs)/len(rs)) for s,rs in groups.items()]
data.sort(key=lambda r:(-r['full'],r['repository'].lower()))
with (ROOT/'analysis/figure4_source.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=['repository','full','diverse']);w.writeheader();w.writerows(data)
fig,ax=plt.subplots(figsize=(5.6,7.4))
fig.subplots_adjust(left=.45,right=.98,bottom=.085,top=.90)
ys=list(range(len(data)))
for y,r in zip(ys,data):ax.plot([r['diverse'],r['full']],[y,y],color='#b7c5ce',lw=1,zorder=1)
ax.scatter([r['full'] for r in data],ys,marker='o',s=22,color='#245c89',label='Full panel',zorder=3)
ax.scatter([r['diverse'] for r in data],ys,marker='D',s=20,color='#398477',label='Genealogy-deduplicated',zorder=2)
labels=[r['repository'].split('/',1)[1] for r in data]
ax.set_yticks(ys,labels,fontsize=8);ax.invert_yaxis();ax.set_xlim(-2,103)
ax.set_xticks([0,25,50,75,100]);ax.set_xlabel('Roots with a qualifying witness (%)',fontsize=8)
ax.tick_params(axis='y',length=0,pad=5);ax.spines['left'].set_visible(False)
ax.grid(axis='x',color='#e5e5e5',lw=.6);ax.set_axisbelow(True)
ax.legend(loc='lower right',bbox_to_anchor=(1,1.015),fontsize=8)
fig.savefig(ROOT/'latex/Fig4.pdf')
fig.savefig(ROOT/'analysis/Fig4.svg')
fig.savefig(ROOT/'analysis/Fig4.png',dpi=300)
