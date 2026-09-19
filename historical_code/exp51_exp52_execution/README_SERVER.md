# Experiment 51/52 execution-alignment Fix3

This package is a pre-candidate mechanical amendment to the already frozen
Experiment 51 sample and Experiment 52 v0.1 design. It does not change the 12
repositories, 576 roots, 23 Exp51 alternatives, 9 retained Exp52 probes,
selection rules, statistical gates, or claim boundaries. Run it only while
the Fix2 receipt still reports zero scientific candidate executions.

Use `python`, not `python3`, in the `leandojo_v2_env` environment.

## 0. Install and verify the package

```bash
cd /home/music/mzz/MZX

unzip -o \
experiment51_exp52_execution_alignment_fix3_python_only.zip

export MZX_ROOT=/home/music/mzz/MZX

python \
experiment51_exp52_execution_alignment_fix3/test_execution_alignment_fix3_static.py
```

Do not continue if the static test fails.

## 1. Freeze the Fix3 amendment

The freeze command runs no Lean process and no scientific candidate tactic. It
adds the content-locked Fix3 execution amendment beside the immutable Fix2
freeze.

```bash
python \
experiment51_exp52_execution_alignment_fix3/freeze_execution_alignment.py
```

The command exits nonzero if any reviewed Fix2 anchor differs. Its receipt
must preserve these anchors exactly:

```text
source_qualification_config_sha256:
d983bac8a2886f31520c3add1f7f2e165c3a99518ca3c629946c1a859bbd8b56
source_qualification_summary_sha256:
2e02f40fc9984b98b04a46ccb0598e1abf560aba15d1ac093e66b691e4a06614
source_exp52_protocol_sha256:
d6ec3926ab97f2b58efa466741b04d7c1e786f41de1a491282727ece368d84de
source_exp52_design_documents_bundle_sha256:
e34f20837ebb0286bf87b3ee5ee15286307317ff44ed159c555200ca28eb46c0
source_exp52_retained_probes: 9
source_copied_build_receipts_exact: true
```

If any anchor differs, stop. Do not edit a frozen receipt to make it agree.
After `amendment_gate` is `true`, compile worker definitions only and capture
the environment/resource receipt:

```bash
python \
experiment51_exp52_execution_alignment_fix3/preflight_exp51_execution.py \
--timeout 300

python \
experiment51_exp52_execution_alignment_fix3/capture_exp51_environment.py \
--timeout 300
```

Stop unless `compile_ok` and `environment_gate` are both `true`, and every
receipt still reports zero scientific candidate tactics.

## 2. Run and finalize the four-root Exp51 smoke

```bash
python \
experiment51_exp52_execution_alignment_fix3/run_exp51_shards.py \
--phase smoke \
--shard-index 0 \
--lean-timeout 900

python \
experiment51_exp52_execution_alignment_fix3/finalize_exp51_execution.py \
--phase smoke
```

Continue only when `smoke_gate` is `true`.

## 3. Run the 16 mutually exclusive Exp51 scientific shards

Each shard owns exactly 36 frozen roots. The following launch loop starts 16
independent Python processes and records a PID and log for each shard.

```bash
mkdir -p \
artifacts/v51/external_repository_replication_scientific/logs/fix3_exp51

for shard in $(seq 0 15); do
  label=$(printf '%02d' "$shard")
  nohup python -u \
  experiment51_exp52_execution_alignment_fix3/run_exp51_shards.py \
  --phase scientific \
  --shard-index "$shard" \
  --lean-timeout 900 \
  > "artifacts/v51/external_repository_replication_scientific/logs/fix3_exp51/shard-${label}.log" \
  2>&1 < /dev/null &
  echo $! > \
  "artifacts/v51/external_repository_replication_scientific/logs/fix3_exp51/shard-${label}.pid"
done
```

Compact progress check:

```bash
python - <<'PY'
import json
from pathlib import Path

root = Path(
    "artifacts/v51/external_repository_replication_scientific/"
    "scientific/shards"
)
summaries = []
for shard in range(16):
    path = root / f"shard-{shard:02d}/summary.json"
    if path.is_file():
        summaries.append(json.load(open(path)))

print(json.dumps({
    "shards_completed": len(summaries),
    "shards_expected": 16,
    "root_receipts": sum(x.get("root_receipts", 0) for x in summaries),
    "evaluable_roots": sum(x.get("evaluable_roots", 0) for x in summaries),
    "all_completed_shard_gates": all(
        x.get("shard_gate") is True for x in summaries
    ),
}, indent=2))
PY
```

