# Exp58 No-Go and Exp59 prospective expansion-only recruitment

This package performs two ordered operations. First it freezes the completed 512-root Exp58 candidate screen as a recruitment No-Go. Second it freezes a disjoint prospective frame containing every 658 source root that Exp58 did not execute. It removes only `aesop?` and `exact?`, because the already frozen Exp49 genealogy classified exactly those two entries as `direct_suggestion` before Exp58 was designed.

The Exp58 decision is not changed. Its suggestion-exclusion counts are a post-run diagnostic only. Exp59 executes zero continuation probes in this package.

## 1. Verify, unpack, and run static checks

```bash
cd /home/music/mzz/MZX
sha256sum experiment58_nogo_exp59_expansion_only_transition_python_only.zip
unzip -o experiment58_nogo_exp59_expansion_only_transition_python_only.zip
export MZX_ROOT=/home/music/mzz/MZX

python experiment59_expansion_only_hard_root_efficiency_confirmation/test_experiment59_static.py
```

## 2. Freeze and export the Exp58 recruitment No-Go

```bash
python \
experiment59_expansion_only_hard_root_efficiency_confirmation/finalize_exp58_recruitment_nogo.py \
| tee artifacts/v58/external_hard_root_efficiency_confirmation/logs/recruitment_nogo.json

python \
experiment59_expansion_only_hard_root_efficiency_confirmation/export_exp58_recruitment_nogo.py
```

The expected decision is `candidate_panel_recruitment_no_go`, with 512 receipts, 511 operational roots, one retained timeout, 11,753 candidate attempts, and zero continuation probes. The public-style export deliberately excludes all target-to-successful-tactic rows and generated proofs.

## 3. Freeze the disjoint Exp59 source frame

```bash
python \
experiment59_expansion_only_hard_root_efficiency_confirmation/freeze_experiment59.py

python \
experiment59_expansion_only_hard_root_efficiency_confirmation/preflight_experiment59.py \
--timeout 900
```

Expected freeze: 658 roots total, with 242 miniF2F roots and 416 PutnamBench roots. Within each dataset, 64 roots are frozen for pilot recruitment and every remaining root is frozen for confirmation recruitment. The candidate panel has 21 entries. These commands execute zero candidate tactics and zero continuation probes.

## 4. Run 32 frozen candidate-only shards

```bash
mkdir -p \
artifacts/v59/expansion_only_hard_root_efficiency_confirmation/logs/candidate_screening

for shard in $(seq 0 31); do
  label=$(printf '%02d' "$shard")
  nohup python -u \
    experiment59_expansion_only_hard_root_efficiency_confirmation/run_experiment59_candidate_screening.py \
    --shard-index "$shard" --shard-count 32 --timeout 1800 \
    > "artifacts/v59/expansion_only_hard_root_efficiency_confirmation/logs/candidate_screening/shard-${label}.log" \
    2>&1 < /dev/null &
  echo $! > \
    "artifacts/v59/expansion_only_hard_root_efficiency_confirmation/logs/candidate_screening/shard-${label}.pid"
done
```

Monitor final receipts without double-counting raw `.lean.json` files:

```bash
python - <<'PY'
import json
import os
import re
from pathlib import Path

root = Path("artifacts/v59/expansion_only_hard_root_efficiency_confirmation")
receipts = [
    p for p in (root / "screening/candidate_receipts").glob("*.json")
    if re.fullmatch(r"[0-9a-f]{24}\.json", p.name)
]
shards = list((root / "screening/shards").glob("shard-*.json"))
running = 0
for p in (root / "logs/candidate_screening").glob("shard-*.pid"):
    try:
        os.kill(int(p.read_text().strip()), 0)
        running += 1
    except (OSError, ValueError):
        pass
print(json.dumps({
    "shards_running": running,
    "shards_completed": len(shards),
    "shards_expected": 32,
    "final_receipts": len(receipts),
    "final_receipts_expected": 658,
    "progress_percent": round(100 * len(receipts) / 658, 2),
}, indent=2))
PY
```

## 5. Finalize recruitment

```bash
python \
experiment59_expansion_only_hard_root_efficiency_confirmation/finalize_experiment59_candidate_screening.py
```

Return `artifacts/v59/expansion_only_hard_root_efficiency_confirmation/screening/summary.json`. If `screening_gate` is true, the next package will freeze the four-policy pilot jobs before running any continuation. If it is false, stop and preserve the prospective recruitment No-Go; do not retry individual roots or lower the quotas.
