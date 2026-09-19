# Exp59 confirmation operational-anomaly amendment Fix1

## Scope

This post-execution amendment retains three completed confirmation cells that
ended with the same deterministic Lean 4.27.0 internal panic:

```text
INTERNAL PANIC: Nat.pow exponent is too big
```

All three cells belong to one frozen miniF2F root, one `simp_all` candidate
branch, and the `omega` continuation probe. The affected policies are `full`,
`effect_aware`, and `head_dedup`. The fixed-budget random policy did not select
that branch. Candidate-only controls for all three affected jobs reconstructed
successfully and produced the same frozen candidate endpoint.

## Frozen disposition

- Preserve every original job, input, cell receipt, hash, process-call count,
  and panic message unchanged.
- Do not rerun, replace, delete, or manually reconcile the affected cells.
- Do not recode an internal panic as an ordinary tactic failure.
- Retain all 64 roots for the actual process-call efficiency estimand because
  every launched process remains an observed call.
- Mark the affected root unevaluable for solved-root coverage and strict
  endpoint preservation. Report complete-case 63-root values only as an
  explicitly nonregistered sensitivity analysis.
- Keep the registered 64-root coverage gate and the registered joint gate
  false/inconclusive.

This amendment executes no Lean code and changes no scientific execution
plan. It only separates an observed operational anomaly from the efficiency
and coverage estimands before any confirmation analysis is produced.
