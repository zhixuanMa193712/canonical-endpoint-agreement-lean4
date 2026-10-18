# Supplementary Results

## S8. Candidate-view and canonicalizer sensitivity

The complete root-positive surface is shown below. Every cell is an exact count over the same 96 immutable roots.

| Root-local candidate view | Raw | Textual (`text48`) | Structural |
|---|---:|---:|---:|
| Full panel (`L0`) | 57 | 57 | 70 |
| No heads ending in ? (`L-no-question`) | 42 | 42 | 64 |
| No `aesop` (`L-no-aesop`) | 44 | 44 | 65 |
| No `aesop?` (`L-no-aesop-question`) | 44 | 44 | 65 |
| No `aesop` + `aesop?` (`L-no-aesop-pair`) | 44 | 44 | 62 |
| No direct suggestions/control wrappers (`L-no-direct-wrapper`) | 42 | 42 | 64 |
| After genealogy deduplication (`L-mechanism-diverse`) | 30 | 30 | 33 |

Full-panel terminality decomposition:

| Canonicalizer | Terminal only | Nonterminal only | Both terminal and nonterminal | Neither |
|---|---:|---:|---:|---:|
| Raw | 21 | 34 | 2 | 39 |
| Textual (`text48`) | 21 | 34 | 2 | 39 |
| Structural | 15 | 47 | 8 | 26 |

The four categories are mutually exclusive and exhaustive. “Both” means that
the same root contains at least one terminal witness pair and at least one
nonterminal witness pair; it does not require one pair to be both terminal and
nonterminal.

The five root-local 23-candidate panels have frequencies 85, 6, 3, 1, and 1.
Their 19-candidate ordered intersection has SHA-256
`6734dce1ae2e6390502c57332f24db29e78bc5915f93e92263ceb2d3607acea9`.
The common panel contains `assumption`, `trivial`, `contradiction`, `simpa`,
`simp_all`, `aesop`, `aesop?`, `norm_num`, `omega`, `linarith`, `nlinarith`,
`ring`, `ring_nf`, `positivity`, `native_decide`, `constructor`, `fun_prop`,
`solve_by_elim`, and `exact?`.

| Common 19-candidate analysis | Raw | Textual | Structural |
|---|---:|---:|---:|
| Root positive | 57 | 57 | 70 |
| Nonterminal root positive | 35 | 35 | 54 |
| Cross-family root positive | 35 | 35 | 43 |
| Successful cross-head pairs | 421 / 16,416 | 421 / 16,416 | 472 / 16,416 |

Repository order is Carleson, FLT, Sphere-Packing-Lean, and Brownian Motion. All intervals below are archived descriptive repository-resampling outputs over four rates.

| Candidate view, structural endpoint | Repository rates | Macro mean | 95% resampling interval |
|---|---|---:|---|
| Full panel (`L0`) | 79.17%, 66.67%, 91.67%, 54.17% | 72.92% | [60.42%, 85.42%] |
| No heads ending in ? (`L-no-question`) | 66.67%, 66.67%, 91.67%, 41.67% | 66.67% | [47.92%, 85.42%] |
| No `aesop` (`L-no-aesop`) | 70.83%, 66.67%, 91.67%, 41.67% | 67.71% | [48.96%, 85.42%] |
| No `aesop?` (`L-no-aesop-question`) | 70.83%, 66.67%, 91.67%, 41.67% | 67.71% | [48.96%, 85.42%] |
| No `aesop` + `aesop?` (`L-no-aesop-pair`) | 66.67%, 58.33%, 91.67%, 41.67% | 64.58% | [47.92%, 83.33%] |
| No direct suggestions/control wrappers (`L-no-direct-wrapper`) | 66.67%, 66.67%, 91.67%, 41.67% | 66.67% | [47.92%, 85.42%] |
| After genealogy deduplication (`L-mechanism-diverse`) | 29.17%, 45.83%, 41.67%, 20.83% | 34.375% | [25.00%, 43.75%] |

For the genealogy-deduplicated view under structural comparison (archive label `L-mechanism-diverse`), nonterminal macro mean was 17.708% and cross-family macro mean was 34.375%. Every repository contributed each signal.

### S8.1. Candidate outcomes

Main-text Table 5 gives successes and nonterminal successes for each executed program. In the case-series rows, 514 of 2,208 attempts succeeded. Failures are recorded in one category; 44 of them were parse failures (`unknown tactic`) at nine roots (`linarith` 8, `nlinarith` 8, `positivity` 8, `ring` 7, `ring_nf` 7, `norm_num` 6), and one was a heartbeat exhaustion of `solve_by_elim`. In the strict frame, 2,357 of 11,776 attempts succeeded; of the failures, 1,764 occurred at parsing, all for Mathlib or Aesop tactics (`linarith` 250, `nlinarith` 250, `ring` 235, `ring_nf` 235, `norm_num` 233, `positivity` 233, `fun_prop` 128, `aesop` 100, `aesop?` 100) in 18 representatives, and 7,655 during execution, 23 of them heartbeat exhaustions at six roots.

The table separates successes that close the goal, successes that change the state and leave a goal, and successes that leave the canonical record unchanged (post hoc). The case-series columns use the textual record and the strict-frame columns the structural one; the classification of closures and failures does not depend on the representation.

