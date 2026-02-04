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
import pyphoplacecellanalysis.External.pyqtgraph as pg
from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode
from pypho_timeline.utils.datetime_helpers import float_to_datetime, datetime_to_unix_timestamp, datetime_to_float, get_reference_datetime_from_xdf_header, unix_timestamp_to_datetime
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



    def add_video_track(self, track_name: str, video_datasource: VideoTrackDatasource, dockSize: Tuple[int, int] = (500, 80), sync_mode: SynchronizedPlotMode = SynchronizedPlotMode.TO_GLOBAL_DATA, use_vispy: bool = False):
            """Add a video track to the timeline.
            
            This is a convenience method that creates a plot widget and adds the video track.
            
            Args:
                track_name: Unique name for this video track
                video_datasource: VideoTrackDatasource instance
                dockSize: Size of the dock widget (width, height). Default: (500, 80)
                sync_mode: Synchronization mode for the plot. Default: TO_GLOBAL_DATA
                use_vispy: If True, use high-performance vispy renderer instead of pyqtgraph (default: False)
                
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
            self.add_track(video_datasource, name=track_name, plot_item=plot_item)
            
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


def merge_streams_by_name(streams_by_file: List[Tuple[List, Path]]) -> Dict[str, List[Tuple[Dict, Path]]]:
    """Group streams by name across multiple XDF files.
    
    Args:
        streams_by_file: List of tuples (streams_list, file_path) where streams_list is a list of stream dictionaries
                         from pyxdf and file_path is the Path to the XDF file
    
    Returns:
        Dictionary mapping stream names to lists of (stream_dict, file_path) tuples
    """
    streams_by_name = {}
    for streams, file_path in streams_by_file:
        for stream in streams:
            stream_name = stream['info']['name'][0]
            if stream_name not in streams_by_name:
                streams_by_name[stream_name] = []
            streams_by_name[stream_name].append((stream, file_path))
    return streams_by_name


def perform_process_all_streams_multi_xdf(streams_list: List[List], xdf_file_paths: List[Path], file_headers: Optional[List[dict]] = None) -> Tuple[Dict, Dict]:
    """Process streams from multiple XDF files and merge streams with the same name.
    
    Streams with the same name across different files will be merged into a single datasource.
    Timestamps are converted to use a common reference datetime (earliest file's reference) to ensure
    proper alignment across multiple files.
    
    Args:
        streams_list: List of stream lists (one per XDF file), where each stream list contains
                     stream dictionaries from pyxdf
        xdf_file_paths: List of Path objects corresponding to each stream list
        file_headers: Optional list of XDF file header dictionaries (one per file)
    
    Returns:
        Tuple of (all_streams dict, all_streams_datasources dict) where:
        - all_streams: Dictionary mapping stream names to merged interval DataFrames
        - all_streams_datasources: Dictionary mapping stream names to merged TrackDatasource instances
    """
    from phoofflineeeganalysis.analysis.historical_data import HistoricalData


    if len(streams_list) != len(xdf_file_paths):
        raise ValueError(f"streams_list length ({len(streams_list)}) must match xdf_file_paths length ({len(xdf_file_paths)})")
    
    # Extract reference datetimes from file headers
    file_reference_datetimes = {}

    xdf_recording_file_metadta_df: pd.DataFrame = HistoricalData.build_file_comparison_df(recording_files=xdf_file_paths) ## this should be cheap because most will already be cached
    
    if file_headers is None:
        file_headers = [None] * len(xdf_file_paths)

    for file_header, file_path in zip(file_headers, xdf_file_paths):
        ref_dt = None
        if file_header is not None:
            ref_dt = get_reference_datetime_from_xdf_header(file_header)
        # ref_dt = get_reference_datetime_from_xdf_file(file_path=file_path, file_header=file_header)
        if ref_dt is not None:
            file_reference_datetimes[file_path] = ref_dt
        else:
            found_file_df_matches = xdf_recording_file_metadta_df[xdf_recording_file_metadta_df['src_file'].apply(lambda s: Path(s).resolve()) == Path(file_path).resolve()]
            if len(found_file_df_matches) == 1:
                # Safely fetch the only row, avoiding KeyErrors and other indexing errors
                meas_datetime = found_file_df_matches.iloc[0]['meas_datetime'] if not found_file_df_matches.empty else None
                ref_dt = meas_datetime # Timestamp('2026-02-04 09:58:42+0000', tz='UTC')
            else:
                print(f'WARN: failed to find xdf file metadata for file file_path: "{file_path.as_posix()}" in xdf_recording_file_metadta_df: {xdf_recording_file_metadta_df}\n\tfound_file_df_matches: {found_file_df_matches}')

        if ref_dt is not None:
            file_reference_datetimes[file_path] = ref_dt
    ## END for file_header, file_path in zip(file_headers, xdf_file_paths):...
    
    # Find earliest reference datetime (common reference for all timestamps)
    earliest_reference_datetime = None
    if file_reference_datetimes:
        earliest_reference_datetime = min(file_reference_datetimes.values())
        print(f"Using earliest reference datetime: {earliest_reference_datetime} for timestamp normalization")
    
    # Group streams by name across all files
    streams_by_file = list(zip(streams_list, xdf_file_paths))
    streams_by_name = merge_streams_by_name(streams_by_file)
    
    all_streams = {}
    all_streams_datasources = {}
    
    # Process each unique stream name
    for stream_name, stream_file_pairs in streams_by_name.items():
        print(f"\nProcessing stream '{stream_name}' from {len(stream_file_pairs)} file(s)...")
        
        # Collect intervals and detailed data from all files for this stream name
        all_intervals_dfs = []
        all_detailed_dfs = []
        stream_type = None
        stream_info = None
        
        for stream, file_path in stream_file_pairs:
            current_stream_type = stream['info']['type'][0]
            if stream_type is None:
                stream_type = current_stream_type
                stream_info = stream['info']
            elif stream_type != current_stream_type:
                print(f"WARN: Stream '{stream_name}' has different types across files: {stream_type} vs {current_stream_type}")
            
            timestamps = stream['time_stamps'] # these already look correct, like unix global timestamps
            time_series = stream['time_series']
            
            if len(timestamps) == 0:
                print(f"  Skipping empty stream from {file_path.name}")
                continue
            
            # Convert timestamps: from relative (to file's reference) to absolute, then to relative (to earliest reference)
            file_ref_dt = file_reference_datetimes.get(file_path)
            if (file_ref_dt is not None) and (timestamps is not None): # 
                # Convert relative timestamps to absolute datetimes using file's reference
                timestamps_absolute = [float_to_datetime(float(ts), file_ref_dt) for ts in timestamps]

                #TODO 2026-02-04 05:15: - [ ] Changing from using relative to earliest reference to unix timestamps (absolute)
                # # Convert absolute datetimes back to relative timestamps using earliest reference
                # if (earliest_reference_datetime is not None):
                #     timestamps = np.array([datetime_to_float(dt, earliest_reference_datetime) for dt in timestamps_absolute])

                # Convert to unix timestamps (absolute) instead ______________________________________________________________________________________________________________________________________________________________________________________________________________________________________ #
                timestamps = np.array([datetime_to_unix_timestamp(dt) for dt in timestamps_absolute]) ## this does actually make e09 instead of e06
                ## yeah they work: [unix_timestamp_to_datetime(v) for v in np.array([datetime_to_unix_timestamp(dt) for dt in timestamps_absolute])] ## actually these are real datetimes, instead of  Timestamp('2026-02-04 21:20:49.471665+0000', tz='UTC') `timestamps_absolute`

            else:
                # Fallback: use timestamps as-is (relative to file start, which may cause misalignment)
                timestamps = np.array([float(ts) for ts in timestamps])
                if file_ref_dt is None:
                    print(f"  WARN: No reference datetime found for {file_path.name}, timestamps may be misaligned")
            
            stream_start = float(timestamps[0])
            stream_end = float(timestamps[-1])
            stream_duration = stream_end - stream_start

            # timestamps = np.array([unix_timestamp_to_datetime(datetime_to_unix_timestamp(dt)) for dt in timestamps_absolute])
            timestamps = np.array([unix_timestamp_to_datetime(v) for v in timestamps])


            ## copied directly from video_metadata_to_intervals_df(...) which works:
            # timestamps = pd.to_datetime(timestamps).apply(lambda dt: dt.tz_localize('UTC') if dt.tzinfo is None else dt).values # ## yeah they work: [unix_timestamp_to_datetime(v) for v in np.array([datetime_to_unix_timestamp(dt) for dt in timestamps_absolute])] ## actually these are real datetimes, instead of  Timestamp('2026-02-04 21:20:49.471665+0000', tz='UTC') `timestamps_absolute`
            # t_start_values = pd.to_datetime(starts).apply(lambda dt: dt.tz_localize('UTC') if dt.tzinfo is None else dt).values

            ts_index = pd.to_datetime(timestamps)
            ts_index = ts_index.tz_localize('UTC') if ts_index.tz is None else ts_index.tz_convert('UTC')
            timestamps = ts_index.values # timestamps: array(['2026-02-04T21:20:47.722655000', '2026-02-04T21:20:47.753887000',
                                                #    '2026-02-04T21:20:47.785120000', ...,
                                                #    '2026-02-04T22:44:58.643416000', '2026-02-04T22:44:58.674648000',
                                                #    '2026-02-04T22:44:58.705881000'], dtype='datetime64[ns]')

            ## ALTERNATIVE post-hoc conversion if I didn't use datetime_to_unix_timestep(...) above:
            # # store that as a datetime column (e.g. pd.Timestamp(...) or a datetime64 column) in the DataFrame.
            # t_start_absolute = float_to_datetime(stream_start, earliest_reference_datetime)
            # t_end_absolute = float_to_datetime(stream_end, earliest_reference_datetime)
                        
            # Create interval DataFrame
            intervals_df = pd.DataFrame({
                't_start': [stream_start],
                't_duration': [stream_duration],
                't_end': [stream_end]
            })
            
            # Add visualization columns
            intervals_df['series_vertical_offset'] = 0.0
            intervals_df['series_height'] = 0.9
            
            # Create pens and brushes
            color = pg.mkColor('blue')
            color.setAlphaF(0.3)
            pen = pg.mkPen(color, width=1)
            brush = pg.mkBrush(color)
            intervals_df['pen'] = [pen]
            intervals_df['brush'] = [brush]
            
            all_intervals_dfs.append(intervals_df)
            
            # Create detailed DataFrame if time_series exists
            if time_series is not None and len(time_series) > 0:
                n_channels = int(stream['info']['channel_count'][0])
                n_t_stamps, n_columns = np.shape(time_series)
                
                if n_channels == n_columns and len(timestamps) == n_t_stamps:
                    # Determine channel names based on stream type
                    if (stream_type.upper() in ['SIGNAL', 'RAW']) and ('Motion' in stream_name):
                        channel_names = modality_channels_dict['MOTION']
                    elif (stream_type.upper() in ['RAW']) and (' eQuality' in stream_name):
                        channel_names = modality_channels_dict['EEG']
                    elif (stream_type.upper() == 'EEG'):
                        channel_names = modality_channels_dict['EEG']
                    elif (stream_type.upper() in ['MARKERS']) and (stream_name in ['EventBoard', 'TextLogger']):
                        channel_names = modality_channels_dict['LOG']
                    else:
                        # Generic: use column indices
                        channel_names = [f'Channel_{i}' for i in range(n_columns)]
                    
                    time_series_df = pd.DataFrame(time_series, columns=channel_names)
                    time_series_df['t'] = timestamps
                    all_detailed_dfs.append(time_series_df)
        
        # Check if we have valid intervals
        if not all_intervals_dfs:
            print(f"  No valid intervals for stream '{stream_name}'")
            continue
        
        # Merge intervals for display (all_streams dict)
        merged_intervals_df = pd.concat(all_intervals_dfs, ignore_index=True).sort_values('t_start')
        all_streams[stream_name] = merged_intervals_df
        
        has_valid_intervals = len(merged_intervals_df) > 0
        has_detailed_data = len(all_detailed_dfs) > 0
        
        # Create merged datasource based on stream type
        # Pass individual DataFrames to from_multiple_sources to let it handle merging
        datasource = None
        
        if (stream_type.upper() in ['SIGNAL', 'RAW']) and ('Motion' in stream_name):
            if has_valid_intervals and has_detailed_data:
                motion_norm_dict = modality_channels_normalization_mode_dict.get('MOTION')
                datasource = MotionTrackDatasource.from_multiple_sources(
                    intervals_dfs=all_intervals_dfs,
                    detailed_dfs=all_detailed_dfs,
                    custom_datasource_name=f"MOTION_{stream_name}",
                    max_points_per_second=10.0,
                    enable_downsampling=True,
                    fallback_normalization_mode=ChannelNormalizationMode.GROUPMINMAXRANGE,
                    normalization_mode_dict=motion_norm_dict,
                )
        
        elif (stream_type.upper() in ['RAW']) and (' eQuality' in stream_name):
            if has_valid_intervals and has_detailed_data:
                from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import DataframePlotDetailRenderer
                channel_names = modality_channels_dict['EEG']
                eeg_norm_dict = modality_channels_normalization_mode_dict.get('EEG')
                
                a_detail_renderer = DataframePlotDetailRenderer(
                    channel_names=channel_names,
                    fallback_normalization_mode=ChannelNormalizationMode.INDIVIDUAL,
                    normalization_mode_dict=eeg_norm_dict,
                )
                
                datasource = IntervalProvidingTrackDatasource.from_multiple_sources(
                    intervals_dfs=all_intervals_dfs,
                    detailed_dfs=all_detailed_dfs,
                    custom_datasource_name=f"EEGQ_{stream_name}",
                    detail_renderer=a_detail_renderer,
                    max_points_per_second=2.0,
                    enable_downsampling=True
                )
        
        elif (stream_type.upper() == 'EEG'):
            if has_valid_intervals and has_detailed_data:
                eeg_norm_dict = modality_channels_normalization_mode_dict.get('EEG')
                datasource = EEGTrackDatasource.from_multiple_sources(
                    intervals_dfs=all_intervals_dfs,
                    detailed_dfs=all_detailed_dfs,
                    custom_datasource_name=f"EEG_{stream_name}",
                    max_points_per_second=10.0,
                    enable_downsampling=True,
                    fallback_normalization_mode=ChannelNormalizationMode.INDIVIDUAL,
                    normalization_mode_dict=eeg_norm_dict,
                )
        
        elif (stream_type.upper() in ['MARKERS']) and (stream_name in ['EventBoard', 'TextLogger']):
            if has_valid_intervals and has_detailed_data:
                from pypho_timeline.rendering.detail_renderers.log_text_plot_renderer import LogTextDataFramePlotDetailRenderer
                channel_names = modality_channels_dict['LOG']
                a_detail_renderer = LogTextDataFramePlotDetailRenderer(text_color='white', text_size=10, channel_names=channel_names)
                
                datasource = IntervalProvidingTrackDatasource.from_multiple_sources(
                    intervals_dfs=all_intervals_dfs,
                    detailed_dfs=all_detailed_dfs,
                    custom_datasource_name=f"LOG_{stream_name}",
                    detail_renderer=a_detail_renderer,
                    enable_downsampling=False
                )
        
        elif has_valid_intervals:
            # Unknown stream type
            datasource = IntervalProvidingTrackDatasource.from_multiple_sources(
                intervals_dfs=all_intervals_dfs,
                detailed_dfs=all_detailed_dfs if has_detailed_data else None,
                custom_datasource_name=f"UNKNOWN_{stream_name}",
                max_points_per_second=1.0,
                enable_downsampling=False
            )
            print(f'WARN: unspecific stream type -- cannot build datasource for stream: stream_name: "{stream_name}", stream_type: "{stream_type}"')
        
        all_streams_datasources[stream_name] = datasource
    
    return all_streams, all_streams_datasources

