# Experiment 53 Preregistration — Cross-Machine Frozen-Subset Re-execution

> Status: **FROZEN BEFORE EXP53 EXECUTION**  
> Protocol: `experiment53-cross-machine-subset-reexecution-v1`  
> Scientific role: execution reproducibility only; no new prevalence or confirmation claim

## Research question

Does a second physical Mac, using independently reconstructed checkouts at the exact Lean v4.27.0 commits, reproduce the registered Exp51 execution status and endpoint content for a portable frozen subset?

## Source evidence and immutable boundary

Exp53 is anchored to the final Exp51 Fix3 bundle with SHA-256 `f8c84a92ef4a7dc025a9f7918a0f16af91160acb112bb0578ee0bf431057511b`. It does not change the Exp51 decision, rerun Exp51 inference, or add repositories to any prevalence estimate. Exp48 remains the sole Tier-1 confirmation; Exp51 remains `inconclusive`; Exp52 remains `continuation_inconclusive`.

The portable registered content excludes absolute paths, process identifiers, elapsed time, stdout/stderr bytes, and diagnostic wording. It includes source and target identities, live-prestate identity, authored replay, all 23 candidate statuses, and raw, `text48`, and strict endpoint content hashes and metadata for every executable branch.

## Frozen subset

Repository selection is outcome-blind. Sort the twelve Exp51 repositories by the UTF-8 byte order of the exact slug and take the first four. Within each selected repository, hash the tuple `(theorem_id, source_file_sha256, file_path, target_pos, target_end_pos)`, sort by that hash, and take the first four roots. The resulting sample has four repositories, four roots per repository, sixteen roots, and 368 candidate attempts.

This subset is an audit sample rather than a scientific sample. It cannot estimate recurrence, rate, structural breadth, or continuation behavior.

## Execution

Each second-machine checkout must be independently materialized on macOS at the frozen commit, use Lean v4.27.0, build without source edits, and match every selected source-file hash. The compile-only preflight rejects the source-server hostname and non-Darwin systems, elaborates zero theorem sources, and executes zero candidates. Scientific execution then starts one fresh Lean process per root and evaluates the exact 23-candidate order through the archived Exp51 live-`TacticInfo` worker. Each root may be attempted once. A prior claim without a row is retained as an interruption and is not retried.

## Decision

- `invalid_execution`: an environment, source, target, authored-replay, completeness, or one-attempt gate fails.
- `cross_machine_exact`: all sixteen roots, 368 statuses, and every registered executable endpoint, initial endpoint, and authored endpoint match exactly.
- `cross_machine_mismatch`: execution is complete and evaluable but at least one registered content field differs.

No manual reconciliation is permitted. A mismatch is retained with its field path. A positive result supports cross-machine reproducibility of the registered subset only. It does not establish runtime identity, machine independence for all roots, proof-term equality, state-independent substitutability, or improved theorem proving.
