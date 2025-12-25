"""Modality-specific track datasources for pyPhoTimeline.

This module provides datasource implementations for various data modalities
that convert from datetime-based formats (used by timeline tracks) to the
float timestamp-based format required by BaseTrackDatasource.
"""

from typing import Tuple, Optional, Any
import numpy as np
import pandas as pd
from datetime import datetime
import pyphoplacecellanalysis.External.pyqtgraph as pg

from pypho_timeline.rendering.datasources.track_datasource import BaseTrackDatasource, DetailRenderer
from pypho_timeline.rendering.detail_renderers import GenericPlotDetailRenderer


# ============================================================================
# Helper Utilities
# ============================================================================

def parse_duration_to_seconds_vectorized(series: pd.Series) -> pd.Series:
    """Convert duration series to seconds, handling various input types vectorially."""
    if series.empty:
        return series
    
    # If already numeric, return as is (coerced to float)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors='coerce')
        
    # If timedelta, get total_seconds
    if pd.api.types.is_timedelta64_dtype(series):
        return series.dt.total_seconds()
        
    # Try converting to timedelta first, then seconds
    try:
        deltas = pd.to_timedelta(series, errors='coerce')
        return deltas.dt.total_seconds()
    except Exception:
        # Fallback to numeric conversion
        return pd.to_numeric(series, errors='coerce')


def datetime_to_timestamp(dt_series: pd.Series) -> pd.Series:
    """Convert datetime series to float timestamps."""
    if dt_series.empty:
        return pd.Series(dtype=float)
    
    # Handle timezone-aware datetimes
    if hasattr(dt_series.dtype, 'tz') and dt_series.dtype.tz is not None:
        # Convert to UTC-naive first
        dt_series = dt_series.dt.tz_localize(None)
    
    # Convert to numpy datetime64, then to float64, then divide by 1e9
    timestamp_values = dt_series.values.astype('datetime64[ns]').astype(np.float64) / 1e9
    return pd.Series(timestamp_values, index=dt_series.index)


def ensure_utc_naive(dt_series: pd.Series) -> pd.Series:
    """Ensure datetime series is UTC-naive."""
    if dt_series.empty:
        return dt_series
    
    if pd.api.types.is_datetime64_any_dtype(dt_series):
        # If timezone-aware, convert to UTC then remove timezone
        if hasattr(dt_series.dtype, 'tz') and dt_series.dtype.tz is not None:
            return dt_series.dt.tz_convert('UTC').dt.tz_localize(None)
        return dt_series
    return dt_series


def create_default_pen_brush(color_tuple: Tuple[int, int, int, int], alpha: float = 0.3) -> Tuple[pg.QtGui.QPen, pg.QtGui.QBrush]:
    """Create default pen and brush with specified color and alpha."""
    color = pg.mkColor(color_tuple)
    color.setAlphaF(alpha)
    pen = pg.mkPen(color, width=1)
    brush = pg.mkBrush(color)
    return pen, brush


# ============================================================================
# Base String Data Datasource
# ============================================================================

