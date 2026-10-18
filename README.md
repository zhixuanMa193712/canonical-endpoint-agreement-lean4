# Measuring State-Conditioned Canonical-Endpoint Agreement in Lean 4

Source code, correction layer and documentation for the manuscript
"Measuring State-Conditioned Canonical-Endpoint Agreement in Lean 4" by
Zhixuan Ma and Zhengwei Shen.

Repository revision **1.22.5** (17 October 2026) synchronizes the documentation
with the manuscript and Online Resource 1 as revised on 17 October 2026.
Frozen experiment implementations and corrected analysis outputs are unchanged
from 1.22.3. Revision 1.22.4 relaxed one comparison in `reproduce_correction.py`;
revision 1.22.5 adds `figures_20261016/`, the manuscript figures redrawn in a
conventional plotting style from the same numerical inputs, and
`review_analyses_20261017/`, the scripts, compact rows and outputs of the post hoc
offline analyses reported in the revised manuscript. See CHANGELOG.md.

## Archived release

Evidence and the matching code package are archived in Zenodo, **version 1.22.3**:
https://doi.org/10.5281/zenodo.23311105 (concept DOI for all versions:
https://doi.org/10.5281/zenodo.22110050). The deposit contains two packages:

- `zenodo_upload_v1.22.2_licensed.zip`: the eleven original experiment archives,
  the correction layer, licence and attribution records, and the earlier source
  snapshot, unchanged since version 1.22.2;
- `GitHub_release_v1.22.3_20261011.zip`: the code package, identical to tag
  `v1.22.3` of this repository (commit `152c608`).

Cite the Zenodo version DOI for the data and the exact tag or Git commit for code.
Revisions 1.22.4 and 1.22.5 are documentation-only and are not separately archived.

## Results and correction layer

Original execution archives are not rewritten. The additional `paper_v1.21`
correction layer is required for the final external-study values: 355/512
(69.34%) full-panel roots and 141/512 (27.54%) genealogy-deduplicated roots in
the 32-repository frame. Original archived summaries contain the old
lexical-head labels (277/512 under the full panel); reproducing their audit alone
does not validate the corrected numbers. See
[`paper_v1.21/CORRECTION_NOTE.md`](paper_v1.21/CORRECTION_NOTE.md). The multistep
comparison supplies the authored steps to every policy on roots with
known proofs; it does not evaluate autonomous tactic generation. The post hoc
analyses in `review_analyses_20261017/` (see its README) execute no Lean code.

## Layout

- `paper_v1.21/`: exact correction script, corrected root rows, summaries, figure
  source, and an English correction note. `REVISION_NOTES.md` there and
  `docs/v1.22_changes.md` are historical internal notes in Chinese, kept unchanged
  for provenance.
- `source_packages/`: original-name execution modules, including final Exp62 fix1 and Exp63/64.
- `historical_code/`: earlier execution/analysis modules retained for provenance.
- `portable_audit/`: older path-portability layer; its audit is not the corrected analysis.
- `docs/supplement/`: Markdown sources of Online Resource 1 (study map, variables,
  claims, manifests and reproduction order), synchronized with the 16 October 2026 revision.
- `docs/`: licence references and a 52-candidate provenance inventory.
- `reproduce_correction.py`: temporary-directory reproduction of final corrections.
- `figures_20261016/`: current manuscript figures (redrawn 16 October 2026), their
  scripts and a record of every plotted value; inputs identical to `figures_20261008/`.
- `figures_20261008/`: the 8 October figure assets, plotting sources and numerical inputs.
- `reproduce_figures.py`: portable wrapper for the four figures and Figure S1.

## Quick offline reproduction

Use Python 3.11+ and NumPy 2.3.5 (the correction environment).
Install `requirements-analysis.txt` in a separate environment, then run:

```bash
python3 reproduce_correction.py --artifacts /absolute/path/to/zenodo/artifacts
```

`zenodo/artifacts/` is obtained by extracting `zenodo_upload_v1.22.2_licensed.zip`
from the Zenodo record above. The script launches no Lean processes and downloads
no repositories. It checks the three input archive hashes, executes the unchanged
correction script in a new temporary workspace, compares five JSON/JSONL outputs
with the bundled final outputs, and writes a receipt. Outputs must be
byte-identical, except that the recorded `numpy_version` field may differ when a
NumPy version other than 2.3.5 is used; the receipt records which comparison
applied. Input archives and bundled results are not modified.

The eleven archive checksums are independently listed in the dataset manifest.
The historical `paper_v1.21/figure4.py` is not the current manuscript figure pipeline.
For current figures, see figures_20261016/README.md; `reproduce_figures.py` rebuilds
the numerical inputs and the 8 October drawings (figures_20261008/README.md). The
order is method, confirmation, external replication, and sensitivity/repeat execution.

## Optional full execution

Historical source uses original sibling-directory names. Stage the contents of
`source_packages/` in a separate workspace and follow the specific final package
README. Set MZX_ROOT there, not to this GitHub repository. Do not execute every
historical driver or overwrite frozen outputs. Lean/toolchains, benchmark data,
and repository dependencies must be acquired separately at their pinned commits.
The lightweight analysis requirements are not a full Lean execution environment.
Full execution has not been rerun for this packaging task.

## Licence and citation

See `LICENSE_STATUS.md`. No blanket third-party relicensing is intended.
Author metadata, the archived DOIs and the preferred citation are in `CITATION.cff`;
the dataset citation is also in `CITATION_DATASET.txt`.
Technical archive labels are provenance identifiers, not additional experiments.

## Licence supplement 1.22.1

Read THIRD_PARTY_NOTICES.md. Fixed-commit licences, upstream NOTICE files and source-file attribution now accompany the unchanged experiment archives. This supplement changes packaging, not the manuscript or experimental results.

## Original software licence, version 1.22.2

Copyright 2026 Zhixuan Ma (马梽轩) and Zhengwei Shen (沈政伟). Original software contributions are licensed under Apache-2.0; see LICENSE and SOFTWARE_LICENSE_SCOPE.md. Third-party content retains upstream terms; original data organization and documentation remain CC BY 4.0.
