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
from pypho_timeline.rendering.detail_renderers import PositionPlotDetailRenderer


class PositionTrackDatasource(IntervalProvidingTrackDatasource):
    """Example TrackDatasource for position data.
    
    Inherits from IntervalProvidingTrackDatasource and implements position-specific
    detail rendering for displaying position data with async detail loading.

    Usage:

        from pypho_timeline.rendering.datasources.specific.position import PositionTrackDatasource
    """
    
    def __init__(self, intervals_df: pd.DataFrame, position_df: pd.DataFrame, custom_datasource_name: Optional[str]=None):
        """Initialize with position data and intervals.
        
        Args:
            position_df: DataFrame with columns ['t', 'x', 'y'] (or ['t', 'x'] for 1D)
            intervals_df: DataFrame with columns ['t_start', 't_duration'] for intervals
        """
        if custom_datasource_name is None:
            custom_datasource_name = "PositionTrack"
        super().__init__(intervals_df, detailed_df=position_df, custom_datasource_name=custom_datasource_name)
        
        # Override visualization properties (parent sets blue, we want blue too, but keep same height)
        # Parent already sets series_height=1.0, which is what we want, so no change needed
        # Parent already sets blue color, which is what we want, so no change needed
    
    def get_detail_renderer(self):
        """Get detail renderer for position data."""
        if self.detailed_df is None:
            return PositionPlotDetailRenderer(pen_color='cyan', pen_width=2, y_column=None)
        return PositionPlotDetailRenderer(pen_color='cyan', pen_width=2, y_column='y' if 'y' in self.detailed_df.columns else None)
    
    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get cache key for interval."""
        return f"position_{interval['t_start']:.3f}_{interval['t_duration']:.3f}"

