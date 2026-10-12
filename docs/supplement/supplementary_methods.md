# Supplementary Methods

## S1. Study map and frozen protocols

The supplementary evidence is organized by scientific role. The untouched-repository confirmation establishes recurrence; candidate and endpoint comparisons characterize the measurement; external frames test its recurrence under other repository selections; and branch-selection studies measure downstream consequences. The table provides a thematic reading order across the methods and results.

| Research theme | Study and purpose | Sections |
|---|---|---|
| Recurrence | Untouched-repository confirmation and cross-repository pair frequencies | S2–S5; Table S3 |
| Measurement sensitivity | Candidate ablations, endpoint definitions, and canonicalizer disagreement | S3–S4, S6, S8–S9 |
| External recurrence | Initial screened frame and strict current-v4.27 frame | S2, S7, S11, S20 |
| Reproducibility | Same-server execution, second-machine subset, and offline reconstruction | S10, S13, S15–S16 |
| Branch selection | Bounded continuation, local pruning, hard-root resource accounting, and oracle-assisted multi-step search | S7, S12, S14, S17, S19 |
| Interpretation and reuse | Scope, claim-to-evidence map, artifact identities, and reproduction instructions | S18 and the closing reference sections |

Each study is presented using its final analysis configuration and complete result set. Software repair histories and superseded execution records remain in the immutable source archives, rather than being repeated as separate experiments here. The Artifact Manifest maps scientific roles to original archive identifiers and checksums; those identifiers are storage labels, not the reading sequence.

Repository commits, targets, candidate rules, endpoint schemas, and analysis specifications were locally frozen before the corresponding scientific execution. This is a prespecified or pre-outcome-frozen design, not a claim of public preregistration. Original protocol fields and amendment records remain available for chronological verification. The untouched-repository confirmation remains the primary independent confirmation sample; robustness and extension studies do not replace it.

## S2. Root provenance

### Untouched-repository confirmation

The confirmation repositories and their archived eligible-frame sizes are:

| Repository | Eligible formal roots in inherited frame | Frozen roots | Selected-file SHA-256 |
|---|---:|---:|---|
| `fpvandoorn/carleson` | 653 | 24 | `d5b9cc9124d3f79fef03ed45523f84cf64f8e16f397ed81cb94f575733149af2` |
| `ImperialCollegeLondon/FLT` | 318 | 24 | `0cb5f8c77b7f3a0a09efa9e055515ab2e5b19c28562f90245de5c00a33f5f75b` |
| `thefundamentaltheor3m/Sphere-Packing-Lean` | 394 | 24 | `0ae2e381147646fdf13064e3749ac34c5b865c5c8da16ae87a6c9b86afea14da` |
| `RemyDegenne/brownian-motion` | 167 | 24 | `92f49415078b81dcd69d02a82ef3a3e8e48552ee5005a9ae507dd8f2fd168ede` |

Each theorem row stores repository commit, source-file hash, theorem identity, statement hash, source span, trace-root state and hash, selected-file hash, and a deterministic `selection_rank`. The confirmation freeze validates exactly 24 formal roots in each selected file and prohibits post-freeze replacement. The compact Mac bundle does not ship the complete inherited preselection ledgers, so an auditor can reconstruct and validate the selected set but cannot independently regenerate every eligible-to-selected rank from that bundle alone. This is an artifact-provenance limitation, not an outcome-dependent exclusion: all 96 frozen confirmation roots were attempted and evaluable.

The independent confirmation audit matched all 220 manifest-listed payload files by size and SHA-256 and reconstructed 198 theorem rows: six smoke rows, 96 discovery rows, and 96 confirmation rows. Only the last 96 rows form the primary confirmation sample. The other 102 document development and discovery. The audit reproduced all repository rates, summaries, intervals, and pair counts without manual reconciliation.

### Initial screened external frame

After zero-candidate build/trace, authored-replay, and lineage qualification, the initial external-frame study sampled 48 roots from each selected repository by simple random sampling without replacement, using master seed `510051`. The frozen target file contains 576 rows and its SHA-256 is `723957673a2ebd7964afcfdb0be759168e76903f76f47ae970586a0cce5d14b7`.

