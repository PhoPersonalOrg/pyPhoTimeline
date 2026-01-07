"""Downsampling utilities for time-series data using LTTB algorithm.

This module provides efficient downsampling of time-series DataFrames using the
Largest-Triangle-Three-Buckets (LTTB) algorithm, which preserves visual features
better than simple decimation.
"""
import numpy as np
import pandas as pd
from typing import Optional, List


def lttb_downsample(x: np.ndarray, y: np.ndarray, max_points: int) -> np.ndarray:
    """Downsample a time series using the Largest-Triangle-Three-Buckets (LTTB) algorithm.
    
    LTTB preserves visual features by selecting points that form the largest triangles
    with adjacent buckets, ensuring peaks and valleys are maintained.
    
    Args:
        x: Time values (1D array, must be sorted)
        y: Data values (1D array)
        max_points: Maximum number of points in output
        
    Returns:
        Boolean mask array indicating which points to keep (True = keep, False = discard)
        
    Reference:
        Sveinn Steinarsson. "Downsampling Time Series for Visual Representation"
        https://skemman.is/bitstream/1946/15343/3/SS_MSthesis.pdf
    """
    n = len(x)
    if n <= max_points:
        # No downsampling needed
        return np.ones(n, dtype=bool)
    
    if max_points < 3:
        # Need at least 3 points for LTTB
        max_points = min(3, n)
    
    # Always keep first and last points
    mask = np.zeros(n, dtype=bool)
    mask[0] = True
    mask[-1] = True
    
    if max_points == 2:
        return mask
    
    # Calculate bucket size
    bucket_size = (n - 2) / (max_points - 2)
    
    # Keep track of selected points
    selected_indices = [0]
    
    # Process each bucket (except first and last)
    for i in range(1, max_points - 1):
        # Calculate bucket range
        range_start = int((i - 1) * bucket_size) + 1
        range_end = int(i * bucket_size) + 1
        range_end = min(range_end, n - 1)
        
        # Next bucket range (for triangle calculation)
        next_range_start = int(i * bucket_size) + 1
        next_range_end = int((i + 1) * bucket_size) + 1
        next_range_end = min(next_range_end, n - 1)
        
        # Get previous point (already selected)
        prev_idx = selected_indices[-1]
        prev_x = x[prev_idx]
        prev_y = y[prev_idx]
        
        # Get next bucket's average point
        if next_range_start < next_range_end:
            next_avg_x = np.mean(x[next_range_start:next_range_end])
            next_avg_y = np.mean(y[next_range_start:next_range_end])
        else:
            # Last bucket, use last point
            next_avg_x = x[-1]
            next_avg_y = y[-1]
        
        # Find point in current bucket that forms largest triangle
        max_area = -1
        best_idx = range_start
        
        for idx in range(range_start, range_end):
            # Calculate triangle area using cross product
            # Area = 0.5 * |(x2-x1)(y3-y1) - (x3-x1)(y2-y1)|
            area = abs(
                (x[idx] - prev_x) * (next_avg_y - prev_y) -
                (next_avg_x - prev_x) * (y[idx] - prev_y)
            )
            
            if area > max_area:
                max_area = area
                best_idx = idx
        
        selected_indices.append(best_idx)
    
    # Always include last point
    if selected_indices[-1] != n - 1:
        selected_indices.append(n - 1)
    
    # Create mask from selected indices
    mask[selected_indices] = True
    return mask


def downsample_dataframe(df: pd.DataFrame, max_points: int, time_col: str = 't') -> pd.DataFrame:
    """Downsample a time-series DataFrame using LTTB algorithm.
    
    This function applies LTTB downsampling to preserve visual features while
    reducing the number of data points. It works on DataFrames with a time column
    and multiple data columns (channels).
    
    Args:
        df: DataFrame with time column and data columns
        max_points: Maximum number of points to keep
        time_col: Name of the time column (default: 't')
        
    Returns:
        Downsampled DataFrame with same columns, sorted by time
        
    Example:
        >>> df = pd.DataFrame({'t': np.linspace(0, 10, 1000), 'ch1': np.sin(np.linspace(0, 10, 1000))})
        >>> downsampled = downsample_dataframe(df, max_points=100)
        >>> len(downsampled)  # Will be <= 100
    """
    if len(df) == 0:
        return df
    
    if len(df) <= max_points:
        # No downsampling needed
        return df.copy()
    
    if time_col not in df.columns:
        raise ValueError(f"Time column '{time_col}' not found in DataFrame")
    
    # Sort by time to ensure proper ordering
    df_sorted = df.sort_values(time_col).reset_index(drop=True)
    
    # Get time values
    t_values = df_sorted[time_col].values
    
    # Get all data columns (everything except time column)
    data_columns = [col for col in df_sorted.columns if col != time_col]
    
    if len(data_columns) == 0:
        # No data columns, just downsample time
        mask = lttb_downsample(t_values, t_values, max_points)
        return df_sorted[mask].copy()
    
    # For multiple channels, we need to downsample in a way that preserves
    # features across all channels. We'll use a combined approach:
    # 1. Calculate a "combined" signal that represents all channels
    # 2. Use LTTB on the combined signal
    # 3. Apply the same mask to all channels
    
    # Normalize each channel to [0, 1] for fair combination
    combined_signal = np.zeros(len(df_sorted))
    for col in data_columns:
        values = df_sorted[col].values.astype(float)
        # Handle NaN and inf
        valid_mask = np.isfinite(values)
        if np.any(valid_mask):
            min_val = np.nanmin(values[valid_mask])
            max_val = np.nanmax(values[valid_mask])
            if max_val > min_val:
                normalized = (values - min_val) / (max_val - min_val)
                normalized[~valid_mask] = 0
            else:
                normalized = np.zeros_like(values)
                normalized[valid_mask] = 0.5
        else:
            normalized = np.zeros_like(values)
        combined_signal += normalized
    
    # Average the combined signal
    if len(data_columns) > 0:
        combined_signal /= len(data_columns)
    
    # Apply LTTB using combined signal
    mask = lttb_downsample(t_values, combined_signal, max_points)
    
    return df_sorted[mask].copy()


__all__ = ['lttb_downsample', 'downsample_dataframe']







