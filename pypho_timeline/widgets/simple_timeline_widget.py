"""
Simple timeline widget for pyPhoTimeline library.

This module provides a simple example timeline widget that demonstrates pyPhoTimeline usage,
along with utility functions for processing stream data.
"""

import numpy as np
import pandas as pd
from qtpy import QtWidgets, QtCore
import pyphoplacecellanalysis.External.pyqtgraph as pg
from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode
from pypho_timeline.docking.nested_dock_area_widget import NestedDockAreaWidget
from pypho_timeline.docking.specific_dock_widget_mixin import SpecificDockWidgetManipulatingMixin
from pypho_timeline.rendering.detail_renderers import DataframePlotDetailRenderer
from pypho_timeline.rendering.graphics.interval_rects_item import IntervalRectsItem, IntervalRectsItemData
from pypho_timeline.rendering.datasources.track_datasource import IntervalProvidingTrackDatasource
from pypho_timeline.rendering.datasources.specific import MotionTrackDatasource, PositionTrackDatasource, VideoTrackDatasource
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
        self.active_window_end_time = window_start + window_dur
        self.active_time_window = (window_start, window_start + window_dur)
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
    

    def __init__(self, total_start_time=0.0, total_end_time=100.0, window_duration=10.0, window_start_time=30.0, add_example_tracks=False, parent=None):
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
        
        # Time window properties
        self.total_data_start_time = total_start_time
        self.total_data_end_time = total_end_time
        self.active_window_start_time = window_start_time
        self.active_window_end_time = window_start_time + window_duration
        
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




