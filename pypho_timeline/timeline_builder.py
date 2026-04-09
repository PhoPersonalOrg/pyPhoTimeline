"""
TimelineBuilder - A class for building and updating timeline widgets from various input sources.

This module provides a unified interface for creating SimpleTimelineWidget instances
from different data sources such as XDF files, pre-loaded streams, or existing datasources.
"""

from pathlib import Path
from typing import Callable, Dict, List, Tuple, Optional, Union, Any, Set
from datetime import datetime, timezone, timedelta
import logging
import re
import numpy as np
import pandas as pd
import pyxdf
from qtpy import QtWidgets, QtCore
from pypho_timeline.widgets import SimpleTimelineWidget
from pypho_timeline.widgets.TimelineWindow.MainTimelineWindow import MainTimelineWindow
from pypho_timeline.rendering.datasources.stream_to_datasources import perform_process_single_xdf_file_all_streams, perform_process_all_streams_multi_xdf, default_dock_named_color_scheme_key
from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode
from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, IntervalProvidingTrackDatasource
from pypho_timeline.EXTERNAL.pyqtgraph.dockarea.Dock import DockButtonConfig
from pypho_timeline.EXTERNAL.pyqtgraph.icons import getGraphIcon
from pypho_timeline.docking.dock_display_configs import CustomCyclicColorsDockDisplayConfig, CustomDockDisplayConfig, NamedColorScheme, get_utility_dock_colors
from pypho_timeline.utils.logging_util import configure_logging, add_qt_log_handler, get_rendering_logger
from pypho_timeline.widgets import LogWidget
from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp, get_earliest_reference_datetime, datetime_to_float, float_to_datetime
from pypho_timeline.rendering.helpers import ChannelNormalizationMode
from pypho_timeline.xdf_session_discovery import discover_xdf_files_for_timeline, select_most_recent_xdf_file


logger = None # get_rendering_logger(__name__)
logger = configure_logging( ## updates the global logger variable
    log_level=logging.DEBUG,
    log_file=None,
    log_to_console=True,
    log_to_file=False,
)

MIN_ACTIVE_XDF_POLL_INTERVAL_SECONDS: float = 1.0


