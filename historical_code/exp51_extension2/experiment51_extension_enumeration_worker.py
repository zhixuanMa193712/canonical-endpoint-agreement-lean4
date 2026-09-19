"""Isolated Extension2 parser worker; inherits the locked Extension1 mechanism."""
from __future__ import annotations

from pathlib import Path

from experiment51_extension_protocol import *  # noqa: F401,F403
from experiment51_repository_frame_extension import (  # noqa: E402
    experiment51_extension_enumeration_worker as implementation,
)


if __name__ == "__main__":
    args = implementation.parse_args()
    implementation.run(Path(args.input))
