# Manuscript figures — journal-style redraw, 16 October 2026

`Fig1.pdf`–`Fig4.pdf` are the figures of the 16 October 2026 manuscript. They
replace the 8 October drawings (still in `../figures_20261008/`) in presentation
only: every plotted number is unchanged.

`Fig1.tex` and `Fig1.pdf` carry one later wording change, made during the review
of 16–17 October 2026 and used in the revised manuscript of 17 October: the
replay box of stage 2 now reads "Replay t_q^auth; its endpoint must equal
kappa(s_q^+)" instead of "Replay t_q^auth and require (M^+, G^+) = P_q^+".
Figures 2–4 are unchanged.

| File | Content |
|---|---|
| `Fig1.tex` | Figure 1, a schematic of the measurement; pdfLaTeX + TikZ, Helvetica text. No execution data. |
| `make_figures_journal.py` | Figures 2–4, Python + matplotlib (Liberation Sans/Arial, embedded TrueType). |
| `figure_source_data.json`, `external_source.csv` | The frozen numerical inputs of 8 October 2026, byte-identical to `figures_20261008/` (written there by `make_figures.py` from the Exp49/Exp50 archives and the corrected Exp64 rows). |
| `figure_values_journal.json` | Every value plotted in Figures 2–4, written by the script for checking. |
| `Fig2.svg`–`Fig4.svg` | Editable vector copies. |

## Rebuild

```bash
python make_figures_journal.py          # Figures 2-4; checks the SHA-256 of both inputs first
pdflatex Fig1.tex                       # Figure 1
```

The script refuses to run if either input differs from the frozen file
(`figure_source_data.json` SHA-256 `c6f39596…a7b50d74`, `external_source.csv`
SHA-256 `50461bae…b8142`). It reads, but never recomputes, filters or resamples,
the archived summaries. Python 3.12 and matplotlib 3.11.2 were used.

## What changed in the drawings

- Figure 1: four stages as plain boxes, plus a schematic of one root (panel b)
  showing how successful branches are grouped by endpoint and when a pair is a witness.
- Figure 2: rings and the "orbit" replaced by grouped bars (positive, nonterminal,
  cross-family roots per repository, with the macro mean and its interval) and a
  bar chart of head pairs by repository breadth.
- Figure 3: the same dumbbell layout on a conventional axis; the macro means and
  intervals become panel b on the same scale.
- Figure 4: panel b shows the full 2×2 classification of the 24,288 candidate pairs
  (590 / 4 / 72 / 23,622) instead of summary cards; panel c shows the six repeat
  modes against the three checked quantities (96 roots, 2,208 statuses, 514
  successful endpoints). Panel a adds the four repository rates already present in
  the inputs.

Colours are the first three slots of a palette checked for colour-vision
deficiency (blue `#2a78d6`, orange `#eb6834`, aqua `#1baf7a`); every series also
has its own marker shape or position, and the values are in the tables.
