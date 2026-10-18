"""Redraw manuscript Figures 2-4 in a conventional journal style.

Copyright 2026 Zhixuan Ma and Zhengwei Shen.
SPDX-License-Identifier: Apache-2.0

The numbers come only from the frozen figure inputs of 8 October 2026
(figure_source_data.json and external_source.csv, written by
figures_20261008/make_figures.py from the archived experiment summaries).
Their SHA-256 values are checked before plotting. No value is recomputed,
filtered, resampled or simulated; only the presentation changes.
Figure 1 is a schematic drawn separately in Fig1.tex (pdfLaTeX + TikZ).

Usage: python make_figures_journal.py [INPUT_DIR] [OUTPUT_DIR]
"""
from pathlib import Path
import csv
import hashlib
import json
import os
import sys

HERE = Path(__file__).resolve().parent
IN = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE
if not (IN / "figure_source_data.json").exists():
    IN = HERE.parent / "figures_20261008"   # repository layout
OUT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else HERE
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(OUT / ".mplcache"))

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LogNorm
import matplotlib.patheffects as pe
HALO = [pe.withStroke(linewidth=2.2, foreground="white")]

EXPECTED = {
    "figure_source_data.json": "c6f39596f948752965405edc0678603c0e6de7699ff8cbcd05da03d6a7b50d74",
    "external_source.csv": "50461bae1d8f78c75045216f751fd7a7b4f125e86b3a4a50f450e6e64ebb8142",
}
for name, digest in EXPECTED.items():
    actual = hashlib.sha256((IN / name).read_bytes()).hexdigest()
    if actual != digest:
        raise SystemExit(f"Input hash mismatch for {name}: {actual}")

SRC = json.loads((IN / "figure_source_data.json").read_text())
with (IN / "external_source.csv").open(newline="") as handle:
    EXT_CSV = list(csv.DictReader(handle))

MM = 1 / 25.4
WIDTH = 119 * MM
INK, INK2, MUTED = "#1a1a1a", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#5f5e5a"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"   # validated categorical slots 1-3
BLUE_LIGHT = "#cde2fb"

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Liberation Sans", "Helvetica", "DejaVu Sans"],
    "font.size": 8,
    "axes.labelsize": 8,
    "axes.titlesize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "axes.linewidth": 0.6,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": INK,
    "xtick.color": AXIS,
    "ytick.color": AXIS,
    "xtick.labelcolor": INK,
    "ytick.labelcolor": INK,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.major.size": 2.5,
    "ytick.major.size": 2.5,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "legend.handlelength": 1.2,
    "legend.handletextpad": 0.5,
    "legend.columnspacing": 1.2,
    "text.color": INK,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
    "savefig.dpi": 600,
})

PLOTTED = {}   # every plotted value, written to figure_values_journal.json


def halo_text(ax, x, y, s, zorder=4, **kw):
    """Text with a thin white halo; the visible glyphs stay real (searchable) text."""
    under = dict(kw, color="white")
    ax.text(x, y, s, zorder=zorder, path_effects=[pe.withStroke(linewidth=2.2, foreground="white")], **under)
    return ax.text(x, y, s, zorder=zorder + 0.1, **kw)


def panel_letter(fig, ax, letter, dx=-9.0, dy=1.5):
    """Bold lowercase panel letter placed dx, dy millimetres from the axes' top-left corner."""
    box = ax.get_position()
    w, h = fig.get_size_inches()
    fig.text(box.x0 + dx * MM / w, box.y1 + dy * MM / h, letter,
             fontsize=10, fontweight="bold", ha="left", va="bottom")


def axes_mm(fig, left, bottom, width, height):
    w, h = fig.get_size_inches()
    return fig.add_axes([left * MM / w, bottom * MM / h, width * MM / w, height * MM / h])


