# Experiment 54 mechanical execution amendment Fix3

## Status and timing

This amendment was written after Fix2 completed all 896 cells but failed its
execution-integrity gate, and before any Fix3 scientific cell was executed.
The original v1, Fix1, and Fix2 executions remain immutable failed executions.

## Frozen scientific content

Fix3 carries forward byte-exact target, pair, and cell plans from v1, Fix1,
and Fix2: the same four repositories and commits, 16 roots, 16 witness pairs,
16 control pairs, representative rule, eight probes, 512 full cells, 384
deduplicated cells, endpoint abstractions, estimands, analysis rules, and
decision rules.

## Mechanical failure isolated in Fix2

Fix2 avoided forcing lazy exception text after heartbeat exhaustion, but the
same seven `solve_by_elim` cells were still classified as candidate
reconstruction failures. Lean 4.27 deliberately lets resource-limit
exceptions escape ordinary `try/catch` in `CoreM`-based monads. The probe
handler used ordinary `try/catch`; consequently, a probe heartbeat exception
escaped to the outer candidate handler even though no lazy message was forced.

Lean 4.27 exposes `tryCatchRuntimeEx` specifically for the exceptional cases
where resource-limit exceptions must be converted into regular recorded
failures. Lean's own tactic infrastructure uses this boundary when running a
tactic under a fresh heartbeat budget.

## Fix scope

Fix3 changes only the downstream-probe exception boundary. It wraps the
existing `withCurrHeartbeats` probe action in `tryCatchRuntimeEx` and records
the stable registered category `tactic_failure` using the constant message
`tactic execution failed`. It neither inspects nor renders the runtime
exception.

Fix3 does not raise the 2,000,000-heartbeat budget, change a tactic or probe,
change a checkpoint, inspect successful outcomes for selection, impute a row,
or rerun only the seven affected cells. It requires a complete new 896-cell
execution.

## Claim boundary

The amended study remains a small frozen depth-2 microbenchmark. It can support
only claims about registered downstream-call reduction and preservation or
loss of registered probe outcomes on this sample. It cannot establish global
tactic interchangeability, arbitrary continuation equivalence, learning
improvement, or general theorem-proving improvement.
