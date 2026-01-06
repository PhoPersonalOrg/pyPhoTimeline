 
from __future__ import annotations # prevents having to specify types for typehinting as strings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    ## typehinting only imports here
    from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import IntervalPlotDetailRenderer


"""TrackDatasource and DetailRenderer protocols for timeline track rendering.

This module defines the protocols for datasources that provide both overview intervals
and detailed data that can be fetched asynchronously when intervals scroll into view.
"""
from typing import Protocol, Optional, Tuple, List, Any, runtime_checkable
from abc import ABC, abstractmethod
import pandas as pd
from qtpy import QtCore

from pypho_timeline.rendering.datasources.interval_datasource import IntervalsDatasource
import pyphoplacecellanalysis.External.pyqtgraph as pg




class DetailRenderer(Protocol):
    """Protocol for rendering detailed data within an interval.
    
    Implementations should render detailed views (plots, thumbnails, etc.) that overlay
    on top of the overview interval rectangles when detailed data is loaded.
    """
    
    def render_detail(self, plot_item: pg.PlotItem, interval: pd.DataFrame, detail_data: Any) -> List[pg.GraphicsObject]:
        """Render detailed view for an interval.
        
        Args:
            plot_item: The pyqtgraph PlotItem to render into
            interval: The interval DataFrame (single row) with at least 't_start' and 't_duration' columns
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
    
    def get_detail_bounds(self, interval: pd.DataFrame, detail_data: Any) -> Tuple[float, float, float, float]:
        """Get the bounds for the detailed view.
        
        Args:
            interval: The interval DataFrame (single row) with at least 't_start' and 't_duration' columns
            detail_data: The detailed data for this interval
            
        Returns:
            Tuple of (x_min, x_max, y_min, y_max) defining the bounds of the detail view
        """
        ...


@runtime_checkable
class TrackDatasource(Protocol):
    """Protocol for track datasources that provide overview intervals and detailed data.
    
    Extends IntervalsDatasource to add methods for fetching detailed data asynchronously
    and providing a renderer for the detailed view.
    
    **Required Methods** (must be implemented):
        - `df` property: Returns the DataFrame containing interval data
        - `time_column_names` property: Returns list of time-related column names
        - `total_df_start_end_times` property: Returns (start, end) tuple for entire dataset
        - `get_updated_data_window(new_start, new_end)`: Returns intervals in time window
        - `fetch_detailed_data(interval)`: Fetches detailed data for an interval (thread-safe)
        - `get_detail_renderer()`: Returns DetailRenderer instance for this track type
    
    **Optional Methods** (have default implementations in BaseTrackDatasource):
        - `get_overview_intervals()`: Returns overview interval data (defaults to `df`)
        - `get_detail_cache_key(interval)`: Returns unique cache key (defaults to time-based key)
        - `update_visualization_properties(function)`: Updates visualization columns
    
    **Required Attributes**:
        - `custom_datasource_name`: str - Name identifier for this datasource
        - `source_data_changed_signal`: QtCore.Signal - Signal emitted when data changes
    """
    
    # Required attributes (from IntervalsDatasource)
    custom_datasource_name: str
    source_data_changed_signal: QtCore.Signal
    
    # Required properties (from IntervalsDatasource)
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
    
    # Required methods (from IntervalsDatasource)
    def get_updated_data_window(self, new_start: float, new_end: float) -> pd.DataFrame:
        """Returns the subset of intervals that overlap with the given time window"""
        ...
    
    def update_visualization_properties(self, dataframe_vis_columns_function):
        """Updates visualization columns in the dataframe"""
        ...
    
    # Required methods for track rendering
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
    
    # Optional method (has default implementation in BaseTrackDatasource)
    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get a unique cache key for an interval's detailed data.
        
        Args:
            interval: Series with at least 't_start' and 't_duration' columns
            
        Returns:
            String key that uniquely identifies this interval's detailed data
        """
        ...


