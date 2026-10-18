# Changelog

## 1.22.5 — 2026-10-17

Synchronizes the supplementary documentation and the figures with the manuscript
and Online Resource 1 as revised on 16 and 17 October 2026. Not separately
archived in Zenodo.

- Add `review_analyses_20261017/`: eleven scripts, compact rows (`data/`) and
  outputs of the post hoc offline analyses added to the manuscript after three
  rounds of blind review. These cover root position, four-way candidate
  outcomes, implementation and alternative groupings, co-activity, the
  conservative recount, Mathlib and parse strata, size controls, intervals,
  printer elisions, failure messages, recruitment attrition, and replays of the
  multistep search logs. No Lean execution; see its README.
- `docs/supplement/`: all Markdown sources updated to Online Resource 1 as revised
  on 17 October 2026 (the four-repository study is now called a case series;
  execution context corrected; post hoc results in S1-S9 and S18-S20).

- S19.2 (new): post hoc decomposition of the multistep invocation savings by
  solve status (58 roots solved by both policies: 5,539 vs 4,536 invocations,
  18.11% fewer; five roots solved by neither, both at the 768-invocation budget;
  one root solved only by endpoint selection, 204 of the 1,207 saved invocations)
  and the number of searches that reached the invocation budget under each policy.
- S20: one sentence listing the most frequent head pairs in the strict external
  frame, computed from `paper_v1.21/analysis/exp64_corrected_rows.jsonl`.
- Add `figures_20261016/`: Figures 1-4 redrawn in a conventional plotting style
  (Figure 1 in TikZ, Figures 2-4 with `make_figures_journal.py`). The script
  checks the SHA-256 of the frozen inputs `figure_source_data.json` and
  `external_source.csv` (identical to `figures_20261008/`), changes no value,
  and records every plotted value in `figure_values_journal.json`.
  `Fig1.tex` and `Fig1.pdf` include the one wording change made to Figure 1
  during the review (stage 2: the endpoint of the replayed authored tactic must
  equal kappa(s_q^+)), as in the manuscript revised on 17 October 2026.
- `docs/supplement/figure_plan.md`: one sentence on the redrawn figures.
- SOFTWARE_FILES.json and SOFTWARE_LICENSE_SCOPE.md list the two new figure
  sources. Regenerate FILES.json and SHA256SUMS.txt. No data, numerical figure
  input or frozen implementation changed.

## 1.22.4 — 2026-10-16

Documentation synchronization with the manuscript and Online Resource 1 editorial
revision of 16 October 2026. This revision is not separately archived in Zenodo.

- Cite Zenodo version 1.22.3 (https://doi.org/10.5281/zenodo.23311105), published
  12 October 2026, in README.md, RELEASE_STATUS.md, CITATION.cff and
  CITATION_DATASET.txt. CITATION.cff now lists the version and concept DOIs as
  identifiers and gives the dataset as the preferred citation.
- Replace six files in `docs/supplement/` with the current supplementary sources:
  corresponding-author address; version 1.22.3 access and reproduction steps;
  the Exp50 schema-label history (706 container-hash differences) in S10; the
  prespecified precision criterion and `inconclusive` decision label of the
  initial external frame in S11; the breadth-first multistep search description;
  and the previously blank eighth cell of the SEPIA/ML4PG/proof mining/TacMiner
  literature row.
- Add `paper_v1.21/CORRECTION_NOTE.md`, an English summary of the v1.21
  lexical-label correction. The Chinese notes `paper_v1.21/REVISION_NOTES.md` and
  `docs/v1.22_changes.md` are kept unchanged as historical internal records.
- `reproduce_correction.py`: an output that differs from the bundled file only in
  the recorded `numpy_version` field now passes. The receipt records the NumPy
  version used and whether each output was byte-identical.
- Regenerate FILES.json, SHA256SUMS.txt and SOFTWARE_FILES.json.
- No change to frozen experiment implementations, correction outputs, figures,
  sample sizes or numerical conclusions.

## 1.22.3 — 2026-10-11

- Restore `third_party/source/LegendreQF_original_source.zip`, already required by
  the 1.22.2 manifest and included in Zenodo, but omitted from Git tracking by the
  ZIP ignore rule. Add a single-path exception. Source bytes are unchanged.
- Synchronize supplementary Markdown and Figure S1 with the 8 October English
  submission materials. S1 partitions 576 roots into 40 selected and 536 without
  an eligible witness. The 36 paired controls are a subset of the 40, not another
  disjoint group. This corrects the earlier diagram's 40/36/500 depiction.
- Include all four current figures and unchanged plotting sources/data. Figure 3
  is external replication; Figure 4 is sensitivity/repeat execution.
- Add a portable figure wrapper that checks reconstructed numerical figure inputs.
- Update publication status and regenerate integrity/software-file manifests.
- No changes to frozen experiment implementations, original experiment archives,
  corrected root-level outputs, sample sizes, or numerical conclusions.

The literature-comparison row for SEPIA/ML4PG/proof mining/TacMiner is preserved
from the approved supplement: seven cells under eight headings. This known
editorial issue is not silently filled by this synchronization.

## 1.22.2 — 2026-09-21

Original-software licensing and third-party attribution supplement. The published
Zenodo dataset retains this version.
