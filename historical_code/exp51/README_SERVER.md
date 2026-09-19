# Experiment 51 — External Repository Replication

This package implements the preregistered two-stage Exp51 protocol. It does not
modify Exp48–50 and it does not execute Exp52. Exp52's witness, control, probe,
denominator, bootstrap, and decision rules are frozen before the first Exp51
scientific candidate is executed.

The scientific object is **state-conditioned one-step executable-effect
agreement** under the frozen `L0` and `L-mechanism-diverse` panels. The package
does not test global tactic interchangeability, proof-strategy equivalence,
proof-term equality, runtime equivalence, or theorem-proving improvement.

## Recruitment fix9 parser fix3 provenance

The protected fix0 recruitment ended with `0/20` build-trace passes and the
protected fix1 recruitment ended with `0/26`. Both executed exactly zero
scientific candidate tactics. Fix1 correctly repaired exact-ref checkout and
stop-gate mechanics, but its diagnostic showed that 19 otherwise trace-ready
rows failed because the active environment contained no importable `lean_dojo`
package or extractor.

Fix2 pins the Python AST parser to `lean-dojo==4.20.0`, verifies its packaged
upstream extractor hash, and deterministically materializes the already archived
Lean-v4.27-compatible extractor. The materialized extractor must match its
frozen SHA-256 before tracing. Parser file hashes and both extractor hashes are
recorded in a compile-free, zero-theorem, zero-candidate runtime preflight.

Fix2 then exposed a scalability defect in the sequential scheduler: complete
repository tracing can spend multiple CPU-hours on a single source file. The
server qualification receipt showed 192 available CPUs and about 974 GB of
available memory, while no scientific candidate had been run.

Fix3 changes scheduling and process isolation only. It freezes four concurrent
build slots, 26 concurrent repository slots, two Lean file processes per
repository, four enumeration slots, and a global maximum of 52 tracing
processes. It preserves complete-source tracing and the four-hour repository
timeout. It adds clean generated-trace removal and process-group termination so
partial artifacts and leaked grandchildren cannot pass a gate.

Fix3 completed all 26 qualification rows with zero scientific candidate
tactics. Fifteen repositories generated AST files and then failed during root
enumeration with shared temporary-directory and process-global-state errors.
The error families (`FileNotFoundError`, `FileExistsError`, and temporary
directory cleanup races) establish that LeanDojo's Python parser is unsafe when
multiple repository enumerations share one threaded Python process.

Fix4 preserves the fix3 repository/build/trace schedule and every eligibility
gate, candidate, timeout, and source rule. It moves each repository enumeration
into a fresh isolated Python process, with at most four such processes at once.
It also removes a stale root-level `ExtractData.lean` only when its SHA-256 is
exactly the frozen generated extractor hash; any different file remains a hard
stop. The two four-hour trace timeouts remain failures and are not extended.

Fix4 proved that process isolation was necessary but not sufficient. All 15
isolated enumeration workers failed at the same pinned parser operation:
LeanDojo 4.20.0 passed Lean 4.27's structured `{"byteIdx": n}` position to an
integer-only `LeanFile.convert_pos`. The observed `lean.py` and `ast.py` hashes
match the already frozen LeanDojo source ledger.

Fix5 installs an in-memory, content-addressed adapter that accepts only a
nonnegative integer or the exact one-key `{"byteIdx": nonnegative-int}` schema.
It records legacy, adapted, and rejected position counts and requires at least
one adapted position and zero rejected positions. It never edits the installed
LeanDojo package. Fix5 does not rerun build or Lean trace: it validates each
fix4 commit, toolchain, tracked checkout, complete source inventory, trace
runtime, AST count, and per-AST SHA-256 before recovery enumeration. The four
fix4 trace failures and seven earlier qualification failures are carried
forward without outcome-dependent retries.

