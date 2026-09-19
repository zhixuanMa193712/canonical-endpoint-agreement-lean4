"""LeanDojo compatibility layer shared by Exp62 qualification and search."""
from __future__ import annotations

import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

from experiment62_protocol import *


def load_lean_dojo() -> dict[str, Any]:
    from lean_dojo import Dojo, LeanGitRepo, Theorem  # type: ignore
    from lean_dojo.interaction.dojo import (  # type: ignore
        LeanError,
        ProofFinished,
        TacticState,
    )
    try:
        from lean_dojo.interaction.dojo import DojoTacticTimeoutError  # type: ignore
    except ImportError:
        class DojoTacticTimeoutError(TimeoutError):
            pass
    return {
        "Dojo": Dojo,
        "LeanGitRepo": LeanGitRepo,
        "Theorem": Theorem,
        "LeanError": LeanError,
        "ProofFinished": ProofFinished,
        "TacticState": TacticState,
        "DojoTacticTimeoutError": DojoTacticTimeoutError,
    }


def canonical_repo(api: dict[str, Any]) -> Any:
    local = os.environ.get("EXP62_MATHLIB_REPO")
    if local:
        path = Path(local).expanduser().resolve()
        if not (path / ".git").is_dir():
            raise FileNotFoundError(f"EXP62_MATHLIB_REPO is not a Git checkout: {path}")
        repo = api["LeanGitRepo"].from_path(path)
        if repo.commit != REPO_COMMIT:
            raise ValueError(f"local mathlib commit {repo.commit} != {REPO_COMMIT}")
        object.__setattr__(repo, "url", REPO_URL)
        return repo
    return api["LeanGitRepo"](url=REPO_URL, commit=REPO_COMMIT)


def theorem_for(api: dict[str, Any], repo: Any, target: Mapping[str, Any]) -> Any:
    return api["Theorem"](repo, str(target["file_path"]), str(target["full_name"]))


def run_tactic(api: dict[str, Any], dojo: Any, state: Any, tactic: str) -> dict[str, Any]:
    started = time.monotonic()
    try:
        result = dojo.run_tac(state, tactic)
    except api["DojoTacticTimeoutError"]:
        return {
            "kind": "tactic_timeout",
            "elapsed_seconds_descriptive": time.monotonic() - started,
        }
    except Exception as error:
        return {
            "kind": "operational_exception",
            "error_type": type(error).__name__,
            "error_sha256": json_sha256(str(error)),
            "error_tail": str(error)[-2000:],
            "elapsed_seconds_descriptive": time.monotonic() - started,
        }
    elapsed = time.monotonic() - started
    if isinstance(result, api["ProofFinished"]):
        return {
            "kind": "proof_finished",
            "terminal": True,
            "elapsed_seconds_descriptive": elapsed,
        }
    if isinstance(result, api["TacticState"]):
        text = str(result.pp)
        return {
            "kind": "tactic_state",
            "terminal": False,
            "state_obj": result,
            "state_text": text,
            "state_sha256": json_sha256(text),
            "endpoint_key": endpoint_key(text),
            "elapsed_seconds_descriptive": elapsed,
        }
    if isinstance(result, api["LeanError"]):
        message = str(result.error)
        return {
            "kind": "lean_rejection",
            "error_sha256": json_sha256(message),
            "elapsed_seconds_descriptive": elapsed,
        }
    return {
        "kind": "unexpected_result",
        "result_type": type(result).__name__,
        "elapsed_seconds_descriptive": elapsed,
    }


def environment_receipt(api: dict[str, Any], repo: Any) -> dict[str, Any]:
    import lean_dojo  # type: ignore
    return seal({
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "python": sys.version,
        "platform": platform.platform(),
        "lean_dojo_version": getattr(lean_dojo, "__version__", None),
        "repository_url": str(repo.url),
        "repository_commit": str(repo.commit),
        "local_repo_override": os.environ.get("EXP62_MATHLIB_REPO"),
    })
