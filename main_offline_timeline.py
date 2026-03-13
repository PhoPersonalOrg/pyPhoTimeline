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

import time

from typing import Dict, List, Tuple, Any
from matplotlib import pyplot as plt

import numpy as np
import pandas as pd

from mne import set_log_level

from phopymnehelper.historical_data import HistoricalData
from phopymnehelper.SavedSessionsProcessor import SavedSessionsProcessor, SessionModality, DataModalityType

from qtpy import QtCore, QtGui, QtWidgets
import pyqtgraph as pg


def get_now_time_str(time_separator='-') -> str:
    return str(time.strftime(f"%Y-%m-%d_%H{time_separator}%m", time.localtime(time.time())))


set_log_level("WARNING")


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


# n_most_recent_sessions_to_preprocess: int = None # None means all sessions
# n_most_recent_sessions_to_preprocess: int = 100
# n_most_recent_sessions_to_preprocess: int = 35
n_most_recent_sessions_to_preprocess: int = 5
# n_most_recent_sessions_to_preprocess: int = 15
# n_most_recent_sessions_to_preprocess = None

# Optional: only include streams whose name matches any of these patterns (regex).
STREAM_ALLOWLIST: Optional[List[str]] = None  # e.g. [r"EEG.*", r"MOTION.*"]

