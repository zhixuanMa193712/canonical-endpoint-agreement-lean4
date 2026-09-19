# Experiment 62 server runbook

Do not run this experiment concurrently with Experiment 61.  The policy jobs
are intentionally sequential because wall-clock and time-to-first-proof are
secondary outcomes and must not be confounded by policy-level resource
competition.

The package assumes `/home/music/mzz/MZX/leandojo_benchmark_4/random/test.json`
and the `leandojo_v2_env` environment.  If a local mathlib checkout at the
frozen commit already exists, set `EXP62_MATHLIB_REPO` to it; otherwise
LeanDojo uses its normal cache and repository resolution.

Install and preflight:

```bash
cd /home/music/mzz/MZX
unzip -o experiment62_multistep_solvable_search_python_only.zip
conda activate leandojo_v2_env
export MZX_ROOT=/home/music/mzz/MZX
EXP62_ROOT=/home/music/mzz/MZX/artifacts/v62/multistep_solvable_search
mkdir -p "$EXP62_ROOT/logs"

python -u experiment62_multistep_solvable_search/install_experiment62.py \
  --artifact-root "$EXP62_ROOT"
python -u experiment62_multistep_solvable_search/preflight_experiment62.py \
  --artifact-root "$EXP62_ROOT"
```

Run qualification after Experiment 61 has stopped.  Two workers affect only
the nonscientific qualification stage:

```bash
nohup python -u \
  experiment62_multistep_solvable_search/run_experiment62_qualification.py \
  --artifact-root "$EXP62_ROOT" \
  --workers 2 \
  > "$EXP62_ROOT/logs/qualification.log" 2>&1 < /dev/null &
echo $!
```

After qualification completes, freeze and run the pilot sequentially:

```bash
python -u experiment62_multistep_solvable_search/freeze_experiment62_phase.py \
  --artifact-root "$EXP62_ROOT" --phase pilot
nohup python -u experiment62_multistep_solvable_search/run_experiment62_phase.py \
  --artifact-root "$EXP62_ROOT" --phase pilot \
  > "$EXP62_ROOT/logs/pilot.log" 2>&1 < /dev/null &
echo $!
```

Analyze the pilot.  Confirmation freeze fails closed unless `pilot_go` is true:

```bash
python -u experiment62_multistep_solvable_search/analyze_experiment62.py \
  --artifact-root "$EXP62_ROOT" --phase pilot
jq '{pilot_go,decision_label,coverage_estimand,efficiency_estimand}' \
  "$EXP62_ROOT/pilot/analysis/summary.json"
python -u experiment62_multistep_solvable_search/freeze_experiment62_phase.py \
  --artifact-root "$EXP62_ROOT" --phase confirmation
```

Run, analyze, audit, and export confirmation:

```bash
nohup python -u experiment62_multistep_solvable_search/run_experiment62_phase.py \
  --artifact-root "$EXP62_ROOT" --phase confirmation \
  > "$EXP62_ROOT/logs/confirmation.log" 2>&1 < /dev/null &
echo $!

python -u experiment62_multistep_solvable_search/analyze_experiment62.py \
  --artifact-root "$EXP62_ROOT" --phase confirmation
python -u experiment62_multistep_solvable_search/audit_experiment62.py \
  --artifact-root "$EXP62_ROOT" --phase confirmation
python -u experiment62_multistep_solvable_search/export_experiment62.py \
  --artifact-root "$EXP62_ROOT"
```

Progress checks:

```bash
jq '{phase,completed_jobs,planned_jobs,operational_failures,solved_jobs,multistep_solved_jobs,tactic_invocations,complete}' \
  "$EXP62_ROOT/pilot/execution/progress.json"
jq '{phase,completed_jobs,planned_jobs,operational_failures,solved_jobs,multistep_solved_jobs,tactic_invocations,complete}' \
  "$EXP62_ROOT/confirmation/execution/progress.json"
tail -n 40 "$EXP62_ROOT/logs/confirmation.log"
```
