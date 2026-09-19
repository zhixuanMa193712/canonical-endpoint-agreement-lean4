# Experiment 48
## Live Lean TacticInfo Counterfactual Equivalence

This repository contains the reproducibility artifact for Experiment 48.

The experiment studies whether independently executed alternative Lean tactics can reach equivalent live proof states when branched from the same original Lean elaboration state.

## Main idea

Instead of restoring serialized proof states, Experiment 48 uses live Lean elaboration information:

- InfoTree TacticInfo
- ContextInfo
- TacticInfo.mctxBefore
- TacticInfo.goalsBefore

The counterfactual branch execution uses:

Lean.Elab.Tactic.run

on the original pre-state.

Serialized state restoration and Pantograph execution are not used.

## Fixed environment

Lean version:

Lean 4.27.0

Target repositories:

8 repositories

Split:

Discovery:
- teorth/pfr
- leanprover-community/physlib
- leanprover-community/sphere-eversion
- leanprover-community/flt-regular

Confirmation:
- fpvandoorn/carleson
- ImperialCollegeLondon/FLT
- thefundamentaltheor3m/Sphere-Packing-Lean
- RemyDegenne/brownian-motion

## Execution pipeline

1. Freeze protocol
freeze_experiment48_live_tacticinfo_equivalence.py
2. Compile preflight
preflight_experiment48_live_worker_fix1.py
3. Run full experiment
run_experiment48_full_pipeline_fix1.py
Pipeline:
Fix amendment
|
Preflight
|
Smoke
|
Discovery
|
Confirmation
|
Bundle export
4. Export analysis artifact
export_experiment48_mac_bundle_fix1.py

## Artifact structure
artifacts/v48/

frozen/
experiment48_config.json

preflight_fix1/

smoke_fix1/

discovery_fix1/

confirmation_fix1/

experiment48_fix1_mac_analysis_bundle.zip

## Reproducibility notes

The experiment uses frozen hashes for:

- source configuration
- selected theorem files
- candidate tactic library
- worker implementation
- repository commits

Any modification requires a new experiment version.