Do not run the finalizer until all 16 summaries exist. If a process is still
active, do not launch the same shard again. A claimed root is never retried.
One root may leave the last progress line unchanged for roughly the frozen
900-second Lean timeout plus process cleanup; that alone is not evidence that
the shard is dead. Check the PID and its descendant before any resume attempt.

## 4. Finalize, analyze, audit, and export Exp51

```bash
python \
experiment51_exp52_execution_alignment_fix3/finalize_exp51_execution.py \
--phase scientific

python \
experiment51_exp52_execution_alignment_fix3/analyze_exp51_fix3.py

python \
experiment51_exp52_execution_alignment_fix3/audit_exp51_fix3.py

python \
experiment51_exp52_execution_alignment_fix3/export_exp51_fix3.py
```

The Exp51 audit must report `audit_pass: true`. Its decision may be a Go, No
Go, inconclusive result, or invalid execution according to the frozen gates;
do not manually replace or reconcile a row.

## 5. Materialize the frozen Exp52 witness/control plan

This is an offline transformation of the completed Exp51 rows. It runs no
Lean process and no continuation probe.

```bash
python \
experiment51_exp52_execution_alignment_fix3/select_exp52_pairs.py

python \
experiment51_exp52_execution_alignment_fix3/preflight_exp52_execution.py \
--workers 12 \
--timeout 300
```

Stop unless `selection_complete`, `compile_gate`, and
`launch_resources.resource_gate` are all `true`. The last gate is a read-only
pre-launch check requiring at least 32 visible logical CPUs, 64 GiB available
memory, and 50 GiB free space on the scientific-artifact filesystem; it does
not elaborate a theorem or execute a continuation probe.

## 6. Run the 32 mutually exclusive Exp52 cell shards

The execution plan determines the number of cells after the Exp51 outcomes
have been mechanically selected. Every cell is one fresh Lean process for one
`(root, pair role, side, probe, repeat kind)` tuple.

```bash
mkdir -p \
artifacts/v51/external_repository_replication_scientific/logs/fix3_exp52

for shard in $(seq 0 31); do
  label=$(printf '%02d' "$shard")
  nohup python -u \
  experiment51_exp52_execution_alignment_fix3/run_exp52_shards.py \
  --shard-index "$shard" \
  > "artifacts/v51/external_repository_replication_scientific/logs/fix3_exp52/shard-${label}.log" \
  2>&1 < /dev/null &
  echo $! > \
  "artifacts/v51/external_repository_replication_scientific/logs/fix3_exp52/shard-${label}.pid"
done
```

Compact progress check:

```bash
python - <<'PY'
import json
from pathlib import Path

root = Path(
    "artifacts/v51/external_repository_replication_scientific/"
    "exp52/execution/shards"
)
summaries = []
for shard in range(32):
    path = root / f"shard-{shard:02d}/summary.json"
    if path.is_file():
        summaries.append(json.load(open(path)))

print(json.dumps({
    "shards_completed": len(summaries),
    "shards_expected": 32,
    "cells_recorded": sum(x.get("cells_recorded", 0) for x in summaries),
    "valid_reconstructions": sum(
        x.get("valid_reconstructions", 0) for x in summaries
    ),
    "all_completed_shard_gates": all(
        x.get("shard_gate") is True for x in summaries
    ),
}, indent=2))
PY
```

Do not rerun a shard while its PID or descendant worker is active. The runner
records active workers and stops rather than creating a conflicting receipt.
A cell may likewise hold its last log line for the 900-second timeout plus
cleanup. Resume only after confirming that both the shard PID and matching
descendant worker have exited; an immutable claim without a result is recorded
as a protocol failure rather than scientifically retried.

## 7. Finalize, analyze, audit, and export Exp52

```bash
python \
experiment51_exp52_execution_alignment_fix3/finalize_exp52_execution.py

python \
experiment51_exp52_execution_alignment_fix3/analyze_exp52.py

python \
experiment51_exp52_execution_alignment_fix3/audit_exp52.py

python \
experiment51_exp52_execution_alignment_fix3/export_exp52_bundle.py
```

The final audit must report `audit_pass: true`. The scientific decision is
restricted to the preregistered bounded continuation response under the
frozen probe panel. It does not establish tactic equivalence, global tactic
interchangeability, semantic equivalence, proof-strategy equivalence, proof-
term equality, runtime equivalence, or theorem-proving improvement.
