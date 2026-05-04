from __future__ import annotations # prevents having to specify types for typehinting as strings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    ## typehinting only imports here
    from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import IntervalPlotDetailRenderer
    from phopymnehelper.xdf_files import LabRecorderXDF


"""TrackDatasource and DetailRenderer protocols for timeline track rendering.

This module defines the protocols for datasources that provide both overview intervals
and detailed data that can be fetched asynchronously when intervals scroll into view.
"""
from typing import Protocol, Optional, Tuple, List, Dict, Any, Union, runtime_checkable
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
from qtpy import QtCore

import mne
from pypho_timeline.rendering.datasources.interval_datasource import IntervalsDatasource
import pypho_timeline.EXTERNAL.pyqtgraph as pg
from pypho_timeline.utils.logging_util import get_rendering_logger, _format_interval_for_log, _format_time_value_for_log, _format_duration_value_for_log
from phopymnehelper.helpers.dataframe_accessor_helpers import MaskedValidDataFrameAccessor
import phopymnehelper.type_aliases as types

logger = get_rendering_logger(__name__)


_UNCHANGED_DOWNSAMPLING = object()


def _first_valid_scalar(series: pd.Series) -> Any:
    valid_values = series.dropna()
    return valid_values.iloc[0] if len(valid_values) > 0 else None


