# Experiment 54 Fix3 server execution

Fix3 preserves all three failed executions (v1, Fix1, and Fix2) and repeats
the exact same 896-cell frozen plan. It changes only the Lean runtime-exception
boundary around the isolated downstream probe. No scientific selection,
tactic, probe, endpoint, heartbeat budget, analysis, or decision rule changes.

Do not delete, rename, or edit these source artifacts or code directories:

- `artifacts/v54/effect_aware_depth2_microbenchmark`
- `artifacts/v54/effect_aware_depth2_microbenchmark_fix1`
- `artifacts/v54/effect_aware_depth2_microbenchmark_fix2`
- `experiment54_effect_aware_depth2_microbenchmark`
- `experiment54_effect_aware_depth2_microbenchmark_fix1`
- `experiment54_effect_aware_depth2_microbenchmark_fix2`

Use `python`, not `python3`:

```bash
cd /home/music/mzz/MZX
unzip -o experiment54_effect_aware_depth2_microbenchmark_fix3_python_only.zip
export MZX_ROOT=/home/music/mzz/MZX

python \
experiment54_effect_aware_depth2_microbenchmark_fix3/test_experiment54_static.py \
--source-archive \
/home/music/mzz/MZX/exports/experiment49_candidate_endpoint_robustness_results.zip

python \
experiment54_effect_aware_depth2_microbenchmark_fix3/freeze_experiment54.py \
--source-archive \
/home/music/mzz/MZX/exports/experiment49_candidate_endpoint_robustness_results.zip

python \
experiment54_effect_aware_depth2_microbenchmark_fix3/preflight_experiment54.py \
--timeout 300
```

The freeze must report exact carry-forward from v1, Fix1, and Fix2;
preservation of 896 cells from each failed execution; and zero Fix3 scientific
executions. The compile-only preflight must report `compile_gate: true` and
zero theorem sources, candidates, and probes executed.

Launch all 16 Fix3 shards. Do not relaunch only the seven previously affected
cells.

```bash
mkdir -p artifacts/v54/effect_aware_depth2_microbenchmark_fix3/logs

for i in $(seq 0 15); do
  label=$(printf '%02d' "$i")
  nohup python -u \
    experiment54_effect_aware_depth2_microbenchmark_fix3/run_experiment54_shards.py \
    --shard-index "$i" \
    > "artifacts/v54/effect_aware_depth2_microbenchmark_fix3/logs/shard-${label}.log" \
    2>&1 < /dev/null &
  echo $! > \
    "artifacts/v54/effect_aware_depth2_microbenchmark_fix3/logs/shard-${label}.pid"
done
```

Compact progress check:

```bash
python - <<'PY'
import json
from pathlib import Path

root = Path("artifacts/v54/effect_aware_depth2_microbenchmark_fix3")
summaries = sorted((root / "execution/shards").glob("shard-*/summary.json"))
rows = list((root / "execution/shards").glob("shard-*/rows/*.json"))
print(json.dumps({
    "shards_completed": len(summaries),
    "shards_expected": 16,
    "cells_recorded": len(rows),
    "cells_expected": 896,
    "percent": round(100 * len(rows) / 896, 2),
}, indent=2))
PY
```

After all shards complete, finalize and inspect the integrity gate:

```bash
python \
experiment54_effect_aware_depth2_microbenchmark_fix3/finalize_experiment54_execution.py
```

Only if `valid_reconstruction_cells` is 896 and
`execution_integrity_gate` is `true`:

```bash
python \
experiment54_effect_aware_depth2_microbenchmark_fix3/analyze_experiment54.py

python \
experiment54_effect_aware_depth2_microbenchmark_fix3/audit_experiment54.py

python \
experiment54_effect_aware_depth2_microbenchmark_fix3/export_experiment54_bundle.py
```

The final bundle is
`exports/experiment54_effect_aware_depth2_fix3_results.zip`. Do not relaunch an
individually claimed Fix3 cell or manually reconcile a row.
