# Experiment 51 Repository-Frame Extension 2

This package continues only the zero-scientific-candidate repository
qualification stage. The protected Extension1 No-Go is immutable: eleven
repositories passed build/trace, twelve are required, authored replay did not
run, and no scientific candidate tactic was executed.

Mechanical fix1 explicitly re-exports the inherited isolated-enumeration entry
point required by the offline parser preflight. It changes no candidate,
repository, timeout, threshold, execution mechanism, or claim boundary.

Extension2 carries those eleven repositories forward from the verified No-Go
ZIP and screens seven new exact-commit public repositories in a frozen order.
It does not lower the twelve-repository minimum. The carry-forward gate also
rechecks every preserved checkout's commit, tracked cleanliness, exact Lean
toolchain, and source inventory before reuse.

## Required server inputs

- `/home/music/mzz/MZX/exports/experiment51_repository_frame_extension1_nogo_results.zip`
  with SHA-256
  `94101bccc3be5d7edff48b91824494a228f9a21fce2580f1353594eeab420473`
  and byte count `1349401`.
- The eleven passing checkouts preserved at the paths recorded in that ZIP.
- The locked base directories
  `/home/music/mzz/MZX/experiment51_external_repository_replication` and
  `/home/music/mzz/MZX/experiment51_repository_frame_extension`.
- LeanDojo 4.20.0 and Lean v4.27.0 in `leandojo_v2_env`.

## Frozen schedule

- 7 repository workers.
- 4 concurrent build/cache slots.
- 7 concurrent trace slots, with 2 Lean threads per trace.
- 4 concurrent isolated enumeration workers.
- At least 16 allowed CPUs, 256 GB total memory, 192 GB available memory, and
  180 GB free disk before new checkout or trace execution.

## Server order

Use `python`, not `python3`.

```bash
cd /home/music/mzz/MZX
unzip -o experiment51_repository_frame_extension2_python_only.zip
export MZX_ROOT=/home/music/mzz/MZX

python experiment51_repository_frame_extension2/test_experiment51_extension2_static.py

python experiment51_repository_frame_extension2/audit_repository_extension_frame.py

python experiment51_repository_frame_extension2/freeze_experiment51_extension.py

python experiment51_repository_frame_extension2/preflight_experiment51_extension.py \
  --stage environment

python experiment51_repository_frame_extension2/screen_experiment51_extension.py \
  --phase carry-forward

python experiment51_repository_frame_extension2/preflight_experiment51_extension.py \
  --stage offline-parser-control \
  --timeout 7200
```

Stop immediately if any command exits nonzero. The build/trace stage is the
first long-running command:

```bash
mkdir -p artifacts/v51/external_repository_replication_extension2/logs

nohup python -u \
  experiment51_repository_frame_extension2/screen_experiment51_extension.py \
  --phase build-trace \
  > artifacts/v51/external_repository_replication_extension2/logs/build_trace.log \
  2>&1 < /dev/null &

echo $! > \
  artifacts/v51/external_repository_replication_extension2/logs/build_trace.pid
```

Monitor without restarting it:

```bash
tail -f \
  artifacts/v51/external_repository_replication_extension2/logs/build_trace.log
```

After it exits, print only the compact receipt:

```bash
python - <<'PY'
import json

p = (
    "artifacts/v51/external_repository_replication_extension2/"
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
print(json.dumps({key: d.get(key) for key in keys}, indent=2))
PY
```

STOP after printing this receipt, even when `build_trace_gate` is `true`.
Do not run authored replay yet. Return the compact receipt for review and a
separate go/no-go instruction.

## Claim boundary

This extension produces repository qualification evidence only. It is not a
scientific replication result. It supports no claim of tactic
interchangeability, proof-strategy equivalence, proof-term equality, runtime
equivalence, or improved theorem proving. Experiment 48 remains the existing
Tier-1 scientific confirmation until a separately frozen experiment completes.