| Program | Case series: closed | changed | unchanged | failed | Strict frame: closed | changed | unchanged | failed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rfl` | 4 | 0 | 0 | 89 | 37 | 0 | 0 | 471 |
| `assumption` | 0 | 0 | 0 | 96 | 0 | 0 | 0 | 512 |
| `trivial` | 8 | 0 | 0 | 88 | 54 | 0 | 0 | 458 |
| `contradiction` | 0 | 0 | 0 | 96 | 0 | 0 | 0 | 512 |
| `simp` | 11 | 15 | 5 | 64 | 24 | 113 | 0 | 374 |
| `simpa` | 12 | 0 | 0 | 84 | 28 | 0 | 0 | 484 |
| `simp_all` | 17 | 20 | 4 | 55 | 35 | 170 | 0 | 307 |
| `aesop` | 20 | 28 | 1 | 47 | 49 | 206 | 0 | 257 |
| `aesop?` | 20 | 28 | 1 | 47 | 49 | 206 | 0 | 257 |
| `norm_num` | 11 | 15 | 62 | 8 | 9 | 73 | 196 | 233 |
| `omega` | 0 | 0 | 0 | 96 | 3 | 0 | 0 | 506 |
| `linarith` | 0 | 0 | 0 | 96 | 1 | 0 | 0 | 511 |
| `nlinarith` | 0 | 0 | 0 | 96 | 1 | 0 | 0 | 511 |
| `ring` | 0 | 16 | 25 | 55 | 0 | 161 | 0 | 351 |
| `ring_nf` | 0 | 16 | 25 | 55 | 0 | 161 | 0 | 351 |
| `positivity` | 0 | 0 | 0 | 96 | 1 | 0 | 0 | 511 |
| `decide` | 0 | 0 | 0 | 95 | 17 | 0 | 0 | 480 |
| `native_decide` | 1 | 0 | 0 | 95 | 26 | 0 | 0 | 476 |
| `constructor` | 7 | 15 | 0 | 74 | 41 | 124 | 0 | 337 |
| `ext` | 0 | 20 | 0 | 70 | 0 | 45 | 0 | 467 |
| `fun_prop` | 2 | 0 | 0 | 94 | 0 | 0 | 0 | 512 |
| `solve_by_elim` | 7 | 0 | 0 | 89 | 52 | 0 | 0 | 460 |
| `exact?` | 93 | 0 | 0 | 3 | 451 | 0 | 0 | 61 |
| `apply_assumption` | 3 | 2 | 0 | 6 | 21 | 3 | 0 | 20 |

Under the structural record, `ring` and `ring_nf` changed the state at all 41 of their case-series successes; 25 of these changes are invisible in the printed state. In the strict frame, the textual record is unchanged at 82 of their 161 successes. `norm_num` left both records unchanged at 62 of 88 case-series and 196 of 278 strict-frame successes (199 textually); in the strict frame it never failed during execution where it parsed, consistent with its silent no-change behavior (Section S5). In both samples and under either representation, only ten programs ever reached a changed nonterminal endpoint.

The archived failure messages of the strict frame (`failure_messages.py`, post hoc) name tactic-level causes: for example `made no progress` for `simp` (374), `simp_all` (307), `ring_nf` and `ring` (116 each), and Aesop (152 each); `linarith failed to find a contradiction` (261); `no applicable constructor found` (185); `Expected type must not contain free variables` for `decide` and `native_decide` (448 each); and `could not close the goal` for `exact?` (59). None mentions a missing declaration name or `sorry`; eight report the recursion-depth limit and 23 the heartbeat limit.

`exact?` succeeded only by closing the goal. At roots that are the first tactic of a theorem's top-level proof it succeeded at 92 of 93 case-series and 437 of 474 strict-frame roots; elsewhere at 1 of 3 and 14 of 38. The authored step closes the goal at 34 and 130 of the theorem-start roots and at 0 and 9 of the others.

### S8.2. Composition of positive roots

| Study and representation | Full: positive | Full: nonterminal | Full: terminal only | Dedup.: positive | Dedup.: nonterminal | Dedup.: terminal only |
|---|---:|---:|---:|---:|---:|---:|
| Case series (96), textual | 57 | 36 | 21 | 30 | 14 | 16 |
| Case series (96), structural | 70 | 55 | 15 | 33 | 17 | 16 |
| Strict frame (512), textual | 321 | 255 | 66 | 132 | 68 | 64 |
| Strict frame (512), structural | 355 | 298 | 57 | 141 | 76 | 65 |

Raw and textual counts are identical. Removing `exact?` from the full panel lowers the case-series textual count from 57 to 55 and the strict structural count from 355 to 353 (textual: 321 to 318). Summed over roots, successful executions that reached a changed nonterminal endpoint and the number of distinct such endpoints were 175 and 99 in the case series (textual; 1.77 per endpoint), 111 and 91 after deduplication (1.22), 1,262 and 662 in the strict frame (structural; 1.91), and 725 and 621 after deduplication (1.17).

The following counts were added during review and recompute the composition under alternative rules. **Implementation groups:** a witness must pair programs from different implementation groups (Section S3). **Conservative recount:** `exact?` is removed from every panel and roots whose declaration carries a `simp`, `ext`, `fun_prop`, `aesop`, `norm_num`, `positivity`, or `grind` attribute are dropped (15 and 18 roots), so that closures by self-citation are excluded as far as the archived data allow. **Visible textual change:** a structural witness counts only if both programs also change the printed state. **Parse strata:** strict-frame roots at which all 23 programs parsed, against roots with at least one parse failure; the two strata differ in which programs could succeed.

| Analysis (post hoc) | Roots | Full: positive | Full: nonterminal | Dedup.: positive | Dedup.: nonterminal |
|---|---:|---:|---:|---:|---:|
| Case series, textual: implementation groups | 96 | 24 | 1 | 9 | 1 |
| Case series, textual: conservative recount | 81 | 42 | 36 | 20 | 14 |
| Case series, structural: implementation groups | 96 | 23 | 0 | 8 | 0 |
| Case series, structural: conservative recount | 81 | 55 | 52 | 23 | 17 |
| Case series, structural with a visible textual change | 96 | 57 | 36 | 29 | 13 |
| Strict frame, textual: implementation groups | 512 | 84 | 4 | 65 | 4 |
| Strict frame, textual: conservative recount | 494 | 300 | 255 | 118 | 68 |
| Strict frame, structural: implementation groups | 512 | 84 | 4 | 65 | 4 |
| Strict frame, structural: conservative recount | 494 | 335 | 298 | 127 | 76 |
| Strict frame, structural with a visible textual change | 512 | 321 | 255 | 138 | 73 |
| Strict frame, textual: all 23 programs parse | 260 | 189 | 173 | 78 | 58 |
| Strict frame, textual: some parse failures | 252 | 132 | 82 | 54 | 10 |
| Strict frame, structural: all 23 programs parse | 260 | 220 | 213 | 83 | 62 |
| Strict frame, structural: some parse failures | 252 | 135 | 85 | 58 | 14 |

The deduplicated view keeps the first member of each genealogy group in library order, so `simp` represents the simplifier family. Keeping `simpa` or `simp_all` instead changes the counts substantially (post hoc):

| Sample, representation | Kept `simp` (default): positive / nonterminal | Kept `simpa` | Kept `simp_all` |
|---|---|---|---|
| Case series, textual | 30 / 14 | 23 / 7 | 33 / 12 |
| Case series, structural | 33 / 17 | 24 / 8 | 41 / 20 |
| Strict frame, textual | 132 / 68 | 86 / 15 | 154 / 81 |
| Strict frame, structural | 141 / 76 | 102 / 31 | 182 / 108 |

Summed over roots, the share of successful executions reaching a changed nonterminal endpoint that duplicate an earlier such endpoint at the same root is 43% in the case series (textual; 76 of 175) and 48% in the strict frame (structural; 600 of 1,262), and 18% and 14% after deduplication.

Nonterminal witness roots under alternative implementation groupings, full panel (deduplicated view in parentheses). The grouping in the main text was defined after the pair counts had been seen:

| Grouping (post hoc) | Case series, textual | Case series, structural | Strict frame, textual | Strict frame, structural |
|---|---:|---:|---:|---:|
| Implementation groups (simplifier group includes Aesop and `norm_num`) | 1 (1) | 0 (0) | 4 (4) | 4 (4) |
| Aesop as a separate group | 8 (8) | 19 (14) | 46 (17) | 91 (43) |
| `norm_num` as a separate group | 13 (13) | 11 (11) | 66 (66) | 64 (64) |
| Aesop and `norm_num` as separate groups | 14 (14) | 22 (17) | 94 (68) | 119 (76) |

Programs from different implementation groups often reach changed nonterminal states at the same root without agreeing. A pair is co-active when both programs reach a changed nonterminal endpoint at the root:

| Sample, representation | Roots with a co-active cross-group pair | Roots with cross-group agreement | Co-active pairs | Agreeing pairs |
|---|---:|---:|---:|---:|
| Case series, textual | 21 | 1 | 116 | 2 |
| Case series, structural | 37 | 0 | 204 | 0 |
| Strict frame, textual | 122 | 4 | 653 | 20 |
| Strict frame, structural | 168 | 4 | 1,007 | 10 |

Strict-frame results by Mathlib dependence of the representative (`scan_dependencies.py`):

| Strict-frame representatives | Roots | Full: positive / nonterminal (structural) | Dedup.: positive / nonterminal (structural) | Full: positive / nonterminal (textual) |
|---|---:|---|---|---|
| Depend on Mathlib (26) | 416 | 317 / 288 | 114 / 76 | 283 / 245 |
| Do not depend on Mathlib (6) | 96 | 38 / 10 | 27 / 0 | 38 / 10 |

Within the 4 representatives that have roots in both parse strata, 31 of 36 all-parse roots and 17 of 28 roots with parse failures were positive under structural comparison (31 and 14 with a nonterminal witness).

By root position, using the full panel; the 38 strict-frame roots that are not theorem starts come from 17 representatives:

| Sample, representation | Theorem-start roots | Positive | Nonterminal | Other roots | Positive | Nonterminal |
|---|---:|---:|---:|---:|---:|---:|
| Case series, textual | 93 | 57 | 36 | 3 | 0 | 0 |
| Case series, structural | 93 | 68 | 53 | 3 | 2 | 2 |
| Strict frame, textual | 474 | 296 | 234 | 38 | 25 | 21 |
| Strict frame, structural | 474 | 325 | 271 | 38 | 30 | 27 |

Agreement at changed states under the implementation grouping was rare: at the single case-series root (textual record) `norm_num` agrees with `ring` and `ring_nf`, and at the four strict-frame roots Aesop agrees with `constructor` or programs of the simplifier group agree with `ring` and `ring_nf`. The deduplicated nonterminal pairs are dominated by programs of the simplifier group (Section S8.5).

### S8.3. Rarefaction by panel size

| Random panel size k | Structural macro frequency | 95% range over 1,000 subsets |
|---:|---:|---|
| 4 | 11.51% | [6.25%, 16.67%] |
| 8 | 30.32% | [23.96%, 37.50%] |
| 12 | 45.40% | [38.54%, 52.08%] |
| 16 | 57.02% | [51.04%, 62.50%] |
| 23 (full) | 72.92% | [72.92%, 72.92%] |

The deduplicated panel of 18 programs (19 at one root) gives 34.38%, below random panels of 12 programs, so the reduction under deduplication is not explained by panel size alone.

Two post hoc controls compare the deduplicated panel with panels of the same size and with panels that lose the same number of programs. The first draws 18 programs at random from each root's panel; the second removes five programs drawn at random from those that succeeded at least once in the sample. Values are macro frequencies over 1,000 draws.

| Sample, representation | Full panel | Random 18 programs, mean [95% range] | Five productive programs removed, mean [95% range] | Deduplicated |
|---|---:|---|---|---:|
| Case series, structural | 72.9% | 61.9% [57.3%, 66.7%] | 56.7% [51.0%, 62.5%] | 34.4% |
| Case series, textual | 59.4% | 49.9% [44.8%, 54.2%] | 45.7% [40.6%, 51.0%] | 31.3% |
| Strict frame, structural | 69.3% | 57.7% [55.3%, 60.4%] | 55.9% [53.3%, 58.4%] | 27.5% |
| Strict frame, textual | 62.7% | 51.2% [48.6%, 53.7%] | 49.5% [46.9%, 52.0%] | 25.8% |

### S8.4. Reproduction of the authored endpoint

Some panel program reached the authored step's endpoint at 35 of the 96 case-series roots (textual) and 170 of the 512 strict-frame roots (structural). When the authored step left a goal open, this happened at 1 of 62 case-series roots and 36 of 373 strict-frame roots. Strict-frame roots whose authored step closes the goal were positive more often (102/139, 73.4%) than the others (253/373, 67.8%), but only through terminal witnesses: nonterminal witnesses occurred at 59 and 239 of them.

### S8.5. Nonterminal pairs after deduplication

Head pairs forming nonterminal structural witnesses in the deduplicated view (post hoc). A root contributes once to each pair it contains.

| Sample | Pair | Roots | Repositories |
|---|---|---:|---:|
| Case series | `aesop/simp` | 14 | 4 |
| Case series | `norm_num/simp` | 11 | 4 |
| Case series | `aesop/norm_num` | 8 | 3 |
| Strict frame | `norm_num/simp` | 61 | 17 |
| Strict frame | `aesop/simp` | 39 | 16 |
| Strict frame | `aesop/norm_num` | 27 | 12 |
| Strict frame | `aesop/constructor` | 3 | 2 |
| Strict frame | `ring/simp` | 1 | 1 |
| Strict frame | `norm_num/ring` | 1 | 1 |

## S9. Endpoint confusion

| Comparison unit, `text48` versus structure | Both negative | Both positive | `text48` only | Structure only |
|---|---:|---:|---:|---:|
| All candidate pairs | 23,622 | 590 | 4 | 72 |
| Nonterminal cross-head pairs | 24,096 | 116 | 4 | 72 |
| Root primary indicator | 26 | 57 | 0 | 13 |
| Root nonterminal indicator | 41 | 36 | 0 | 19 |

Raw and `text48` agreed exactly in the archived comparisons. The confusion table establishes measurement-construct sensitivity only. The `Both negative` cell of the first two rows includes pairs in which at least one candidate failed; the second row counts nonterminal pairs among all 24,288 pairs.

All 76 discordant pairs are nonterminal, because a closed goal has the same record under every representation. Of the 72 structure-only pairs, 38 differ textually only in the names of instance hypotheses: `aesop` and `aesop?` give them accessible names (`inst`, `inst_1`), whereas `simp`, `simp_all`, and `norm_num` leave them inaccessible (`inst<GEN>²`). The pairs are `simp_all`/`aesop` and `simp_all`/`aesop?` (11 each), `simp`/`aesop` and `simp`/`aesop?` (6 each), and `aesop`/`norm_num` and `aesop?`/`norm_num` (2 each). In the other 34, at 28 roots, both programs changed the state structurally without changing the printed state, so the textual endpoint equals the initial one and the pair does not qualify textually. They are `ring`/`ring_nf` (25 pairs), `simp`/`simp_all` (4), and Aesop with simplifier programs (5). The constants that differ between the initial and the resulting structural records are instance paths, for example `CommSemiring.toSemiring` and `Semiring.toNonAssocSemiring`: the tactics rewrite how an instance is reached without changing what is printed. The structural record therefore counts instance rewrites as transitions. In the strict frame, requiring a visible textual change as well lowers the structural counts from 355 to 321 positive and from 298 to 255 nonterminal roots, the textual values (Section S8.2). The printer also abbreviates proof subterms as `⋯` (`ellipsis_scan.py`, post hoc). No case-series record contains the abbreviation. In the strict frame it occurs in 42 of the 1071 changed nonterminal textual records and in 14 of the 358 textual witness classes at changed nonterminal states, and 8 strict-frame roots are positive under textual comparison only through such classes. The four text-only pairs print identically but differ structurally: at the Carleson root `TileStructure.Forest.adjoint_density_tree_bound1`, `norm_num` and `ring` (and `ring_nf`) produce different instance terms for the same complex multiplication, and at a Sphere Packing root on the E8 lattice, `simp` and `simp_all` differ from `norm_num` in a subterm that prints identically.

## S10. Same-server exact-comparison accounting

| Mode | Roots | Candidate attempts | Condition | Outcome |
|---|---:|---:|---|---|
| M0 | 96 | 2,208 | Historical order | Exact source endpoint content |
| M1 | 96 | 2,208 | Reverse order | Exact M0 |
| M2 | 96 | 2,208 | Seeded shuffle 500052 | Exact M0 |
| M3 | 96 | 2,208 | Seeded shuffle 500053 | Exact M0 |
| M4 | 96 | 2,208 | Seeded shuffle 500054 | Exact M0 |
| M5 | 96 | 2,208 | One fresh Lean process per branch | Exact M0 |

All six modes matched the prespecified endpoint content exactly. Comparison used the content fields defined in Section S6, with zero content mismatches and zero manual reconciliation.

The first automated comparison of M0 with the archived robustness rows hashed the complete raw-endpoint container rather than its content. It reported 706 differences: 514 candidate endpoints, 96 authored-replay endpoints, and 96 initial endpoints. All arose because the two runners wrote different recorder schema labels (`exp49-raw-endpoint-v1` and `exp50-raw-endpoint-v1`) into otherwise identical containers. Statuses, ordered raw state bytes, goal counts, terminal flags, textual endpoints, and strict endpoints already matched, and the order and process comparisons (M1--M5 against M0) matched from the start. A versioned analysis-only amendment, which executed no Lean process and modified no execution row, reproduced all 706 original differences and then compared container content while validating each runner's container hash separately. The original analysis, its mismatch ledger, and the amendment are preserved with their hashes in the archive.

## S11. External-frame repository rates

| Repository | `L0` rate | Frequency after genealogy deduplication |
|---|---:|---:|
| `PatrickMassot/GlimpseOfLean` | 47.92% | 22.92% |
| `AfonsoBitoque/LeanServer` | 62.50% | 39.58% |
| `dissensus-ai/lean-formalizations` | 79.17% | 22.92% |
| `leanprover-community/batteries` | 50.00% | 4.17% |
| `bergmannjg/Regex` | 60.42% | 4.17% |
| `Verified-zkEVM/VCVio` | 95.83% | 79.17% |
| `leanprover-community/lean-auto` | 22.92% | 4.17% |
| `YaelDillies/misc-yd` | 60.42% | 25.00% |
| `MichaelStollBayreuth/LegendreQF` | 75.00% | 27.08% |
| `verse-lab/Lentil` | 41.67% | 8.33% |
| `AmosNico/validator` | 83.33% | 39.58% |
| `spectra-research/asymptotic-tensor-rank-semicontinuity` | 50.00% | 18.75% |

Following the lexical-label correction described in Section S3, the full-panel macro mean is 60.7639% (350/576 roots), with a descriptive two-level bootstrap interval [49.1319%, 72.2222%]. The genealogy-deduplicated macro mean remains 24.6528% (142/576), with a recomputed interval [13.8889%, 37.6736%]. The correction uses stored executions and adds no new Lean calls. The prespecified primary criteria for this frame required a lower interval bound above 20%, nonzero frequencies in at least 75% of repositories, and an interval half-width of at most 10 percentage points. The first two were met. The half-width criterion was not met by the archived interval [31.08%, 59.90%] or by the corrected interval, so the archived decision label remains `inconclusive` and this frame is reported descriptively.

## S12. Bounded-continuation responses

| Item | Archived value |
|---|---:|
| Source external-frame roots accounted | 576 |
| Selected witnesses | 40 roots / 7 repositories |
| Valid within-root controls | 36 roots / 6 repositories |
| Informative paired deltas | 33 |
| Primary cells | 1,208 |
| Determinism-audit cells | 112 |
| Total cells | 1,320 |
| Successful probe executions | 211 |
| Recorded tactic failures | 1,109 |
| Timeouts | 0 |
| Determinism mismatches | 0 |
| Manual reconciliations | 0 |

Unified denominators distinguish selected roots, side--probe execution cells,
and paired-response units:

| Component | Role | Repeat kind | Unit | Planned | Observed | Valid |
|---|---|---|---|---:|---:|---:|
| Source frame | all | selection | root | 576 | 576 | 576 |
| Selected witnesses | witness | selection | root | 40 | 40 | 40 |
| Within-root controls | control | selection | root pair | 36 | 36 | 36 |
| Continuation execution | witness | primary | side--probe cell | 636 | 636 | 636 |
| Continuation execution | control | primary | side--probe cell | 572 | 572 | 572 |
| Continuation execution | witness | determinism audit | side--probe cell | 112 | 112 | 112 |
| Paired response | witness | primary | pair--probe | 318 | 318 | 318 |
| Paired response | control | primary | pair--probe | 286 | 286 | 286 |
| Paired response | witness | determinism audit | pair--probe | 56 | 56 | 56 |
| Determinism comparison | all | audit | side--probe cell | 112 | 112 | 112 |
| All execution | all | all | side--probe cell | 1,320 | 1,320 | 1,320 |

| Primary response category | Count |
|---|---:|
| Both fail, same category | 486 |
| Both succeed, same structural endpoint | 52 |
| Both succeed, different structural endpoints | 23 |
| Left succeeds only | 18 |
| Right succeeds only | 25 |

The probe pool contained 12 programs; the qualified probe surface retained nine (`rfl`, `assumption`, `simp`, `simp_all`, `omega`, `constructor`, `intro`, `solve_by_elim`, and `first | rfl | assumption`), and the members of each pair were removed, giving at most nine probes per pair. The prespecified gates required at least 200 valid witness roots from at least 12 repositories and at least 100 within-root controls from at least eight repositories; the realized 40 roots from seven repositories and 36 controls did not meet them, which is why the archived decision is `continuation_inconclusive`.

The archived measures A, B, and C use probes for which at least one side succeeds. A is the fraction with exactly one successful side; B also counts probes where both sides succeed but reach different structural endpoints; C is the fraction where both sides succeed at the same structural endpoint. D indicates whether a root has any discordant probe of either kind. Their witness macro means, with equal repository weights, were A=0, B=0, C=1, and D=0. The all-concordant empirical bootstrap produced A and B intervals `[0,0]`, C interval `[1,1]`, and a B empirical one-sided value of 0. The paired-control delta in C was 0.958333 with interval [0.875,1.0]. The limited witness, control, and repository support makes these descriptive observations rather than evidence of general continuation equivalence; an all-concordant empirical bootstrap does not bound unseen discordance.

## S13. Second-machine exact subset

The second-machine subset contains four repositories, four roots per repository, 16 roots, and 368 candidate attempts. Every prespecified field matches the frozen external-frame projection. The mismatch ledger is empty; its archived SHA-256 is `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. The study records zero manual reconciliation and the immutable decision label `cross_machine_exact`.

