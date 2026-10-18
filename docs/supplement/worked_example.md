# Supplementary Worked Example

## Archived identity

- Repository: `ImperialCollegeLondon/FLT`
- Commit: `1d5a9a2c4b2027b50cde88ecfa8f9b8e9a27c966`
- Theorem: `AbsoluteValue.pos_of_pos`
- Source: `FLT/Mathlib/Algebra/Order/AbsoluteValue/Basic.lean`, lines 56–57
- Theorem ID: `cf821ba8b49ebdd2f0cd5a19395ecdf58f9023a4afd8fc76f12f53cf2a173d8b`
- Source SHA-256: `05a596a927fdbc825e5e7045a53d7c51c628613ba9044566d172835fe500acc5`
- Root-state SHA-256: `8d1bb10a527ddb6f2cd51cd9fa42debdceaed627dc47ae623797361f3ec0595a`
- Authored tactic: `rwa [AbsoluteValue.pos_iff] at hv ⊢`

## Displayed starting state with normalized identifiers

```text
F : Type u_1
S : Type u_2
inst<GEN>² : Field F
inst<GEN>¹ : Field S
inst<GEN> : LinearOrder S
v w : AbsoluteValue F S
a : F
hv : 0 < v a
⊢ 0 < w a
```

## Independent candidate branches

| Candidate | Parsed head | Frozen family | Success | Terminal | Endpoint SHA-256 |
|---|---|---|---|---|---|
| `simp` | `simp` | simplification | Yes | No | `88572d5b854271f6a975b9a6a17fb4c7d6ff37787256c73f69c6a035eff1bece` |
| `norm_num` | `norm_num` | arithmetic normalization | Yes | No | `88572d5b854271f6a975b9a6a17fb4c7d6ff37787256c73f69c6a035eff1bece` |

Both branches produced the following displayed state. Generated instance identifiers use the frozen textual normalization; the universe levels remain explicit.

```text
F : Type u_1
S : Type u_2
inst<GEN>² : Field F
inst<GEN>¹ : Field S
inst<GEN> : LinearOrder S
v w : AbsoluteValue F S
a : F
hv : 0 < v a
⊢ ¬a = 0
```

The endpoint differs from the initial state, retains one goal, and has equal textual content in the two branches. It is therefore a witness with different tactic heads and families, a changed endpoint, and one remaining goal under the definition of main Section 2.3. The row also contains other terminal same-endpoint pairs; those are not needed for this example.

The example does not compare proof terms, messages, time, or future trajectories. It should never be described as a global replacement rule for `simp` and `norm_num`.

## Additional archived endpoint cases

| Repository and theorem | Programs | Observed endpoint relation | Purpose |
|---|---|---|---|
| FLT, `TwoSidedIdeal.span_singleton_eq_bot` | `simpa`; `simp_all` | Textual and structural; terminal | Same-genealogy programs with different parsed heads |
| FLT, `RestrictedProduct.isOpenMap_linearMap_of_surjective` | `simp_all`; `aesop` | Structural only; nonterminal | Generated local names differ in rendering, while deterministic alpha-normalized structure agrees |
| Carleson, `TileStructure.Forest.adjoint_density_tree_bound1` | `norm_num`; `ring` | Textual only; nonterminal | Printed residual goal agrees, while strict structural records differ |

The two disagreement cases are why the manuscript does not order the frozen textual and structural canonicalizers by refinement. These are archived examples selected to explain already reported endpoint-confusion categories; they do not add roots or outcomes.
