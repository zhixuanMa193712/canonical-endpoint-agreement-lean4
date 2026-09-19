# Prospective Exp59 four-policy pilot amendment

This amendment is applied only after the expansion-only candidate screen has
completed and before any continuation probe. The protected screen contains 658
operational roots, 459 eligible roots, and a balanced deterministic pilot of 32
roots (16 miniF2F and 16 PutnamBench roots).

Each root is evaluated under four frozen policies: full expansion,
strict-effect-aware deduplication, tactic-head deduplication, and fixed-budget
random pruning. Every policy independently reconstructs all 21 one-step
candidates in fresh Lean processes. It then executes the same ordered panel of
eight continuation probes on the branches selected without downstream outcome
information. Search stops at the first terminal strict endpoint or the common
root-policy elapsed-process-time budget.

The primary efficiency estimand is the paired full-minus-effect-aware number of
actual fresh Lean process calls per root. Coverage is a distinct estimand: the
fraction of roots solved by full expansion but not by effect-aware expansion,
with a registered 0.05 noninferiority margin. Wall-clock is descriptive only.
The pilot is planning evidence, not confirmation evidence. A balanced,
disjoint confirmation set may be frozen only after an immutable execution,
offline analysis, independent reconstruction audit, and prospectively locked
power simulation.

No confirmation execution runner is included in this package. If no tested
sample size up to 128 roots reaches the registered joint planning probability,
the workflow stops and requires a prospective amendment.
