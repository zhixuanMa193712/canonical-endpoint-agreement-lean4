# Exp59 four-policy pilot: server instructions

This Python-only package starts from the already completed Exp59 screening
summary with record SHA-256
`96ef54df49716b1037d84ae383b790d6fde86800fb4fc3325a371a61cec80331`.
It does not rerun candidate recruitment.

## 1. Install and run zero-Lean validation

```bash
cd /home/music/mzz/MZX
unzip -o experiment59_four_policy_pilot_execution_python_only.zip
export MZX_ROOT=/home/music/mzz/MZX

python experiment59_four_policy_pilot_execution/test_experiment59_pilot_static.py
python experiment59_four_policy_pilot_execution/freeze_experiment59_pilot.py
python experiment59_four_policy_pilot_execution/preflight_experiment59_pilot.py --timeout 900
```

The freeze must report 32 roots, 128 jobs, and zero continuation probes before
freeze. The preflight must report `compile_gate: true`.

## 2. Run the 32-root pilot

The bounded launcher runs at most 16 root shards concurrently:

```bash
nohup python -u \
  experiment59_four_policy_pilot_execution/launch_experiment59_pilot.py \
  --max-workers 16 \
  > artifacts/v59/expansion_only_hard_root_efficiency_confirmation/pilot/logs/launcher.log \
  2>&1 < /dev/null &

echo $! > artifacts/v59/expansion_only_hard_root_efficiency_confirmation/pilot/logs/nohup.pid
```

Monitor without printing long logs:

```bash
python experiment59_four_policy_pilot_execution/monitor_experiment59_pilot.py
tail -n 30 artifacts/v59/expansion_only_hard_root_efficiency_confirmation/pilot/logs/launcher.log
```

Do not relaunch a cell that has an input receipt but no final result. The runner
fails closed because such a relaunch would be a scientific retry.

## 3. Finalize, analyze, audit, and plan confirmation n

Run these only after the monitor reports 32 shards and 128 jobs:

```bash
python experiment59_four_policy_pilot_execution/finalize_experiment59_pilot.py
python experiment59_four_policy_pilot_execution/analyze_experiment59_pilot.py
python experiment59_four_policy_pilot_execution/audit_experiment59_pilot.py
python experiment59_four_policy_pilot_execution/plan_experiment59_power.py
```

The analysis reports actual process-call saving and coverage loss as separate
estimands. It must not be described as confirmation evidence.

## 4. Freeze, but do not execute, the confirmation set

Only if `power_gate` is true:

```bash
python experiment59_four_policy_pilot_execution/freeze_experiment59_confirmation.py
```

This creates a balanced, disjoint, immutable confirmation selection and a full
selection audit. The package intentionally contains no confirmation execution
runner; that must be a separate post-freeze package.