def save(fig, stem):
    fig.savefig(OUT / f"{stem}.pdf")
    fig.savefig(OUT / f"{stem}.svg")
    fig.savefig(OUT / f"{stem}.png", dpi=300)
    plt.close(fig)


# --------------------------------------------------------------------- Fig. 2
def figure2():
    conf = SRC["confirmation"]
    repos = conf["repositories"]
    fig = plt.figure(figsize=(WIDTH, 72 * MM))

    # (a) per-repository occurrence, nonterminal and cross-family witnesses
    ax = axes_mm(fig, 27, 11, 55, 45)
    series = [("positive", "Positive roots", BLUE),
              ("nonterminal", "Nonterminal witness", ORANGE),
              ("cross_family", "Witness across families", AQUA)]
    bar_h, gap = 0.22, 0.04
    lo, hi = conf["interval"]
    macro = conf["macro"]
    band = ax.axvspan(100 * lo, 100 * hi, color=BLUE_LIGHT, alpha=0.6, lw=0, zorder=0,
                      label=f"Interval {100 * lo:.2f}\u2013{100 * hi:.2f}%")
    line = ax.axvline(100 * macro, color=BLUE, lw=0.9, zorder=1, label=f"Macro mean {100 * macro:.2f}%")
    bars = []
    for i, r in enumerate(repos):
        for j, (key, label, color) in enumerate(series):
            y = i + (j - 1) * (bar_h + gap)
            value = 100 * r[key] / r["roots"]
            b = ax.barh(y, value, height=bar_h, color=color, lw=0, zorder=2, label=label if i == 0 else None)
            if i == 0:
                bars.append(b)
            halo_text(ax, value + 1.2, y, f'{r[key]}', va="center", ha="left", fontsize=8, color=INK2)
        ax.text(104, i, f'{r["pairs"]}', va="center", ha="left", fontsize=8, color=INK)
    ax.text(104, -0.55, "Head\npairs", va="bottom", ha="left", fontsize=8, color=INK2, linespacing=1.05)
    ax.set_xlim(0, 100)
    ax.set_ylim(len(repos) - 0.5, -0.55)
    ax.set_yticks(range(len(repos)), [r["repository"] for r in repos])
    ax.tick_params(axis="y", length=0, pad=3)
    ax.spines["left"].set_visible(False)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("Roots (% of 24 per repository)")
    ax.grid(axis="x", color=GRID, lw=0.5, zorder=0)
    ax.set_axisbelow(True)
    handles = bars + [line, band]
    labels = [h.get_label() for h in handles]
    w, h = fig.get_size_inches()
    fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(6 * MM / w, 1.0), ncol=2,
               handlelength=1.1, columnspacing=1.6, borderaxespad=0.4, fontsize=8,
               labelspacing=0.3)
    panel_letter(fig, ax, "a", dx=-26.5, dy=11.5)

    # (b) recurrence of head pairs across repositories
    bx = axes_mm(fig, 99, 11, 18, 45)
    counts = conf["breadth_counts"]
    x = [1, 2, 3, 4]
    bx.bar(x, counts, width=0.62, color=MUTED, lw=0, zorder=2)
    for xi, c in zip(x, counts):
        bx.text(xi, c + 0.8, str(c), ha="center", va="bottom", fontsize=8, color=INK2)
    bx.set_xticks(x)
    bx.set_xlim(0.4, 4.6)
    bx.set_ylim(0, 50)
    bx.set_yticks([0, 10, 20, 30, 40, 50])
    bx.set_xlabel("Repositories")
    bx.set_ylabel("Distinct head pairs", labelpad=2)
    bx.grid(axis="y", color=GRID, lw=0.5, zorder=0)
    bx.set_axisbelow(True)
    total, recurring = sum(counts), sum(counts[1:])
    bx.text(0.04, 0.97, f"{recurring} of {total}\nin \u22652", transform=bx.transAxes,
            ha="left", va="top", fontsize=8, color=INK2, linespacing=1.1)
    panel_letter(fig, bx, "b", dx=-10.5, dy=11.5)

    save(fig, "Fig2")
    PLOTTED["Fig2"] = {
        "repositories": [{k: r[k] for k in ("repository", "positive", "nonterminal", "cross_family", "pairs", "roots")} for r in repos],
        "macro": macro, "interval": [lo, hi], "breadth_counts": counts,
        "total_pairs": total, "recurring_pairs": recurring,
    }


