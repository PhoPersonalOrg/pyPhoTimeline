 
from __future__ import annotations # prevents having to specify types for typehinting as strings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    ## typehinting only imports here
    from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import IntervalPlotDetailRenderer


"""TrackDatasource and DetailRenderer protocols for timeline track rendering.

This module defines the protocols for datasources that provide both overview intervals
and detailed data that can be fetched asynchronously when intervals scroll into view.
"""
from typing import Protocol, Optional, Tuple, List, Any, Union, runtime_checkable
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import pandas as pd
from qtpy import QtCore

from pypho_timeline.rendering.datasources.interval_datasource import IntervalsDatasource
import pyqtgraph as pg
from pypho_timeline.utils.datetime_helpers import unix_timestamp_to_datetime
from pypho_timeline.utils.logging_util import get_rendering_logger, _format_interval_for_log, _format_time_value_for_log, _format_duration_value_for_log

logger = get_rendering_logger(__name__)



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
    def total_df_start_end_times(self) -> Union[Tuple[float, float], Tuple[datetime, datetime], Tuple[pd.Timestamp, pd.Timestamp]]:
        """Returns (earliest_time, latest_time) for the entire dataset"""
        ...
    
    # Required methods (from IntervalsDatasource)
    def get_updated_data_window(self, new_start: Union[float, datetime, pd.Timestamp], new_end: Union[float, datetime, pd.Timestamp]) -> pd.DataFrame:
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


