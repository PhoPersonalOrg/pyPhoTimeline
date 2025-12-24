"""TrackDatasource and DetailRenderer protocols for timeline track rendering.

This module defines the protocols for datasources that provide both overview intervals
and detailed data that can be fetched asynchronously when intervals scroll into view.
"""
from typing import Protocol, Optional, Tuple, List, Any
import pandas as pd
from qtpy import QtCore

from pypho_timeline.rendering.datasources.interval_datasource import IntervalsDatasource
import pyphoplacecellanalysis.External.pyqtgraph as pg


class DetailRenderer(Protocol):
    """Protocol for rendering detailed data within an interval.
    
    Implementations should render detailed views (plots, thumbnails, etc.) that overlay
    on top of the overview interval rectangles when detailed data is loaded.
    """
    
    def render_detail(self, plot_item: pg.PlotItem, interval: pd.Series, detail_data: Any) -> List[pg.GraphicsObject]:
        """Render detailed view for an interval.
        
        Args:
            plot_item: The pyqtgraph PlotItem to render into
            interval: The interval Series with at least 't_start' and 't_duration' columns
            detail_data: The detailed data fetched for this interval (type depends on track type)
            
        Returns:
            List of GraphicsObject items that were added to the plot (for cleanup later)
        """
        ...
    
    def clear_detail(self, plot_item: pg.PlotItem, graphics_objects: List[pg.GraphicsObject]) -> None:
        """Clear/remove detailed view graphics objects.
        
        Args:
            plot_item: The pyqtgraph PlotItem containing the graphics
            graphics_objects: List of GraphicsObject items to remove (from previous render_detail call)
        """
        ...
    
    def get_detail_bounds(self, interval: pd.Series, detail_data: Any) -> Tuple[float, float, float, float]:
        """Get the bounds for the detailed view.
        
        Args:
            interval: The interval Series with at least 't_start' and 't_duration' columns
            detail_data: The detailed data for this interval
            
        Returns:
            Tuple of (x_min, x_max, y_min, y_max) defining the bounds of the detail view
        """
        ...


class TrackDatasource(Protocol):
    """Protocol for track datasources that provide overview intervals and detailed data.
    
    Extends IntervalsDatasource to add methods for fetching detailed data asynchronously
    and providing a renderer for the detailed view.
    """
    
    # Inherit from IntervalsDatasource
    custom_datasource_name: str
    source_data_changed_signal: QtCore.Signal
    
    @property
    def df(self) -> pd.DataFrame:
        """The dataframe containing interval data with columns ['t_start', 't_duration', ...]"""
        ...
    
    @property
    def time_column_names(self) -> list:
        """The names of time-related columns (e.g., ['t_start', 't_duration', 't_end'])"""
        ...
    
    @property
    def total_df_start_end_times(self) -> Tuple[float, float]:
        """Returns (earliest_time, latest_time) for the entire dataset"""
        ...
    
    def get_updated_data_window(self, new_start: float, new_end: float) -> pd.DataFrame:
        """Returns the subset of intervals that overlap with the given time window"""
        ...
    
    def update_visualization_properties(self, dataframe_vis_columns_function):
        """Updates visualization columns in the dataframe"""
        ...
    
    # New methods for track rendering
    def get_overview_intervals(self) -> pd.DataFrame:
        """Get overview interval data for rendering simple rectangles.
        
        Returns:
            DataFrame with columns ['t_start', 't_duration', ...] and visualization columns
            ['series_vertical_offset', 'series_height', 'pen', 'brush'] if needed.
        """
        ...
    
    def fetch_detailed_data(self, interval: pd.Series) -> Any:
        """Fetch detailed data for a specific interval (synchronous, called from worker thread).
        
        This method will be called from a worker thread, so it should be thread-safe.
        It should not perform any GUI operations.
        
        Args:
            interval: Series with at least 't_start' and 't_duration' columns
            
        Returns:
            Detailed data for this interval (type depends on track type, e.g., DataFrame for position,
            image array for video, etc.)
        """
        ...
    
    def get_detail_renderer(self) -> DetailRenderer:
        """Get the renderer for detailed views of this track type.
        
        Returns:
            A DetailRenderer instance that knows how to render the detailed data
        """
        ...
    
    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get a unique cache key for an interval's detailed data.
        
        Args:
            interval: Series with at least 't_start' and 't_duration' columns
            
        Returns:
            String key that uniquely identifies this interval's detailed data
        """
        ...


__all__ = ['TrackDatasource', 'DetailRenderer']