![](FigS1_continuation_second_machine.png)

**Supplementary Figure S1. Continuation sample and reproduction on a second machine.** Of 576 source roots, 40 supply an eligible witness and 536 do not. The 36 paired controls belong to the selected witness roots; they are not an additional group of roots. Of these, 33 yield informative paired deltas. The lower panel reports exact reproduction of the frozen 16-root projection on a second machine. This portability result does not alter the external-frame or continuation decisions.

## S14. Prespecified downstream branch selection

The frozen design contains four repositories, 16 roots, 16 same-endpoint witness pairs, 16 different-endpoint controls, and eight probes per pair. Full expansion contains 512 cells. Representative pruning contains 384 cells because it retains one branch for each witness pair but both sides of every control. Initial candidate execution is unchanged.

| Quantity | Full expansion | Representative pruning |
|---|---:|---:|
| Downstream calls | 512 | 384 |
| Distinct successful strict endpoints | 26 | 26 |
| Distinct endpoints per 100 calls | 5.078 | 6.771 |
| Pair--probe combinations with any terminal success | 10 | 10 |
| Terminal-success cells | 17 | 12 |

All 896 frozen cells were reconstructed in fresh Lean processes, every attempt ordinal was one, all overlap cells reproduced exactly, and both scientific retries and manual reconciliation were zero. The successful strict-endpoint union and the set of pair--probe combinations with any terminal success were preserved. However, two of 128 side-specific witness--probe comparisons differed, affecting two of 16 witness pairs. The exact archived label is `coverage_loss_detected`: union-level coverage was preserved, while side-specific coverage or multiplicity was not lossless.