def _series_looks_datetime(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    first_valid = _first_valid_scalar(series)
    return isinstance(first_valid, (datetime, pd.Timestamp, np.datetime64))


def _series_looks_timedelta(series: pd.Series) -> bool:
    if pd.api.types.is_timedelta64_dtype(series):
        return True
    first_valid = _first_valid_scalar(series)
    return isinstance(first_valid, (timedelta, pd.Timedelta, np.timedelta64))


def _normalize_time_series_to_unix_seconds(series: pd.Series) -> pd.Series:
    if _series_looks_datetime(series):
        dt_series = pd.to_datetime(series, utc=True, errors='coerce')
        normalized_series = pd.Series(np.nan, index=series.index, dtype=float)
        valid_mask = dt_series.notna()
        normalized_series.loc[valid_mask] = (dt_series.loc[valid_mask].astype('int64') / 1e9).astype(float)
        return normalized_series
    return pd.to_numeric(series, errors='coerce').astype(float)


def _normalize_duration_series_to_seconds(series: pd.Series) -> pd.Series:
    if _series_looks_timedelta(series):
        td_series = pd.to_timedelta(series, errors='coerce')
        normalized_series = pd.Series(np.nan, index=series.index, dtype=float)
        valid_mask = td_series.notna()
        normalized_series.loc[valid_mask] = td_series.loc[valid_mask].dt.total_seconds().astype(float)
        return normalized_series
    return pd.to_numeric(series, errors='coerce').astype(float)



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
    def get_detail_cache_key(self, interval: Union[pd.Series, pd.DataFrame]) -> str:
        """Get a unique cache key for an interval's detailed data.
        
        Args:
            interval: Single-row DataFrame or Series with at least 't_start' and 't_duration'
            
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
    
    def get_detail_cache_key(self, interval: Union[pd.Series, pd.DataFrame]) -> str:
        """Get a unique cache key for an interval's detailed data.
        
        Default implementation generates a key from `t_start` and `t_duration`,
        supporting float, datetime, and timedelta types. Override if you need a more specific key format.
        
        Args:
            interval: Single-row DataFrame or Series with at least 't_start' and 't_duration'
            
        Returns:
            String key that uniquely identifies this interval's detailed data
        """
        if isinstance(interval, pd.DataFrame):
            interval = interval.iloc[0]
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
        intervals_df = intervals_df.copy()
        if 't_start' in intervals_df.columns:
            intervals_df['t_start'] = _normalize_time_series_to_unix_seconds(intervals_df['t_start'])
        if 't_duration' in intervals_df.columns:
            intervals_df['t_duration'] = _normalize_duration_series_to_seconds(intervals_df['t_duration'])
        if 't_end' in intervals_df.columns:
            intervals_df['t_end'] = _normalize_time_series_to_unix_seconds(intervals_df['t_end'])
        elif ('t_start' in intervals_df.columns) and ('t_duration' in intervals_df.columns):
            intervals_df['t_end'] = intervals_df['t_start'] + intervals_df['t_duration']

        if detailed_df is not None:
            detailed_df = detailed_df.copy()
            if 't' in detailed_df.columns:
                detailed_df['t'] = _normalize_time_series_to_unix_seconds(detailed_df['t'])
        
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
    
    @property
    def num_intervals(self) -> int:
        """The num_sessions property."""
        return len(self.get_overview_intervals())


    def set_downsampling(self, max_points_per_second: Any = _UNCHANGED_DOWNSAMPLING, enable_downsampling: Any = _UNCHANGED_DOWNSAMPLING, *, emit_changed: bool = True) -> bool:
        """Update runtime downsampling settings and optionally emit a refresh signal.

        Returns:
            True when at least one setting changed.

        Usage:
            timeline.track_datasources['EEG_Stream'].set_downsampling(max_points_per_second=50.0)
            timeline.track_datasources['EEG_Stream'].set_downsampling(enable_downsampling=False, max_points_per_second=None)
        """
        did_change = False

        if max_points_per_second is not _UNCHANGED_DOWNSAMPLING:
            normalized_max_points_per_second = None if max_points_per_second is None else float(max_points_per_second)
            if self.max_points_per_second != normalized_max_points_per_second:
                self.max_points_per_second = normalized_max_points_per_second
                did_change = True

        if enable_downsampling is not _UNCHANGED_DOWNSAMPLING:
            normalized_enable_downsampling = bool(enable_downsampling)
            if self.enable_downsampling != normalized_enable_downsampling:
                self.enable_downsampling = normalized_enable_downsampling
                did_change = True

        if did_change and emit_changed:
            self.source_data_changed_signal.emit()

        return did_change


    def fetch_detailed_data(self, interval: pd.Series) -> pd.DataFrame:
        """Fetch position data for an interval with optional downsampling.
        # BUG 2026-02-06 21:48: - [ ] BUG IS FOR SURE HERE 
        """
        if self.detailed_df is None:
            return pd.DataFrame()  # Return empty DataFrame if no position data available

        if 't' not in self.detailed_df.columns:
            mask = pd.Series([False] * len(self.detailed_df))
        else:
            t_start = interval.get('t_start', 0.0)
            t_duration = interval.get('t_duration', 0.0)
            t_end = interval.get('t_end', float(t_start) + float(t_duration))
            if isinstance(t_start, (datetime, pd.Timestamp)):
                t_start = _normalize_time_series_to_unix_seconds(pd.Series([t_start])).iloc[0]
            if isinstance(t_end, (datetime, pd.Timestamp)):
                t_end = _normalize_time_series_to_unix_seconds(pd.Series([t_end])).iloc[0]
            mask = (self.detailed_df['t'] >= float(t_start)) & (self.detailed_df['t'] < float(t_end))
        
        result_df = self.detailed_df[mask].copy()
        result_df = self._post_slice_detailed_dataframe(result_df, interval)
        
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


    def _post_slice_detailed_dataframe(self, result_df: pd.DataFrame, interval: pd.Series) -> pd.DataFrame:
        """Hook for subclasses to filter rows after interval slice and before downsampling."""
        return result_df.masked_df.get_masked(copy=True)
        # return result_df
    

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


            
    def get_detail_cache_key(self, interval: Union[pd.Series, pd.DataFrame]) -> str:
        """Get cache key for interval (single-row DataFrame or Series)."""
        return super().get_detail_cache_key(interval)


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


class RawProvidingTrackDatasource(IntervalProvidingTrackDatasource):
    """A TrackDatasource that holds access to raw MNE objects.

    Inherits from IntervalProvidingTrackDatasource and implements all required methods for
    displaying position data with async detail loading. Subclasses may implement
    :meth:`try_extract_raw_datasets_dict` to populate ``raw_datasets_dict`` from
    :attr:`lab_obj_dict` when the caller passes ``raw_datasets_dict=None``.
    """
    def __init__(self, intervals_df: pd.DataFrame, detailed_df: Optional[pd.DataFrame]=None, custom_datasource_name: Optional[str]=None, detail_renderer: Optional[IntervalPlotDetailRenderer]=None,
            max_points_per_second: Optional[float]=1000.0, enable_downsampling: bool=True,
            lab_obj_dict: Optional[Dict[str, Optional[LabRecorderXDF]]] = None, raw_datasets_dict: Optional[Dict[str, Optional[List[mne.io.Raw]]]] = None,
            parent: Optional[QtCore.QObject] = None,
        ):
        """Initialize with position data and intervals.
        
        Args:
            intervals_df: DataFrame with columns ['t_start', 't_duration'] for intervals
            detailed_df: DataFrame with columns ['t'] and data columns (optional)
            custom_datasource_name: Custom name for this datasource (optional)
            detail_renderer: Custom detail renderer (optional)
            max_points_per_second: Maximum points per second for downsampling. If None, no downsampling. Default: 1000.0
            enable_downsampling: Whether to enable downsampling. Default: True
            lab_obj_dict: Map of source id (e.g. XDF filename) to optional LabRecorderXDF for that file.
            raw_datasets_dict: Map of source id to optional list of MNE Raw objects for that source.
                If ``None``, :meth:`try_extract_raw_datasets_dict` is used (subclass-specific).
        """
        if custom_datasource_name is None:
            custom_datasource_name = "GenericRawProvidingTrack"
        super().__init__(intervals_df, detailed_df=detailed_df, custom_datasource_name=custom_datasource_name, detail_renderer=detail_renderer,
                            max_points_per_second=max_points_per_second, enable_downsampling=enable_downsampling, parent=parent)
        self._lab_obj_dict = dict(lab_obj_dict) if lab_obj_dict is not None else {}
        self._raw_datasets_dict = raw_datasets_dict
        if self._raw_datasets_dict is None:
            self._raw_datasets_dict = self.try_extract_raw_datasets_dict()


    def try_extract_raw_datasets_dict(self) -> Optional[Dict[str, Optional[List[Any]]]]:
        """Build per-source raw lists from :attr:`lab_obj_dict`; base returns ``None``."""
        return None


    @property
    def lab_obj_dict(self) -> Dict[str, Optional[LabRecorderXDF]]:
        """Map of source id (e.g. XDF basename) to optional LabRecorderXDF for that file."""
        return self._lab_obj_dict
    @lab_obj_dict.setter
    def lab_obj_dict(self, value: Optional[Dict[str, Optional[LabRecorderXDF]]]):
        self._lab_obj_dict = dict(value) if value is not None else {}


    @property
    def raw_datasets_dict(self) -> Optional[Dict[str, Optional[List[mne.io.Raw]]]]:
        """Map of source id to optional list of MNE Raw objects; None if never set."""
        return self._raw_datasets_dict
    @raw_datasets_dict.setter
    def raw_datasets_dict(self, value: Optional[Dict[str, Optional[List[mne.io.Raw]]]]):
        self._raw_datasets_dict = value


    @classmethod
    def _flatten_raw_lists_from_dict(cls, raw_datasets_dict: Optional[Dict[str, Optional[List[Any]]]]) -> List[Any]:
        if not raw_datasets_dict:
            return []
        out: List[Any] = []
        for _k in sorted(raw_datasets_dict.keys(), key=lambda x: str(x)):
            v = raw_datasets_dict[_k]
            if v:
                out.extend(v)
        return out


    @classmethod
    def _sort_raws_by_meas_start(cls, raws: Union[List[Any], Dict[str, Any]]) -> Union[List[Any], Dict[str, Any]]:
        """ sorts the list of raws by the meas start """
        def _key(x):
            # allow either raw or (key, raw)
            r = x[1] if isinstance(x, tuple) and len(x) == 2 else x

            if isinstance(r, dict):
                tr_m = r.get("raw_timerange")
                info = r.get("info")
            else:
                tr_m = getattr(r, "raw_timerange", None)
                info = r.info if hasattr(r, "info") else None

            start = None

            if callable(tr_m):
                try:
                    start, _end = tr_m()
                except Exception:
                    start = None

            if start is None and info is not None:
                if hasattr(info, "get"):
                    start = info.get("meas_date")
                else:
                    try:
                        start = info["meas_date"]
                    except (TypeError, KeyError):
                        start = None

            if start is None:
                return True, datetime.max.replace(tzinfo=timezone.utc)

            if getattr(start, "tzinfo", None) is None:
                start = start.replace(tzinfo=timezone.utc)

            return False, start

        # --- only real change is here ---
        if isinstance(raws, dict):
            return dict(sorted(raws.items(), key=_key))
        else:
            return sorted(raws, key=_key)


    @classmethod
    def get_sorted_and_extracted_raws(cls, raw_datasets_dict):
        return cls._sort_raws_by_meas_start(cls._flatten_raw_lists_from_dict(raw_datasets_dict))

    
    @classmethod
    def from_multiple_sources(cls, intervals_dfs: List[pd.DataFrame], detailed_dfs: Optional[List[pd.DataFrame]] = None, custom_datasource_name: Optional[str] = None, detail_renderer: Optional['DetailRenderer'] = None,
                            max_points_per_second: Optional[float] = 1000.0, enable_downsampling: bool = True,
                            lab_obj_dict: Optional[Dict[str, Optional[LabRecorderXDF]]] = None, raw_datasets_dict: Optional[Dict[str, Optional[List[mne.io.Raw]]]] = None, **kwargs) -> 'IntervalProvidingTrackDatasource':
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
            enable_downsampling=enable_downsampling,
            lab_obj_dict=lab_obj_dict, raw_datasets_dict=raw_datasets_dict, **kwargs
        )


    @property
    def earliest_unix_timestamp(self)-> Optional[float]:
        """ gets the earliest timestamp for this datasource in the unix_timestamp format 

        t0: float = eeg_ds.earliest_unix_timestamp
        """
        if self.detailed_df is None:
            return None

        detailed_df: pd.DataFrame = self.detailed_df.sort_values("t").reset_index(drop=True)
        _t = detailed_df['t']
        # print(f"type(_t): {type(_t)}, t: {_t}")
        if pd.api.types.is_datetime64_any_dtype(_t):
            t0 = float(pd.to_datetime(_t, utc=True, errors="coerce").astype(np.int64).iloc[0] / 1e9)
        else:
            t0 = float(pd.to_numeric(_t, errors="coerce").iloc[0])
        # print(f'\tt0: {t0}')
        ## OUTPUTS: t0
        return t0



    def export_all_to_EDF(self, xdf_to_exported_EDF_parent_export_path: Path) -> List[Path]:
        """2026-04-15 - Export loaded sessions to EDF for analysis in other apps
        Exports the `self.raw_datasets_dict` to separate .EDF files


        exported_edf_paths: List[Path] = eeg_ds.export_all_to_EDF(xdf_to_exported_EDF_parent_export_path=xdf_to_exported_EDF_parent_export_path)
        exported_edf_paths

        """
        import mne

        ## INPUTS: xdf_to_exported_EDF_parent_export_path
        assert xdf_to_exported_EDF_parent_export_path is not None
        # xdf_to_exported_EDF_parent_export_path = sso.eeg_analyzed_parent_export_path
        flat_raws: List[mne.io.Raw] = self._flatten_raw_lists_from_dict(self.raw_datasets_dict)
        edf_export_parent_path: Path = xdf_to_exported_EDF_parent_export_path.resolve() # .joinpath("exported_EDF")
        edf_export_parent_path.mkdir(exist_ok=True, parents=True)

        exported_edf_paths: List[Path] = []
        for raw_idx, a_raw in enumerate(flat_raws):
            source_stem = None
            raw_description = a_raw.info.get("description")
            if raw_description:
                try:
                    source_stem = Path(str(raw_description)).stem
                except Exception:
                    source_stem = None

            if not source_stem:
                raw_filenames = getattr(a_raw, "filenames", None)
                if raw_filenames and raw_filenames[0]:
                    source_stem = Path(str(raw_filenames[0])).stem

            if not source_stem:
                source_stem = f"session_{raw_idx:03d}"

            curr_file_edf_path: Path = edf_export_parent_path.joinpath(f"{source_stem}.edf").resolve()
            exported_edf_paths.append(a_raw.save_to_edf(output_path=curr_file_edf_path))

        ## END for raw_idx, a_raw in enumerate(flat_raws)....

        print(f"Exported {len(exported_edf_paths)} EDF file(s) to: {edf_export_parent_path}")
        return exported_edf_paths




class ComputableDatasourceMixin:
    """ implementors are able to recompute their results when a property changes

    from pypho_timeline.rendering.datasources.track_datasource import ComputableDatasourceMixin
    from phopymnehelper.analysis.computations.eeg_registry import run_eeg_computations_graph, session_fingerprint_for_raw_or_path

    """
    sigSourceComputeStarted = QtCore.Signal()
    sigSourceComputeFinished = QtCore.Signal(bool)

    @property
    def computed_result(self) -> Dict[types.EEGComputationId, Any]:
        """The result computed this sources .compute(...) function."""
        return self._computed_result
    @computed_result.setter
    def computed_result(self, value: Dict[types.EEGComputationId, Any]):
        self._computed_result = value


    @property
    def eeg_comps_flat_concat_dict(self):
        """The eeg_comps_flat_concat_dict property."""
        return self.computed_result.get('eeg_comps_flat_concat_dict', None)
    @eeg_comps_flat_concat_dict.setter
    def eeg_comps_flat_concat_dict(self, value):
        self._eeg_comps_flat_concat_dict = value

    def ComputableDatasourceMixin_on_init(self):
        """ perform any parameters setting/checking during init """
        self._computed_result = {} ## init to a dictionary


    def ComputableDatasourceMixin_on_setup(self):
        """ perform setup/creation of widget/graphical/data objects. Only the core objects are expected to exist on the implementor (root widget, etc) """
        pass


    def ComputableDatasourceMixin_on_buildUI(self):
        """ perform setup/creation of widget/graphical/data objects. Only the core objects are expected to exist on the implementor (root widget, etc) """
        pass
    

    def ComputableDatasourceMixin_on_destroy(self):
        """ perform teardown/destruction of anything that needs to be manually removed or released """
        self.clear_computed_result()


    def clear_computed_result(self):
        print(f'clear_computed_result()')
        self.computed_result.clear()


    def compute(self, **kwargs):
        """ a function to perform recomputation of the datasource properties at runtime 

        datasource: EEGSpectrogramTrackDatasource
        datasource = self

        from phopymnehelper.analysis.computations.eeg_registry import run_eeg_computations_graph, session_fingerprint_for_raw_or_path

        active_compute_goals_list = ("time_independent_bad_channels", "bad_epochs",)
        eeg_comps_flat_concat_dict = self.computed_result
        for a_specific_computed_goal_name in active_compute_goals_list:
            if a_specific_computed_goal_name not in eeg_comps_flat_concat_dict:
                eeg_comps_flat_concat_dict[a_specific_computed_goal_name] = [] ## create a list


        for a_sess_xdf_filename, eeg_raw_list in self.raw_datasets_dict.items():
            if eeg_raw_list is not None:
                for eeg_raw in eeg_raw_list:
                    if eeg_raw is not None:
                        # if a_sess_xdf_filename not in eeg_comps_results_dict:
                        #     eeg_comps_results_dict[a_sess_xdf_filename] = []

                        ## do the computation:
                        eeg_comps_result = run_eeg_computations_graph(eeg_raw, session=session_fingerprint_for_raw_or_path(eeg_raw), goals=active_compute_goals_list)
                        # eeg_comps_results_dict[a_sess_xdf_filename].append(eeg_comps_result) ## append to the result

                        for a_specific_computed_goal_name, a_specific_computed_value in eeg_comps_result.items():
                            if a_specific_computed_value is not None:
                                if a_specific_computed_goal_name not in eeg_comps_flat_concat_dict:
                                    eeg_comps_flat_concat_dict[a_specific_computed_goal_name] = []
                                eeg_comps_flat_concat_dict[a_specific_computed_goal_name].append(a_specific_computed_value)

        ## END for a_sess_xdf_filename, eeg_raw_list in self.raw_datasets_dict.items()...

        ## OUTPUTS: eeg_comps_flat_concat_dict



        """
        raise NotImplementedError(f'Implementors must override to perform their computations')

        self.clear_computed_result()
        self.sigSourceComputeStarted.emit()

        active_compute_goals_list = ("time_independent_bad_channels", "bad_epochs",)
        eeg_comps_flat_concat_dict = self.computed_result
        for a_specific_computed_goal_name in active_compute_goals_list:
            if a_specific_computed_goal_name not in eeg_comps_flat_concat_dict:
                eeg_comps_flat_concat_dict[a_specific_computed_goal_name] = [] ## create a list


        for a_sess_xdf_filename, eeg_raw_list in self.raw_datasets_dict.items():
            if eeg_raw_list is not None:
                for eeg_raw in eeg_raw_list:
                    if eeg_raw is not None:
                        # if a_sess_xdf_filename not in eeg_comps_results_dict:
                        #     eeg_comps_results_dict[a_sess_xdf_filename] = []

                        ## do the computation:
                        eeg_comps_result = run_eeg_computations_graph(eeg_raw, session=session_fingerprint_for_raw_or_path(eeg_raw), goals=active_compute_goals_list)
                        # eeg_comps_results_dict[a_sess_xdf_filename].append(eeg_comps_result) ## append to the result

                        ## do basic extraction from result here either way:
                        for a_specific_computed_goal_name, a_specific_computed_value in eeg_comps_result.items():
                            if a_specific_computed_value is not None:
                                if a_specific_computed_goal_name not in eeg_comps_flat_concat_dict:
                                    eeg_comps_flat_concat_dict[a_specific_computed_goal_name] = []
                                eeg_comps_flat_concat_dict[a_specific_computed_goal_name].append(a_specific_computed_value)

        ## END for a_sess_xdf_filename, eeg_raw_list in self.raw_datasets_dict.items()...

        ## OUTPUTS: eeg_comps_flat_concat_dict
        self.on_compute_finished()


    def on_compute_finished(self, **kwargs):
        """ called to indicate that a recompute is finished """
        print(f'on_compute_finished()')



    def extract_all_datasets_results(self, eeg_comps_results_dict: Dict[types.xdf_file_name, List]) -> Dict[types.EEGComputationId, Any]:
        """ PURE: doesn't alter self

        """
        # eeg_comps_results_dict: Dict[types.xdf_file_name, Dict] = {}

        eeg_comps_flat_concat_dict: Dict[types.EEGComputationId, Any] = {} ## A dict with keys like {"time_independent_bad_channels": {}, "bad_epochs": {}}

        for a_sess_xdf_filename, a_sess_comps_results_list in eeg_comps_results_dict.items():
            if a_sess_comps_results_list is None:
                continue
            for eeg_comps_result in a_sess_comps_results_list:
                if eeg_comps_result is None:
                    continue
                ## main extract from result
                if isinstance(eeg_comps_result, dict):
                    for a_specific_computed_goal_name, a_specific_computed_value in eeg_comps_result.items():
                        if a_specific_computed_value is None:
                            continue
                        if a_specific_computed_goal_name not in eeg_comps_flat_concat_dict:
                            eeg_comps_flat_concat_dict[a_specific_computed_goal_name] = []
                        eeg_comps_flat_concat_dict[a_specific_computed_goal_name].append(a_specific_computed_value)
                else:
                    print(f'WARN')

        ## END for a_sess_xdf_filename, a_sess_comps_results_list in eeg_comps_results_dict.items()...
        return eeg_comps_flat_concat_dict

        # for a_sess_xdf_filename, eeg_raw_list in self.raw_datasets_dict.items():
        #     if eeg_raw_list is not None:
        #         for eeg_raw in eeg_raw_list:
        #             if eeg_raw is not None:
        #                 eeg_comps_result = run_eeg_computations_graph(eeg_raw, session=session_fingerprint_for_raw_or_path(eeg_raw), goals=("time_independent_bad_channels", "bad_epochs",))
        #                 if a_sess_xdf_filename not in eeg_comps_results_dict:
        #                     eeg_comps_results_dict[a_sess_xdf_filename] = []
        #                 eeg_comps_results_dict[a_sess_xdf_filename].append(eeg_comps_result)
        #                 for a_specific_computed_goal_name, a_specific_computed_value in eeg_comps_result.items():
        #                     if a_specific_computed_value is not None:
        #                         if a_specific_computed_goal_name not in eeg_comps_flat_concat_dict:
        #                             eeg_comps_flat_concat_dict[a_specific_computed_goal_name] = []
        #                         eeg_comps_flat_concat_dict[a_specific_computed_goal_name].append(a_specific_computed_value)

        #                 # time_independent_bad_channels = eeg_comps_result["time_independent_bad_channels"]
        #                 # bad_epochs = eeg_comps_result["bad_epochs"]
        #                 # time_independent_bad_channels
        #                 # bad_epochs

        #                 # bad_epoch_intervals_rel = bad_epochs['bad_epoch_intervals_rel']
        #                 # bad_epoch_intervals_df: pd.DataFrame = pd.DataFrame(bad_epoch_intervals_rel, columns=['start_t_rel', 'end_t_rel'])
        #                 # t_col_names: str = ['start_t', 'end_t']
        #                 # for a_t_col in t_col_names:
        #                 #     bad_epoch_intervals_df[a_t_col] = bad_epoch_intervals_df[f'{a_t_col}_rel'] + t0

        # ## OUTPUTS: eeg_comps_flat_concat_dict
        # return eeg_comps_flat_concat_dict






__all__ = ['TrackDatasource', 'DetailRenderer', 'BaseTrackDatasource', 'IntervalProvidingTrackDatasource', 'RawProvidingTrackDatasource']

