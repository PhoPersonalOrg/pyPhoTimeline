"""main_offline_timeline.py -- Offline timeline from XDF files.

This script creates a PyQt timeline window from one or more XDF files:
  1. Loads streams from the given XDF file paths (optionally filtered by
     stream_allowlist / stream_blocklist).
  2. Builds a :class:`~pypho_timeline.widgets.simple_timeline_widget.SimpleTimelineWidget`
     via :class:`~pypho_timeline.timeline_builder.TimelineBuilder`.
  3. Shows the timeline; scroll/zoom to inspect data.

Usage::

    python main_offline_timeline.py

Edit DEMO_XDF_PATHS and STREAM_BLOCKLIST (or STREAM_ALLOWLIST) below to change
which files and streams are loaded.
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
from typing import List, Optional

import pyqtgraph as pg

from pypho_timeline.timeline_builder import TimelineBuilder


# ─────────────────────────────────────────────────────────────────────────────
# Configuration: XDF paths and stream filters
# ─────────────────────────────────────────────────────────────────────────────

DEMO_XDF_PATHS: List[Path] = [
    Path('E:/Dropbox (Personal)/Databases/UnparsedData/LabRecorderStudies/sub-P001/LabRecorder_Apogee_2026-03-04T225210.949Z_eeg.xdf'),
    Path('E:/Dropbox (Personal)/Databases/UnparsedData/PhoLogToLabStreamingLayer_logs/20260304_225204_log.xdf'),
    Path('E:/Dropbox (Personal)/Databases/UnparsedData/LabRecorderStudies/sub-P001/LabRecorder_Apogee_2026-03-04T192035.507Z_eeg.xdf'),
    Path('E:/Dropbox (Personal)/Databases/UnparsedData/PhoLogToLabStreamingLayer_logs/20260304_192023_log.xdf'),
    Path('E:/Dropbox (Personal)/Databases/UnparsedData/LabRecorderStudies/sub-P001/LabRecorder_Apogee_2026-03-04T191528.965Z_eeg.xdf'),
    Path('E:/Dropbox (Personal)/Databases/UnparsedData/PhoLogToLabStreamingLayer_logs/20260304_191511_log.xdf'),
    Path('E:/Dropbox (Personal)/Databases/UnparsedData/LabRecorderStudies/sub-P001/LabRecorder_Apogee_2026-03-04T162633.469Z_eeg.xdf'),
    Path('E:/Dropbox (Personal)/Databases/UnparsedData/PhoLogToLabStreamingLayer_logs/20260304_162623_log.xdf'),
    Path('E:/Dropbox (Personal)/Databases/UnparsedData/LabRecorderStudies/sub-P001/LabRecorder_Apogee_2026-03-03T223004.805Z_eeg.xdf'),
    Path('E:/Dropbox (Personal)/Databases/UnparsedData/PhoLogToLabStreamingLayer_logs/20260303_222952_log.xdf'),
    Path('E:/Dropbox (Personal)/Databases/UnparsedData/LabRecorderStudies/sub-P001/LabRecorder_Apogee_2026-03-03T191723.860Z_eeg.xdf'),
    Path('E:/Dropbox (Personal)/Databases/UnparsedData/PhoLogToLabStreamingLayer_logs/20260303_191710_log.xdf'),
    Path('E:/Dropbox (Personal)/Databases/UnparsedData/LabRecorderStudies/sub-P001/LabRecorder_Apogee_2026-03-03T012438.863Z_eeg.xdf'),
    Path('E:/Dropbox (Personal)/Databases/UnparsedData/LabRecorderStudies/sub-P001/LabRecorder_Apogee_2026-03-03T005759.073Z_eeg.xdf'),
    Path('E:/Dropbox (Personal)/Databases/UnparsedData/PhoLogToLabStreamingLayer_logs/20260303_005724_log.xdf'),
]

# Optional: only include streams whose name matches any of these patterns (regex).
STREAM_ALLOWLIST: Optional[List[str]] = None  # e.g. [r"EEG.*", r"MOTION.*"]

# Optional: exclude streams whose name matches any of these patterns (regex).
STREAM_BLOCKLIST: Optional[List[str]] = ['Epoc X Motion', 'Epoc X eQuality']


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    """Build and show the offline timeline from XDF files."""
    app = pg.mkQApp("pyPhoTimelineOffline")

    builder: TimelineBuilder = TimelineBuilder()
    timeline = builder.build_from_xdf_files(xdf_file_paths=DEMO_XDF_PATHS, stream_allowlist=STREAM_ALLOWLIST, stream_blocklist=STREAM_BLOCKLIST)

    if timeline is None:
        print("No streams found. Check XDF paths and stream filters.")
        return 1

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
