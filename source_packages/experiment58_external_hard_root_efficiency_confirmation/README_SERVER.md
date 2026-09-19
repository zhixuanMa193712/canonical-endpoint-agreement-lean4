# Exp58 server instructions: pre-continuation Fix2 package

This Fix2 package completes only the source lock, candidate-only eligibility screen, disjoint pilot freeze, and pilot-based power machinery. It intentionally contains no confirmation continuation runner. Fix1 changed only the Lake 5 build invocation from unsupported `lake build -j N` to `lake build`. Fix2 stages each frozen, hash-identical measurement source under the corresponding Lake project because Lean 4.27 rejects frontend input paths outside the project root. The 512 pre-candidate root-path failures remain preserved in place, and replacement receipts use a separate execution root.

## 1. Verify and unpack

```bash
cd /home/music/mzz/MZX
sha256sum experiment58_external_hard_root_efficiency_confirmation_root_path_fix2_python_only.zip
unzip -o experiment58_external_hard_root_efficiency_confirmation_root_path_fix2_python_only.zip
export MZX_ROOT=/home/music/mzz/MZX
```

Keep `experiment57_end_to_end_search_benchmark_results.zip` in the project root. Its required SHA-256 is `da9da92de0dfd4a7426f1bd2284e9a862d95ae9f56f15fd9d1dbc2fffad4cbf0`.

## 2. Static tests and protected Fix2 amendment

```bash
python experiment58_external_hard_root_efficiency_confirmation/test_experiment58_static.py
python experiment58_external_hard_root_efficiency_confirmation/apply_experiment58_fix2.py
python experiment58_external_hard_root_efficiency_confirmation/preflight_experiment58.py --timeout 900
```

Both commands execute zero theorem roots and zero tactics.

The amendment validates and preserves all 512 Fix1 failures, records zero candidate/probe execution, and selects `screening/root_path_fix2` for replacement receipts. Do not rebuild or re-enumerate the already exact benchmark sources.

## 3. Exact checkouts and build (fresh installations only)

```bash
python -u experiment58_external_hard_root_efficiency_confirmation/prepare_experiment58_benchmarks.py \
  --build --build-jobs 16 --timeout 28800 \
  | tee artifacts/v58/external_hard_root_efficiency_confirmation/logs/prepare.log
```

This checks out exact detached commits, verifies the Apache-2.0 files and Lean v4.27.0, and builds both projects.

## 4. Enumerate and compile-preflight

```bash
python experiment58_external_hard_root_efficiency_confirmation/enumerate_experiment58_targets.py
python experiment58_external_hard_root_efficiency_confirmation/preflight_experiment58.py --timeout 900
```

These commands execute zero candidate tactics and zero continuation probes.

## 5. Run 32 candidate-only screening shards

```bash
mkdir -p artifacts/v58/external_hard_root_efficiency_confirmation/logs/candidate_screening_fix2

for shard in $(seq 0 31); do
  label=$(printf '%02d' "$shard")
  nohup python -u \
    experiment58_external_hard_root_efficiency_confirmation/run_experiment58_candidate_screening.py \
    --shard-index "$shard" --shard-count 32 --timeout 1800 \
    > "artifacts/v58/external_hard_root_efficiency_confirmation/logs/candidate_screening_fix2/shard-${label}.log" \
    2>&1 < /dev/null &
  echo $! > "artifacts/v58/external_hard_root_efficiency_confirmation/logs/candidate_screening_fix2/shard-${label}.pid"
done
```

Monitor compactly:

```bash
python - <<'PY'
from pathlib import Path
import json
r = Path('artifacts/v58/external_hard_root_efficiency_confirmation')
print(json.dumps({
  'candidate_receipts': len(list((r/'screening/root_path_fix2/candidate_receipts').glob('*.json'))),
  'expected': 512,
  'shards_complete': len(list((r/'screening/root_path_fix2/shards').glob('shard-*.json'))),
}, indent=2))
PY
```

Each root runs all 23 candidates in one Lean process from independent copies of the same pre-state. No downstream tactic is passed to the worker.

## 6. Finalize screening and freeze pilot

```bash
python experiment58_external_hard_root_efficiency_confirmation/finalize_experiment58_candidate_screening.py
python experiment58_external_hard_root_efficiency_confirmation/freeze_experiment58_pilot.py
```

Stop here and return the `screening/summary.json` and `pilot/frozen/design.json` receipts. The next code package will execute only the 32 frozen pilot roots. After that pilot produces `pilot/results/paired_root_metrics.jsonl`, run:

```bash
python experiment58_external_hard_root_efficiency_confirmation/plan_experiment58_power.py
python experiment58_external_hard_root_efficiency_confirmation/freeze_experiment58_confirmation.py
```

Never publish PutnamBench target-to-successful-tactic rows. See `THIRD_PARTY_AUDIT.csv`.
