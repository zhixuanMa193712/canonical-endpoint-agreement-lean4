"""Freeze Exp51 repository-frame extension 2 before new screening."""
from __future__ import annotations

import json

from experiment51_extension_protocol import *
from experiment51_repository_frame_extension import (  # noqa: E402
    freeze_experiment51_extension as implementation,
)

_extension1_build_config = implementation.build_config


def build_config(created_utc: str) -> dict:
    value = _extension1_build_config(created_utc)
    value["permitted_operations"] = [
        "content-addressed carry-forward of eleven zero-candidate qualification passes",
        "clone and detach seven exact Extension2 commits",
        "unmodified exact-toolchain build",
        "pinned LeanDojo v4.27 trace",
        "single-process parser-compatible root enumeration with remote dependency metadata disabled",
        "authored replay with an empty scientific candidate list only after the twelve-repository build/trace gate",
        "source-lineage measurement",
    ]
    value["next_step"] = (
        "Run Extension2 environment preflight; execute zero theorem roots and zero candidates."
    )
    value["identity_sha256"] = json_sha256({
        key: item for key, item in value.items()
        if key not in {"created_utc", "identity_sha256"}
    })
    return value


implementation.build_config = build_config


if __name__ == "__main__":
    implementation.freeze(implementation.parse_args())
