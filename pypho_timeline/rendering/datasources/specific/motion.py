import numpy as np
import pandas as pd
# from qtpy import QtWidgets, QtCore
from typing import Dict, List, Tuple, Optional, Callable, Union, Any
# import pyphoplacecellanalysis.External.pyqtgraph as pg
# from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode
# from pypho_timeline.docking.nested_dock_area_widget import NestedDockAreaWidget
# from pypho_timeline.docking.specific_dock_widget_mixin import SpecificDockWidgetManipulatingMixin
# from pypho_timeline.docking.dock_display_configs import CustomCyclicColorsDockDisplayConfig, NamedColorScheme
# from pypho_timeline.core.pyqtgraph_time_synchronized_widget import PyqtgraphTimeSynchronizedWidget
# from pypho_timeline.rendering.graphics.interval_rects_item import IntervalRectsItem, IntervalRectsItemData
from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, BaseTrackDatasource, IntervalProvidingTrackDatasource
from pypho_timeline.rendering.detail_renderers.motion_plot_renderer import MotionPlotDetailRenderer


class MotionTrackDatasource(IntervalProvidingTrackDatasource):
    """Example TrackDatasource for motion data.
    
    Inherits from IntervalProvidingTrackDatasource and implements motion-specific
    detail rendering for displaying motion data with async detail loading.

    Usage:

        from pypho_timeline.rendering.datasources.specific.motion import MotionTrackDatasource
    """
    
    def __init__(self, intervals_df: pd.DataFrame, motion_df: pd.DataFrame, custom_datasource_name: Optional[str]=None, max_points_per_second: Optional[float]=1000.0, enable_downsampling: bool=True):
        """Initialize with motion data and intervals.
        
        Args:
            intervals_df: DataFrame with columns ['t_start', 't_duration'] for intervals
            motion_df: DataFrame with columns ['t'] and channel columns (e.g., ['AccX', 'AccY', ...])
            custom_datasource_name: Custom name for this datasource (optional)
            max_points_per_second: Maximum points per second for downsampling. If None, no downsampling. Default: 1000.0
            enable_downsampling: Whether to enable downsampling. Default: True
        """
        if custom_datasource_name is None:
            custom_datasource_name = "MotionTrack"
        super().__init__(intervals_df, detailed_df=motion_df, custom_datasource_name=custom_datasource_name, max_points_per_second=max_points_per_second, enable_downsampling=enable_downsampling)
        
        # Override visualization properties (parent sets blue, we want blue too, but keep same height)
        # Parent already sets series_height=1.0, which is what we want, so no change needed
        # Parent already sets blue color, which is what we want, so no change needed
    
    def get_detail_renderer(self):
        """Get detail renderer for motion data."""
        if self.detailed_df is None:
            print(f'WARN: self.detailed_df is None!')
            return MotionPlotDetailRenderer(pen_width=2)
        return MotionPlotDetailRenderer(pen_width=2)


    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get cache key for interval."""
        return f"motion_{interval['t_start']:.3f}_{interval['t_duration']:.3f}"

