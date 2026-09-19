# Prospective expansion-only hard-root efficiency confirmation

## Status and separation from the preceding screen

The preceding 512-root screen is frozen as `candidate_panel_recruitment_no_go`. Its registered 23-entry panel mixed ordinary expansion operators with two entries that the pre-existing Exp49 genealogy classified as `direct_suggestion`: `aesop?` and `exact?`. The observed suggestion-exclusion counts are retained only as a design diagnostic and do not change that decision.

This experiment uses every source root not executed by the preceding screen. The 658-root frame, its role assignment, the 21-entry candidate order, eligibility gates, selection keys, and minimum counts are frozen before any candidate execution on these roots. No preceding target can enter this frame.

## Frozen source frame

- miniF2F: 242 unused roots; 64 prospective pilot-recruitment roots and 178 prospective confirmation-recruitment roots.
- PutnamBench: 416 unused roots; 64 prospective pilot-recruitment roots and 352 prospective confirmation-recruitment roots.
- Assignment within each dataset is a deterministic hash order. The first 64 are pilot-recruitment roots; all remaining roots are confirmation-recruitment roots.
- No manual replacement is permitted.

## Frozen candidate-only screen

The panel preserves the preceding order after deleting exactly `aesop?` and `exact?`. A root is eligible only when:

1. the worker reconstructs exactly one pre-state and accounts for all 21 candidates;
2. no candidate terminates the theorem;
3. at least four candidates execute to nonterminal states; and
4. at least one strict-endpoint equivalence class contains at least two candidates.

Candidate screening executes no continuation probe. A timeout or worker failure is retained with attempt ordinal one and is never retried. Recruitment requires at least 16 eligible pilot roots and 64 eligible confirmation roots in each dataset. These quotas cannot be lowered after execution.

## Future pilot and confirmation boundary

If recruitment passes, a later code package will freeze four policy jobs on the first 16 eligible pilot roots in each dataset under the registered selection key. Only that pilot may inform confirmation sample-size planning. The primary efficiency estimand will remain the paired reduction in actual Lean process calls for full expansion versus effect-aware deduplication. Coverage preservation is a separate estimand. `aesop?` and `exact?` may be evaluated only as meta-search baselines whose wall-clock and internal search costs are reported; they are not ordinary one-call branches.

If recruitment fails, the run stops as a prospective recruitment No-Go. No root-level retry, manual replacement, quota reduction, or reuse of preceding-screen candidate outcomes is permitted.