### Strict current-v4.27 external frame

The strict recruitment stage froze 52 repositories from a complete current-commit candidate frame. Qualification completed all 52 receipts: 33 repositories passed, four were definitively ineligible, and 15 remained operationally unresolved. Lineage analysis retained 32 lineage-deduplicated representatives. This label records a documented heuristic screen for forks, mirrors, shared snapshots, benchmark repackagings, multiple project commits, and high source overlap; it does not assert statistical independence. The recruitment audit passed all frame, current-commit, exact-toolchain, static-minimum, receipt-partition, resource-contract, and zero-scientific-tactic checks. The historical target of 38 repositories was a recruitment design goal; it is retained in the archive but is not used as a scientific validity threshold.

Every strict-frame representative had a current default-branch commit, exact root toolchain `leanprover/lean4:v4.27.0`, a root Lake project and licence, at least 16 statically identified tactic roots, unchanged build and trace, and an exact zero-candidate authored replay. The complete set of 32 lineage representatives was frozen before scientific execution. For each repository, eligible roots were ordered by `SHA-256(seed || slug || theorem_id)` with seed `640064`, and the first 16 were retained. This produced 512 roots and 11,776 planned candidate invocations. The target ledger SHA-256 is `59bc4eca7b53b4f65abed0b7420abd7ce77af6f44aeb0cfb365ed93bff01434a`; the protocol SHA-256 is `b6746a999c7d646f520048cec33c80c21b5a81d4dccac84c6993354bc389dc40`.

## S3. Ordered candidate source library and genealogy

The ordered library contains 32 source programs. A root-specific deterministic rule removes the exact authored command and retains the first 23 remaining programs. The number 23 is the alternative budget inherited from the pre-outcome protocol; together with authored replay it gives 24 root-local executions. It was not selected by optimizing a witness rate, candidate-ablation result, or downstream outcome and has no claim to statistical or computational optimality. `Class` and `group` are frozen candidate-view ablation metadata; they are not execution semantics.

**Supplementary Table S2. Frozen ordered candidate source library and genealogy metadata.**

| Order | Program | Class | Genealogy group |
|---:|---|---|---|
| 1 | `rfl` | distinct entry | `rfl` |
| 2 | `assumption` | distinct entry | `assumption` |
| 3 | `trivial` | distinct entry | `trivial` |
| 4 | `contradiction` | distinct entry | `contradiction` |
| 5 | `simp` | shared core | `simp_engine` |
| 6 | `simpa` | shared core | `simp_engine` |
| 7 | `simp_all` | shared core | `simp_engine` |
| 8 | `aesop` | shared core | `aesop_engine` |
| 9 | `aesop?` | direct suggestion | `aesop_engine` |
| 10 | `norm_num` | distinct entry | `norm_num` |
| 11 | `omega` | distinct entry | `omega` |
| 12 | `linarith` | distinct entry | `linarith` |
| 13 | `nlinarith` | distinct entry | `nlinarith` |
| 14 | `ring` | shared core | `ring_engine` |
| 15 | `ring_nf` | shared core | `ring_engine` |
| 16 | `positivity` | distinct entry | `positivity` |
| 17 | `decide` | distinct entry | `decide` |
| 18 | `native_decide` | distinct entry | `native_decide` |
| 19 | `constructor` | distinct entry | `constructor` |
| 20 | `ext` | distinct entry | `ext` |
| 21 | `fun_prop` | distinct entry | `fun_prop` |
| 22 | `solve_by_elim` | distinct entry | `solve_by_elim` |
| 23 | `exact?` | direct suggestion | `exact_suggestion` |
| 24 | `apply_assumption` | distinct entry | `apply_assumption` |
| 25 | `tauto` | distinct entry | `tauto` |
| 26 | `left` | distinct entry | `left` |
| 27 | `right` | distinct entry | `right` |
| 28 | `intro` | shared core | `intro_engine` |
| 29 | `intros` | shared core | `intro_engine` |
| 30 | `all_goals simp` | direct control wrapper | `simp_engine` |
| 31 | `all_goals aesop` | direct control wrapper | `aesop_engine` |
| 32 | `first \| rfl \| assumption` | direct control wrapper | `first_rfl_assumption` |

