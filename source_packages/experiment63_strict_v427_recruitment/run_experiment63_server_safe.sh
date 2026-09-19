#!/usr/bin/env bash
# Safe launcher: this script runs in a child Bash process, so any setup failure
# returns to the caller's terminal instead of terminating the interactive shell.

MZX_SERVER_ROOT=/home/music/mzz/MZX
EXP63_SERVER_ROOT="$MZX_SERVER_ROOT/artifacts/v63/strict_v427_recruitment"

cd "$MZX_SERVER_ROOT" || {
  echo "ERROR: cannot enter $MZX_SERVER_ROOT"
  exit 1
}

if ! command -v conda >/dev/null 2>&1; then
  echo "ERROR: conda is not available in PATH; terminal remains open."
  exit 1
fi

EXP63_CONDA_BASE="$(conda info --base 2>/dev/null)"
if [ -f "$EXP63_CONDA_BASE/etc/profile.d/conda.sh" ]; then
  # shellcheck disable=SC1090
  source "$EXP63_CONDA_BASE/etc/profile.d/conda.sh"
fi
if ! conda activate leandojo_v2_env; then
  echo "ERROR: could not activate leandojo_v2_env; terminal remains open."
  exit 1
fi

export MZX_ROOT="$MZX_SERVER_ROOT"
export EXP63_ROOT="$EXP63_SERVER_ROOT"

if [ -z "${GITHUB_TOKEN:-}" ] && command -v gh >/dev/null 2>&1; then
  EXP63_GH_TOKEN="$(gh auth token 2>/dev/null)"
  if [ -n "$EXP63_GH_TOKEN" ]; then
    export GITHUB_TOKEN="$EXP63_GH_TOKEN"
  fi
fi

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "ERROR: GITHUB_TOKEN is not set; Exp63 was not started."
  echo "Run: export GITHUB_TOKEN='your_token'"
  echo "Then rerun: bash experiment63_strict_v427_recruitment/run_experiment63_server_safe.sh"
  exit 1
fi

if [ ! -f "$MZX_SERVER_ROOT/experiment63_strict_v427_recruitment/run_experiment63.py" ]; then
  echo "ERROR: Experiment 63 package is incomplete; terminal remains open."
  exit 1
fi
if [ ! -f "$MZX_SERVER_ROOT/artifacts/v61/archival_v427_infrastructure_recovery/recruitment_shortfall/audit.json" ]; then
  echo "ERROR: Experiment 61 source artifacts were not found; Exp63 was not started."
  exit 1
fi

if pgrep -f 'experiment63_strict_v427_recruitment/run_experiment63.py' >/dev/null 2>&1; then
  echo "EXP63_ALREADY_RUNNING; no duplicate process was started."
  pgrep -af 'experiment63_strict_v427_recruitment/run_experiment63.py'
  exit 0
fi

mkdir -p "$EXP63_ROOT/logs" "$MZX_SERVER_ROOT/exports"

nohup python -u experiment63_strict_v427_recruitment/run_experiment63.py \
  --artifact-root "$EXP63_ROOT" \
  --source-exp61-root "$MZX_SERVER_ROOT/artifacts/v61/archival_v427_infrastructure_recovery" \
  --phase all \
  --search-workers 48 \
  --static-workers 4 \
  --threads 2 \
  --wait-for-exp62 \
  > "$EXP63_ROOT/logs/pipeline.log" 2>&1 < /dev/null &

EXP63_PIPELINE_PID=$!
echo "EXP63_STARTED pid=$EXP63_PIPELINE_PID"
echo "LOG=$EXP63_ROOT/logs/pipeline.log"
exit 0
