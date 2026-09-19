# External hard-root efficiency confirmation preregistration

## Question and claim boundary

This prospective study asks whether strict-endpoint effect-aware branch deduplication reduces **actual** Lean process calls and expanded depth-two nodes on external hard theorem-proving benchmarks. It does not treat the planned frontier size as an observed saving. It does not claim global tactic interchangeability, arbitrary continuation equivalence, learning improvement, or a general theorem-prover speedup.

The independent unit is the theorem root. The four policies are paired within each root. Dataset is a prespecified stratum, not a replicate.

## External sources

Two exact upstream snapshots are frozen before candidate execution:

- Google DeepMind miniF2F, commit `f0a20e14c1eeccd859d51bb4c2b3ee487889c303`, Lean `v4.27.0`, Apache-2.0. The official `Valid.lean` split is pilot-only and `Test.lean` is confirmation-only.
- PutnamBench, commit `34eba93650f2fa803ca6aae6dfd2c9f22d46c00d`, Lean4 subtree, Lean `v4.27.0`, Apache-2.0. A deterministic SHA-256 partition assigns one quarter of sources to pilot and the remainder to confirmation before any tactic runs.

PutnamBench explicitly asks researchers not to publish proofs. Accordingly, public artifacts may contain source identities, counts, hashes, exclusions, and aggregate estimates, but must not contain target-to-successful-tactic mappings, generated proof scripts, or raw successful rows without written maintainer approval.

## Candidate-only screening

The complete proof-hole ledger is created first; miniF2F declarations that already contain authored proofs are counted as source-census exclusions and never enter the target frame. A deterministic screening frame contains 64 pilot and 192 confirmation candidates per dataset (512 roots total). The candidate order is the exact 23-candidate order frozen in the immutable four-policy benchmark. Candidate screening executes no downstream probe.

A root is eligible only if all of the following hold:

1. exact source, commit, toolchain, generated-worker, and measurement-source hashes pass;
2. all 23 candidate outcomes are accounted for from one candidate-only Lean process;
3. the pre-state has exactly one goal and all candidate branches share the same pre-state;
4. no candidate is terminal;
5. at least four candidates execute and remain nonterminal; and
6. at least one strict structural endpoint class contains two or more candidates.

The no-terminal rule directly addresses the earlier benchmark failure mode in which the common candidate stage solved almost every root before any policy-specific depth-two work occurred.

## Pilot and sample-size planning

Exactly 16 eligible pilot roots per dataset are selected by a frozen hash key. No manual replacement is permitted. A later, separately audited execution package will run all four policies on these 32 roots.

The pilot is used only for engineering feasibility and sample-size planning. It is not pooled with the confirmation estimate. Candidate confirmation roots remain unexecuted while planning occurs.

For each candidate total confirmation size in `48, 64, 80, 96, 112, 128`, a deterministic stratified empirical simulation resamples roots within each dataset. The smallest balanced size is selected only if both operating-characteristic estimates are at least 0.90:

- the one-sided 95% lower bound for mean paired call saving is greater than zero; and
- the one-sided 95% Wilson upper bound for paired coverage loss is at most 0.05.

If no grid value passes, the experiment stops. Any larger design must be prospectively amended before confirmation execution.

## Policies and common execution rules

The policies are full expansion, strict-endpoint effect-aware deduplication, tactic-head deduplication, and deterministic fixed-budget random pruning. All policies receive the identical ordered 23-candidate stage. Policy selection uses candidate-stage metadata only. All receive the same ordered eight-probe panel, per-cell timeout, root-policy time budget, and stop-at-first-proof rule. Every scientific cell is attempted once in a fresh Lean process; failures and timeouts remain in the denominator.

## Estimands

The primary efficiency estimand is the root-level paired difference

`full Lean process calls - effect-aware Lean process calls`.

Expanded-node difference, wall-clock, and time-to-first-proof are secondary. Wall-clock is descriptive because scheduling noise is not independently replicated.

Coverage is a separate non-inferiority estimand. Its loss event is “full solves within budget and effect-aware does not.” The one-sided margin is 0.05. A positive call-saving result does not imply coverage preservation, and coverage preservation does not imply a call-saving result.

## Fail-closed decisions

All ineligible roots and failure reasons remain in the eligibility ledger. The study stops on an incomplete source frame, failed build or worker preflight, missing candidate receipt, insufficient eligible pilot/confirmation pools, failed pilot integrity, insufficient power, or any confirmation probe executed before the final freeze. Historical inconclusive and coverage-loss decisions are never overwritten.
