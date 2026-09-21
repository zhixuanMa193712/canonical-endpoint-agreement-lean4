# Artifact Manifest

The following local bundles were independently checksum-verified on the manuscript machine. Byte counts and hashes are immutable identifiers; public repository identifiers are intentionally left unresolved until deposition.

| Archive ID | Local bundle | Bytes | SHA-256 | Evidential role |
|---|---|---:|---|---|
| Exp48 | `experiment48_fix1_mac_analysis_bundle.zip` | 801,359 | `fb5b08d9b6ef73ec7530f06f9d4f28af26a9d23dd7a1dd89f21788774cd34fd3` | Sole Tier-1 confirmation and row-level Mac reconstruction |
| Exp49 | `experiment49_candidate_endpoint_robustness_results.zip` | 75,658,652 | `f57f6938c5de6d32339f2ca9e8cb2789ceed1dd2263feb7155ee76b35caefdc2` | Same-root candidate ablation and strict endpoint construct check |
| Exp50 | `experiment50_independent_reexecution_fix1_results.zip` | 77,906,720 | `111e3e2e9b0686dc18240120ee065953a3d28cf09f3dd39ac3515c5542a8f78f` | Same-server independent implementation, order, and fresh-process re-execution |
| Exp51 | `experiment51_external_repository_replication_fix3_results.zip` | 12,602,870 | `f8c84a92ef4a7dc025a9f7918a0f16af91160acb112bb0578ee0bf431057511b` | Twelve-repository screened-frame measurement; audited but precision-inconclusive |
| Exp52 | `experiment52_continuation_probe_fix4_results.zip` | 31,698,260 | `316fae4c4de34c249edbc06b7c25222e829154abb8c87ee7ad14215d8803ee73` | Immediate continuation probe; audited but information-inconclusive |
| Exp53 | `exports/experiment53_cross_machine_subset_results.zip` | 375,350 | `fd89f8ed99f98f9db251b3736527eab8741affd5e9008e2608761cf8dcf2240a` | Exact second-machine re-execution of a frozen 16-root subset |
| Exp54 | `experiment54_effect_aware_depth2_fix3_results.zip` | 8,730,588 | `af8b69ff24808f635b73da14c33eece875281ede81a695f86b704366ab0a05b0` | Frozen branch-selection intervention; audited scheduled-call-reduction--coverage trade-off |
| Exp59 | `experiment59_four_policy_confirmation_fix1_results.zip` | 182,734,447 | `50c5df747c206fac992c38f9e7e741cfff03b9e655fa16566a30996dc313a2e3` | Prospectively frozen miniF2F/PutnamBench four-policy confirmation; actual-call efficiency measured, paired coverage unavailable for one root |
| Exp62 | `experiment62_multistep_solvable_search_fix1_results.zip` | 4,510,824 | `b2960650f01811d333f0ed4beea422c00d9149eb1f5eac7c55f1333a75230f57` | Prospectively frozen oracle-assisted multi-step four-policy confirmation (archive label: witness-injected); paired full-only loss and tactic-call efficiency measured |
| Exp63 | `experiment63_strict_v427_recruitment_results.zip` | 37,221,373 | `227f649021399d1c994d0d0bc00e02103cc0e30188256c15f4ed75cd63fa02fd` | Complete zero-scientific-tactic current-commit recruitment, strict v4.27 qualification, and lineage ledger |
| Exp64 | `experiment64_strict_v427_external_replication_results.zip` | 10,930,864 | `2aaebc31501b5946a6dcfb7a279d2dda0cdd4cf20160f7e49ec63674e5411130` | Strict current-v4.27 external replication over 32 lineage-deduplicated representatives and 512 roots |

## Integrity and archive labels

The table is a lookup crosswalk, not an experimental sequence. Internal numbers and `fix` suffixes identify immutable files and are not renumbered. Final analyses retain all frozen observations, including unavailable coverage outcomes. The archives preserve execution receipts, protocol histories, and superseded diagnostics for audit without treating those records as additional independent experiments.

The confirmation audit verifies 220 manifest-listed payloads and reconstructs 198 rows, of which 96 are confirmation roots (Section S2). The multi-step audit reconstructs all 256 confirmation jobs; the strict external audit reconstructs all 512 roots and 11,776 candidate invocations. Section S16 describes the independent offline reconstruction of the derived tables.

## Deposition fields

- Public artifact repository: `https://doi.org/10.5281/zenodo.22110052 (reserved; publication not yet verified)`
- Persistent DOI/accession: `10.5281/zenodo.22110052`
- Artifact license: `CC BY 4.0 for original data organization and documentation; upstream terms for third-party content; see LICENSE_STATUS.md`
- Third-party source and license notice: prepared in the release audit; final author confirmation pending
- Embargo or access restriction: none planned; final author confirmation pending

Submission must stop until a clean-room download from the public record reproduces all eleven hashes or the table is revised to the deposited archive identities.

The v1.21 external-label correction is an additional analysis layer, not one of the eleven original execution archives. Public release must include `reanalyze_heads.py`, the corrected per-root rows and summaries for both external frames, the source-file-cluster sensitivity, and their file hashes. The original audit hashes certify the original archive reconstruction, not the corrected numerical summaries.
