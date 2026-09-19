# Experiment 64: strict v4.27 external replication

This package performs the scientific follow-up to Experiment 63. It freezes all
32 independent lineage representatives, selects exactly 16 previously authored-
replay-qualified roots per repository, and evaluates the same 23-candidate panel
on every root. The resulting 512-root frame requests 11,776 candidate tactic
invocations.

The primary estimate is the equal-weight mean of repository-specific Y-L0 root
frequencies. The analysis reports the observed estimate, a named two-level
nonparametric bootstrap interval, the repository-rate distribution, leave-one-
repository-out values, and frozen-frame worst-case missingness bounds. It does
not use the historical 38-repository recruitment target as a scientific gate.

## Run

From `/home/music/mzz/MZX`, unzip the delivery archive and run:

```bash
bash experiment64_strict_v427_external_replication/run_experiment64_server_safe.sh
```

The launcher uses `nohup`, writes a PID and a pipeline log, and returns control to
the shell. It is safe to close SSH after `EXP64_STARTED` is printed. Re-running
the same command resumes completed repository and theorem receipts rather than
repeating them.

Before any scientific root is evaluated, an operational repository failure is
retried once under a fixed two-attempt rule. Scientific outcomes never trigger
repository replacement or selective rerunning; completed theorem receipts are
immutable and reused after an interruption.

Only an exact, newly created LeanDojo cache for the currently completed Exp64
repository is removed. A cache that existed before that repository began is
retained. No broad cache glob and no path outside the Exp64 checkout root or the
exact LeanDojo cache candidates is deleted.

## Monitor

```bash
cd /home/music/mzz/MZX
export EXP64_ROOT=/home/music/mzz/MZX/artifacts/v64/strict_v427_external_replication

echo "===== TIME AND PROCESS ====="
date
pgrep -af '[r]un_experiment64_pipeline.py|[l]ake build|[l]ake env lean' \
  || echo "EXP64_PROCESS_NOT_FOUND"

echo "===== PROGRESS ====="
if [ -s "$EXP64_ROOT/execution/progress.json" ]; then
  jq '{
    frozen_repositories,
    completed_repositories,
    scientific_execution_complete_repositories,
    operational_repository_failures,
    frozen_roots,
    roots_with_worker_receipts,
    evaluable_roots,
    candidate_invocations_requested,
    candidate_invocations_recorded,
    remaining_repositories,
    disk_free_gib: (.disk_free_bytes / 1073741824),
    stopping_reason
  }' "$EXP64_ROOT/execution/progress.json"
else
  echo "FREEZE_OR_FIRST_REPOSITORY_STILL_RUNNING"
fi

echo "===== LATEST LOG ====="
tail -n 40 "$EXP64_ROOT/logs/pipeline.log" 2>/dev/null || true

echo "===== FINAL ANALYSIS/AUDIT ====="
if [ -s "$EXP64_ROOT/analysis/summary.json" ]; then
  jq '{
    repositories,
    frozen_roots,
    evaluable_roots,
    primary,
    mechanism_diverse_sensitivity,
    integrity_passed
  }' "$EXP64_ROOT/analysis/summary.json"
else
  echo "ANALYSIS_NOT_CREATED"
fi
if [ -s "$EXP64_ROOT/audit/audit.json" ]; then
  jq '{audit_passed, repositories_reconstructed, roots_reconstructed, checks}' \
    "$EXP64_ROOT/audit/audit.json"
else
  echo "AUDIT_NOT_CREATED"
fi

echo "===== DISK AND EXPORT ====="
df -h /home/music/mzz/MZX
ls -lh /home/music/mzz/MZX/exports/experiment64_strict_v427_external_replication_results.zip* \
  2>/dev/null || echo "EXPORT_NOT_CREATED"
```

## Interpretation boundary

The result describes immediate candidate-relative endpoint agreement in this
strict, current-commit Lean-v4.27 frame. It is not an ecosystem-wide prevalence
estimate and it does not establish whole-proof tactic equivalence.
