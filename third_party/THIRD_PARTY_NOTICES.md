# Third-party notices and licence supplement

Packaging version 1.22.2, 2026-09-21. This supplement accompanies manuscript v1.22.
It corrects incomplete notices in the earlier packaging; it does not change scientific results.

## Scope and priority

Original experiment ZIPs remain byte-for-byte unchanged. Their source-derived text,
including theorem/tactic expressions, proof states, generated wrappers and source-bearing
logs, retains applicable upstream terms. The licence and attribution files in this
directory accompany those immutable archives. Read this supplement together with them.
Historical `redistribution_allowed=yes` and `notice_included=yes` entries are not a
current legal-clearance certificate; this explicit inventory supersedes that implication.

Original dataset organization and documentation by Zhixuan Ma and Zhengwei Shen are
CC BY 4.0. That grant does not relicense upstream material or unlicensed software.
Nothing here asserts that every mathematical fact, short tactic or execution output
is copyrightable, or that merely referencing a dependency redistributes its source.

## Materials and changes

Third-party materials include extracted theorem/tactic/state fields, benchmark witness
sequences, and generated probes containing source-derived expressions. The study authors
performed selection, extraction, Lean execution, state canonicalization, probe construction
and statistical analysis. These are research transformations, not upstream-authored results.
Per-source attribution is in SOURCE_FILE_ATTRIBUTION.md and source_file_attribution.json.
The original source is identified by fixed commit, path and available file hash.
Raw result archives are preserved as historical records, not silently rewritten to insert headers.

## LeanDojo software and Benchmark 4 are distinct sources

LeanDojo Team, LeanDojo v4.20.0, commit
`3bbc4c02fb8a058b282c8d3982a02d6563f3b08a`:
https://github.com/lean-dojo/LeanDojo/tree/3bbc4c02fb8a058b282c8d3982a02d6563f3b08a
Copyright (c) 2023 LeanDojo Team. MIT licence is included under licenses/.
The experiment51_trace_runtime adapter contains original upstream fragments and study
modifications for Lean 4.27; it does not contain an unmodified full LeanDojo distribution.

LeanDojo Team, *LeanDojo Benchmark 4*: https://doi.org/10.5281/zenodo.8040109
The upstream benchmark licence notice supplied with the source dataset states CC BY 2.0:
https://creativecommons.org/licenses/by/2.0/
This attribution applies to the upstream benchmark extraction, not to the entire new deposit.
Exp62 derives a selected witness/tactic frame from this benchmark. Row hashes and source
indices are retained in the original Exp62 candidate_frame.jsonl; a precise Zenodo version
identifier for the locally used benchmark download was not recorded and is not invented.
The underlying mathlib4 commit is `29dcec074de168ac2bf835a77ef68bbe069194c5`.
Three of 192 candidate rows refer to Batteries files; its pinned dependency commit is
`bba0af6e930ebcbabfacf021b21dd881d58aaa9d`, verified from mathlib lake-manifest.json.
Applicable mathlib/Batteries Apache-2.0 terms and attribution also remain in force.

## Specific notice corrections

- All available fixed-commit root licence texts reviewed for Exp63/64 are included,
  including the nine MIT sources in Exp64. Each original copyright line is preserved.
- Paraxiom/scheming-proofs and qscqesze/graffiti-pc-conjecture-141 NOTICE files are
  reproduced verbatim. The latter credits Jun Qing and The Formal Conjectures Authors.
- Eric Merle's collatz-conditional-cycles source remains CC BY 4.0; the included
  upstream licence identifies Eric Merle. Research extraction and normalization are
  modifications by the study authors, with no upstream endorsement implied.
- PutnamBench's applicable Lean licence is at lean4/LICENSE, not root LICENSE:
  https://github.com/trishullab/PutnamBench/blob/34eba93650f2fa803ca6aae6dfd2c9f22d46c00d/lean4/LICENSE

## GPL source and metadata-only AGPL provenance