# ==================================================================================================================================================================================================================================================================================== #
# Begin Testing/Building                                                                                                                                                                                                                                                               #
# ==================================================================================================================================================================================================================================================================================== #
modality_channels_dict = {'EEG': ['AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4'],
                        'MOTION': ['AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'GyroZ'],
                        'GENERIC': ['AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4'],
                        'LOG': ['msg'],
}

modality_sfreq_dict = {'EEG': 128, 'MOTION': 16,
                        'GENERIC': 128, 'LOG': -1,
}

## Default modality normalization modes:
modality_channels_normalization_mode_dict = {
    'EEG': {
        ('AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4'): ChannelNormalizationMode.INDIVIDUAL,
    },
    'MOTION': {
        ('AccX', 'AccY', 'AccZ'): ChannelNormalizationMode.GROUPMINMAXRANGE,
        ('GyroX', 'GyroY', 'GyroZ'): ChannelNormalizationMode.GROUPMINMAXRANGE,
    },
    'GENERIC': {
        ('AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4'): ChannelNormalizationMode.GROUPMINMAXRANGE,
    },
    'LOG': {
        ('msg',): ChannelNormalizationMode.NONE,
    },
}



def perform_process_all_streams(streams):
    """ main function! Processes streams to build datasources, and thus tracks.

    """
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
        has_valid_intervals: bool = (intervals_df is not None) and (len(intervals_df) > 0)

        # Create datasource
        if (stream_type.upper() in ['SIGNAL', 'RAW']) and ('Motion' in stream_name):
            assert has_valid_intervals
            n_t_stamps, n_columns = np.shape(time_series)
            assert n_channels == n_columns, f"n_channels: {n_channels} != n_columns: {n_columns}"
            assert len(timestamps) == n_t_stamps, f"len(timestamps): {len(timestamps)} != n_t_stamps: {n_t_stamps}"
            time_series_df = pd.DataFrame(time_series, columns=modality_channels_dict['MOTION']) # ['AccelX', 'AccelY', 'AccelZ', 'GyroX', 'GyroY', 'GyroZ']
            time_series_df['t'] = timestamps
            # High-frequency motion data: use 1000 points/second for downsampling
            motion_norm_dict = modality_channels_normalization_mode_dict.get('MOTION')
            datasource = MotionTrackDatasource(
                motion_df=time_series_df,
                intervals_df=intervals_df,
                custom_datasource_name=f"MOTION_{stream_name}",
                max_points_per_second=10.0,
                enable_downsampling=True,
                fallback_normalization_mode=ChannelNormalizationMode.GROUPMINMAXRANGE,
                normalization_mode_dict=motion_norm_dict,
            )
            datasource.custom_datasource_name = f"MOTION_{stream_name}"

        elif (stream_type.upper() in ['RAW']) and (' eQuality' in stream_name): #  and ('Epoc X' in stream_name)
            ## TODO: Implement EEG datasource:
            assert has_valid_intervals

            from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import DataframePlotDetailRenderer
            channel_names = modality_channels_dict['EEG']
            eeg_norm_dict = modality_channels_normalization_mode_dict.get('EEG')

            a_detail_renderer: DataframePlotDetailRenderer = DataframePlotDetailRenderer(
                channel_names=channel_names,
                fallback_normalization_mode=ChannelNormalizationMode.INDIVIDUAL,
                normalization_mode_dict=eeg_norm_dict,
            )
            
            n_t_stamps, n_columns = np.shape(time_series)
            assert n_channels == n_columns, f"n_channels: {n_channels} != n_columns: {n_columns}"
            assert len(timestamps) == n_t_stamps, f"len(timestamps): {len(timestamps)} != n_t_stamps: {n_t_stamps}"
            time_series_df = pd.DataFrame(time_series, columns=channel_names) # ['AccelX', 'AccelY', 'AccelZ', 'GyroX', 'GyroY', 'GyroZ']
            time_series_df['t'] = timestamps
            # High-frequency EEG data: use 1000 points/second for downsampling
            # datasource = EEGTrackDatasource(intervals_df=intervals_df, eeg_df=time_series_df, custom_datasource_name=f"EEG_{stream_name}")
            datasource = IntervalProvidingTrackDatasource(intervals_df=intervals_df, detailed_df=time_series_df, custom_datasource_name=f"EEGQ_{stream_name}", detail_renderer=a_detail_renderer, max_points_per_second=2.0, enable_downsampling=True)
            # datasource.custom_datasource_name = f"EEG_{stream_name}"

        elif (stream_type.upper() == 'EEG'): #  and ('Epoc X' in stream_name)
            ## TODO: Implement EEG datasource:
            n_t_stamps, n_columns = np.shape(time_series)
            assert n_channels == n_columns, f"n_channels: {n_channels} != n_columns: {n_columns}"
            assert len(timestamps) == n_t_stamps, f"len(timestamps): {len(timestamps)} != n_t_stamps: {n_t_stamps}"
            time_series_df = pd.DataFrame(time_series, columns=modality_channels_dict['EEG']) # ['AccelX', 'AccelY', 'AccelZ', 'GyroX', 'GyroY', 'GyroZ']
            time_series_df['t'] = timestamps
            # High-frequency EEG data: use 1000 points/second for downsampling
            eeg_norm_dict = modality_channels_normalization_mode_dict.get('EEG')
            datasource = EEGTrackDatasource(
                intervals_df=intervals_df,
                eeg_df=time_series_df,
                custom_datasource_name=f"EEG_{stream_name}",
                max_points_per_second=10.0,
                enable_downsampling=True,
                fallback_normalization_mode=ChannelNormalizationMode.INDIVIDUAL,
                normalization_mode_dict=eeg_norm_dict,
            )
            # datasource = IntervalProvidingTrackDatasource(intervals_df=intervals_df, detailed_df=None, custom_datasource_name=f"EEG_{stream_name}")
            # datasource.custom_datasource_name = f"EEG_{stream_name}"

        elif (stream_type.upper() in ['MARKERS']) and (stream_name in ['EventBoard', 'TextLogger']): #  and ('Epoc X' in stream_name)
            ## Text log datasource:
            assert has_valid_intervals
            from pypho_timeline.rendering.detail_renderers.log_text_plot_renderer import LogTextDataFramePlotDetailRenderer
        

            channel_names = modality_channels_dict['LOG']

            a_detail_renderer: LogTextDataFramePlotDetailRenderer = LogTextDataFramePlotDetailRenderer(text_color='white', text_size=10, channel_names=channel_names)
            
            n_t_stamps, n_columns = np.shape(time_series)
            assert n_channels == n_columns, f"n_channels: {n_channels} != n_columns: {n_columns}"
            assert len(timestamps) == n_t_stamps, f"len(timestamps): {len(timestamps)} != n_t_stamps: {n_t_stamps}"
            time_series_df = pd.DataFrame(time_series, columns=channel_names) # ['AccelX', 'AccelY', 'AccelZ', 'GyroX', 'GyroY', 'GyroZ']
            time_series_df['t'] = timestamps
            # High-frequency EEG data: use 1000 points/second for downsampling
            # datasource = EEGTrackDatasource(intervals_df=intervals_df, eeg_df=time_series_df, custom_datasource_name=f"EEG_{stream_name}")
            datasource = IntervalProvidingTrackDatasource(intervals_df=intervals_df, detailed_df=time_series_df, custom_datasource_name=f"LOG_{stream_name}", detail_renderer=a_detail_renderer, enable_downsampling=False)


        elif has_valid_intervals:
            # Unknown stream type: disable downsampling by default
            datasource = IntervalProvidingTrackDatasource(intervals_df=intervals_df, detailed_df=None, custom_datasource_name=f"UNKNOWN_{stream_name}", max_points_per_second=1.0, enable_downsampling=False)
            datasource.custom_datasource_name = f"UNKNOWN_{stream_name}"
            print(f'WARN: unspecific stream type -- cannot build datasource for stream: stream_name: "{stream_name}", stream_type: "{stream_type}"')

        else:
            datasource = None
            print(f'WARN: NO intervals_df!! unknown stream type -- cannot build datasource for stream: stream_name: "{stream_name}", stream_type: "{stream_type}"')

        all_streams_datasources[stream_name] = datasource
    ## END for i, s in enumerate(streams)...

    return all_streams, all_streams_datasources