Fix5's pinned runtime passed, but its preflight mistakenly retained fix3's
resource gate for 52 concurrent Lean trace processes, including a 250 GB free
disk requirement. The server had 184.39 GB free, so the gate correctly stopped
before parser preflight and executed zero theorem sources and zero candidates.
Fix6 changes only this capacity profile: the permitted recovery workload is
four isolated Python parsers, zero Lean trace processes, and small content
ledgers. Its frozen minima are 8 CPUs, 64 GB total memory, 32 GB available
memory, and 100 GB free disk. The adapter, trace-reuse validation, candidate
frame, timeouts, and every scientific gate are unchanged.

Fix6 passed that corrected capacity gate, then its one-repository parser
preflight exposed an import-order defect. The adapter imported LeanDojo before
`NUM_PROCS=2` was installed. LeanDojo therefore froze its default multi-worker
topology and delegated AST parsing to Ray actors, where the driver's in-memory
`LeanFile.convert_pos` patch was absent. The worker input was committed, but no
parser receipt or theorem frame was produced; no Lean trace, authored replay,
or scientific candidate ran.

Fix7 moves the exact `NUM_PROCS=2` and `LOAD_USED_PACKAGES_ONLY=1` assignments
before every LeanDojo import. For LeanDojo 4.20.0 this freezes `NUM_WORKERS=1`
and selects its local sequential parsing branch inside each isolated repository
worker. The position adapter, position counters, and AST consumption now occur
in the same process. A new hard gate requires the recorded parser profile,
`NUM_PROCS=2`, `NUM_WORKERS=1`, no initialized Ray runtime, and the adapter PID
to equal the enumeration-worker PID. Up to four repositories may still be
parsed concurrently because each repository has its own isolated Python
process.

Fix7's one-repository parser preflight then passed exactly: 2,648 structured
positions were adapted, none were rejected, the adapter and worker PIDs were
identical, and Ray remained uninitialized. Recovery nevertheless stopped before
submitting a repository worker because the frozen `qualification_recovery`
mapping contained `parser_execution_profile` while the code's strict expected
mapping accidentally omitted it. Fix8 adds that one already-frozen field to the
expected mapping. It changes no value, candidate, repository, trace, timeout,
parser behavior, or scientific rule.

Fix8 therefore submitted the complete frozen recovery schedule. It preserved all
26 qualification decisions, reused 15 content-addressed trace sets, executed no
new Lean trace and no scientific candidate, and completed all rows. Two
repositories passed root enumeration (`bergmannjg/Regex`, 333 roots;
`dissensus-ai/lean-formalizations`, 218 roots), while
`GasStationManager/SafeVerify` enumerated zero eligible roots. Of the remaining
12 enumeration failures, 11 ended at pinned LeanDojo 4.20.0's two-child
`CommandSectionNode` assertion and one ended at its CRLF rejection. The other
11 qualification failures (four trace, three checkout, three exact-toolchain,
and one build) remain frozen and are not retried.

A read-only scan of all 15 reused trace ledgers then identified exactly 742 Lean
4.27 `section` nodes and only two raw schemas: 380 named and 362 unnamed nodes.
Both contain a four-null `sectionHeader`, the `section` atom, and a null optional
name wrapper. A separate byte scan found exactly seven standard-CRLF source
files, all in `AfonsoBitoque/LeanServer`, totaling 3,460 CRLF lines and zero bare
carriage returns. No third section schema or mixed newline schema was observed.

Fix9 adds only a strict, in-memory compatibility layer for those frozen shapes.
It rejects every unobserved section, position, or newline schema, normalizes the
v4.27 section header to LeanDojo's two-child internal representation, and never
edits a checkout or installed parser file. Its parser preflight covers the CRLF
repository, a repository with both section forms, and both fix8 successes. The
two success frames must match fix8 byte-for-byte. Recovery reruns Python
enumeration for all 15 validated traces and still requires at least 12
repository passes before authored replay. No Lean trace or scientific
alternative is permitted in these stages.