The scheduled-call estimand and coverage-preservation estimand are reported
separately. A positive call reduction cannot make the coverage estimand pass,
and union-level endpoint equality cannot erase side-specific mismatches.

Both side-specific differences occurred for `simp_all`/`aesop` witness pairs. Probe success and strict endpoints agreed, while generated local-instance display names differed. This explains the response-signature discrepancy without implying lossless pruning: terminal-success multiplicity was 17 versus 12, despite preservation of the strict-endpoint union.

## S15. Selected-root provenance validation

All 96 selected case-series roots have a recorded selection rank, theorem and
file identity, source hash, trace hash, and repository commit. The 24 ranks are
unique within each of the four repositories; all selected-file, source, and
trace hashes are internally consistent. The archive also records the reported
eligible-root totals (653, 318, 394, and 167) and three repository-level
exclusions. However, the compact archive does not contain every nonselected
eligible-root record. It can therefore verify selected-row identities and
ranks, but cannot prove from the deposited material alone that the 24 selected
ranks are globally the first 24 among each complete eligible frame. This is a
limit on reconstructing the original selection from the compact archive.

## S16. Immutable offline reanalysis

The five-panel reconstruction, common-19 analysis, complete 7-by-3 matrix,
four-way terminality table, unified denominators, provenance ledger, and split
downstream estimands were regenerated from the five locked case-series, sensitivity,
initial external-frame, continuation, and local branch-selection archives. An independent offline audit regenerated all
17 derived files byte-for-byte with zero mismatches and zero manual
reconciliation. The reanalysis leaves the original outcomes unchanged.

