# External hard-root four-policy confirmation

This directory contains the frozen execution, post-execution amendment,
analysis, audit, and export code for the 64-root confirmation over miniF2F and
PutnamBench. Historical internal identifiers are retained in filenames for
receipt compatibility.

The four registered policies are full expansion, effect-aware selection,
syntax-head deduplication, and fixed-budget random pruning. The primary
efficiency estimand is the paired difference in actual Lean process calls per
root between full and effect-aware execution. Coverage is a separate estimand.

The immutable result bundle is distributed through the versioned Zenodo record,
not GitHub. Its SHA-256 is
`50c5df747c206fac992c38f9e7e741cfff03b9e655fa16566a30996dc313a2e3`.

The final Fix1 analysis retains three identical Lean internal-panic cells on
one frozen root. It executes no Lean, rewrites no original receipt, performs no
retry, and makes no imputation. Consequently:

- actual process-call efficiency is evaluated on all 64 frozen roots;
- registered 64-root coverage remains inconclusive;
- the 63-root complete-case result is sensitivity analysis only; and
- the exact decision label is
  `actual_call_efficiency_confirmed_coverage_inconclusive_due_locked_operational_anomaly`.

For server execution and the protected amendment order, follow
`README_SERVER.md` and `README_FIX1_SERVER.md`. For clean-download verification,
use the Zenodo release's `portable_audit/portable_audit.py` entry point.