class BaseTrackDatasource(QtCore.QObject):
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
    source_data_changed_signal = QtCore.Signal()

    def __init__(self, parent: Optional[QtCore.QObject] = None):
        """Initialize the base datasource with common attributes."""
        super().__init__(parent=parent)
        self.custom_datasource_name = "BaseTrackDatasource"
        # self.source_data_changed_signal = QtCore.Signal()
    

    # Required abstract properties
    @property
    def df(self) -> pd.DataFrame:
        """The dataframe containing interval data with columns ['t_start', 't_duration', ...]"""
        raise NotImplementedError(f'Needs override in inheriting class!')
    
    @property
    def time_column_names(self) -> list:
        """The names of time-related columns (e.g., ['t_start', 't_duration', 't_end'])"""
        raise NotImplementedError(f'Needs override in inheriting class!')
    
    @property
    def total_df_start_end_times(self) -> Union[Tuple[float, float], Tuple[datetime, datetime], Tuple[pd.Timestamp, pd.Timestamp]]:
        """Returns (earliest_time, latest_time) for the entire dataset"""
        raise NotImplementedError(f'Needs override in inheriting class!')
    
    # Required abstract methods
    def get_updated_data_window(self, new_start: Union[float, datetime, pd.Timestamp], new_end: Union[float, datetime, pd.Timestamp]) -> pd.DataFrame:
        """Returns the subset of intervals that overlap with the given time window"""
        raise NotImplementedError(f'Needs override in inheriting class!')
    
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
        raise NotImplementedError(f'Needs override in inheriting class!')

    def get_detail_renderer(self) -> DetailRenderer:
        """Get the renderer for detailed views of this track type.
        
        Returns:
            A DetailRenderer instance that knows how to render the detailed data
        """
        raise NotImplementedError(f'Needs override in inheriting class!')
    
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
        
        Default implementation generates a key from `t_start` and `t_duration`,
        supporting float, datetime, and timedelta types. Override if you need a more specific key format.
        
        Args:
            interval: Series with at least 't_start' and 't_duration' columns

        interval_series: 
            t_start                                                   1773126048.489956
            t_duration                                                      7092.950728
            t_end                                                     1773133141.440685
            series_vertical_offset                                                  0.0
            series_height                                                           1.0
            pen                         <PyQt5.QtGui.QPen object at 0x000002783F9EF610>
            brush                     <PyQt5.QtGui.QBrush object at 0x000002783F9EF5A0>
            t_start_dt                                       2026-03-10 07:00:48.489956
            t_end_dt                                         2026-03-10 08:59:01.440685

            
        Returns:
            String key that uniquely identifies this interval's detailed data
        """
        t_start = interval.get('t_start', 0.0)
        t_duration = interval.get('t_duration', 0.0)
        if hasattr(t_start, 'item'):
            try:
                t_start = t_start.item()
            except (ValueError, AttributeError):
                pass
        if hasattr(t_duration, 'item'):
            try:
                t_duration = t_duration.item()
            except (ValueError, AttributeError):
                pass
        if isinstance(t_start, (datetime, pd.Timestamp)):
            t_start_str = f"{t_start.timestamp():.6f}"
        else:
            try:
                ts = pd.Timestamp(t_start)
                t_start_str = f"{ts.timestamp():.6f}"
            except (ValueError, TypeError, AttributeError):
                try:
                    t_start_str = f"{float(t_start):.6f}"
                except (ValueError, TypeError):
                    t_start_str = str(t_start).replace(' ', '_').replace(':', '-').replace('/', '-')
        if isinstance(t_duration, (timedelta, pd.Timedelta)):
            t_duration_str = f"{t_duration.total_seconds():.6f}"
        else:
            try:
                td = pd.Timedelta(t_duration)
                t_duration_str = f"{td.total_seconds():.6f}"
            except (ValueError, TypeError, AttributeError):
                try:
                    t_duration_str = f"{float(t_duration):.6f}"
                except (ValueError, TypeError):
                    t_duration_str = str(t_duration).replace(' ', '_').replace(':', '-').replace('/', '-')
        cache_key: str =  f"{self.custom_datasource_name}_{t_start_str}_{t_duration_str}"
        logger.info(f"\tBaseTrackDatasource.get_detail_cache_key(interval: {interval}) -> cache_key='{cache_key}'")
        return cache_key


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
    source_data_changed_signal = QtCore.Signal()
    
    def __init__(self, intervals_df: pd.DataFrame, detailed_df: Optional[pd.DataFrame]=None, custom_datasource_name: Optional[str]=None, detail_renderer: Optional[IntervalPlotDetailRenderer]=None,
            max_points_per_second: Optional[float]=1000.0, enable_downsampling: bool=True, parent: Optional[QtCore.QObject] = None,
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
        super().__init__(parent=parent)
        self._detail_renderer = detail_renderer
        
        self.detailed_df = detailed_df
        
        if ('t_start_dt' not in intervals_df) or ('t_end_dt' not in intervals_df):
            intervals_df['t_start_dt'] = intervals_df['t_start'].map(lambda x: unix_timestamp_to_datetime(x))
            if 't_end' in intervals_df.columns:
                intervals_df['t_end_dt'] = intervals_df['t_end'].map(lambda x: unix_timestamp_to_datetime(x))
            elif 't_duration' in intervals_df.columns:
                intervals_df['t_end_dt'] = intervals_df['t_start_dt'] + pd.to_timedelta(intervals_df['t_duration'], unit='s')
            else:
                raise ValueError("intervals_df must have either 't_end' or 't_duration' to compute t_end_dt")
            # Change column type to datetime64[ns] for columns: 't_start_dt', 't_end_dt' -- this is so they can be matched against `detailed_df['t']`
            intervals_df = intervals_df.astype({'t_start_dt': 'datetime64[ns]', 't_end_dt': 'datetime64[ns]'})

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
        color = pg.mkColor('grey')
        color.setAlphaF(0.7)
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
            # Return appropriate default based on expected type
            # Check if we have datetime columns elsewhere, or default to float
            return (0.0, 1.0)
        
        t_start = self.intervals_df['t_start'].min()
        
        # Check if t_start is datetime-like
        is_datetime = pd.api.types.is_datetime64_any_dtype(self.intervals_df['t_start'])
        
        if is_datetime:
            # Use timedelta for duration
            t_end = (self.intervals_df['t_start'] + pd.to_timedelta(self.intervals_df['t_duration'], unit='s')).max()
            return (t_start, t_end)
        else:
            # Use float arithmetic
            t_end = (self.intervals_df['t_start'] + self.intervals_df['t_duration']).max()
            return (float(t_start), float(t_end))
    
    def get_updated_data_window(self, new_start: Union[float, datetime, pd.Timestamp], new_end: Union[float, datetime, pd.Timestamp]) -> pd.DataFrame:
        """Get intervals overlapping with time window."""
        # Check if DataFrame uses datetime columns
        is_datetime = pd.api.types.is_datetime64_any_dtype(self.intervals_df['t_start'])
        
        # Convert inputs to match DataFrame dtype
        if is_datetime:
            # Convert float inputs to datetime
            if isinstance(new_start, (int, float)):
                # Assume Unix timestamp if float
                new_start = pd.Timestamp.fromtimestamp(new_start, tz='UTC')
            elif not isinstance(new_start, (datetime, pd.Timestamp)):
                new_start = pd.Timestamp(new_start)
            
            if isinstance(new_end, (int, float)):
                new_end = pd.Timestamp.fromtimestamp(new_end, tz='UTC')
            elif not isinstance(new_end, (datetime, pd.Timestamp)):
                new_end = pd.Timestamp(new_end)
            
            # Ensure timezone-aware
            if isinstance(new_start, datetime) and new_start.tzinfo is None:
                new_start = pd.Timestamp(new_start).tz_localize('UTC')
            if isinstance(new_end, datetime) and new_end.tzinfo is None:
                new_end = pd.Timestamp(new_end).tz_localize('UTC')
            
            # Calculate t_end for each interval using timedelta
            t_end_col = self.intervals_df['t_start'] + pd.to_timedelta(self.intervals_df['t_duration'], unit='s')
        else:
            # Convert datetime inputs to float (Unix timestamp)
            if isinstance(new_start, (datetime, pd.Timestamp)):
                new_start = new_start.timestamp() if hasattr(new_start, 'timestamp') else pd.Timestamp(new_start).timestamp()
            if isinstance(new_end, (datetime, pd.Timestamp)):
                new_end = new_end.timestamp() if hasattr(new_end, 'timestamp') else pd.Timestamp(new_end).timestamp()
            
            # Use float arithmetic
            t_end_col = self.intervals_df['t_start'] + self.intervals_df['t_duration']
        
        mask = (t_end_col >= new_start) & (self.intervals_df['t_start'] <= new_end)
        return self.intervals_df[mask].copy()
    
    def update_visualization_properties(self, dataframe_vis_columns_function):
        """Update visualization properties."""
        self.intervals_df = dataframe_vis_columns_function(self.intervals_df)
    
    def get_overview_intervals(self) -> pd.DataFrame:
        """Get overview intervals."""
        return self.intervals_df
    

    def fetch_detailed_data(self, interval: pd.Series) -> pd.DataFrame:
        """Fetch position data for an interval with optional downsampling.
        # BUG 2026-02-06 21:48: - [ ] BUG IS FOR SURE HERE 
        """
        if self.detailed_df is None:
            return pd.DataFrame()  # Return empty DataFrame if no position data available
        
        t_start_col_name: str = 't_start_dt'
        t_end_col_name: str = 't_end_dt'


        # t_start = interval['t_start']
        t_start = interval[t_start_col_name]        
        t_end = interval[t_end_col_name]

        # Check if using datetime in intervals_df
        intervals_is_datetime = pd.api.types.is_datetime64_any_dtype(self.intervals_df[t_start_col_name])
        
        # Check if detailed_df 't' column is datetime
        detailed_is_datetime = False
        if 't' in self.detailed_df.columns:
            detailed_is_datetime = pd.api.types.is_datetime64_any_dtype(self.detailed_df['t'])
        
        # # Calculate t_end based on intervals_df type
        # if intervals_is_datetime:
        #     t_end = t_start + pd.to_timedelta(interval['t_duration'], unit='s')
        # else:
        #     t_end = t_start + interval['t_duration']

        
        # Ensure t_start and t_end match the dtype of detailed_df['t'] for comparison
        if 't' in self.detailed_df.columns:
            # if detailed_is_datetime:
            #     # Check if detailed_df['t'] is timezone-aware and get its timezone
            #     detailed_tz = None
            #     detailed_tz_aware = False
            #     # Check dtype first (for DatetimeTZDtype)
            #     if hasattr(self.detailed_df['t'].dtype, 'tz') and self.detailed_df['t'].dtype.tz is not None:
            #         detailed_tz = self.detailed_df['t'].dtype.tz
            #         detailed_tz_aware = True
            #     else:
            #         # Check by sampling a value (for regular datetime64 that might have timezone-aware values)
            #         try:
            #             if len(self.detailed_df) > 0:
            #                 sample_val = self.detailed_df['t'].iloc[0]
            #                 if isinstance(sample_val, pd.Timestamp) and sample_val.tz is not None:
            #                     detailed_tz = sample_val.tz
            #                     detailed_tz_aware = True
            #         except (IndexError, AttributeError, TypeError):
            #             pass
                
            #     # Convert t_start and t_end to datetime if they're not already
            #     if not isinstance(t_start, (datetime, pd.Timestamp)):
            #         if isinstance(t_start, (int, float)):
            #             if detailed_tz_aware and detailed_tz is not None:
            #                 t_start = pd.Timestamp.fromtimestamp(t_start, tz=detailed_tz)
            #             else:
            #                 t_start = pd.Timestamp.fromtimestamp(t_start)
            #         else:
            #             t_start = pd.Timestamp(t_start)
            #             # After conversion, ensure timezone matches
            #             if detailed_tz_aware and detailed_tz is not None:
            #                 if t_start.tzinfo is None:
            #                     t_start = t_start.tz_localize(detailed_tz)
            #                 elif t_start.tzinfo != detailed_tz:
            #                     t_start = t_start.tz_convert(detailed_tz)
            #             else:
            #                 if t_start.tzinfo is not None:
            #                     t_start = t_start.tz_convert('UTC').tz_localize(None)
            #     else:
            #         # Ensure timezone awareness matches detailed_df
            #         if detailed_tz_aware and detailed_tz is not None:
            #             if t_start.tzinfo is None:
            #                 t_start = t_start.tz_localize(detailed_tz)
            #             elif t_start.tzinfo != detailed_tz:
            #                 t_start = t_start.tz_convert(detailed_tz)
            #         else:
            #             if t_start.tzinfo is not None:
            #                 # Convert to UTC then remove timezone to make it naive
            #                 t_start = t_start.tz_convert('UTC').tz_localize(None)
                
            #     if not isinstance(t_end, (datetime, pd.Timestamp)):
            #         if isinstance(t_end, (int, float)):
            #             if detailed_tz_aware and detailed_tz is not None:
            #                 t_end = pd.Timestamp.fromtimestamp(t_end, tz=detailed_tz)
            #             else:
            #                 t_end = pd.Timestamp.fromtimestamp(t_end)
            #         else:
            #             t_end = pd.Timestamp(t_end)
            #             # After conversion, ensure timezone matches
            #             if detailed_tz_aware and detailed_tz is not None:
            #                 if t_end.tzinfo is None:
            #                     t_end = t_end.tz_localize(detailed_tz)
            #                 elif t_end.tzinfo != detailed_tz:
            #                     t_end = t_end.tz_convert(detailed_tz)
            #             else:
            #                 if t_end.tzinfo is not None:
            #                     t_end = t_end.tz_convert('UTC').tz_localize(None)
            #     else:
            #         # Ensure timezone awareness matches detailed_df
            #         if detailed_tz_aware and detailed_tz is not None:
            #             if t_end.tzinfo is None:
            #                 t_end = t_end.tz_localize(detailed_tz)
            #             elif t_end.tzinfo != detailed_tz:
            #                 t_end = t_end.tz_convert(detailed_tz)
            #         else:
            #             if t_end.tzinfo is not None:
            #                 # Convert to UTC then remove timezone to make it naive
            #                 t_end = t_end.tz_convert('UTC').tz_localize(None)
            # else:
            #     # Convert t_start and t_end to float if they're datetime
            #     if isinstance(t_start, (datetime, pd.Timestamp)):
            #         t_start = t_start.timestamp() if hasattr(t_start, 'timestamp') else pd.Timestamp(t_start).timestamp()
            #     if isinstance(t_end, (datetime, pd.Timestamp)):
            #         t_end = t_end.timestamp() if hasattr(t_end, 'timestamp') else pd.Timestamp(t_end).timestamp()
            
            mask = (self.detailed_df['t'] >= t_start) & (self.detailed_df['t'] < t_end)
        else:
            mask = pd.Series([False] * len(self.detailed_df))
        
        result_df = self.detailed_df[mask].copy()
        
        # Apply downsampling if enabled
        if self.enable_downsampling and (self.max_points_per_second is not None) and (len(result_df) > 0):
            raw_duration = interval.get('t_duration', (t_end - t_start))
            if isinstance(raw_duration, (timedelta, pd.Timedelta)):
                t_duration_sec: float = raw_duration.total_seconds()
            else:
                t_duration_sec = float(raw_duration)
            print(f't_duration_sec: {t_duration_sec}')
            max_allowed_points: int = int(t_duration_sec * self.max_points_per_second)
            curr_df_points_per_sec: float = float(len(result_df['t'])) / t_duration_sec
            print(f'curr_df_points_per_sec: {curr_df_points_per_sec}')
            if len(result_df) > max_allowed_points:
                from pypho_timeline.utils.downsampling import downsample_dataframe
                result_df = downsample_dataframe(result_df, max_points=max_allowed_points, time_col='t')
                curr_downsampled_points_per_sec = float(len(result_df['t'])) / t_duration_sec
                print(f'curr_downsampled_points_per_sec: {curr_downsampled_points_per_sec}')

        print(f'result_df')
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
        # Extract values from Series - use .iloc[0] if it's a single-row DataFrame converted to Series
        # or direct access if it's already a Series
        active_t_start = None
        if isinstance(interval, pd.Series):
            t_start_dt = interval.get('t_start_dt', interval.iloc[0] if 't_start_dt' in interval.index else None)
            active_t_start = t_start_dt
            if t_start_dt is None:
                t_start = interval.get('t_start', interval.iloc[0] if 't_start' in interval.index else None)
                active_t_start = t_start
            t_duration = interval.get('t_duration', interval.iloc[0] if 't_duration' in interval.index else None)
        else:
            # Fallback for DataFrame row
            t_start_dt = interval.get('t_start_dt') if hasattr(interval, 'get') else interval['t_start_dt'] ## #TODO 2026-02-28 14:59: - [ ] this one might fail if the column doesn't exist
            active_t_start = t_start_dt
            if active_t_start is None:
                t_start = interval.get('t_start') if hasattr(interval, 'get') else interval['t_start']
                active_t_start = t_start

            t_duration = interval.get('t_duration') if hasattr(interval, 'get') else interval['t_duration']
        
        assert active_t_start is not None
        # Convert pandas scalars/numpy types to Python native types
        # This is critical for proper type checking and formatting
        if hasattr(active_t_start, 'item'):
            try:
                active_t_start = active_t_start.item()
            except (ValueError, AttributeError):
                pass  # Not a scalar, keep as-is
        if hasattr(t_duration, 'item'):
            try:
                t_duration = t_duration.item()
            except (ValueError, AttributeError):
                pass  # Not a scalar, keep as-is
        
        # Handle datetime objects in cache key - check datetime types first
        t_start_str = None
        try:
            # Check if it's a datetime/Timestamp
            if isinstance(active_t_start, (datetime, pd.Timestamp)):
                timestamp_value = active_t_start.timestamp()
                # t_start_str = f"{timestamp_value:.3f}"
                t_start_str = str(timestamp_value)
            else:
                # Try to convert to Timestamp (handles string dates, numpy datetime64, etc.)
                try:
                    ts = pd.Timestamp(active_t_start)
                    # t_start_str = f"{ts.timestamp():.3f}"
                    t_start_str = str(ts.timestamp())
                except (ValueError, TypeError, AttributeError):
                    # Not a datetime, try as numeric
                    try:
                        t_start_float = float(active_t_start)
                        # t_start_str = f"{t_start_float:.3f}"
                        t_start_str = str(t_start_float)
                    except (ValueError, TypeError):
                        # Last resort: use string representation
                        t_start_str = str(active_t_start).replace(' ', '_').replace(':', '-').replace('/', '-')
        except Exception as e:
            # Ultimate fallback
            logger.error(f"Error formatting t_start for cache key: {active_t_start} (type: {type(active_t_start)}), error: {e}")
            t_start_str = str(active_t_start).replace(' ', '_').replace(':', '-').replace('/', '-')
        
        # Handle duration/timedelta objects
        t_duration_str = None
        try:
            if isinstance(t_duration, timedelta):
                t_duration_str = f"{t_duration.total_seconds()}"
            elif isinstance(t_duration, pd.Timedelta):
                t_duration_str = f"{t_duration.total_seconds()}"
            else:
                # Try to convert to Timedelta (handles string durations, numpy timedelta64, etc.)
                try:
                    td = pd.Timedelta(t_duration)
                    t_duration_str = f"{td.total_seconds()}"
                except (ValueError, TypeError, AttributeError):
                    # Not a timedelta, try as numeric
                    try:
                        t_duration_float = float(t_duration)
                        t_duration_str = f"{t_duration_float}"
                    except (ValueError, TypeError):
                        # Last resort: use string representation
                        t_duration_str = str(t_duration).replace(' ', '_').replace(':', '-').replace('/', '-')
        except Exception as e:
            # Ultimate fallback
            logger.error(f"Error formatting t_duration for cache key: {t_duration} (type: {type(t_duration)}), error: {e}")
            t_duration_str = str(t_duration).replace(' ', '_').replace(':', '-').replace('/', '-')
        
        result_key = f"{self.custom_datasource_name}_{t_start_str}_{t_duration_str}"
        return result_key


    @classmethod
    def from_multiple_sources(cls, intervals_dfs: List[pd.DataFrame], detailed_dfs: Optional[List[pd.DataFrame]] = None, custom_datasource_name: Optional[str] = None, detail_renderer: Optional['DetailRenderer'] = None, max_points_per_second: Optional[float] = 1000.0, enable_downsampling: bool = True) -> 'IntervalProvidingTrackDatasource':
        """Create an IntervalProvidingTrackDatasource by merging data from multiple sources.
        
        Args:
            intervals_dfs: List of interval DataFrames to merge (each with columns ['t_start', 't_duration'])
            detailed_dfs: Optional list of detailed DataFrames to merge (each with column 't' and data columns)
            custom_datasource_name: Custom name for this datasource (optional)
            detail_renderer: Custom detail renderer (optional)
            max_points_per_second: Maximum points per second for downsampling. If None, no downsampling. Default: 1000.0
            enable_downsampling: Whether to enable downsampling. Default: True
            
        Returns:
            IntervalProvidingTrackDatasource instance with merged data
        """
        if not intervals_dfs:
            raise ValueError("intervals_dfs list cannot be empty")
        
        # Merge intervals
        merged_intervals_df = pd.concat(intervals_dfs, ignore_index=True).sort_values('t_start')
        
        # Merge detailed data if provided
        merged_detailed_df = None
        if detailed_dfs:
            filtered_detailed_dfs = [df for df in detailed_dfs if df is not None and len(df) > 0]
            if filtered_detailed_dfs:
                merged_detailed_df = pd.concat(filtered_detailed_dfs, ignore_index=True).sort_values('t')
        
        # Create instance with merged data
        return cls(
            intervals_df=merged_intervals_df,
            detailed_df=merged_detailed_df,
            custom_datasource_name=custom_datasource_name,
            detail_renderer=detail_renderer,
            max_points_per_second=max_points_per_second,
            enable_downsampling=enable_downsampling
        )


__all__ = ['TrackDatasource', 'DetailRenderer', 'BaseTrackDatasource', 'IntervalProvidingTrackDatasource']

