# Experiment 54 mechanical execution amendment Fix1

## Status and timing

This amendment was written after the first 896-cell execution failed its
execution-integrity gate and before any Fix1 scientific cell was executed. The
failed v1 execution is retained in full. It is not analyzed as scientific
evidence and is not replaced or edited.

## Frozen scientific content

Fix1 carries forward the v1 repositories, commits, 16 roots, 16 witness pairs,
16 control pairs, representative rule, eight probes, full policy, deduplicated
policy, 896-cell plan, endpoint abstractions, estimands, analysis rules, and
decision rules exactly. The freeze verifies byte-exact equality of all target,
pair, and cell records against v1.

## Mechanical failures in v1

The v1 execution recorded all 896 planned cells but failed integrity:

- 529 candidate endpoint checks differed only in the derived `text48` hash;
  their raw and strict endpoint hashes and Lean checkpoint comparisons agreed.
  Exp54 had not copied the frozen Exp49 whitespace and generated-identifier
  normalizer exactly.
- Seven Python workers attempted `int(None)` after Lean returned a
  non-executable candidate record. The raw records were retained.
- Those seven raw records showed a 200,000-heartbeat candidate timeout before
  `solve_by_elim` was attempted, while the same candidate checkpoints were
  reconstructed for the other seven probes. `ContextInfo.runMetaM` had restored
  target-command options instead of the 2,000,000-heartbeat option declared by
  the generated worker.

## Fix scope

Fix1 makes only the following code changes:

1. It uses the exact Exp49 `text48` normalizer.
2. It installs `maxHeartbeats = 2,000,000` in the live `ContextInfo` used for
   counterfactual execution.
3. It calls `withCurrHeartbeats` immediately before the downstream probe, so
   candidate reconstruction and probe execution have isolated budgets.
4. It records null/non-executable candidate results fail-closed without a
   Python exception.

Fix1 performs a complete new 896-cell execution. It does not rerun only failed
cells, borrow sibling outcomes, impute results, reconcile rows manually, or use
v1 downstream outcomes for selection.

## Claim boundary

The amended microbenchmark remains limited to depth-2 execution on the frozen
sample. It can measure downstream-call reduction and preservation or loss of
the registered probe outcomes. It cannot establish global tactic
interchangeability, arbitrary continuation equivalence, learning improvement,
or general theorem-proving improvement.