LegendreQF, Michael Stoll and upstream contributors, commit
`ffc076a15ac2da4f165746160677ec6b4f8b98cf`, is supplied with its original GPL v2
licence, preserved file notices, and an unmodified source ZIP under source/.
Applicable LegendreQF-derived protected portions retain GPL terms; they are excluded
from the deposit's CC BY grant. The study's source-form transformations and worker
code are in the immutable experiment archives and accompanying source_packages.
This is not a representation that a repository URL alone satisfies every GPL obligation,
nor that unrelated aggregate statistics or independent files become GPL merely by aggregation.
The precise derivative-work boundary remains subject to applicable law.

Shoumei-RTL, commit `10b3686647f1d76c853c196026cde45709c698b4`, appears in Exp63
recruitment provenance (paths/hashes/names/build status); it is not an Exp64 scientific
repository. Its AGPL v3 text is included for clarity, without asserting that these
metadata records constitute redistribution of its full program or impose AGPL on this deposit.

## Verification limits

This is a technical preservation supplement, not legal advice or a guarantee of clearance.
Exact-source licence text and observable notices have been preserved. It does not establish
ownership of upstream contributions, exhaustively audit every nested dependency, or resolve
the legal status of all generated expressions. Unresolved fetches are explicitly recorded.
The named authors' original software contributions are now licensed under Apache-2.0; see ../SOFTWARE_LICENSE_SCOPE.md. Upstream materials remain excluded from that grant.

## Repository inventory

The following entries identify actual source versions or metadata-only records; read their
scope column before treating them as copied source. Full machine-readable details are in
repositories.json. Source files have their own attribution ledger.

