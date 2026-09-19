# Effect-aware depth-2 search microbenchmark preregistration

## Question

Under a frozen two-step Lean execution protocol, does pruning one member of a
same-strict-endpoint cross-head pair reduce downstream branch executions while
preserving the observed downstream outcome set for a fixed probe panel?

The experiment evaluates a bounded candidate-selection mechanism. It does not
test global tactic interchangeability, arbitrary continuations, proof-term
equality, learning performance, or general theorem-proving improvement.

## Frozen sample

The source is the immutable Experiment 49 archive. The frame contains the four
untouched confirmation repositories. A root is eligible when it is an evaluable
single-goal root with both:

1. a noninitial, nonterminal, cross-head pair whose strict endpoints agree; and
2. a noninitial, nonterminal, cross-head pair whose strict endpoints differ.

To keep the microbenchmark portable, source theorem records above 20 MiB are
excluded before any downstream execution. Within each repository, eligible
roots are ordered by archive-member bytes and then theorem identifier. The first
four are retained. Within each root, pair choice and representative choice use
only frozen depth-1 endpoint identities and candidate positions. No downstream
probe outcome enters selection.

The frozen sample therefore contains 16 roots, 16 witness pairs, and 16
within-root control pairs. Repository is a design block. The candidate pair is
the independent unit; the eight probes are repeated measurements.

## Policies

- **Full:** expand both members of every witness and control pair.
- **Effect-aware dedup:** expand the frozen representative of each witness pair,
  while retaining both members of each different-endpoint control pair.

Both policies are executed separately. Every cell launches one fresh Python
worker and one fresh Lean process, has attempt ordinal one, and permits no
scientific retry or manual reconciliation. Depth-1 candidate execution is not
reduced; only depth-2 expansion is evaluated.

## Probe panel

The ordered probe panel is `rfl`, `assumption`, `simp`, `simp_all`, `omega`,
`constructor`, `intro`, and `solve_by_elim`. Each probe is executed after an
exact reconstruction check against the archived raw and strict candidate
endpoint.

The full policy has 512 planned Lean calls. The dedup policy has 384, for a
preregistered reduction of 128 calls (25% overall and 50% within witness pairs).

## Primary estimands and decision

The primary efficiency estimand is the exact number and fraction of downstream
Lean calls removed. Preservation requires all of the following:

- exact outcome agreement between full and dedup reruns for every retained cell;
- exact left/right outcome agreement for every witness-pair probe;
- equality of the full and dedup per-pair/probe outcome sets;
- equality of the successful strict-endpoint union; and
- complete, fresh-process, no-retry execution with zero manual reconciliation.

An outcome includes success/failure status, failure category, and, on success,
raw, normalized-text, and strict endpoint hashes, goal count, and terminality.
The decision is `effect_aware_depth2_supported` only if every integrity,
efficiency, and preservation gate passes. A completed run with any preservation
mismatch is `coverage_loss_detected`; an invalid or incomplete run is
`effect_aware_depth2_inconclusive`.

No null-hypothesis p-value is used. If zero witness pairs show any mismatch, the
analysis reports the one-sided exact 95% upper bound for a pair-level mismatch
rate. Probe-cell counts remain descriptive because probes within a pair are not
independent replicates.

## Secondary descriptive quantity

Successful strict endpoints per 100 executed depth-2 calls are reported as a
descriptive yield measure. It is not interpreted as global tactic diversity or
as evidence of a better prover.

