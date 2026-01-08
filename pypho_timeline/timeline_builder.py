"""
TimelineBuilder - A class for building and updating timeline widgets from various input sources.

This module provides a unified interface for creating SimpleTimelineWidget instances
from different data sources such as XDF files, pre-loaded streams, or existing datasources.
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
import logging
import numpy as np
import pandas as pd
import pyxdf
from pypho_timeline.widgets import SimpleTimelineWidget, perform_process_all_streams, perform_process_all_streams_multi_xdf
from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode
from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource
from pypho_timeline.utils.logging_util import configure_logging

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
    """
    
    def __init__(self, log_level: int = logging.DEBUG, log_file: Optional[Path] = None, log_to_console: bool = True, log_to_file: bool = True):
        """Initialize the TimelineBuilder with logging configuration.
        
        Args:
            log_level: Logging level (default: logging.DEBUG)
            log_file: Path to log file (default: None, uses "timeline_rendering.log")
            log_to_console: Whether to log to console (default: True)
            log_to_file: Whether to log to file (default: True)
        """
        self.log_level = log_level
        self.log_file = log_file if log_file is not None else Path("timeline_rendering.log")
        self.log_to_console = log_to_console
        self.log_to_file = log_to_file
        
        # Configure logging
        configure_logging(
            log_level=self.log_level,
            log_file=self.log_file,
            log_to_console=self.log_to_console,
            log_to_file=self.log_to_file
        )
        if self.log_to_console or self.log_to_file:
            print(f"Logging configured for TimelineBuilder - console: {self.log_to_console}, file: {self.log_to_file} ({self.log_file})")
    
    ## MAIN FUNCTION
    def build_from_xdf_file(self, xdf_file_path: Path, window_duration: Optional[float] = None, window_start_time: Optional[float] = None, add_example_tracks: bool = False, window_title: Optional[str] = None, window_size: Tuple[int, int] = (1000, 800)) -> Optional[SimpleTimelineWidget]:
        """Build a timeline widget from an XDF file.
        
        Args:
            xdf_file_path: Path to the XDF file
            window_duration: Duration of the time window (default: auto-calculated from data)
            window_start_time: Start time of the window (default: auto-calculated from data)
            add_example_tracks: Whether to add example tracks (default: False)
            window_title: Custom window title (default: auto-generated from filename)
            window_size: Window size as (width, height) tuple (default: (1000, 800))
            
        Returns:
            SimpleTimelineWidget instance, or None if no streams found
        """
        # Use multi-file method for backward compatibility
        return self.build_from_xdf_files(xdf_file_paths=[xdf_file_path], window_duration=window_duration, window_start_time=window_start_time, add_example_tracks=add_example_tracks, window_title=window_title, window_size=window_size)
    
    def build_from_xdf_files(self, xdf_file_paths: List[Path], window_duration: Optional[float] = None, window_start_time: Optional[float] = None, add_example_tracks: bool = False, window_title: Optional[str] = None, window_size: Tuple[int, int] = (1000, 800)) -> Optional[SimpleTimelineWidget]:
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
            
        Returns:
            SimpleTimelineWidget instance, or None if no streams found
            
        Example:
            builder = TimelineBuilder()
            timeline = builder.build_from_xdf_files([
                Path("file1.xdf"),
                Path("file2.xdf")
            ])
        """
        if not xdf_file_paths:
            raise ValueError("xdf_file_paths list cannot be empty")
        
        print("=" * 60)
        if len(xdf_file_paths) == 1:
            print(f"pyPhoTimeline - Load all modalities from XDF: {xdf_file_paths[0]}")
        else:
            print(f"pyPhoTimeline - Load all modalities from {len(xdf_file_paths)} XDF files:")
            for path in xdf_file_paths:
                print(f"  - {path}")
        print("=" * 60)
        
        # Load all XDF files
        all_streams_by_file = []
        all_file_headers = []
        for xdf_file_path in xdf_file_paths:
            print(f"Loading XDF file: {xdf_file_path} ...")
            streams, file_header = pyxdf.load_xdf(str(xdf_file_path))
            print(f"  Streams loaded: {[s['info']['name'][0] for s in streams]}")
            all_streams_by_file.append(streams)
            all_file_headers.append(file_header)
        
        # Process streams from all files and merge by stream name
        all_streams, all_streams_datasources = perform_process_all_streams_multi_xdf(streams_list=all_streams_by_file, xdf_file_paths=xdf_file_paths)
        
        if not all_streams:
            print("No streams found.")
            return None
        
        print(f"Found {len(all_streams)} unique stream names after merging: {[a_name for a_name in list(all_streams_datasources.keys())]}")
        
        # Get active datasources
        active_datasources_dict = {k: v for k, v in all_streams_datasources.items() if v is not None}
        active_datasource_list = list(active_datasources_dict.values())
        print(f"\tbuild active_datasources: {len(active_datasource_list)} datasources.")
        
        if not active_datasource_list:
            print("No valid datasources found.")
            return None
        
        # Generate window title if not provided
        if window_title is None:
            if len(xdf_file_paths) == 1:
                window_title = f"pyPhoTimeline - ALL Modalities from XDF: {xdf_file_paths[0].name}"
            else:
                file_names = ", ".join([p.name for p in xdf_file_paths])
                window_title = f"pyPhoTimeline - ALL Modalities from {len(xdf_file_paths)} XDF files: {file_names}"
        
        # Build timeline from merged datasources
        return self.build_from_datasources(datasources=active_datasource_list, window_duration=window_duration, window_start_time=window_start_time, add_example_tracks=add_example_tracks, window_title=window_title, window_size=window_size)
    
    def build_from_video(self, video_datasource: Optional[VideoTrackDatasource] = None, video_folder_path: Optional[Path] = None, video_paths: Optional[List[Union[Path, str]]] = None, video_df: Optional[pd.DataFrame] = None, video_intervals_df: Optional[pd.DataFrame] = None, custom_datasource_name: Optional[str] = None, reference_timestamp: Optional[float] = None, window_duration: Optional[float] = None, window_start_time: Optional[float] = None, window_title: Optional[str] = None, window_size: Tuple[int, int] = (1000, 800), frames_per_second: float = 10.0, thumbnail_size: Optional[Tuple[int, int]] = (128, 128)) -> SimpleTimelineWidget:
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
        
        # Check if datasource has any intervals
        if video_datasource.intervals_df.empty:
            raise ValueError("VideoTrackDatasource has no video intervals. Check that video files exist and are valid.")
        
        # Build timeline from the single video datasource
        return self.build_from_datasources(
            datasources=[video_datasource],
            window_duration=window_duration,
            window_start_time=window_start_time,
            add_example_tracks=False,
            window_title=window_title or f"pyPhoTimeline - Video Track: {video_datasource.custom_datasource_name}",
            window_size=window_size
        )
    

    

    def build_from_streams(self, streams: List, window_duration: Optional[float] = None, window_start_time: Optional[float] = None, add_example_tracks: bool = False, window_title: Optional[str] = None, window_size: Tuple[int, int] = (1000, 800)) -> Optional[SimpleTimelineWidget]:
        """Build a timeline widget from pre-loaded streams.
        
        Args:
            streams: List of stream dictionaries from pyxdf
            window_duration: Duration of the time window (default: auto-calculated from data)
            window_start_time: Start time of the window (default: auto-calculated from data)
            add_example_tracks: Whether to add example tracks (default: False)
            window_title: Custom window title (default: "pyPhoTimeline")
            window_size: Window size as (width, height) tuple (default: (1000, 800))
            
        Returns:
            SimpleTimelineWidget instance, or None if no streams found
        """
        # Process streams to get datasources
        all_streams, all_streams_datasources = self._process_xdf_streams(streams)
        
        if not all_streams:
            print("No streams found.")
            return None
        
        print(f"Found {len(all_streams)} streams: {[a_name for a_name in list(all_streams_datasources.keys())]}")
        
        # Get active datasources
        active_datasources_dict = {k: v for k, v in all_streams_datasources.items() if v is not None}
        active_datasource_list = list(active_datasources_dict.values())
        print(f"\tbuild active_datasources: {len(active_datasource_list)} datasources.")
        
        if not active_datasource_list:
            print("No valid datasources found.")
            return None
        
        # Build timeline from datasources
        return self.build_from_datasources(datasources=active_datasource_list, window_duration=window_duration, window_start_time=window_start_time, add_example_tracks=add_example_tracks, window_title=window_title or "pyPhoTimeline", window_size=window_size)
    
    def build_from_datasources(self, datasources: List[TrackDatasource], window_duration: Optional[float] = None, window_start_time: Optional[float] = None, add_example_tracks: bool = False, window_title: Optional[str] = None, window_size: Tuple[int, int] = (1000, 800)) -> SimpleTimelineWidget:
        """Build a timeline widget from existing datasources.
        
        Args:
            datasources: List of TrackDatasource instances
            window_duration: Duration of the time window (default: auto-calculated from data)
            window_start_time: Start time of the window (default: auto-calculated from data)
            add_example_tracks: Whether to add example tracks (default: False)
            window_title: Custom window title (default: "pyPhoTimeline")
            window_size: Window size as (width, height) tuple (default: (1000, 800))
            
        Returns:
            SimpleTimelineWidget instance
        """
        if not datasources:
            raise ValueError("datasources list cannot be empty")
        
        # Calculate time range from datasources
        total_start_time: float = np.nanmin([ds.total_df_start_end_times[0] for ds in datasources])
        total_end_time: float = np.nanmax([ds.total_df_start_end_times[1] for ds in datasources])
        
        # Calculate window duration if not provided
        if window_duration is None:
            window_duration = total_end_time - total_start_time
            window_duration = max(window_duration, 10.0)
        
        # Calculate window start time if not provided
        if window_start_time is None:
            window_start_time = total_start_time
        
        # Create the timeline widget
        timeline = SimpleTimelineWidget(
            total_start_time=total_start_time,
            total_end_time=total_end_time,
            window_duration=window_duration,
            window_start_time=window_start_time,
            add_example_tracks=add_example_tracks
        )
        
        # Add tracks to the timeline
        self._add_tracks_to_timeline(timeline, datasources)
        
        # Configure window
        timeline.setWindowTitle(window_title or "pyPhoTimeline")
        timeline.resize(window_size[0], window_size[1])
        timeline.show()
        
        print("\nTimeline widget created with tracks:")
        for ds in datasources:
            print(f"  - {ds.custom_datasource_name}, time: {ds.total_df_start_end_times}")
        
        print("\nScroll on the timeline to see loaded intervals for each stream.")
        print("Close the window to exit.\n")
        
        return timeline
    
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
            print("No datasources provided for update.")
            return timeline
        
        # Update time range if requested
        if update_time_range:
            existing_start = timeline.total_data_start_time
            existing_end = timeline.total_data_end_time
            new_start = np.nanmin([ds.total_df_start_end_times[0] for ds in datasources])
            new_end = np.nanmax([ds.total_df_start_end_times[1] for ds in datasources])
            
            total_start_time = min(existing_start, new_start)
            total_end_time = max(existing_end, new_end)
            
            # Update timeline time range
            timeline.total_data_start_time = total_start_time
            timeline.total_data_end_time = total_end_time
            timeline.spikes_window.total_df_start_end_times = (total_start_time, total_end_time)
        
        # Add tracks to the timeline
        self._add_tracks_to_timeline(timeline, datasources)
        
        print(f"\nUpdated timeline with {len(datasources)} new tracks:")
        for ds in datasources:
            print(f"  - {ds.custom_datasource_name}, time: {ds.total_df_start_end_times}")
        
        return timeline
    
    def _process_xdf_streams(self, streams: List) -> Tuple[Dict, Dict]:
        """Process XDF streams to extract datasources.
        
        Args:
            streams: List of stream dictionaries from pyxdf
            
        Returns:
            Tuple of (all_streams dict, all_streams_datasources dict)
        """
        return perform_process_all_streams(streams=streams)
    
    def _add_tracks_to_timeline(self, timeline: SimpleTimelineWidget, datasources: List[TrackDatasource]) -> None:
        """Add tracks to a timeline widget.
        
        Args:
            timeline: SimpleTimelineWidget instance
            datasources: List of TrackDatasource instances to add
        """
        for datasource in datasources:
            # Get detail renderer
            a_detail_renderer = datasource.get_detail_renderer()
            
            # Create plot widget for this track
            track_widget, a_root_graphics, a_plot_item, a_dock = timeline.add_new_embedded_pyqtgraph_render_plot_widget(
                name=datasource.custom_datasource_name,
                dockSize=(500, 80),
                dockAddLocationOpts=['bottom'],
                sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA
            )
            
            assert a_detail_renderer is not None, f"Detail renderer is None for datasource: {datasource.custom_datasource_name}"
            track_widget.set_track_renderer(a_detail_renderer)
            
            # Explicitly set the optionsPanel attribute
            track_widget.optionsPanel = track_widget.getOptionsPanel()
            
            # Try to force dock to update button visibility
            a_dock.updateWidgetsHaveOptionsPanel()
            a_dock.update()  # May refresh the title bar
            
            # Or if available:
            if hasattr(a_dock, 'updateTitleBar') or hasattr(a_dock, 'refresh'):
                a_dock.updateTitleBar()  # or refresh()
            
            # Set the plot to show the full time range
            a_plot_item.setXRange(timeline.total_data_start_time, timeline.total_data_end_time, padding=0)
            a_plot_item.setYRange(0, 1, padding=0)
            a_plot_item.setLabel('bottom', 'Time', units='s')
            a_plot_item.setLabel('left', datasource.custom_datasource_name)
            a_plot_item.hideAxis('left')  # Hide Y-axis for cleaner look
            
            # Add the track to the plot
            a_track_name: str = datasource.custom_datasource_name
            timeline.add_track(datasource, name=a_track_name, plot_item=a_plot_item)
        ## END for datasource in datasources...
        
