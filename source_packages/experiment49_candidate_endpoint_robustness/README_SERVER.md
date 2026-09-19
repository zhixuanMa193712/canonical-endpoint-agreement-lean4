# Experiment 49 server runbook

This Fix1 package implements the frozen Exp49 candidate-ablation and strict-endpoint
validation protocol. It reuses the exact 96 Exp48 confirmation roots and their
23 frozen alternatives. It never writes under `artifacts/v48`.

Fix1 repairs only Lean `do`/structure-literal layout errors found by the initial
compile-only preflight. That failed preflight executed zero theorem sources and
zero scientific candidate tactics.

Exp49 is a post-hoc robustness/construct-validation experiment, not an
independent confirmation. Its supported object remains state-conditioned,
one-step endpoint agreement.

## Required server layout

The archived project root must remain `/home/music/mzz/MZX` and must already
contain:

- `artifacts/v48/live_tacticinfo_counterfactual_equivalence/frozen/experiment48_config.json`
- `artifacts/v48/live_tacticinfo_counterfactual_equivalence/confirmation_fix1/summary.json`
- all 96 Exp48 `confirmation_fix1/theorems/*/*.json` rows
- the eight frozen repository checkouts and selected theorem files referenced
  by the Exp48 config
- `/home/music/mzz/MZX/raid/data`
- `lake` and Lean `v4.27.0` in the frozen repository environments

The Exp49 package directory must be:

`/home/music/mzz/MZX/experiment49_candidate_endpoint_robustness`

No third-party Python package is required; Python 3.10+ standard library is
sufficient.

## Replacing the initial compile-failing package

If the initial preflight produced Lean syntax errors, preserve that zero-run
artifact tree and start a fresh freeze for Fix1:

```bash
cd /home/music/mzz/MZX
mv artifacts/v49/candidate_endpoint_robustness \
  artifacts/v49/candidate_endpoint_robustness_preflight_failed_fix0_20260821
unzip -o experiment49_candidate_endpoint_robustness_fix1_python_only.zip
export MZX_ROOT=/home/music/mzz/MZX
```

The `mv` is intentional: the initial frozen config contains the old code lock,
so Fix1 must not overwrite or reconcile it. The moved directory is retained as
an audit record of a compile-only failure with zero theorem/candidate runs.

## Recommended step-by-step execution

Start from the project root:

```bash
cd /home/music/mzz/MZX
export MZX_ROOT=/home/music/mzz/MZX
```

Run the following commands in exactly this order.

### 1. Freeze

```bash
python experiment49_candidate_endpoint_robustness/freeze_experiment49.py
```

Do not edit any package Python file after this command. The freeze records a
code lock and exact hashes for the Exp48 source evidence.

### 2. Compile-only preflight

```bash
python experiment49_candidate_endpoint_robustness/preflight_experiment49.py \
  --timeout 300
```

This compiles only the embedded worker. It elaborates zero theorem sources and
executes zero candidate tactics. Continue only if
`artifacts/v49/candidate_endpoint_robustness/preflight/strict_worker_compile.json`
contains `"compile_ok": true`.

### 3. Smoke

```bash
python experiment49_candidate_endpoint_robustness/run_experiment49.py \
  --phase smoke \
  --lean-timeout 900
```

Continue only if `smoke/execution_summary.json` contains
`"protocol_smoke_ok": true`.

### 4. Exact 96-root validation re-execution

```bash
python experiment49_candidate_endpoint_robustness/run_experiment49.py \
  --phase validation \
  --lean-timeout 900
```

This is deliberately sequential. Every root executes authored replay plus all
23 alternatives from the same live `TacticInfo` pre-state. Continue only if
`validation/execution_summary.json` contains `"validation_go": true`. That
gate also requires every L0/text48 theorem result to match its archived Exp48
row.

### 5. Frozen offline analysis

```bash
python experiment49_candidate_endpoint_robustness/experiment49_analysis.py
```

This stage executes no Lean code. It computes all frozen candidate views,
strict/text endpoint confusion, pair-density normalization,
leave-one-head-out diagnostics, and deterministic rarefaction from the saved
complete execution matrix.

### 6. Export result bundle

```bash
python experiment49_candidate_endpoint_robustness/export_experiment49_bundle.py
```

The result is written to:

`/home/music/mzz/MZX/exports/experiment49_candidate_endpoint_robustness_results.zip`

Download both that ZIP and its adjacent `.receipt.json` file.

## Resuming an interrupted phase

If smoke or validation was interrupted after its claim file was created but
before `execution_summary.json` was written, rerun the same phase with
`--resume`. Existing theorem rows are identity-checked and reused.

```bash
python experiment49_candidate_endpoint_robustness/run_experiment49.py \
  --phase validation \
  --lean-timeout 900 \
  --resume
```

For an interrupted freeze, rerun `freeze_experiment49.py --resume-freeze`.
Never delete a claim or manually reconcile rows.

## One-command resumable alternative

After reviewing the stepwise protocol, the same ordered pipeline can be run as:

```bash
python experiment49_candidate_endpoint_robustness/run_experiment49_full_pipeline.py \
  --preflight-timeout 300 \
  --lean-timeout 900
```

The orchestrator skips completed stages and supplies the correct resume flag
when a phase claim exists.
