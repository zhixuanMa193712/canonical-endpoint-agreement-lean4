# Exp59 confirmation execution: server commands

## Freeze exact jobs and run compile-only preflight

```bash
cd /home/music/mzz/MZX
unzip -o experiment59_four_policy_confirmation_execution_python_only.zip
export MZX_ROOT=/home/music/mzz/MZX

python experiment59_four_policy_confirmation_execution/test_experiment59_confirmation_static.py
python experiment59_four_policy_confirmation_execution/freeze_experiment59_confirmation_execution.py
python experiment59_four_policy_confirmation_execution/preflight_experiment59_confirmation.py --timeout 900
```

Require `execution_freeze_gate: true`, 64 roots, 256 jobs, zero pre-freeze
confirmation probes, and `compile_gate: true`.

## Launch 64 root shards

```bash
mkdir -p artifacts/v59/expansion_only_hard_root_efficiency_confirmation/confirmation/logs

nohup python -u \
  experiment59_four_policy_confirmation_execution/launch_experiment59_confirmation.py \
  --max-workers 16 \
  > artifacts/v59/expansion_only_hard_root_efficiency_confirmation/confirmation/logs/launcher.log \
  2>&1 < /dev/null &

echo $! > artifacts/v59/expansion_only_hard_root_efficiency_confirmation/confirmation/logs/nohup.pid
```

Monitor:

```bash
python experiment59_four_policy_confirmation_execution/monitor_experiment59_confirmation.py
```

## Finalize, analyze, audit, export

After 64 shards and 256 jobs complete:

```bash
python experiment59_four_policy_confirmation_execution/finalize_experiment59_confirmation.py
python experiment59_four_policy_confirmation_execution/analyze_experiment59_confirmation.py
python experiment59_four_policy_confirmation_execution/audit_experiment59_confirmation.py
python experiment59_four_policy_confirmation_execution/export_experiment59_confirmation.py
```

The registered efficiency and coverage gates are reported separately. If full
solves zero roots, the manuscript must state that solved-root coverage is
uninformative even if the numerical noninferiority bound passes.