class _ActiveXdfReloadWorker(QtCore.QObject):
    """Runs ``pyxdf`` + datasource rebuild off the GUI thread for active (growing) ``.xdf`` polling."""

    finished = QtCore.Signal(object, object)
    failed = QtCore.Signal(object, object)

    def __init__(self, signature_at_start: Tuple[int, int], collect_fn: Callable[[], Dict[str, TrackDatasource]], parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self._signature_at_start = signature_at_start
        self._collect_fn = collect_fn


    @QtCore.Slot()
    def run(self) -> None:
        try:
            self.finished.emit(self._collect_fn(), self._signature_at_start)
        except Exception as e:
            self.failed.emit(e, self._signature_at_start)


# Import MNE (optional - may not be available)
try:
    import mne
    MNE_AVAILABLE = True
except ImportError:
    MNE_AVAILABLE = False
    mne = None

# Import datasources
try:
    from pypho_timeline.rendering.datasources.specific.eeg import EEGTrackDatasource, EEGSpectrogramTrackDatasource
    from pypho_timeline.rendering.datasources.specific.motion import MotionTrackDatasource
    from pypho_timeline.rendering.detail_renderers.log_text_plot_renderer import LogTextDataFramePlotDetailRenderer
except ImportError:
    EEGTrackDatasource = None
    EEGSpectrogramTrackDatasource = None
    MotionTrackDatasource = None
    LogTextDataFramePlotDetailRenderer = None

try:
    from phopymnehelper.analysis.computations.specific.EEG_Spectograms import compute_raw_eeg_spectrogram
    EEG_SPECTROGRAM_AVAILABLE = True
except ImportError:
    compute_raw_eeg_spectrogram = None
    EEG_SPECTROGRAM_AVAILABLE = False

# Import VideoTrackDatasource for video-only timeline building
try:
    from pypho_timeline.rendering.datasources.specific.video import VideoTrackDatasource
except ImportError:
    VideoTrackDatasource = None


class TimelineBuilder:
    """Builder class for creating and updating SimpleTimelineWidget instances from various input sources.
    
    This class provides methods to build timeline widgets from:
    - XDF files (via build_from_xdf_file)
    - Pre-loaded streams (via build_from_streams)
    - Existing datasources (via build_from_datasources)
    - Video tracks only (via build_from_video)
    - Updating existing timeline widgets (via update_timeline)
    
    Example usage:
        builder = TimelineBuilder()
        timeline = builder.build_from_xdf_file(Path("data.xdf"))
        # Or build from video only:
        timeline = builder.build_from_video(video_folder_path=Path("path/to/videos"))


    Main Call Hierarchy
        cls.build_from_xdf_files(...)

            for ...
                streams, file_header = pyxdf.load_xdf(str(xdf_file_path))
            ## Calls `perform_process_all_streams_multi_xdf(...)` to process streams from all files and merge by stream name
            all_streams, all_streams_datasources = perform_process_all_streams_multi_xdf(streams_list=all_streams_by_file, xdf_file_paths=xdf_file_paths, file_headers=all_file_headers)

            self.build_from_datasources
    """
    
    def __init__(self, log_level: int = logging.DEBUG, log_file: Optional[Path] = None, log_to_console: bool = False, log_to_file: bool = True):
        """Initialize the TimelineBuilder with logging configuration.
        
        Args:
            log_level: Logging level (default: logging.DEBUG)
            log_file: Path to log file (default: None, uses "timeline_rendering.log")
            log_to_console: Whether to log to console (default: True)
            log_to_file: Whether to log to file (default: True)
        """
        self.log_level = log_level
        self.log_file = log_file if log_file is not None else Path('EXTERNAL/LOGGING').resolve().joinpath("timeline_rendering.log")
        self.log_to_console = log_to_console
        self.log_to_file = log_to_file
        self.log_widget = None
        self._current_main_window = None
        self._current_timeline = None
        self._refresh_config: Optional[Dict[str, Any]] = None
        self._loaded_xdf_paths: Set[Path] = set()
        self._loaded_video_paths: Set[Path] = set()
        self._refresh_generation: int = 0
        self._active_xdf_path: Optional[Path] = None
        self._active_xdf_last_signature: Optional[Tuple[int, int]] = None
        self._active_xdf_poll_timer: Optional[QtCore.QTimer] = None
        self._active_xdf_poll_interval_seconds: float = 10.0
        self._active_xdf_reload_thread: Optional[QtCore.QThread] = None
        self._active_xdf_reload_worker: Optional[_ActiveXdfReloadWorker] = None
        self._active_xdf_refresh_busy: bool = False


        # Create log widget
        self.log_widget = LogWidget()

        # Configure logging
        logger = configure_logging( ## updates the global logger variable
            log_level=self.log_level,
            log_file=self.log_file,
            log_to_console=self.log_to_console,
            log_to_file=self.log_to_file
        )
    
        # Add Qt handler for widget display
        add_qt_log_handler(logger, self.log_widget, log_level=logging.DEBUG)

        if self.log_to_console or self.log_to_file:
            logger.info(f"Logging configured for TimelineBuilder - console: {self.log_to_console}, file: {self.log_to_file} ({self.log_file})")


    def set_refresh_config(self, xdf_discovery_dirs: Optional[List[Path]] = None, n_most_recent: Optional[int] = None, stream_allowlist: Optional[List[str]] = None, stream_blocklist: Optional[List[str]] = None, video_discovery_dirs: Optional[List[Path]] = None, video_extensions: Optional[List[str]] = None, enable_active_xdf_monitoring: bool = True, active_xdf_poll_interval_seconds: float = 10.0):
        xdf_discovery_dirs = [Path(p) for p in (xdf_discovery_dirs or [])]
        video_discovery_dirs = [Path(p) for p in (video_discovery_dirs or [])]
        self._active_xdf_poll_interval_seconds = self._clamp_poll_interval_seconds(active_xdf_poll_interval_seconds)
        self._refresh_config = {
            "xdf_discovery_dirs": xdf_discovery_dirs,
            "n_most_recent": n_most_recent,
            "stream_allowlist": stream_allowlist,
            "stream_blocklist": stream_blocklist,
            "video_discovery_dirs": video_discovery_dirs,
            "video_extensions": tuple(video_extensions or ['.mp4', '.avi', '.mov', '.mkv', '.wmv']),
            "enable_active_xdf_monitoring": bool(enable_active_xdf_monitoring),
            "active_xdf_poll_interval_seconds": self._active_xdf_poll_interval_seconds,
        }
        if not bool(enable_active_xdf_monitoring):
            self._stop_active_xdf_monitoring()


    def _append_refresh_log(self, message: str, level: int = logging.INFO, level_name: str = "INFO"):
        logger.log(level, message)
        if self._current_main_window is not None and hasattr(self._current_main_window, "_log_widget"):
            self._current_main_window._log_widget.append_log(message, level, level_name)

    def _clamp_poll_interval_seconds(self, poll_interval_seconds: float) -> float:
        return max(float(poll_interval_seconds), MIN_ACTIVE_XDF_POLL_INTERVAL_SECONDS)


    def _enable_heavy_xdf_processing(self) -> bool:
        if self._refresh_config is None:
            return True
        return bool(self._refresh_config.get("enable_heavy_xdf_processing", not self._refresh_config.get("enable_active_xdf_monitoring", False)))


    def _teardown_active_xdf_reload_thread(self, wait_ms: int = 2000) -> None:
        if self._active_xdf_reload_thread is not None:
            try:
                self._active_xdf_reload_thread.quit()
                self._active_xdf_reload_thread.wait(wait_ms)
            except Exception:
                pass
            self._active_xdf_reload_thread = None
        self._active_xdf_reload_worker = None


    def _embed_log_widget_in_timeline(self, timeline: SimpleTimelineWidget) -> None:
        if self.log_widget is None:
            return
        dock_area = timeline.ui.dynamic_docked_widget_container
        if dock_area.find_display_dock('log_widget') is not None:
            self.log_widget.show()
            return
        self.log_widget.hide()
        _log_dock_display_config = CustomDockDisplayConfig()
        _log_dock_display_config.custom_get_colors_callback = get_utility_dock_colors
        _, _dock = dock_area.add_display_dock(identifier='log_widget', widget=self.log_widget, dockSize=(800, 200), dockAddLocationOpts=['bottom'], display_config=_log_dock_display_config)
        self.log_widget.show()


    def _sync_main_window_session_jump_controls(self, main_window: Optional[Any] = None) -> None:
        mw = main_window if main_window is not None else self._current_main_window
        if mw is not None and hasattr(mw, "sync_session_jump_controls"):
            mw.sync_session_jump_controls()

    def _build_discovered_xdf_paths(self, xdf_discovery_dirs: List[Path], n_most_recent: Optional[int]) -> List[Path]:
        return discover_xdf_files_for_timeline(xdf_discovery_dirs=xdf_discovery_dirs, n_most_recent=n_most_recent).xdf_paths


    def _get_file_signature(self, file_path: Path) -> Optional[Tuple[int, int]]:
        try:
            stat_result = file_path.stat()
            return (int(stat_result.st_size), int(stat_result.st_mtime_ns))
        except OSError:
            return None


    def _select_active_xdf_path(self, candidate_paths: List[Path]) -> Optional[Path]:
        return select_most_recent_xdf_file(candidate_paths)


    def _start_active_xdf_monitoring(self) -> None:
        if self._refresh_config is None or not self._refresh_config.get("enable_active_xdf_monitoring", False):
            self._stop_active_xdf_monitoring()
            return
        if self._active_xdf_path is None:
            self._stop_active_xdf_monitoring()
            return
        interval_ms = int(float(self._refresh_config.get("active_xdf_poll_interval_seconds", self._active_xdf_poll_interval_seconds)) * 1000.0)
        if self._active_xdf_poll_timer is None:
            self._active_xdf_poll_timer = QtCore.QTimer()
            self._active_xdf_poll_timer.timeout.connect(self._on_active_xdf_poll_timer)
        self._active_xdf_poll_timer.setInterval(interval_ms)
        self._active_xdf_poll_timer.start()


    def _stop_active_xdf_monitoring(self) -> None:
        if self._active_xdf_poll_timer is not None:
            self._active_xdf_poll_timer.stop()


    def _on_active_xdf_poll_timer(self) -> None:
        self.refresh_from_directories(async_active_xdf_reload=True)


    def _schedule_async_active_xdf_reload(self, refresh_paths: List[Path], stream_allowlist: Optional[List[str]], stream_blocklist: Optional[List[str]], signature_at_start: Tuple[int, int]) -> None:
        if self._active_xdf_refresh_busy:
            return
        self._active_xdf_refresh_busy = True
        self._teardown_active_xdf_reload_thread(wait_ms=2000)
        parent = self._current_main_window if self._current_main_window is not None else None
        thread = QtCore.QThread(parent)
        enable_raw = self._enable_heavy_xdf_processing()
        collect_fn = lambda rp=refresh_paths, sa=stream_allowlist, sb=stream_blocklist, er=enable_raw: self._collect_datasources_by_name_for_paths(rp, stream_allowlist=sa, stream_blocklist=sb, enable_raw_xdf_processing=er)
        worker = _ActiveXdfReloadWorker(signature_at_start, collect_fn)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_async_active_xdf_reload_finished)
        worker.failed.connect(self._on_async_active_xdf_reload_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._on_async_active_xdf_thread_finished)
        self._active_xdf_reload_thread = thread
        self._active_xdf_reload_worker = worker
        thread.start()


    def _on_async_active_xdf_reload_finished(self, refreshed_map: Any, signature_at_start: Any) -> None:
        self._active_xdf_refresh_busy = False
        try:
            if self._current_timeline is None:
                return
            refreshed_datasource_count = self._refresh_existing_timeline_datasources(self._current_timeline, refreshed_map, update_time_range=True)
            self._active_xdf_last_signature = signature_at_start
            if refreshed_datasource_count > 0 and self._active_xdf_path is not None:
                self._append_refresh_log(f"Updated {refreshed_datasource_count} active track datasource(s) from open XDF (background): {self._active_xdf_path.name}", level=logging.INFO, level_name="INFO")
        except Exception as e:
            self._append_refresh_log(f"Active XDF refresh apply failed: {e}", level=logging.ERROR, level_name="ERROR")


    def _on_async_active_xdf_reload_failed(self, err: Any, signature_at_start: Any) -> None:
        self._active_xdf_refresh_busy = False
        self._append_refresh_log(f"Active XDF background reload failed: {err}", level=logging.ERROR, level_name="ERROR")


    def _on_async_active_xdf_thread_finished(self) -> None:
        self._active_xdf_reload_thread = None
        self._active_xdf_reload_worker = None


    def _collect_datasources_by_name_for_paths(self, xdf_paths: List[Path], stream_allowlist: Optional[List[str]] = None, stream_blocklist: Optional[List[str]] = None, enable_raw_xdf_processing: Optional[bool] = None) -> Dict[str, TrackDatasource]:
        all_streams_by_file = []
        all_file_headers = []
        all_loaded_paths = []
        for xdf_file_path in xdf_paths:
            try:
                streams, file_header = pyxdf.load_xdf(str(xdf_file_path))
                if (stream_allowlist is not None) or (stream_blocklist is not None):
                    streams = self._filter_streams_by_name(streams, stream_allowlist=stream_allowlist, stream_blocklist=stream_blocklist)
                all_streams_by_file.append(streams)
                all_file_headers.append(file_header)
                all_loaded_paths.append(xdf_file_path)
            except Exception as err:
                logger.warning(f'failed to load file {xdf_file_path} with error: {err}. Skipping.')
        if len(all_streams_by_file) == 0:
            return {}
        raw_proc = self._enable_heavy_xdf_processing() if enable_raw_xdf_processing is None else bool(enable_raw_xdf_processing)
        _, all_streams_datasources = perform_process_all_streams_multi_xdf(streams_list=all_streams_by_file, xdf_file_paths=all_loaded_paths, file_headers=all_file_headers, enable_raw_xdf_processing=raw_proc)
        return {k: v for k, v in all_streams_datasources.items() if v is not None}


    def _refresh_existing_timeline_datasources(self, timeline: SimpleTimelineWidget, datasources_by_name: Dict[str, TrackDatasource], update_time_range: bool = True) -> int:
        updated_count = 0
        for track_name, existing_ds in timeline.track_datasources.items():
            incoming_ds = datasources_by_name.get(track_name, None)
            if incoming_ds is None:
                continue
            if hasattr(existing_ds, "intervals_df") and hasattr(incoming_ds, "intervals_df"):
                existing_ds.intervals_df = incoming_ds.intervals_df.copy()
            if hasattr(existing_ds, "detailed_df") and hasattr(incoming_ds, "detailed_df"):
                incoming_detailed = getattr(incoming_ds, "detailed_df", None)
                existing_ds.detailed_df = incoming_detailed.copy() if incoming_detailed is not None else None
            if hasattr(existing_ds, "lab_obj_dict") and hasattr(incoming_ds, "lab_obj_dict"):
                existing_ds.lab_obj_dict = getattr(incoming_ds, "lab_obj_dict", {})
            if hasattr(existing_ds, "raw_datasets_dict") and hasattr(incoming_ds, "raw_datasets_dict"):
                existing_ds.raw_datasets_dict = getattr(incoming_ds, "raw_datasets_dict", None)
            if hasattr(existing_ds, "normalization_reference_df") and hasattr(incoming_ds, "normalization_reference_df"):
                incoming_norm = getattr(incoming_ds, "normalization_reference_df", None)
                existing_ds.normalization_reference_df = incoming_norm.copy() if incoming_norm is not None else None
            if hasattr(existing_ds, "source_data_changed_signal"):
                existing_ds.source_data_changed_signal.emit()
            updated_count += 1
        if update_time_range and len(timeline.track_datasources) > 0:
            starts = [ds.total_df_start_end_times[0] for ds in timeline.track_datasources.values() if ds is not None]
            ends = [ds.total_df_start_end_times[1] for ds in timeline.track_datasources.values() if ds is not None]
            if len(starts) > 0 and len(ends) > 0:
                first_start = starts[0]
                if isinstance(first_start, (datetime, pd.Timestamp)):
                    to_timestamp_sort_key = lambda x: pd.Timestamp(x) if not isinstance(x, pd.Timestamp) else x
                    total_start_time = min(starts, key=to_timestamp_sort_key)
                    total_end_time = max(ends, key=to_timestamp_sort_key)
                else:
                    total_start_time = float(np.nanmin(starts))
                    total_end_time = float(np.nanmax(ends))
                timeline.total_data_start_time = total_start_time
                timeline.total_data_end_time = total_end_time
                timeline.spikes_window.total_df_start_end_times = (total_start_time, total_end_time)
                if hasattr(timeline.ui, "calendar") and timeline.ui.calendar is not None:
                    timeline.ui.calendar.set_total_range(total_start_time, total_end_time)
                if hasattr(timeline.ui, "compare_calendar") and timeline.ui.compare_calendar is not None:
                    timeline.ui.compare_calendar.set_total_range(total_start_time, total_end_time)
        return updated_count


    def _collect_new_datasources_for_xdf_path(self, xdf_file_path: Path, stream_allowlist: Optional[List[str]] = None, stream_blocklist: Optional[List[str]] = None, enable_raw_xdf_processing: Optional[bool] = None) -> List[TrackDatasource]:
        streams, file_header = pyxdf.load_xdf(str(xdf_file_path))
        if (stream_allowlist is not None) or (stream_blocklist is not None):
            streams = self._filter_streams_by_name(streams, stream_allowlist=stream_allowlist, stream_blocklist=stream_blocklist)
        if len(streams) == 0:
            return []
        raw_proc = self._enable_heavy_xdf_processing() if enable_raw_xdf_processing is None else bool(enable_raw_xdf_processing)
        _, all_streams_datasources = perform_process_all_streams_multi_xdf(streams_list=[streams], xdf_file_paths=[xdf_file_path], file_headers=[file_header], enable_raw_xdf_processing=raw_proc)
        output_datasources: List[TrackDatasource] = []
        for datasource in all_streams_datasources.values():
            if datasource is None:
                continue
            datasource.custom_datasource_name = f"{datasource.custom_datasource_name} [{xdf_file_path.stem}]"
            output_datasources.append(datasource)
        return output_datasources


    def refresh_from_directories(self, async_active_xdf_reload: bool = False):
        if self._current_timeline is None or self._current_main_window is None:
            self._append_refresh_log("Refresh skipped: timeline window is not ready yet.", level=logging.WARNING, level_name="WARNING")
            return
        if self._refresh_config is None:
            self._append_refresh_log("Refresh skipped: no discovery directories were configured at startup.", level=logging.WARNING, level_name="WARNING")
            return
        xdf_discovery_dirs: List[Path] = self._refresh_config.get("xdf_discovery_dirs", [])
        n_most_recent: Optional[int] = self._refresh_config.get("n_most_recent", None)
        stream_allowlist: Optional[List[str]] = self._refresh_config.get("stream_allowlist", None)
        stream_blocklist: Optional[List[str]] = self._refresh_config.get("stream_blocklist", None)
        enable_active_xdf_monitoring: bool = bool(self._refresh_config.get("enable_active_xdf_monitoring", False))
        video_discovery_dirs: List[Path] = self._refresh_config.get("video_discovery_dirs", [])
        video_extensions: Tuple[str, ...] = self._refresh_config.get("video_extensions", ('.mp4', '.avi', '.mov', '.mkv', '.wmv'))
        self._append_refresh_log("Refreshing XDF/Video directories...", level=logging.INFO, level_name="INFO")
        try:
            discovered_xdf_paths: List[Path] = self._build_discovered_xdf_paths(xdf_discovery_dirs=xdf_discovery_dirs, n_most_recent=n_most_recent)
            if enable_active_xdf_monitoring:
                self._active_xdf_path = self._select_active_xdf_path(discovered_xdf_paths)
                self._start_active_xdf_monitoring()
            new_xdf_paths: List[Path] = [p for p in discovered_xdf_paths if p not in self._loaded_xdf_paths]
            for xdf_path in new_xdf_paths:
                self._append_refresh_log(f"Discovered new XDF: {xdf_path}", level=logging.INFO, level_name="INFO")
            all_new_datasources: List[TrackDatasource] = []
            for xdf_path in new_xdf_paths:
                try:
                    all_new_datasources.extend(self._collect_new_datasources_for_xdf_path(xdf_file_path=xdf_path, stream_allowlist=stream_allowlist, stream_blocklist=stream_blocklist))
                    self._loaded_xdf_paths.add(xdf_path)
                except Exception as e:
                    self._append_refresh_log(f"Failed to load new XDF '{xdf_path}': {e}", level=logging.ERROR, level_name="ERROR")
            refreshed_datasource_count = 0
            async_reload_scheduled = False
            if enable_active_xdf_monitoring and (self._active_xdf_path is not None) and (self._active_xdf_path in self._loaded_xdf_paths):
                current_signature = self._get_file_signature(self._active_xdf_path)
                if (current_signature is not None) and (current_signature != self._active_xdf_last_signature):
                    refresh_paths = [self._active_xdf_path] if len(self._loaded_xdf_paths) == 1 else sorted(self._loaded_xdf_paths)
                    if async_active_xdf_reload:
                        self._schedule_async_active_xdf_reload(refresh_paths, stream_allowlist, stream_blocklist, current_signature)
                        async_reload_scheduled = True
                        if self._active_xdf_path is not None:
                            self._append_refresh_log(f"Active XDF changed; background reload scheduled for {self._active_xdf_path.name}", level=logging.INFO, level_name="INFO")
                    else:
                        refreshed_map = self._collect_datasources_by_name_for_paths(refresh_paths, stream_allowlist=stream_allowlist, stream_blocklist=stream_blocklist)
                        refreshed_datasource_count = self._refresh_existing_timeline_datasources(self._current_timeline, refreshed_map, update_time_range=True)
                        self._active_xdf_last_signature = current_signature
                        if refreshed_datasource_count > 0:
                            self._append_refresh_log(f"Updated {refreshed_datasource_count} active track datasource(s) from open XDF: {self._active_xdf_path.name}", level=logging.INFO, level_name="INFO")
            new_video_paths: List[Path] = []
            for video_dir in video_discovery_dirs:
                if not video_dir.exists() or not video_dir.is_dir():
                    continue
                for video_path in sorted(video_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                    if video_path.suffix.lower() in video_extensions and video_path not in self._loaded_video_paths:
                        new_video_paths.append(video_path)
            if n_most_recent is not None and len(new_video_paths) > n_most_recent:
                new_video_paths = new_video_paths[:n_most_recent]
            if len(new_video_paths) > 0:
                for video_path in new_video_paths:
                    self._append_refresh_log(f"Discovered new Video: {video_path}", level=logging.INFO, level_name="INFO")
                if VideoTrackDatasource is None:
                    self._append_refresh_log("Video datasource unavailable; skipping new video tracks.", level=logging.WARNING, level_name="WARNING")
                else:
                    self._refresh_generation += 1
                    try:
                        video_datasource = VideoTrackDatasource(video_paths=new_video_paths, custom_datasource_name=f"VIDEO_REFRESH_{self._refresh_generation}")
                        all_new_datasources.append(video_datasource)
                        self._loaded_video_paths.update(new_video_paths)
                    except Exception as e:
                        self._append_refresh_log(f"Failed to load new videos: {e}", level=logging.ERROR, level_name="ERROR")
            if len(all_new_datasources) == 0 and refreshed_datasource_count == 0:
                if async_reload_scheduled:
                    self._append_refresh_log("Refresh complete: active XDF reload running in background.", level=logging.INFO, level_name="INFO")
                else:
                    self._append_refresh_log("Refresh complete: no new XDF or Video entries found.", level=logging.INFO, level_name="INFO")
                return
            if len(all_new_datasources) > 0:
                self.update_timeline(timeline=self._current_timeline, datasources=all_new_datasources, update_time_range=True)
            self._append_refresh_log(f"Refresh complete: added {len(all_new_datasources)} new track datasource(s), refreshed {refreshed_datasource_count} active datasource(s).", level=logging.INFO, level_name="INFO")
        except Exception as e:
            self._append_refresh_log(f"Refresh failed: {e}", level=logging.ERROR, level_name="ERROR")


    
    ## MAIN FUNCTION
    def build_from_xdf_file(self, xdf_file_path: Path, window_duration: Optional[float] = None, window_start_time: Optional[float] = None, add_example_tracks: bool = False, window_title: Optional[str] = None, window_size: Tuple[int, int] = (1000, 800), stream_allowlist: Optional[List[str]] = None, stream_blocklist: Optional[List[str]] = None, add_overview_strip: bool = True, **kwargs) -> Optional[SimpleTimelineWidget]:
        """Build a timeline widget from an XDF file.
        
        Args:
            xdf_file_path: Path to the XDF file
            window_duration: Duration of the time window (default: auto-calculated from data)
            window_start_time: Start time of the window (default: auto-calculated from data)
            add_example_tracks: Whether to add example tracks (default: False)
            window_title: Custom window title (default: auto-generated from filename)
            window_size: Window size as (width, height) tuple (default: (1000, 800))
            stream_allowlist: Optional list of regex patterns. If provided, only streams matching any pattern are loaded.
            stream_blocklist: Optional list of regex patterns. If provided, streams matching any pattern are excluded.
            add_overview_strip: Passed through to :meth:`build_from_xdf_files`.
            
        Returns:
            SimpleTimelineWidget instance, or None if no streams found
        """
        # Use multi-file method for backward compatibility
        return self.build_from_xdf_files(xdf_file_paths=[xdf_file_path], window_duration=window_duration, window_start_time=window_start_time, add_example_tracks=add_example_tracks, window_title=window_title, window_size=window_size, stream_allowlist=stream_allowlist, stream_blocklist=stream_blocklist, add_overview_strip=add_overview_strip, **kwargs)
    

    # @function_attributes(short_name=None, tags=['MAIN', 'used], input_requires=[], output_provides=[], uses=['self.build_from_datasources'], used_by=[], creation_date='2026-02-03 19:53', related_items=[])
    def build_from_xdf_files(self, xdf_file_paths: List[Path], window_duration: Optional[float] = None, window_start_time: Optional[float] = None, add_example_tracks: bool = False, window_title: Optional[str] = None, window_size: Tuple[int, int] = (1000, 800), stream_allowlist: Optional[List[str]] = None, stream_blocklist: Optional[List[str]] = None, add_overview_strip: bool = True, **kwargs) -> Optional[SimpleTimelineWidget]:
        """Build a timeline widget from multiple XDF files, merging streams by name.
        
        Streams with the same name across different files will be merged into a single track.
        Timestamps are preserved as absolute values (no time shifting).
        
        Args:
            xdf_file_paths: List of paths to XDF files
            window_duration: Duration of the time window (default: auto-calculated from data)
            window_start_time: Start time of the window (default: auto-calculated from data)
            add_example_tracks: Whether to add example tracks (default: False)
            window_title: Custom window title (default: auto-generated from filenames)
            window_size: Window size as (width, height) tuple (default: (1000, 800))
            stream_allowlist: Optional list of regex patterns. If provided, only streams matching any pattern are loaded.
            stream_blocklist: Optional list of regex patterns. If provided, streams matching any pattern are excluded.
            add_overview_strip: If True (default), attach a read-only interval overview minimap below the main dock area.
            
        Returns:
            SimpleTimelineWidget instance, or None if no streams found
            
        Example:
            builder = TimelineBuilder()
            timeline = builder.build_from_xdf_files([
                Path("file1.xdf"),
                Path("file2.xdf")
            ])
            
            # Only load EEG and Motion streams
            timeline = builder.build_from_xdf_files(
                xdf_file_paths=[Path("file1.xdf")],
                stream_allowlist=[r"EEG.*", r"MOTION.*"]
            )
            
            # Exclude logger streams
            timeline = builder.build_from_xdf_files(
                xdf_file_paths=[Path("file1.xdf")],
                stream_blocklist=[r".*Logger.*", r".*Event.*"]
            )
        """
        if not xdf_file_paths:
            raise ValueError("xdf_file_paths list cannot be empty")
        self._loaded_xdf_paths = set([Path(p) for p in xdf_file_paths])
        if self._refresh_config is not None and self._refresh_config.get("enable_active_xdf_monitoring", False):
            self._active_xdf_path = self._select_active_xdf_path(list(self._loaded_xdf_paths))
            self._active_xdf_last_signature = self._get_file_signature(self._active_xdf_path) if self._active_xdf_path is not None else None
        else:
            self._active_xdf_path = None
            self._active_xdf_last_signature = None
        
        
        logger.info("=" * 60)
        if len(xdf_file_paths) == 1:
            logger.info(f"pyPhoTimeline - Load all modalities from XDF: {xdf_file_paths[0]}")
        else:
            logger.info(f"pyPhoTimeline - Load all modalities from {len(xdf_file_paths)} XDF files:")
            for path in xdf_file_paths:
                logger.info(f"  - {path}")
        logger.info("=" * 60)
        
        # Load all XDF files
        all_streams_by_file = []
        all_file_headers = []
        all_loaded_xdf_file_paths = []

        for xdf_file_path in xdf_file_paths:
            logger.info(f"Loading XDF file: {xdf_file_path} ...")
            try:
                streams, file_header = pyxdf.load_xdf(str(xdf_file_path))

                # # #TODO 2026-03-02 05:30: - [ ] Could instead do 
                # from phopymnehelper.xdf_files import XDFDataStreamAccessor, LabRecorderXDF

                # obj: LabRecorderXDF = LabRecorderXDF.init_from_lab_recorder_xdf_file(a_xdf_file=xdf_file_path, should_load_full_file_data=True) ## #TODO 2026-03-02 07:47: - [ ] introduces `ValueError: Date must be datetime object in UTC: datetime.datetime(2026, 3, 1, 2, 9, 18, tzinfo=<UTC>)` error
                # # stream_infos = _obj.stream_infos
                # # raws = _obj.datasets
                # # raws_dict = _obj.datasets_dict
                # ## Convert back to the simple outputs:
                # streams = obj.xdf_streams
                # file_header = obj.xdf_header  # streams, file_header = pyxdf.load_xdf(str(xdf_file_path), verbose=True)

                logger.info(f"  Streams loaded: {[s['info']['name'][0] for s in streams]}")
                
                # Filter streams if allowlist/blocklist is provided
                if (stream_allowlist is not None) or (stream_blocklist is not None):
                    streams = self._filter_streams_by_name(streams, stream_allowlist=stream_allowlist, stream_blocklist=stream_blocklist)
                
                all_streams_by_file.append(streams)
                all_file_headers.append(file_header)
                all_loaded_xdf_file_paths.append(xdf_file_path)

            except (OSError, FileExistsError, FileNotFoundError) as err:
                logger.warning(f'failed to load file {xdf_file_path} with error: {err}. Skipping.')
                pass
        ## END for xdf_file_path in xdf_file_paths


        ## Calls `perform_process_all_streams_multi_xdf(...)` to process streams from all files and merge by stream name
        all_streams, all_streams_datasources = perform_process_all_streams_multi_xdf(streams_list=all_streams_by_file, xdf_file_paths=all_loaded_xdf_file_paths, file_headers=all_file_headers, enable_raw_xdf_processing=self._enable_heavy_xdf_processing())
        
        if not all_streams:
            logger.warning("No streams found.")
            return None
        
        logger.info(f"Found {len(all_streams)} unique stream names after merging: {[a_name for a_name in list(all_streams_datasources.keys())]}")
        
        # Get active datasources
        active_datasources_dict = {k: v for k, v in all_streams_datasources.items() if v is not None}
        active_datasource_list = list(active_datasources_dict.values())
        logger.info(f"\tbuild active_datasources: {len(active_datasource_list)} datasources.")
        
        if not active_datasource_list:
            logger.warning("No valid datasources found.")
            return None
        
        # Extract reference datetime from XDF headers (for datetime axis alignment)
        reference_datetime = get_earliest_reference_datetime(all_file_headers, active_datasource_list)
        if reference_datetime is not None:
            logger.info(f"Using reference datetime: {reference_datetime}")
        else:
            logger.warning("Warning: No reference datetime found, using Unix epoch")
        
        # Generate window title if not provided
        if window_title is None:
            if len(all_loaded_xdf_file_paths) == 1:
                window_title = f"pyPhoTimeline - ALL Modalities from XDF: {all_loaded_xdf_file_paths[0].name}"
            else:
                file_names = ", ".join([p.name for p in all_loaded_xdf_file_paths])
                window_title = f"pyPhoTimeline - ALL Modalities from {len(all_loaded_xdf_file_paths)} XDF files: {file_names}"
        
        # Build timeline from merged datasources with reference datetime
        timeline = self.build_from_datasources(datasources=active_datasource_list, window_duration=window_duration, window_start_time=window_start_time, add_example_tracks=add_example_tracks, window_title=window_title, window_size=window_size, reference_datetime=reference_datetime, **kwargs)
        if (timeline is not None) and add_overview_strip:
            timeline.add_timeline_overview_strip(position='bottom')
        return timeline


    # @function_attributes(short_name=None, tags=[''], input_requires=[], output_provides=[], uses=['self.build_from_datasources'], used_by=[], creation_date='2026-02-03 19:53', related_items=[])
    def build_from_video(self, video_datasource: Optional[VideoTrackDatasource] = None, video_folder_path: Optional[Path] = None, video_paths: Optional[List[Union[Path, str]]] = None, video_df: Optional[pd.DataFrame] = None, video_intervals_df: Optional[pd.DataFrame] = None, custom_datasource_name: Optional[str] = None, reference_timestamp: Optional[float] = None, window_duration: Optional[float] = None, window_start_time: Optional[float] = None, window_title: Optional[str] = None, window_size: Tuple[int, int] = (1000, 800), frames_per_second: float = 10.0, thumbnail_size: Optional[Tuple[int, int]] = (128, 128), **kwargs) -> SimpleTimelineWidget:
        """Build a timeline widget from video files only (no XDF file required).
        
        Args:
            video_datasource: Existing VideoTrackDatasource instance (optional, if provided, other video args ignored)
            video_folder_path: Path to folder containing videos (optional)
            video_paths: List of video file paths (Path objects or strings) (optional)
            video_df: Pre-parsed DataFrame from VideoMetadataParser (optional)
            video_intervals_df: DataFrame with video intervals (optional)
            custom_datasource_name: Custom name for the video datasource (optional)
            reference_timestamp: Optional reference timestamp for time conversion (default: first video start time)
            window_duration: Duration of the time window (default: auto-calculated from video data)
            window_start_time: Start time of the window (default: auto-calculated from video data)
            window_title: Custom window title (default: "pyPhoTimeline - Video Track")
            window_size: Window size as (width, height) tuple (default: (1000, 800))
            frames_per_second: Target frame rate for thumbnail extraction (default: 10.0)
            thumbnail_size: Optional (width, height) tuple for resizing frames (default: (128, 128))
            
        Returns:
            SimpleTimelineWidget instance with video track
            
        Example:
            builder = TimelineBuilder()
            # Option 1: From folder
            timeline = builder.build_from_video(video_folder_path=Path("path/to/videos"))
            # Option 2: From list of video files
            timeline = builder.build_from_video(video_paths=[Path("video1.mp4"), Path("video2.mp4")])
            # Option 3: From existing datasource
            video_ds = VideoTrackDatasource(video_folder_path=Path("path/to/videos"))
            timeline = builder.build_from_video(video_datasource=video_ds)
        """
        if VideoTrackDatasource is None:
            raise ImportError("VideoTrackDatasource is not available. Make sure video dependencies are installed.")
        
        # Create VideoTrackDatasource if not provided
        if video_datasource is None:
            video_datasource = VideoTrackDatasource(
                video_intervals_df=video_intervals_df,
                video_folder_path=video_folder_path,
                video_df=video_df,
                video_paths=video_paths,
                custom_datasource_name=custom_datasource_name,
                reference_timestamp=reference_timestamp,
                frames_per_second=frames_per_second,
                thumbnail_size=thumbnail_size
            )
        if video_paths is not None:
            self._loaded_video_paths.update([Path(p) for p in video_paths])
        
        # Check if datasource has any intervals
        if video_datasource.intervals_df.empty:
            raise ValueError("VideoTrackDatasource has no video intervals. Check that video files exist and are valid.")
        
        # Get reference datetime (use reference_timestamp if available, otherwise fallback)
        reference_datetime = None
        if reference_timestamp is not None:
            # Convert reference_timestamp (float) to datetime (assuming Unix epoch, UTC)
            reference_datetime = datetime.fromtimestamp(reference_timestamp, tz=timezone.utc)
        else:
            # Fallback to earliest timestamp or Unix epoch
            reference_datetime = get_earliest_reference_datetime([], [video_datasource])
        
        # Build timeline from the single video datasource
        return self.build_from_datasources(
            datasources=[video_datasource],
            window_duration=window_duration,
            window_start_time=window_start_time,
            add_example_tracks=False,
            window_title=window_title or f"pyPhoTimeline - Video Track: {video_datasource.custom_datasource_name}",
            window_size=window_size,
            reference_datetime=reference_datetime, **kwargs,
        )
    

    # @function_attributes(short_name=None, tags=[''], input_requires=[], output_provides=[], uses=['self.build_from_datasources'], used_by=[], creation_date='2026-02-03 19:53', related_items=[])
    def build_from_streams(self, streams: List, window_duration: Optional[float] = None, window_start_time: Optional[float] = None, add_example_tracks: bool = False, window_title: Optional[str] = None, window_size: Tuple[int, int] = (1000, 800), stream_allowlist: Optional[List[str]] = None, stream_blocklist: Optional[List[str]] = None, **kwargs) -> Optional[SimpleTimelineWidget]:
        """Build a timeline widget from pre-loaded streams.
        
        Args:
            streams: List of stream dictionaries from pyxdf
            window_duration: Duration of the time window (default: auto-calculated from data)
            window_start_time: Start time of the window (default: auto-calculated from data)
            add_example_tracks: Whether to add example tracks (default: False)
            window_title: Custom window title (default: "pyPhoTimeline")
            window_size: Window size as (width, height) tuple (default: (1000, 800))
            stream_allowlist: Optional list of regex patterns. If provided, only streams matching any pattern are loaded.
            stream_blocklist: Optional list of regex patterns. If provided, streams matching any pattern are excluded.
            
        Returns:
            SimpleTimelineWidget instance, or None if no streams found
        """
        # Filter streams if allowlist/blocklist is provided
        if stream_allowlist is not None or stream_blocklist is not None:
            streams = self._filter_streams_by_name(streams, stream_allowlist=stream_allowlist, stream_blocklist=stream_blocklist)
        
        # Process streams to get datasources
        all_streams, all_streams_datasources = self._process_xdf_streams(streams)
        
        if not all_streams:
            logger.warning("No streams found.")
            return None
        
        logger.info(f"Found {len(all_streams)} streams: {[a_name for a_name in list(all_streams_datasources.keys())]}")
        
        # Get active datasources
        active_datasources_dict = {k: v for k, v in all_streams_datasources.items() if v is not None}
        active_datasource_list = list(active_datasources_dict.values())
        logger.info(f"\tbuild active_datasources: {len(active_datasource_list)} datasources.")
        
        if not active_datasource_list:
            logger.warning("No valid datasources found.")
            return None
        
        # Get reference datetime (fallback to earliest timestamp since no XDF headers available)
        from pypho_timeline.utils.datetime_helpers import get_earliest_reference_datetime
        reference_datetime = get_earliest_reference_datetime([], active_datasource_list)
        
        # Build timeline from datasources
        return self.build_from_datasources(datasources=active_datasource_list, window_duration=window_duration, window_start_time=window_start_time, add_example_tracks=add_example_tracks, window_title=window_title or "pyPhoTimeline", window_size=window_size, reference_datetime=reference_datetime, **kwargs)
    

    # @function_attributes(short_name=None, tags=[''], input_requires=[], output_provides=[], uses=['self.build_from_datasources'], used_by=[], creation_date='2026-02-03 19:53', related_items=[])
    def build_from_eeg_raw_and_stream_info(self, eeg_raws: List, stream_infos_df: pd.DataFrame, window_duration: Optional[float] = None, window_start_time: Optional[float] = None, add_example_tracks: bool = False, window_title: Optional[str] = None, window_size: Tuple[int, int] = (1000, 800), stream_allowlist: Optional[List[str]] = None, stream_blocklist: Optional[List[str]] = None, **kwargs) -> Optional[SimpleTimelineWidget]:
        """Build a timeline widget from MNE Raw objects and XDF stream info DataFrame.
        
        Args:
            eeg_raws: List of MNE Raw objects (mne.io.BaseRaw instances)
            stream_infos_df: DataFrame with stream information, must contain 'xdf_dataset_idx' column
            window_duration: Duration of the time window (default: auto-calculated from data)
            window_start_time: Start time of the window (default: auto-calculated from data)
            add_example_tracks: Whether to add example tracks (default: False)
            window_title: Custom window title (default: auto-generated)
            window_size: Window size as (width, height) tuple (default: (1000, 800))
            stream_allowlist: Optional list of regex patterns. If provided, only streams matching any pattern are loaded.
            stream_blocklist: Optional list of regex patterns. If provided, streams matching any pattern are excluded.
            
        Returns:
            SimpleTimelineWidget instance, or None if no valid datasources found
            
        Example:
            builder = TimelineBuilder()
            timeline = builder.build_from_eeg_raw_and_stream_info(
                eeg_raws=_out_eeg_raw,
                stream_infos_df=_out_xdf_stream_infos_df
            )
            
            # Only load EEG streams
            timeline = builder.build_from_eeg_raw_and_stream_info(
                eeg_raws=_out_eeg_raw,
                stream_infos_df=_out_xdf_stream_infos_df,
                stream_allowlist=[r"EEG.*"]
            )
        """
        if not MNE_AVAILABLE:
            raise ImportError("MNE is not available. Please install mne-python to use this method.")
        
        if not eeg_raws:
            logger.warning("No EEG Raw objects provided.")
            return None
        
        if stream_infos_df.empty:
            logger.warning("Stream info DataFrame is empty.")
            return None
        
        if 'xdf_dataset_idx' not in stream_infos_df.columns:
            raise ValueError("stream_infos_df must contain 'xdf_dataset_idx' column")
        
        # Filter stream_infos_df if allowlist/blocklist is provided
        if stream_allowlist is not None or stream_blocklist is not None:
            if stream_allowlist is not None and stream_blocklist is not None:
                raise ValueError("Cannot specify both stream_allowlist and stream_blocklist. Only one can be provided.")
            
            if 'name' not in stream_infos_df.columns:
                logger.warning("Warning: 'name' column not found in stream_infos_df, cannot filter by stream name")
            else:
                original_count = len(stream_infos_df)
                mask = pd.Series([True] * len(stream_infos_df), index=stream_infos_df.index)
                
                if stream_allowlist is not None:
                    # Include only if matches any pattern in allowlist
                    name_matches = stream_infos_df['name'].apply(
                        lambda name: any(re.search(pattern, str(name)) for pattern in stream_allowlist)
                    )
                    mask = mask & name_matches
                elif stream_blocklist is not None:
                    # Exclude if matches any pattern in blocklist
                    name_matches = stream_infos_df['name'].apply(
                        lambda name: any(re.search(pattern, str(name)) for pattern in stream_blocklist)
                    )
                    mask = mask & ~name_matches
                
                stream_infos_df = stream_infos_df[mask].copy()
                filtered_count = original_count - len(stream_infos_df)
                
                if filtered_count > 0:
                    filter_type = "allowlist" if stream_allowlist is not None else "blocklist"
                    patterns = stream_allowlist if stream_allowlist is not None else stream_blocklist
                    logger.debug(f"Filtered out {filtered_count} stream info row(s) using {filter_type} {patterns}")
                    logger.debug(f"Kept {len(stream_infos_df)} out of {original_count} stream info row(s) after filtering")
                
                if stream_infos_df.empty:
                    logger.warning("No stream info rows remaining after filtering.")
                    return None
        
        logger.info("=" * 60)
        logger.info(f"pyPhoTimeline - Load from {len(eeg_raws)} MNE Raw objects and {len(stream_infos_df)} stream info rows")
        logger.info("=" * 60)
        
        # Extract reference datetime from stream_infos_df
        reference_datetime = None
        if 'recording_datetime' in stream_infos_df.columns:
            # Use earliest recording_datetime
            valid_dts = stream_infos_df['recording_datetime'].dropna()
            if len(valid_dts) > 0:
                reference_datetime = valid_dts.min()
        elif 'first_timestamp_dt' in stream_infos_df.columns:
            # Fallback to earliest first_timestamp_dt
            valid_dts = stream_infos_df['first_timestamp_dt'].dropna()
            if len(valid_dts) > 0:
                reference_datetime = valid_dts.min()
        
        if reference_datetime is None:
            logger.warning("Warning: No reference datetime found in stream_infos_df, will use earliest datetime from datasources")
            # Don't set a default here - let build_from_datasources determine it from the actual data
            reference_datetime = None
        else:
            # Convert pandas Timestamp to datetime if needed
            if isinstance(reference_datetime, pd.Timestamp):
                reference_datetime = reference_datetime.to_pydatetime()
            # Ensure timezone-aware
            if reference_datetime.tzinfo is None:
                reference_datetime = reference_datetime.replace(tzinfo=timezone.utc)
            logger.info(f"Using reference datetime: {reference_datetime}")
        
        # Extract datasources from Raw objects
        all_datasources = []
        processed_count = 0
        skipped_count = 0
        
        for idx, row in stream_infos_df.iterrows():
            xdf_dataset_idx = row.get('xdf_dataset_idx', None)
            if xdf_dataset_idx is None or pd.isna(xdf_dataset_idx):
                logger.warning(f"Warning: Skipping row {idx} - missing xdf_dataset_idx")
                skipped_count += 1
                continue
            
            try:
                xdf_dataset_idx = int(xdf_dataset_idx)
            except (ValueError, TypeError):
                logger.warning(f"Warning: Skipping row {idx} - invalid xdf_dataset_idx: {xdf_dataset_idx}")
                skipped_count += 1
                continue
            
            # Find corresponding Raw object
            if xdf_dataset_idx < 0 or xdf_dataset_idx >= len(eeg_raws):
                logger.warning(f"Warning: Skipping row {idx} - xdf_dataset_idx {xdf_dataset_idx} out of range (0-{len(eeg_raws)-1})")
                skipped_count += 1
                continue
            
            raw = eeg_raws[xdf_dataset_idx]
            if raw is None:
                logger.warning(f"Warning: Skipping row {idx} - Raw object at index {xdf_dataset_idx} is None")
                skipped_count += 1
                continue
            
            # Check if Raw object is valid
            if not hasattr(raw, 'times') or len(raw.times) == 0:
                logger.warning(f"Warning: Skipping row {idx} - Raw object at index {xdf_dataset_idx} has no time data")
                skipped_count += 1
                continue
            
            # Extract datasources from this Raw object
            stream_name = row.get('name', f'Stream_{xdf_dataset_idx}')
            try:
                datasources = self._extract_datasources_from_eeg_raw(
                    raw=raw,
                    stream_info_row=row,
                    reference_datetime=reference_datetime,
                    stream_name=stream_name
                )
                if datasources:
                    all_datasources.extend(datasources)
                    processed_count += 1
                else:
                    logger.warning(f"Warning: No datasources extracted from '{stream_name}'")
                    skipped_count += 1
            except Exception as e:
                logger.error(f"Error: Failed to extract datasources from '{stream_name}': {e}")
                skipped_count += 1
                import traceback
                traceback.print_exc()
        
        logger.info(f"Processed {processed_count} streams, skipped {skipped_count} streams")
        
        if not all_datasources:
            logger.warning("No valid datasources found.")
            return None
        
        logger.info(f"Found {len(all_datasources)} datasources from {len(stream_infos_df)} stream info rows")
        
        # Merge datasources that share the same track name.
        #
        # Rationale:
        # - We may have many recordings for the same logical stream (e.g. multiple XDF segments).
        # - `TrackRenderingMixin.add_track` uses `name` as a unique key and will not create
        #   multiple tracks with identical names.
        # - Therefore, we merge intervals (and detailed data where present) into a single datasource
        #   per `custom_datasource_name`, yielding multiple overview rectangles per track.
        datasources_by_name: Dict[str, List[TrackDatasource]] = {}
        for ds in all_datasources:
            datasources_by_name.setdefault(ds.custom_datasource_name, []).append(ds)

        merged_datasources: List[TrackDatasource] = []
        for name, ds_group in datasources_by_name.items():
            if len(ds_group) == 1:
                merged_datasources.append(ds_group[0])
                continue

            first = ds_group[0]
            # All of our concrete datasources inherit IntervalProvidingTrackDatasource and
            # expose `intervals_df` and (optionally) `detailed_df`.
            intervals_dfs = [getattr(d, "intervals_df") for d in ds_group if getattr(d, "intervals_df", None) is not None]
            detailed_dfs = [getattr(d, "detailed_df") for d in ds_group if getattr(d, "detailed_df", None) is not None]

            try:
                # Prefer specialized merge constructors when available (keeps renderer behavior)
                if EEGTrackDatasource is not None and isinstance(first, EEGTrackDatasource):
                    merged = EEGTrackDatasource.from_multiple_sources(
                        intervals_dfs=intervals_dfs,
                        detailed_dfs=detailed_dfs,
                        custom_datasource_name=name,
                        max_points_per_second=getattr(first, "max_points_per_second", 1000.0),
                        enable_downsampling=getattr(first, "enable_downsampling", True),
                        fallback_normalization_mode=getattr(first, "fallback_normalization_mode", ChannelNormalizationMode.GROUPMINMAXRANGE),
                        normalization_mode_dict=getattr(first, "normalization_mode_dict", None),
                        arbitrary_bounds=getattr(first, "arbitrary_bounds", None),
                        normalize=getattr(first, "normalize", True),
                        normalize_over_full_data=getattr(first, "normalize_over_full_data", True),
                        normalization_reference_df=getattr(first, "normalization_reference_df", None),
                    )
                    merged_datasources.append(merged)
                    continue

                if MotionTrackDatasource is not None and isinstance(first, MotionTrackDatasource):
                    merged = MotionTrackDatasource.from_multiple_sources(
                        intervals_dfs=intervals_dfs,
                        detailed_dfs=detailed_dfs,
                        custom_datasource_name=name,
                        max_points_per_second=getattr(first, "max_points_per_second", 1000.0),
                        enable_downsampling=getattr(first, "enable_downsampling", True),
                        fallback_normalization_mode=getattr(first, "fallback_normalization_mode", ChannelNormalizationMode.GROUPMINMAXRANGE),
                        normalization_mode_dict=getattr(first, "normalization_mode_dict", None),
                        arbitrary_bounds=getattr(first, "arbitrary_bounds", None),
                    )
                    merged_datasources.append(merged)
                    continue

                if EEGSpectrogramTrackDatasource is not None and isinstance(first, EEGSpectrogramTrackDatasource):
                    spec_results = []
                    for ds in ds_group:
                        stored_results = getattr(ds, "_spectrogram_results", None)
                        if stored_results is not None:
                            spec_results.extend(list(stored_results))
                            continue
                        stored_result = getattr(ds, "_spectrogram_result", None)
                        if stored_result is not None:
                            spec_results.append(stored_result)
                    expected_result_count = sum(len(df) for df in intervals_dfs)
                    if len(spec_results) == expected_result_count:
                        merged = EEGSpectrogramTrackDatasource.from_multiple_sources(intervals_dfs=intervals_dfs, spectrogram_results=spec_results, custom_datasource_name=name,
                            freq_min=getattr(first, "_freq_min", 1.0), freq_max=getattr(first, "_freq_max", 40.0), group_config=getattr(first, "_group_config", None), channel_group_presets=getattr(first, "_channel_group_presets", None))
                        merged_datasources.append(merged)
                    else:
                        merged_datasources.append(first)
                    continue

                # Generic interval + optional detail (e.g. annotations)
                merged = IntervalProvidingTrackDatasource.from_multiple_sources(
                    intervals_dfs=intervals_dfs,
                    detailed_dfs=detailed_dfs if detailed_dfs else None,
                    custom_datasource_name=name,
                    detail_renderer=getattr(first, "_detail_renderer", None) or first.get_detail_renderer(),
                    max_points_per_second=getattr(first, "max_points_per_second", 1000.0),
                    enable_downsampling=getattr(first, "enable_downsampling", True),
                )
                merged_datasources.append(merged)
            except Exception as e:
                logger.warning(f"Warning: failed to merge datasources for '{name}': {e}. Falling back to first datasource.")
                merged_datasources.append(first)

        # Generate window title if not provided
        if window_title is None:
            window_title = f"pyPhoTimeline - MNE Raw Data ({len(eeg_raws)} recordings)"
        
        # If reference_datetime is None, it will be set from the earliest datetime in datasources
        # Build timeline from datasources
        return self.build_from_datasources(
            datasources=merged_datasources,
            window_duration=window_duration,
            window_start_time=window_start_time,
            add_example_tracks=add_example_tracks,
            window_title=window_title,
            window_size=window_size,
            reference_datetime=reference_datetime, **kwargs,
        )
    

    def _overview_row_t_end(self, overview_df: pd.DataFrame, j: int, is_datetime: bool) -> Optional[Any]:
        ts = overview_df['t_start'].iloc[j]
        if 't_end' in overview_df.columns:
            te = overview_df['t_end'].iloc[j]
            if te is None or (isinstance(te, float) and np.isnan(te)):
                return None
            if is_datetime:
                out = pd.Timestamp(te)
                return out.tz_localize('UTC') if out.tzinfo is None else out
            return float(te)
        if 't_duration' not in overview_df.columns:
            return None
        dur = overview_df['t_duration'].iloc[j]
        if is_datetime:
            t0 = pd.Timestamp(ts)
            if t0.tzinfo is None:
                t0 = t0.tz_localize('UTC')
            if isinstance(dur, (timedelta, pd.Timedelta)):
                return t0 + pd.Timedelta(dur)
            if dur is None or (isinstance(dur, float) and np.isnan(dur)):
                return None
            return t0 + timedelta(seconds=float(dur))
        if dur is None or (isinstance(dur, float) and np.isnan(dur)):
            return None
        if isinstance(dur, (timedelta, pd.Timedelta)):
            return float(ts) + float(pd.Timedelta(dur).total_seconds())
        return float(ts) + float(dur)



    def _max_overview_interval_end(self, datasources: List[TrackDatasource], is_datetime: bool) -> Optional[Any]:
        vals: List[Any] = []
        for ds in datasources:
            try:
                ov = ds.get_overview_intervals()
            except Exception:
                continue
            if ov is None or ov.empty or 't_start' not in ov.columns:
                continue
            for j in range(len(ov)):
                te = self._overview_row_t_end(ov, j, is_datetime=is_datetime)
                if te is not None:
                    vals.append(te)
        if not vals:
            return None
        if is_datetime:
            return max(vals, key=lambda x: pd.Timestamp(x))
        return max(vals)



    def _end_aligned_window_start(self, datasources: List[TrackDatasource], total_start_time: Any, total_end_time: Any, window_duration: float, is_datetime: bool) -> Any:
        anchor = self._max_overview_interval_end(datasources, is_datetime)
        if is_datetime:
            total_start_time = pd.Timestamp(total_start_time)
            total_end_time = pd.Timestamp(total_end_time)
            if anchor is None:
                anchor = total_end_time
            else:
                anchor = pd.Timestamp(anchor)
                if anchor.tzinfo is None:
                    anchor = anchor.tz_localize('UTC')
            effective_end = min(anchor, total_end_time)
            span_sec = (total_end_time - total_start_time).total_seconds()
            if window_duration >= span_sec:
                return total_start_time
            desired = effective_end - timedelta(seconds=float(window_duration))
            latest = total_end_time - timedelta(seconds=float(window_duration))
            return max(total_start_time, min(desired, latest))
        if anchor is None:
            anchor = float(total_end_time)
        total_start_time = float(total_start_time)
        total_end_time = float(total_end_time)
        effective_end = min(float(anchor), total_end_time)
        span = total_end_time - total_start_time
        if window_duration >= span:
            return total_start_time
        desired = effective_end - float(window_duration)
        latest = total_end_time - float(window_duration)
        return max(total_start_time, min(desired, latest))


    # @function_attributes(short_name=None, tags=['MAIN'], input_requires=[], output_provides=[], uses=['self._add_tracks_to_timeline'], used_by=['self.build_from_eeg_raw_and_stream_info', 'self.build_from_streams', 'self.build_from_video', 'self.build_from_xdf_files'], creation_date='2026-02-03 19:53', related_items=[])
    def build_from_datasources(self, datasources: List[TrackDatasource], window_duration: Optional[float] = None, window_start_time: Optional[float] = None, add_example_tracks: bool = False, window_title: Optional[str] = None, window_size: Tuple[int, int] = (1000, 800), reference_datetime: Optional[datetime] = None,
                use_absolute_datetime_track_mode: bool = True, enable_calendar_widget_track: bool = False, enable_log_table_widget: bool = False, **kwargs,
                ) -> SimpleTimelineWidget:
        """Build a timeline widget from existing datasources.
        
        Args:
            datasources: List of TrackDatasource instances
            window_duration: Duration of the time window (default: auto-calculated from data)
            window_start_time: Start time of the window. If omitted, the window is placed so its end aligns with the latest ``t_end`` from :meth:`get_overview_intervals` across datasources (capped by the global data end), clamped within the global range; if no overview intervals exist, uses ``total_end_time`` as the anchor.
            add_example_tracks: Whether to add example tracks (default: False)
            window_title: Custom window title (default: "pyPhoTimeline")
            window_size: Window size as (width, height) tuple (default: (1000, 800))
            reference_datetime: Reference datetime for datetime axis alignment (default: None, uses Unix epoch)
            
        Returns:
            SimpleTimelineWidget instance
        """
        if not datasources:
            raise ValueError("datasources list cannot be empty")
        
        # Calculate time range from datasources
        # Check if datasources use datetime objects
        first_start, first_end = datasources[0].total_df_start_end_times
        is_datetime = isinstance(first_start, (datetime, pd.Timestamp))
        
        #TODO 2026-02-03 20:10: - [ ] Implement proper full datetime use here like I did downstream in `self._add_tracks_to_timeline(...)` for use_absolute_datetime_track_mode == True mode.
        if is_datetime:
            # Use datetime operations
            total_start_time = min([ds.total_df_start_end_times[0] for ds in datasources], key=lambda x: pd.Timestamp(x) if not isinstance(x, pd.Timestamp) else x)
            total_end_time = max([ds.total_df_start_end_times[1] for ds in datasources], key=lambda x: pd.Timestamp(x) if not isinstance(x, pd.Timestamp) else x)
            
            # Ensure they're pd.Timestamp
            total_start_time = pd.Timestamp(total_start_time)
            total_end_time = pd.Timestamp(total_end_time)
            if total_start_time.tzinfo is None:
                total_start_time = total_start_time.tz_localize('UTC')
            if total_end_time.tzinfo is None:
                total_end_time = total_end_time.tz_localize('UTC')
            
            # Calculate window duration if not provided
            if window_duration is None:
                duration_delta = total_end_time - total_start_time
                window_duration = duration_delta.total_seconds()
                window_duration = max(window_duration, 10.0)
            
            # Calculate window start time if not provided (end-aligned to last overview interval)
            if window_start_time is None:
                window_start_time = self._end_aligned_window_start(datasources, total_start_time, total_end_time, float(window_duration), is_datetime=True)

            elif isinstance(window_start_time, (int, float)):
                # Convert relative float to absolute datetime
                if reference_datetime is not None:
                    window_start_time = reference_datetime + timedelta(seconds=float(window_start_time))
                else:
                    window_start_time = total_start_time + timedelta(seconds=float(window_start_time))
        else:
            # Use float operations (backward compatibility)
            total_start_time: float = np.nanmin([ds.total_df_start_end_times[0] for ds in datasources])
            total_end_time: float = np.nanmax([ds.total_df_start_end_times[1] for ds in datasources])
            
            # Calculate window duration if not provided
            if window_duration is None:
                window_duration = total_end_time - total_start_time
                window_duration = max(window_duration, 10.0)
            
            # Calculate window start time if not provided (end-aligned to last overview interval)
            if window_start_time is None:
                window_start_time = self._end_aligned_window_start(datasources, total_start_time, total_end_time, float(window_duration), is_datetime=False)
        
        # Set reference_datetime appropriately
        if is_datetime:
            # When using datetime objects, reference_datetime is just for display formatting
            # Use the earliest datetime from datasources as reference
            if reference_datetime is None:
                reference_datetime = total_start_time
            else:
                # Ensure it's a datetime object
                reference_datetime = pd.Timestamp(reference_datetime)
                if reference_datetime.tzinfo is None:
                    reference_datetime = reference_datetime.tz_localize('UTC')
        else:
            # Use Unix epoch as fallback if no reference datetime provided (for float timestamps)
            if reference_datetime is None:
                from pypho_timeline.utils.datetime_helpers import get_earliest_reference_datetime
                reference_datetime = get_earliest_reference_datetime([], datasources)

        # Create main window (do not show until timeline is added and configured)
        main_window = MainTimelineWindow(show_immediately=False, builder=self)
        # Create the timeline widget with reference datetime, parented to main window content area
        timeline = SimpleTimelineWidget(total_start_time=total_start_time, total_end_time=total_end_time, window_duration=window_duration, window_start_time=window_start_time, add_example_tracks=add_example_tracks, reference_datetime=reference_datetime, parent=main_window.contentWidget)
        main_window.contentWidget.layout().addWidget(timeline)
        # Add tracks to the timeline
        self._add_tracks_to_timeline(timeline, datasources, use_absolute_datetime_track_mode=use_absolute_datetime_track_mode, **kwargs)
        self._sync_main_window_session_jump_controls(main_window=main_window)
        self._current_main_window = main_window
        self._current_timeline = timeline
        if self._refresh_config is not None and self._refresh_config.get("enable_active_xdf_monitoring", False):
            self._start_active_xdf_monitoring()
        else:
            self._stop_active_xdf_monitoring()
        # Configure and show main window
        main_window.setWindowTitle(window_title or "pyPhoTimeline")
        main_window.resize(window_size[0], window_size[1])
        main_window.show()
            
        
        # enable_dynamic_locked_widget_track: bool = False


        ## Add the calendar widget
        if enable_calendar_widget_track:
            a_cal_nav = timeline.add_calendar_navigator()

        self._embed_log_widget_in_timeline(timeline)
        main_window.attach_collapsed_dock_overflow(timeline.ui.dynamic_docked_widget_container)

        ## add the table widget:
        if enable_log_table_widget:
            if "LOG_TextLogger" in timeline.track_datasources:
                table_widget = timeline.add_dataframe_table_track("Text Log", timeline.track_datasources["LOG_TextLogger"].df) # timeline.add_dataframe_table_track()
        
        logger.info("\nTimeline widget created with tracks:")
        for ds in datasources:
            logger.info(f"  - {ds.custom_datasource_name}, time: {ds.total_df_start_end_times}")
        
        logger.info("\nScroll on the timeline to see loaded intervals for each stream.")
        logger.info("Close the window to exit.\n")

        ## hide the extra/redundant xaxis labels
        timeline.hide_extra_xaxis_labels_and_axes()

        
        return timeline
    

    
    # @function_attributes(short_name=None, tags=[''], input_requires=[], output_provides=[], uses=['self._add_tracks_to_timeline'], used_by=[], creation_date='2026-02-03 19:58', related_items=[])
    def update_timeline(self, timeline: SimpleTimelineWidget, datasources: List[TrackDatasource], update_time_range: bool = True) -> SimpleTimelineWidget:
        """Add tracks to an existing timeline widget.
        
        Args:
            timeline: Existing SimpleTimelineWidget instance
            datasources: List of TrackDatasource instances to add
            update_time_range: Whether to update the timeline's time range to include new datasources (default: True)
            
        Returns:
            The updated SimpleTimelineWidget instance
        """
        if not datasources:
            logger.warning("No datasources provided for update.")
            return timeline
        
        # Update time range if requested
        if update_time_range:
            existing_start = timeline.total_data_start_time
            existing_end = timeline.total_data_end_time
            
            # Check if using datetime objects
            first_start, first_end = datasources[0].total_df_start_end_times
            is_datetime = isinstance(first_start, (datetime, pd.Timestamp))
            
            if is_datetime:
                new_start = min([ds.total_df_start_end_times[0] for ds in datasources], key=lambda x: pd.Timestamp(x) if not isinstance(x, pd.Timestamp) else x)
                new_end = max([ds.total_df_start_end_times[1] for ds in datasources], key=lambda x: pd.Timestamp(x) if not isinstance(x, pd.Timestamp) else x)
                
                # Ensure they're pd.Timestamp
                new_start = pd.Timestamp(new_start)
                new_end = pd.Timestamp(new_end)
                if new_start.tzinfo is None:
                    new_start = new_start.tz_localize('UTC')
                if new_end.tzinfo is None:
                    new_end = new_end.tz_localize('UTC')
                
                # Convert existing times if they're floats
                if isinstance(existing_start, (int, float)):
                    if timeline.reference_datetime is not None:
                        existing_start = timeline.reference_datetime + timedelta(seconds=float(existing_start))
                    else:
                        existing_start = pd.Timestamp.fromtimestamp(float(existing_start), tz='UTC')
                if isinstance(existing_end, (int, float)):
                    if timeline.reference_datetime is not None:
                        existing_end = timeline.reference_datetime + timedelta(seconds=float(existing_end))
                    else:
                        existing_end = pd.Timestamp.fromtimestamp(float(existing_end), tz='UTC')
                
                total_start_time = min(pd.Timestamp(existing_start), new_start)
                total_end_time = max(pd.Timestamp(existing_end), new_end)
            else:
                new_start = np.nanmin([ds.total_df_start_end_times[0] for ds in datasources])
                new_end = np.nanmax([ds.total_df_start_end_times[1] for ds in datasources])
                
                total_start_time = min(float(existing_start), float(new_start))
                total_end_time = max(float(existing_end), float(new_end))
            
            # Update timeline time range
            timeline.total_data_start_time = total_start_time
            timeline.total_data_end_time = total_end_time
            timeline.spikes_window.total_df_start_end_times = (total_start_time, total_end_time)
        
        # Add tracks to the timeline
        self._add_tracks_to_timeline(timeline, datasources)
        self._sync_main_window_session_jump_controls()

        logger.info(f"\nUpdated timeline with {len(datasources)} new tracks:")
        for ds in datasources:
            logger.info(f"  - {ds.custom_datasource_name}, time: {ds.total_df_start_end_times}")
        
        return timeline
    

    def _extract_datasources_from_eeg_raw(self, raw, stream_info_row: pd.Series, reference_datetime: datetime, stream_name: str) -> List[TrackDatasource]:
        """Extract datasources from a single MNE Raw object.
        
        Args:
            raw: MNE Raw object (mne.io.BaseRaw)
            stream_info_row: Series with stream information (from stream_infos_df)
            reference_datetime: Reference datetime for timestamp conversion
            stream_name: Name of the stream
            
        Returns:
            List of TrackDatasource instances (EEG, Motion, Annotations, etc.)
        """
        datasources = []
        
        # Check if Raw object has data
        if len(raw.times) == 0:
            logger.warning(f"Warning: Raw object for '{stream_name}' has no time data")
            return datasources
        
        # Get meas_date from Raw object
        meas_date = None
        try:
            meas_date = raw.info.get('meas_date', None)
        except (AttributeError, KeyError):
            pass
        
        if meas_date is None:
            # Try to get from stream_info_row
            meas_date = stream_info_row.get('recording_datetime', None)
            if pd.isna(meas_date):
                meas_date = None
        
        if meas_date is None:
            # Try first_timestamp_dt as fallback
            meas_date = stream_info_row.get('first_timestamp_dt', None)
            if pd.isna(meas_date):
                meas_date = None
        
        if meas_date is None:
            logger.warning(f"Warning: No meas_date found for '{stream_name}', using reference_datetime")
            meas_date = reference_datetime
        
        # Ensure meas_date is timezone-aware
        if meas_date is not None:
            if isinstance(meas_date, pd.Timestamp):
                meas_date = meas_date.to_pydatetime()
            if meas_date.tzinfo is None:
                meas_date = meas_date.replace(tzinfo=timezone.utc)
        
        raw_time_values = np.asarray(raw.times, dtype=float)
        if meas_date is not None:
            time_origin_unix = float(datetime_to_unix_timestamp(meas_date))
            detail_timestamps = time_origin_unix + raw_time_values
        elif reference_datetime is not None:
            time_origin_unix = float(datetime_to_unix_timestamp(reference_datetime))
            detail_timestamps = time_origin_unix + raw_time_values
        else:
            detail_timestamps = raw_time_values
        
        t_start = float(detail_timestamps[0]) if len(detail_timestamps) > 0 else 0.0
        t_end = float(detail_timestamps[-1]) if len(detail_timestamps) > 0 else 0.0
        t_duration = t_end - t_start
        base_intervals_df = pd.DataFrame({
            't_start': [t_start],
            't_duration': [t_duration],
            't_end': [t_end]
        })
        
        # Extract EEG channel data
        eeg_channels = [ch for ch in raw.ch_names if raw.get_channel_types([ch])[0] == 'eeg']
        if eeg_channels:
            try:
                eeg_data = raw.get_data(picks=eeg_channels)
                eeg_df = pd.DataFrame(eeg_data.T, columns=eeg_channels)
                eeg_df['t'] = detail_timestamps
                
                # Create EEGTrackDatasource
                eeg_datasource = EEGTrackDatasource(
                    intervals_df=base_intervals_df.copy(),
                    eeg_df=eeg_df,
                    custom_datasource_name=f"EEG_{stream_name}",
                    max_points_per_second=10.0,
                    enable_downsampling=True,
                    fallback_normalization_mode=ChannelNormalizationMode.INDIVIDUAL
                )
                datasources.append(eeg_datasource)
                logger.info(f"  Created EEG datasource for '{stream_name}' with {len(eeg_channels)} channels")

                # Create EEGSpectrogramTrackDatasource (same intervals, detail = spectrogram image)
                if EEGSpectrogramTrackDatasource is not None and EEG_SPECTROGRAM_AVAILABLE and compute_raw_eeg_spectrogram is not None:
                    try:
                        spec_result = compute_raw_eeg_spectrogram(raw)
                        if eeg_datasource is not None:
                            spec_datasource_kwargs = dict(lab_obj_dict=eeg_datasource.lab_obj_dict, raw_datasets_dict=eeg_datasource.raw_datasets_dict, parent=eeg_datasource)
                        else:
                            spec_datasource_kwargs = dict()

                        spec_datasource = EEGSpectrogramTrackDatasource(intervals_df=base_intervals_df.copy(), spectrogram_result=spec_result, custom_datasource_name=f"EEG_Spectrogram_{stream_name}",
                                                                        **spec_datasource_kwargs)
                        datasources.append(spec_datasource)
                        logger.info(f"  Created EEG Spectrogram datasource for '{stream_name}'")
                    except Exception as spec_e:
                        logger.warning(f"Warning: Failed to create spectrogram for '{stream_name}': {spec_e}")
            except Exception as e:
                logger.warning(f"Warning: Failed to extract EEG data from '{stream_name}': {e}")
        
        # Extract Motion data (check for motion channels)
        motion_channel_names = ['AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'GyroZ']
        motion_channels = [ch for ch in raw.ch_names if any(mc in ch for mc in motion_channel_names)]
        if not motion_channels:
            # Try alternative naming
            motion_channels = [ch for ch in raw.ch_names if 'acc' in ch.lower() or 'gyro' in ch.lower() or 'motion' in ch.lower()]
        
        if motion_channels:
            try:
                motion_data = raw.get_data(picks=motion_channels)
                # Map to standard motion channel names if possible
                motion_df = pd.DataFrame(motion_data.T, columns=motion_channels)
                motion_df['t'] = detail_timestamps
                
                # Create MotionTrackDatasource
                if MotionTrackDatasource is not None:
                    motion_datasource = MotionTrackDatasource(
                        intervals_df=base_intervals_df.copy(),
                        motion_df=motion_df,
                        custom_datasource_name=f"MOTION_{stream_name}",
                        max_points_per_second=10.0,
                        enable_downsampling=True,
                        fallback_normalization_mode=ChannelNormalizationMode.GROUPMINMAXRANGE
                    )
                    datasources.append(motion_datasource)
                    logger.info(f"  Created Motion datasource for '{stream_name}' with {len(motion_channels)} channels")
            except Exception as e:
                logger.warning(f"Warning: Failed to extract Motion data from '{stream_name}': {e}")
        
        # Extract Annotations
        if hasattr(raw, 'annotations') and raw.annotations is not None and len(raw.annotations) > 0:
            try:
                annotations_df = raw.annotations.to_data_frame()
                if meas_date is not None:
                    annotation_time_origin_unix = float(datetime_to_unix_timestamp(meas_date))
                    annotations_df['t'] = annotation_time_origin_unix + pd.to_numeric(annotations_df['onset'], errors='coerce')
                elif reference_datetime is not None:
                    annotation_time_origin_unix = float(datetime_to_unix_timestamp(reference_datetime))
                    annotations_df['t'] = annotation_time_origin_unix + pd.to_numeric(annotations_df['onset'], errors='coerce')
                else:
                    annotations_df['t'] = pd.to_numeric(annotations_df['onset'], errors='coerce')
                
                # Create log datasource for annotations
                if LogTextDataFramePlotDetailRenderer is not None:
                    log_renderer = LogTextDataFramePlotDetailRenderer(
                        text_color='white',
                        text_size=10,
                        channel_names=['description']
                    )
                    
                    # Prepare DataFrame with 't' and 'description' columns
                    log_df = pd.DataFrame({
                        't': annotations_df['t'],
                        'description': annotations_df['description'].astype(str)
                    })
                    
                    # Create intervals for each annotation
                    annotation_intervals = []
                    for _, ann_row in annotations_df.iterrows():
                        ann_t_start = ann_row['t']
                        ann_duration = ann_row.get('duration', 0.0)
                        
                        annotation_intervals.append({
                            't_start': float(ann_t_start),
                            't_duration': float(ann_duration),
                            't_end': float(ann_t_start) + float(ann_duration)
                        })
                    
                    if annotation_intervals:
                        ann_intervals_df = pd.DataFrame(annotation_intervals)
                        
                        ann_datasource = IntervalProvidingTrackDatasource(
                            intervals_df=ann_intervals_df,
                            detailed_df=log_df,
                            custom_datasource_name=f"ANNOTATIONS_{stream_name}",
                            detail_renderer=log_renderer,
                            enable_downsampling=False
                        )
                        datasources.append(ann_datasource)
                        logger.info(f"  Created Annotations datasource for '{stream_name}' with {len(annotations_df)} annotations")
            except Exception as e:
                logger.warning(f"Warning: Failed to extract Annotations from '{stream_name}': {e}")
        
        return datasources
    
    def _process_xdf_streams(self, streams: List) -> Tuple[Dict, Dict]:
        """Process XDF streams to extract datasources.
        
        Args:
            streams: List of stream dictionaries from pyxdf
            
        Returns:
            Tuple of (all_streams dict, all_streams_datasources dict)
        """
        return perform_process_single_xdf_file_all_streams(streams=streams)
    
    def _filter_streams_by_name(self, streams: List, stream_allowlist: Optional[List[str]] = None, stream_blocklist: Optional[List[str]] = None) -> List:
        """Filter streams by name using regex patterns.
        
        Args:
            streams: List of stream dictionaries from pyxdf
            stream_allowlist: Optional list of regex patterns. If provided, only streams matching any pattern are kept.
            stream_blocklist: Optional list of regex patterns. If provided, streams matching any pattern are excluded.
            
        Returns:
            Filtered list of streams
            
        Raises:
            ValueError: If both allowlist and blocklist are provided
        """
        if stream_allowlist is not None and stream_blocklist is not None:
            raise ValueError("Cannot specify both stream_allowlist and stream_blocklist. Only one can be provided.")
        
        if stream_allowlist is None and stream_blocklist is None:
            return streams
        
        filtered_streams = []
        filtered_out_names = []
        
        for stream in streams:
            stream_name = stream['info']['name'][0]
            should_include = True
            
            if stream_allowlist is not None:
                # Include only if matches any pattern in allowlist
                should_include = any(re.search(pattern, stream_name) for pattern in stream_allowlist)
            elif stream_blocklist is not None:
                # Exclude if matches any pattern in blocklist
                should_include = not any(re.search(pattern, stream_name) for pattern in stream_blocklist)
            
            if should_include:
                filtered_streams.append(stream)
            else:
                filtered_out_names.append(stream_name)
        
        if filtered_out_names:
            filter_type = "allowlist" if stream_allowlist is not None else "blocklist"
            patterns = stream_allowlist if stream_allowlist is not None else stream_blocklist
            logger.info(f"Filtered out {len(filtered_out_names)} stream(s) using {filter_type} {patterns}: {filtered_out_names}")
        
        logger.info(f"Kept {len(filtered_streams)} out of {len(streams)} stream(s) after filtering")
        
        return filtered_streams

    # @function_attributes(short_name=None, tags=['MAIN', 'add'], input_requires=[], output_provides=[], uses=[], used_by=['self.update_timeline', 'self.build_from_datasources'], creation_date='2026-02-03 19:57', related_items=[])
    def _add_tracks_to_timeline(self, timeline: SimpleTimelineWidget, datasources: List[TrackDatasource], enable_hide_extra_track_x_axes: bool=False, use_absolute_datetime_track_mode: bool = True) -> None:
        """Add tracks to a timeline widget.
        
        Args:
            timeline: SimpleTimelineWidget instance
            datasources: List of TrackDatasource instances to add
        """
        def _is_eeg_spectrogram_datasource(ds: TrackDatasource) -> bool:
            if EEGSpectrogramTrackDatasource is not None and isinstance(ds, EEGSpectrogramTrackDatasource):
                return True
            return ds.custom_datasource_name.startswith('EEG_Spectrogram_')

        spec_names = [d.custom_datasource_name for d in datasources if _is_eeg_spectrogram_datasource(d)]
        logger.info(f"[dock_group:eeg_spec] spectrogram datasource count={len(spec_names)} names={spec_names!r}")

        for datasource in datasources:
            # Get detail renderer
            a_detail_renderer = datasource.get_detail_renderer()
            _scheme_key = default_dock_named_color_scheme_key(datasource.custom_datasource_name)
            _is_spec = _is_eeg_spectrogram_datasource(datasource)
            display_config = CustomCyclicColorsDockDisplayConfig(named_color_scheme=NamedColorScheme[_scheme_key], showCloseButton=True, showCollapseButton=True, showGroupButton=_is_spec, corner_radius='3px')

            if getattr(display_config, 'custom_button_configs', None) is None:
                setattr(display_config, 'custom_button_configs', {})
                # setattr(display_config, 'custom_button_callback_connections', {})

            # else:
            #     ## disconnect before setting now
            #     for k, v in getattr(display_config, 'custom_button_callback_connections', {}).items():
            #         a_dock.sigCustomButtonClicked.disconnect(v)



            if datasource.custom_datasource_name.startswith('LOG_') and getattr(datasource, 'detailed_df', None) is not None:
                setattr(display_config, 'custom_button_configs', {'show_table': DockButtonConfig(showButton=True, buttonQIcon=getGraphIcon('table'), buttonToolTip='Show table')})
            elif getattr(datasource, 'detailed_df', None) is not None:
                ## enable for all tracks with a detailed_df
                setattr(display_config, 'custom_button_configs', {'show_table': DockButtonConfig(showButton=True, buttonQIcon=getGraphIcon('table'), buttonToolTip='Show table')})


            track_widget, a_root_graphics, a_plot_item, a_dock = timeline.add_new_embedded_pyqtgraph_render_plot_widget(
                name=datasource.custom_datasource_name,
                dockSize=(500, 80),
                dockAddLocationOpts=['bottom'],
                display_config=display_config,
                sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA,
                dock_group_names=[SimpleTimelineWidget.EEG_SPECTROGRAM_DOCK_GROUP] if _is_spec else None
            )
            # if datasource.custom_datasource_name.startswith('LOG_') and getattr(datasource, 'detailed_df', None) is not None:


            # for a_custom_button_key, a_dock_button_config in display_config.custom_button_configs.items():
            #     if a_custom_button_key == 'show_table':

            if getattr(datasource, 'detailed_df', None) is not None:
                if ('show_table' in display_config.custom_button_configs):
                    def _on_show_table(dock, button_id, tl=timeline, ds=datasource):
                        if button_id != 'show_table':
                            return
                        table_name = f"{ds.custom_datasource_name}_table"
                        existing = tl.ui.dynamic_docked_widget_container.find_display_dock(table_name)
                        if existing is not None:
                            existing.show()
                            existing.raise_()
                            return

                        _scheme_key = default_dock_named_color_scheme_key(datasource.custom_datasource_name)
                        table_dock_display_config = CustomCyclicColorsDockDisplayConfig(named_color_scheme=NamedColorScheme[_scheme_key], showCloseButton=True, showCollapseButton=True, showGroupButton=True, corner_radius='1px')
                        tl.add_dataframe_table_track(track_name=table_name, dataframe=getattr(ds, 'detailed_df'), time_column='t', dockSize=(400, 200), display_config=table_dock_display_config, sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA)
                    a_dock.sigCustomButtonClicked.connect(_on_show_table)
            


            assert a_detail_renderer is not None, f"Detail renderer is None for datasource: {datasource.custom_datasource_name}"
            #TODO 2026-03-28 06:30: - [ ] note `track_widget.set_track_renderer(a_detail_renderer)` was removed
            # track_widget.set_track_renderer(a_detail_renderer)
            # bottom_label_text: str = 'Time'
            bottom_label_text: str = ''

            # Set the plot to show the full time range
            # Handle datetime objects directly
            if isinstance(timeline.total_data_start_time, (datetime, pd.Timestamp)):
                if not use_absolute_datetime_track_mode:
                    # Timeline uses datetime objects - convert directly to Unix timestamps
                    unix_start = datetime_to_unix_timestamp(timeline.total_data_start_time)
                    unix_end = datetime_to_unix_timestamp(timeline.total_data_end_time)
                    a_plot_item.setXRange(unix_start, unix_end, padding=0)
                else:
                    ## use_absolute_datetime_track_mode - use the datetimes directly
                    unix_start = datetime_to_unix_timestamp(timeline.total_data_start_time)
                    unix_end = datetime_to_unix_timestamp(timeline.total_data_end_time)
                    # a_plot_item.setXRange(timeline.total_data_start_time, timeline.total_data_end_time, padding=0) ## performs So min and max (your timeline.total_data_start_time and timeline.total_data_end_time) are datetime objects. In Python, datetime + datetime is invalid (only datetime - datetime or datetime + timedelta are defined), so you get that TypeError.
                    a_plot_item.setXRange(unix_start, unix_end, padding=0)

                a_plot_item.setLabel('bottom', bottom_label_text)
            elif (timeline.reference_datetime is not None):
                # Timeline uses float timestamps with reference_datetime - convert to datetime then Unix timestamp
                dt_start = float_to_datetime(timeline.total_data_start_time, timeline.reference_datetime)
                dt_end = float_to_datetime(timeline.total_data_end_time, timeline.reference_datetime)
                # Convert datetime to Unix timestamp for PyQtGraph (DateAxisItem expects timestamps but displays as dates)
                unix_start = datetime_to_unix_timestamp(dt_start)
                unix_end = datetime_to_unix_timestamp(dt_end)
                a_plot_item.setXRange(unix_start, unix_end, padding=0)
                a_plot_item.setLabel('bottom', bottom_label_text)
            else:
                # Fallback: use float timestamps directly
                a_plot_item.setXRange(timeline.total_data_start_time, timeline.total_data_end_time, padding=0)
                a_plot_item.setLabel('bottom', bottom_label_text, units='s')

            # a_plot_item.showLabel('bottom', False)

            a_plot_item.setYRange(0, 1, padding=0)
            a_plot_item.setLabel('left', datasource.custom_datasource_name)
            a_plot_item.hideAxis('left')  # Hide Y-axis for cleaner look
            
            # Add the track to the plot (installs TrackRenderer on track_widget; options panel must be created after this)
            a_track_name: str = datasource.custom_datasource_name
            timeline.add_track(datasource, name=a_track_name, plot_item=a_plot_item)

            # Explicitly set the optionsPanel attribute:
            track_widget.optionsPanel = track_widget.getOptionsPanel()
            # Or if available:
            a_dock.updateWidgetsHaveOptionsPanel()
            a_dock.update()

            # Or if available:
            if hasattr(a_dock, 'updateTitleBar') or hasattr(a_dock, 'refresh'):
                a_dock.updateTitleBar()
        ## END for datasource in datasources...

        if spec_names:
            _dock_container = timeline.ui.dynamic_docked_widget_container
            _spec_group_id = SimpleTimelineWidget.EEG_SPECTROGRAM_DOCK_GROUP
            logger.info(f"[dock_group:eeg_spec] calling layout_dockGroups for group={_spec_group_id!r}")
            _pre_groups = _dock_container.get_dockGroup_dock_dict()
            _pre_members = {k: [d.name() for d in v] for k, v in _pre_groups.items()}
            logger.debug(f"[dock_group:eeg_spec] dock groups before layout keys={list(_pre_groups.keys())!r} members={_pre_members!r}")
            try:
                _dock_container.layout_dockGroups(dock_group_names_order=[_spec_group_id], dock_group_add_location_opts={_spec_group_id: ['bottom']})
            except Exception:
                logger.exception("[dock_group:eeg_spec] EEG spectrogram dock grouping failed")
            else:
                logger.info(f"[dock_group:eeg_spec] layout_dockGroups finished; matplotlib_view_widgets count={len(timeline.ui.matplotlib_view_widgets)}")
                if hasattr(_dock_container, 'nested_dock_items') and getattr(_dock_container, 'nested_dock_items', None):
                    logger.debug(f"[dock_group:eeg_spec] nested_dock_items keys={list(_dock_container.nested_dock_items.keys())!r}")

        # Hide x-axis labels for all tracks except the bottom-most one
        if len(timeline.ui.matplotlib_view_widgets) > 1:
            # Get all plot items
            all_plot_items = []
            for widget_name, widget in timeline.ui.matplotlib_view_widgets.items():
                plot_item = widget.getRootPlotItem()
                if plot_item is not None:
                    all_plot_items.append((widget_name, plot_item))
            
            # Hide x-axis for all except the last one (bottom-most)
            if len(all_plot_items) > 1:
                # Hide x-axis for all tracks except the last one
                if enable_hide_extra_track_x_axes:
                    for widget_name, plot_item in all_plot_items[:-3]:
                        plot_item.hideAxis('bottom')
                    # Ensure the last track shows its x-axis
                    all_plot_items[-1][1].showAxis('bottom')
                else:
                    ## show all
                    for widget_name, plot_item in all_plot_items:
                        plot_item.showAxis('bottom')
