# Experiment 50 — independent end-to-end re-execution

Exp50 re-executes the exact 96 Experiment 48 confirmation roots and the exact
23 frozen candidates per root.  It is an execution-reproducibility and
infrastructure-validation experiment, not a new scientific repository sample.

The achieved independence level is deliberately narrow and explicit:

- a separately packaged Exp50 Python/Lean runner imports no Exp48/Exp49 runner;
- every M0–M4 root is elaborated in a new Lean process;
- every M5 `(root,candidate)` is elaborated in its own new Lean process and runs
  authored replay before the candidate;
- the run still uses `gpuserver01` and the same frozen repository checkouts.

Therefore this run is not a physically independent-machine replication.

## Preconditions

- working directory: `/home/music/mzz/MZX`
- active environment: `leandojo_v2_env`
- Lean: exactly v4.27.0
- passing immutable Exp48 and Exp49 artifact trees at their original paths
- the Exp49 validation and offline analysis must already be complete

All commands below intentionally use `python`, not `python3`.

## 1. Install and set the root

```bash
cd /home/music/mzz/MZX
unzip -o experiment50_independent_reexecution_python_only.zip
export MZX_ROOT=/home/music/mzz/MZX
```

Do not edit any Exp50 file after freezing.  The code lock will reject a change.

## 2. Freeze

```bash
python experiment50_independent_reexecution/freeze_experiment50.py
```

Print only the frozen facts needed for review:

```bash
python -c 'import json; p="artifacts/v50/independent_reexecution/frozen/experiment50_config.json"; x=json.load(open(p)); print(json.dumps({"protocol_version":x["protocol_version"],"roots":x["roots"],"repositories":x["repositories"],"modes":x["all_modes"],"operator_statement":x["operator_statement"],"next_step":x["next_step"]},indent=2))'
```

## 3. Compile-only preflight

This step elaborates zero theorem sources and executes zero scientific
candidates.

```bash
python experiment50_independent_reexecution/preflight_experiment50.py --timeout 300
```

Compact output for sharing:

```bash
python -c 'import json; p="artifacts/v50/independent_reexecution/preflight/worker_compile.json"; x=json.load(open(p)); print(json.dumps({k:x.get(k) for k in ["protocol_version","diagnostic_only","theorem_sources_elaborated","candidate_tactics_executed","lean_version","compile_ok","independent_import_scan","stdout","stderr","next_step"]},indent=2))'
```

Stop if `compile_ok` is not `true`.

## 4. Capture and gate the environment

```bash
python experiment50_independent_reexecution/capture_experiment50_environment.py --timeout 300
```

Compact output for sharing:

```bash
python -c 'import json; p="artifacts/v50/independent_reexecution/environment/receipt.json"; x=json.load(open(p)); print(json.dumps({"independence_label":x["independence_label"],"independence_limit":x["independence_limit"],"checks":x["checks"],"environment_gate":x["environment_gate"],"repositories":[{"slug":r["slug"],"commit_ok":r["commit_ok"],"lean_version_ok":r["lean_version_ok"],"selected_sources_ok":r["selected_sources_ok"],"checkout_clean_descriptive":r["checkout_clean_descriptive"]} for r in x["repositories"]],"next_step":x["next_step"]},indent=2))'
```

Stop if `environment_gate` is not `true`.  A dirty checkout is recorded, but
the gate depends on the exact commit and all 96 selected source hashes; unrelated
untracked files do not silently invalidate those identities.

## 5. Smoke

```bash
python experiment50_independent_reexecution/run_experiment50.py --phase smoke --lean-timeout 900
```

```bash
python -c 'import json; p="artifacts/v50/independent_reexecution/smoke/summary.json"; x=json.load(open(p)); print(json.dumps(x,indent=2))'
```

Stop if `smoke_gate` is not `true`.

## 6. M0 independent baseline

```bash
python experiment50_independent_reexecution/run_experiment50.py --phase M0 --lean-timeout 900
```