The candidate-library SHA-256 is `9eea3b178d414ad93cbefadb96fb93f271a26bcb255a723f9d604996a679ad78`.

### Root-local panel reconstruction

The 96 immutable confirmation rows instantiate five distinct 23-program panels. Their frequencies are 85, 6, 3, 1, and 1. Repository-local frequency partitions are:

| Repository | Frequencies of distinct root-local panels |
|---|---|
| `fpvandoorn/carleson` | 19, 4, 1 |
| `ImperialCollegeLondon/FLT` | 21, 1, 1, 1 |
| `thefundamentaltheor3m/Sphere-Packing-Lean` | 22, 1, 1 |
| `RemyDegenne/brownian-motion` | 23, 1 |

The intersection of the five panels contains 19 programs: `aesop`, `aesop?`, `assumption`, `constructor`, `contradiction`, `exact?`, `fun_prop`, `linarith`, `native_decide`, `nlinarith`, `norm_num`, `omega`, `positivity`, `ring`, `ring_nf`, `simp_all`, `simpa`, `solve_by_elim`, and `trivial`. Their union contains 24 programs, adding `apply_assumption`, `decide`, `ext`, `rfl`, and `simp`. This reconstruction uses only frozen selection rows and changes no scientific execution or outcome.

### S3.1. Lexical head contract and external-label correction

The finite-library head rule strips surrounding whitespace and takes the first token before whitespace or `[`, `(`, `{`, `|`, or `;`. Question marks and underscores are retained. This is a lexical classifier, not a Lean AST parser or macro expander; inner commands are not substituted for the outer control head.

| Program | Lexical head | Genealogy treatment |
|---|---|---|
| `simp` / `simpa` / `simp_all` | `simp` / `simpa` / `simp_all` | Shared simplification engine |
| `aesop` / `aesop?` | `aesop` / `aesop?` | Shared Aesop engine; suggestion excluded in deduplicated view |
| `all_goals simp` | `all_goals` | Direct control wrapper; simplification genealogy |
| `all_goals aesop` | `all_goals` | Direct control wrapper; Aesop genealogy |
| `first \| rfl \| assumption` | `first` | Direct control wrapper |

The external-study implementation contained an over-escaped regular-expression character class: it split on literal `s` instead of whitespace, mapping `simp`, `simpa`, `simp_all`, and `solve_by_elim` to `<empty>` and both Aesop forms to `ae`. The v1.21 correction derives heads and descriptive families from the stored tactic text, then recomputes cross-head witnesses using the unchanged structural endpoint hashes. The four-repository and multi-step protocol functions use the correctly escaped head rule. External genealogy selection uses exact full-program dictionary entries and is unchanged. This is a disclosed post-outcome analysis correction, not a new prospective analysis or an execution rerun. Sections S11 and S20 report corrected external results. Source ZIPs and their hashes remain unchanged; the correction code, root rows, and summaries form an additional reproducibility layer that must accompany the public release.

## S4. Candidate views

| View | Frozen attack |
|---|---|
| `L0` | **Full panel:** root-specific 23-alternative historical panel |
| `L-no-question` | **No heads ending in ?:** exclude every parsed tactic head ending in `?` |
| `L-no-aesop` | **No `aesop`:** exclude the parsed head `aesop` only |
| `L-no-aesop-question` | **No `aesop?`:** exclude the parsed head `aesop?` only |
| `L-no-aesop-pair` | **No `aesop` + `aesop?`:** exclude both exact parsed heads |
| `L-no-direct-wrapper` | **No direct suggestions/control wrappers:** exclude the two frozen genealogy classes |
| `L-mechanism-diverse` | **After genealogy deduplication:** apply the direct-suggestion/control-wrapper exclusions and retain at most one entry per remaining genealogy group |

## S5. Live execution pipeline

