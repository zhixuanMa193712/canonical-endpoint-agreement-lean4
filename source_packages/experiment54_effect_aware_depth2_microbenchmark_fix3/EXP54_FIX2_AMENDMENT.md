# Experiment 54 mechanical execution amendment Fix2

## Status and timing

This amendment was written after Fix1 completed all 896 cells but failed its
execution-integrity gate, and before any Fix2 scientific cell was executed.
Both the original v1 execution and Fix1 remain immutable failed executions.

## Frozen scientific content

Fix2 carries forward byte-exact target, pair, and cell plans from v1 and Fix1:
the same repositories, commits, 16 roots, 16 witness pairs, 16 control pairs,
representative rule, eight probes, 512 full cells, 384 deduplicated cells,
endpoint abstractions, estimands, analysis rules, and decision rules.

## Mechanical failure isolated in Fix1

Fix1 corrected endpoint normalization, null-result handling, and live-context
heartbeat options. It produced 889 valid rows and seven structured candidate
reconstruction failures. All seven occurred for the `solve_by_elim` probe on
one repository, despite involving three distinct candidate tactics (`aesop`,
`aesop?`, and `constructor`) whose checkpoints reconstructed under the other
seven probes.

The probe ran under an isolated heartbeat budget. When it exhausted that
budget, the catch handler forced `Exception.toMessageData.toString`. The lazy
message required elaborator context and heartbeat work after the budget was
already exhausted, so exception rendering raised a second timeout. That second
exception escaped to the outer candidate handler and replaced the real probe
failure with a candidate failure record.

## Fix scope

Fix2 changes one Lean exception-recording site. The downstream-probe catch no
longer forces lazy exception text. It records the stable registered category
`tactic_failure` using the constant message `tactic execution failed`.
Exception text and internal tactic traces are not estimands in this study.

Fix2 does not raise the frozen heartbeat budget, change a tactic or probe,
change a checkpoint, inspect successful outcomes for selection, impute a row,
or rerun only the seven affected cells. It performs a complete new 896-cell
execution.

## Claim boundary

The amended study remains a small depth-2 microbenchmark. It can support only
claims about registered downstream-call reduction and preservation or loss of
registered probe outcomes on the frozen sample. It cannot support global tactic
interchangeability, arbitrary continuation equivalence, learning improvement,
or general theorem-proving improvement.
