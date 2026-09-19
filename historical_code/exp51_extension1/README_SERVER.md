# Experiment 51 Repository-Frame Extension 1

This package extends only the zero-scientific-candidate repository recruitment
stage.  The protected fix9 fix3 No-Go remains immutable: seven repositories
passed, twelve are required, the old frame upper bound is nine, and no
scientific candidate tactic was executed.

The extension carries forward the seven archive-exact qualification passes and
screens 28 new exact-commit repositories in frozen order.  It never lowers the
twelve-repository minimum.  No Exp51 scientific alternative may run unless the
combined build/trace gate and the later authored-replay/lineage gate both pass.

## Required server inputs

- `/home/music/mzz/MZX/exports/experiment51_recruitment_nogo_fix9_fix3_results.zip`
  with SHA-256
  `5f3ef5ee40609015d20954e6e34fdfd6c53f30263545dcbcfc9ebe0bddf9b683`.
- The active fix9 fix3 artifacts at
  `/home/music/mzz/MZX/artifacts/v51/external_repository_replication`.
- The protected base code directory
  `/home/music/mzz/MZX/experiment51_external_repository_replication`.
- LeanDojo 4.20.0 and Lean v4.27.0 in `leandojo_v2_env`.

## Frozen qualification schedule

- 16 repository workers.
- 8 concurrent build/cache slots.
- 16 concurrent trace slots, with 2 Lean threads per trace.
- 8 concurrent isolated enumeration workers.
- At least 32 allowed CPUs, 256 GB total memory, 192 GB available memory, and
  250 GB free disk before new checkout or trace execution.

The offline enumeration adapter is in-memory only.  It returns an empty
dependency metadata map for `build_deps=False` and rejects any GitHub API call.
Before new tracing, two carried repositories must reproduce their archived
frames byte-for-byte under this adapter.

## Server order

Run these commands from a clean shell.  Use `python`, not `python3`.

```bash
cd /home/music/mzz/MZX
unzip -o experiment51_repository_frame_extension1_python_only.zip
export MZX_ROOT=/home/music/mzz/MZX

python experiment51_repository_frame_extension/freeze_experiment51_extension.py

python experiment51_repository_frame_extension/preflight_experiment51_extension.py \
  --stage environment

python experiment51_repository_frame_extension/screen_experiment51_extension.py \
  --phase carry-forward

python experiment51_repository_frame_extension/preflight_experiment51_extension.py \
  --stage offline-parser-control \
  --timeout 7200
```

Stop immediately if any command exits nonzero.  In particular, do not delete
artifacts merely to satisfy the disk gate; report the compact environment
receipt first.

The 28-repository build/trace stage is long-running.  Start it with `nohup` so
an SSH disconnect does not terminate it:

```bash
mkdir -p artifacts/v51/external_repository_replication_extension1/logs

nohup python -u \
  experiment51_repository_frame_extension/screen_experiment51_extension.py \
  --phase build-trace \
  > artifacts/v51/external_repository_replication_extension1/logs/build_trace.log \
  2>&1 < /dev/null &

echo $! > \
  artifacts/v51/external_repository_replication_extension1/logs/build_trace.pid
```

Monitor without restarting the job:

```bash
tail -f \
  artifacts/v51/external_repository_replication_extension1/logs/build_trace.log
```

After the process exits, print only the compact summary:

```bash
python - <<'PY'
import json

p = (
    "artifacts/v51/external_repository_replication_extension1/"
    "screening/build_trace_summary.json"
)
d = json.load(open(p))
keys = [
    "carry_forward_passes",
    "extension_candidates",
    "extension_passes",
    "combined_build_trace_passes",
    "minimum_required",
    "failure_gate_counts",
    "trace_qualified_for_enumeration",
    "enumeration_receipts_found",
    "enumeration_receipt_accounting_exact",
    "enumeration_failure_receipts_preserved",
    "github_api_attempts",
    "execution_complete",
    "build_trace_gate",
    "next_step",
]
print(json.dumps({k: d.get(k) for k in keys}, indent=2))
PY
```

Only when `build_trace_gate` is `true`, continue:

```bash
python experiment51_repository_frame_extension/preflight_experiment51_extension.py \
  --stage screening \
  --timeout 300

nohup python -u \
  experiment51_repository_frame_extension/screen_experiment51_extension.py \
  --phase authored-replay \
  > artifacts/v51/external_repository_replication_extension1/logs/authored_replay.log \
  2>&1 < /dev/null &

echo $! > \
  artifacts/v51/external_repository_replication_extension1/logs/authored_replay.pid
```

Authored replay executes only the original authored tactic at each root; its
scientific candidate list is empty.  After it exits, inspect
`screening/summary.json`.  If `screening_gate` is false, Exp51 remains stopped.
If it is true, stop anyway and create a separate scientific freeze before any
candidate alternative execution.

## Claim boundary

This extension produces repository-qualification evidence only.  It is not a
scientific replication result and supports no claim of tactic
interchangeability, proof-strategy equivalence, proof-term equality, runtime
equivalence, or improved theorem proving.  Experiment 48 remains the existing
Tier-1 scientific confirmation until a separately frozen experiment completes.
