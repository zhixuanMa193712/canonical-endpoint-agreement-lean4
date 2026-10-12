"""Correct the continuation accounting diagram using the sealed selection ledger."""
import json
import zipfile
from matplotlib.patches import FancyArrowPatch
from reference_style import sheet, box, text, BLUE, TEAL, GREY, INK
from make_figures import BASE, PROJECT

with zipfile.ZipFile(PROJECT / "experiment52_continuation_probe_fix4_results.zip") as z:
    selection = json.loads(z.read("artifacts/exp52/selection/summary.json"))
    analysis = json.loads(z.read("artifacts/exp52/analysis/summary.json"))
assert selection["root_status_counts"] == {"no_eligible_witness": 536, "witness_selected": 40}
assert selection["within_root_control_pairs"] == 36
assert analysis["informative_paired_control_deltas"] == 33

fig, ax = sheet(104)
text(ax,2,101,"a  Continuation sample",9,BLUE,"bold")
box(ax,36,79,47,13,"#eaf1f8")
text(ax,59.5,89,"576 source roots",9,BLUE,"bold",ha="center")
text(ax,59.5,83.5,"12 repositories",8,GREY,ha="center")
for x in (28,92):
    ax.add_patch(FancyArrowPatch((59.5,79),(x,73),arrowstyle="-|>",mutation_scale=7,lw=.7,color=GREY))
box(ax,2,37,54,35,"#e6f2ef")
text(ax,29,69,"40 selected witness roots",9,TEAL,"bold",ha="center")
text(ax,29,63,"7 repositories",8,GREY,ha="center")
ax.plot([6,52],[58,58],color="#c4dbd5",lw=.6)
text(ax,6,55,"Within these 40 roots:",8,INK,"bold")
text(ax,6,49.5,"36 have paired controls\n33 yield informative paired deltas",8)
box(ax,65,54,52,18,"#f3f5f7")
text(ax,91,68,"536 roots not selected",9,GREY,"bold",ha="center")
text(ax,91,62,"No eligible witness",8,GREY,ha="center")
text(ax,66,48,"Controls are not additional roots.",8,GREY)
text(ax,2,31,"604 primary paired responses: 318 witness + 286 control",8,GREY)
ax.plot([2,117],[24,24],color="#dce5eb",lw=.6)
text(ax,2,20,"b  Second machine: exact reproduction of a frozen subset",9,BLUE,"bold")
for x,top,bottom in [(18,"4","repositories"),(48,"16","roots"),(78,"368","attempts"),(106,"0","mismatches")]:
    text(ax,x,13,top,10,TEAL,"bold",ha="center")
    text(ax,x,6.5,bottom,8,GREY,ha="center")
fig.savefig(BASE/"supplement/FigS1_continuation_second_machine.png",dpi=600)
fig.savefig(BASE/"supplement/FigS1_continuation_second_machine.pdf")
fig.savefig(BASE/"supplement/FigS1_continuation_second_machine.svg")