class StringDataTrackDatasource(BaseTrackDatasource):
    """Base datasource for string/comment data tracks.
    
    Expects DataFrame with columns:
    - onset: datetime (start time)
    - duration: float or Timedelta (duration in seconds)
    """
    
    def __init__(self, df: pd.DataFrame, onset_col: str = "onset", duration_col: str = "duration", 
                 color_tuple: Tuple[int, int, int, int] = (150, 150, 150, 255), alpha: float = 0.3):
        """Initialize string data datasource.
        
        Args:
            df: DataFrame with onset and duration columns
            onset_col: Name of onset column (default: 'onset')
            duration_col: Name of duration column (default: 'duration')
            color_tuple: RGBA color tuple for visualization
            alpha: Alpha transparency for visualization
        """
        super().__init__()
        self._df_original = df.copy()
        self._onset_col = onset_col
        self._duration_col = duration_col
        self.custom_datasource_name = "StringDataTrack"
        
        # Normalize datetime columns
        if self._onset_col in self._df_original.columns:
            self._df_original[self._onset_col] = ensure_utc_naive(self._df_original[self._onset_col])
        
        # Convert to interval format
        self._intervals_df = self._convert_to_intervals()
        
        # Create visualization properties
        pen, brush = create_default_pen_brush(color_tuple, alpha)
        self._intervals_df['pen'] = [pen] * len(self._intervals_df)
        self._intervals_df['brush'] = [brush] * len(self._intervals_df)
    
    def _convert_to_intervals(self) -> pd.DataFrame:
        """Convert original DataFrame to interval format with t_start and t_duration."""
        if self._df_original.empty or self._onset_col not in self._df_original.columns:
            return pd.DataFrame(columns=['t_start', 't_duration', 'series_vertical_offset', 'series_height'])
        
        df = self._df_original.copy()
        
        # Get start times
        start_dt = df[self._onset_col]
        
        # Get durations
        if self._duration_col in df.columns:
            durations = parse_duration_to_seconds_vectorized(df[self._duration_col])
            durations = durations.fillna(0.1)
            durations[durations <= 0] = 0.1
        else:
            durations = pd.Series(0.1, index=df.index)
        
        # Convert to timestamps
        t_start = datetime_to_timestamp(start_dt)
        t_duration = durations
        
        # Create intervals DataFrame
        intervals_df = pd.DataFrame({
            't_start': t_start.values,
            't_duration': t_duration.values,
        })
        
        # Add visualization columns
        intervals_df['series_vertical_offset'] = 0.0
        intervals_df['series_height'] = 1.0
        
        # Preserve original row data
        for col in df.columns:
            if col not in intervals_df.columns:
                intervals_df[col] = df[col].values
        
        return intervals_df
    
    @property
    def df(self) -> pd.DataFrame:
        return self._intervals_df
    
    @property
    def time_column_names(self) -> list:
        return ['t_start', 't_duration', 't_end']
    
    @property
    def total_df_start_end_times(self) -> Tuple[float, float]:
        if len(self._intervals_df) == 0:
            return (0.0, 1.0)
        t_start = self._intervals_df['t_start'].min()
        t_end = (self._intervals_df['t_start'] + self._intervals_df['t_duration']).max()
        return (t_start, t_end)
    
    def get_updated_data_window(self, new_start: float, new_end: float) -> pd.DataFrame:
        """Get intervals overlapping with time window."""
        mask = (self._intervals_df['t_start'] + self._intervals_df['t_duration'] >= new_start) & \
               (self._intervals_df['t_start'] <= new_end)
        return self._intervals_df[mask].copy()
    
    def update_visualization_properties(self, dataframe_vis_columns_function):
        """Update visualization properties."""
        self._intervals_df = dataframe_vis_columns_function(self._intervals_df)
    
    def get_overview_intervals(self) -> pd.DataFrame:
        """Get overview intervals."""
        return self._intervals_df
    
    def fetch_detailed_data(self, interval: pd.Series) -> Optional[pd.DataFrame]:
        """Fetch detailed data for interval (returns None for base class)."""
        return None
    
    def get_detail_renderer(self) -> Optional[DetailRenderer]:
        """Get detail renderer (returns None for base class)."""
        return None
    
    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get cache key for interval."""
        return f"string_{interval['t_start']:.3f}_{interval['t_duration']:.3f}"


# ============================================================================
# Video Metadata Datasource
# ============================================================================

class VideoMetadataTrackDatasource(BaseTrackDatasource):
    """Datasource for video recording intervals.
    
    Expects DataFrame with columns:
    - video_start_datetime: datetime
    - video_end_datetime: datetime (or video_start_datetime + video_duration)
    """
    
    def __init__(self, video_df: pd.DataFrame):
        """Initialize video metadata datasource.
        
        Args:
            video_df: DataFrame with video_start_datetime and video_end_datetime columns
        """
        super().__init__()
        self._video_df = video_df.copy()
        self.custom_datasource_name = "VideoMetadataTrack"
        
        # Normalize datetime columns
        if 'video_start_datetime' in self._video_df.columns:
            self._video_df['video_start_datetime'] = ensure_utc_naive(self._video_df['video_start_datetime'])
        if 'video_end_datetime' in self._video_df.columns:
            self._video_df['video_end_datetime'] = ensure_utc_naive(self._video_df['video_end_datetime'])
        
        # Convert to interval format
        self._intervals_df = self._convert_to_intervals()
        
        # Create visualization properties (blue theme)
        pen, brush = create_default_pen_brush((100, 150, 200, 255), alpha=0.3)
        self._intervals_df['pen'] = [pen] * len(self._intervals_df)
        self._intervals_df['brush'] = [brush] * len(self._intervals_df)
    
    def _convert_to_intervals(self) -> pd.DataFrame:
        """Convert video DataFrame to interval format."""
        if self._video_df.empty or 'video_start_datetime' not in self._video_df.columns:
            return pd.DataFrame(columns=['t_start', 't_duration', 'series_vertical_offset', 'series_height'])
        
        df = self._video_df.copy()
        start_dt = df['video_start_datetime']
        
        # Calculate end times
        if 'video_end_datetime' in df.columns:
            end_dt = df['video_end_datetime']
        elif 'video_duration' in df.columns:
            durations = parse_duration_to_seconds_vectorized(df['video_duration'])
            end_dt = start_dt + pd.to_timedelta(durations, unit='s')
        else:
            # Default duration if missing
            end_dt = start_dt + pd.Timedelta(seconds=1.0)
        
        # Filter valid rows
        mask = start_dt.notna() & end_dt.notna() & (end_dt > start_dt)
        df = df[mask].copy()
        start_dt = start_dt[mask]
        end_dt = end_dt[mask]
        
        if len(df) == 0:
            return pd.DataFrame(columns=['t_start', 't_duration', 'series_vertical_offset', 'series_height'])
        
        # Convert to timestamps
        t_start = datetime_to_timestamp(start_dt)
        t_end = datetime_to_timestamp(end_dt)
        t_duration = t_end - t_start
        
        # Create intervals DataFrame
        intervals_df = pd.DataFrame({
            't_start': t_start.values,
            't_duration': t_duration.values,
        })
        
        # Add visualization columns
        intervals_df['series_vertical_offset'] = 0.0
        intervals_df['series_height'] = 50.0
        
        # Preserve original row data
        for col in df.columns:
            if col not in intervals_df.columns:
                intervals_df[col] = df[col].values
        
        return intervals_df
    
    @property
    def df(self) -> pd.DataFrame:
        return self._intervals_df
    
    @property
    def time_column_names(self) -> list:
        return ['t_start', 't_duration', 't_end']
    
    @property
    def total_df_start_end_times(self) -> Tuple[float, float]:
        if len(self._intervals_df) == 0:
            return (0.0, 1.0)
        t_start = self._intervals_df['t_start'].min()
        t_end = (self._intervals_df['t_start'] + self._intervals_df['t_duration']).max()
        return (t_start, t_end)
    
    def get_updated_data_window(self, new_start: float, new_end: float) -> pd.DataFrame:
        """Get intervals overlapping with time window."""
        mask = (self._intervals_df['t_start'] + self._intervals_df['t_duration'] >= new_start) & \
               (self._intervals_df['t_start'] <= new_end)
        return self._intervals_df[mask].copy()
    
    def update_visualization_properties(self, dataframe_vis_columns_function):
        """Update visualization properties."""
        self._intervals_df = dataframe_vis_columns_function(self._intervals_df)
    
    def get_overview_intervals(self) -> pd.DataFrame:
        """Get overview intervals."""
        return self._intervals_df
    
    def fetch_detailed_data(self, interval: pd.Series) -> Optional[dict]:
        """Fetch video frames for interval (returns None if not available)."""
        # In a real implementation, this would load video frames from video_path
        # For now, return None to indicate no detail data available
        return None
    
    def get_detail_renderer(self) -> Optional[DetailRenderer]:
        """Get detail renderer for video (returns None if no video frames available)."""
        return None
    
    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get cache key for interval."""
        return f"video_{interval['t_start']:.3f}_{interval['t_duration']:.3f}"