The initial fix9 package stopped while validating the preserved fix8 archive,
before creating a recruitment config or running any parser, Lean source, or
candidate. Its validator required the literal text `CommandSectionNode` in the
11 tracebacks, but the protected traceback records only the exact pinned parser
path, `ast.py` line 1480, the two-child assertion, and `AssertionError`. Validator
fix1 replaces that nonexistent class-name condition with those four observed
fields and additionally requires the already frozen `ast.py` and `lean.py`
SHA-256 values. It changes no parser behavior, compatibility schema, frame,
repository, candidate, timeout, or scientific gate.

Validator fix1 reached the four-repository parser preflight and exposed that
the initial CRLF adapter used the checkout's physical two-byte CRLF width.
Read-only instrumentation first observed 15 empty premise slices at pinned
`traced_data.py:663`, then an empty tactic slice at line 652. The tactic value is
consumed by root enumeration, so the package stopped rather than suppressing
the exception. Every empty slice occurred in a CRLF source.

A second read-only diagnostic represented standard CRLF files with the
LF-normalized source buffer used by Lean v4.27 `String.Pos.Raw.byteIdx`. It
parsed all 50 reused AST-bearing LeanServer files, recovered 874 traced
theorems, and observed zero empty premise or tactic slices. Five of those 50
traced files contain 2,470 CRLF lines. The complete hash-validated checkout
inventory still contains seven CRLF files and 3,460 CRLF lines: two source files
have no reused AST and therefore are not instantiated by LeanDojo's parser.

Fix9 fix2 changes only this in-memory CRLF byte-index representation. It freezes
the two measurement levels separately: parser execution must observe 5/2,470,
while the complete source-inventory gate must observe 7/3,460. Both require zero
line-ending rejection, and installed parser files and repository files remain
unchanged. Section counts remain 380 named and 362 unnamed nodes.

Fix2 then completed the LeanServer portion of the parser preflight and stopped
on two `noncomputable section` nodes in `PatrickMassot/GlimpseOfLean`. A new
read-only exhaustive scan covered all 15 reused trace sets, all 874 AST files,
and all 742 section nodes with exact AST-count agreement. It showed that the
earlier 380/362 name split was correct but the header scan had treated modifier
slots too coarsely. The 362 unnamed nodes consist of 71 plain, 4
`noncomputable`, 135 `public`, 43 `public meta`, 107 `@[expose] public`, and 2
`@[expose] public meta` sections. The 380 named nodes are all plain. No other
header slot or name layout occurred.

Fix9 fix3 freezes exactly those seven layouts. Each modifier atom must have the
observed one-key wrapper and exact v4.27 original-byteIdx source information;
the `@[expose]` slot must contain exactly the three atoms `@[`, `expose`, and
`]`. Modified named sections and every unobserved modifier combination are hard
failures. After raw classification, the parsed header atoms are checked again
before the already-elaborated header wrapper is removed from LeanDojo's
section-name-only representation. Recovery requires every per-layout aggregate
count above to match exactly.

The 26-entry candidate frame remains unchanged from fix1 and was frozen before
scientific outcomes. The fix0 through fix8 zero-candidate diagnostics are
mandatory source controls for fix9 and are included in the final audit export.

## Protection boundary

Repository recruitment is allowed to clone, build, trace, enumerate roots, and
replay only the authored tactic. It supplies an empty scientific candidate list.
The scientific freeze is impossible unless at least 12 untouched, exact Lean
v4.27.0 repositories each supply at least 48 live authored-replay-valid roots
after the lineage gate.

The candidate manifest is a screening frame, not a declaration that every
listed project is eligible. Every failure remains in the exclusion ledger. A
failed or low-signal repository is never replaced after scientific outcomes are
available.

## Server prerequisites

