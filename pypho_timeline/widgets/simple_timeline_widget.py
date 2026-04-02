from __future__ import annotations # prevents having to specify types for typehinting as strings
from typing import TYPE_CHECKING

"""
Simple timeline widget for pyPhoTimeline library.

This module provides a simple example timeline widget that demonstrates pyPhoTimeline usage,
along with utility functions for processing stream data.
"""
import json
import logging
import numpy as np
import pandas as pd
from typing import Tuple, List, Dict, Optional, Union, Any
from datetime import datetime, timedelta
from pathlib import Path
from qtpy import QtWidgets, QtCore
import pyqtgraph as pg
from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode
from pypho_timeline.utils.datetime_helpers import float_to_datetime, datetime_to_unix_timestamp, datetime_to_float, get_reference_datetime_from_xdf_header, unix_timestamp_to_datetime
from pypho_timeline.docking.nested_dock_area_widget import NestedDockAreaWidget
from pypho_timeline.docking.specific_dock_widget_mixin import SpecificDockWidgetManipulatingMixin
from pypho_timeline.rendering.datasources.track_datasource import IntervalProvidingTrackDatasource
from pypho_timeline.rendering.datasources.specific import MotionTrackDatasource, VideoTrackDatasource
from pypho_timeline.rendering.datasources.specific.eeg import EEGTrackDatasource
from pypho_timeline.rendering.mixins.track_rendering_mixin import TrackRenderingMixin
from pypho_timeline.rendering.helpers import ChannelNormalizationMode

from pyphocorehelpers.gui.PhoUIContainer import PhoUIContainer
from pyphocorehelpers.DataStructure.general_parameter_containers import RenderPlotsData, RenderPlots
from pyphocorehelpers.DataStructure.RenderPlots.PyqtgraphRenderPlots import PyqtgraphRenderPlots

from pypho_timeline.widgets.track_options_panels import apply_track_options_document, build_track_options_document

if TYPE_CHECKING:
    ## typehinting only imports here
    from pypho_timeline.docking.dock_display_configs import CustomDockDisplayConfig

logger = logging.getLogger(__name__)

# Create a simple time window object (mimicking spikes_window)
class SimpleTimeWindow:
    def __init__(self, start, end, window_dur, window_start):
        self.total_df_start_end_times = (start, end)
        self.active_window_start_time = window_start
        
        # Handle datetime objects for window_end calculation
        if isinstance(window_start, (datetime, pd.Timestamp)) and isinstance(window_dur, timedelta):
            self.active_window_end_time = window_start + window_dur
        elif isinstance(window_start, (datetime, pd.Timestamp)):
            self.active_window_end_time = window_start + timedelta(seconds=float(window_dur))
        else:
            self.active_window_end_time = window_start + window_dur
        
        self.active_time_window = (self.active_window_start_time, self.active_window_end_time)
        self.window_duration = window_dur
        
    def update_window_start_end(self, start_t, end_t):
        self.active_window_start_time = start_t
        self.active_window_end_time = end_t
        self.active_time_window = (start_t, end_t)



