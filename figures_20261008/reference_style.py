"""Figure presentation adapted from the author-supplied v1.20 PDF.

Uses only the archived observations used by make_figures.py. No statistics
are fitted or resampled. The main-paper order is method, confirmation,
external replication, then sensitivity/repeat execution.
"""
import hashlib
import json
import math
from collections import defaultdict

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Wedge, FancyBboxPatch, FancyArrowPatch

from make_figures import BASE, PROJECT, WIDTH, BLUE, TEAL, PURPLE, GREY, INK, save, soft_card, arrow

ORANGE = "#c77c32"
BLUE = "#256a9e"
TEAL = "#328e91"
PURPLE = "#8060a7"
PALE = "#f4f7fa"


def sheet(height):
    """Draw in physical millimetres, at the actual manuscript width."""
    fig = plt.figure(figsize=(119/25.4, height/25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set(xlim=(0,119), ylim=(0,height), aspect="equal")
    ax.axis("off")
    return fig, ax


def text(ax, x, y, s, size=8, color=INK, weight="normal", ha="left", va="top"):
    return ax.text(x,y,s,fontsize=size,color=color,fontweight=weight,
                   ha=ha,va=va,linespacing=1.25)


def box(ax,x,y,w,h,fill=PALE,edge="none",radius=1.4):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle=f"round,pad=0,rounding_size={radius}",
                 facecolor=fill,edgecolor=edge,linewidth=.55))


def dial(ax,x,y,r,n,d,color=BLUE):
    ax.add_patch(Wedge((x,y),r,0,360,width=.8,facecolor="#dce6ee",edgecolor="none"))
    ax.add_patch(Wedge((x,y),r,90-360*n/d,90,width=.8,facecolor=color,edgecolor="none"))
    text(ax,x,y+1.6,f"{n}/{d}",8,color, "bold",ha="center",va="center")
    text(ax,x,y-2.0,f"{100*n/d:.1f}%",8,GREY,ha="center",va="center")


def canvas(fig):
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")
    return ax


def pipeline():
    fig, ax = sheet(95)
    cards = [
        ("Locate\ntactic", BLUE, "Source file and\nfrozen position", "Elaborate file.\nFind the unique\ntactic node.", "Authored tactic\nand its state"),
        ("Recover\nstate", TEAL, "Context C,\nmetavariables M,\nordered goals G", "Keep one goal.\nReplay authored\ntactic; check\nrecorded result.", "Validated state\ns = (C, M, G)"),
        ("Execute\nbranches", ORANGE, "Validated state;\nfixed candidates", "Restore M, G\nfor each tactic.\nRun separately;\nrecord outcomes.", "Independent\nresulting states"),
        ("Compare\nendpoints", PURPLE, "Successful\nresulting states", "Normalize using κ.\nCompare results\nacross distinct\ntactic heads.", "Endpoint classes\nand root witness"),
    ]
    for i, (title, color, inputs, operation, output) in enumerate(cards):
        x=1+i*29.7
        box(ax,x,19,27.5,73)
        ax.plot([x+2,x+25.5],[91,91],lw=1.5,color=color,solid_capstyle="round")
        ax.add_patch(Circle((x+4,85.8),2.5,facecolor=color,edgecolor="none"))
        text(ax,x+4,85.8,str(i+1),8,"white","bold",ha="center",va="center")
        text(ax,x+8,89.4,title,8.5,color,"bold")
        text(ax,x+2,76,"Input",8,color,"bold")
        text(ax,x+2,71.4,inputs)
        ax.plot([x+2,x+25.5],[55.8,55.8],color="#d8e2e8",lw=.5)
        text(ax,x+2,52.6,"Operation",8,color,"bold")
        text(ax,x+2,47.8,operation)
        box(ax,x+1.3,20.5,24.9,11.5,fill={BLUE:"#e6eff7",TEAL:"#e4f1f0",ORANGE:"#fbefe3",PURPLE:"#eee8f5"}[color])
        text(ax,x+2.2,30.5,output,8,color)
        if i<3:
            ax.add_patch(FancyArrowPatch((x+27.7,59),(x+29.6,59),arrowstyle="-|>",
                         mutation_scale=5,lw=.65,color=GREY))
    ax.plot([2,117],[15,15],color="#d8e2e8",lw=.6)
    text(ax,59.5,12,"One step · single goal · successful domain · candidate relative",8,BLUE,ha="center")
    text(ax,59.5,6.5,"A witness has distinct heads and a shared endpoint changed from the start.",8,GREY,ha="center")
    save(fig, 1)


