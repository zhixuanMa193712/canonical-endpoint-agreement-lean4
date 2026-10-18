# Post hoc offline analyses (October 2026)

These scripts produce the post hoc analyses that were added to the manuscript and Online Resource 1 between 16 and 17 October 2026. None of them runs Lean. They read either the archived execution rows, the archived receipts and diagnostics, or the public source files at the pinned commits. Online Resource 1, Section S1, lists where each result is reported.

The scripts were written separately from the execution pipeline. They use their own lexical head function and reproduce the corrected counts of the external studies.

## Inputs

- The eleven experiment archives of Zenodo version 1.22.3. The scripts read Exp48, Exp49, Exp62, Exp63 and Exp64.
- `data/`: compact rows written by `export_compact_rows.py` from Exp49, Exp64 and Exp62. They are included so that the analyses can be rerun without the archives.
- The public GitHub repositories of the case series and of the strict frame, at the pinned commits. `fetch_sources.py` fetches the 271 sampled source files, together with the Lake manifests, into `src/` and checks every file against its archived SHA-256 value.

## Order

| Step | Command | Output |
|---|---|---|
| 1 | `python3 revision_r1_offline_reanalysis.py --root <folder with the archives> --out revision_r1_offline_reanalysis.json` | Candidate outcomes, decomposition, multiplicity, discordant pairs, multistep qualification flow and depth table |
| 2 | `python3 export_compact_rows.py --root <folder with the archives> --out data` | `data/*.jsonl` (already included) |
| 3 | `python3 fetch_sources.py .` | `src/` (not included; third-party sources) |
| 4 | `python3 classify_roots.py .` | `root_positions.json`: root position and declaration attributes, including `(attr := ...)` |
| 5 | `python3 scan_options.py .` | `options_in_scope.json`: `set_option` commands in scope at each root |
| 6 | `python3 scan_dependencies.py .` | `strict_dependencies.json`: Mathlib and Aesop dependence of the strict-frame representatives |
| 7 | `python3 round2_analysis.py .` | `round2_analysis.json`: four-way outcomes, implementation grouping, conservative recount, visibility requirement, root-position and parse strata, size controls, frame-conditional intervals, search-log replay |
| 8 | `python3 round3_analysis.py .` | `round3_analysis.json`: alternative groupings, co-activity, Mathlib strata, strict-frame views, representative-only intervals, collision types, attribution of duplicate subtrees, replay without duplicate programs |
| 9 | `python3 exp63_attrition.py <Exp63 archive>` | `exp63_attrition.json`: recruitment attrition and covariates |
| 10 | `python3 ellipsis_scan.py <folder with the archives>` | `ellipsis_scan.json`: abbreviated proof subterms in stored textual records |
| 11 | `python3 failure_messages.py <Exp64 archive>` | `failure_messages.json`: stored failure messages of the strict frame, by program |

## Notes

- Steps 7 and 8 are deterministic and give byte-identical JSON under different values of `PYTHONHASHSEED`.
- The random draws use fixed seeds:
  - size controls: seeds 18 and 5;
  - interval resampling: seed 20260918, with 20,000 replicates.
- The replays of the multistep search assume deterministic execution and a state key that determines all outcomes at a node. They therefore measure cost only and cannot detect losses caused by merging states.
