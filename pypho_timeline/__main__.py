"""
Example usage of pyPhoTimeline library.

This demonstrates how to create a timeline with docked tracks that can display
time-synchronized data.
"""

# Compatibility shim for scipy.integrate.simps -> simpson
# simps was deprecated and removed in SciPy 1.12+, replaced with simpson
# This must be imported before any other modules that might use simps
try:
    from scipy.integrate import simps
except ImportError:
    # simps doesn't exist, provide it as an alias to simpson
    try:
        from scipy.integrate import simpson
        import scipy.integrate
        scipy.integrate.simps = simpson
    except ImportError:
        # If simpson also doesn't exist, we can't fix it
        pass

from pathlib import Path
from re import S
import sys
import numpy as np
import pandas as pd
from qtpy import QtWidgets, QtCore
from typing import Dict, List, Tuple, Optional, Callable, Union, Any
import pyphoplacecellanalysis.External.pyqtgraph as pg
from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode
from pypho_timeline.docking.nested_dock_area_widget import NestedDockAreaWidget
from pypho_timeline.docking.specific_dock_widget_mixin import SpecificDockWidgetManipulatingMixin
from pypho_timeline.docking.dock_display_configs import CustomCyclicColorsDockDisplayConfig, NamedColorScheme
from pypho_timeline.core.pyqtgraph_time_synchronized_widget import PyqtgraphTimeSynchronizedWidget
from pypho_timeline.rendering.graphics.interval_rects_item import IntervalRectsItem, IntervalRectsItemData
from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, BaseTrackDatasource, IntervalProvidingTrackDatasource
from pypho_timeline.rendering.datasources.specific.position import PositionTrackDatasource
from pypho_timeline.rendering.datasources.specific.video import VideoTrackDatasource
from pypho_timeline.rendering.detail_renderers import PositionPlotDetailRenderer, VideoThumbnailDetailRenderer, GenericPlotDetailRenderer
from pypho_timeline.rendering.mixins.track_rendering_mixin import TrackRenderingMixin
from pyphocorehelpers.gui.PhoUIContainer import PhoUIContainer
from pyphocorehelpers.DataStructure.general_parameter_containers import RenderPlotsData, RenderPlots
from pyphocorehelpers.DataStructure.RenderPlots.PyqtgraphRenderPlots import PyqtgraphRenderPlots