## S17. Prospectively frozen external hard-root confirmation

The confirmation retained 64 roots, 32 from miniF2F and 32 from PutnamBench,
and completed four paired policies per root. The 256 jobs contained 14,688
actual Lean process calls/cells. All candidate stages were exact, all cells used
fresh processes, every attempt ordinal was one, and scientific retries and
manual reconciliation were zero.

| Policy | Candidate calls | Downstream calls | Actual process calls | Selected depth-2 branches | Unique complete-case endpoints |
|---|---:|---:|---:|---:|---:|
| Full expansion | 1,344 | 2,856 | 4,200 | 357 | 410 |
| Endpoint selection | 1,344 | 1,800 | 3,144 | 225 | 410 |
| Deduplication by tactic head | 1,344 | 2,856 | 4,200 | 357 | 410 |
| Random control matching child counts at each node (`fixed_budget_random`) | 1,344 | 1,800 | 3,144 | 225 | 381 |

Endpoint selection saved 1,056 actual Lean process calls relative to full
expansion, a reduction of 25.1429%. The candidate stage was identical under both policies (1,344 calls), so the saving equals the eight probes for each of the 132 depth-two branches that endpoint selection did not retain (357 minus 225); it follows from the number of retained branches. The paired mean saving was 16.5 calls per
root, the dataset-stratified bootstrap 95% interval was [14.5,18.5], and the
protocol-specified normal-approximation one-sided 95% lower bound, `mean(d) - z_0.95 * sd(d) / sqrt(n)`, was 14.8196. Deduplication
by tactic head saved no calls. Equal-budget random
pruning matched the endpoint call count but did not preserve the
complete-case strict-endpoint union and matched the full per-root endpoint set
on 47/63 roots, versus 63/63 for endpoint selection.

One miniF2F root was unevaluable for paired coverage after a Lean internal panic in three policy cells. Its launched calls remain included in efficiency, and its coverage outcome is neither replaced nor imputed. Full-sample coverage is therefore unavailable.

The remaining 63 roots form a non-prespecified complete-case sensitivity set.
Full and endpoint selection each solved zero roots; paired coverage loss was
zero and its one-sided 95% Wilson score upper bound was 0.0411768. The strict-endpoint union
and every per-root endpoint set were identical between full and endpoint
selection on these 63 roots. Because no root was solved and one frozen root
was unevaluable, these observations do not establish theorem-solve-rate
improvement or complete-sample coverage noninferiority.

## S18. Interpretation scope

This section states the scope of the reported measurements and their reuse. Final numerical outcomes are given in the corresponding result sections.

