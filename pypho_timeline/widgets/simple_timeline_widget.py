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
        super().__init__(parent)
        
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
        
        # Create the dock area container
        self.ui.dynamic_docked_widget_container = NestedDockAreaWidget()
        self.ui.dynamic_docked_widget_container.setObjectName("dynamic_docked_widget_container")
        
        # Add to layout
        self.ui.layout.addWidget(self.ui.dynamic_docked_widget_container)

        self.TrackRenderingMixin_on_buildUI()
        
        # Add some example tracks (only if requested)
        if self._add_example_tracks:
            self.add_example_tracks()
        

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



    def add_video_track(self, track_name: str, video_datasource: VideoTrackDatasource, dockSize: Tuple[int, int] = (500, 80), sync_mode: SynchronizedPlotMode = SynchronizedPlotMode.TO_GLOBAL_DATA, use_vispy: bool = False, enable_time_crosshair: bool = True):
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