# --------------------------------------------------------------------- Fig. 3
ABBREV = {"bezier-bernstein-voronovskaja-lean": "bezier-bernstein", "Collatz-Binary-Topology": "Collatz-Binary",
          "IsoperimetricInequality": "Isoperimetric", "bastien-khormali-conjecture": "bastien-khormali",
          "collatz-conditional-cycles": "collatz-cycles", "paper-2026-verified-filter-lean": "verified-filter",
          "lean4-search-algorithms": "lean4-search", "erdos274-hs-abelian": "erdos274",
          "graffiti-pc-conjecture-141": "graffiti-141", "aint26-lean-solutions": "aint26",
          "IndependentTransversals": "IndependentTransv.", "discrete-game-theory": "discrete-game"}


def figure3():
    ext = SRC["external"]
    repos = ext["repositories"]
    assert [r["repository"] for r in repos] == [r["repository"] for r in EXT_CSV]
    for r, c in zip(repos, EXT_CSV):
        assert float(c["full"]) == r["full"] and float(c["diverse"]) == r["diverse"] and int(c["roots"]) == r["roots"]
    n = len(repos)
    fig = plt.figure(figsize=(WIDTH, 158 * MM))
    ax = axes_mm(fig, 33, 30, 82, 118)
    names = [ABBREV.get(r["repository"].split("/", 1)[1], r["repository"].split("/", 1)[1]) for r in repos]
    for y, r in enumerate(repos):
        ax.plot([r["diverse"], r["full"]], [y, y], color="#b4b2aa", lw=0.9, zorder=1, solid_capstyle="butt")
    ax.scatter([r["full"] for r in repos], range(n), s=44, marker="o", color=BLUE,
               edgecolor="white", linewidth=0.6, zorder=3, label="Full panel")
    ax.scatter([r["diverse"] for r in repos], range(n), s=15, marker="D", color=ORANGE,
               edgecolor="white", linewidth=0.6, zorder=4, label="After genealogy deduplication")
    ax.set_ylim(n - 0.4, -0.6)
    ax.set_yticks(range(n), names)
    ax.tick_params(axis="y", length=0, pad=3, labelsize=8)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(-2, 102)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.tick_params(axis="x", labelbottom=False)
    ax.grid(axis="x", color=GRID, lw=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.02, 1.005), ncol=2, borderaxespad=0.2)
    panel_letter(fig, ax, "a", dx=-32, dy=4.5)

    bx = axes_mm(fig, 33, 11, 82, 14)
    agg = ext["aggregate"]
    rows = [("full", "Full panel", BLUE, "o"), ("diverse", "After deduplication", ORANGE, "D")]
    for y, (key, label, color, marker) in enumerate(rows):
        m, (lo, hi) = 100 * agg[key]["mean"], [100 * v for v in agg[key]["ci"]]
        bx.plot([lo, hi], [y, y], color=color, lw=1.2, solid_capstyle="butt", zorder=2)
        for v in (lo, hi):
            bx.plot([v, v], [y - 0.18, y + 0.18], color=color, lw=1.0, zorder=2)
        bx.scatter([m], [y], s=22, marker=marker, color=color, edgecolor="white", linewidth=0.6, zorder=3)
        right = hi < 60
        halo_text(bx, hi + 2 if right else lo - 2, y, f"{m:.2f}% [{lo:.2f}, {hi:.2f}]", va="center",
                  ha="left" if right else "right", fontsize=8, color=INK2)
    bx.set_ylim(1.6, -0.6)
    bx.set_yticks([0, 1], [r[1] for r in rows])
    bx.tick_params(axis="y", length=0, pad=3, labelsize=8)
    bx.spines["left"].set_visible(False)
    bx.set_xlim(-2, 102)
    bx.set_xticks([0, 25, 50, 75, 100])
    bx.set_xlabel("Positive roots (%)")
    bx.grid(axis="x", color=GRID, lw=0.5, zorder=0)
    bx.set_axisbelow(True)
    panel_letter(fig, bx, "b", dx=-32, dy=1.0)

    save(fig, "Fig3")
    PLOTTED["Fig3"] = {"repositories": [{"repository": r["repository"], "label": nm, "full": r["full"],
                                          "diverse": r["diverse"], "roots": r["roots"]} for r, nm in zip(repos, names)],
                       "aggregate": agg}


