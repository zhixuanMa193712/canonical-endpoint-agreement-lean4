# Experiment 53 Second-Machine Run Order

Exp53 is already frozen. Do not rerun `freeze_experiment53.py` on machine two. The second machine must be physically distinct from the Exp51 server `gpuserver01`; the compile-only preflight rejects that hostname.

## Requirements

- a physical Mac running macOS (`platform.system() == "Darwin"`) and distinct from `gpuserver01`;
- Python 3.9 or newer (the package static test passed under Python 3.9.6);
- `git`, `elan`, and `lake` on `PATH`;
- enough disk space to build four exact Lean repositories;
- network access for the initial repository and dependency checkout;
- the extracted `experiment53_cross_machine_subset_reexecution` directory.

No Exp51 or Exp52 result ZIP is required on machine two because the sixteen portable reference projections are embedded and hash-locked in the package.

## Run order

From the directory that contains the extracted package:

```bash
python3 experiment53_cross_machine_subset_reexecution/test_exp53_static.py

python3 experiment53_cross_machine_subset_reexecution/prepare_exp53_checkouts.py \
  --checkout-root external_repos/experiment53_machine2 \
  --artifact-root artifacts/v53/cross_machine_subset \
  --build \
  --build-timeout 14400

python3 experiment53_cross_machine_subset_reexecution/preflight_exp53.py \
  --artifact-root artifacts/v53/cross_machine_subset \
  --timeout 900
```

The preflight must report `compile_gate: true`, `theorem_sources_elaborated: 0`, and `candidate_tactics_executed: 0`.

Run the four shards. They may run in four terminals or as four detached `nohup` processes:

```bash
mkdir -p artifacts/v53/cross_machine_subset/logs

for shard in 0 1 2 3; do
  nohup python3 -u experiment53_cross_machine_subset_reexecution/run_exp53.py \
    --artifact-root artifacts/v53/cross_machine_subset \
    --shard-index "$shard" \
    --shard-count 4 \
    --lean-timeout 900 \
    > "artifacts/v53/cross_machine_subset/logs/shard-${shard}.log" 2>&1 < /dev/null &
done
```

After all four shard logs contain a JSON summary with `shard_gate: true`:

```bash
python3 experiment53_cross_machine_subset_reexecution/analyze_exp53.py \
  --artifact-root artifacts/v53/cross_machine_subset \
  --shard-count 4

python3 experiment53_cross_machine_subset_reexecution/export_exp53_bundle.py \
  --artifact-root artifacts/v53/cross_machine_subset \
  --output exports/experiment53_cross_machine_subset_results.zip
```

The target positive label is `cross_machine_exact`. Any `cross_machine_mismatch` or `invalid_execution` is retained and must not be manually repaired or rerun under the same freeze.
