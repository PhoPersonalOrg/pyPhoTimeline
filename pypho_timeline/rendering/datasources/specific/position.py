import numpy as np
import pandas as pd
# from qtpy import QtWidgets, QtCore
from typing import Dict, List, Tuple, Optional, Callable, Union, Any
# from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode
# from pypho_timeline.docking.nested_dock_area_widget import NestedDockAreaWidget
# from pypho_timeline.docking.specific_dock_widget_mixin import SpecificDockWidgetManipulatingMixin
# from pypho_timeline.docking.dock_display_configs import CustomCyclicColorsDockDisplayConfig, NamedColorScheme
# from pypho_timeline.core.pyqtgraph_time_synchronized_widget import PyqtgraphTimeSynchronizedWidget
# from pypho_timeline.rendering.graphics.interval_rects_item import IntervalRectsItem, IntervalRectsItemData
import pyphoplacecellanalysis.External.pyqtgraph as pg
from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, BaseTrackDatasource, IntervalProvidingTrackDatasource, DetailRenderer
from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import GenericPlotDetailRenderer


# ==================================================================================================================================================================================================================================================================================== #
# PositionPlotDetailRenderer - Renders position data as line plots.                                                                                                                                                                                                                              #
# ==================================================================================================================================================================================================================================================================================== #

## TODO: should implement/conform to `DetailRenderer`
## TODO: should inherit from `GenericPlotDetailRenderer`
class PositionPlotDetailRenderer(DetailRenderer):
    """Detail renderer for position tracks that displays position as a line plot.
    
    Expects detail_data to be a DataFrame with columns ['t', 'x', 'y'] or ['t', 'x'].
    """
    
    def __init__(self, pen_color='cyan', pen_width=2, y_column='y'):
        """Initialize the position plot renderer.
        
        Args:
            pen_color: Color for the position line (default: 'cyan')
            pen_width: Width of the position line (default: 2)
            y_column: Column name for y-coordinate (default: 'y', use None for 1D position)
        """
        self.pen_color = pen_color
        self.pen_width = pen_width
        self.y_column = y_column
    
    def render_detail(self, plot_item: pg.PlotItem, interval: pd.DataFrame, detail_data: Any) -> List[pg.GraphicsObject]:
        """Render position data as a line plot.
        
        Args:
            plot_item: The pyqtgraph PlotItem to render into
            interval: The interval DataFrame (single row) with 't_start' and 't_duration'
            detail_data: DataFrame with columns ['t', 'x', 'y'] or ['t', 'x']
            
        Returns:
            List of GraphicsObject items added (PlotDataItem)
        """
        if detail_data is None or len(detail_data) == 0:
            return []
        
        if not isinstance(detail_data, pd.DataFrame):
            raise TypeError(f"PositionPlotDetailRenderer expects DataFrame, got {type(detail_data)}")
        
        graphics_objects = []
        
        # Check required columns
        if 't' not in detail_data.columns or 'x' not in detail_data.columns:
            return []
        
        # Sort by time
        df_sorted = detail_data.sort_values('t')
        t_values = df_sorted['t'].values
        x_values = df_sorted['x'].values
        
        if self.y_column is not None and self.y_column in df_sorted.columns:
            # 2D position plot
            y_values = df_sorted[self.y_column].values
            pen = pg.mkPen(self.pen_color, width=self.pen_width)
            plot_data_item = pg.PlotDataItem(x_values, y_values, pen=pen, connect='finite')
            plot_item.addItem(plot_data_item)
            graphics_objects.append(plot_data_item)
        else:
            # 1D position plot (x vs time)
            pen = pg.mkPen(self.pen_color, width=self.pen_width)
            plot_data_item = pg.PlotDataItem(t_values, x_values, pen=pen, connect='finite')
            plot_item.addItem(plot_data_item)
            graphics_objects.append(plot_data_item)
        
        return graphics_objects
    
    def clear_detail(self, plot_item: pg.PlotItem, graphics_objects: List[pg.GraphicsObject]) -> None:
        """Remove position plot graphics objects.
        
        Args:
            plot_item: The pyqtgraph PlotItem
            graphics_objects: List of GraphicsObject items to remove
        """
        for obj in graphics_objects:
            plot_item.removeItem(obj)
            if hasattr(obj, 'setParentItem'):
                obj.setParentItem(None)
    
    def get_detail_bounds(self, interval: pd.DataFrame, detail_data: Any) -> Tuple[float, float, float, float]:
        """Get bounds for the position plot.
        
        Args:
            interval: The interval DataFrame (single row) with 't_start' and 't_duration'
            detail_data: DataFrame with position data
            
        Returns:
            Tuple of (x_min, x_max, y_min, y_max)
        """
        if detail_data is None or len(detail_data) == 0:
            t_start = interval['t_start'].iloc[0] if len(interval) > 0 and 't_start' in interval.columns else 0.0
            t_duration = interval['t_duration'].iloc[0] if len(interval) > 0 and 't_duration' in interval.columns else 1.0
            return (t_start, t_start + t_duration, 0.0, 1.0)
        
        if not isinstance(detail_data, pd.DataFrame):
            t_start = interval['t_start'].iloc[0] if len(interval) > 0 and 't_start' in interval.columns else 0.0
            t_duration = interval['t_duration'].iloc[0] if len(interval) > 0 and 't_duration' in interval.columns else 1.0
            return (t_start, t_start + t_duration, 0.0, 1.0)
        
        t_start = interval['t_start'].iloc[0] if len(interval) > 0 and 't_start' in interval.columns else 0.0
        t_duration = interval['t_duration'].iloc[0] if len(interval) > 0 and 't_duration' in interval.columns else 1.0
        t_end = t_start + t_duration
        
        if self.y_column is not None and self.y_column in detail_data.columns:
            # 2D position: bounds are x and y ranges
            x_min, x_max = detail_data['x'].min(), detail_data['x'].max()
            y_min, y_max = detail_data[self.y_column].min(), detail_data[self.y_column].max()
            # Add padding
            x_pad = (x_max - x_min) * 0.1 if x_max > x_min else 1.0
            y_pad = (y_max - y_min) * 0.1 if y_max > y_min else 1.0
            return (x_min - x_pad, x_max + x_pad, y_min - y_pad, y_max + y_pad)
        else:
            # 1D position: x vs time
            x_min, x_max = detail_data['x'].min(), detail_data['x'].max()
            x_pad = (x_max - x_min) * 0.1 if x_max > x_min else 1.0
            return (t_start, t_end, x_min - x_pad, x_max + x_pad)


# ==================================================================================================================================================================================================================================================================================== #
# PositionTrackDatasource                                                                                                                                                                                                                                                                   #
# ==================================================================================================================================================================================================================================================================================== #

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


__all__ = ['PositionPlotDetailRenderer', 'PositionTrackDatasource']