def ring(fig, cx, cy, radius, fraction, color, thickness=.16):
    """Radius in figure-width units; keep rings physically circular."""
    h = radius * fig.get_figwidth() / fig.get_figheight()
    ax = fig.add_axes([cx-radius, cy-h, 2*radius, 2*h])
    ax.set(xlim=(-1.05, 1.05), ylim=(-1.05, 1.05), aspect="equal")
    ax.axis("off")
    ax.add_patch(Wedge((0,0), 1, 0, 360, width=thickness, facecolor="#dce8f1", edgecolor="none"))
    ax.add_patch(Wedge((0,0), 1, 90-360*fraction, 90, width=thickness,
                       facecolor=color, edgecolor="none"))
    return ax


def confirmation(summary):
    rows = [
        dict(repository="Carleson", positive=17, roots=24, nonterminal=11, cross_family=10, pairs=65),
        dict(repository="FLT", positive=13, roots=24, nonterminal=7, cross_family=8, pairs=56),
        dict(repository="Sphere Packing", positive=16, roots=24, nonterminal=12, cross_family=12, pairs=65),
        dict(repository="Brownian Motion", positive=11, roots=24, nonterminal=6, cross_family=6, pairs=56),
    ]
    assert sum(r["positive"] for r in rows) == 57
    assert sum(r["nonterminal"] for r in rows) == sum(r["cross_family"] for r in rows) == 36
    mean = summary["macros"]["L0"]["text48"]["primary_repo_macro_mean"]
    ci = summary["macros"]["L0"]["text48"]["primary_repo_bootstrap_95ci"]
    assert mean == 57/96
    breadth = [8, 1, 16, 46]
    fig, a = sheet(106)
    text(a,2,103,"Four repositories",9,BLUE,"bold")
    text(a,2,98,"24 frozen roots each",8,GREY)
    for r,y in zip(rows,[85,64,43,22]):
        # Restrained spokes connect repositories to the pooled summary.
        a.plot([43,48.5],[y,55],color="#dce6ee",lw=.6,zorder=0)
        dial(a,37,y,6.5,r["positive"],24)
        text(a,2,y+5.8,r["repository"],8,INK,"bold")
        text(a,2,y+.8,f'N {r["nonterminal"]} · F {r["cross_family"]}',8,TEAL)
        text(a,2,y-4.0,f'{r["pairs"]} head pairs',8,PURPLE)
    text(a,60,80,"Frozen\nconfirmation",8.5,BLUE,"bold",ha="center")
    a.add_patch(Wedge((60,55),11.5,0,360,width=1.3,facecolor="#e2edf5",edgecolor="none"))
    a.add_patch(Wedge((60,55),11.5,90-360*mean,90,width=1.3,facecolor=BLUE,edgecolor="none"))
    text(a,60,59.8,"96/96",10,INK,"bold",ha="center",va="center")
    text(a,60,55.2,"evaluable",8,GREY,ha="center",va="center")
    text(a,60,50.3,"59.38%",10,BLUE,"bold",ha="center",va="center")
    text(a,60,39,"Macro frequency",8,BLUE,ha="center")
    text(a,60,34.5,"50.00–68.75%",8,GREY,ha="center")
    text(a,60,30,"95% interval",8,GREY,ha="center")
    # One point represents one observed head pair; orbit radius encodes breadth.
    shades = ["#b5c5d1", TEAL, "#5587b2", BLUE]
    for n, radius, color in zip(breadth, [9.2,12.2,15,18], shades):
        a.add_patch(Circle((98,55),radius,fill=False,edgecolor="#f0f4f7",lw=4))
        angles = [2*math.pi*j/n for j in range(n)]
        a.scatter([98+radius*math.cos(v) for v in angles], [55+radius*math.sin(v) for v in angles],
                  s=5, color=color, zorder=3)
    text(a,98,57.3,"71",11,INK,"bold",ha="center",va="center")
    text(a,98,52.7,"head pairs",8,GREY,ha="center",va="center")
    box(a,78,82,40,13,"#e9f4f0")
    text(a,98,92.8,"63/71 recurring",9,TEAL,"bold",ha="center")
    text(a,98,87.5,"in ≥2 repositories",8,TEAL,ha="center")
    text(a,98,29,"Repository breadth",8,GREY,ha="center")
    for j, (n,color) in enumerate(zip(breadth,shades)):
        x=82+(j%2)*20; y=21-(j//2)*6
        a.plot(x,y,"o",color=color,ms=2.8)
        text(a,x+2.5,y,f'{j+1}: {n}',8,GREY,va="center")
    a.plot([2,117],[10,10],color="#dce6ee",lw=.55)
    text(a,59.5,7.5,"N = nonterminal (36/96) · F = across tactic families (36/96)",8,GREY,ha="center")
    save(fig,2)
    return dict(repositories=rows,breadth_counts=breadth,macro=mean,interval=ci)


def external():
    source=PROJECT/"publication_release/release_v1.22.2/github/paper_v1.21/analysis/exp64_corrected_rows.jsonl"
    aggregate_path=source.with_name("exp64_correction.json")
    aggregate=json.loads(aggregate_path.read_text())
    rows=[json.loads(line) for line in source.read_text().splitlines()]
    groups=defaultdict(list)
    for row in rows: groups[row["slug"]].append(row)
    assert len(rows)==512 and len(groups)==32 and all(len(v)==16 for v in groups.values())
    assert sum(r["full"]["Y"] for r in rows)==aggregate["full"]["positives"]==355
    assert sum(r["diverse"]["Y"] for r in rows)==aggregate["diverse"]["positives"]==141
    data=[dict(repository=s,roots=len(rs),full=100*sum(r["full"]["Y"] for r in rs)/len(rs),
               diverse=100*sum(r["diverse"]["Y"] for r in rs)/len(rs)) for s,rs in groups.items()]
    data.sort(key=lambda r:(-r["full"],r["repository"].lower()))
    abbreviations={"bezier-bernstein-voronovskaja-lean":"bezier-bernstein", "Collatz-Binary-Topology":"Collatz-Binary",
        "IsoperimetricInequality":"Isoperimetric", "bastien-khormali-conjecture":"bastien-khormali",
        "collatz-conditional-cycles":"collatz-cycles", "paper-2026-verified-filter-lean":"verified-filter",
        "lean4-search-algorithms":"lean4-search", "erdos274-hs-abelian":"erdos274",
        "graffiti-pc-conjecture-141":"graffiti-141", "aint26-lean-solutions":"aint26",
        "IndependentTransversals":"IndependentTransv.", "discrete-game-theory":"discrete-game"}
    fig=plt.figure(figsize=(WIDTH,6.55))
    background=canvas(fig)
    soft_card(background,.718,.497,.271,.219,"#e8eff5","#f3f7fa")
    soft_card(background,.718,.280,.271,.219,"#e4efee","#f0f7f6")
    for x,y,text,color,marker in [(.340,.963,"Full panel",BLUE,"o"),(.340,.933,"After genealogy deduplication",TEAL,"D")]:
        fig.add_artist(plt.Line2D([x],[y],transform=fig.transFigure,marker=marker,color=color,
                                 linestyle="none",markersize=3.5))
        fig.text(x+.025,y,text,fontsize=8.5,va="center",color=color)
    ax=fig.add_axes([.340,.106,.347,.803])
    for y,r in enumerate(data):
        if y%2==0: ax.axhspan(y-.48,y+.48,color="#f4f7f9",zorder=0)
        ax.plot([r["diverse"],r["full"]],[y,y],color="#a9bdc9",lw=.65,zorder=1)
    ax.scatter([r["full"] for r in data],range(32),marker="o",s=11,color=BLUE,zorder=3)
    ax.scatter([r["diverse"] for r in data],range(32),marker="D",s=10,color=TEAL,zorder=2)
    ax.set(xlim=(-3,103),ylim=(31.7,-.7),xlabel="Positive roots (%)")
    ax.set_yticks(range(32),[abbreviations.get(r["repository"].split("/",1)[1],r["repository"].split("/",1)[1]) for r in data])
    ax.set_xticks([0,25,50,75,100]); ax.tick_params(axis="y",length=0,pad=4)
    ax.spines["left"].set_visible(False); ax.grid(axis="x",color="#dce5eb",lw=.55); ax.set_axisbelow(True)
    fig.text(.735,.882,"32 repository\nrepresentatives",fontsize=9,fontweight="bold",color=BLUE,va="top",linespacing=1.15)
    fig.text(.735,.808,"16 frozen roots\neach; all evaluable",fontsize=8.5,color=GREY,va="top",linespacing=1.15)
    for y,key,title,color in [(.696,"full","Full panel",BLUE),(.482,"diverse","After genealogy\ndeduplication",TEAL)]:
        obj=aggregate[key]
        fig.text(.735,y,title,fontsize=8.5,color=color,va="top",linespacing=1.12)
        fig.text(.735,y-.065,f'{100*obj["mean"]:.2f}%',fontsize=12,fontweight="bold",color=color,va="center")
        fig.text(.735,y-.109,"Macro frequency",fontsize=8.5,color=GREY,va="center")
        a=fig.add_axes([.735,y-.157,.228,.022]); a.set(xlim=(0,100),ylim=(0,1)); a.axis("off")
        a.plot([0,100],[.5,.5],color="#dce5eb",lw=1)
        a.plot([100*obj["ci"][0],100*obj["ci"][1]],[.5,.5],color=color,lw=2)
        a.plot(100*obj["mean"],.5,"o",color=color,ms=3)
        fig.text(.735,y-.178,f'{100*obj["ci"][0]:.2f}–{100*obj["ci"][1]:.2f}%',fontsize=8.5,color=GREY,va="center")
    fig.text(.735,.225,"355/512 full\n141/512 deduplicated",fontsize=8.5,va="top",linespacing=1.35)
    fig.text(.735,.167,"124 head pairs\n87 recur in ≥2 repos",fontsize=8.5,va="top",linespacing=1.35)
    fig.text(.735,.105,"95% descriptive\nresampling intervals",fontsize=8.5,color=GREY,va="top",linespacing=1.2)
    save(fig,3)
    return dict(repositories=data,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                aggregate_source_sha256=hashlib.sha256(aggregate_path.read_bytes()).hexdigest(),
                aggregate={k:{"mean":aggregate[k]["mean"],"ci":aggregate[k]["ci"]} for k in ["full","diverse"]})


def sensitivity(summary,repeat):
    views=[("L0","Full panel"),("L-no-question","No heads\nending in ?"),
        ("L-no-aesop","No aesop"),("L-no-aesop-question","No aesop?"),
        ("L-no-aesop-pair","No aesop +\naesop?"),
        ("L-no-direct-wrapper","No direct\nsuggestions/\ncontrol wrappers"),
        ("L-mechanism-diverse","After genealogy\ndeduplication")]
    values=[summary["macros"][key]["struct"] for key,_ in views]
    assert [round(v["primary_repo_macro_mean"]*96) for v in values]==[70,64,65,65,62,64,33]
    fig,c=sheet(112)
    text(c,2,109,"a",10,BLUE,"bold")
    text(c,7,108.6,"Candidate views",9,INK,"bold")
    text(c,7,103,"Structural endpoint",8,GREY)
    ax=fig.add_axes([.286,.214,.208,.634])
    for y,v in enumerate(values):
        mean=100*v["primary_repo_macro_mean"]; lo,hi=[100*x for x in v["primary_repo_bootstrap_95ci"]]
        color=TEAL if y==6 else BLUE
        ax.plot([lo,hi],[y,y],color=color,lw=1.1); ax.plot(mean,y,"o",color=color,ms=3)
        ax.text(1.04,y,f'{mean:.1f}',transform=ax.get_yaxis_transform(),fontsize=8,ha="left",va="center",color=color)
    ax.set(xlim=(15,100),ylim=(6.65,-.65),xlabel="Positive roots (%)")
    ax.set_xticks([20,60,100]); ax.set_yticks(range(7),[name for _,name in views])
    ax.tick_params(axis="y",length=0,pad=4,labelsize=8); ax.spines["left"].set_visible(False)
    ax.tick_params(axis="x",labelsize=8); ax.xaxis.label.set_size(8)
    ax.grid(axis="x",color="#e2e8ed",lw=.6); ax.set_axisbelow(True)
    text(c,72,109,"b",10,BLUE,"bold")
    text(c,77,108.6,"Endpoint comparison",9,INK,"bold")
    for x,title,count,rate,color,fill in [(72,"Textual","57/96","59.38%",BLUE,"#eaf1f8"),
                                       (97,"Structural","70/96","72.92%",TEAL,"#eaf4f3")]:
        box(c,x,76,21,23,fill)
        text(c,x+10.5,96,title,8,color,ha="center")
        text(c,x+10.5,89.5,count,10,INK,"bold",ha="center")
        text(c,x+10.5,82.7,rate,9,color,ha="center")
    confusion=summary["endpoint_confusion"]["text48_vs_struct"]["cross_head_candidate_pairs"]
    assert confusion["left_only"]==4 and confusion["right_only"]==72
    text(c,72,72,"Same full panel in both",8,GREY)
    text(c,72,65.5,"Matches only in structure: 72\nMatches only in text: 4",8)
    c.plot([72,118],[53,53],color="#dce5eb",lw=.6)
    text(c,72,49,"c",10,BLUE,"bold")
    text(c,77,48.6,"Repeat execution",9,INK,"bold")
    modes=[("M0_source","Historical"),("M1","Reverse"),("M2","Shuffle 1"),
           ("M3","Shuffle 2"),("M4","Shuffle 3"),("M5","Fresh")]
    c.plot([75,115],[38,38],color="#c7dedc",lw=1.2)
    for j,(mode,name) in enumerate(modes):
        assert repeat["root_level_complete_agreement"][mode]==96
        x=75+j*8
        c.add_patch(Circle((x,38),1.3,facecolor=TEAL,edgecolor="white",lw=.5))
        text(c,x,34.5,f'M{j}',8,GREY,ha="center")
    checks=repeat["agreement_counts_content_based_raw"]["order_and_process_modes_vs_M0"]
    assert all(v["status_equal"]==2208 and v["strict_endpoint_equal"]==514 for v in checks.values())
    text(c,72,27,"96/96 roots matched",8.5,TEAL,"bold")
    text(c,72,21.5,"2,208 statuses; 514 endpoints",8,TEAL)
    c.plot([2,118],[14,14],color="#dce5eb",lw=.6)
    text(c,2,11,"M0: historical · M1: reversed · M2–M4: shuffled · M5: fresh process",8,GREY)
    text(c,2,5.5,"96 reused roots; intervals describe resampling of the observed repositories.",8,GREY)
    save(fig,4)
    return dict(views=[dict(key=k,label=n,**v) for (k,n),v in zip(views,values)],
                pair_confusion=confusion,modes=modes,successful_endpoints=514,candidate_statuses=2208)