class BaseTrackDatasource(ABC):
    """Abstract base class implementing the TrackDatasource protocol.
    
    This class provides a concrete implementation that datasources can inherit from,
    with default implementations for common methods. Subclasses must implement the
    abstract methods marked with @abstractmethod.
    
    **Required Methods to Implement** (abstract):
        - `df` property: Returns the DataFrame containing interval data
        - `time_column_names` property: Returns list of time-related column names
        - `total_df_start_end_times` property: Returns (start, end) tuple for entire dataset
        - `get_updated_data_window(new_start, new_end)`: Returns intervals in time window
        - `fetch_detailed_data(interval)`: Fetches detailed data for an interval (thread-safe)
        - `get_detail_renderer()`: Returns DetailRenderer instance for this track type
    
    **Default Implementations Provided**:
        - `get_overview_intervals()`: Returns `df` property by default
        - `get_detail_cache_key(interval)`: Generates key from `t_start` and `t_duration`
        - `update_visualization_properties(function)`: Applies function to dataframe
    
    **Example Usage**:
        ```python
        class MyTrackDatasource(BaseTrackDatasource):
            def __init__(self, data_df):
                super().__init__()
                self._df = data_df
                self.custom_datasource_name = "MyTrack"
            
            @property
            def df(self) -> pd.DataFrame:
                return self._df
            
            @property
            def time_column_names(self) -> list:
                return ['t_start', 't_duration', 't_end']
            
            @property
            def total_df_start_end_times(self) -> Tuple[float, float]:
                # Implement based on your data
                ...
            
            def get_updated_data_window(self, new_start: float, new_end: float) -> pd.DataFrame:
                # Implement filtering logic
                ...
            
            def fetch_detailed_data(self, interval: pd.Series) -> Any:
                # Implement data fetching
                ...
            
            def get_detail_renderer(self) -> DetailRenderer:
                # Return appropriate renderer
                ...
        ```
    """
    
    def __init__(self):
        """Initialize the base datasource with common attributes."""
        self.custom_datasource_name = "BaseTrackDatasource"
        self.source_data_changed_signal = QtCore.Signal()
    
    # Required abstract properties
    @property
    @abstractmethod
    def df(self) -> pd.DataFrame:
        """The dataframe containing interval data with columns ['t_start', 't_duration', ...]"""
        ...
    
    @property
    @abstractmethod
    def time_column_names(self) -> list:
        """The names of time-related columns (e.g., ['t_start', 't_duration', 't_end'])"""
        ...
    
    @property
    @abstractmethod
    def total_df_start_end_times(self) -> Tuple[float, float]:
        """Returns (earliest_time, latest_time) for the entire dataset"""
        ...
    
    # Required abstract methods
    @abstractmethod
    def get_updated_data_window(self, new_start: float, new_end: float) -> pd.DataFrame:
        """Returns the subset of intervals that overlap with the given time window"""
        ...
    
    @abstractmethod
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
    
    @abstractmethod
    def get_detail_renderer(self) -> DetailRenderer:
        """Get the renderer for detailed views of this track type.
        
        Returns:
            A DetailRenderer instance that knows how to render the detailed data
        """
        ...
    
    # Default implementations for optional methods
    def get_overview_intervals(self) -> pd.DataFrame:
        """Get overview interval data for rendering simple rectangles.
        
        Default implementation returns the `df` property. Override if you need
        different overview data or additional processing.
        
        Returns:
            DataFrame with columns ['t_start', 't_duration', ...] and visualization columns
            ['series_vertical_offset', 'series_height', 'pen', 'brush'] if needed.
        """
        return self.df
    
    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get a unique cache key for an interval's detailed data.
        
        Default implementation generates a key from `t_start` and `t_duration`.
        Override if you need a more specific key format.
        
        Args:
            interval: Series with at least 't_start' and 't_duration' columns
            
        Returns:
            String key that uniquely identifies this interval's detailed data
        """
        t_start = interval.get('t_start', 0.0)
        t_duration = interval.get('t_duration', 0.0)
        return f"{self.custom_datasource_name}_{t_start:.6f}_{t_duration:.6f}"
    
    def update_visualization_properties(self, dataframe_vis_columns_function):
        """Updates visualization columns in the dataframe.
        
        Default implementation applies the function to the dataframe. Override if
        you need custom behavior for updating visualization properties.
        
        Args:
            dataframe_vis_columns_function: Function that takes a DataFrame and returns
                a modified DataFrame with updated visualization columns
        """
        # This is a no-op by default since we can't modify the df property directly
        # Subclasses should override this if they need to update visualization properties
        pass


class IntervalProvidingTrackDatasource(BaseTrackDatasource):
    """A TrackDatasource that at the minimum provides time intervals for its data (such as when the recording was started/ended).
    
    Inherits from BaseTrackDatasource and implements all required methods for
    displaying position data with async detail loading.
    """
    
    def __init__(self, intervals_df: pd.DataFrame, detailed_df: Optional[pd.DataFrame]=None, custom_datasource_name: Optional[str]=None, detail_renderer: Optional[IntervalPlotDetailRenderer]=None,
        max_points_per_second: Optional[float]=1000.0, enable_downsampling: bool=True,
        ):
        """Initialize with position data and intervals.
        
        Args:
            intervals_df: DataFrame with columns ['t_start', 't_duration'] for intervals
            detailed_df: DataFrame with columns ['t'] and data columns (optional)
            custom_datasource_name: Custom name for this datasource (optional)
            detail_renderer: Custom detail renderer (optional)
            max_points_per_second: Maximum points per second for downsampling. If None, no downsampling. Default: 1000.0
            enable_downsampling: Whether to enable downsampling. Default: True
        """
        super().__init__()
        self._detail_renderer = detail_renderer
        
        self.detailed_df = detailed_df
        self.intervals_df = intervals_df.copy()
        if custom_datasource_name is None:
            custom_datasource_name = "GenericIntervalTrack"
        self.custom_datasource_name = custom_datasource_name
        
        # Downsampling configuration
        self.max_points_per_second = max_points_per_second
        self.enable_downsampling = enable_downsampling

        # Add visualization columns to intervals
        self.intervals_df['series_vertical_offset'] = 0.0
        self.intervals_df['series_height'] = 1.0
        
        # Create pens and brushes
        color = pg.mkColor('blue')
        color.setAlphaF(0.3)
        pen = pg.mkPen(color, width=1)
        brush = pg.mkBrush(color)
        self.intervals_df['pen'] = [pen] * len(self.intervals_df)
        self.intervals_df['brush'] = [brush] * len(self.intervals_df)


    @property
    def df(self) -> pd.DataFrame:
        return self.intervals_df
    
    @property
    def time_column_names(self) -> list:
        return ['t_start', 't_duration', 't_end']
    
    @property
    def total_df_start_end_times(self) -> tuple:
        if len(self.intervals_df) == 0:
            return (0.0, 1.0)
        t_start = self.intervals_df['t_start'].min()
        t_end = (self.intervals_df['t_start'] + self.intervals_df['t_duration']).max()
        return (t_start, t_end)
    
    def get_updated_data_window(self, new_start: float, new_end: float) -> pd.DataFrame:
        """Get intervals overlapping with time window."""
        mask = (self.intervals_df['t_start'] + self.intervals_df['t_duration'] >= new_start) & \
               (self.intervals_df['t_start'] <= new_end)
        return self.intervals_df[mask].copy()
    
    def update_visualization_properties(self, dataframe_vis_columns_function):
        """Update visualization properties."""
        self.intervals_df = dataframe_vis_columns_function(self.intervals_df)
    
    def get_overview_intervals(self) -> pd.DataFrame:
        """Get overview intervals."""
        return self.intervals_df
    

    def fetch_detailed_data(self, interval: pd.Series) -> pd.DataFrame:
        """Fetch position data for an interval with optional downsampling."""
        if self.detailed_df is None:
            return pd.DataFrame()  # Return empty DataFrame if no position data available
        t_start = interval['t_start']
        t_end = t_start + interval['t_duration']
        mask = (self.detailed_df['t'] >= t_start) & (self.detailed_df['t'] < t_end)
        result_df = self.detailed_df[mask].copy()
        
        # Apply downsampling if enabled
        if self.enable_downsampling and (self.max_points_per_second is not None) and (len(result_df) > 0):
            # Calculate target point count based on interval duration
            t_duration: float = interval.get('t_duration', (t_end - t_start))
            max_allowed_points: int = int(t_duration * self.max_points_per_second) ## compute the max allowed points in the current interval
            curr_df_points_per_sec: float = float(len(result_df['t']))/t_duration

            # Only downsample if we have more points than target
            if len(result_df) > max_allowed_points:
                from pypho_timeline.utils.downsampling import downsample_dataframe
                result_df = downsample_dataframe(result_df, max_points=max_allowed_points, time_col='t')
                curr_downsampled_points_per_sec = float(len(result_df['t']))/t_duration

        return result_df
    

    def get_detail_renderer(self):
        """Get detail renderer for position data."""
        if self._detail_renderer is None:
            from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import IntervalPlotDetailRenderer
            if self.detailed_df is None:
                return IntervalPlotDetailRenderer(pen_color='cyan', pen_width=2)
            return IntervalPlotDetailRenderer(pen_color='cyan', pen_width=2)
        else:
            # if self.detailed_df is None:
            #     return IntervalPlotDetailRenderer(pen_color='cyan', pen_width=2)
            # return IntervalPlotDetailRenderer(pen_color='cyan', pen_width=2)
            return self._detail_renderer


            
    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get cache key for interval."""
        return f"{self.custom_datasource_name}_{interval['t_start']:.3f}_{interval['t_duration']:.3f}"


__all__ = ['TrackDatasource', 'DetailRenderer', 'BaseTrackDatasource', 'IntervalProvidingTrackDatasource']