1. Verify repository, commit, toolchain, source, configuration, and code identities. The configuration index `xi` includes Lean/toolchain version, repository commit and imports, options, heartbeat/timeout limits, process-isolation policy, runner/parser version, and canonicalizer version.
2. Elaborate unchanged source and locate exactly one frozen `TacticInfo` occurrence.
3. Recover `ContextInfo`, `mctxBefore`, and ordered `goalsBefore`; require one goal.
4. Replay exact authored syntax and require the recorded `mctxAfter` and `goalsAfter`.
5. Start every candidate from the same recovered pre-state in an independent `MetaM` branch.
6. Retain failure or serialize every prespecified endpoint.
7. Require complete candidate accounting before pair construction.
8. Derive root and repository summaries from immutable rows.
9. Independently reconstruct prespecified summaries and verify export manifests.

### External tracing and compatibility controls

External tracing used pinned LeanDojo 4.20.0 and hash-locked extractor and parser ledgers. Fail-closed in-memory adapters handled only the prespecified Lean-v4.27 position, section-header, and line-ending schemas, altering neither repository sources nor the installed package. Content-addressed trace reuse required exact commits, toolchains, source inventories, runtime identities, AST counts, and per-AST hashes. The corresponding archive manifests bind the extractor/parser ledgers and execution receipts. Qualification used authored replay with an empty scientific candidate list, so these checks did not expose candidate-policy outcomes.

## S6. Endpoint content

`text48` normalizes generated identifiers and horizontal whitespace in ordered rendered goals. The strict structural schema preserves expression ASTs, ordered goal declarations, complete ordered local declarations, binder information, let values, local-instance membership, universe structure, and reachable unassigned metavariable declarations under deterministic alpha-normalization. It excludes proof terms, timing, messages, and internal tactic traces. The same-root disagreement table demonstrates that these definitions are related but not identical.

### Same-server comparison fields

Re-execution comparisons use branch status, ordered raw state bytes, goal count, terminality, and the prespecified canonical endpoints. Runner-specific container schema labels are metadata rather than endpoint content. The final comparison checks these content fields without changing the underlying execution rows; its complete mode-by-mode results appear in Section S10.

## S7. Statistical reporting policy

- Untouched-confirmation and candidate-sensitivity intervals are archived repository-bootstrap percentile outputs over four observed repository rates. The manuscript calls them descriptive repository-resampling intervals.
- Initial external-frame intervals come from the archived two-level repository-to-root bootstrap over a screened frozen frame. They are not ecosystem-level intervals.
- The bounded-continuation study's `[1,1]` concordance interval and empirical one-sided discordance value `0` result from resampling an all-concordant observed witness sample. They are not calibrated unseen-event bounds.
- The external hard-root study's process-call interval is a 20,000-replicate dataset-stratified percentile bootstrap over 64 frozen roots, with 32 roots from each of miniF2F and PutnamBench. Its separately frozen one-sided lower bound is the normal approximation `mean(d) - z_0.95 * sd(d) / sqrt(n)`. Efficiency uses all launched calls on all roots. Coverage is not imputed for the one operationally unevaluable root; the 63-root Wilson upper bound is complete-case sensitivity analysis only.
- The oracle-assisted multi-step study's coverage loss fraction counts every operationally incomplete pair as a loss and uses a one-sided 95% Wilson score upper bound. The Wilson value is an uncertainty summary under a binomial working model, not a population bound for mathlib or the Lean ecosystem. Its efficiency estimand is the paired full-minus-endpoint tactic-invocation count over 64 roots. The two-sided interval is a 20,000-replicate authored-depth-stratified percentile bootstrap; the separately frozen one-sided lower bound is the normal approximation `mean(d) - z_0.95 * sd(d) / sqrt(n)`.
- The strict external-frame study's primary estimand is the equal-weight mean of the 32 repository-specific full-panel root frequencies. Its interval is a two-level nonparametric bootstrap that resamples the observed repository representatives and then their roots for 20,000 replicates with PCG64 seed `20260918` in the corrected analysis. The genealogy-deduplicated sensitivity estimate uses the same resampling design. These are descriptive empirical frame-resampling stability summaries, not population intervals; the procedure treats the observed representatives and within-repository roots as empirical resampling units and does not turn the lineage heuristic into a proof of independence. The archive also reports a source-file sensitivity: within each repository it averages the sampled-file-specific root frequencies equally, then averages the 32 repository values equally. Because all 512 roots were evaluable, complete-case estimates and frozen-frame worst-case missingness bounds coincide.
- The depth-stratified invocation and saving distributions reported in the revision are exact tabulations of immutable multi-step job receipts; no post hoc inferential subgroup test was introduced. Candidate-view/canonicalizer and terminality tables are likewise exact tabulations of archived root classifications.
- Historical planning thresholds and archived protocol labels are retained for exact reconstruction. Because their substantive scientific basis was not separately documented, the main text interprets point estimates, uncertainty summaries, and realized support directly rather than treating those targets as universal validity boundaries.

