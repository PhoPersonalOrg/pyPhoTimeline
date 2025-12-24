"""PositionPlotDetailRenderer - Renders position data as line plots."""
from typing import List, Tuple, Any
import numpy as np
import pandas as pd
import pyphoplacecellanalysis.External.pyqtgraph as pg

from pypho_timeline.rendering.datasources.track_datasource import DetailRenderer


class PositionPlotDetailRenderer:
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
    
    def render_detail(self, plot_item: pg.PlotItem, interval: pd.Series, detail_data: Any) -> List[pg.GraphicsObject]:
        """Render position data as a line plot.
        
        Args:
            plot_item: The pyqtgraph PlotItem to render into
            interval: The interval Series with 't_start' and 't_duration'
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
    
    def get_detail_bounds(self, interval: pd.Series, detail_data: Any) -> Tuple[float, float, float, float]:
        """Get bounds for the position plot.
        
        Args:
            interval: The interval Series with 't_start' and 't_duration'
            detail_data: DataFrame with position data
            
        Returns:
            Tuple of (x_min, x_max, y_min, y_max)
        """
        if detail_data is None or len(detail_data) == 0:
            t_start = interval.get('t_start', 0.0)
            t_duration = interval.get('t_duration', 1.0)
            return (t_start, t_start + t_duration, 0.0, 1.0)
        
        if not isinstance(detail_data, pd.DataFrame):
            t_start = interval.get('t_start', 0.0)
            t_duration = interval.get('t_duration', 1.0)
            return (t_start, t_start + t_duration, 0.0, 1.0)
        
        t_start = interval.get('t_start', 0.0)
        t_duration = interval.get('t_duration', 1.0)
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


__all__ = ['PositionPlotDetailRenderer']