# ============================================================================
# EEG Recording Datasource
# ============================================================================

class EEGRecordingTrackDatasource(BaseTrackDatasource):
    """Datasource for EEG recording intervals.
    
    Expects DataFrame with columns:
    - recording_datetime: datetime (start time)
    - duration_sec: Timedelta or float (duration in seconds)
    """
    
    def __init__(self, eeg_df: pd.DataFrame):
        """Initialize EEG recording datasource.
        
        Args:
            eeg_df: DataFrame with recording_datetime and duration_sec columns
        """
        super().__init__()
        self._eeg_df = eeg_df.copy()
        self.custom_datasource_name = "EEGRecordingTrack"
        
        # Normalize datetime columns
        if 'recording_datetime' in self._eeg_df.columns:
            self._eeg_df['recording_datetime'] = ensure_utc_naive(self._eeg_df['recording_datetime'])
        
        # Convert to interval format
        self._intervals_df = self._convert_to_intervals()
        
        # Create visualization properties (green/blue theme)
        pen, brush = create_default_pen_brush((50, 200, 100, 255), alpha=0.3)
        self._intervals_df['pen'] = [pen] * len(self._intervals_df)
        self._intervals_df['brush'] = [brush] * len(self._intervals_df)
    
    def _convert_to_intervals(self) -> pd.DataFrame:
        """Convert EEG DataFrame to interval format."""
        if self._eeg_df.empty or 'recording_datetime' not in self._eeg_df.columns:
            return pd.DataFrame(columns=['t_start', 't_duration', 'series_vertical_offset', 'series_height'])
        
        df = self._eeg_df.copy()
        start_dt = df['recording_datetime']
        
        # Calculate durations
        durations = pd.Series(np.nan, index=df.index, dtype=float)
        if 'duration_sec_check' in df.columns:
            durations = parse_duration_to_seconds_vectorized(df['duration_sec_check'])
        if 'duration_sec' in df.columns:
            durations2 = parse_duration_to_seconds_vectorized(df['duration_sec'])
            durations = durations.combine_first(durations2)
        
        # Fill NaN durations with default minimum
        if durations.isna().all():
            durations = pd.Series(0.1, index=df.index, dtype=float)
        else:
            durations = durations.fillna(0.1)
            durations[durations <= 0] = 0.1
        
        # Calculate end times
        end_dt = start_dt + pd.to_timedelta(durations, unit='s')
        
        # Filter valid rows
        mask = start_dt.notna() & end_dt.notna() & (end_dt > start_dt)
        df = df[mask].copy()
        start_dt = start_dt[mask]
        durations = durations[mask]
        
        if len(df) == 0:
            return pd.DataFrame(columns=['t_start', 't_duration', 'series_vertical_offset', 'series_height'])
        
        # Convert to timestamps
        t_start = datetime_to_timestamp(start_dt)
        t_duration = durations.values
        
        # Create intervals DataFrame
        intervals_df = pd.DataFrame({
            't_start': t_start.values,
            't_duration': t_duration,
        })
        
        # Add visualization columns
        intervals_df['series_vertical_offset'] = 0.0
        intervals_df['series_height'] = 1.0
        
        # Preserve original row data
        for col in df.columns:
            if col not in intervals_df.columns:
                intervals_df[col] = df[col].values
        
        return intervals_df
    
    @property
    def df(self) -> pd.DataFrame:
        return self._intervals_df
    
    @property
    def time_column_names(self) -> list:
        return ['t_start', 't_duration', 't_end']
    
    @property
    def total_df_start_end_times(self) -> Tuple[float, float]:
        if len(self._intervals_df) == 0:
            return (0.0, 1.0)
        t_start = self._intervals_df['t_start'].min()
        t_end = (self._intervals_df['t_start'] + self._intervals_df['t_duration']).max()
        return (t_start, t_end)
    
    def get_updated_data_window(self, new_start: float, new_end: float) -> pd.DataFrame:
        """Get intervals overlapping with time window."""
        mask = (self._intervals_df['t_start'] + self._intervals_df['t_duration'] >= new_start) & \
               (self._intervals_df['t_start'] <= new_end)
        return self._intervals_df[mask].copy()
    
    def update_visualization_properties(self, dataframe_vis_columns_function):
        """Update visualization properties."""
        self._intervals_df = dataframe_vis_columns_function(self._intervals_df)
    
    def get_overview_intervals(self) -> pd.DataFrame:
        """Get overview intervals."""
        return self._intervals_df
    
    def fetch_detailed_data(self, interval: pd.Series) -> Optional[pd.DataFrame]:
        """Fetch detailed data for interval (returns None for overview-only track)."""
        return None
    
    def get_detail_renderer(self) -> Optional[DetailRenderer]:
        """Get detail renderer (returns None for overview-only track)."""
        return None
    
    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get cache key for interval."""
        return f"eeg_{interval['t_start']:.3f}_{interval['t_duration']:.3f}"


# ============================================================================
# Motion Recording Datasource
# ============================================================================

class MotionRecordingTrackDatasource(BaseTrackDatasource):
    """Datasource for motion recording intervals.
    
    Expects DataFrame with columns:
    - recording_datetime: datetime (start time)
    - duration_sec: Timedelta or float (duration in seconds)
    """
    
    def __init__(self, motion_df: pd.DataFrame, position_datasource: Optional[Any] = None):
        """Initialize motion recording datasource.
        
        Args:
            motion_df: DataFrame with recording_datetime and duration_sec columns
            position_datasource: Optional datasource for position data (AccX, AccY, AccZ, GyroX, GyroY, GyroZ)
        """
        super().__init__()
        self._motion_df = motion_df.copy()
        self._position_datasource = position_datasource
        self.custom_datasource_name = "MotionRecordingTrack"
        
        # Normalize datetime columns
        if 'recording_datetime' in self._motion_df.columns:
            self._motion_df['recording_datetime'] = ensure_utc_naive(self._motion_df['recording_datetime'])
        
        # Convert to interval format
        self._intervals_df = self._convert_to_intervals()
        
        # Create visualization properties (orange/red theme)
        pen, brush = create_default_pen_brush((255, 150, 50, 255), alpha=0.3)
        self._intervals_df['pen'] = [pen] * len(self._intervals_df)
        self._intervals_df['brush'] = [brush] * len(self._intervals_df)
    
    def _convert_to_intervals(self) -> pd.DataFrame:
        """Convert motion DataFrame to interval format."""
        if self._motion_df.empty or 'recording_datetime' not in self._motion_df.columns:
            return pd.DataFrame(columns=['t_start', 't_duration', 'series_vertical_offset', 'series_height'])
        
        df = self._motion_df.copy()
        start_dt = df['recording_datetime']
        
        # Calculate durations
        durations = pd.Series(np.nan, index=df.index, dtype=float)
        if 'duration_sec' in df.columns:
            durations = parse_duration_to_seconds_vectorized(df['duration_sec'])
        
        # Fill NaN durations with default minimum
        if durations.isna().all():
            durations = pd.Series(0.1, index=df.index, dtype=float)
        else:
            durations = durations.fillna(0.1)
            durations[durations <= 0] = 0.1
        
        # Calculate end times
        end_dt = start_dt + pd.to_timedelta(durations, unit='s')
        
        # Filter valid rows
        mask = start_dt.notna() & end_dt.notna() & (end_dt > start_dt)
        df = df[mask].copy()
        start_dt = start_dt[mask]
        durations = durations[mask]
        
        if len(df) == 0:
            return pd.DataFrame(columns=['t_start', 't_duration', 'series_vertical_offset', 'series_height'])
        
        # Convert to timestamps
        t_start = datetime_to_timestamp(start_dt)
        t_duration = durations.values
        
        # Create intervals DataFrame
        intervals_df = pd.DataFrame({
            't_start': t_start.values,
            't_duration': t_duration,
        })
        
        # Add visualization columns
        intervals_df['series_vertical_offset'] = 0.0
        intervals_df['series_height'] = 1.0
        
        # Preserve original row data
        for col in df.columns:
            if col not in intervals_df.columns:
                intervals_df[col] = df[col].values
        
        return intervals_df
    
    @property
    def df(self) -> pd.DataFrame:
        return self._intervals_df
    
    @property
    def time_column_names(self) -> list:
        return ['t_start', 't_duration', 't_end']
    
    @property
    def total_df_start_end_times(self) -> Tuple[float, float]:
        if len(self._intervals_df) == 0:
            return (0.0, 1.0)
        t_start = self._intervals_df['t_start'].min()
        t_end = (self._intervals_df['t_start'] + self._intervals_df['t_duration']).max()
        return (t_start, t_end)
    
    def get_updated_data_window(self, new_start: float, new_end: float) -> pd.DataFrame:
        """Get intervals overlapping with time window."""
        mask = (self._intervals_df['t_start'] + self._intervals_df['t_duration'] >= new_start) & \
               (self._intervals_df['t_start'] <= new_end)
        return self._intervals_df[mask].copy()
    
    def update_visualization_properties(self, dataframe_vis_columns_function):
        """Update visualization properties."""
        self._intervals_df = dataframe_vis_columns_function(self._intervals_df)
    
    def get_overview_intervals(self) -> pd.DataFrame:
        """Get overview intervals."""
        return self._intervals_df
    
    def fetch_detailed_data(self, interval: pd.Series) -> Optional[pd.DataFrame]:
        """Fetch position data for interval if position datasource is available."""
        if self._position_datasource is None:
            return None
        
        t_start = interval['t_start']
        t_end = t_start + interval['t_duration']
        
        # Query position datasource for the time range
        if hasattr(self._position_datasource, 'get_updated_data_window'):
            position_df = self._position_datasource.get_updated_data_window(t_start, t_end)
            return position_df if isinstance(position_df, pd.DataFrame) else None
        
        return None
    
    def get_detail_renderer(self) -> Optional[DetailRenderer]:
        """Get detail renderer for motion data (returns None if no position datasource)."""
        if self._position_datasource is None:
            return None
        
        # Return generic plot renderer that can handle position data
        # In a real implementation, this could be a custom renderer for motion data
        return None
    
    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get cache key for interval."""
        return f"motion_{interval['t_start']:.3f}_{interval['t_duration']:.3f}"


