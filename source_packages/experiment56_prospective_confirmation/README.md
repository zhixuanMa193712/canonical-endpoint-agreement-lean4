# Prospective repository confirmation

This package freezes a new, independently recruited confirmation. It does not
repair or overwrite the historical 96-root study.

The planning design uses 38 lineage-representative repositories and 16 roots
per repository (608 roots). The repository frame, every pass and exclusion,
and both repository and root selection keys must be deposited before any
scientific alternative is run.

Current state: the protocol and power design are executable and frozen. The
repository qualification receipts and scientific results do not yet exist;
they require the Linux Lean 4.27 server and a newly snapshotted external frame.

Server order (run from `/home/music/mzz/MZX` with `MZX_ROOT` exported):

1. `python experiment56_prospective_confirmation/test_experiment56_static.py`
2. `python experiment56_prospective_confirmation/freeze_experiment56.py`
3. `GITHUB_TOKEN=... python experiment56_prospective_confirmation/snapshot_github_frame.py` (four locked,
   disjoint star strata; raw API responses retained)
4. `python experiment56_prospective_confirmation/freeze_candidate_frame.py --input artifacts/v56/prospective_confirmation/recruitment_snapshot/candidate_frame_input.jsonl`
5. `python experiment56_prospective_confirmation/qualify_repository_frame.py --phase all` (this may take a long time;
   use `nohup` and preserve its log)
6. `python experiment56_prospective_confirmation/select_repositories_and_roots.py`
7. if and only if `selection_gate` is true, launch 38 shards with
   `python experiment56_prospective_confirmation/run_prospective_shards.py --shard-index INDEX`
8. `python experiment56_prospective_confirmation/analyze_prospective_confirmation.py`
9. `python experiment56_prospective_confirmation/audit_prospective_confirmation.py`

The candidate snapshot may legitimately yield fewer than 38 independent
eligible repositories. In that case the registered outcome is a recruitment
shortfall: stop and preserve it rather than adding repositories by hand.