class SimpleTimelineWidget(TrackRenderingMixin, SpecificDockWidgetManipulatingMixin, QtWidgets.QWidget):
    """A simple example timeline widget that demonstrates pyPhoTimeline usage."""
    
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
    
    def __init__(self, total_start_time=0.0, total_end_time=100.0, window_duration=10.0, window_start_time=30.0, add_example_tracks=True, parent=None):
        super().__init__(parent)
        
        # Store whether to add example tracks
        self._add_example_tracks = add_example_tracks
        
        # Initialize UI container
        self.ui = PhoUIContainer()
        self.ui.matplotlib_view_widgets = {}
        self.ui.connections = {}
        
        # Initialize plots_data and plots for mixins
        self.plots_data = RenderPlotsData(name='SimpleTimelineWidget')
        self.plots = PyqtgraphRenderPlots(name='SimpleTimelineWidget')
        
        # Time window properties
        self.total_data_start_time = total_start_time
        self.total_data_end_time = total_end_time
        self.active_window_start_time = window_start_time
        self.active_window_end_time = window_start_time + window_duration
        
        # Create a simple time window object (mimicking spikes_window)
        class SimpleTimeWindow:
            def __init__(self, start, end, window_dur, window_start):
                self.total_df_start_end_times = (start, end)
                self.active_window_start_time = window_start
                self.active_window_end_time = window_start + window_dur
                self.active_time_window = (window_start, window_start + window_dur)
                self.window_duration = window_dur
                
            def update_window_start_end(self, start_t, end_t):
                self.active_window_start_time = start_t
                self.active_window_end_time = end_t
                self.active_time_window = (start_t, end_t)
        
        self.spikes_window = SimpleTimeWindow(
            total_start_time, total_end_time, window_duration, window_start_time
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
        
        # Add some example tracks (only if requested)
        if self._add_example_tracks:
            self.add_example_tracks()
        
    def add_example_tracks(self):
        """Add example timeline tracks to demonstrate functionality."""
        
        # Track 1: Overview track (shows all data, no sync)
        print("Adding overview track...")
        overview_widget, root_graphics, plot_item, dock = self.add_new_embedded_pyqtgraph_render_plot_widget(
            name='overview',
            dockSize=(500, 100),
            dockAddLocationOpts=['bottom'],
            sync_mode=SynchronizedPlotMode.NO_SYNC
        )
        
        # Set the overview to show the full time range
        plot_item.setXRange(self.total_data_start_time, self.total_data_end_time, padding=0)
        plot_item.setYRange(0, 10, padding=0)
        plot_item.setLabel('bottom', 'Time', units='s')
        plot_item.setLabel('left', 'Overview')
        
        # Add some sample data to the overview
        x_data = np.linspace(self.total_data_start_time, self.total_data_end_time, 100)
        y_data = 5 + 3 * np.sin(2 * np.pi * x_data / 20)
        plot_item.plot(x_data, y_data, pen='y', name='overview_data')
        
        # Track 2: Window-synchronized track (syncs with active window)
        print("Adding window-synchronized track...")
        window_widget, root_graphics2, plot_item2, dock2 = self.add_new_embedded_pyqtgraph_render_plot_widget(
            name='window_track',
            dockSize=(500, 100),
            dockAddLocationOpts=['bottom'],
            sync_mode=SynchronizedPlotMode.TO_WINDOW
        )
        
        # Set initial range to match the active window
        plot_item2.setXRange(self.active_window_start_time, self.active_window_end_time, padding=0)
        plot_item2.setYRange(0, 10, padding=0)
        plot_item2.setLabel('bottom', 'Time', units='s')
        plot_item2.setLabel('left', 'Window Track')
        
        # Add sample data
        x_data2 = np.linspace(self.total_data_start_time, self.total_data_end_time, 200)
        y_data2 = 5 + 2 * np.cos(2 * np.pi * x_data2 / 15)
        plot_item2.plot(x_data2, y_data2, pen='c', name='window_data')
        
        # Track 3: Global data track (one-time sync to global range)
        print("Adding global data track...")
        global_widget, root_graphics3, plot_item3, dock3 = self.add_new_embedded_pyqtgraph_render_plot_widget(
            name='global_track',
            dockSize=(500, 100),
            dockAddLocationOpts=['bottom'],
            sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA
        )
        
        # This will be set automatically by the sync, but we can set it manually too
        plot_item3.setXRange(self.total_data_start_time, self.total_data_end_time, padding=0)
        plot_item3.setYRange(0, 10, padding=0)
        plot_item3.setLabel('bottom', 'Time', units='s')
        plot_item3.setLabel('left', 'Global Track')
        
        # Add sample data
        x_data3 = np.linspace(self.total_data_start_time, self.total_data_end_time, 150)
        y_data3 = 5 + 4 * np.sin(2 * np.pi * x_data3 / 25)
        plot_item3.plot(x_data3, y_data3, pen='m', name='global_data')
        
        # Track 4: Interval rectangles track (shows time intervals as rectangles)
        print("Adding interval rectangles track...")
        intervals_widget, root_graphics4, plot_item4, dock4 = self.add_new_embedded_pyqtgraph_render_plot_widget(
            name='intervals_track',
            dockSize=(500, 80),
            dockAddLocationOpts=['bottom'],
            sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA
        )
        
        # Set range to show full time range
        plot_item4.setXRange(self.total_data_start_time, self.total_data_end_time, padding=0)
        plot_item4.setYRange(0, 5, padding=0)
        plot_item4.setLabel('bottom', 'Time', units='s')
        plot_item4.setLabel('left', 'Intervals')
        plot_item4.hideAxis('left')  # Hide Y-axis for cleaner look
        
        # Create sample interval data
        # Intervals at different vertical positions with different colors
        interval_data = []
        
        # Series 1: Red intervals at y=1
        intervals_1 = [
            (10.0, 1.0, 0.5, 5.0, 0.8),  # (start, y_offset, duration, height, alpha)
            (15.0, 1.0, 0.5, 5.0, 0.8),
            (20.0, 1.0, 0.5, 5.0, 0.8),
            (35.0, 1.0, 0.5, 5.0, 0.8),
            (50.0, 1.0, 0.5, 5.0, 0.8),
            (65.0, 1.0, 0.5, 5.0, 0.8),
            (80.0, 1.0, 0.5, 5.0, 0.8),
        ]
        
        # Series 2: Green intervals at y=2
        intervals_2 = [
            (12.0, 2.0, 1.0, 4.0, 0.7),
            (25.0, 2.0, 1.0, 4.0, 0.7),
            (40.0, 2.0, 1.0, 4.0, 0.7),
            (55.0, 2.0, 1.0, 4.0, 0.7),
            (70.0, 2.0, 1.0, 4.0, 0.7),
        ]
        
        # Series 3: Blue intervals at y=3
        intervals_3 = [
            (5.0, 3.0, 2.0, 3.0, 0.6),
            (30.0, 3.0, 2.0, 3.0, 0.6),
            (60.0, 3.0, 2.0, 3.0, 0.6),
            (85.0, 3.0, 2.0, 3.0, 0.6),
        ]
        
        # Create pens and brushes for each series
        red_color = pg.mkColor('r')
        red_color.setAlphaF(0.8)
        red_pen = pg.mkPen(red_color, width=2)
        red_brush = pg.mkBrush(red_color)
        
        green_color = pg.mkColor('g')
        green_color.setAlphaF(0.7)
        green_pen = pg.mkPen(green_color, width=2)
        green_brush = pg.mkBrush(green_color)
        
        blue_color = pg.mkColor('b')
        blue_color.setAlphaF(0.6)
        blue_pen = pg.mkPen(blue_color, width=2)
        blue_brush = pg.mkBrush(blue_color)
        
        # Add intervals from series 1 (red)
        for start, y_offset, duration, height, alpha in intervals_1:
            interval_data.append(IntervalRectsItemData(
                start_t=start,
                series_vertical_offset=y_offset,
                duration_t=duration,
                series_height=height,
                pen=red_pen,
                brush=red_brush,
                label=f"Event at {start:.1f}s"
            ))
        
        # Add intervals from series 2 (green)
        for start, y_offset, duration, height, alpha in intervals_2:
            interval_data.append(IntervalRectsItemData(
                start_t=start,
                series_vertical_offset=y_offset,
                duration_t=duration,
                series_height=height,
                pen=green_pen,
                brush=green_brush,
                label=f"Interval at {start:.1f}s"
            ))
        
        # Add intervals from series 3 (blue)
        for start, y_offset, duration, height, alpha in intervals_3:
            interval_data.append(IntervalRectsItemData(
                start_t=start,
                series_vertical_offset=y_offset,
                duration_t=duration,
                series_height=height,
                pen=blue_pen,
                brush=blue_brush,
                label=f"Long interval at {start:.1f}s"
            ))
        
        # Create the IntervalRectsItem and add it to the plot
        interval_rects_item = IntervalRectsItem(interval_data)
        plot_item4.addItem(interval_rects_item)
        
        # Store reference for potential updates
        self.ui.intervals_item = interval_rects_item
        
        # Track 5: Position track with async detail loading
        print("Adding position track with async detail loading...")
        position_widget, root_graphics5, plot_item5, dock5 = self.add_new_embedded_pyqtgraph_render_plot_widget(
            name='position_track',
            dockSize=(500, 100),
            dockAddLocationOpts=['bottom'],
            sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA
        )
        
        plot_item5.setXRange(self.total_data_start_time, self.total_data_end_time, padding=0)
        plot_item5.setYRange(-5, 5, padding=0)
        plot_item5.setLabel('bottom', 'Time', units='s')
        plot_item5.setLabel('left', 'Position Track')
        
        # Create sample position data
        position_times = np.linspace(self.total_data_start_time, self.total_data_end_time, 1000)
        position_x = 2 * np.sin(2 * np.pi * position_times / 20)
        position_y = 2 * np.cos(2 * np.pi * position_times / 20)
        position_df = pd.DataFrame({'t': position_times, 'x': position_x, 'y': position_y})
        
        # Create intervals (every 10 seconds)
        interval_starts = np.arange(self.total_data_start_time, self.total_data_end_time, 10.0)
        intervals_df = pd.DataFrame({
            't_start': interval_starts,
            't_duration': [10.0] * len(interval_starts)
        })
        
        # Create position track datasource
        position_datasource = PositionTrackDatasource(position_df, intervals_df)
        
        # Add track (this will initialize track rendering)
        self.TrackRenderingMixin_on_buildUI()
        self.add_track(position_datasource, name='position_track', plot_item=plot_item5)
        
        # Track 6: Video track with async detail loading
        print("Adding video track with async detail loading...")
        video_widget, root_graphics6, plot_item6, dock6 = self.add_new_embedded_pyqtgraph_render_plot_widget(
            name='video_track',
            dockSize=(500, 80),
            dockAddLocationOpts=['bottom'],
            sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA
        )
        
        plot_item6.setXRange(self.total_data_start_time, self.total_data_end_time, padding=0)
        plot_item6.setYRange(0, 60, padding=0)
        plot_item6.setLabel('bottom', 'Time', units='s')
        plot_item6.setLabel('left', 'Video Track')
        plot_item6.hideAxis('left')
        
        # Create video intervals
        video_intervals_df = pd.DataFrame({
            't_start': [15.0, 35.0, 55.0, 75.0],
            't_duration': [5.0, 5.0, 5.0, 5.0],
            'video_path': ['video1.mp4', 'video2.mp4', 'video3.mp4', 'video4.mp4']
        })
        
        # Create video track datasource
        video_datasource = VideoTrackDatasource(video_intervals_df)
        
        # Add track
        self.add_track(video_datasource, name='video_track', plot_item=plot_item6)
        
    def simulate_window_scroll(self, new_start_time):
        """Simulate scrolling the time window (for demonstration)."""
        new_end_time = new_start_time + (self.active_window_end_time - self.active_window_start_time)
        self.active_window_start_time = new_start_time
        self.active_window_end_time = new_end_time
        self.spikes_window.update_window_start_end(new_start_time, new_end_time)
        
        # Emit the signal to update synchronized tracks
        self.window_scrolled.emit(new_start_time, new_end_time)
        print(f"Window scrolled to: {new_start_time:.2f} - {new_end_time:.2f}")



modality_channels_dict = {'EEG': ['AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4'],
                        'MOTION': ['AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'GyroZ'],
                        'GENERIC': ['AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4'],
}

modality_sfreq_dict = {'EEG': 128, 'MOTION': 16,
                        'GENERIC': 128, 
}


def perform_process_all_streams(streams):
    all_streams = {}
    all_streams_datasources = {}
    for i, s in enumerate(streams):
        stream_name = s['info']['name'][0]
        stream_type = s['info']['type'][0]
        # if ('type' in s['info']):
        #     a_type = s['info']['type'][0]
        #     all_streams[a_type] = s
        timestamps = s['time_stamps'] ## get stream data
        time_series = s['time_series'] ## get stream data
        
        n_channels: int = int(s['info']['channel_count'][0])
        print(f"Stream {i}: {stream_name}, channels: {n_channels}, samples: {len(timestamps)}")

        # Create a single interval representing the entire stream recording
        if len(timestamps) == 0:
            continue
        
        stream_start = float(timestamps[0])
        stream_end = float(timestamps[-1])
        stream_duration = stream_end - stream_start
        
        # Create interval DataFrame with proper structure
        intervals_df = pd.DataFrame({
            't_start': [stream_start],
            't_duration': [stream_duration],
            't_end': [stream_end]
        })

        # Add visualization columns
        intervals_df['series_vertical_offset'] = (1.0) * float(i)
        intervals_df['series_height'] = 0.9
        
        # Create pens and brushes
        color = pg.mkColor('blue')
        color.setAlphaF(0.3)
        pen = pg.mkPen(color, width=1)
        brush = pg.mkBrush(color)
        intervals_df['pen'] = [pen]
        intervals_df['brush'] = [brush]


        all_streams[stream_name] = intervals_df

        # Create datasource
        if 'Motion' in stream_name:
            n_t_stamps, n_columns = np.shape(time_series)
            assert n_channels == n_columns, f"n_channels: {n_channels} != n_columns: {n_columns}"
            assert len(timestamps) == n_t_stamps, f"len(timestamps): {len(timestamps)} != n_t_stamps: {n_t_stamps}"
            time_series_df = pd.DataFrame(time_series, columns=modality_channels_dict['MOTION']) # ['AccelX', 'AccelY', 'AccelZ', 'GyroX', 'GyroY', 'GyroZ']
            time_series_df['t'] = timestamps
            datasource = PositionTrackDatasource(position_df=time_series_df, intervals_df=intervals_df)
            datasource.custom_datasource_name = f"MOTION_{stream_name}"
        # elif 'Epoc X' in stream_name:
        #     ## TODO: Implement EEG datasource:
        #     datasource = BaseTrackDatasource()
        #     datasource.custom_datasource_name = f"EEG_{stream_name}"
        else:
            datasource = None
            print(f'unknown stream type -- cannot build datasource for stream: stream_name: "{stream_name}", stream_type: "{stream_type}"')

        all_streams_datasources[stream_name] = datasource
    ## END for i, s in enumerate(streams)...

    return all_streams, all_streams_datasources



# ==================================================================================================================================================================================================================================================================================== #
# Testing Functions                                                                                                                                                                                                                                                                    #
# ==================================================================================================================================================================================================================================================================================== #

def main():
    """Main function demonstrating pyPhoTimeline usage."""
    print("=" * 60)
    print("pyPhoTimeline Example")
    print("=" * 60)
    
    # Create Qt application
    app = pg.mkQApp("pyPhoTimelineExample")
    
    # Create the timeline widget
    timeline = SimpleTimelineWidget(
        total_start_time=0.0,
        total_end_time=100.0,
        window_duration=15.0,
        window_start_time=30.0
    )
    
    # Set window properties
    timeline.setWindowTitle("pyPhoTimeline Example - Timeline with Docked Tracks")
    timeline.resize(800, 600)
    timeline.show()
    
    # Demonstrate programmatic window scrolling after a delay
    def scroll_demo():
        """Demonstrate scrolling the window."""
        print("\nDemonstrating window scrolling...")
        # Scroll forward
        timeline.simulate_window_scroll(40.0)
        QtCore.QTimer.singleShot(2000, lambda: timeline.simulate_window_scroll(50.0))
        QtCore.QTimer.singleShot(4000, lambda: timeline.simulate_window_scroll(60.0))
    
    # Start the scroll demo after 1 second
    QtCore.QTimer.singleShot(1000, scroll_demo)
    
    print("\nTimeline widget created with 6 example tracks:")
    print("  1. Overview track (NO_SYNC) - shows full time range")
    print("  2. Window track (TO_WINDOW) - syncs with active window")
    print("  3. Global track (TO_GLOBAL_DATA) - one-time sync to global range")
    print("  4. Intervals track (TO_GLOBAL_DATA) - displays time intervals as colored rectangles")
    print("  5. Position track (TO_GLOBAL_DATA) - async detail loading with position plots")
    print("  6. Video track (TO_GLOBAL_DATA) - async detail loading with video thumbnails")
    print("\nThe window will automatically scroll to demonstrate synchronization.")
    print("Scroll the position and video tracks to see detail data load asynchronously.")
    print("Hover over the interval rectangles to see tooltips.")
    print("Close the window to exit.\n")
    
    # Run the application
    sys.exit(app.exec_())

# def main_all_eeg_modalities_from_xdf_file_example(xdf_file_path: Path):
#     """Main function demonstrating pyPhoTimeline usage with all EEG modalities from an XDF file."""
#     print("=" * 60)
#     print(f"pyPhoTimeline - Load all EEG (or LSL) modalities from XDF: {xdf_file_path}")
#     print("=" * 60)

#     # Create Qt application
#     app = pg.mkQApp("pyPhoTimelineXDFExample")

#     # --- 1. Load the XDF file (using pyxdf) ---
#     import pyxdf

#     print(f"Loading XDF file: {xdf_file_path} ...")
#     streams, file_header = pyxdf.load_xdf(str(xdf_file_path))
#     print(f"Streams loaded: {[s['info']['name'][0] for s in streams]}")
#     print(f"File Header: {file_header}")

#     # --- 2. Inspect and extract EEG/continuous data streams ---
#     eeg_streams = []
#     for s in streams:
#         if 'type' in s['info'] and 'EEG' in s['info']['type'][0]:
#             eeg_streams.append(s)


#     all_streams = {}
#     for s in streams:
#         if ('type' in s['info']):
#             a_type = s['info']['type'][0]
#             all_streams[a_type] = s


#     if not eeg_streams:
#         print("No EEG streams found in XDF file.")
#         return

#     print(f"Found {len(eeg_streams)} EEG streams: {[s['info']['name'][0] for s in eeg_streams]}")

#     # --- 3. Build interval DataFrame for each EEG stream ---
#     eeg_datasources = []
#     for i, s in enumerate(eeg_streams):
#         timestamps = s['time_stamps']
#         stream_name = s['info']['name'][0]
#         n_channels = int(s['info']['channel_count'][0])
#         print(f"Stream {i}: {stream_name}, channels: {n_channels}, samples: {len(timestamps)}")

#         # Create a single interval representing the entire stream recording
#         if len(timestamps) == 0:
#             continue
        
#         stream_start = float(timestamps[0])
#         stream_end = float(timestamps[-1])
#         stream_duration = stream_end - stream_start
        
#         # Create interval DataFrame with proper structure
#         intervals_df = pd.DataFrame({
#             't_start': [stream_start],
#             't_duration': [stream_duration],
#             't_end': [stream_end]
#         })
        
#         # Add visualization columns
#         intervals_df['series_vertical_offset'] = 0.0
#         intervals_df['series_height'] = 1.0
        
#         # Create pens and brushes
#         color = pg.mkColor('blue')
#         color.setAlphaF(0.3)
#         pen = pg.mkPen(color, width=1)
#         brush = pg.mkBrush(color)
#         intervals_df['pen'] = [pen]
#         intervals_df['brush'] = [brush]
        
#         # Create datasource
#         datasource = PositionTrackDatasource(position_df=None, intervals_df=intervals_df)
#         datasource.custom_datasource_name = f"EEG_{stream_name}"
#         eeg_datasources.append(datasource)





#     # --- 4. Create the timeline widget and add EEG tracks ---
#     timeline = SimpleTimelineWidget(
#         total_start_time=min([ds.total_df_start_end_times[0] for ds in eeg_datasources]),
#         total_end_time=max([ds.total_df_start_end_times[1] for ds in eeg_datasources]),
#         window_duration=10.0,
#         window_start_time=min([ds.total_df_start_end_times[0] for ds in eeg_datasources]),
#         add_example_tracks=False  # Don't add example tracks for XDF data
#     )

#     # Create plot widgets for each EEG stream and add tracks
#     for datasource in eeg_datasources:
#         # Create a plot widget for this track
#         track_widget, root_graphics, plot_item, dock = timeline.add_new_embedded_pyqtgraph_render_plot_widget(
#             name=datasource.custom_datasource_name,
#             dockSize=(500, 80),
#             dockAddLocationOpts=['bottom'],
#             sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA
#         )
        
#         # Set the plot to show the full time range
#         plot_item.setXRange(
#             timeline.total_data_start_time, 
#             timeline.total_data_end_time, 
#             padding=0
#         )
#         plot_item.setYRange(0, 1, padding=0)
#         plot_item.setLabel('bottom', 'Time', units='s')
#         plot_item.setLabel('left', datasource.custom_datasource_name)
#         plot_item.hideAxis('left')  # Hide Y-axis for cleaner look
        
#         # Add the track to the plot
#         timeline.add_track(
#             datasource,
#             name=datasource.custom_datasource_name,
#             plot_item=plot_item
#         )

#     timeline.setWindowTitle(f"pyPhoTimeline - EEG Modalities from XDF: {xdf_file_path.name}")
#     timeline.resize(1000, 800)
#     timeline.show()

#     print("\nTimeline widget created with EEG tracks from XDF:")
#     for ds in eeg_datasources:
#         print(f"  - {ds.custom_datasource_name}, time: {ds.total_df_start_end_times}")

#     print("\nScroll on the timeline to see loaded EEG intervals for each stream.")
#     print("Close the window to exit.\n")

#     sys.exit(app.exec_())


def main_all_modalities_from_xdf_file_example(xdf_file_path: Path):
    """Main function demonstrating pyPhoTimeline usage with all EEG modalities from an XDF file."""
    print("=" * 60)
    print(f"pyPhoTimeline - Load all modalities from XDF: {xdf_file_path}")
    print("=" * 60)

    # Create Qt application
    app = pg.mkQApp("pyPhoTimelineXDFExample")

    # --- 1. Load the XDF file (using pyxdf) ---
    import pyxdf

    print(f"Loading XDF file: {xdf_file_path} ...")
    streams, file_header = pyxdf.load_xdf(str(xdf_file_path))
    print(f"Streams loaded: {[s['info']['name'][0] for s in streams]}")
    print(f"File Header: {file_header}")

    # --- 2. Inspect and extract EEG/continuous data streams ---
    all_streams, all_streams_datasources = perform_process_all_streams(streams=streams)

    if not all_streams:
        print("No streams found in XDF file.")
        return

    print(f"Found {len(all_streams)} streams: {[a_name for a_name in list(all_streams_datasources.keys())]}")

    
    active_datasources_dict = {k:v for k, v in all_streams_datasources.items() if v is not None}
    active_datasource_list = list(active_datasources_dict.values())
    print(f"\tbuild active_datasources: {len(active_datasource_list)} datasources.")

    # --- 4. Create the timeline widget and add EEG tracks ---
    timeline = SimpleTimelineWidget(
        total_start_time=min([ds.total_df_start_end_times[0] for ds in active_datasource_list]),
        total_end_time=max([ds.total_df_start_end_times[1] for ds in active_datasource_list]),
        window_duration=10.0,
        window_start_time=min([ds.total_df_start_end_times[0] for ds in active_datasource_list]),
        add_example_tracks=False  # Don't add example tracks for XDF data
    )

    # Create plot widgets for each EEG stream and add tracks
    for datasource in active_datasource_list:
        # Create a plot widget for this track
        track_widget, root_graphics, plot_item, dock = timeline.add_new_embedded_pyqtgraph_render_plot_widget(
            name=datasource.custom_datasource_name,
            dockSize=(500, 80),
            dockAddLocationOpts=['bottom'],
            sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA
        )
        
        # Set the plot to show the full time range
        plot_item.setXRange(
            timeline.total_data_start_time, 
            timeline.total_data_end_time, 
            padding=0
        )
        plot_item.setYRange(0, 1, padding=0)
        plot_item.setLabel('bottom', 'Time', units='s')
        plot_item.setLabel('left', datasource.custom_datasource_name)
        plot_item.hideAxis('left')  # Hide Y-axis for cleaner look
        
        # Add the track to the plot
        timeline.add_track(
            datasource,
            name=datasource.custom_datasource_name,
            plot_item=plot_item
        )

    timeline.setWindowTitle(f"pyPhoTimeline - ALL Modalities from XDF: {xdf_file_path.name}")
    timeline.resize(1000, 800)
    timeline.show()

    print("\nTimeline widget created with tracks from XDF:")
    for ds in active_datasource_list:
        print(f"  - {ds.custom_datasource_name}, time: {ds.total_df_start_end_times}")

    print("\nScroll on the timeline to see loaded EEG intervals for each stream.")
    print("Close the window to exit.\n")


    sys.exit(app.exec_())




if __name__ == "__main__":
    # To demo: supply a path to a valid XDF file containing EEG/LFP/continuous apparatus streams:
    # e.g. replace with your local file: demo_xdf_path = Path("/path/to/your/example.xdf")
    # Or, use main() for standard demo
    import argparse

    parser = argparse.ArgumentParser(description="Run pyPhoTimeline EEG XDF example.")
    parser.add_argument('--xdf', type=str, help='Path to XDF file to visualize EEG tracks.')
    args = parser.parse_args()

    if args.xdf is not None:
        demo_xdf_path = Path(args.xdf)

    else:
        demo_xdf_path = Path(r"E:/Dropbox (Personal)/Databases/UnparsedData/LabRecorderStudies/sub-P001/LabRecorder_Apogee_2025-10-21T051157.400Z_eeg.xdf").resolve()
        assert demo_xdf_path.exists()


    if not demo_xdf_path.exists():
        print(f"ERROR: XDF file does not exist: {demo_xdf_path}")
        sys.exit(1)
    else:
        print(f'loading xdf file: "{demo_xdf_path.as_posix()}"')
    # main_all_eeg_modalities_from_xdf_file_example(demo_xdf_path)
    main_all_modalities_from_xdf_file_example(demo_xdf_path)
    