# ============================================================================
# PhoLog Track Datasource
# ============================================================================

class PhoLogTrackDatasource(BaseTrackDatasource):
    """Datasource for PHO_LOG annotation intervals.
    
    Expects DataFrame with columns:
    - onset: datetime (or 'time' column)
    - duration: float or Timedelta (optional, defaults to 0 for point markers)
    """
    
    def __init__(self, pho_log_df: pd.DataFrame):
        """Initialize PHO_LOG datasource.
        
        Args:
            pho_log_df: DataFrame with onset (or time) and duration columns
        """
        super().__init__()
        self._pho_log_df = pho_log_df.copy()
        self.custom_datasource_name = "PhoLogTrack"
        
        # Detect and normalize onset column
        onset_col = None
        if 'time' in self._pho_log_df.columns:
            if 'onset' not in self._pho_log_df.columns:
                self._pho_log_df = self._pho_log_df.rename(columns={'time': 'onset'})
            onset_col = 'onset'
        elif 'onset' in self._pho_log_df.columns:
            onset_col = 'onset'
        else:
            raise ValueError(f"DataFrame must have either 'time' or 'onset' column but only has columns: {list(self._pho_log_df.columns)}")
        
        # Normalize datetime columns
        if onset_col in self._pho_log_df.columns:
            self._pho_log_df[onset_col] = ensure_utc_naive(self._pho_log_df[onset_col])
        
        # Convert to interval format
        self._intervals_df = self._convert_to_intervals(onset_col)
        
        # Create visualization properties (purple theme)
        pen, brush = create_default_pen_brush((200, 100, 255, 255), alpha=0.3)
        self._intervals_df['pen'] = [pen] * len(self._intervals_df)
        self._intervals_df['brush'] = [brush] * len(self._intervals_df)
    
    def _convert_to_intervals(self, onset_col: str) -> pd.DataFrame:
        """Convert PHO_LOG DataFrame to interval format, preserving 0 durations for point markers."""
        if self._pho_log_df.empty or onset_col not in self._pho_log_df.columns:
            return pd.DataFrame(columns=['t_start', 't_duration', 'series_vertical_offset', 'series_height'])
        
        df = self._pho_log_df.copy()
        start_dt = df[onset_col]
        
        # Get durations (preserve 0 for point markers)
        if 'duration' in df.columns:
            durations = parse_duration_to_seconds_vectorized(df['duration'])
            # Fill NaN with 0.1, but preserve explicit 0 values for point markers
            durations = durations.fillna(0.1)
            durations[durations < 0] = 0.1
        else:
            # No duration - set to 0 for point markers
            durations = pd.Series(0.0, index=df.index)
        
        # Calculate end times
        end_dt = start_dt + pd.to_timedelta(durations, unit='s')
        
        # Filter valid rows
        mask = start_dt.notna() & end_dt.notna()
        df = df[mask].copy()
        start_dt = start_dt[mask]
        durations = durations[mask]
        
        if len(df) == 0:
            return pd.DataFrame(columns=['t_start', 't_duration', 'series_vertical_offset', 'series_height'])
        
        # Convert to timestamps
        t_start = datetime_to_timestamp(start_dt)
        t_duration = durations.values
        
        # Create intervals DataFrame
        intervals_df = pd.DataFrame({
            't_start': t_start.values,
            't_duration': t_duration,
        })
        
        # Add visualization columns
        intervals_df['series_vertical_offset'] = 0.0
        intervals_df['series_height'] = 1.0
        
        # Preserve original row data
        for col in df.columns:
            if col not in intervals_df.columns:
                intervals_df[col] = df[col].values
        
        return intervals_df
    
    @property
    def df(self) -> pd.DataFrame:
        return self._intervals_df
    
    @property
    def time_column_names(self) -> list:
        return ['t_start', 't_duration', 't_end']
    
    @property
    def total_df_start_end_times(self) -> Tuple[float, float]:
        if len(self._intervals_df) == 0:
            return (0.0, 1.0)
        t_start = self._intervals_df['t_start'].min()
        t_end = (self._intervals_df['t_start'] + self._intervals_df['t_duration']).max()
        return (t_start, t_end)
    
    def get_updated_data_window(self, new_start: float, new_end: float) -> pd.DataFrame:
        """Get intervals overlapping with time window."""
        mask = (self._intervals_df['t_start'] + self._intervals_df['t_duration'] >= new_start) & \
               (self._intervals_df['t_start'] <= new_end)
        return self._intervals_df[mask].copy()
    
    def update_visualization_properties(self, dataframe_vis_columns_function):
        """Update visualization properties."""
        self._intervals_df = dataframe_vis_columns_function(self._intervals_df)
    
    def get_overview_intervals(self) -> pd.DataFrame:
        """Get overview intervals."""
        return self._intervals_df
    
    def fetch_detailed_data(self, interval: pd.Series) -> Optional[pd.DataFrame]:
        """Fetch detailed data for interval (returns None, text rendering handled by track)."""
        return None
    
    def get_detail_renderer(self) -> Optional[DetailRenderer]:
        """Get detail renderer (returns None, text rendering handled by track)."""
        return None
    
    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get cache key for interval."""
        return f"pholog_{interval['t_start']:.3f}_{interval['t_duration']:.3f}"


# ============================================================================
# Whisper Track Datasource
# ============================================================================

class WhisperTrackDatasource(BaseTrackDatasource):
    """Datasource for Whisper transcript intervals.
    
    Expects DataFrame with columns:
    - onset: datetime (start time)
    - duration: float or Timedelta (duration in seconds)
    """
    
    def __init__(self, whisper_df: pd.DataFrame):
        """Initialize Whisper datasource.
        
        Args:
            whisper_df: DataFrame with onset and duration columns
        """
        super().__init__()
        self._whisper_df = whisper_df.copy()
        self.custom_datasource_name = "WhisperTrack"
        
        # Normalize datetime columns
        if 'onset' in self._whisper_df.columns:
            self._whisper_df['onset'] = ensure_utc_naive(self._whisper_df['onset'])
        
        # Convert to interval format
        self._intervals_df = self._convert_to_intervals()
        
        # Create visualization properties (cyan/teal theme)
        pen, brush = create_default_pen_brush((50, 200, 255, 255), alpha=0.3)
        self._intervals_df['pen'] = [pen] * len(self._intervals_df)
        self._intervals_df['brush'] = [brush] * len(self._intervals_df)
    
    def _convert_to_intervals(self) -> pd.DataFrame:
        """Convert Whisper DataFrame to interval format."""
        if self._whisper_df.empty or 'onset' not in self._whisper_df.columns:
            return pd.DataFrame(columns=['t_start', 't_duration', 'series_vertical_offset', 'series_height'])
        
        df = self._whisper_df.copy()
        start_dt = df['onset']
        
        # Get durations
        if 'duration' in df.columns:
            durations = parse_duration_to_seconds_vectorized(df['duration'])
            durations = durations.fillna(0.1)
            durations[durations <= 0] = 0.1
        else:
            durations = pd.Series(0.1, index=df.index)
        
        # Calculate end times
        end_dt = start_dt + pd.to_timedelta(durations, unit='s')
        
        # Filter valid rows
        mask = start_dt.notna() & end_dt.notna()
        df = df[mask].copy()
        start_dt = start_dt[mask]
        durations = durations[mask]
        
        if len(df) == 0:
            return pd.DataFrame(columns=['t_start', 't_duration', 'series_vertical_offset', 'series_height'])
        
        # Convert to timestamps
        t_start = datetime_to_timestamp(start_dt)
        t_duration = durations.values
        
        # Create intervals DataFrame
        intervals_df = pd.DataFrame({
            't_start': t_start.values,
            't_duration': t_duration,
        })
        
        # Add visualization columns
        intervals_df['series_vertical_offset'] = 0.0
        intervals_df['series_height'] = 1.0
        
        # Preserve original row data
        for col in df.columns:
            if col not in intervals_df.columns:
                intervals_df[col] = df[col].values
        
        return intervals_df
    
    @property
    def df(self) -> pd.DataFrame:
        return self._intervals_df
    
    @property
    def time_column_names(self) -> list:
        return ['t_start', 't_duration', 't_end']
    
    @property
    def total_df_start_end_times(self) -> Tuple[float, float]:
        if len(self._intervals_df) == 0:
            return (0.0, 1.0)
        t_start = self._intervals_df['t_start'].min()
        t_end = (self._intervals_df['t_start'] + self._intervals_df['t_duration']).max()
        return (t_start, t_end)
    
    def get_updated_data_window(self, new_start: float, new_end: float) -> pd.DataFrame:
        """Get intervals overlapping with time window."""
        mask = (self._intervals_df['t_start'] + self._intervals_df['t_duration'] >= new_start) & \
               (self._intervals_df['t_start'] <= new_end)
        return self._intervals_df[mask].copy()
    
    def update_visualization_properties(self, dataframe_vis_columns_function):
        """Update visualization properties."""
        self._intervals_df = dataframe_vis_columns_function(self._intervals_df)
    
    def get_overview_intervals(self) -> pd.DataFrame:
        """Get overview intervals."""
        return self._intervals_df
    
    def fetch_detailed_data(self, interval: pd.Series) -> Optional[pd.DataFrame]:
        """Fetch detailed data for interval (returns None for overview-only track)."""
        return None
    
    def get_detail_renderer(self) -> Optional[DetailRenderer]:
        """Get detail renderer (returns None for overview-only track)."""
        return None
    
    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get cache key for interval."""
        return f"whisper_{interval['t_start']:.3f}_{interval['t_duration']:.3f}"


