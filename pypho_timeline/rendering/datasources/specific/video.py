import numpy as np
import pandas as pd
# from qtpy import QtWidgets, QtCore
from typing import Dict, List, Tuple, Optional, Callable, Union, Any
import pyphoplacecellanalysis.External.pyqtgraph as pg
# from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode
# from pypho_timeline.docking.nested_dock_area_widget import NestedDockAreaWidget
# from pypho_timeline.docking.specific_dock_widget_mixin import SpecificDockWidgetManipulatingMixin
# from pypho_timeline.docking.dock_display_configs import CustomCyclicColorsDockDisplayConfig, NamedColorScheme
# from pypho_timeline.core.pyqtgraph_time_synchronized_widget import PyqtgraphTimeSynchronizedWidget
# from pypho_timeline.rendering.graphics.interval_rects_item import IntervalRectsItem, IntervalRectsItemData
from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, BaseTrackDatasource, IntervalProvidingTrackDatasource
from pypho_timeline.rendering.detail_renderers import VideoThumbnailDetailRenderer


class VideoTrackDatasource(IntervalProvidingTrackDatasource):
    """Example TrackDatasource for video data.
    
    Inherits from IntervalProvidingTrackDatasource and implements video-specific
    detail rendering for displaying video intervals with async detail loading.

    Usage:

        from pypho_timeline.rendering.datasources.specific.video import VideoTrackDatasource
    """
    
    def __init__(self, video_intervals_df: pd.DataFrame):
        """Initialize with video intervals.
        
        Args:
            video_intervals_df: DataFrame with columns ['t_start', 't_duration', 'video_path']
        """
        super().__init__(video_intervals_df, detailed_df=None)
        self.custom_datasource_name = "VideoTrack"
        
        # Override visualization properties (parent sets blue, we want green; parent sets height=1.0, we want 50.0)
        self.intervals_df['series_height'] = 50.0
        
        # Create pens and brushes with green color
        color = pg.mkColor('green')
        color.setAlphaF(0.3)
        pen = pg.mkPen(color, width=1)
        brush = pg.mkBrush(color)
        self.intervals_df['pen'] = [pen] * len(self.intervals_df)
        self.intervals_df['brush'] = [brush] * len(self.intervals_df)
    
    def fetch_detailed_data(self, interval: pd.Series) -> dict:
        """Fetch video frames for an interval (simulated with random images)."""
        # In a real implementation, this would load video frames
        # For demo, generate synthetic frame data
        n_frames = max(1, int(interval['t_duration'] * 10))  # 10 fps
        frames = []
        for i in range(n_frames):
            # Generate a simple colored frame
            frame = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
            frames.append(frame)
        return {'frames': frames, 'timestamps': np.linspace(interval['t_start'], interval['t_start'] + interval['t_duration'], n_frames)}
    
    def get_detail_renderer(self):
        """Get detail renderer for video."""
        return VideoThumbnailDetailRenderer(thumbnail_height=50.0, spacing=0.1)
    
    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get cache key for interval."""
        return f"video_{interval['t_start']:.3f}_{interval['t_duration']:.3f}"