class SimpleTimelineWidget(TrackRenderingMixin, SpecificDockWidgetManipulatingMixin, QtWidgets.QWidget):
    """A simple example timeline widget that demonstrates pyPhoTimeline usage.

    from pypho_timeline.widgets.simple_timeline_widget import SimpleTimelineWidget, SimpleTimeWindow

    Optional overview minimap (primary tracks, overview intervals; viewport region syncs with main tracks)::

        tw = SimpleTimelineWidget(...)
        tw.add_timeline_overview_strip(position='bottom', row_height_px=20)

    XDF builder path adds the strip at the bottom by default via ``TimelineBuilder.build_from_xdf_files``.

    """
    
    # Signal emitted when the time window changes
    window_scrolled = QtCore.Signal(float, float)
    compare_window_scrolled = QtCore.Signal(float, float)
    SPLIT_PRIMARY_DOCK_GROUP = 'timeline_primary_column'
    SPLIT_COMPARE_DOCK_GROUP = 'timeline_compare_column'
    
    @property
    def interval_rendering_plots(self):
        """Return list of plots for interval rendering."""
        # Return all plot items from matplotlib_view_widgets
        plots = []
        for widget in self.ui.matplotlib_view_widgets.values():
            plots.append(widget.getRootPlotItem())
        return plots
    

    def __init__(self, total_start_time: Union[float, datetime, pd.Timestamp] = 0.0, total_end_time: Union[float, datetime, pd.Timestamp] = 100.0, window_duration: Union[float, timedelta] = 10.0, window_start_time: Union[float, datetime, pd.Timestamp] = 30.0, add_example_tracks=False, reference_datetime: Optional[datetime] = None, parent=None):
        super().__init__(parent=parent)
        
        # Store whether to add example tracks
        self._add_example_tracks = add_example_tracks
        
        # Initialize UI container
        self.ui = PhoUIContainer()
        self.ui.matplotlib_view_widgets = {}
        self.ui.connections = {}
        
        # Initialize plots_data and plots for mixins
        self.plots_data = RenderPlotsData(name='SimpleTimelineWidget')
        self.plots = PyqtgraphRenderPlots(name='SimpleTimelineWidget', render_detail_graphics_objects={})
        
        # Reference datetime for datetime axis alignment (shared across all tracks)
        if reference_datetime is None:
            from pypho_timeline.utils.datetime_helpers import get_earliest_reference_datetime
            reference_datetime = get_earliest_reference_datetime([], [])
        self.reference_datetime = reference_datetime
        
        # Convert time properties to datetime if they're floats and reference_datetime is available
        # Otherwise store as-is (datetime objects stay as datetime, floats stay as floats)
        if isinstance(total_start_time, (int, float)):
            if reference_datetime is not None:
                # Convert relative float to absolute datetime
                self.total_data_start_time = reference_datetime + timedelta(seconds=float(total_start_time))
            else:
                # Keep as float if no reference
                self.total_data_start_time = float(total_start_time)
        else:
            # Already a datetime object, convert to pd.Timestamp for consistency
            self.total_data_start_time = pd.Timestamp(total_start_time)
            if self.total_data_start_time.tzinfo is None:
                self.total_data_start_time = self.total_data_start_time.tz_localize('UTC')
        
        if isinstance(total_end_time, (int, float)):
            if reference_datetime is not None:
                self.total_data_end_time = reference_datetime + timedelta(seconds=float(total_end_time))
            else:
                self.total_data_end_time = float(total_end_time)
        else:
            self.total_data_end_time = pd.Timestamp(total_end_time)
            if self.total_data_end_time.tzinfo is None:
                self.total_data_end_time = self.total_data_end_time.tz_localize('UTC')
        
        if isinstance(window_start_time, (int, float)):
            if reference_datetime is not None:
                self.active_window_start_time = reference_datetime + timedelta(seconds=float(window_start_time))
            else:
                self.active_window_start_time = float(window_start_time)
        else:
            self.active_window_start_time = pd.Timestamp(window_start_time)
            if self.active_window_start_time.tzinfo is None:
                self.active_window_start_time = self.active_window_start_time.tz_localize('UTC')
        
        # Calculate window_end_time
        if isinstance(self.active_window_start_time, (datetime, pd.Timestamp)):
            if isinstance(window_duration, timedelta):
                self.active_window_end_time = self.active_window_start_time + window_duration
            else:
                self.active_window_end_time = self.active_window_start_time + timedelta(seconds=float(window_duration))
        else:
            self.active_window_end_time = self.active_window_start_time + float(window_duration)
        
        self.spikes_window = SimpleTimeWindow(
            self.total_data_start_time, self.total_data_end_time, window_duration, self.active_window_start_time
        )
        self._last_applied_plot_window_x0 = self._window_value_to_signal_float(self.active_window_start_time)
        self._last_applied_plot_window_x1 = self._window_value_to_signal_float(self.active_window_end_time)
        self.compare_window_start_time = self.active_window_start_time
        self.compare_window_end_time = self.active_window_end_time
        self._is_updating_compare_window = False
        self._applying_window_from_signal = False
        self.ui.compare_track_names = set()
        self.ui.compare_track_master_name = None
        self.ui.split_group_docks = {}
        
        # Initialize plots_data and plots BEFORE setupUI (needed by mixins)
        # Initialize track rendering mixin
        self.TrackRenderingMixin_on_init()
        self.TrackRenderingMixin_on_setup()
        
        # Setup UI (this will call add_example_tracks which uses the mixins)
        self.setupUI()
        
        
    def setupUI(self):
        """Setup the user interface."""
        # Create main layout
        self.ui.layout = QtWidgets.QVBoxLayout(self)
        self.ui.layout.setContentsMargins(0, 0, 0, 0)

        self.ui.controls_layout = QtWidgets.QHBoxLayout()
        self.ui.controls_layout.setContentsMargins(4, 4, 4, 0)
        self.ui.jump_prev_interval_button = QtWidgets.QPushButton("◀")
        self.ui.jump_prev_interval_button.setToolTip("Jump to the start of the previous interval")
        self.ui.jump_prev_interval_button.setAutoDefault(False)
        self.ui.jump_prev_interval_button.clicked.connect(self._on_jump_prev_interval_clicked)
        self.ui.controls_layout.addWidget(self.ui.jump_prev_interval_button)
        self.ui.jump_next_interval_button = QtWidgets.QPushButton("▶")
        self.ui.jump_next_interval_button.setToolTip("Jump to the start of the next interval")
        self.ui.jump_next_interval_button.setAutoDefault(False)
        self.ui.jump_next_interval_button.clicked.connect(self._on_jump_next_interval_clicked)
        self.ui.controls_layout.addWidget(self.ui.jump_next_interval_button)
        self.ui.controls_layout.addStretch(1)
        self.ui.split_all_tracks_button = QtWidgets.QPushButton("Split All Tracks")
        self.ui.split_all_tracks_button.setToolTip("Create an independent compare column for every track.")
        self.ui.split_all_tracks_button.clicked.connect(self._on_split_all_tracks_clicked)
        self.ui.controls_layout.addWidget(self.ui.split_all_tracks_button)
        self.ui.save_track_options_button = QtWidgets.QPushButton("Save track options…")
        self.ui.save_track_options_button.setToolTip("Save channel visibility and related per-track options to a JSON file.")
        self.ui.save_track_options_button.setAutoDefault(False)
        self.ui.save_track_options_button.clicked.connect(self._on_save_track_options_clicked)
        self.ui.controls_layout.addWidget(self.ui.save_track_options_button)
        self.ui.load_track_options_button = QtWidgets.QPushButton("Load track options…")
        self.ui.load_track_options_button.setToolTip("Restore per-track options from a JSON file (matching track names).")
        self.ui.load_track_options_button.setAutoDefault(False)
        self.ui.load_track_options_button.clicked.connect(self._on_load_track_options_clicked)
        self.ui.controls_layout.addWidget(self.ui.load_track_options_button)
        self.ui.layout.addLayout(self.ui.controls_layout)
        
        # Create the dock area container
        self.ui.dynamic_docked_widget_container = NestedDockAreaWidget()
        self.ui.dynamic_docked_widget_container.setObjectName("dynamic_docked_widget_container")
        
        # Add to layout
        self.ui.layout.addWidget(self.ui.dynamic_docked_widget_container)

        self.TrackRenderingMixin_on_buildUI()
        
        # Add some example tracks (only if requested)
        if self._add_example_tracks:
            self.add_example_tracks()

        self.sigTrackAdded.connect(lambda _n: self._update_interval_jump_buttons_enabled())
        self.sigTrackRemoved.connect(lambda _n: self._update_interval_jump_buttons_enabled())
        self._update_interval_jump_buttons_enabled()
        QtCore.QTimer.singleShot(0, self._update_interval_jump_buttons_enabled)


    def _on_split_all_tracks_clicked(self):
        """Split every primary track into the compare column."""
        self.add_compare_column_for_all_tracks()


    def get_track_options_config(self) -> Dict[str, Any]:
        """Return a versioned dict of per-track options (e.g. channel visibility), suitable for JSON."""
        return build_track_options_document(self.track_renderers)


    def set_track_options_config(self, config: Dict[str, Any]) -> None:
        """Apply options from :meth:`get_track_options_config` or a loaded JSON document."""
        apply_track_options_document(config, self.track_renderers)


    def save_track_options_config_to_path(self, path: Union[str, Path]) -> None:
        """Write :meth:`get_track_options_config` to ``path`` as UTF-8 JSON."""
        p = Path(path)
        p.write_text(json.dumps(self.get_track_options_config(), indent=2), encoding="utf-8")


    def load_track_options_config_from_path(self, path: Union[str, Path]) -> None:
        """Load JSON from ``path`` and apply via :meth:`set_track_options_config`."""
        p = Path(path)
        self.set_track_options_config(json.loads(p.read_text(encoding="utf-8")))


    def _on_save_track_options_clicked(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save track options", "", "JSON (*.json);;All files (*.*)")
        if path:
            self.save_track_options_config_to_path(path)


    def _on_load_track_options_clicked(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load track options", "", "JSON (*.json);;All files (*.*)")
        if not path:
            return
        try:
            self.load_track_options_config_from_path(path)
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, "Load track options", str(ex))


    def _scalar_to_sort_float(self, t: Any) -> float:
        """Map a time scalar to float seconds for ordering (unix timestamp when datetime-like)."""
        if isinstance(t, (datetime, pd.Timestamp)):
            return pd.Timestamp(t).timestamp()
        if isinstance(t, (np.floating, np.integer)):
            return float(t)
        return float(t)


    # ==================================================================================================================================================================================================================================================================================== #
    # Jump Prev/Next Interval                                                                                                                                                                                                                                                              #
    # ==================================================================================================================================================================================================================================================================================== #
    def _collect_primary_interval_starts_unique(self) -> Tuple[np.ndarray, List[Any]]:
        """Sorted unique interval start keys (float) and one original scalar per key from primary tracks."""
        pairs: List[Tuple[float, Any]] = []
        for name in self.get_track_names_for_window_sync_group(window_sync_group='primary'):
            ds = self.track_datasources.get(name, None)
            if ds is None:
                continue
            df = getattr(ds, 'df', None)
            if df is None or df.empty or ('t_start' not in df.columns):
                continue
            for raw in df['t_start'].values:
                pairs.append((self._scalar_to_sort_float(raw), raw))
        if not pairs:
            return np.array([], dtype=float), []
        pairs.sort(key=lambda x: x[0])
        fs = np.array([p[0] for p in pairs], dtype=float)
        uniq_sorted, first_idx = np.unique(fs, return_index=True)
        originals = [pairs[int(i)][1] for i in first_idx]
        return uniq_sorted, originals


    def _interval_jump_prev_next_targets(self) -> Tuple[Optional[Any], Optional[Any]]:
        """(previous_start, next_start) relative to active_window_start_time; None if absent."""
        arr, originals = self._collect_primary_interval_starts_unique()
        if arr.size == 0:
            return None, None
        w = self._scalar_to_sort_float(self.active_window_start_time)
        idx_l = int(np.searchsorted(arr, w, side='left'))
        idx_r = int(np.searchsorted(arr, w, side='right'))
        prev_tgt = originals[idx_l - 1] if idx_l > 0 else None
        next_tgt = originals[idx_r] if idx_r < len(originals) else None
        return prev_tgt, next_tgt


    _GOTO_NAV_TIME_EPS = 1e-6


    def _target_window_start_go_latest(self) -> Any:
        """Scroll target start for :meth:`go_to_latest_window` (same clamping as that action)."""
        if isinstance(self.active_window_start_time, (datetime, pd.Timestamp)) and isinstance(self.active_window_end_time, (datetime, pd.Timestamp)):
            duration = self.active_window_end_time - self.active_window_start_time
            new_start = self.total_data_end_time - duration
            if new_start < self.total_data_start_time:
                new_start = self.total_data_start_time
            return new_start
        duration = float(self.active_window_end_time) - float(self.active_window_start_time)
        new_start = float(self.total_data_end_time) - duration
        ts = float(self.total_data_start_time)
        if new_start < ts:
            new_start = ts
        return new_start


    def _target_window_start_go_earliest(self) -> Any:
        """Scroll target start for :meth:`go_to_earliest_window` (same clamping as that action)."""
        if isinstance(self.active_window_start_time, (datetime, pd.Timestamp)) and isinstance(self.active_window_end_time, (datetime, pd.Timestamp)):
            duration = self.active_window_end_time - self.active_window_start_time
            new_start = self.total_data_start_time
            if new_start + duration > self.total_data_end_time:
                new_start = self.total_data_end_time - duration
            if new_start < self.total_data_start_time:
                new_start = self.total_data_start_time
            return new_start
        duration = float(self.active_window_end_time) - float(self.active_window_start_time)
        new_start = float(self.total_data_start_time)
        te = float(self.total_data_end_time)
        if new_start + duration > te:
            new_start = te - duration
        ts = float(self.total_data_start_time)
        if new_start < ts:
            new_start = ts
        return new_start


    def _goto_scroll_target_differs_from_active_start(self, target_start: Any) -> bool:
        return abs(self._scalar_to_sort_float(self.active_window_start_time) - self._scalar_to_sort_float(target_start)) > self._GOTO_NAV_TIME_EPS


    def _update_interval_jump_buttons_enabled(self):
        if not hasattr(self.ui, 'jump_prev_interval_button'):
            return
        prev_t, next_t = self._interval_jump_prev_next_targets()
        en_prev, en_next = prev_t is not None, next_t is not None
        tgt_earliest = self._target_window_start_go_earliest()
        tgt_latest = self._target_window_start_go_latest()
        en_earliest = self._goto_scroll_target_differs_from_active_start(tgt_earliest)
        en_latest = self._goto_scroll_target_differs_from_active_start(tgt_latest)
        self.ui.jump_prev_interval_button.setEnabled(en_prev)
        self.ui.jump_next_interval_button.setEnabled(en_next)
        p = self.parentWidget()
        while p is not None:
            if hasattr(p, 'actionGoToPrev'):
                p.actionGoToPrev.setEnabled(en_prev)
                if hasattr(p, 'actionGoToNext'):
                    p.actionGoToNext.setEnabled(en_next)
                if hasattr(p, 'actionGoToEarliest'):
                    p.actionGoToEarliest.setEnabled(en_earliest)
                if hasattr(p, 'actionGoToLatest'):
                    p.actionGoToLatest.setEnabled(en_latest)
                break
            p = p.parentWidget()


    def _on_jump_prev_interval_clicked(self):
        prev_t, _ = self._interval_jump_prev_next_targets()
        if prev_t is not None:
            self.simulate_window_scroll(prev_t)


    def _on_jump_next_interval_clicked(self):
        _, next_t = self._interval_jump_prev_next_targets()
        if next_t is not None:
            self.simulate_window_scroll(next_t)


    def jump_to_previous_interval(self):
        self._on_jump_prev_interval_clicked()


    def jump_to_next_interval(self):
        self._on_jump_next_interval_clicked()


    def go_to_latest_window(self):
        """Move the viewport so its end aligns with ``total_data_end_time``, preserving window duration; start is clamped to ``total_data_start_time``."""
        self.simulate_window_scroll(self._target_window_start_go_latest())


    def go_to_earliest_window(self):
        """Move the viewport so its start aligns with ``total_data_start_time`` when possible, preserving window duration; if the window would extend past ``total_data_end_time``, start is shifted earlier; start is clamped to ``total_data_start_time`` when needed (symmetric to ``go_to_latest_window``)."""
        self.simulate_window_scroll(self._target_window_start_go_earliest())


    # ==================================================================================================================================================================================================================================================================================== #
    # Split Docks Horizontally/Multiple Viewport Functionality                                                                                                                                                                                                                             #
    # ==================================================================================================================================================================================================================================================================================== #
    def _set_track_dock_group(self, track_name: str, dock_group_name: str):
        """Assign a single group name to an existing track dock."""
        track_dock = self.ui.dynamic_docked_widget_container.find_display_dock(track_name)
        if track_dock is None:
            return None

        track_dock.config.dock_group_names = [dock_group_name]
        return track_dock


    def _retag_split_track_docks(self):
        """Tag primary and compare tracks so they can be wrapped into parent split columns."""
        for track_name in self.get_track_names_for_window_sync_group(window_sync_group='primary'):
            self._set_track_dock_group(track_name, self.SPLIT_PRIMARY_DOCK_GROUP)

        for track_name in self.get_track_names_for_window_sync_group(window_sync_group='compare'):
            self._set_track_dock_group(track_name, self.SPLIT_COMPARE_DOCK_GROUP)


    def _rebuild_split_track_dock_groups(self):
        """Wrap the primary and compare tracks into two parent docks that resize as columns."""
        dock_container = self.ui.dynamic_docked_widget_container
        if hasattr(dock_container, 'nested_dock_items') and len(dock_container.nested_dock_items) > 0:
            dock_container.unwrap_docks_in_all_nested_dock_area()

        self._retag_split_track_docks()
        split_group_docks, _ = dock_container.layout_dockGroups(dock_group_names_order=[self.SPLIT_PRIMARY_DOCK_GROUP, self.SPLIT_COMPARE_DOCK_GROUP], dock_group_add_location_opts={self.SPLIT_PRIMARY_DOCK_GROUP: ['bottom']})
        primary_group_dock = split_group_docks.get(self.SPLIT_PRIMARY_DOCK_GROUP, None)
        if primary_group_dock is not None and (self.SPLIT_COMPARE_DOCK_GROUP in split_group_docks):
            dock_container.unwrap_docks_in_nested_dock_area(dock_group_name=self.SPLIT_COMPARE_DOCK_GROUP)
            dock_container.layout_dockGroups(dock_group_names_order=[self.SPLIT_PRIMARY_DOCK_GROUP, self.SPLIT_COMPARE_DOCK_GROUP], dock_group_add_location_opts={self.SPLIT_PRIMARY_DOCK_GROUP: ['bottom'], self.SPLIT_COMPARE_DOCK_GROUP: [primary_group_dock, 'right']})

        self.ui.split_group_docks = getattr(dock_container, 'nested_dock_items', {})
        

    def simulate_window_scroll(self, new_start_time: Union[float, datetime, pd.Timestamp]): # , new_end_time: Optional[Union[float, datetime, pd.Timestamp]]=None
        """Simulate scrolling the time window (for demonstration)."""
        # Calculate duration
        if isinstance(self.active_window_start_time, (datetime, pd.Timestamp)) and isinstance(self.active_window_end_time, (datetime, pd.Timestamp)):
            duration = self.active_window_end_time - self.active_window_start_time
            if isinstance(new_start_time, (int, float)):
                # Convert float to datetime if needed
                if self.reference_datetime is not None:
                    new_start_time = self.reference_datetime + timedelta(seconds=float(new_start_time))
                else:
                    new_start_time = pd.Timestamp.fromtimestamp(float(new_start_time), tz='UTC')
            new_end_time = new_start_time + duration
        else:
            duration = self.active_window_end_time - self.active_window_start_time
            if isinstance(new_start_time, (datetime, pd.Timestamp)):
                # Convert datetime to float if needed
                new_start_time = new_start_time.timestamp() if hasattr(new_start_time, 'timestamp') else pd.Timestamp(new_start_time).timestamp()
            new_end_time = new_start_time + duration
        
        self.active_window_start_time = new_start_time
        self.active_window_end_time = new_end_time
        self.spikes_window.update_window_start_end(new_start_time, new_end_time)
        
        # Emit the signal to update synchronized tracks (convert to float for signal)
        if isinstance(new_start_time, (datetime, pd.Timestamp)):
            emit_start = new_start_time.timestamp() if hasattr(new_start_time, 'timestamp') else pd.Timestamp(new_start_time).timestamp()
            emit_end = new_end_time.timestamp() if hasattr(new_end_time, 'timestamp') else pd.Timestamp(new_end_time).timestamp()
        else:
            emit_start = float(new_start_time)
            emit_end = float(new_end_time)
        self._last_applied_plot_window_x0 = float(emit_start)
        self._last_applied_plot_window_x1 = float(emit_end)
        self._applying_window_from_signal = True
        try:
            self.update_window(emit_start, emit_end) ## the main update function, calls recurrsively
            self.window_scrolled.emit(emit_start, emit_end)
        finally:
            self._applying_window_from_signal = False
        if isinstance(new_start_time, (datetime, pd.Timestamp)):
            print(f"Window scrolled to: {new_start_time} - {new_end_time}")
        else:
            print(f"Window scrolled to: {new_start_time:.2f} - {new_end_time:.2f}")

        self._update_interval_jump_buttons_enabled()


    def apply_active_window_from_plot_x(self, x0: float, x1: float, block_signals: bool=True):
        """Set the active window from pyqtgraph plot x (Unix seconds if ``reference_datetime`` is set, else data seconds). Updates ``spikes_window`` and emits ``window_scrolled``."""
        xa, xb = (float(x0), float(x1)) if x0 <= x1 else (float(x1), float(x0))
        if xb <= xa:
            xb = xa + 1e-9
        if self.reference_datetime is not None:
            new_start = pd.Timestamp(unix_timestamp_to_datetime(xa))
            new_end = pd.Timestamp(unix_timestamp_to_datetime(xb))
            emit_start, emit_end = xa, xb
        else:
            new_start, new_end = xa, xb
            emit_start, emit_end = xa, xb

        self.active_window_start_time = new_start
        self.active_window_end_time = new_end
        self.spikes_window.update_window_start_end(new_start, new_end)
        self._last_applied_plot_window_x0 = float(emit_start)
        self._last_applied_plot_window_x1 = float(emit_end)
        if not block_signals:
            self._applying_window_from_signal = True
            try:
                self.window_scrolled.emit(float(emit_start), float(emit_end))
            finally:
                self._applying_window_from_signal = False

        logger.debug("apply_active_window_from_plot_x: x0=%s x1=%s active=[%s, %s] emit=[%s, %s] block_signals=%s emitted=%s", x0, x1, new_start, new_end, emit_start, emit_end, block_signals, not block_signals)
        self._update_interval_jump_buttons_enabled()


    def _window_value_to_signal_float(self, value: Union[float, datetime, pd.Timestamp]) -> float:
        """Convert a stored window boundary value to the float expected by Qt signals."""
        if isinstance(value, (datetime, pd.Timestamp)):
            return value.timestamp() if hasattr(value, 'timestamp') else pd.Timestamp(value).timestamp()
        return float(value)


    @pyqtExceptionPrintingSlot(float, float)
    def update_window(self, new_start: Optional[float] = None, new_end: Optional[float] = None):
        """Called to programmatically update the viewport window of all child tracks. 

        Args:
            new_start: New start time of viewport
            new_end: New end time of viewport
        """
        logger.debug(f"update_window: new_start: {new_start}, new_end: {new_end}")

        if new_start is None or new_end is None:
             logger.error(f"\tupdate_window: new_start: {new_start}, new_end: {new_end} one of the values is None! Aborting and not applying changes.")
             return

        # # Emit the signal to update synchronized tracks (convert to float for signal)
        # if isinstance(new_start_time, (datetime, pd.Timestamp)):
        #     emit_start = new_start_time.timestamp() if hasattr(new_start_time, 'timestamp') else pd.Timestamp(new_start_time).timestamp()
        #     emit_end = new_end_time.timestamp() if hasattr(new_end_time, 'timestamp') else pd.Timestamp(new_end_time).timestamp()
        # else:
        #     emit_start = float(new_start_time)
        #     emit_end = float(new_end_time)
        # self._last_applied_plot_window_x0 = float(emit_start)
        # self._last_applied_plot_window_x1 = float(emit_end)

        assert len(timeline.get_track_names_for_window_sync_group('primary')) > 0, f"must have at least one synced track to properly set window programmatically!"
        a_track_name: str = timeline.get_track_names_for_window_sync_group('primary')[0]
        a_widget, _, _ = timeline.get_track_tuple(a_track_name)
        # a_widget.on_window_changed(start_t=1776323640.023324, end_t=1776370487.5812337)
        a_widget.on_window_changed(start_t=new_start, end_t=new_end)
        ## done
        logger.debug(f"\done.")




    def _resolve_window_bounds(self, start_time: Optional[Union[float, datetime, pd.Timestamp]], end_time: Optional[Union[float, datetime, pd.Timestamp]], default_start: Union[float, datetime, pd.Timestamp], default_end: Union[float, datetime, pd.Timestamp]):
        """Resolve a partial window specification using the current window duration."""
        if (start_time is None) and (end_time is None):
            return default_start, default_end

        window_duration = default_end - default_start
        resolved_start = default_start if start_time is None else start_time
        resolved_end = default_end if end_time is None else end_time

        if start_time is None:
            resolved_start = resolved_end - window_duration
        elif end_time is None:
            resolved_end = resolved_start + window_duration

        return resolved_start, resolved_end


    def _copy_track_plot_configuration(self, source_plot_item: pg.PlotItem, destination_plot_item: pg.PlotItem):
        """Copy the visible plot configuration needed for compare tracks."""
        _, source_y_range = source_plot_item.viewRange()
        if len(source_y_range) == 2:
            destination_plot_item.setYRange(source_y_range[0], source_y_range[1], padding=0)

        destination_plot_item.hideAxis('left')
        if source_plot_item.getAxis('bottom').isVisible():
            destination_plot_item.showAxis('bottom')
        else:
            destination_plot_item.hideAxis('bottom')


    def _set_compare_window_state(self, start_time: Union[float, datetime, pd.Timestamp], end_time: Union[float, datetime, pd.Timestamp], emit_signal: bool = True):
        """Update the compare window state and notify any compare navigators."""
        self.compare_window_start_time = start_time
        self.compare_window_end_time = end_time

        if emit_signal:
            self.compare_window_scrolled.emit(self._window_value_to_signal_float(start_time), self._window_value_to_signal_float(end_time))


    def _on_compare_master_viewport_changed(self, evt):
        """Mirror the compare master viewport into the compare window state."""
        if self._is_updating_compare_window:
            return

        _, view_range, _ = evt
        x_range, _ = view_range
        if len(x_range) != 2:
            return

        if self.reference_datetime is not None:
            compare_start = unix_timestamp_to_datetime(x_range[0])
            compare_end = unix_timestamp_to_datetime(x_range[1])
        else:
            compare_start = float(x_range[0])
            compare_end = float(x_range[1])

        self._set_compare_window_state(compare_start, compare_end, emit_signal=True)


    def _set_compare_track_master(self, compare_track_name: str):
        """Designate the compare-column master plot that drives linked compare tracks."""
        self.ui.compare_track_master_name = compare_track_name
        compare_widget = self.ui.matplotlib_view_widgets.get(compare_track_name, None)
        if compare_widget is None:
            return

        compare_plot_item = compare_widget.getRootPlotItem()
        compare_viewbox = compare_plot_item.getViewBox() if compare_plot_item is not None else None
        if compare_viewbox is None:
            return

        proxy_key = 'compare_track_master_viewport_proxy'
        self.ui.connections[proxy_key] = pg.SignalProxy(compare_viewbox.sigRangeChanged, rateLimit=30, slot=self._on_compare_master_viewport_changed)


    def simulate_compare_window_scroll(self, new_start_time: Union[float, datetime, pd.Timestamp]):
        """Scroll the independent compare column without affecting the primary timeline."""
        if isinstance(self.compare_window_start_time, (datetime, pd.Timestamp)) and isinstance(self.compare_window_end_time, (datetime, pd.Timestamp)):
            duration = self.compare_window_end_time - self.compare_window_start_time
            if isinstance(new_start_time, (int, float)):
                if self.reference_datetime is not None:
                    new_start_time = self.reference_datetime + timedelta(seconds=float(new_start_time))
                else:
                    new_start_time = pd.Timestamp.fromtimestamp(float(new_start_time), tz='UTC')
            new_end_time = new_start_time + duration
        else:
            duration = self.compare_window_end_time - self.compare_window_start_time
            if isinstance(new_start_time, (datetime, pd.Timestamp)):
                new_start_time = new_start_time.timestamp() if hasattr(new_start_time, 'timestamp') else pd.Timestamp(new_start_time).timestamp()
            new_end_time = new_start_time + duration

        compare_master_name = getattr(self.ui, 'compare_track_master_name', None)
        compare_master_widget = self.ui.matplotlib_view_widgets.get(compare_master_name, None) if compare_master_name is not None else None

        self._is_updating_compare_window = True
        try:
            self._set_compare_window_state(new_start_time, new_end_time, emit_signal=False)
            if compare_master_widget is not None:
                compare_master_widget.on_window_changed(new_start_time, new_end_time)
        finally:
            self._is_updating_compare_window = False

        self._set_compare_window_state(new_start_time, new_end_time, emit_signal=True)


    def add_compare_track_view(self, track_name: str, compare_track_name: Optional[str] = None, compare_window_start_time: Optional[Union[float, datetime, pd.Timestamp]] = None, compare_window_end_time: Optional[Union[float, datetime, pd.Timestamp]] = None, dockSize: Optional[Tuple[int, int]] = None, enable_time_crosshair: bool = True):
        """Clone an existing timeline track into the independent compare column."""
        primary_widget, primary_track_renderer, primary_datasource = self.get_track_tuple(track_name)
        if (primary_widget is None) or (primary_track_renderer is None) or (primary_datasource is None):
            raise ValueError(f'Cannot create compare view for missing track "{track_name}".')

        if compare_track_name is None:
            compare_track_name = f"{track_name}__compare"

        compare_window_start_time, compare_window_end_time = self._resolve_window_bounds(compare_window_start_time, compare_window_end_time, self.compare_window_start_time, self.compare_window_end_time)
        extant_compare_widget, extant_compare_renderer, _ = self.get_track_tuple(compare_track_name)
        if (extant_compare_widget is not None) and (extant_compare_renderer is not None):
            extant_compare_plot_item = extant_compare_widget.getRootPlotItem()
            extant_compare_dock = self.ui.dynamic_docked_widget_container.find_display_dock(compare_track_name)
            extant_compare_widget.on_window_changed(compare_window_start_time, compare_window_end_time)
            self._set_compare_window_state(compare_window_start_time, compare_window_end_time, emit_signal=True)
            return extant_compare_widget, extant_compare_widget.getRootGraphicsLayoutWidget(), extant_compare_plot_item, extant_compare_dock

        primary_dock = self.ui.dynamic_docked_widget_container.find_display_dock(track_name)
        dock_add_location_opts = [primary_dock, 'right'] if primary_dock is not None else ['bottom']
        if dockSize is None:
            dockSize = (max(primary_widget.width(), 500), max(primary_widget.height(), 80))

        compare_widget, root_graphics, compare_plot_item, compare_dock = self.add_new_embedded_pyqtgraph_render_plot_widget(name=compare_track_name, dockSize=dockSize, dockAddLocationOpts=dock_add_location_opts, sync_mode=SynchronizedPlotMode.NO_SYNC, dock_group_names=[self.SPLIT_COMPARE_DOCK_GROUP])
        primary_plot_item = primary_widget.getRootPlotItem()
        self._copy_track_plot_configuration(primary_plot_item, compare_plot_item)
        self.add_track(primary_datasource, name=compare_track_name, plot_item=compare_plot_item, enable_time_crosshair=enable_time_crosshair, window_sync_group='compare')

        self.ui.compare_track_names.add(compare_track_name)
        if self.ui.compare_track_master_name is None:
            self._set_compare_track_master(compare_track_name)
        else:
            master_plot_item = self.ui.matplotlib_view_widgets[self.ui.compare_track_master_name].getRootPlotItem()
            compare_plot_item.setXLink(master_plot_item)

        compare_widget.on_window_changed(compare_window_start_time, compare_window_end_time)
        self._set_compare_window_state(compare_window_start_time, compare_window_end_time, emit_signal=True)

        return compare_widget, root_graphics, compare_plot_item, compare_dock


    def add_compare_column_for_all_tracks(self, track_names: Optional[List[str]] = None, compare_window_start_time: Optional[Union[float, datetime, pd.Timestamp]] = None, compare_window_end_time: Optional[Union[float, datetime, pd.Timestamp]] = None, compare_suffix: str = '__compare', enable_time_crosshair: bool = True):
        """Create a compare-column clone for each primary track."""
        if track_names is None:
            track_names = self.get_track_names_for_window_sync_group(window_sync_group='primary')

        created_compare_tracks = {}
        for track_name in track_names:
            compare_track_name = f"{track_name}{compare_suffix}"
            created_compare_tracks[track_name] = self.add_compare_track_view(track_name=track_name, compare_track_name=compare_track_name, compare_window_start_time=compare_window_start_time, compare_window_end_time=compare_window_end_time, enable_time_crosshair=enable_time_crosshair)

        self._rebuild_split_track_dock_groups()
        return created_compare_tracks



    def add_video_track(self, track_name: str, video_datasource: VideoTrackDatasource, dockSize: Tuple[int, int] = (500, 80), sync_mode: SynchronizedPlotMode = SynchronizedPlotMode.TO_GLOBAL_DATA, 
            use_vispy: bool = False, enable_time_crosshair: bool = True, hide_other_track_x_axes: bool = False):
            """Add a video track to the timeline.
            
            This is a convenience method that creates a plot widget and adds the video track.
            
            Args:
                track_name: Unique name for this video track
                video_datasource: VideoTrackDatasource instance
                dockSize: Size of the dock widget (width, height). Default: (500, 80)
                sync_mode: Synchronization mode for the plot. Default: TO_GLOBAL_DATA
                use_vispy: If True, use high-performance vispy renderer instead of pyqtgraph (default: False)
                enable_time_crosshair: If True, show vertical time crosshair overlay on this track (default: True)
                
            Returns:
                Tuple of (widget, root_graphics, plot_item, dock) from add_new_embedded_pyqtgraph_render_plot_widget
            """
            # Create plot widget
            video_widget, root_graphics, plot_item, dock = self.add_new_embedded_pyqtgraph_render_plot_widget(
                name=track_name,
                dockSize=dockSize,
                dockAddLocationOpts=['bottom'],
                sync_mode=sync_mode,
                dock_group_names=[self.SPLIT_PRIMARY_DOCK_GROUP]
            )
            
            # Set vispy renderer flag on datasource if requested
            if use_vispy:
                video_datasource.use_vispy_renderer = True
            
            # Get time range from datasource
            t_start, t_end = video_datasource.total_df_start_end_times
            if t_start == t_end:
                # Default range if no data
                t_start = self.total_data_start_time
                t_end = self.total_data_end_time
            
            # Set plot ranges (convert to datetime then Unix timestamp if reference available)
            if self.reference_datetime is not None:
                dt_start = float_to_datetime(t_start, self.reference_datetime)
                dt_end = float_to_datetime(t_end, self.reference_datetime)
                # Convert datetime to Unix timestamp for PyQtGraph (DateAxisItem expects timestamps but displays as dates)
                unix_start = datetime_to_unix_timestamp(dt_start)
                unix_end = datetime_to_unix_timestamp(dt_end)
                plot_item.setXRange(unix_start, unix_end, padding=0)
                plot_item.setLabel('bottom', 'Time')
            else:
                plot_item.setXRange(t_start, t_end, padding=0)
                plot_item.setLabel('bottom', 'Time', units='s')
            plot_item.setYRange(0, 60, padding=0)
            plot_item.setLabel('left', track_name)
            plot_item.hideAxis('left')
            
            # Ensure TrackRenderingMixin is initialized
            self.TrackRenderingMixin_on_buildUI()
            
            # Add track
            self.add_track(video_datasource, name=track_name, plot_item=plot_item, enable_time_crosshair=enable_time_crosshair)
            
            # Hide x-axis labels for all tracks except the bottom-most one
            if hide_other_track_x_axes:
                self.hide_extra_xaxis_labels_and_axes()
            
            return video_widget, root_graphics, plot_item, dock


    # ==================================================================================================================================================================================================================================================================================== #
    # Timeline Overview Strip Widget                                                                                                                                                                                                                                                       #
    # ==================================================================================================================================================================================================================================================================================== #
    def add_timeline_overview_strip(self, position: str = 'top', row_height_px: int = 20):
        """Add an overview strip: stacked interval previews per primary track and a viewport region.

        The strip view itself does not pan/zoom; dragging or resizing the viewport region updates the main window via ``sigViewportChanged`` (and the region follows ``window_scrolled``).
        Safe to call once; subsequent calls return the existing strip.

        Args:
            position: ``'top'`` (above controls), ``'below_controls'`` (between controls and track docks),
                or ``'bottom'`` (below the main dock area — default for :meth:`TimelineBuilder.build_from_xdf_files`).
            row_height_px: Minimum height per track row in the strip.
        """
        from pypho_timeline.widgets.timeline_overview_strip import TimelineOverviewStrip
        ext = self.ui.get('timeline_overview_strip', None)
        if ext is not None:
            return ext
        strip = TimelineOverviewStrip(reference_datetime=self.reference_datetime, row_height_px=row_height_px, parent=self)
        self.ui.timeline_overview_strip = strip
        if position == 'top':
            self.ui.layout.insertWidget(0, strip)
        elif position == 'below_controls':
            self.ui.layout.insertWidget(1, strip)
        else:
            self.ui.layout.addWidget(strip)
        if not hasattr(self, '_overview_rebuild_timer'):
            self._overview_rebuild_timer = QtCore.QTimer(self)
            self._overview_rebuild_timer.setSingleShot(True)
            self._overview_rebuild_timer.timeout.connect(self._rebuild_timeline_overview_strip)
        if not hasattr(self, '_overview_connected_ds'):
            self._overview_connected_ds = {}

        self.window_scrolled.connect(strip.set_viewport)
        strip.sigViewportChanged.connect(lambda x0, x1: self.apply_active_window_from_plot_x(x0, x1, False))
        self.sigTrackAdded.connect(self._schedule_timeline_overview_strip_rebuild)
        self.sigTrackRemoved.connect(self._schedule_timeline_overview_strip_rebuild)
        self._schedule_timeline_overview_strip_rebuild()
        return strip



    def _schedule_timeline_overview_strip_rebuild(self, *_args):
        if self.ui.get('timeline_overview_strip', None) is None:
            return
        self._overview_rebuild_timer.start(45)



    def _overview_on_datasource_changed(self):
        self._schedule_timeline_overview_strip_rebuild()



    def _resync_timeline_overview_datasource_connections(self):
        if self.ui.get('timeline_overview_strip', None) is None:
            return
        current = {}
        for name in self.get_track_names_for_window_sync_group(window_sync_group='primary'):
            ds = self.track_datasources.get(name, None)
            if ds is not None and hasattr(ds, 'source_data_changed_signal'):
                current[id(ds)] = ds
        for i, ds in list(self._overview_connected_ds.items()):
            if i not in current:
                try:
                    ds.source_data_changed_signal.disconnect(self._overview_on_datasource_changed)
                except TypeError:
                    pass
                del self._overview_connected_ds[i]
        for i, ds in current.items():
            if i not in self._overview_connected_ds:
                ds.source_data_changed_signal.connect(self._overview_on_datasource_changed)
                self._overview_connected_ds[i] = ds



    def _overview_strip_fallback_x_range(self) -> Tuple[float, float]:
        a = self._window_value_to_signal_float(self.total_data_start_time)
        b = self._window_value_to_signal_float(self.total_data_end_time)
        if b < a:
            a, b = b, a
        if b <= a:
            b = a + 1.0
        return (a, b)



    def _rebuild_timeline_overview_strip(self):
        strip = self.ui.get('timeline_overview_strip', None)
        if strip is None:
            return
        self._resync_timeline_overview_datasource_connections()
        names = self.get_track_names_for_window_sync_group(window_sync_group='primary')
        strip.rebuild(names, lambda n: self.track_datasources.get(n), self._overview_strip_fallback_x_range())
        strip.set_viewport(self._window_value_to_signal_float(self.active_window_start_time), self._window_value_to_signal_float(self.active_window_end_time))



    def add_calendar_navigator(self):
        """Adds the calendar navigator to the bottom of the timeline."""
        from pypho_timeline.widgets import TimelineCalendarWidget

        self.ui.calendar = TimelineCalendarWidget()
        self.ui.layout.addWidget(self.ui.calendar)

        # Initialize ranges
        self.ui.calendar.set_total_range(self.total_data_start_time, self.total_data_end_time)
        self.ui.calendar.set_active_window(self.active_window_start_time, self.active_window_end_time)

        # Bidirectional sync
        self.ui.calendar.sigWindowChanged.connect(lambda s, e: self.simulate_window_scroll(s))
        self.window_scrolled.connect(self.ui.calendar.set_active_window)

        return self.ui.calendar


    def add_compare_calendar_navigator(self):
        """Adds a second calendar navigator for the independent compare column."""
        from pypho_timeline.widgets import TimelineCalendarWidget

        self.ui.compare_calendar = TimelineCalendarWidget()
        self.ui.layout.addWidget(self.ui.compare_calendar)

        self.ui.compare_calendar.set_total_range(self.total_data_start_time, self.total_data_end_time)
        self.ui.compare_calendar.set_active_window(self.compare_window_start_time, self.compare_window_end_time)

        self.ui.compare_calendar.sigWindowChanged.connect(lambda s, e: self.simulate_compare_window_scroll(s))
        self.compare_window_scrolled.connect(self.ui.compare_calendar.set_active_window)

        return self.ui.compare_calendar


    # Track Dataframe Tables _____________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________ #
    def add_dataframe_table_track(self, track_name: str, dataframe: pd.DataFrame, time_column: Optional[str] = None, dockSize: Tuple[int, int] = (400, 200), dockAddLocationOpts=None, display_config:CustomDockDisplayConfig=None, sync_mode: SynchronizedPlotMode = SynchronizedPlotMode.TO_GLOBAL_DATA, dock_group_names=None, **kwargs):
        """Add a dataframe table track to the timeline.
        
        Args:
            track_name: Unique name for this track
            dataframe: pandas DataFrame to display
            time_column: Column name to sync with. If None, it will try to guess.
            dockSize: Size of the dock widget. Default: (400, 200)
            sync_mode: Synchronization mode. Default: TO_GLOBAL_DATA
            
        Returns:
            The created DataFrameTableWidget
            
        Example:
            >>> timeline.add_dataframe_table_track("Text Log", timeline.datasources["TextLogger"].df)
        """
        from pypho_timeline.widgets import DataFrameTableWidget
        
        # Create the widget
        table_widget = DataFrameTableWidget(df=dataframe, time_column=time_column, name=track_name, reference_datetime=self.reference_datetime)
        
        if dockAddLocationOpts is None:
            # Try to find the log widget to dock next to it
            log_dock = self.ui.dynamic_docked_widget_container.find_display_dock('log_widget')
            if log_dock:
                dockAddLocationOpts = [log_dock, 'right']
            else:
                dockAddLocationOpts = ['bottom']
            
        # Add to docking system
        self.ui.dynamic_docked_widget_container.add_display_dock(identifier=track_name, widget=table_widget, dockSize=dockSize, dockAddLocationOpts=dockAddLocationOpts, display_config=display_config, **kwargs)
        
        # Connect synchronization
        if sync_mode == SynchronizedPlotMode.TO_GLOBAL_DATA:
            self.window_scrolled.connect(table_widget.on_window_changed)
            # Initial sync
            if hasattr(self, 'spikes_window'):
                start_t = self.spikes_window.active_window_start_time
                end_t = self.spikes_window.active_window_end_time
                if isinstance(start_t, (datetime, pd.Timestamp)):
                    start_t = start_t.timestamp()
                if isinstance(end_t, (datetime, pd.Timestamp)):
                    end_t = end_t.timestamp()
                table_widget.on_window_changed(float(start_t), float(end_t))
            
        return table_widget



    def hide_extra_xaxis_labels_and_axes(self, enable_hide_extra_track_x_axes: bool=True):
        """ Hide x-axis labels for all tracks except the bottom-most one
        """
        # Hide x-axis labels for all tracks except the bottom-most one
        if len(self.ui.matplotlib_view_widgets) > 1:
            # Get all plot items
            all_plot_items = []
            for widget_name, widget in self.ui.matplotlib_view_widgets.items():
                plot_item = widget.getRootPlotItem()
                if plot_item is not None:
                    all_plot_items.append((widget_name, plot_item))
            
            # Hide x-axis for all except the last one (bottom-most)
            if len(all_plot_items) > 1:
                # Hide x-axis for all tracks except the last one
                if enable_hide_extra_track_x_axes:
                    # for widget_name, plot_item in all_plot_items[:-3]: ## bottom 3 tracks
                    for widget_name, plot_item in all_plot_items[:-1]:
                        plot_item.hideAxis('bottom')
                    # Ensure the last track shows its x-axis
                    all_plot_items[-1][1].showAxis('bottom')
                else:
                    ## show all
                    for widget_name, plot_item in all_plot_items:
                        plot_item.showAxis('bottom')



# Re-export stream-to-datasources processing for backward compatibility
from pypho_timeline.rendering.datasources.stream_to_datasources import (
    modality_channels_dict,
    modality_sfreq_dict,
    modality_channels_normalization_mode_dict,
    merge_streams_by_name,
    perform_process_single_xdf_file_all_streams,
    perform_process_all_streams_multi_xdf,
)
