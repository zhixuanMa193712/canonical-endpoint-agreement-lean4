# Final English manuscript figures — 8 October 2026

Ready-to-use Fig1.pdf–Fig4.pdf and SVG/PNG files are copied unchanged from the
final manuscript assets. Order: method, confirmation, external replication,
sensitivity/repeat execution. Figure S1 is in ../docs/supplement/. Numerical
inputs are in figure_source_data.json and external_source.csv.

The three plotting scripts are unchanged workspace sources. Use the portable
wrapper from the repository root, rather than running them directly:

```bash
python -m pip install -r requirements-figures.txt
python reproduce_figures.py --artifacts /absolute/path/to/zenodo/artifacts --output /absolute/path/to/new-figure-output
```

The output directory must not exist. The wrapper verifies Exp49/50/52 archive
hashes, stages the scripts and corrected external results in a temporary layout,
renders five figures, and compares numerical JSON/CSV outputs to final inputs.
No Lean call, bootstrap, filtering or network access occurs during generation.

Python 3.12 and matplotlib 3.11.2 were used for the final assets. Arial is preferred,
with Helvetica/DejaVu Sans fallbacks. PDF timestamps and fonts can change binary
hashes and glyph placement; numerical matching does not guarantee pixel-identical
graphics. Inspect regenerated figures before replacing manuscript assets.
No proprietary fonts are bundled.

Original plotting software contributions are covered by the repository software
licence scope; original documentation/figure organization is CC BY 4.0. Upstream
repository names and source-derived content retain applicable terms.