# --------------------------------------------------------------------- Fig. 4
VIEW_LABELS = {
    "L0": "Full panel",
    "L-no-question": "No heads ending in ?",
    "L-no-aesop": "No aesop",
    "L-no-aesop-question": "No aesop?",
    "L-no-aesop-pair": "No aesop, aesop?",
    "L-no-direct-wrapper": "No direct suggestions\nor control wrappers",
    "L-mechanism-diverse": "After genealogy\ndeduplication",
}


def figure4():
    sens = SRC["sensitivity"]
    views = sens["views"]
    conf = SRC["confirmation"]
    fig = plt.figure(figsize=(WIDTH, 106 * MM))

    # (a) seven candidate views under the structural endpoint
    ax = axes_mm(fig, 38, 56, 64, 44)
    for y, v in enumerate(views):
        m = 100 * v["primary_repo_macro_mean"]
        lo, hi = [100 * c for c in v["primary_repo_bootstrap_95ci"]]
        ax.plot([lo, hi], [y, y], color=BLUE, lw=1.1, solid_capstyle="butt", zorder=2)
        for e in (lo, hi):
            ax.plot([e, e], [y - 0.15, y + 0.15], color=BLUE, lw=0.9, zorder=2)
        reps = [100 * r for r in v["repository_primary_rates"]]
        ax.scatter(reps, [y + 0.30] * len(reps), s=7, marker="o", facecolor="none",
                   edgecolor=MUTED, linewidth=0.6, zorder=1, label="Repository rate" if y == 0 else None)
        ax.scatter([m], [y], s=22, color=BLUE, edgecolor="white", linewidth=0.6, zorder=3,
                   label="Macro mean, 95% interval" if y == 0 else None)
        ax.text(104, y, f"{m:.1f}", va="center", ha="left", fontsize=8)
    ax.text(104, -0.75, "Mean", va="bottom", ha="left", fontsize=8, color=INK2)
    ax.set_ylim(len(views) - 0.45, -0.6)
    ax.set_yticks(range(len(views)), [VIEW_LABELS[v["key"]] for v in views])
    ax.tick_params(axis="y", length=0, pad=3, labelsize=8)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("Positive roots, structural endpoint (%)")
    ax.grid(axis="x", color=GRID, lw=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.52, 1.0), ncol=2, borderaxespad=0.2, fontsize=8)
    panel_letter(fig, ax, "a", dx=-37, dy=1.5)

    # (b) candidate-pair classification, textual versus structural endpoint
    pc = sens["pair_confusion"]
    matrix = [[pc["both_positive"], pc["left_only"]], [pc["right_only"], pc["both_negative"]]]
    total = sum(sum(r) for r in matrix)
    bx = axes_mm(fig, 24, 7, 25, 25)
    cmap = LinearSegmentedColormap.from_list("blue", ["#eef4fc", "#9ec5f4", "#2a78d6", "#184f95"])
    bx.imshow(matrix, cmap=cmap, norm=LogNorm(vmin=1, vmax=total), aspect="equal")
    for i in range(2):
        for j in range(2):
            v = matrix[i][j]
            bx.text(j, i, f"{v:,}", ha="center", va="center", fontsize=8,
                    color="white" if v > 300 else INK)
    bx.set_xticks([0, 1], ["Match", "No match"])
    bx.set_yticks([0, 1], ["Match", "No match"])
    bx.xaxis.set_label_position("top")
    bx.xaxis.tick_top()
    bx.set_xlabel("Structural endpoint", labelpad=3)
    bx.set_ylabel("Textual endpoint", labelpad=2)
    bx.tick_params(length=0, pad=2, labelsize=8)
    for s in bx.spines.values():
        s.set_visible(False)
    bx.text(0.5, -0.08, f"{total:,} candidate pairs", transform=bx.transAxes,
            ha="center", va="top", fontsize=8, color=INK2)
    fig.text(0.0, 42.5 * MM / fig.get_size_inches()[1], "b", fontsize=10, fontweight="bold", ha="left", va="bottom")
    struct_pos = round(sum(24 * r for r in views[0]["repository_primary_rates"]))
    text_pos = sum(r["positive"] for r in conf["repositories"])

    # (c) repeat execution: agreement with the archived rows in six modes
    cx = axes_mm(fig, 77, 13, 31, 15)
    modes = sens["modes"]
    checks = [("Roots", 96), ("Statuses", sens["candidate_statuses"]),
              ("Endpoints", sens["successful_endpoints"])]
    for i in range(len(checks)):
        cx.scatter(range(len(modes)), [i] * len(modes), s=30, marker="s", color=AQUA,
                   edgecolor="white", linewidth=0.6, zorder=2)
        cx.text(len(modes) - 0.2, i, f"{checks[i][1]:,}", va="center", ha="left", fontsize=8, color=INK2)
    cx.text(len(modes) - 0.2, -0.85, "n", va="bottom", ha="left", fontsize=8, color=INK2, style="italic")
    cx.set_xlim(-0.6, len(modes) - 0.4)
    cx.set_ylim(len(checks) - 0.5, -0.5)
    cx.set_xticks(range(len(modes)), ["M0", "M1", "M2", "M3", "M4", "M5"])
    cx.set_yticks(range(len(checks)), [name for name, _ in checks])
    cx.tick_params(length=0, pad=2, labelsize=8)
    cx.tick_params(axis="x", labelsize=8)
    for s in cx.spines.values():
        s.set_visible(False)
    cx.xaxis.tick_top()
    cx.text(0.5, -0.12, "Each square: all n comparisons\nmatched the archived rows",
            transform=cx.transAxes, ha="center", va="top", fontsize=8, color=INK2, linespacing=1.2)
    fig.text(58 * MM / WIDTH, 42.5 * MM / fig.get_size_inches()[1], "c", fontsize=10, fontweight="bold", ha="left", va="bottom")

    save(fig, "Fig4")
    PLOTTED["Fig4"] = {
        "views": [{"key": v["key"], "mean": v["primary_repo_macro_mean"], "ci": v["primary_repo_bootstrap_95ci"],
                   "repository_rates": v["repository_primary_rates"]} for v in views],
        "pair_matrix": {"text_and_struct": matrix[0][0], "text_only": matrix[0][1],
                        "struct_only": matrix[1][0], "neither": matrix[1][1], "total": total},
        "positive_roots_for_caption": {"textual": text_pos, "textual_macro": conf["macro"],
                                       "structural": struct_pos,
                                       "structural_macro": views[0]["primary_repo_macro_mean"]},
        "modes": modes, "checks": checks,
    }


if __name__ == "__main__":
    figure2()
    figure3()
    figure4()
    PLOTTED["inputs_sha256"] = EXPECTED
    (OUT / "figure_values_journal.json").write_text(json.dumps(PLOTTED, indent=2) + "\n")
    print("Figures 2-4 written to", OUT)
