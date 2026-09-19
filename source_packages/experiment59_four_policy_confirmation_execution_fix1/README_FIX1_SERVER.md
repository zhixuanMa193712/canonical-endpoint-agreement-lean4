# Exp59 confirmation Fix1: offline server commands

This package is used **after** all 64 confirmation shards and 256 policy jobs
have completed. It executes no Lean process and does not rewrite any original
receipt. It accepts only the three exact, hash-locked Lean internal-panic cells
recorded by the package.

```bash
cd /home/music/mzz/MZX
unzip -o experiment59_four_policy_confirmation_execution_fix1_python_only.zip
export MZX_ROOT=/home/music/mzz/MZX

python \
  experiment59_four_policy_confirmation_execution_fix1/test_experiment59_confirmation_fix1_static.py

python \
  experiment59_four_policy_confirmation_execution_fix1/freeze_operational_anomaly_fix1.py

python \
  experiment59_four_policy_confirmation_execution_fix1/finalize_experiment59_confirmation_fix1.py

python \
  experiment59_four_policy_confirmation_execution_fix1/analyze_experiment59_confirmation_fix1.py

python \
  experiment59_four_policy_confirmation_execution_fix1/audit_experiment59_confirmation_fix1.py

python \
  experiment59_four_policy_confirmation_execution_fix1/export_experiment59_confirmation_fix1.py
```

Required interpretation of the final output:

- `locked_operational_anomaly_cells` must equal 3;
- `coverage_unevaluable_roots` must equal 1;
- `efficiency_evaluable_roots` must equal 64;
- `coverage_evaluable_roots` must equal 63;
- `registered_coverage_gate` and `registered_joint_gate` must remain false;
- the complete-case coverage result is sensitivity analysis, not a replacement
  for the registered 64-root coverage estimand;
- `scientific_retry_count` and `manual_reconciliation_count` must remain zero.

The immutable result archive is written to:

```text
exports/experiment59_four_policy_confirmation_fix1_results.zip
```
