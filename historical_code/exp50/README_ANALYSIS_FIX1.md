# Exp50 analysis-fix1

This is an additive, analysis-only mechanical amendment.  It does not replace
or overwrite any frozen source, M0–M5 execution row, original analysis summary,
or original mismatch ledger.  It invokes no Lean process.

The original analysis hashed the entire raw endpoint container.  Exp49 and
Exp50 used different recorder schema labels inside otherwise identical
containers:

- `exp49-raw-endpoint-v1`
- `exp50-raw-endpoint-v1`

The original 706 mismatches consist exactly of the resulting raw container
hash differences: 514 executable candidates, 96 authored endpoints, and 96
initial endpoints.  Status, raw ordered state bytes, goal count, terminal flag,
`kappa_text48`, and the strict endpoint are verified independently by fix1.

## Run

```bash
cd /home/music/mzz/MZX
unzip -o experiment50_independent_reexecution_analysis_fix1_python_only.zip
export MZX_ROOT=/home/music/mzz/MZX

python experiment50_independent_reexecution/amend_experiment50_analysis_fix1.py
```

This writes only:

`artifacts/v50/independent_reexecution/analysis_fix1/`

The original failed analysis remains under `analysis/`.

## Compact result

```bash
python -c 'import json; p="artifacts/v50/independent_reexecution/analysis_fix1/summary.json"; x=json.load(open(p)); keys=["fix_id","original_failed_analysis_preserved","original_mismatch_count","superseded_schema_only_container_hash_mismatches","mismatch_count","manual_reconciliation_count","roots","executable_candidates","raw_endpoint_content_definition","amendment_checks","checks","root_level_complete_agreement","repository_level_complete_agreement","analysis_fix1_pass","reexecution_pass","independence_limit","next_step"]; print(json.dumps({k:x.get(k) for k in keys},indent=2))'
```

## Export after a passing fix1 gate

```bash
python experiment50_independent_reexecution/export_experiment50_bundle_fix1.py
```

The result is written to:

`/home/music/mzz/MZX/exports/experiment50_independent_reexecution_fix1_results.zip`
