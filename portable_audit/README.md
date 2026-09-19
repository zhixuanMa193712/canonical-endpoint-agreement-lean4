# Portable audit revision

This directory is an additive publication-layer repair for the Exp48 and
Exp50--Exp54 result bundles.  It does **not** alter any frozen experiment,
scientific row, decision label, or original result ZIP.

The repair addresses two clean-download problems:

1. archived Python entry points assumed the server checkout layout; and
2. immutable rows intentionally retained absolute provenance paths.

`portable_audit.py` verifies every original bundle manifest and then resolves
the retained server paths against files extracted into a temporary directory.
The temporary working tree is deleted after the audit.

Run from an extracted Zenodo release:

```bash
python3 portable_audit/portable_audit.py --release-root .
```

To mark a verification performed from a separately downloaded/extracted copy:

```bash
python3 portable_audit/portable_audit.py \
  --release-root . \
  --independent-clean-download \
  --receipt portable_audit_receipt.json
```

To retain a machine-readable receipt:

```bash
python3 portable_audit/portable_audit.py \
  --release-root . \
  --receipt portable_audit_receipt.json
```

The audit uses only the Python standard library.  It never launches Lean,
never downloads repositories, and never edits the source result ZIPs.

The two gates have distinct meanings:

- `bundle_integrity_gate`: all archived manifest entries have the registered
  size and SHA-256;
- `portable_scientific_audit_gate`: the experiment-specific offline
  reconstruction/decision checks pass from a clean extraction path.

Exp49 was already path portable.  It remains covered by release and internal
manifest verification, but is not counted as a repaired entry point.

Individual repaired workers can also be invoked for diagnosis with
`--worker exp48`, `exp50`, `exp51`, `exp52`, `exp53`, or `exp54`, together with
the matching `--bundle artifacts/<name>.zip`. The default command is preferred
because it enforces the complete release gate.