### Formal controls used in the main text

Main Section 2.2 gives a conditional refinement argument: if equality under one canonicalizer always implies equality under another, the former distinguishes at least as many states. This premise does not hold for the two frozen canonicalizers. The observed text-only and structure-only matches show that their endpoint relations are not nested on the measured rows.

For a fixed root, execution configuration, and canonicalizer, enlarging the candidate panel cannot remove an already observed witness, as stated in main Section 2.3. The root indicator depends on the candidates available at that root. This implication is one-way: a zero under a finite panel does not imply absence among all Lean programs.

### Frozen downstream root, pair, and representative selection

The downstream intervention uses no probe outcome during selection. A root is eligible only if its archived robustness row is evaluable, has one pre-goal, and contains both a non-initial nonterminal cross-head equal-strict-endpoint pair and a corresponding different-endpoint control pair. Archive members above 20 MiB are excluded by a frozen portability gate. Eligible roots are ordered by archive-member bytes and theorem identifier, and the first four per repository are selected.

Within each root, branches are ordered by frozen candidate position. Eligible pair records are ordered by their strict-endpoint hash tuple and then by the two frozen candidate positions. The first witness and first control are retained. The witness representative is the left branch in this frozen order. The rule depends only on archived depth-1 identities and positions; downstream probe outcomes cannot select or replace a root, pair, or representative.

### External hard-root selection and four-policy execution

Pinned miniF2F commit `f0a20e14c1eeccd859d51bb4c2b3ee487889c303` and PutnamBench commit `34eba93650f2fa803ca6aae6dfd2c9f22d46c00d` were built under Lean v4.27.0. Complete source enumeration identified theorem holes, and candidate-only screening used 21 frozen expansion tactics: `rfl`, `assumption`, `trivial`, `contradiction`, `simp`, `simpa`, `simp_all`, `aesop`, `norm_num`, `omega`, `linarith`, `nlinarith`, `ring`, `ring_nf`, `positivity`, `decide`, `native_decide`, `constructor`, `ext`, `fun_prop`, and `solve_by_elim`. Suggestion queries `exact?` and `aesop?` were excluded before screening. Of 658 screened roots, 459 were eligible, 28 failed the minimum effect-class size, 100 failed the minimum executable-nonterminal count, and 71 had a terminal candidate.

Every root retained an eligibility receipt, source partition, deterministic pilot key, deterministic confirmation key, selection rank, and exclusion reason. The pilot selected 16 roots per dataset. A 20,000-replicate stratified simulation then fixed a disjoint confirmation of 32 roots per dataset before any confirmation continuation probe. The selected-root ledger SHA-256 is `cbfc4569e5869e74b8f72e4ee5f4ce6f1def6d23fdde274ef15e224a169d6bb6`; the complete selection-audit SHA-256 is `2c341eeed3b5e8729f2861cac867918c53faa2bff2fbe66717510c8f631b745b`.

All four policies execute the same ordered 21-candidate front end. Full expansion follows every successful nonterminal branch. Endpoint selection keeps the first branch for each structural endpoint hash. Deduplication by tactic head keeps the first branch for each parsed head. The random control matching child counts at each node (archive label `fixed_budget_random`) uses a root-specific frozen seed to select exactly as many branches as endpoint selection. Each retained branch receives the same ordered eight-probe panel. Candidate calls and branch--probe calls each launch fresh Lean processes; cell timeout is 900 seconds and the common root--policy budget is 7,200 seconds.

