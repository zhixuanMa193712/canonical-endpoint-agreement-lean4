# Literature-Gap Matrix

## Search boundary

The literature freeze for this draft is **1 September 2026**. Searches combined terms for Lean proof state, tactic effect, tactic/operator representation, duplicate-state pruning, state merging, proof trace, proof query, goal clone, and counterfactual tactic execution. Bibliographic fields were checked against publisher, proceedings, or official venue pages. The matrix distinguishes an unstudied research question from an absent technical ingredient: prior systems already execute tactics, record states, learn from effects, prune duplicate proof states, and merge convergent states.

## Closest-neighbor comparison

| Work | Primary object and purpose | Executes or records effects? | Same exact live pre-state? | Counterfactual alternatives? | Exact canonical endpoint relation as estimand? | Cross-repository recurrence measurement? | Boundary relative to this paper |
|---|---|---:|---:|---:|---:|---:|---|
| Lean 4 [1] | Extensible prover and metaprogramming framework | Yes | Infrastructure | Possible | No | No | Supplies execution substrate, not the empirical estimand |
| Pantograph [2] | Machine-facing Lean interaction and data extraction | Yes | Yes, through an interaction interface | Yes | No | No | Interface contribution rather than a prespecified recurrence study |
| Proof-state snapshotting [22] | Reuse one elaborated Lean proof state across tactic branches to reduce reconstruction cost | Yes | Yes, from one captured state | Yes | No | No | Branch-startup and wall-time engineering rather than endpoint-agreement frequency |
| LeanDojo [3] | Repository tracing, interaction, and retrieval-augmented proving | Yes | Yes | Yes | No | No | Infrastructure and proving benchmark rather than endpoint-agreement measurement |
| Aesop [4] | White-box best-first automation | Yes | Internal search states | Yes | No | No | Candidate program appearing in the frozen library, not a measurement protocol |
| PACT [5] | Learning from proof artifacts for theorem-proving models | Records authored effects | State-conditioned training examples | Not the target | No | No | Prediction/completion objective |
| ASTactic [21] | Learned Coq tactic-program generation with depth-first search | Executes generated tactics | Search-state conditioned | Yes | Duplicate proof states trigger backtracking, not an endpoint-frequency estimand | No | Direct duplicate-state-pruning predecessor; evaluates proving rather than endpoint recurrence |
| TacticToe [19] | Learned HOL4 tactic policy inside Monte Carlo tree search | Executes tactic-level actions | Search-state conditioned | Yes, during search | No | No | Optimizes proof search and solve rate rather than measuring endpoint frequency |
| Learning Proof Transformations [20] | Predict a tactic from a Coq before/desired-after transformation | Records and predicts transformations | Before state plus desired after-state | Dataset-derived alternatives | After-state equality modulo alpha-equivalence is a target condition, not an endpoint-frequency estimand | No | Closest transformation-conditioned synthesis work; it trains predictors and evaluates proof shortening/suggestion |
| CARTS [6] | Effect-aware candidate diversity and search calibration | Yes | Yes during search | Yes | No | No | Uses effects to guide search rather than estimating exact endpoint agreement |
| 3D-Prover [7] | Effect-, success-, and time-aware tactic representations | Yes | Yes during evaluation | Yes | No | No | Learns diversity for selection rather than measuring recurrent equality |
| Modeling Tactics as Operators [8] | Representations learned from before/tactic/after triples | Records authored effects | Yes for recorded triples | No frozen alternative panel | No | No | Closest representation-level neighbor; equality and recurrence are not the response variables |
| Proof planning and method learning [9,10] | Reusable multi-step proof methods | Usually symbolic/trace based | Not as the focal estimand | Varies | No | No | Studies plans, whereas this paper is one-step and state-indexed |
| SEPIA, ML4PG, proof mining, TacMiner [11–14] | Sequence automata, clusters, mined subgraphs, reusable tactic libraries | Mostly authored traces | Not as a frozen branch point | Generally no | No | Corpus recurrence of structures, not equality of counterfactual endpoints | Study trajectories and reusable procedures in authored proofs rather than independent alternatives at one branch point |
| Querying Proofs [15] | Queries over hierarchical proof objects and input/output goals | Records proof objects | For authored steps | No | No | No | Establishes proof effects as queryable data; alternatives are not executed at a frozen live state |
| Goal clone detection [16] | Exact/generalized/alpha-equivalent goals across Rocq developments | Analyzes recorded goals | No common departure state required | No | No | Yes, for cloned goals | Finds similar obligations; this paper compares branches leaving the same state |
| AlphaProof [17] | Reinforcement-learning search with merging of tactics reaching the same Lean state | Yes | Yes during search | Yes | Operationally, for merging | No endpoint-frequency estimand | Most direct Lean operational neighbor; uses convergence for search, not as a prespecified empirical relation |
| LeanTree [18] | Factorized states for parallel proof search and reuse | Yes | Yes during search | Yes | State reuse, not this estimand | No | Shows utility of state reuse without measuring candidate-relative recurrence |

## Gap statement supported by the matrix

The defensible gap is narrow. Prior work does **not** ignore tactic effects or convergent states. The frozen search identified no archival study that combines independent execution of alternative one-step programs from the same recovered live Lean state, a frozen endpoint canonicalizer, cross-repository recurrence as the response variable, and candidate, endpoint, execution-order, process, and machine-level audits. The contribution is therefore a measurement object and validation protocol, not a priority claim over all effect-aware theorem-proving work.

ASTactic's duplicate-state backtracking statement and bibliographic metadata were verified against the official PMLR paper page and PDF (PMLR 97:6984--6994). TacticToe metadata and study purpose were verified against the official Journal of Automated Reasoning page (DOI `10.1007/s10817-020-09580-x`). Learning Proof Transformations metadata, authors, page range, and transformation-conditioned objective were verified against the official Springer FroCoS 2023 chapter page (DOI `10.1007/978-3-031-43369-6_13`).

## Current-work integration

The official arXiv v2 record for Shen and Shi's 2026 preprint, Keep the Proof State Live: Snapshotting for Efficient Tactic Search in Lean 4 (arXiv:2605.25556; DOI `10.48550/arXiv.2605.25556`), was checked on 1 September 2026. The work captures an elaborated Lean proof state and reuses it across tactic branches to avoid repeated import loading and theorem-body elaboration. Its reported object is branch-startup and wall-time efficiency, not same-live-state canonical-endpoint frequency or cross-repository recurrence. It is therefore cited in the main Related Work and included in the matrix as a close engineering neighbor rather than left on a watchlist.
