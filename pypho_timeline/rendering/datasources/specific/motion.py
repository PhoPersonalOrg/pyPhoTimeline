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
    
    def __init__(self, motion_df: pd.DataFrame, intervals_df: pd.DataFrame, custom_datasource_name: Optional[str]=None):
        """Initialize with motion data and intervals.
        
        Args:
            motion_df: DataFrame with columns ['t', 'x', 'y'] (or ['t', 'x'] for 1D)
            intervals_df: DataFrame with columns ['t_start', 't_duration'] for intervals
        """
        super().__init__(intervals_df, detailed_df=motion_df)
        if custom_datasource_name is None:
            custom_datasource_name = "MotionTrack"
        self.custom_datasource_name = custom_datasource_name
        
        # Override visualization properties (parent sets blue, we want blue too, but keep same height)
        # Parent already sets series_height=1.0, which is what we want, so no change needed
        # Parent already sets blue color, which is what we want, so no change needed
    
    def get_detail_renderer(self):
        """Get detail renderer for motion data."""
        if self.detailed_df is None:
            return MotionPlotDetailRenderer(pen_color='cyan', pen_width=2, y_column=None)
        return MotionPlotDetailRenderer(pen_color='cyan', pen_width=2, y_column='y' if 'y' in self.detailed_df.columns else None)
    
    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get cache key for interval."""
        return f"motion_{interval['t_start']:.3f}_{interval['t_duration']:.3f}"

