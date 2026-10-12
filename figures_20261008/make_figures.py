"""Redraw four manuscript figures from unchanged archived summaries.

119-mm width, Python/matplotlib, all 32 external repositories retained.
No new Lean execution, bootstrap, statistical test, or simulated data.
"""
from pathlib import Path
from collections import defaultdict
import csv
import hashlib
import json
import os
import zipfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".mplcache"))
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

BASE = Path(__file__).resolve().parents[1]
PROJECT = BASE.parent
OUT = Path(__file__).resolve().parent
LATEX = BASE / "latex"
WIDTH_MM = 119
WIDTH = WIDTH_MM / 25.4
BLUE = "#245c89"
TEAL = "#29776d"
GREY = "#697681"
INK = "#20303b"
PURPLE = "#6c548e"
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 9,
    "axes.labelsize": 9,
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
    "ps.fonttype": 42,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": .6,
    "legend.frameon": False,
    "text.color": INK,
})


def archive_json(filename, member):
    path = PROJECT / filename
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read(member)), {
            "archive": filename, "member": member,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }


def save(fig, number):
    # Fixed canvas: the PDF's physical size matches its manuscript inclusion.
    fig.savefig(LATEX / f"Fig{number}.pdf")
    fig.savefig(OUT / f"Fig{number}.svg")
    fig.savefig(OUT / f"Fig{number}.eps")
    fig.savefig(OUT / f"Fig{number}.png", dpi=300)
    fig.savefig(OUT / f"Fig{number}.tiff", dpi=600)
    plt.close(fig)


def label(fig, letter, y):
    fig.text(.015, y, letter, fontsize=11, fontweight="bold", va="top")


def panel_header(fig, letter, text, y, color=BLUE):
    fig.text(.025, y, letter, fontsize=10.5, fontweight="bold", va="top", color=color)
    fig.text(.080, y-.003, text, fontsize=9.2, fontweight="bold", va="top")


def soft_card(ax, x, y, w, h, color=BLUE, fill="#f2f6fa", radius=.010):
    patch = FancyBboxPatch((x,y), w,h, boxstyle=f"round,pad=0.004,rounding_size={radius}",
                          facecolor=fill,edgecolor=color,linewidth=.65)
    ax.add_patch(patch)
    return patch


def arrow(ax, a, b, color=GREY):
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle="-|>",mutation_scale=8,
                                color=color,linewidth=.8))




if __name__=="__main__":
    # User-supplied v1.20 figure reference: presentation only, current data.
    from reference_style import pipeline, confirmation, external, sensitivity
    OUT.mkdir(exist_ok=True)
    s,source49=archive_json("experiment49_candidate_endpoint_robustness_results.zip","artifacts/analysis/summary.json")
    r,source50=archive_json("experiment50_independent_reexecution_fix1_results.zip","artifacts/analysis_fix1/summary.json")
    pipeline()
    data={"width_mm":WIDTH_MM,"archive_sources":[source49,source50],
          "confirmation":confirmation(s),"external":external(),"sensitivity":sensitivity(s,r),
          "new_lean_executions":0,"data_exclusions":0}
    (OUT/"figure_source_data.json").write_text(json.dumps(data,indent=2)+"\n")
    with (OUT/"external_source.csv").open("w",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=["repository","roots","full","diverse"])
        writer.writeheader();writer.writerows(data["external"]["repositories"])
    print(json.dumps({"figures":4,"width_mm":WIDTH_MM,"external_repositories":32,
                      "external_roots":512,"new_lean_executions":0},indent=2))
