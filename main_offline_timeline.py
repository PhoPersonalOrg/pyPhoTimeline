"""main_offline_timeline.py -- Offline timeline from XDF files.

This script creates a PyQt timeline window from one or more XDF files:
  1. Discovers XDF paths via :func:`~pypho_timeline.xdf_session_discovery.discover_xdf_files_for_timeline`
     from the configured database directories.
  2. Loads streams (optionally filtered by stream_allowlist / stream_blocklist).
  3. Builds a :class:`~pypho_timeline.widgets.simple_timeline_widget.SimpleTimelineWidget`
     via :class:`~pypho_timeline.timeline_builder.TimelineBuilder`.
  4. Shows the timeline; scroll/zoom to inspect data.

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
from typing import List, Optional, cast

import time

import pandas as pd

from mne import set_log_level

import pyqtgraph as pg


def get_now_time_str(time_separator='-') -> str:
    return str(time.strftime(f"%Y-%m-%d_%H{time_separator}%m", time.localtime(time.time())))


set_log_level("WARNING")


from pypho_timeline.EXTERNAL.pyqtgraph_extensions.graphicsObjects.CustomLinearRegionItem import CustomLinearRegionItem
from pypho_timeline.timeline_builder import TimelineBuilder
from pypho_timeline.widgets.simple_timeline_widget import FixupMisalignedData, SimpleTimelineWidget
from pypho_timeline.widgets.timeline_overview_strip import TimelineOverviewStrip
from pypho_timeline.xdf_session_discovery import discover_xdf_files_for_timeline


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
# n_most_recent_sessions_to_preprocess: int = 5
n_most_recent_sessions_to_preprocess: int = 15
# n_most_recent_sessions_to_preprocess = None

# enable_video_track: bool = True
enable_video_track: bool = False

# Optional: only include streams whose name matches any of these patterns (regex).
STREAM_ALLOWLIST: Optional[List[str]] = None  # e.g. [r"EEG.*", r"MOTION.*"]

# Optional: exclude streams whose name matches any of these patterns (regex).
# STREAM_BLOCKLIST: Optional[List[str]] = ['Epoc X Motion', 'Epoc X eQuality']
# STREAM_BLOCKLIST: Optional[List[str]] = ['Epoc X eQuality', 'VideoRecorderMarkers']
STREAM_BLOCKLIST: Optional[List[str]] = ['VideoRecorderMarkers']


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
    xdf_to_exported_EDF_parent_export_path = db_root_path.joinpath('AnalysisData/exported_EDF').resolve()
    xdf_to_exported_EDF_parent_export_path.mkdir(exist_ok=True)

    # lab_recorder_output_path = Path(r"E:\Dropbox (Personal)\Databases\UnparsedData\LabRecorderStudies\sub-P001")
    lab_recorder_output_path = db_root_path.joinpath('UnparsedData/LabRecorderStudies/sub-P001')
    assert lab_recorder_output_path.exists()

    xdf_file_cache_filename: str = f"{get_now_time_str()}_found_xdf_files.csv"
    xdf_file_cache_filepath: Path = xdf_to_rerun_rrd_parent_export_path.joinpath(xdf_file_cache_filename).resolve()
    print(f'exporting xdf .csv to xdf_file_cache_filepath: "{xdf_file_cache_filepath}..."')
    discovery = discover_xdf_files_for_timeline(xdf_discovery_dirs=[lab_recorder_output_path, pho_log_to_LSL_recordings_path], n_most_recent=n_most_recent_sessions_to_preprocess, csv_export_path=xdf_file_cache_filepath)
    final_xdf_paths: List[Path] = discovery.xdf_paths
    print(f'processing len(active_EEG_recording_files): {len(final_xdf_paths)} recording files...')


    # ==================================================================================================================================================================================================================================================================================== #
    # BEGIN MAIN                                                                                                                                                                                                                                                                           #
    # ==================================================================================================================================================================================================================================================================================== #
    
    app = pg.mkQApp("pyPhoTimelineOffline")

    builder: TimelineBuilder = TimelineBuilder()
    active_video_discovery_dirs: List[Path] = [video_recordings_path] if enable_video_track and video_recordings_path.exists() and video_recordings_path.is_dir() else []
    builder.set_refresh_config(xdf_discovery_dirs=[lab_recorder_output_path, pho_log_to_LSL_recordings_path], n_most_recent=n_most_recent_sessions_to_preprocess, stream_allowlist=STREAM_ALLOWLIST, stream_blocklist=STREAM_BLOCKLIST, video_discovery_dirs=active_video_discovery_dirs)
    timeline: Optional[SimpleTimelineWidget] = builder.build_from_xdf_files(xdf_file_paths=final_xdf_paths, stream_allowlist=STREAM_ALLOWLIST, stream_blocklist=STREAM_BLOCKLIST)

    if timeline is None:
        print("No streams found. Check XDF paths and stream filters.")
        return 1

    all_track_names = timeline.get_all_track_names()
    print(f"all_track_names: {all_track_names}")

    eeg_ds = None
    if 'EEG_Epoc X' in all_track_names:
        eeg_widget, eeg_track, eeg_ds = timeline.get_track_tuple('EEG_Epoc X')
        detailed_eeg_df: pd.DataFrame = eeg_ds.detailed_df
    else:
        print("WARN: expected EEG_Epoc X track was not found.")

    if 'MOTION_Epoc X Motion' in all_track_names:
        motion_widget, motion_track, motion_ds = timeline.get_track_tuple('MOTION_Epoc X Motion')
    else:
        print("WARN: expected MOTION_Epoc X Motion track was not found.")

    if 'LOG_TextLogger' in all_track_names:
        txt_log_widget, txt_log_renderer, txt_log_ds = timeline.get_track_tuple('LOG_TextLogger')
    else:
        print("WARN: expected LOG_TextLogger track was not found.")

    eeg_spectogram_track_names = ['EEG_Spectrogram_Epoc X_Frontal-L', 'EEG_Spectrogram_Epoc X_Frontal-R', 'EEG_Spectrogram_Epoc X_Posterior-L', 'EEG_Spectrogram_Epoc X_Posterior-R', 'EEG_Spectrogram_Epoc X_All']
    for a_spectogram_track_name in eeg_spectogram_track_names:
        if a_spectogram_track_name in all_track_names:
            a_spectogram_widget, a_spectogram_track, a_spectogram_ds = timeline.get_track_tuple(a_spectogram_track_name)
            a_root_graphics_layout_widget = a_spectogram_widget.getRootGraphicsLayoutWidget()
            a_plot_item = a_spectogram_widget.getRootPlotItem()
            a_plot_item.hideAxis('bottom')

    timeline.hide_extra_xaxis_labels_and_axes(enable_hide_extra_track_x_axes=True)

    if eeg_ds is not None:
        try:
            eeg_track_correction_delta = FixupMisalignedData.extract_eeg_track_correction_delta(eeg_ds=eeg_ds)
            FixupMisalignedData.fix_all_timeline_tracks(timeline=timeline, eeg_track_correction_delta=eeg_track_correction_delta)
        except Exception as exc:
            print(f"WARN: could not apply FixupMisalignedData correction: {exc}")
    else:
        print("WARN: skipping FixupMisalignedData because EEG datasource is unavailable.")

    [timeline.add_new_now_line_for_plot_item(widget.getRootPlotItem()) for widget in timeline.ui.matplotlib_view_widgets.values()]
    timeline.update_now_lines()

    strip: TimelineOverviewStrip = timeline.ui.timeline_overview_strip
    region: CustomLinearRegionItem = strip._viewport_region

    if enable_video_track:
        # Machine-specific folders from notebook run-main flow.
        from phopylslhelper.file_metadata_caching.manager import BaseFileMetadataManager
        from phopylslhelper.file_metadata_caching.video_metadata import VideoMetadataParser
        from pypho_timeline.__main__ import VideoTrackDatasource

        video_manager: BaseFileMetadataManager = BaseFileMetadataManager(parse_folders=[Path("M:/ScreenRecordings/EyeTrackerVR_Recordings"), Path("M:/ScreenRecordings/REC_continuous_video_recorder")], parsers={'video': VideoMetadataParser})
        recent_videos: List[Path] = video_manager.get_most_recent_video_paths(max_num_videos=25)
        video_ds: VideoTrackDatasource = VideoTrackDatasource(video_paths=cast(List[Path | str], recent_videos))
        video_track_name: str = "RecentVideosTrack"
        video_widget, root_graphics, plot_item, dock = timeline.add_video_track(track_name=video_track_name, video_datasource=video_ds, enable_time_crosshair=True)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
