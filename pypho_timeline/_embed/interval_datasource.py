"""Minimal IntervalsDatasource embedded from pyPhoPlaceCellAnalysis for pypho_timeline (no neuropy)."""
from copy import deepcopy
from typing import Dict, List, Tuple, Union, Any

import numpy as np
import pandas as pd
from qtpy import QtCore

# Optional: re-export for callers that need the synonym dict
TIME_COLUMN_NAME_SYNONYMS = {"t_start": {"begin", "start", "start_t"}, "t_end": {"end", "stop", "stop_t"}, "t_duration": {"duration"}}


def _renaming_synonym_columns_if_needed(df: pd.DataFrame, required_columns_synonym_dict: Dict[str, Any]) -> pd.DataFrame:
    """Rename columns to match required names using synonym dict. No neuropy dependency."""
    df = df.copy()
    for required_name, synonyms in required_columns_synonym_dict.items():
        if required_name in df.columns:
            continue
        if isinstance(synonyms, set):
            aliases = synonyms
        else:
            aliases = set(synonyms) if isinstance(synonyms, (list, tuple)) else {synonyms}
        for col in df.columns:
            if col in aliases:
                df = df.rename(columns={col: required_name})
                break
    return df


class IntervalsDatasource(QtCore.QObject):
    """Minimal interval datasource: holds a DataFrame with t_start, t_duration and optional viz columns. Emits signal on change."""

    _required_interval_time_columns = ["t_start", "t_duration"]
    _all_interval_time_columns = ["t_start", "t_duration", "t_end"]
    _required_interval_visualization_columns = ["t_start", "t_duration", "series_vertical_offset", "series_height", "pen", "brush"]
    _series_update_dict_position_columns = ["series_vertical_offset", "series_height"]
    _time_column_name_synonyms = TIME_COLUMN_NAME_SYNONYMS

    source_data_changed_signal = QtCore.Signal(object)

    @property
    def time_column_names(self) -> List[str]:
        return ["t_start", "t_duration", "t_end"]

    @property
    def total_datasource_start_end_times(self) -> Tuple[Any, Any]:
        return self.total_df_start_end_times

    @property
    def total_df_start_end_times(self) -> Tuple[Any, Any]:
        cols = [c for c in self.time_column_names if c in self._df.columns]
        if not cols:
            return (None, None)
        df_timestamps = self._df[cols].to_numpy()
        if df_timestamps.size == 0:
            return (None, None)
        earliest = df_timestamps[:, 0].min()
        latest = df_timestamps[:, -1].max()
        return (earliest, latest)


    @property
    def df(self) -> pd.DataFrame:
        return self._df
    @df.setter
    def df(self, value: pd.DataFrame) -> None:
        self._df = value
        self.source_data_changed_signal.emit(self)


    def __init__(self, df: pd.DataFrame, datasource_name: str = "default_intervals_datasource"):
        super().__init__()
        self.custom_datasource_name = datasource_name
        if not np.isin(self._required_interval_time_columns, df.columns).all():
            df = _renaming_synonym_columns_if_needed(df, self._time_column_name_synonyms)
        assert np.isin(self._required_interval_time_columns, df.columns).all(), f"dataframe is missing required columns: {self._required_interval_time_columns}, current: {list(df.columns)}"
        self._df = df.copy()


    def update_visualization_properties(self, dataframe_vis_columns_function: Union[callable, Dict]) -> None:
        if isinstance(dataframe_vis_columns_function, dict):
            from pypho_timeline._embed.general_2d_render_time_epochs import General2DRenderTimeEpochs
            an_epoch_formatting_dict = dataframe_vis_columns_function
            dataframe_vis_columns_function = lambda active_df, **kwargs: General2DRenderTimeEpochs._update_df_visualization_columns(active_df, **(an_epoch_formatting_dict | kwargs))
        self._df = dataframe_vis_columns_function(self._df)
        self.source_data_changed_signal.emit(self)


    def get_updated_data_window(self, new_start: Union[float, int], new_end: Union[float, int]) -> pd.DataFrame:
        if self._df.empty:
            return self._df
        if "t_end" not in self._df.columns:
            self._df = self._df.copy()
            self._df["t_end"] = self._df["t_start"] + self._df["t_duration"]
        is_start_in = (new_start <= self._df["t_start"]) & (self._df["t_start"] < new_end)
        is_end_in = (new_start < self._df["t_end"]) & (self._df["t_end"] <= new_end)
        mask = is_start_in | is_end_in
        return self._df.loc[mask]

    @classmethod
    def add_missing_reciprocal_columns_if_needed(cls, df: pd.DataFrame) -> pd.DataFrame:
        if all(c in df.columns for c in ["t_start", "t_duration", "t_end"]):
            return df
        if "t_end" not in df.columns and "t_start" in df.columns and "t_duration" in df.columns:
            df = df.copy()
            df["t_end"] = df["t_start"] + df["t_duration"]
        elif "t_duration" not in df.columns and "t_start" in df.columns and "t_end" in df.columns:
            df = df.copy()
            df["t_duration"] = df["t_end"] - df["t_start"]
        return df


