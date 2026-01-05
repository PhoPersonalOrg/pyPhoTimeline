"""GenericPlotDetailRenderer - Generic renderer for arbitrary plot data."""
from typing import List, Tuple, Any, Callable, Optional
import numpy as np
import pandas as pd
import pyphoplacecellanalysis.External.pyqtgraph as pg

from pypho_timeline.rendering.datasources.track_datasource import DetailRenderer

class GenericPlotDetailRenderer(DetailRenderer):
    """Generic detail renderer that uses a custom render function.
    
    This renderer allows users to provide their own rendering function for
    custom track types.

    from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import GenericPlotDetailRenderer

    """
    
    def __init__(self, render_fn: Callable[[pg.PlotItem, pd.Series, Any], List[pg.GraphicsObject]],
                 clear_fn: Optional[Callable[[pg.PlotItem, List[pg.GraphicsObject]], None]] = None,
                 bounds_fn: Optional[Callable[[pd.Series, Any], Tuple[float, float, float, float]]] = None):
        """Initialize the generic plot renderer.
        
        Args:
            render_fn: Function that renders detail data and returns list of GraphicsObjects
            clear_fn: Optional function to clear graphics objects (default: removes all items)
            bounds_fn: Optional function to compute detail bounds (default: uses interval bounds)
        """
        self.render_fn = render_fn
        self.clear_fn = clear_fn or self._default_clear
        self.bounds_fn = bounds_fn or self._default_bounds
    
    def render_detail(self, plot_item: pg.PlotItem, interval: pd.Series, detail_data: Any) -> List[pg.GraphicsObject]:
        """Render detail data using the custom render function.
        
        Args:
            plot_item: The pyqtgraph PlotItem to render into
            interval: The interval Series with 't_start' and 't_duration'
            detail_data: The detailed data (type depends on track type)
            
        Returns:
            List of GraphicsObject items added
        """
        return self.render_fn(plot_item, interval, detail_data)
    
    def clear_detail(self, plot_item: pg.PlotItem, graphics_objects: List[pg.GraphicsObject]) -> None:
        """Clear detail graphics using the custom clear function.
        
        Args:
            plot_item: The pyqtgraph PlotItem
            graphics_objects: List of GraphicsObject items to remove
        """
        self.clear_fn(plot_item, graphics_objects)
    
    def get_detail_bounds(self, interval: pd.Series, detail_data: Any) -> Tuple[float, float, float, float]:
        """Get bounds for the detail view using the custom bounds function.
        
        Args:
            interval: The interval Series with 't_start' and 't_duration'
            detail_data: The detailed data
            
        Returns:
            Tuple of (x_min, x_max, y_min, y_max)
        """
        return self.bounds_fn(interval, detail_data)
    
    def _default_clear(self, plot_item: pg.PlotItem, graphics_objects: List[pg.GraphicsObject]) -> None:
        """Default clear function that removes all graphics objects."""
        for obj in graphics_objects:
            plot_item.removeItem(obj)
            if hasattr(obj, 'setParentItem'):
                obj.setParentItem(None)
    
    def _default_bounds(self, interval: pd.Series, detail_data: Any) -> Tuple[float, float, float, float]:
        """Default bounds function that uses interval bounds."""
        t_start = interval.get('t_start', 0.0)
        t_duration = interval.get('t_duration', 1.0)
        t_end = t_start + t_duration
        
        y_offset = interval.get('series_vertical_offset', 0.0)
        y_height = interval.get('series_height', 1.0)
        
        return (t_start, t_end, y_offset, y_offset + y_height)

"""IntervalPlotDetailRenderer - Renders position data as line plots."""
## TODO: should inherit from `GenericPlotDetailRenderer`
class IntervalPlotDetailRenderer(DetailRenderer):
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
            raise TypeError(f"IntervalPlotDetailRenderer expects DataFrame, got {type(detail_data)}")
        
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



__all__ = ['GenericPlotDetailRenderer', 'IntervalPlotDetailRenderer']

