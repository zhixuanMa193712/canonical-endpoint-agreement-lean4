# Experiment 63: strict current-v4.27 repository recruitment

Experiment 63 is a recruitment and qualification experiment only. It executes
zero scientific candidate tactics. Its purpose is to determine whether at least
38 lineage-distinct external repositories can be qualified under a corrected,
strict Lean v4.27 protocol.

## Why Exp61 consumed disk despite about 300 GB initially being free

The prior backend copied the complete Lean toolchain prefix into every retained
repository at `.lake/packages/lean4`. Each passing checkout also retained its
Mathlib/dependency cache, build products and LeanDojo AST output. The failure was
therefore cumulative across concurrent and retained repositories; there is no
evidence that one repository itself required 300 GB.

Exp63 runs heavy qualification one repository at a time, hardlinks the immutable
Lean prefix when the filesystem permits, measures physical free-space loss from
the beginning of each repository, rejects/stops a repository at 100 GiB of new
physical allocation, retains at least 150 GiB globally, and removes the scoped
Exp63 checkout after every outcome. A repository that genuinely needs more than
100 GiB is not eligible under this protocol; this is still far below the roughly
300 GB discussed, while leaving a 150 GiB safety reserve on the shared disk.

## Why this is strict v4.27 recruitment rather than blind recruitment

Before any build, Exp63 exhaustively partitions GitHub repository search by
creation date so every search cell stays below GitHub's 1,000-result ceiling.
It then accepts only the current default-branch content-addressed commit of a
public, non-fork, non-archived repository with:

- root `lean-toolchain` exactly `leanprover/lean4:v4.27.0`;
- a root license and root Lake project file;
- no prior use as a scientific repository in this project;
- at least 16 conservative repository-authored tactic-proof declarations after
  excluding dependency, generated, benchmark, example and test paths.

This strict frame is frozen before build/trace. Final acceptance additionally
requires an unmodified build, Lean 4.27 runtime, LeanDojo trace, at least 16
trace-qualified roots, successful empty-candidate authored replay, and less than
20% source overlap with earlier accepted lineage representatives.

## One integrated server command

Run the following block from the server. A GitHub token is required for the
complete search; the block reuses an authenticated `gh` session if available.
By default the pipeline performs network/static discovery immediately and waits
for any Experiment 62 process to finish before heavy qualification.

```bash
cd /home/music/mzz/MZX
unzip -o experiment63_strict_v427_recruitment.zip
bash experiment63_strict_v427_recruitment/run_experiment63_server_safe.sh
```

The launcher always runs as a child Bash process. A missing token, Conda error,
or missing artifact exits only the launcher and returns control to the current
terminal; it cannot terminate the interactive shell.

## One integrated monitor command

```bash
cd /home/music/mzz/MZX && \
export EXP63_ROOT=/home/music/mzz/MZX/artifacts/v63/strict_v427_recruitment && \
date && \
pgrep -af 'experiment63_strict_v427_recruitment/run_experiment63.py' || echo EXP63_PROCESS_NOT_FOUND && \
tail -n 40 "$EXP63_ROOT/logs/pipeline.log" 2>/dev/null || true && \
if [ -s "$EXP63_ROOT/qualification/progress.json" ]; then jq '{completed_repositories,qualified_repositories,lineage_representatives,definitive_ineligible,operationally_unresolved,remaining_candidates,conservative_upper_bound,repository_target,target_reached,futility_reached,disk_free_bytes,stopping_reason}' "$EXP63_ROOT/qualification/progress.json"; fi && \
df -h /home/music/mzz/MZX
```

The final integrity audit is written to
`$EXP63_ROOT/audit/audit.json`. Operational failures remain unresolved; they are
not silently converted to scientific or repository ineligibility.