- Run from `/home/music/mzz/MZX` in `leandojo_v2_env`.
- Exp49 must have final `Green` analysis artifacts.
- Exp50 must have the final passing `analysis_fix1/summary.json`.
- `MZX_ROOT` must point to the project root.
- Network access is needed once to install the pinned `lean-dojo==4.20.0`
  distribution and dependencies if they are not already cached.
- Use `python`, not `python3`.

## Preserve the failed fix9 fix2 preflight before installing fix9 fix3

The fix8 archive remains mandatory and must not be renamed. Before unzipping
fix9 fix3, preserve the active failed fix9 fix2 preflight directory:

```bash
cd /home/music/mzz/MZX

mv artifacts/v51/external_repository_replication \
  artifacts/v51/external_repository_replication_preflight_failed_fix9_fix2_archive_20260823
```

Do not delete or edit any archive or any checkout under
`external_repos/experiment51_screen`. Fix9 fix3 requires the complete fix0--fix8
diagnostic chain, the original fix4 through fix8 ZIP files, and the 15
fix4-generated AST sets. The required fix8 ZIP SHA-256 is
`af592254cb03a200f5412e478f88754dbc1df96f3d97b16979668a3a6f94e0ac`.

Install the fix9 fix3 code package only after the move:

```bash
sha256sum experiment51_external_repository_replication_fix9_fix3_python_only.zip
unzip -o experiment51_external_repository_replication_fix9_fix3_python_only.zip
export MZX_ROOT=/home/music/mzz/MZX
```

Compare the printed package hash with the value supplied alongside the download.

## Required staged order

Do not use the one-command pipeline for the first run. Run the gates separately
and inspect each receipt.

```bash
cd /home/music/mzz/MZX
export MZX_ROOT=/home/music/mzz/MZX
```

### 1. Install the pinned Python tracing parser

```bash
python -m pip install -r \
  experiment51_external_repository_replication/requirements.txt
```

This is infrastructure qualification and executes no theorem or tactic.

### 2. Freeze the zero-candidate recruitment frame

```bash
python experiment51_external_repository_replication/freeze_experiment51_recruitment.py
```

Expected: `scientific_candidate_tactics_executed: 0`.

### 3. Preflight the pinned tracing runtime

```bash
python experiment51_external_repository_replication/preflight_experiment51.py \
  --stage trace-runtime
```

Expected: `runtime_ok: true`, `theorem_sources_elaborated: 0`, and
`candidate_tactics_executed: 0`. Fix9 additionally requires
`qualification_resources.parallel_capacity_ok: true` before starting the
frozen parser recovery, under capacity profile
`four-python-parser-trace-reuse-v1`.

### 4. Preflight the strict Lean 4.27 parser adapters on four reused traces

```bash
python experiment51_external_repository_replication/preflight_experiment51.py \
  --stage parser-adapter \
  --timeout 7200
```

Expected: `adapter_ok: true`, `trace_executed: false`, four passing
`compatibility_smokes`, `fix8_success_frames_exact: true`, and zero candidate
tactics. The two fix8 success frames must remain exactly 333 and 218 rows. The
LeanServer parser receipt must record five traced CRLF files and 2,470 traced
CRLF lines, while its complete source-inventory receipt must independently
record seven CRLF files and 3,460 CRLF lines. The GlimpseOfLean smoke must
exercise named, unnamed, and `noncomputable` section layouts. Every nested
`parser_execution` receipt must also show profile
`single-process-in-memory-v427-adapter-no-ray-v1`, `num_procs: 2`,
`num_workers: 1`, `ray_initialized: false`, and an adapter PID equal to the
enumeration-worker PID.

### 5. Re-enumerate all 15 hash-validated traces

```bash
python experiment51_external_repository_replication/screen_experiment51_repositories.py \
  --phase recover-enumeration \
  --enumeration-workers 4 \
  --enumeration-timeout 7200
```

