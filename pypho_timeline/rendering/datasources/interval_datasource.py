"""IntervalsDatasource interface and type hints for pypho_timeline.

This module provides type hints and a minimal interface for interval datasources.
The actual IntervalsDatasource implementation should be imported from pyphoplacecellanalysis
if available, or a compatible implementation can be provided.
"""
from typing import Protocol, Optional, Tuple, Union
from datetime import datetime
import pandas as pd
from qtpy import QtCore

# Try to import the actual IntervalsDatasource from pyphoplacecellanalysis
try:
    from pyphoplacecellanalysis.General.Model.Datasources.IntervalDatasource import IntervalsDatasource
    __all__ = ['IntervalsDatasource']
except ImportError:
    # If not available, define a minimal Protocol for type checking
    class IntervalsDatasourceProtocol(Protocol):
        """Protocol defining the interface expected from an IntervalsDatasource.
        
        This protocol matches the interface of pyphoplacecellanalysis.General.Model.Datasources.IntervalDatasource.IntervalsDatasource
        """
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
        def total_df_start_end_times(self) -> Union[Tuple[float, float], Tuple[datetime, datetime], Tuple[pd.Timestamp, pd.Timestamp]]:
            """Returns (earliest_time, latest_time) for the entire dataset"""
            ...
        
        def get_updated_data_window(self, new_start: Union[float, datetime, pd.Timestamp], new_end: Union[float, datetime, pd.Timestamp]) -> pd.DataFrame:
            """Returns the subset of intervals that overlap with the given time window"""
            ...
        
        def update_visualization_properties(self, dataframe_vis_columns_function):
            """Updates visualization columns in the dataframe"""
            ...
    
    # Create a type alias that can be used for type hints
    IntervalsDatasource = IntervalsDatasourceProtocol
    __all__ = ['IntervalsDatasource', 'IntervalsDatasourceProtocol']