The primary efficiency estimand is the paired per-root difference in actual Lean process calls between full and endpoint policies. The archived coverage estimand is the fraction of roots solved by full but not endpoint selection, with an inherited planning margin of 0.05. Endpoint-union and per-root endpoint-set equality are diagnostics. One root has an unavailable coverage outcome because three policy cells encountered a Lean internal panic. All launched processes remain counted for efficiency; coverage is not imputed. The planning margin is retained in the protocol for reconstruction and is not treated as a universal scientific threshold.

### Oracle-assisted known-solvable multi-step selection and four-policy execution

The oracle-assisted multi-step study uses the 2,000 theorem rows in LeanDojo benchmark partition `leandojo_benchmark_4/random/test.json` at mathlib4 commit `29dcec074de168ac2bf835a77ef68bbe069194c5`. Offline graph analysis admitted 409 roots whose shortest recorded authored path had depth 2--6 and contained neither `sorry` nor `admit`. A role- and depth-stratified 192-root candidate frame was frozen before any scientific policy job. Live qualification completed all 192 receipts: 142 passed, 50 failed, and one failure was operational. The confirmation-qualified pool contained 38 depth-2 roots and 55 depth-3--6 roots. The confirmation selected the first 32 frozen-rank passing roots in each stratum, disjoint from the 16-root pilot. The total of 64 was frozen before confirmation outcome access as a balanced computational budget of 32 roots per authored-depth stratum; the archived protocol contains no power or precision derivation for this number.

The generic candidate panel contains `rfl`, `assumption`, `solve_by_elim`, `trivial`, `contradiction`, `simp`, `simp only`, `simp_all`, `simpa`, two fixed-budget `aesop` variants, `norm_num`, `omega`, `linarith`, `nlinarith`, `ring`, `ring_nf`, `positivity`, `constructor`, `constructor <;> try assumption`, `intro`, `intro h`, `ext`, and `fun_prop`. Each root's nonforbidden authored-witness actions are added to this panel. At a state where the next witness action is recognized, it is inserted at index 3, or rank four. Every policy therefore sees the same disclosed route to a proof; this intentionally neutralizes candidate acquisition.

Search runs through fresh LeanDojo theorem sessions. Full expansion retains all successful children. Endpoint selection (archive label `effect_aware`) retains the first child per normalized `text48_v1` endpoint key. This key is the SHA-256 digest of LeanDojo's `TacticState.pp` after CRLF/CR-to-LF conversion, removal of surrounding and blank-line whitespace, per-line collapse of horizontal whitespace, and replacement of generated identifiers by `<GEN>`. It reuses the string-normalization logic of the primary textual canonicalizer but operates on the LeanDojo pretty-printed state; it is not the structural serializer and does not preserve the complete ordered local context or metavariable declarations. The name records the original archive identifier and schema version, not 48 state fields, and its implementation was frozen before confirmation outcomes. Deduplication by tactic head (archive label `head_dedup`) retains the first child per parsed tactic head. The random control matching child counts at each node (archive label `fixed_budget_random`) uses seed `620054` to retain the same child count as endpoint selection at each visited node. Root-specific policy order is a deterministic cyclic Latin order. Policies execute sequentially within root. The common scientific limits are depth 6, 32 expanded nodes, 768 tactic invocations, and 240 seconds beginning only after live initial-state validation. The invocation counter increases before each candidate is executed, so endpoint observation and classification costs are included even when the resulting child is not retained. Repository/theorem initialization has a separate 1,800-second envelope and finalization a 120-second grace period.

The 16-root pilot completed all policy jobs and produced 13 full-policy multi-step solves before the confirmation freeze. Confirmation comprised 64 roots and 256 jobs. The coverage estimand is the fraction of roots solved by full but not endpoint selection, counting every operationally incomplete pair as a loss. Historical planning cutoffs remain in the protocol; the article interprets the observed loss fraction, uncertainty summary, saving distribution, and depth strata directly. Seeds `620051`--`620055` fix the frame, candidate order, policy order, random control, and bootstrap respectively.
