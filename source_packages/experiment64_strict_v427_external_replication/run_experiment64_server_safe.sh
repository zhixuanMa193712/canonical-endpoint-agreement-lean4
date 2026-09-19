#!/usr/bin/env bash
set -euo pipefail

MZX_ROOT=/home/music/mzz/MZX
EXP63_ROOT="$MZX_ROOT/artifacts/v63/strict_v427_recruitment"
EXP64_ROOT="$MZX_ROOT/artifacts/v64/strict_v427_external_replication"
EXP64_LOG="$EXP64_ROOT/logs/pipeline.log"
EXP64_OUTPUT="$MZX_ROOT/exports/experiment64_strict_v427_external_replication_results.zip"

cd "$MZX_ROOT"
if [ -f /home/music/miniconda3/etc/profile.d/conda.sh ]; then
  source /home/music/miniconda3/etc/profile.d/conda.sh
fi
conda activate leandojo_v2_env
export MZX_ROOT

test -s "$EXP63_ROOT/audit/audit.json"
jq -e '.audit_passed == true and .completed_repositories == 52 and .lineage_representatives == 32' \
  "$EXP63_ROOT/audit/audit.json" >/dev/null

if pgrep -af '[r]un_experiment64_pipeline.py' >/dev/null; then
  echo "REFUSED: an Exp64 pipeline process is already running."
  pgrep -af '[r]un_experiment64_pipeline.py'
  exit 2
fi

FREE_GIB=$(df -Pk "$MZX_ROOT" | awk 'NR==2 {printf "%d", $4/1024/1024}')
if [ "$FREE_GIB" -lt 170 ]; then
  echo "REFUSED: only ${FREE_GIB} GiB is free; Exp64 requires at least 170 GiB before launch."
  exit 2
fi

python -m py_compile experiment64_strict_v427_external_replication/*.py
mkdir -p "$EXP64_ROOT/logs" "$MZX_ROOT/exports"

nohup python -u \
  experiment64_strict_v427_external_replication/run_experiment64_pipeline.py \
  --artifact-root "$EXP64_ROOT" \
  --source-exp63-root "$EXP63_ROOT" \
  --output "$EXP64_OUTPUT" \
  --git-timeout 1800 \
  --build-timeout 14400 \
  --trace-timeout 14400 \
  --enumeration-timeout 7200 \
  --lean-timeout 1200 \
  --threads 2 \
  > "$EXP64_LOG" 2>&1 < /dev/null &

EXP64_PID=$!
printf '%s\n' "$EXP64_PID" > "$EXP64_ROOT/logs/pipeline.pid"
echo "EXP64_STARTED pid=$EXP64_PID"
echo "LOG=$EXP64_LOG"
echo "Closing SSH or the MacBook will not stop this nohup process."
