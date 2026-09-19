# Experiment 62 preregistration

Experiment 62 is a prospective, paired, witness-injected evaluation of four
branch-selection policies during real multi-step LeanDojo proof search.  It is
designed to answer the narrow question left unresolved by Experiments 57 and
59: when candidate acquisition is deliberately made non-limiting, can
effect-aware branch selection reduce verified search work without losing
multi-step theorem solutions?

The source population is the 2,000-theorem `random/test` split of LeanDojo
Benchmark 4 at mathlib commit
`29dcec074de168ac2bf835a77ef68bbe069194c5`.  Experiment 39 used
`random/train`, so its 600 formal and eight smoke roots do not overlap this
split.  Before any Exp62 Lean execution, the source trace is converted to a
directed state-transition graph.  The shortest recorded path from the initial
state to `no goals` must contain two to six tactic invocations and may not use
`sorry` or `admit`.

The frozen frame contains separate pilot and confirmation roles and two depth
strata.  Live qualification replays the authored witness in Lean and excludes
any root closed by one candidate-panel invocation.  Qualification executes no
scientific search policy.  Sixteen qualified pilot roots are then evaluated.
Confirmation is allowed only if every pilot root has all four evaluable policy
outcomes and full search solves at least 12 roots with at least two external
tactic invocations.  No budget, action panel, threshold, or sample size may be
changed after pilot access.

The untouched confirmation contains 64 roots: 32 with a two-step authored
witness and 32 with a three-to-six-step witness.  Within each root the four
policies run sequentially in a frozen target-specific cyclic order:

- `full` retains every successful nonterminal candidate branch;
- `effect_aware` retains the first branch per `text48_v1` endpoint;
- `head_dedup` retains the first branch per tactic head;
- `fixed_budget_random` retains a deterministic random subset with the same
  size as the effect-aware subset.

All policies execute the same candidate panel at each expanded node.  The
registered next authored tactic is placed at rank four whenever the live
endpoint matches a qualified witness endpoint.  This disclosure is deliberate:
the experiment evaluates search control under known action support, not tactic
generation or theorem-prover generalization.

The independent unit is the theorem root.  Primary outputs are policy solve
rate, multi-step solve rate, effect-aware coverage loss relative to full, and
paired full-minus-effect-aware actual Lean tactic invocations.  Confirmation
requires at least 48 full-policy multi-step solves for an informative coverage
test.  The coverage loss fraction uses a one-sided 95% Wilson upper bound and a
0.05 noninferiority margin.  Every operationally incomplete full/effect-aware
pair is conservatively imputed as one loss.  Efficiency requires at least 60
complete pairs and a positive one-sided 95% lower bound for mean tactic-call
saving.  Expanded nodes, endpoint coverage, time-to-first-proof, and wall-clock
are secondary; wall-clock is descriptive.

This experiment does not test autonomous tactic proposal, learned model
generalization, proof-term identity, or semantic state identity.  Its endpoint
key is the registered text-normalized observation, not Lean kernel equality.
