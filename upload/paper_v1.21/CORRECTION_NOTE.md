# Lexical-head correction (v1.21, 18 September 2026)

This note summarizes in English the post-outcome analysis correction recorded in
the Chinese `REVISION_NOTES.md` in this directory. It changes no execution record.

## Defect

The external-study implementation of the lexical tactic-head rule used an
over-escaped regular-expression character class that split on the literal letter
`s` instead of whitespace. It mapped `simp`, `simpa`, `simp_all` and
`solve_by_elim` to `<empty>`, and both `aesop` and `aesop?` to `ae`. Pairs within
these groups were therefore treated as having the same head and were excluded
by the cross-head witness predicate. The original deterministic audit reproduced
the archived labels and could not detect the defect in the rule itself. The
four-repository confirmation and the multistep protocol use the correctly
escaped head rule.

## Correction

`reanalyze_heads.py` reads the complete tactic text and structural-endpoint
hashes from the scientific receipts in the original external-study archives.
It first reconstructs every archived root indicator and checks it against the
archived analysis, then derives heads and descriptive families from the stored
tactic text and recomputes the cross-head witnesses. A direct pairwise predicate
cross-checks the endpoint-group implementation. Smoke receipts are excluded.

Candidate programs, their order, execution statuses, structural endpoints and
sampled roots are unchanged, and no Lean process is run. Intervals are recomputed
with the same two-level repository/root resampling design, 20,000 replicates,
NumPy PCG64 seed 20260918 and linear percentiles.

## Effect

| Quantity | Archived (v1.20) | Corrected (v1.21) |
| --- | ---: | ---: |
| 32-repository frame, full-panel positive roots | 277/512 (54.10%) | 355/512 (69.34%) |
| 32-repository frame, positive roots after genealogy deduplication | 141/512 (27.54%) | unchanged |
| 32-repository frame, nonterminal positive roots | 217/512 | 298/512 |
| 32-repository frame, distinct cross-head pairs / recurring in at least two repositories | 69 / 44 | 124 / 87 |
| 12-repository frame, full-panel positive roots | 259/576 (44.97%) | 350/576 (60.76%) |
| 12-repository frame, positive roots after genealogy deduplication | 142/576 (24.65%) | unchanged |

This is a disclosed post-outcome correction, not a new prospective analysis, and
the higher corrected values are not presented as independent support. Archived
decision labels are unchanged; the initial 12-repository frame keeps its
`inconclusive` label because its prespecified precision criterion is not met
before or after the correction.

The corrected rows and summaries in `analysis/`, together with the source-file
cluster sensitivity analysis of the multistep study, are reproduced by
`reproduce_correction.py` at the repository root. The original archives must
accompany this correction layer and are not modified by it.