# Optional: exclude streams whose name matches any of these patterns (regex).
STREAM_BLOCKLIST: Optional[List[str]] = ['Epoc X Motion', 'Epoc X eQuality']


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    """Build and show the offline timeline from XDF files."""


    # db_root_path = Path('/content/drive/MyDrive/Databases')
    # db_root_path = Path(r'E:/Dropbox (Personal)/Databases') ## APOGEE
    db_root_path = Path(r'E:/Dropbox (Personal)/Databases') # WIN10_VM
    assert db_root_path.exists(), f"'{db_root_path.as_posix()}' does not exist!"

    # eeg_recordings_file_path: Path = Path(r'E:/Dropbox (Personal)/Databases/UnparsedData/EmotivEpocX_EEGRecordings/fif')
    # headset_motion_recordings_file_path: Path = Path(r'E:/Dropbox (Personal)/Databases/UnparsedData/EmotivEpocX_EEGRecordings/MOTION_RECORDINGS/fif')

    # assert eeg_recordings_file_path.exists()
    # assert headset_motion_recordings_file_path.exists()

    # eeg_recordings_file_path: Path = db_root_path.joinpath('UnparsedData/EmotivEpocX_EEGRecordings/fif')
    # flutter_eeg_recordings_file_path: Path = db_root_path.joinpath('UnparsedData/EmotivEEG_FlutterRecordings')
    # flutter_motion_recordings_file_path: Path = db_root_path.joinpath('UnparsedData/EmotivEEG_FlutterRecordings/MOTION_RECORDINGS')
    # flutter_GENERIC_recordings_file_path: Path = db_root_path.joinpath('UnparsedData/EmotivEEG_FlutterRecordings/GENERIC_RECORDINGS')

    # headset_motion_recordings_file_path: Path = db_root_path.joinpath('UnparsedData/EmotivEpocX_EEGRecordings/MOTION_RECORDINGS/fif')
    # WhisperVideoTranscripts_LSL_Converted = db_root_path.joinpath('UnparsedData/WhisperVideoTranscripts_LSL_Converted')
    pho_log_to_LSL_recordings_path: Path = db_root_path.joinpath('UnparsedData/PhoLogToLabStreamingLayer_logs')
    video_recordings_path: Path = db_root_path.joinpath('UnparsedData/LabRecorderStudies/sub-P001/Videos')
    ## These contain little LSL .fif files with names like: '20250808_062814_log.fif',

    # eeg_analyzed_parent_export_path = db_root_path.joinpath('AnalysisData/MNE_preprocessed')
    # pickled_data_path = db_root_path.joinpath('AnalysisData/MNE_preprocessed/PICKLED_COLLECTION')
    # assert pickled_data_path.exists()
    xdf_to_rerun_rrd_parent_export_path = db_root_path.joinpath('AnalysisData/to_rerun_rrd').resolve()
    xdf_to_rerun_rrd_parent_export_path.mkdir(exist_ok=True)
    # print(f'xdf_to_rerun_rrd_parent_export_path: "{xdf_to_rerun_rrd_parent_export_path.as_posix()}"')

    # lab_recorder_output_path = Path(r"E:\Dropbox (Personal)\Databases\UnparsedData\LabRecorderStudies\sub-P001")
    lab_recorder_output_path = db_root_path.joinpath('UnparsedData/LabRecorderStudies/sub-P001')
    assert lab_recorder_output_path.exists()



    # modern_found_EEG_recording_files = HistoricalData.get_recording_files(recordings_dir=lab_recorder_output_path, recordings_extensions=['.xdf'])
    modern_found_EEG_recording_files = HistoricalData.get_recording_files(recordings_dir=[lab_recorder_output_path, pho_log_to_LSL_recordings_path], recordings_extensions=['.xdf']) ## both sources
    # modern_found_EEG_recording_files

    most_recent_modern_found_EEG_recording_files: List[Path] = modern_found_EEG_recording_files[:n_most_recent_sessions_to_preprocess]
    # most_recent_modern_found_EEG_recording_files


    # active_EEG_recording_files = modern_found_EEG_recording_files
    active_EEG_recording_files = most_recent_modern_found_EEG_recording_files

    print(f'processing len(active_EEG_recording_files): {len(active_EEG_recording_files)} recording files...')
    most_recent_modern_found_EEG_recording_file_df: pd.DataFrame = HistoricalData.build_file_comparison_df(recording_files=active_EEG_recording_files) ## 8m for 65 files
    # most_recent_modern_found_EEG_recording_file_df: pd.DataFrame = HistoricalData.build_file_comparison_df(recording_files=most_recent_modern_found_EEG_recording_files) ## 5m for 35 files !! SLOWER: 9.2min for 35 files
    most_recent_modern_found_EEG_recording_file_df


    # modern_found_EEG_recording_file_df: pd.DataFrame = HistoricalData.build_file_comparison_df(recording_files=modern_found_EEG_recording_files)
    # modern_found_EEG_recording_file_df

    ## OUTPUTS: modern_found_EEG_recording_file_df, modern_found_EEG_recording_files

    ## INPUTS: most_recent_modern_found_EEG_recording_file_df

    xdf_file_cache_filename: str = f"{get_now_time_str()}_found_xdf_files.csv"
    xdf_file_cache_filepath: Path = xdf_to_rerun_rrd_parent_export_path.joinpath(xdf_file_cache_filename).resolve()

    print(f'exporting xdf .csv to xdf_file_cache_filepath: "{xdf_file_cache_filepath}..."')
    most_recent_modern_found_EEG_recording_file_df.to_csv(xdf_file_cache_filepath)


    most_recent_modern_found_EEG_recording_file_df['src_file'].to_list()
    final_xdf_paths: List[Path] = [Path(v) for v in most_recent_modern_found_EEG_recording_file_df['src_file'].to_list()]
    final_xdf_paths

    ## OUTPUTS: final_xdf_paths


    # ==================================================================================================================================================================================================================================================================================== #
    # BEGIN MAIN                                                                                                                                                                                                                                                                           #
    # ==================================================================================================================================================================================================================================================================================== #
    
    app = pg.mkQApp("pyPhoTimelineOffline")

    builder: TimelineBuilder = TimelineBuilder()
    active_video_discovery_dirs: List[Path] = [video_recordings_path] if video_recordings_path.exists() and video_recordings_path.is_dir() else []
    builder.set_refresh_config(xdf_discovery_dirs=[lab_recorder_output_path, pho_log_to_LSL_recordings_path], n_most_recent=n_most_recent_sessions_to_preprocess, stream_allowlist=STREAM_ALLOWLIST, stream_blocklist=STREAM_BLOCKLIST, video_discovery_dirs=active_video_discovery_dirs)
    timeline = builder.build_from_xdf_files(xdf_file_paths=final_xdf_paths, stream_allowlist=STREAM_ALLOWLIST, stream_blocklist=STREAM_BLOCKLIST)

    if timeline is None:
        print("No streams found. Check XDF paths and stream filters.")
        return 1

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