| Repository | Commit | Scope | Included licence/notice files |
|---|---|---|---|
| qscqesze/graffiti-pc-conjecture-141 | `d86f3c5f41191c9447ea8162d34cb116013b85a1` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/qscqesze__graffiti-pc-conjecture-141/d86f3c5f41191c9447ea8162d34cb116013b85a1/LICENSE; licenses/qscqesze__graffiti-pc-conjecture-141/d86f3c5f41191c9447ea8162d34cb116013b85a1/NOTICE |
| Paraxiom/scheming-proofs | `02ceadbd6df9bcb7f471b0214e133ed2f43e5cfc` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/Paraxiom__scheming-proofs/02ceadbd6df9bcb7f471b0214e133ed2f43e5cfc/LICENSE; licenses/Paraxiom__scheming-proofs/02ceadbd6df9bcb7f471b0214e133ed2f43e5cfc/NOTICE |
| AIDoctrine/CollatzLayerA | `5e27e335c8a1bca3b0cf2f89ee593d7bbe6d08fd` | Exp63 qualification: definitive_ineligible; Exp63 static metadata | licenses/AIDoctrine__CollatzLayerA/5e27e335c8a1bca3b0cf2f89ee593d7bbe6d08fd/LICENSE |
| taeyool/lean-flag-algebras-release | `06423a2e6c6f8d9435a8956e2b7409e210154b8c` | Exp63 qualification: operationally_unresolved; Exp63 static metadata | licenses/taeyool__lean-flag-algebras-release/06423a2e6c6f8d9435a8956e2b7409e210154b8c/LICENSE |
| MechMath/MechGeoBench | `ef1ef410ee2bc9844108f71d23e0a5aebecd6488` | Exp63 qualification: operationally_unresolved; Exp63 static metadata | licenses/MechMath__MechGeoBench/ef1ef410ee2bc9844108f71d23e0a5aebecd6488/LICENSE |
| alexoltean61/msphml-lean | `9d6559db6502bc9813dcf028d7ea26ae80e9dc93` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/alexoltean61__msphml-lean/9d6559db6502bc9813dcf028d7ea26ae80e9dc93/LICENSE |
| korbexmachina/GlimpseOfLean | `7d99667f124922bc047dc0bbb2ca6cf63edd90f8` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/korbexmachina__GlimpseOfLean/7d99667f124922bc047dc0bbb2ca6cf63edd90f8/LICENSE |
| google-deepmind/alphaproof-nexus-results | `0647711a71183c1ea492ad60860776617ce1ea88` | Exp63 qualification: operationally_unresolved; Exp63 static metadata | licenses/google-deepmind__alphaproof-nexus-results/0647711a71183c1ea492ad60860776617ce1ea88/LICENSE |
| abcrtzyn/sudoku_prover | `38bd5d3321af47bac8a0774e8dbd44d368cb9193` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/abcrtzyn__sudoku_prover/38bd5d3321af47bac8a0774e8dbd44d368cb9193/LICENSE |
| fc0web/lean-d-fumt8 | `2f4c97aee73b53378b8554b46297fb98f3a2b3c0` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/fc0web__lean-d-fumt8/2f4c97aee73b53378b8554b46297fb98f3a2b3c0/LICENSE |
| GasStationManager/ArtificialAlgorithms | `0d78ca4b92004fd539d97661e3c2eeef5099d0a8` | Exp63 qualification: operationally_unresolved; Exp63 static metadata | licenses/GasStationManager__ArtificialAlgorithms/0d78ca4b92004fd539d97661e3c2eeef5099d0a8/LICENSE |
| tamura70/lean_study | `addb8e51bf0d78285bf38dff8c18d994436d6f96` | Exp63 qualification: definitive_ineligible; Exp63 static metadata | licenses/tamura70__lean_study/addb8e51bf0d78285bf38dff8c18d994436d6f96/LICENSE |
| rupakm/leslie | `58e58b2502b2a570e4ce4fdb6b40748c3cb30e5d` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/rupakm__leslie/58e58b2502b2a570e4ce4fdb6b40748c3cb30e5d/LICENSE |
| galvusdamor/lean4-search-algorithms | `cffe2a8136e7f45de1d3507f2397d9decc0d6424` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/galvusdamor__lean4-search-algorithms/cffe2a8136e7f45de1d3507f2397d9decc0d6424/LICENSE |
| danuaemx/lean-257-2 | `53fd59dcf68dfcfbc93e213ed888ef72e6f150ba` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/danuaemx__lean-257-2/53fd59dcf68dfcfbc93e213ed888ef72e6f150ba/LICENSE |
| TPColor/bastien-khormali-conjecture | `ba950f184f1a682e3bc7d59391b4a126818d7f34` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/TPColor__bastien-khormali-conjecture/ba950f184f1a682e3bc7d59391b4a126818d7f34/LICENSE |
| AxiomMath/erdos-public | `3ccf48c78b9df4aa26e1b2f90058bdd3f61da1ab` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/AxiomMath__erdos-public/3ccf48c78b9df4aa26e1b2f90058bdd3f61da1ab/LICENSE |
| LoganEvans/litlib4 | `c689568887fbd8a7ff59c032af486c930053e77b` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/LoganEvans__litlib4/c689568887fbd8a7ff59c032af486c930053e77b/LICENSE |
| atvrager/Shoumei-RTL | `10b3686647f1d76c853c196026cde45709c698b4` | Exp63 qualification: operationally_unresolved; Exp63 static metadata | licenses/atvrager__Shoumei-RTL/10b3686647f1d76c853c196026cde45709c698b4/LICENSE |
| ilyasergey/lean-move | `ca5dbc9a6606bc60f5b57a82b733accbd8241b96` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/ilyasergey__lean-move/ca5dbc9a6606bc60f5b57a82b733accbd8241b96/LICENSE |
| mathTensor/AI4Math-Putnam2025 | `35279ef7f469f002aa2cbe90e8b3f7e5a849567b` | Exp63 qualification: operationally_unresolved; Exp63 static metadata | licenses/mathTensor__AI4Math-Putnam2025/35279ef7f469f002aa2cbe90e8b3f7e5a849567b/LICENSE |
| repowazdogz-droid/omega-lean-proof | `2fab5d1766dc40fbf8b52298c0fa9ca33a8489cf` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/repowazdogz-droid__omega-lean-proof/2fab5d1766dc40fbf8b52298c0fa9ca33a8489cf/LICENSE |
| galvusdamor/lean4-planner | `0c4ed9d804d52420b3a8842d03ab38500ba25861` | Exp63 qualification: operationally_unresolved; Exp63 static metadata | licenses/galvusdamor__lean4-planner/0c4ed9d804d52420b3a8842d03ab38500ba25861/LICENSE |
| ericmerle3789/collatz-nocycle-lean4 | `4ec239deeea642315fcb431ca0d22a09727911f3` | Exp63 qualification: qualified; Exp63 static metadata | licenses/ericmerle3789__collatz-nocycle-lean4/4ec239deeea642315fcb431ca0d22a09727911f3/LICENSE |
| mirajcs/IsoperimetricInequality | `300de78eafd39002343aa507630639f52347d335` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/mirajcs__IsoperimetricInequality/300de78eafd39002343aa507630639f52347d335/LICENSE |
| ericmerle3789/collatz-conditional-cycles | `c24633cc8999ec509782125d664b47396cb89593` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/ericmerle3789__collatz-conditional-cycles/c24633cc8999ec509782125d664b47396cb89593/LICENSE |
| Kuberwastaken/wowii-63-85-counterexample | `aec1307942b2aaaf248694822def1a4a1289fa47` | Exp63 qualification: operationally_unresolved; Exp63 static metadata | licenses/Kuberwastaken__wowii-63-85-counterexample/aec1307942b2aaaf248694822def1a4a1289fa47/LICENSE |
| RobertoZunino/ITPCourse | `258f979cc736fc2845e90ac7e0dd78c9b43ed798` | Exp63 qualification: operationally_unresolved; Exp63 static metadata | licenses/RobertoZunino__ITPCourse/258f979cc736fc2845e90ac7e0dd78c9b43ed798/LICENSE |
| katydid/paper-2026-verified-filter-lean | `742e142a028c4af82e3055a08289195b1f3f1761` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/katydid__paper-2026-verified-filter-lean/742e142a028c4af82e3055a08289195b1f3f1761/LICENSE |
| VTrelat/BEer | `d846712bf296520d4f4b39d0e0ae48211a7e4e15` | Exp63 qualification: operationally_unresolved; Exp63 static metadata | licenses/VTrelat__BEer/d846712bf296520d4f4b39d0e0ae48211a7e4e15/LICENSE |
| tobiasosborne/ProjSeminorm | `b614563b9e1ceb5e9828646c975d8c57fee9e44a` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/tobiasosborne__ProjSeminorm/b614563b9e1ceb5e9828646c975d8c57fee9e44a/LICENSE |
| manman4/LeanMathAtlas | `c6ec93594f406562eafe3a4a8d12b5006486ca78` | Exp63 qualification: definitive_ineligible; Exp63 static metadata | licenses/manman4__LeanMathAtlas/c6ec93594f406562eafe3a4a8d12b5006486ca78/LICENSE |
| Pjotr5/IndependentTransversals | `205372fe2b4b17ec77ef3f4629c43686223c1028` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/Pjotr5__IndependentTransversals/205372fe2b4b17ec77ef3f4629c43686223c1028/LICENSE |
| scidonia/vericode | `5ecd4ccc09bb133f7c34a73264d9a2291a99fb22` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/scidonia__vericode/5ecd4ccc09bb133f7c34a73264d9a2291a99fb22/LICENSE |
| pablo-vs/discrete-game-theory | `b12b2d88409864306299b03fa0c14b771fe47327` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/pablo-vs__discrete-game-theory/b12b2d88409864306299b03fa0c14b771fe47327/LICENSE |
| mike1729/goedel-workbook-lean427 | `3c2afe6bfc6bdeca6b78d1f257468164bba56966` | Exp63 qualification: definitive_ineligible; Exp63 static metadata | licenses/mike1729__goedel-workbook-lean427/3c2afe6bfc6bdeca6b78d1f257468164bba56966/LICENSE |
| ronut01/erdos1002-lean | `b7c9e7db433a64de629989c31a344f5220fe360e` | Exp63 qualification: operationally_unresolved; Exp63 static metadata | licenses/ronut01__erdos1002-lean/b7c9e7db433a64de629989c31a344f5220fe360e/LICENSE |
| akakabrian/WOW-146 | `18201d492b52a2f82a2966551aed1640c45ec13b` | Exp63 qualification: operationally_unresolved; Exp63 static metadata | licenses/akakabrian__WOW-146/18201d492b52a2f82a2966551aed1640c45ec13b/LICENSE |
| primateria/erdos608 | `b50849234b8de6cb5c642b5cb0479cab2e9e9908` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/primateria__erdos608/b50849234b8de6cb5c642b5cb0479cab2e9e9908/LICENSE |
| beowulf127/wowii144-lean | `046429d509b28c90ee2ec38ae27c1ad377c6a5fc` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/beowulf127__wowii144-lean/046429d509b28c90ee2ec38ae27c1ad377c6a5fc/LICENSE |
| Robertboy18/aint26-lean-solutions | `feb939008bbd1f0dd2b24fd40ab0e592062d9717` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/Robertboy18__aint26-lean-solutions/feb939008bbd1f0dd2b24fd40ab0e592062d9717/LICENSE |
| mkwatson/unique-sums-notes | `b982a044dc0806bcecaf111f2d72c24697bd78e9` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/mkwatson__unique-sums-notes/b982a044dc0806bcecaf111f2d72c24697bd78e9/LICENSE |
| Shashi456/erdos-formalizations | `286f856aa3fc08957b80950fd18a45aab8d045ea` | Exp63 qualification: operationally_unresolved; Exp63 static metadata | licenses/Shashi456__erdos-formalizations/286f856aa3fc08957b80950fd18a45aab8d045ea/LICENSE |
| YijunYuan/HarderNarasimhan | `e10fd2c1127dc7720bc62fd2f81f7d1577ceff3f` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/YijunYuan__HarderNarasimhan/e10fd2c1127dc7720bc62fd2f81f7d1577ceff3f/LICENSE |
| NethermindEth/poseidon2-fv | `ab3d3c4a567ee9fc99005b1527cca91c6c41edc6` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/NethermindEth__poseidon2-fv/ab3d3c4a567ee9fc99005b1527cca91c6c41edc6/LICENSE |
| paolino/keri-lean | `e54b668e546545db4dfe20b62bb2f21d417b5763` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/paolino__keri-lean/e54b668e546545db4dfe20b62bb2f21d417b5763/LICENSE |
| LoganEvans/chiral-gauge-dynamics | `f05834b9272518ab2c885ba9dda4d5e359ab6977` | Exp63 qualification: operationally_unresolved; Exp63 static metadata | licenses/LoganEvans__chiral-gauge-dynamics/f05834b9272518ab2c885ba9dda4d5e359ab6977/LICENSE |
| grenewode/LeanServer | `9dfee1c7bc10d6ef50b1adf7cc947fc3b96a08ad` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/grenewode__LeanServer/9dfee1c7bc10d6ef50b1adf7cc947fc3b96a08ad/LICENSE |
| MaskoMys/Collatz-Binary-Topology | `a9a5167830f0cd0f2b98a2afd339b46234253fd9` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/MaskoMys__Collatz-Binary-Topology/a9a5167830f0cd0f2b98a2afd339b46234253fd9/LICENSE |
| Jostamon/erdos274-hs-abelian | `2ab8a2e39e7dd7836adf577b52555f069244466f` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/Jostamon__erdos274-hs-abelian/2ab8a2e39e7dd7836adf577b52555f069244466f/LICENSE |
| schmittj/prop51-formal | `02bd8cc32582f54d36e9a0ff471a44d4d0461017` | Exp63 qualification: operationally_unresolved; Exp63 static metadata | licenses/schmittj__prop51-formal/02bd8cc32582f54d36e9a0ff471a44d4d0461017/LICENSE |
| KitaKen1/bezier-bernstein-voronovskaja-lean | `3f35c631d215b3841242275bf3ed2c59ea153a2d` | Exp63 qualification: qualified; Exp63 static metadata; Exp64 scientific | licenses/KitaKen1__bezier-bernstein-voronovskaja-lean/3f35c631d215b3841242275bf3ed2c59ea153a2d/LICENSE |
| taterowney/DSLean | `7f819f4e861bccddefb2697d28ec9bf235bbce4f` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| jlebar/vir | `c61e3517a12921395b3c043805844863901a0d60` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| provables/synthetic | `d041860f3211cd7e21d2ba3207a11a2f8fd48c40` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| acherm/agentic-chessengine-lean-codex | `071b6c32536de04f0df9a4589557ea50494ca2b7` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| gdncc/Cryptography | `883139dc0cd152a0f6f219b23aae35cbf6d67223` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| erhant/dnalang | `e729848590040942d64c4e405bfa01a42f9c485f` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| google-deepmind/formal-imo | `a85d84b97c8e88a352c136b1e29c355139609bea` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| sdiehl/kitty-cats | `81d93fa60002e115c6866d93e96490739237c524` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| google-deepmind/miniF2F | `f0a20e14c1eeccd859d51bb4c2b3ee487889c303` | Exp63 static metadata; historical_audit | licenses/google-deepmind__miniF2F/f0a20e14c1eeccd859d51bb4c2b3ee487889c303/LICENSE |
| initsecret/lightmode | `803ad4affc786dec4f85222bdd5103c7ff7cdae0` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| pimotte/verbose-lean4-testrepo | `cb9ad5b522b1f6b5560c10752231d485a42487f5` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| jkleid/erdos945-equivalence | `a8ec707e749946646455ecd749afd45169098840` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| kevinsullivan/DMT1F25 | `c3559a0acb2f92732893e02f277a77c285570e7b` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| JoshuaPurtell/lithe | `67fc8d0ada1fa17430005cb0eb60e86bae853594` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| google-deepmind/formal-putnam-like | `636c2d46b3a7d7e77a9f58209b0c17816f8d172b` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| MdRahman22/CS6501-Final-Project | `884eea90efe72ab581f973b459832990e58c89a0` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| kaito2/lean-http | `56b7523bc2e194843a035cbdb99679628523b320` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| josephmckinsey/lean-uri | `4d717ff58f42b229ac08815855087344a62ec613` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| beowulf127/wowii322-lean | `c364a407badee491944eecdde05133fd6b936309` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| Kuberwastaken/conway99-c3-orbit-restriction | `be7b0ae3394721a4c3a1375008a1dbfca44981fc` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| ClockworksCompute/ccc | `cf2f0a503c0269d47bc6467e088dd8681570944c` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| heartpunk/formalized-papers | `565872c49d22c3c4ddcafa12b189e35ea14d6511` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| Qiu233/uri | `7035449c026bc2e2b3e278b6c67ef5b7b50ef90c` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| demath-ai/formal-statements-lean | `ba7d54b8e7ee342f203313251fc5ca8cb649769c` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| JWKennington/LoopGroup | `c777923e0aff88f45c12bfdaf25a001855d85c0e` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| kaito2/lean-pq | `b6a9ed8db1ed18793f6f81f9349eead988f6cbd2` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| Paraxiom/identity-architecture-lean | `d2cf92fb6efe4d43923ce162c27a46eae9c145a0` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| ChemistMikeLam/Lean4Gists | `a316a3c81821c51be27a0e617135565d857200b7` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| MiskinAleksandr23/WOWII-1 | `eda16f6e96b313bd112351ae9859133b77d537c9` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| pandaman64/LeanToDo | `a6f118af9176fdbe0e2bcc4f073ca982dcbbb172` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| GasStationManager/SafeVerify | `b291b588a53999a7e837dda61c7dbfe8c550c814` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| josefs/logict-lean | `207120d4275ebdb4af496a38d06695a28320c1e4` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| artie2000/intro-to-lean | `cea6f0984aaea0cfc303d954cc2ce266111d9b80` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| OathTech/lean-tcb | `79d49148076114dcd3a18e11bcb82e00448cee92` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| bergmannjg/leanCurl | `d725fede14f67acc746c18eaec962f6461dee5cb` | Exp63 static metadata | Metadata-only entry; no upstream text asserted |
| trishullab/PutnamBench | `34eba93650f2fa803ca6aae6dfd2c9f22d46c00d` | historical_audit | licenses/trishullab__PutnamBench/34eba93650f2fa803ca6aae6dfd2c9f22d46c00d/lean4/LICENSE |
| AfonsoBitoque/LeanServer | `9dfee1c7bc10d6ef50b1adf7cc947fc3b96a08ad` | historical_audit | licenses/AfonsoBitoque__LeanServer/9dfee1c7bc10d6ef50b1adf7cc947fc3b96a08ad/LICENSE |
| AmosNico/validator | `97e2990e74972b8d9f0769be6903cdff4b12cec6` | historical_audit | licenses/AmosNico__validator/97e2990e74972b8d9f0769be6903cdff4b12cec6/LICENSE |
| bergmannjg/Regex | `1dc9404d9533e6888d30f1ec1807664f3620bbf4` | historical_audit | licenses/bergmannjg__Regex/1dc9404d9533e6888d30f1ec1807664f3620bbf4/LICENSE |
| dissensus-ai/lean-formalizations | `b25f4583f497a0473dc43a36f04dd6dedc0b6fd6` | historical_audit | licenses/dissensus-ai__lean-formalizations/b25f4583f497a0473dc43a36f04dd6dedc0b6fd6/LICENSE |
| fpvandoorn/carleson | `0ddd15b3b35b21a6ae175011f02fda5d1a0abd69` | historical_audit | licenses/fpvandoorn__carleson/0ddd15b3b35b21a6ae175011f02fda5d1a0abd69/LICENSE |
| ImperialCollegeLondon/FLT | `1d5a9a2c4b2027b50cde88ecfa8f9b8e9a27c966` | historical_audit | licenses/ImperialCollegeLondon__FLT/1d5a9a2c4b2027b50cde88ecfa8f9b8e9a27c966/LICENSE |
| leanprover-community/batteries | `b25b36a7caf8e237e7d1e6121543078a06777c8a` | historical_audit | licenses/leanprover-community__batteries/b25b36a7caf8e237e7d1e6121543078a06777c8a/LICENSE |
| leanprover-community/lean-auto | `7e8f3ab431d4790bd803e467d661b1be2522bfd3` | historical_audit | licenses/leanprover-community__lean-auto/7e8f3ab431d4790bd803e467d661b1be2522bfd3/LICENSE |
| MichaelStollBayreuth/LegendreQF | `ffc076a15ac2da4f165746160677ec6b4f8b98cf` | historical_audit | licenses/MichaelStollBayreuth__LegendreQF/ffc076a15ac2da4f165746160677ec6b4f8b98cf/LICENSE |
| PatrickMassot/GlimpseOfLean | `7dc816910638406f4232d23977bbcc59a335393c` | historical_audit | licenses/PatrickMassot__GlimpseOfLean/7dc816910638406f4232d23977bbcc59a335393c/LICENSE |
| RemyDegenne/brownian-motion | `f6ae873ca6043e9c9dd37a2b1c81da02580f0a9d` | historical_audit | licenses/RemyDegenne__brownian-motion/f6ae873ca6043e9c9dd37a2b1c81da02580f0a9d/LICENSE |
| spectra-research/asymptotic-tensor-rank-semicontinuity | `f3a83b4e862c84ab718163d063093ad64644c9ef` | historical_audit | licenses/spectra-research__asymptotic-tensor-rank-semicontinuity/f3a83b4e862c84ab718163d063093ad64644c9ef/LICENSE |
| thefundamentaltheor3m/Sphere-Packing-Lean | `4e45ef809c68f6e51d9a02552ba04e6fd79d0fd7` | historical_audit | licenses/thefundamentaltheor3m__Sphere-Packing-Lean/4e45ef809c68f6e51d9a02552ba04e6fd79d0fd7/LICENSE |
| Verified-zkEVM/VCVio | `0dbb0a202445c14219f505d20eb523012f78a31c` | historical_audit | licenses/Verified-zkEVM__VCVio/0dbb0a202445c14219f505d20eb523012f78a31c/LICENSE |
| verse-lab/Lentil | `7f83b7493c3aa839d1aeeeeacc5b3711116c2856` | historical_audit | licenses/verse-lab__Lentil/7f83b7493c3aa839d1aeeeeacc5b3711116c2856/LICENSE |
| YaelDillies/misc-yd | `10837040a49ab7580877d652dea7c172f69adbbf` | historical_audit | licenses/YaelDillies__misc-yd/10837040a49ab7580877d652dea7c172f69adbbf/LICENSE |
| leanprover-community/mathlib4 | `29dcec074de168ac2bf835a77ef68bbe069194c5` | Exp62 benchmark | licenses/leanprover-community__mathlib4/29dcec074de168ac2bf835a77ef68bbe069194c5/LICENSE |
| teorth/pfr | `e7278b10821f3b0fef1ed500f6666ef414931dbb` | Exp48 source/config | licenses/teorth__pfr/e7278b10821f3b0fef1ed500f6666ef414931dbb/LICENSE |
| leanprover-community/physlib | `08d3f3388230601397afab0b3a2ce4e64cc1eaae` | Exp48 source/config | licenses/leanprover-community__physlib/08d3f3388230601397afab0b3a2ce4e64cc1eaae/LICENSE |
| leanprover-community/sphere-eversion | `5ebc398fb50f29879811ad29f54ed47d4116bfe8` | Exp48 source/config | licenses/leanprover-community__sphere-eversion/5ebc398fb50f29879811ad29f54ed47d4116bfe8/LICENSE |
| leanprover-community/flt-regular | `4e2d2985158da1db38a220229a1fe8ea47dd2555` | Exp48 source/config | licenses/leanprover-community__flt-regular/4e2d2985158da1db38a220229a1fe8ea47dd2555/LICENSE |
| james18lpc/GibbsMeasure | `ac72864b90fbf034b8cff207cc3b1d8564c4c582` | Exp48 source/config | licenses/james18lpc__GibbsMeasure/ac72864b90fbf034b8cff207cc3b1d8564c4c582/LICENSE |
| kbuzzard/ClassFieldTheory | `7af4d9fe773ce82d84fe2c3230f2d4f89c50922b` | Exp48 source/config | licenses/kbuzzard__ClassFieldTheory/7af4d9fe773ce82d84fe2c3230f2d4f89c50922b/LICENSE |
| Paul-Lez/PersistentDecomp | `ca97f19a836af9f83b0728a29268bc24eea75c33` | Exp48 source/config | licenses/Paul-Lez__PersistentDecomp/ca97f19a836af9f83b0728a29268bc24eea75c33/LICENSE |
| lean-dojo/LeanDojo | `3bbc4c02fb8a058b282c8d3982a02d6563f3b08a` | LeanDojo 4.20.0 adapter fragments; MIT | licenses/lean-dojo__LeanDojo/3bbc4c02fb8a058b282c8d3982a02d6563f3b08a/LICENSE |
| leanprover-community/batteries | `bba0af6e930ebcbabfacf021b21dd881d58aaa9d` | Exp62 benchmark dependency; Apache-2.0 | licenses/leanprover-community__batteries/bba0af6e930ebcbabfacf021b21dd881d58aaa9d/LICENSE |
