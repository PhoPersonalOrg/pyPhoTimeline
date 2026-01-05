"""GenericPlotDetailRenderer - Generic renderer for arbitrary plot data."""
from typing import List, Tuple, Any, Callable, Optional
import numpy as np
import pandas as pd
import pyphoplacecellanalysis.External.pyqtgraph as pg

from pypho_timeline.rendering.datasources.track_datasource import DetailRenderer

## TODO: should implement/conform to `DetailRenderer`
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


__all__ = ['GenericPlotDetailRenderer']

