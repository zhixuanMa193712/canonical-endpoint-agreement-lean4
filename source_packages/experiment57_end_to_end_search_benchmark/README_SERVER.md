# Four-policy end-to-end depth-two search benchmark

This experiment compares full expansion, strict-effect-aware deduplication,
head-based deduplication, and fixed-budget random pruning on exactly the same 16
roots, complete 23-candidate order, eight-probe order, and 7,200-second
per-root-policy budget. Every policy independently re-executes all 23 candidates
before selecting its depth-two frontier; every candidate and candidate-plus-
probe path receives one fresh Lean process and no retry. Process calls and
expanded nodes are primary efficiency metrics; wall-clock is secondary and
descriptive.

Run on the Lean 4.27 server:

```bash
export MZX_ROOT=/home/music/mzz/MZX
python experiment57_end_to_end_search_benchmark/test_experiment57_static.py
python experiment57_end_to_end_search_benchmark/freeze_experiment57.py
mkdir -p artifacts/v57/end_to_end_search_benchmark/logs

for shard in $(seq 0 15); do
  nohup python -u experiment57_end_to_end_search_benchmark/run_experiment57_shards.py \
    --shard-index "$shard" \
    > "artifacts/v57/end_to_end_search_benchmark/logs/shard-$(printf '%02d' "$shard").log" 2>&1 < /dev/null &
done
```

After all 16 shard receipts exist:

```bash
python experiment57_end_to_end_search_benchmark/analyze_experiment57.py
```
