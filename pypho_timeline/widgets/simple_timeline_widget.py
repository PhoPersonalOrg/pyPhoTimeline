"""
Simple timeline widget for pyPhoTimeline library.

This module provides a simple example timeline widget that demonstrates pyPhoTimeline usage,
along with utility functions for processing stream data.
"""

import numpy as np
import pandas as pd
from typing import Tuple, List, Dict, Optional, Union
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

    """
    
    # Signal emitted when the time window changes
    window_scrolled = QtCore.Signal(float, float)
    compare_window_scrolled = QtCore.Signal(float, float)
    
    @property
    def interval_rendering_plots(self):
        """Return list of plots for interval rendering."""
        # Return all plot items from matplotlib_view_widgets
        plots = []
        for widget in self.ui.matplotlib_view_widgets.values():
            plots.append(widget.getRootPlotItem())
        return plots
    

    def __init__(self, total_start_time: Union[float, datetime, pd.Timestamp] = 0.0, 
                 total_end_time: Union[float, datetime, pd.Timestamp] = 100.0, 
                 window_duration: Union[float, timedelta] = 10.0, 
                 window_start_time: Union[float, datetime, pd.Timestamp] = 30.0, 
                 add_example_tracks=False, 
                 reference_datetime: Optional[datetime] = None, 
                 parent=None):
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
        self.compare_window_start_time = self.active_window_start_time
        self.compare_window_end_time = self.active_window_end_time
        self._is_updating_compare_window = False
        self.ui.compare_track_names = set()
        self.ui.compare_track_master_name = None
        
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
        self.ui.controls_layout.addStretch(1)
        self.ui.split_all_tracks_button = QtWidgets.QPushButton("Split All Tracks")
        self.ui.split_all_tracks_button.setToolTip("Create an independent compare column for every track.")
        self.ui.split_all_tracks_button.clicked.connect(self._on_split_all_tracks_clicked)
        self.ui.controls_layout.addWidget(self.ui.split_all_tracks_button)
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


    def _on_split_all_tracks_clicked(self):
        """Split every primary track into the compare column."""
        self.add_compare_column_for_all_tracks()
        

    def simulate_window_scroll(self, new_start_time: Union[float, datetime, pd.Timestamp]):
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
        
        self.window_scrolled.emit(emit_start, emit_end)
        
        if isinstance(new_start_time, (datetime, pd.Timestamp)):
            print(f"Window scrolled to: {new_start_time} - {new_end_time}")
        else:
            print(f"Window scrolled to: {new_start_time:.2f} - {new_end_time:.2f}")


    def _window_value_to_signal_float(self, value: Union[float, datetime, pd.Timestamp]) -> float:
        """Convert a stored window boundary value to the float expected by Qt signals."""
        if isinstance(value, (datetime, pd.Timestamp)):
            return value.timestamp() if hasattr(value, 'timestamp') else pd.Timestamp(value).timestamp()
        return float(value)


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

        compare_widget, root_graphics, compare_plot_item, compare_dock = self.add_new_embedded_pyqtgraph_render_plot_widget(name=compare_track_name, dockSize=dockSize, dockAddLocationOpts=dock_add_location_opts, sync_mode=SynchronizedPlotMode.NO_SYNC)
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
                sync_mode=sync_mode
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
                if len(self.ui.matplotlib_view_widgets) > 1:
                    # Get all plot items
                    all_plot_items = []
                    for widget_name, widget in self.ui.matplotlib_view_widgets.items():
                        plot_item_widget = widget.getRootPlotItem()
                        if plot_item_widget is not None:
                            all_plot_items.append((widget_name, plot_item_widget))
                    
                    # Hide x-axis for all except the last one (bottom-most)
                    if len(all_plot_items) > 1:
                        # Hide x-axis for all tracks except the last one
                        for widget_name, plot_item_widget in all_plot_items[:-1]:
                            plot_item_widget.hideAxis('bottom')
                        # Ensure the last track shows its x-axis
                        all_plot_items[-1][1].showAxis('bottom')
            
            return video_widget, root_graphics, plot_item, dock


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


    def add_dataframe_table_track(self, track_name: str, dataframe: pd.DataFrame, time_column: Optional[str] = None, dockSize: Tuple[int, int] = (400, 200), sync_mode: SynchronizedPlotMode = SynchronizedPlotMode.TO_GLOBAL_DATA):
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
        
        # Try to find the log widget to dock next to it
        log_dock = self.ui.dynamic_docked_widget_container.find_display_dock('log_widget')
        if log_dock:
            dock_opts = [log_dock, 'right']
        else:
            dock_opts = ['bottom']
            
        # Add to docking system
        self.ui.dynamic_docked_widget_container.add_display_dock(identifier=track_name, widget=table_widget, dockSize=dockSize, dockAddLocationOpts=dock_opts)
        
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


# Re-export stream-to-datasources processing for backward compatibility
from pypho_timeline.rendering.datasources.stream_to_datasources import (
    modality_channels_dict,
    modality_sfreq_dict,
    modality_channels_normalization_mode_dict,
    merge_streams_by_name,
    perform_process_single_xdf_file_all_streams,
    perform_process_all_streams_multi_xdf,
)
