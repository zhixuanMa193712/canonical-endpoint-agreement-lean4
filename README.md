# Measuring State-Conditioned Canonical-Endpoint Agreement in Lean 4

Code packaging **1.22.3**, synchronized with the English manuscript and supplement
editorial revision of **8 October 2026**. The published evidence dataset remains
**1.22.2**: https://doi.org/10.5281/zenodo.22110052.
This update does not modify that deposit or its eleven original archives.
See RELEASE_STATUS.md and CHANGELOG.md for code/data version distinctions.

## Results and data

Data DOI: https://doi.org/10.5281/zenodo.22110052. Code repository: https://github.com/zhixuanMa193712/canonical-endpoint-agreement-lean4.
The Zenodo dataset contains eleven immutable evidence archives and a matching
source snapshot. Original execution archives are not rewritten. The additional
`paper_v1.21` correction layer is required for the final external-study values:
355/512 (69.34%) full-panel roots and 141/512 (27.54%) genealogy-deduplicated
roots in the 32-repository frame. Original archived summaries contain the old
lexical-head labels; reproducing their audit alone does not validate these
corrected numbers. The multi-step comparison is oracle-assisted and known-solvable.

## Layout

- `paper_v1.21/`: exact correction script, corrected root rows, summaries and figure source.
- `source_packages/`: original-name execution modules, including final Exp62 fix1 and Exp63/64.
- `historical_code/`: earlier execution/analysis modules retained for provenance.
- `portable_audit/`: older path-portability layer; its audit is not the corrected analysis.
- `docs/supplement/`: study map, variables, claims, manifests and reproduction order.
- `docs/`: licence references and a 52-candidate provenance inventory.
- `reproduce_correction.py`: temporary-directory reproduction of final corrections.
- `figures_20261008/`: final figure assets, unchanged plotting sources and numerical inputs.
- `reproduce_figures.py`: portable wrapper for the four figures and Figure S1.

## Quick offline reproduction

Use Python 3.11+ and NumPy 2.3.5 (the correction environment).
Install `requirements-analysis.txt` in a separate environment, then run:

```bash
python3 reproduce_correction.py --artifacts /absolute/path/to/zenodo/artifacts
```

This launches no Lean processes and downloads no repositories. It checks the
three input archive hashes, executes the unchanged correction script in a new
temporary workspace, compares five JSON/JSONL outputs with the bundled final
outputs, and writes a receipt. Input archives and bundled results are not modified.
The eleven archive checksums are independently listed in the dataset manifest.
The historical `paper_v1.21/figure4.py` is not the current manuscript figure pipeline.
For current figures, see figures_20261008/README.md. Their order is method,
confirmation, external replication, and sensitivity/repeat execution.

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
Author metadata is in `CITATION.cff`. The dataset DOI is published; it is not a
separately assigned software DOI. Cite the exact Git commit for this code revision.
Technical archive labels are provenance identifiers, not additional experiments.

## Licence supplement 1.22.1

Read THIRD_PARTY_NOTICES.md. Fixed-commit licences, upstream NOTICE files and source-file attribution now accompany the unchanged experiment archives. This supplement changes packaging, not the manuscript or experimental results.

## Original software licence, version 1.22.2

Copyright 2026 Zhixuan Ma (马梽轩) and Zhengwei Shen (沈政伟). Original software contributions are licensed under Apache-2.0; see LICENSE and SOFTWARE_LICENSE_SCOPE.md. Third-party content retains upstream terms; original data organization and documentation remain CC BY 4.0.