```bash
python -c 'import json; p="artifacts/v50/independent_reexecution/M0/summary.json"; x=json.load(open(p)); print(json.dumps({k:x.get(k) for k in ["mode","roots_expected","roots_attempted","candidate_attempts_expected","candidate_attempts","evaluable_roots","execution_complete","mode_gate","repository_execution","next_step"]},indent=2))'
```

Stop if `mode_gate` is not `true`.

## 7. M1–M4 order perturbations

```bash
python experiment50_independent_reexecution/run_experiment50.py --phase orders --lean-timeout 900
```

```bash
python -c 'import json; p="artifacts/v50/independent_reexecution/orders/summary.json"; x=json.load(open(p)); print(json.dumps({"modes_expected":x["modes_expected"],"orders_execution_gate":x["orders_execution_gate"],"mode_summaries":[{"mode":m["mode"],"roots_attempted":m["roots_attempted"],"candidate_attempts":m["candidate_attempts"],"evaluable_roots":m["evaluable_roots"],"mode_gate":m["mode_gate"]} for m in x["mode_summaries"]],"next_step":x["next_step"]},indent=2))'
```

Stop if `orders_execution_gate` is not `true`.

## 8. M5 one fresh Lean process per candidate

This is the long phase: 2,208 Lean processes.  Run it sequentially as frozen;
do not externally parallelize or reorder it.

```bash
python experiment50_independent_reexecution/run_experiment50.py --phase M5 --lean-timeout 900
```

The command is resumable: rerunning it reuses records only after checking their
frozen identity.  It never overwrites a completed record.

```bash
python -c 'import json; p="artifacts/v50/independent_reexecution/M5/summary.json"; x=json.load(open(p)); print(json.dumps({k:x.get(k) for k in ["mode","roots_expected","roots_attempted","candidate_attempts_expected","candidate_attempts","evaluable_roots","fresh_lean_processes_expected","fresh_lean_processes_observed","one_process_per_root_candidate","mode_gate","repository_execution","next_step"]},indent=2))'
```

Stop if `mode_gate` is not `true`.

## 9. Frozen exact analysis

```bash
python experiment50_independent_reexecution/analyze_experiment50.py
```

```bash
python -c 'import json; p="artifacts/v50/independent_reexecution/analysis/summary.json"; x=json.load(open(p)); print(json.dumps({k:x.get(k) for k in ["protocol_version","roots","candidates_per_root","order_comparisons","M5_fresh_processes","mismatch_count","manual_reconciliation_count","checks","root_level_complete_agreement","repository_level_complete_agreement","reexecution_pass","independence_limit","next_step"]},indent=2))'
```

If `reexecution_pass` is false, do not edit the mismatch ledger and do not turn
the gate into a tolerance.  Preserve the run and inspect:

```bash
python -c 'import json; p="artifacts/v50/independent_reexecution/analysis/mismatch_ledger.jsonl"; rows=[json.loads(s) for s in open(p) if s.strip()]; print(json.dumps({"mismatch_count":len(rows),"first_20":rows[:20]},indent=2))'
```

## 10. Export

Only a passing final gate can be exported.

```bash
python experiment50_independent_reexecution/export_experiment50_bundle.py
```

```bash
python -c 'import json; p="artifacts/v50/independent_reexecution/export/receipt.json"; print(json.dumps(json.load(open(p)),indent=2))'
```

Download:

`/home/music/mzz/MZX/exports/experiment50_independent_reexecution_results.zip`

## One-command resumable alternative

The explicit staged order above is preferred because each gate can be reviewed.
After a clean install, the same order can be run with:

```bash
python experiment50_independent_reexecution/run_experiment50_full_pipeline.py --preflight-timeout 300 --lean-timeout 900
```

## Failure discipline

- Never drop a root, candidate, or execution mode.
- Never manually reconcile a mismatch.
- Do not change endpoint definitions, source spans, seeds, or candidate lists.
- After a code correction, archive the failed Exp50 artifact directory and issue
  a versioned mechanical fix before refreezing.
- Exp50 may support a reproducibility claim only.  It does not add a scientific
  confirmation repository, tactic-equivalence claim, runtime-equivalence claim,
  proof-term claim, or theorem-proving improvement claim.
