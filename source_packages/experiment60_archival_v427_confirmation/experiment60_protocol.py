"""Protocol helpers for the archival-v4.27 prospective confirmation."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent /
                       "experiment56_prospective_confirmation"))
from experiment56_protocol import *


PACKAGE_ROOT_60 = Path(__file__).resolve().parent
WORKSPACE_ROOT_60 = Path(os.environ.get("MZX_ROOT", PACKAGE_ROOT_60.parent)).resolve()
ARTIFACT_ROOT_60 = WORKSPACE_ROOT_60 / "artifacts/v60/archival_v427_confirmation"
PROTOCOL_VERSION_60 = "experiment60-prospective-archival-v427-confirmation-v1"
ARCHIVAL_TAG_PATTERN = r"^(?:lean[-_])?v?4[._-]27[._-]0$"
ARCHIVAL_FEED_MAX_ENTRIES = 20
ARCHIVAL_WORKERS = 24
SOURCE_EXP56_FRAME = WORKSPACE_ROOT_60 / "artifacts/v56/prospective_confirmation/frozen/candidate_frame.jsonl"
SOURCE_EXP56_FRAME_RECEIPT = WORKSPACE_ROOT_60 / "artifacts/v56/prospective_confirmation/frozen/candidate_frame_receipt.json"
SOURCE_EXP56_SHORTFALL = WORKSPACE_ROOT_60 / "artifacts/v56/prospective_confirmation/recruitment_shortfall/summary.json"
BASE_EXP56_PROTOCOL = WORKSPACE_ROOT_60 / "artifacts/v56/prospective_confirmation/frozen/protocol.json"
