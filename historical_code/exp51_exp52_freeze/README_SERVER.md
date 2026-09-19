# Exp51 Extension2 → Scientific Freeze + Exp52 Alignment Fix2

## Mechanical correction from Fix1

The protected Fix1 probe-surface No-Go must be retained as a failed diagnostic.
It reported a passing baseline import gate but removed all twelve probes.  The
generated nonempty files had annotated `` `(tactic| ...) `` as
`Lean.Syntax`. Lean tactic quotation elaborates to a monadic computation that
returns `Lean.TSyntax `tactic`; `Lean.MacroM (Lean.TSyntax `tactic)` is a valid
standard expected type. Consequently, every nonempty generated file failed
with the same container type mismatch before individual probe syntax was
qualified.

Fix2 changes only that compile-only annotation.  It does not change the twelve
frozen probes, global-removal rule, minimum of eight, repositories, roots,
candidate library, endpoints, thresholds, timeouts, or scientific protocol.
It still elaborates zero theorem sources and executes zero tactic candidates.

This Python-only package does not modify the protected Extension2 qualification
artifact and does not replace any code covered by its code lock. It adds a new
bridge that:

1. validates the completed Extension2 build/trace and authored-only replay;
2. proves that every selected authored row executed an empty candidate list;
3. stages the deterministic 48-root-per-repository scientific sample;
4. performs global, compile-only Exp52 tactic-syntax qualification;
5. freezes Exp51 scientific targets and the aligned Exp52 v0.1 protocol in a
   separate artifact root.

The package itself contains no Lean source. The probe-surface command generates
temporary syntax-quotation files on the server and compiles them against
already-built repository modules. It elaborates zero theorem source files and
executes zero tactic candidates.

## Protected roots

- Qualification input, read-only:
  `artifacts/v51/external_repository_replication_extension2`
- New scientific output:
  `artifacts/v51/external_repository_replication_scientific`

Do not run the old command
`experiment51_external_repository_replication/freeze_experiment51.py`. It reads
the earlier base recruitment artifact instead of the successful Extension2
qualification frame and embeds the superseded Exp52 helper.

## Server order

Use `python`, not `python3`.

Wait until the existing authored replay process exits and
`screening/summary.json` reports `screening_gate: true`. Then:

```bash
cd /home/music/mzz/MZX

unzip -o \
experiment51_exp52_scientific_freeze_alignment_fix2_python_only.zip

export MZX_ROOT=/home/music/mzz/MZX

mv \
artifacts/v51/external_repository_replication_scientific \
artifacts/v51/external_repository_replication_scientific_probe_surface_nogo_fix1_archive_20260825

python \
experiment51_exp52_scientific_freeze_alignment/test_exp51_exp52_freeze_static.py
```

The first server command that invokes Lean is compile-only probe-surface
qualification. Run it detached because the number of unique sampled modules is
not known until authored replay finishes:

```bash
mkdir -p \
artifacts/v51/external_repository_replication_scientific/logs

nohup python -u \
experiment51_exp52_scientific_freeze_alignment/preflight_exp52_probe_surface.py \
--workers 16 \
--timeout 900 \
> artifacts/v51/external_repository_replication_scientific/logs/exp52_probe_surface.log \
2>&1 < /dev/null &

echo $! > \
artifacts/v51/external_repository_replication_scientific/logs/exp52_probe_surface.pid
```

Monitor without restarting:

```bash
tail -f \
artifacts/v51/external_repository_replication_scientific/logs/exp52_probe_surface.log
```

After it exits, print the compact receipt:

```bash
python - <<'PY'
import json

p = (
    "artifacts/v51/external_repository_replication_scientific/"
    "preflight/exp52_probe_surface.json"
)
d = json.load(open(p))
keys = [
    "alignment_version",
    "mechanical_fix_id",
    "selected_repositories",
    "staged_targets",
    "unique_source_modules",
    "compile_workers",
    "baseline_import_gate",
    "retained_panel",
    "globally_removed_probes",
    "candidate_tactics_executed",
    "theorem_sources_elaborated",
    "probe_surface_gate",
    "next_step",
]
print(json.dumps({key: d.get(key) for key in keys}, indent=2))
PY
```

Stop after printing this receipt and return it for review. If
`probe_surface_gate` is not `true`, do not change the panel by hand. Run the
following freeze command only after the Fix2 receipt has been explicitly
reviewed and accepted:

```bash
python \
experiment51_exp52_scientific_freeze_alignment/freeze_experiment51_scientific.py
```

Print only the compact freeze receipt:

```bash
python - <<'PY'
import json

p = (
    "artifacts/v51/external_repository_replication_scientific/"
    "frozen/freeze_receipt.json"
)
d = json.load(open(p))
keys = [
    "repositories",
    "roots",
    "qualification_config_sha256",
    "qualification_summary_sha256",
    "copied_build_receipts_exact",
    "exp52_protocol_sha256",
    "exp52_design_documents_bundle_sha256",
    "exp52_retained_probes",
    "scientific_candidate_execution_before_freeze",
    "scientific_candidate_tactics_executed",
]
print(json.dumps({key: d.get(key) for key in keys}, indent=2))
PY
```

Stop after this receipt and return it for review. Do not run the scientific
worker preflight, environment capture, smoke, or scientific candidates until
the freeze receipt is checked.

## Claim boundary

This package freezes measurement rules only. It produces no scientific result
and supports no claim of tactic equivalence, tactic interchangeability,
semantic equivalence, proof-strategy equivalence, proof-term equality, runtime
equivalence, or improved theorem proving.