This phase runs Python AST parsing only. It does not invoke `lake`, Lean,
authored replay, or any scientific alternative. Every reused AST receives a
new content ledger before enumeration. Expected: `reused_trace_repositories`
equals 15, `fix8_success_frames_exact: true`, exact aggregate compatibility counts,
at least 12 passes, and `recovery_gate: true`. A smaller pass count is a hard
stop even if one or more repositories passed.

### 6. Compile-only screening worker preflight

```bash
python experiment51_external_repository_replication/preflight_experiment51.py \
  --stage screening \
  --timeout 300
```

Expected: `compile_ok: true`, `theorem_sources_elaborated: 0`, and
`candidate_tactics_executed: 0`.

### 7. Authored-only live replay screening

```bash
python experiment51_external_repository_replication/screen_experiment51_repositories.py \
  --phase authored-replay \
  --replay-timeout 900
```

This can be long because every preliminary theorem root is replay-qualified.
It still executes zero scientific alternatives.

Print the compact recruitment decision:

```bash
python - <<'PY'
import json
p = "artifacts/v51/external_repository_replication/screening/summary.json"
d = json.load(open(p))
print(json.dumps({
    "candidates_screened": d["candidates_screened"],
    "selected_count": d["selected_count"],
    "selected_repositories": d["selected_repositories"],
    "screening_gate": d["screening_gate"],
    "next_step": d["next_step"],
}, indent=2))
PY
```

If `screening_gate` is false, stop. Do not lower the 12-repository minimum and
do not mix another Lean version into Exp51.

### 8. Freeze Exp51 scientific targets and Exp52 protocol

```bash
python experiment51_external_repository_replication/freeze_experiment51.py
```

Expected: 12–16 repositories, 48 sampled roots per repository,
`scientific_candidate_execution_before_freeze: false`, and a nonempty
`exp52_protocol_sha256`.

### 9. Compile-only scientific worker preflight

```bash
python experiment51_external_repository_replication/preflight_experiment51.py \
  --stage scientific \
  --timeout 300
```

### 10. Capture the exact environment receipt

```bash
python experiment51_external_repository_replication/capture_experiment51_environment.py \
  --timeout 300
```

Expected: `environment_gate: true` and
`scientific_candidate_tactics_executed: 0`.

### 11. Scientific smoke

```bash
python experiment51_external_repository_replication/run_experiment51.py \
  --phase smoke \
  --lean-timeout 900
```

Proceed only if `smoke_gate: true`. Smoke outcomes never change the frozen full
sample or candidate panels.

### 12. Full frozen scientific execution

```bash
python experiment51_external_repository_replication/run_experiment51.py \
  --phase scientific \
  --lean-timeout 900
```

### 13. Frozen offline analysis

```bash
python experiment51_external_repository_replication/analyze_experiment51.py
```

The possible labels are `robust_replication_go`, `replication_go`,
`inconclusive`, `replication_no_go`, and `invalid_execution`. A No Go or
inconclusive result is retained; it does not change Exp48's archived result.

### 14. Independent offline reconstruction audit

```bash
python experiment51_external_repository_replication/audit_experiment51.py
```

Expected: `audit_pass: true`, `manual_reconciliation_count: 0`. This audit
reconstructs Exp51 only and adds no scientific result.

### 15. Export and verify the audit bundle

```bash
python experiment51_external_repository_replication/export_experiment51_bundle.py
```

The default output is:

```text
exports/experiment51_external_repository_replication_results.zip
```

## Optional one-command resume

Only after understanding the protected stages:

```bash
python experiment51_external_repository_replication/run_experiment51_full_pipeline.py \
  --enumeration-workers 4 \
  --enumeration-timeout 7200 \
  --lean-timeout 900
```

## Important stop conditions

- exact toolchain is not `leanprover/lean4:v4.27.0`;
- fewer than 12 lineage-independent eligible repositories;
- screening preflight or authored replay protection fails;
- Exp52 protocol is absent before scientific execution;
- scientific compile/environment/smoke gate fails;
- frozen source, AST, commit, candidate, or code hashes change.
