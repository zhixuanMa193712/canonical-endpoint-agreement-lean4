# Exp52 pre-probe compile compatibility Fix4

This package is a narrow mechanical amendment after the completed Exp51 Fix3
execution and the frozen Exp52 selection, but before the first continuation
probe. It preserves `exp52/preflight/worker_compile.json` as the failed Fix3
compiler diagnostic and writes the new receipt to
`exp52/preflight/worker_compile_fix4.json`.

The generated Lean source differs at one site only: the unsupported
`ToString Exception` call is rendered through
`Exception.toMessageData.toString` in `BaseIO`. The frozen 576 Exp51 roots,
40 selected witness roots, 36 controls, 9 probes, 1320 Exp52 cells, endpoint
definitions, statistics, information thresholds, no-retry policy, and claim
boundaries are unchanged.

## Run now: static check, freeze, compile-only preflight

```bash
cd /home/music/mzz/MZX

unzip -o \
experiment52_compile_compatibility_fix4_python_only.zip

export MZX_ROOT=/home/music/mzz/MZX

python \
experiment52_compile_compatibility_fix4/test_exp52_compile_fix4_static.py

python \
experiment52_compile_compatibility_fix4/freeze_exp52_compile_fix4.py

python \
experiment52_compile_compatibility_fix4/preflight_exp52_execution.py \
--workers 12 \
--timeout 300
```

Stop after the preflight and inspect
`artifacts/v51/external_repository_replication_scientific/exp52/preflight/worker_compile_fix4.json`.
No scientific candidate or continuation probe is executed by these commands.

## Only after `compile_gate: true`

Run the 32 immutable shards in separate background processes:

```bash
cd /home/music/mzz/MZX
export MZX_ROOT=/home/music/mzz/MZX

mkdir -p \
artifacts/v51/external_repository_replication_scientific/logs/fix4_exp52

for shard in $(seq 0 31); do
  label=$(printf '%02d' "$shard")
  nohup python -u \
  experiment52_compile_compatibility_fix4/run_exp52_shards.py \
  --shard-index "$shard" \
  > "artifacts/v51/external_repository_replication_scientific/logs/fix4_exp52/shard-${label}.log" \
  2>&1 < /dev/null &
  echo $! > \
  "artifacts/v51/external_repository_replication_scientific/logs/fix4_exp52/shard-${label}.pid"
done
```

After all shard summaries exist:

```bash
python \
experiment52_compile_compatibility_fix4/finalize_exp52_execution.py

python \
experiment52_compile_compatibility_fix4/analyze_exp52.py

python \
experiment52_compile_compatibility_fix4/audit_exp52.py

python \
experiment52_compile_compatibility_fix4/export_exp52_bundle.py
```

The frozen selection contains only 40 witness roots across 7 repositories and
36 controls across 6 repositories, below the preregistered information
thresholds. Therefore a valid run can produce descriptive continuation
measurements and `continuation_inconclusive`, but cannot satisfy the frozen
support or no-go information gates.