# ============================================================================
# XDF Stream Track Datasource
# ============================================================================

class XDFStreamTrackDatasource(BaseTrackDatasource):
    """Datasource for XDF stream intervals.
    
    Expects DataFrame with columns:
    - recording_datetime: datetime (or first_timestamp_dt)
    - duration_sec: Timedelta or float (or last_timestamp_dt)
    """
    
    def __init__(self, stream_df: pd.DataFrame):
        """Initialize XDF stream datasource.
        
        Args:
            stream_df: DataFrame with recording_datetime (or first_timestamp_dt) and duration_sec (or last_timestamp_dt) columns
        """
        super().__init__()
        self._stream_df = stream_df.copy()
        self.custom_datasource_name = "XDFStreamTrack"
        
        # Normalize datetime columns
        for col in ['recording_datetime', 'first_timestamp_dt', 'last_timestamp_dt']:
            if col in self._stream_df.columns:
                self._stream_df[col] = ensure_utc_naive(self._stream_df[col])
        
        # Convert to interval format
        self._intervals_df = self._convert_to_intervals()
        
        # Create visualization properties (gray theme)
        pen, brush = create_default_pen_brush((150, 150, 150, 255), alpha=0.3)
        self._intervals_df['pen'] = [pen] * len(self._intervals_df)
        self._intervals_df['brush'] = [brush] * len(self._intervals_df)
    
    def _convert_to_intervals(self) -> pd.DataFrame:
        """Convert XDF stream DataFrame to interval format with flexible datetime column handling."""
        if self._stream_df.empty:
            return pd.DataFrame(columns=['t_start', 't_duration', 'series_vertical_offset', 'series_height'])
        
        df = self._stream_df.copy()
        
        # Calculate start times (prefer first_timestamp_dt, fallback to recording_datetime)
        start_dt = pd.Series(pd.NaT, index=df.index)
        if 'first_timestamp_dt' in df.columns:
            start_dt = df['first_timestamp_dt']
        elif 'recording_datetime' in df.columns:
            start_dt = df['recording_datetime']
        
        # Calculate end times (prefer last_timestamp_dt, then duration_sec)
        end_dt = pd.Series(pd.NaT, index=df.index)
        if 'last_timestamp_dt' in df.columns:
            end_dt = df['last_timestamp_dt']
        elif 'duration_sec_check' in df.columns:
            durations = parse_duration_to_seconds_vectorized(df['duration_sec_check'])
            valid_mask = durations.notna()
            if valid_mask.any():
                calc_ends = pd.Series(pd.NaT, index=df.index)
                calc_ends[valid_mask] = start_dt[valid_mask] + pd.to_timedelta(durations[valid_mask], unit='s')
                end_dt = calc_ends
        elif 'duration_sec' in df.columns:
            durations = parse_duration_to_seconds_vectorized(df['duration_sec'])
            valid_mask = durations.notna()
            if valid_mask.any():
                calc_ends = pd.Series(pd.NaT, index=df.index)
                calc_ends[valid_mask] = start_dt[valid_mask] + pd.to_timedelta(durations[valid_mask], unit='s')
                end_dt = calc_ends
        
        # Fallback for markers (0.1 second duration)
        is_marker = pd.Series(False, index=df.index)
        if 'type' in df.columns:
            is_marker |= df['type'] == 'Markers'
        if 'name' in df.columns:
            is_marker |= df['name'] == 'TextLogger'
        
        if is_marker.any():
            marker_ends = start_dt + pd.Timedelta(seconds=0.1)
            end_dt = end_dt.combine_first(marker_ends.where(is_marker))
        
        # Filter valid rows
        mask = start_dt.notna() & end_dt.notna() & (end_dt > start_dt)
        df = df[mask].copy()
        start_dt = start_dt[mask]
        end_dt = end_dt[mask]
        
        if len(df) == 0:
            return pd.DataFrame(columns=['t_start', 't_duration', 'series_vertical_offset', 'series_height'])
        
        # Convert to timestamps
        t_start = datetime_to_timestamp(start_dt)
        t_end = datetime_to_timestamp(end_dt)
        t_duration = t_end - t_start
        
        # Create intervals DataFrame
        intervals_df = pd.DataFrame({
            't_start': t_start.values,
            't_duration': t_duration.values,
        })
        
        # Add visualization columns
        intervals_df['series_vertical_offset'] = 0.0
        intervals_df['series_height'] = 1.0
        
        # Preserve original row data
        for col in df.columns:
            if col not in intervals_df.columns:
                intervals_df[col] = df[col].values
        
        return intervals_df
    
    @property
    def df(self) -> pd.DataFrame:
        return self._intervals_df
    
    @property
    def time_column_names(self) -> list:
        return ['t_start', 't_duration', 't_end']
    
    @property
    def total_df_start_end_times(self) -> Tuple[float, float]:
        if len(self._intervals_df) == 0:
            return (0.0, 1.0)
        t_start = self._intervals_df['t_start'].min()
        t_end = (self._intervals_df['t_start'] + self._intervals_df['t_duration']).max()
        return (t_start, t_end)
    
    def get_updated_data_window(self, new_start: float, new_end: float) -> pd.DataFrame:
        """Get intervals overlapping with time window."""
        mask = (self._intervals_df['t_start'] + self._intervals_df['t_duration'] >= new_start) & \
               (self._intervals_df['t_start'] <= new_end)
        return self._intervals_df[mask].copy()
    
    def update_visualization_properties(self, dataframe_vis_columns_function):
        """Update visualization properties."""
        self._intervals_df = dataframe_vis_columns_function(self._intervals_df)
    
    def get_overview_intervals(self) -> pd.DataFrame:
        """Get overview intervals."""
        return self._intervals_df
    
    def fetch_detailed_data(self, interval: pd.Series) -> Optional[pd.DataFrame]:
        """Fetch detailed data for interval (returns None for overview-only track)."""
        return None
    
    def get_detail_renderer(self) -> Optional[DetailRenderer]:
        """Get detail renderer (returns None for overview-only track)."""
        return None
    
    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get cache key for interval."""
        return f"xdf_{interval['t_start']:.3f}_{interval['t_duration']:.3f}"


__all__ = [
    'StringDataTrackDatasource',
    'VideoMetadataTrackDatasource',
    'EEGRecordingTrackDatasource',
    'MotionRecordingTrackDatasource',
    'PhoLogTrackDatasource',
    'WhisperTrackDatasource',
    'XDFStreamTrackDatasource',
]

