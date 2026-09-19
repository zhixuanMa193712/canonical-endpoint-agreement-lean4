"""Perform an environment-only Exp62 preflight without scientific root execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiment62_protocol import *
from experiment62_dojo import canonical_repo, environment_receipt, load_lean_dojo


def preflight(root: Path) -> dict[str, Any]:
    protocol = load_installed_protocol(root)
    install = read_json(root / "frozen/install_receipt.json")
    assert_sealed(install, "Exp62 install")
    api = load_lean_dojo()
    repo = canonical_repo(api)
    environment = environment_receipt(api, repo)
    atomic_json_dump(environment, root / "preflight/environment.json")
    value = seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "initial_protocol_record_sha256": protocol["record_sha256"],
        "install_gate": install.get("install_gate") is True,
        "lean_dojo_import_gate": True,
        "repository_identity_gate": str(repo.commit) == REPO_COMMIT,
        "scientific_theorem_opened": False,
        "scientific_tactic_executed": False,
        "preflight_gate": install.get("install_gate") is True and str(repo.commit) == REPO_COMMIT,
        "next_step": "Run run_experiment62_qualification.py.",
    })
    atomic_json_dump(value, root / "preflight/summary.json")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(preflight(Path(parse_args().artifact_root).resolve()), indent=2))