| Scope or exception | Extended record | Consequence for interpretation |
|---|---|---|
| Lean version and repository frame | The recurrence, repeat-execution, and hard-root studies executed under Lean v4.27.0 at pinned commits. The multistep study used LeanDojo 4.20.0 at mathlib4 commit `29dcec07`, whose toolchain is Lean v4.10.0-rc1. The case series contains four repositories; the initial external frame contains 12 screened lineage representatives; the strict current-commit frame contains 32 lineage-deduplicated representatives. None is a probability sample, and the lineage screen does not prove statistical independence. | Reported macro means and descriptive frame-resampling intervals describe frozen frames and do not estimate ecosystem-wide frequency or later-version portability. |
| Case-series root provenance | The compact archive of the case series preserves selected-row identities, ranks, eligible counts, source hashes, and selected-file hashes, but not every nonselected eligible-root ledger from the inherited corpus protocol. | The 96 selected rows can be reconstructed exactly, but every eligible-to-selected ranking cannot be regenerated from the compact bundle alone. |
| Candidate panels | The recurrence experiment uses a 32-entry source library and deterministic 23-alternative root-local panels; only entries 1--24 were executed. Genealogy and family labels understate shared implementation (for example `norm_num`, `simp`, and Aesop's normalization all run the simplifier). The hard-root experiment uses a separate 21-program expansion panel. The multi-step experiment combines 24 generic actions with disclosed supplied authored steps. | A zero indicator means that no witness appeared in the frozen panel, not that no Lean program could produce one. Multi-step solvability does not measure autonomous candidate acquisition. |
| Environment | Candidates run in the environment recorded after the theorem's command, which contains the theorem; authored replay checks goals and metavariable context only. | Closures may use the theorem being proved; the multistep study, run through LeanDojo, does not share this difference. |
| Root position | The selected root is the first traced tactic of its theorem; it is the first tactic of the top-level proof at 93 of 96 case-series and 474 of 512 strict-frame roots. | Results describe the first step from a theorem's statement; agreement deeper in proofs was not measured. |
| Transition scope | Admitted recurrence pre-states contain one goal. The primary recurrence response covers one tactic invocation, and the continuation experiment adds one independent probe. The oracle-assisted multistep study follows authored-depth-2--6 trajectories. | Arbitrary trajectories outside the disclosed action set and multi-goal starting states require separate evaluation. |
| Endpoint abstraction | Textual and structural canonicalizers exclude proof terms, runtime, messages, internal traces, and selected metadata. Text-only and structure-only matches are both observed. The completed multi-step evaluation uses only `text48_v1`. | Prespecified endpoint equality is not proof-term identity, semantic equivalence, or cost equivalence. No completed same-root multi-step comparison yet measures the consequences of textual versus strict structural keys. |
| Continuation information | The observed witness sample was all-concordant on its informative denominator, but realized witness, control, and repository support remained restricted. | The authoritative archive label remains `continuation_inconclusive`; the observed cells do not bound arbitrary unseen trajectories. |
| Local branch selection | Representative selection reduced scheduled downstream calls by 25% and preserved the strict-endpoint union. Two side-specific witness--probe comparisons changed response multiplicity through generated local-instance display names. | The exact label remains `coverage_loss_detected`; Section S14 reports the coverage comparison. |
| Hard-root efficiency | Endpoint selection saved 1,056 actual Lean process calls. One root lacks the paired coverage outcome under the frozen no-retry rule, and no complete-case root was solved by either principal policy. | Process-call efficiency is measured on all 64 roots; coverage and theorem-solve-rate improvement are not established. Section S17 reports the complete-case sensitivity analysis. |
| Oracle-assisted multi-step solvable search | Endpoint selection solved 59/64 roots versus 58/64 for full expansion, with 0/64 full-only losses and 1,207 fewer tactic invocations, from expanding 373 instead of 417 nodes. Every policy received the root's supplied authored steps. A replay of the logs indicates that global merging of repeated keys would have used 5,730 invocations against 5,868 for endpoint selection on 60 roots. | The one-sided 95% Wilson upper bound was 0.04056 under a binomial working model; only 12 roots offered a chance to lose a solve (bounds 0.184 and 0.221). All savings occurred in depth-3--6 roots. The replay assumes deterministic execution and an adequate key. The solve-count difference is not interpreted as superiority, and candidate acquisition was not evaluated. |
| Execution success and environment | A branch succeeds when no exception is raised; aborted tactic blocks are caught, error recovery is on, and logged messages and `sorry` in the assignment are not checked; `norm_num` can succeed without changing the goal. Executions see the environment after the command, which contains the declaration being proved. | Successful branches are not certified sorry-free. `exact?` closed nearly every theorem-start goal and these closures are probably self-citations; removing `exact?` changes 2/57 and 2/355 positives, and the conservative recount in Section S8.2 bounds the effect on positive roots. |
| Implementation sharing | Genealogy and family labels separate programs that share the simplifier or ring normalization; Aesop's nonterminal successes are failed searches. | Agreement at changed states between implementation groups occurred at 1/96 (textual) and 4/512 roots; deduplicated nonterminal counts mostly record agreement within the simplifier group. |
| Reproducibility | Same-server re-execution changes implementation, order, and process isolation, but uses the same Lean interfaces and environment; it covers the case series, and the second-machine subset covers initial-frame roots. No repeat execution of the strict frame was made. Second-machine re-execution covers 16 frozen roots and 368 attempts. | Exact prespecified-content agreement is established only on the re-executed scopes. |
| Public availability | Zenodo version 1.22.3 retains the original data ZIP with eleven unchanged experiment archives, manifests, license records, and the correction layer, and adds an updated code package; access details appear in the Artifact Manifest. | Archive integrity and corrected-analysis reconstruction are separate checks. Neither adds a new scientific execution. |

## S19. Oracle-assisted known-solvable multi-step branch selection

The immutable archive and protocol use the historical label `witness-injected`; the main manuscript describes this as search with supplied actions because every policy receives disclosed supplied authored steps. This is also called oracle-assisted search in the supplementary methods. The frozen candidate frame contained 192 roots, and live qualification wrote 192/192 receipts. There were 142 qualification passes and 50 failures, including one operational failure. The qualified confirmation pool contained 38 authored-depth-2 roots and 55 authored-depth-3--6 roots. The frozen confirmation used 32 roots from each stratum and did not replace any root manually. This balanced 64-root total was a pre-outcome computational budget; no power or precision calculation for the sample size is recorded. The 16-root pilot completed all 64 jobs without operational failure, and full expansion produced 13 multi-step solves before the main run was frozen.

The main run completed 256/256 root--policy jobs. All 64 roots had four policy receipts, every attempt ordinal was one, and operational failures, scientific retries, and manual reconciliations were all zero. Every reported solve used at least two external tactic invocations.

| Policy | Multi-step solved roots | Solve rate | Tactic invocations | Expanded nodes | Observed endpoint union | Median time to first proof (s) | Wall clock (s), descriptive |
|---|---:|---:|---:|---:|---:|---:|---:|
| Full expansion | 58/64 | 90.625% | 10,147 | 417 | 772 | 5.182 | 1,772.36 |
| Endpoint selection | 59/64 | 92.188% | 8,940 | 373 | 836 | 5.168 | 1,604.95 |
| Deduplication by tactic head | 56/64 | 87.500% | 10,019 | 411 | 809 | 5.093 | 1,731.78 |
| Random control matching child counts at each node (`fixed_budget_random`) | 40/64 | 62.500% | 14,269 | 563 | 1,025 | 4.556 | 2,238.03 |

For the prespecified paired coverage estimand, endpoint selection had zero losses and one gain relative to full expansion. There were no operationally incomplete pairs to count under the worst-case rule. The full-only loss fraction was therefore 0/64, with a one-sided 95% Wilson score upper bound of 0.0405595. This value is a Wilson uncertainty summary under the specified binomial working model; it is not a population bound for mathlib, other repositories, or other canonicalizers. The 59/64 versus 58/64 solve counts are not interpreted as evidence of superiority. Full and endpoint per-root endpoint sets were exactly equal on 58/64 roots (90.625%); this diagnostic was not a universal endpoint-preservation result.

Endpoint selection used 1,207 fewer tactic invocations than full expansion, an 11.895% reduction. The counter includes every executed candidate, including candidates whose children are not retained; because every policy executes all candidates at each expanded node, the saving reflects the 44 nodes that endpoint selection did not expand. The paired mean full-minus-endpoint saving was 18.859 invocations per root, with standard deviation 49.090. The authored-depth-stratified 20,000-replicate percentile-bootstrap 95% interval was [8.828,30.703]. The separately frozen normal-approximation one-sided 95% lower bound, `mean(d) - z_0.95 * sd(d) / sqrt(n)`, was 8.766. Here d is the paired saving in invocations, n is the number of roots, and z_0.95 is the 95th percentile of the standard normal distribution.

The per-root saving distribution was concentrated: 13/64 roots had positive savings, 51/64 had zero savings, and none had negative savings; the minimum, first quartile, median, and third quartile were all 0, and the maximum was 234 invocations. In the 32 authored-depth-2 roots, both policies executed 1,184 invocations and solved 32/32 roots, so the observed saving was 0. In the 32 authored-depth-3--6 roots, full expansion executed 8,963 invocations and solved 26/32 roots, whereas endpoint selection executed 7,756 invocations and solved 27/32. The 1,207-invocation difference is 13.466% of the full-policy total in that stratum and accounts for the entire aggregate saving. These are exact descriptive strata, not post hoc inferential subgroups.

Endpoint collisions were observed by the endpoint policy on 52/64 roots: 22/32 depth-2 roots contributed 79 collisions, and 30/32 depth-3--6 roots contributed 681. The depth-2 stratum therefore contained endpoint collisions without call savings, largely as a consequence of the design. The supplied step at rank four produces at most the fourth child of the root, and every depth-2 proof was found while expanding at most the third child: 24 searches expanded two nodes, seven expanded three, and one expanded four, identically under full expansion and endpoint selection. Savings at this depth require two of the few children expanded before the proof to share a key, which did not occur; the collisions involved later children.

| Authored depth | Roots | Full expansion invocations | Endpoint selection invocations | Solved (full / endpoint) |
|---:|---:|---:|---:|---|
| 2 | 32 | 1,184 | 1,184 | 32 / 32 |
| 3 | 20 | 3,103 | 2,356 | 20 / 20 |
| 4 | 8 | 3,236 | 2,892 | 5 / 6 |
| 5 | 1 | 768 | 768 | 0 / 0 |
| 6 | 3 | 1,856 | 1,740 | 1 / 1 |

Under breadth-first search without cross-branch merging, pruning a child whose key equals that of an earlier sibling can lose a proof only if the key merges states with different continuations or execution is not deterministic. The zero losses are consistent with both premises on these roots, but endpoint selection altered the search only at the 13 roots where it expanded fewer nodes and at the five roots solved by neither policy, where both spent the full budget on different nodes. A loss was therefore possible only at the 12 of the 13 that full expansion solved; for 0/12 the Wilson and Clopper--Pearson bounds are 0.184 and 0.221. For the 32 deeper roots, the one-sided Wilson and Clopper--Pearson bounds for 0/32 losses are 0.0780 and 0.0894.

The independent audit reconstructed every policy's solve, invocation, expanded-node, and operational-failure totals from immutable receipts. It verified all 256 job identities, exact transition-to-invocation accounting, all attempt ordinals equal to one, zero scientific retries, and zero manual reconciliation. The Artifact Manifest identifies the exact result bundle and protocol.

This experiment executes real multi-step LeanDojo interaction, but every policy receives the root's independently replayed authored steps. It therefore evaluates search-tree branch selection after candidate acquisition has been deliberately neutralized. It does not establish autonomous tactic generation, proof-term identity, semantic state identity, general wall-clock superiority, or performance beyond the frozen mathlib4 benchmark partition.

### S19.1. Source-file-cluster sensitivity

A post-outcome sensitivity resampled all 63 source-file clusters, retained every sampled file's roots together, and equally weighted the two authored-depth stratum means. There were 32 files represented in each stratum, with one file shared between strata; its two roots were always sampled together. With 20,000 resamples and PCG64 seed 20260918, the percentile interval for mean paired call savings was [8.89, 30.75], compared with the root-stratified interval [8.83, 30.70]. Because nearly every file contributes a single root, this check addresses little additional dependence. Shared mathematical dependencies and theorem-family clustering remain outside this sensitivity. All observed coverage losses were zero, making an ordinary nonparametric loss bootstrap degenerate; it supplies no valid zero-risk guarantee. The reported Wilson bound retains its explicitly stated binomial working-model interpretation.

### S19.2. Post hoc decomposition by solve status

This decomposition was computed after outcome observation from the archived per-root metrics (`paired_root_metrics.jsonl` in the Exp62 result bundle); it is descriptive and was not a prespecified estimand. On the 58 roots solved by both full expansion and endpoint selection, full expansion executed 5,539 tactic invocations and endpoint selection 4,536, a saving of 1,003 invocations (18.11%). On the five roots solved by neither policy, both policies exhausted the 768-invocation budget (3,840 invocations each), so these roots contributed no saving. The single root solved only by endpoint selection, in the authored-depth-3--6 stratum, used 768 invocations under full expansion and 564 under endpoint selection; its saving of 204 invocations is 16.90% of the aggregate 1,207. The efficiency gain is therefore not an artifact of the one additional solve.

Budget exhaustion also differed by policy. The 768-invocation budget was reached on 6/64 roots under full expansion, 5/64 under endpoint selection, 7/64 under deduplication by tactic head, and 11/64 under the random control; every search that reached the budget ended unsolved. The random control left 24 roots unsolved, 11 of them at the invocation budget; the other 13 ended before reaching any limit, which is consistent with discarding the child produced by the supplied step. No search under any policy reached the 32-node expansion limit, and no search reached the 240-second limit (the longest took 184 seconds).

### S19.3. Post hoc replay and key collisions

The replay of Section S7 reproduced the archived outcome and invocation total of full expansion at 61 of 64 roots and of endpoint selection at 58. At the others it needed transitions that the full-expansion logs do not contain, because those searches stopped at the invocation budget. In the full-expansion logs, 68 keys were expanded more than once, and every repeated expansion had the same candidate outcomes and child keys as the first, which supports the replay's premises.

With a global set of seen keys, the replay was complete at 60 roots. On these roots it solved 59 with 5,730 invocations, against 59 solves and 5,868 invocations for endpoint selection and 58 solves and 7,075 invocations for full expansion as archived. It used fewer invocations than endpoint selection at 3 roots. On these roots and budgets, global merging under the textual key would therefore have saved 138 invocations (2.4%) beyond sibling-only selection.

At completely expanded nodes of the endpoint-selection searches, 760 children were discarded because an earlier sibling had the same key; 741 of these collisions were between two of the 24 generic programs, and the discarded child was never the one produced by a supplied authored step. The most frequent pairs were:

| Pair (lexical heads) | Collisions |
|---|---:|
| `ring/ring_nf` | 194 |
| `aesop/aesop` | 164 |
| `norm_num/ring` | 80 |
| `norm_num/ring_nf` | 76 |
| `norm_num/simp` | 71 |
| `simp/simp_all` | 60 |
| `constructor/constructor` | 42 |
| `norm_num/simp_all` | 24 |

The pair `aesop`/`aesop` denotes the two Aesop configurations, and `constructor`/`constructor` the programs `constructor` and `constructor <;> try assumption`. Deduplication by tactic head lost 2 roots solved by full expansion and gained none.

Of the 760 collisions, 311 involved children whose key equals that of the expanded node; every policy discards these as cycles, so they cost nothing. Most came from `ring`, `ring_nf`, and `norm_num` leaving the printed state unchanged. The pairs among the other 449 collisions were:

| Pair (lexical heads), child differs from the expanded node | Collisions |
|---|---:|
| `aesop/aesop` | 164 |
| `norm_num/simp` | 70 |
| `simp/simp_all` | 56 |
| `ring/ring_nf` | 52 |
| `constructor/constructor` | 42 |
| `norm_num/simp_all` | 24 |
| `aesop/simp_all` | 7 |
| `aesop/norm_num` | 6 |

On the 61 roots whose full-expansion log replays exactly, full expansion spent 1,616 invocations in subtrees rooted at a sibling whose key repeats an earlier sibling's. By the pair that produced the duplicate:

| Pair | Invocations | Share |
|---|---:|---:|
| `aesop/aesop` | 665 | 41.2% |
| `ring/ring_nf` | 240 | 14.9% |
| `simp/simp_all` | 219 | 13.6% |
| `norm_num/simp` | 165 | 10.2% |
| `constructor/constructor` | 161 | 10.0% |
| `norm_num/simp_all` | 85 | 5.3% |
| `ring/simp` | 27 | 1.7% |
| `ring_nf/simp` | 27 | 1.7% |
| `aesop/simp_all` | 27 | 1.7% |

With `ring_nf`, one Aesop configuration, and `constructor <;> try assumption` removed from the generic panel, the replay was complete for 54 roots. Full expansion and endpoint selection both solved all of them, with 3,470 and 3,302 invocations (190 and 183 expanded nodes), 4.8% fewer under endpoint selection; with the original panel the same roots used 5,134 and 4,185 invocations. No loss occurred.

The four roots for which the global-merging replay is incomplete were all unsolved by both policies within the 768-invocation budget:

| Root | Replay stopped because | Invocations replayed | Nodes replayed |
|---|---|---:|---:|
| `01d621e53777` | needed a node absent from the logs | 616 | 23 |
| `681706ddd36d` | needed a node whose logged expansion is incomplete | 588 | 20 |
| `a9cc2141a353` | needed a node absent from the logs, with the budget already used | 768 | 28 |
| `9ca08a37fe22` | needed a node absent from the logs | 690 | 24 |

19 collisions involved a supplied authored step. The supplied step's child was never discarded; it was kept once, and in that case only because of its promotion to rank four.

## S20. Strict current-v4.27 external frame

The zero-scientific-tactic recruitment stage exhausted its 52-repository frozen frame. Thirty-three repositories passed qualification, four were definitively ineligible, and 15 were operationally unresolved; lineage analysis retained 32 lineage-deduplicated representatives. The strict external frame (archive label: replication) froze all 32 representatives and 16 authored-replay-qualified roots per repository before scientific execution. Every one of the 512 roots produced a worker receipt, all 512 were evaluable, and all 11,776 requested candidate invocations were recorded. Each root is the first traced tactic of its theorem, and at 474 roots it is the first tactic of the theorem's top-level proof (Section S2). There was no missing-root imputation, scientific repository replacement, or manual reconciliation.

| Repository | Full-panel frequency | Frequency after genealogy deduplication | Cross-family roots | Nonterminal roots |
|---|---:|---:|---:|---:|
| `Paraxiom/scheming-proofs` | 62.50% | 31.25% | 5/16 | 8/16 |
| `NethermindEth/poseidon2-fv` | 68.75% | 37.50% | 7/16 | 11/16 |
| `beowulf127/wowii144-lean` | 75.00% | 25.00% | 9/16 | 11/16 |
| `galvusdamor/lean4-search-algorithms` | 68.75% | 12.50% | 5/16 | 10/16 |
| `LoganEvans/litlib4` | 81.25% | 12.50% | 5/16 | 13/16 |
| `danuaemx/lean-257-2` | 93.75% | 37.50% | 10/16 | 15/16 |
| `mirajcs/IsoperimetricInequality` | 100.00% | 37.50% | 10/16 | 16/16 |
| `katydid/paper-2026-verified-filter-lean` | 31.25% | 18.75% | 3/16 | 2/16 |
| `Pjotr5/IndependentTransversals` | 18.75% | 6.25% | 2/16 | 3/16 |
| `fc0web/lean-d-fumt8` | 81.25% | 81.25% | 13/16 | 0/16 |
| `ericmerle3789/collatz-conditional-cycles` | 93.75% | 50.00% | 9/16 | 15/16 |
| `rupakm/leslie` | 31.25% | 12.50% | 5/16 | 1/16 |
| `AxiomMath/erdos-public` | 81.25% | 31.25% | 7/16 | 13/16 |
| `ilyasergey/lean-move` | 100.00% | 31.25% | 6/16 | 13/16 |
| `TPColor/bastien-khormali-conjecture` | 100.00% | 31.25% | 8/16 | 16/16 |
| `primateria/erdos608` | 75.00% | 18.75% | 4/16 | 12/16 |
| `Jostamon/erdos274-hs-abelian` | 62.50% | 43.75% | 8/16 | 9/16 |
| `paolino/keri-lean` | 12.50% | 12.50% | 2/16 | 1/16 |
| `abcrtzyn/sudoku_prover` | 87.50% | 12.50% | 4/16 | 12/16 |
| `mkwatson/unique-sums-notes` | 93.75% | 56.25% | 9/16 | 14/16 |
| `MaskoMys/Collatz-Binary-Topology` | 100.00% | 12.50% | 10/16 | 16/16 |
| `korbexmachina/GlimpseOfLean` | 62.50% | 31.25% | 6/16 | 5/16 |
| `qscqesze/graffiti-pc-conjecture-141` | 31.25% | 6.25% | 5/16 | 5/16 |
| `Robertboy18/aint26-lean-solutions` | 68.75% | 25.00% | 4/16 | 11/16 |
| `KitaKen1/bezier-bernstein-voronovskaja-lean` | 100.00% | 18.75% | 3/16 | 16/16 |
| `repowazdogz-droid/omega-lean-proof` | 37.50% | 12.50% | 3/16 | 3/16 |
| `grenewode/LeanServer` | 62.50% | 37.50% | 8/16 | 4/16 |
| `alexoltean61/msphml-lean` | 100.00% | 37.50% | 8/16 | 8/16 |
| `scidonia/vericode` | 12.50% | 6.25% | 2/16 | 0/16 |
| `pablo-vs/discrete-game-theory` | 62.50% | 6.25% | 1/16 | 9/16 |
| `YijunYuan/HarderNarasimhan` | 93.75% | 43.75% | 8/16 | 15/16 |
| `tobiasosborne/ProjSeminorm` | 68.75% | 43.75% | 7/16 | 11/16 |

The corrected full panel produced 355/512 positive roots, an equal-weight repository macro frequency of 0.693359375, median repository frequency 0.71875, and descriptive two-level interval [0.591796875, 0.7890625]. Repository frequencies ranged from 0.125 to 1.0. Leave-one-repository-out means ranged from 0.6834677 to 0.7116935. The 512 roots came from 213 files; equal weighting of files within repositories gave 0.7058819971.

The genealogy-deduplicated view retained 141/512 positives (0.275390625; interval [0.208984375, 0.34765625]). Cross-family witnesses occurred on 196 roots in all 32 repositories, and nonterminal witnesses on 298 roots in 30 repositories. There were 124 distinct cross-head pairs, 87 recurring in at least two repositories. The most frequent pairs were `aesop`/`aesop?` (255 roots in 26 repositories), `ring`/`ring_nf` (161 roots in 18), `aesop?`/`simp_all` and `aesop`/`simp_all` (117 roots in 23 each), `simp`/`simp_all` (104 roots in 30), and `norm_num`/`simp` (70 roots in 18). On 60 positive roots, `aesop`/`aesop?` was the only qualifying pair. All roots were evaluable, so complete-case and missingness-bound estimates coincide.

Under the structural endpoint, 57 of the 355 positive roots had terminal witnesses only. After deduplication, 141 roots were positive, 65 through terminal witnesses only and 76 with a nonterminal witness, in 21 of the 32 representatives. The most frequent deduplicated pairs were `norm_num`/`simp` (70 roots), `aesop`/`simp` (58), `solve_by_elim`/`trivial` (46), `constructor`/`solve_by_elim` (41), `constructor`/`trivial` (40), and `rfl`/`trivial` (37). Removing `exact?` lowers the full-panel count from 355 to 353; the conservative recount, the implementation grouping, and the parse strata are reported in Section S8.2. At the 260 roots in 18 representatives where all 23 programs parsed, 220 roots were positive under the structural record and 213 had a nonterminal witness; at the 252 roots with parse failures, 135 and 85. Recomputed from the same stored executions under the textual endpoint, the full panel had 321 positive roots (255 nonterminal, 66 terminal only) and the deduplicated panel 132 (68 nonterminal, 64 terminal only); raw and textual counts are identical. The label correction added 78 full-panel positives and removed none, and the 141 deduplicated positives are the same roots before and after the correction.

The original deterministic audit reproduced the original labels and summaries; it did not detect the label-extraction defect. The correction layer independently checked the direct pair predicate against endpoint-group aggregation and reproduced every archived root indicator before relabeling. The archived full-panel count was 277; the corrected count is 355. Candidate programs, their order, execution statuses, and structural endpoint hashes are unchanged. Corrected intervals use 20,000 repository/root resamples, NumPy PCG64 seed 20260918, and linear percentile quantiles. This post-outcome correction supersedes the external summary statistics, not the frozen execution frame or source archives.

The seven candidate views of Section S4, recomputed for the strict frame from the stored executions (post hoc):

| Candidate view | Textual: positive / nonterminal | Structural: positive / nonterminal |
|---|---|---|
| Full panel | 321 / 255 | 355 / 298 |
| No heads ending in ? | 226 / 165 | 292 / 238 |
| No `aesop` | 231 / 165 | 295 / 238 |
| No `aesop?` | 231 / 165 | 295 / 238 |
| No `aesop` + `aesop?` | 213 / 149 | 273 / 217 |
| No direct suggestions/control wrappers | 226 / 165 | 292 / 238 |
| After genealogy deduplication | 132 / 68 | 141 / 76 |

### S20.1. Root-level multiplicity from the same executions

These descriptive summaries use all 512 roots and the full 23-candidate panels. Successful candidates include initial-state-preserving executions; endpoint classes include their initial endpoint when present. Duplicate successful candidates equal successful candidates minus distinct structural endpoints. Qualifying pairs instead require different lexical heads and a shared non-initial endpoint, matching the primary witness definition. Quartiles use linear interpolation.

| Per-root quantity | Minimum | Q1 | Median | Q3 | Maximum |
|---|---:|---:|---:|---:|---:|
| Successful candidates | 0 | 2 | 4 | 7 | 15 |
| Distinct successful structural endpoints | 0 | 2 | 3 | 3 | 6 |
| Qualifying cross-head candidate pairs | 0 | 0 | 1 | 4 | 67 |
| Duplicate successful candidates | 0 | 0 | 1 | 3 | 12 |

The binary root indicator and these multiplicity summaries answer different questions: occurrence of at least one witness versus the number of observed alternatives or agreements. None is a predicted percentage search speedup. Root-level corrected rows and the correction script accompany the manuscript revision as an additional analysis layer.
