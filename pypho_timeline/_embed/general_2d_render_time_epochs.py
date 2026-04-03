"""Minimal General2DRenderTimeEpochs embedded from pyPhoPlaceCellAnalysis for pypho_timeline (DataFrame/tuple only, no neuropy)."""
from typing import Any, Callable

import numpy as np
import pandas as pd
import pypho_timeline.EXTERNAL.pyqtgraph as pg

from pypho_timeline._embed.interval_datasource import IntervalsDatasource, _renaming_synonym_columns_if_needed

_required_interval_visualization_columns = ["t_start", "t_duration", "series_vertical_offset", "series_height", "pen", "brush"]


class General2DRenderTimeEpochs:
    """Minimal helper: _update_df_visualization_columns and build_render_time_epochs_datasource for DataFrame/tuple."""

    default_datasource_name: str = "GeneralEpochs"
    _required_interval_visualization_columns = _required_interval_visualization_columns

    @classmethod
    def _update_df_visualization_columns(cls, active_df: pd.DataFrame, y_location=None, height=None, pen_color=None, brush_color=None, **kwargs) -> pd.DataFrame:
        if y_location is not None:
            if isinstance(y_location, (list, tuple)):
                active_df["series_vertical_offset"] = kwargs.setdefault("series_vertical_offset", [y for y in y_location])
            else:
                active_df["series_vertical_offset"] = kwargs.setdefault("series_vertical_offset", y_location)
        if height is not None:
            if isinstance(height, (list, tuple)):
                active_df["series_height"] = kwargs.setdefault("series_height", [h for h in height])
            else:
                active_df["series_height"] = kwargs.setdefault("series_height", height)
        if pen_color is not None:
            if isinstance(pen_color, (list, tuple)):
                active_df["pen"] = kwargs.setdefault("pen", [pg.mkPen(c) for c in pen_color])
            else:
                active_df["pen"] = kwargs.setdefault("pen", pg.mkPen(pen_color))
        if brush_color is not None:
            if isinstance(brush_color, (list, tuple)):
                active_df["brush"] = kwargs.setdefault("brush", [pg.mkBrush(c) for c in brush_color])
            else:
                active_df["brush"] = kwargs.setdefault("brush", pg.mkBrush(brush_color))
        return active_df

    @classmethod
    def build_epochs_dataframe_formatter(cls, **kwargs) -> Callable:
        def _add_interval_dataframe_visualization_columns_general_epoch(active_df: pd.DataFrame) -> pd.DataFrame:
            y_location = 0.0
            height = 1.0
            pen_color = pg.mkColor("red")
            brush_color = pg.mkColor("red")
            active_df = cls._update_df_visualization_columns(active_df, y_location, height, pen_color, brush_color, **kwargs)
            return active_df

        return _add_interval_dataframe_visualization_columns_general_epoch

    @classmethod
    def build_render_time_epochs_datasource(cls, active_epochs_obj: Any, **kwargs) -> IntervalsDatasource:
        custom_epochs_df_formatter = kwargs.pop("epochs_dataframe_formatter", None)
        datasource_name = kwargs.pop("datasource_name", "intervals_datasource_from_general_obj")
        if custom_epochs_df_formatter is None:
            active_epochs_df_formatter = cls.build_epochs_dataframe_formatter(**kwargs)
        else:
            active_epochs_df_formatter = custom_epochs_df_formatter

        if isinstance(active_epochs_obj, pd.DataFrame):
            active_df = active_epochs_obj.copy()
            active_df = _renaming_synonym_columns_if_needed(active_df, IntervalsDatasource._time_column_name_synonyms)
            active_df = IntervalsDatasource.add_missing_reciprocal_columns_if_needed(active_df)
            if not np.isin(cls._required_interval_visualization_columns, active_df.columns).all():
                active_df = active_epochs_df_formatter(active_df)
            return IntervalsDatasource(active_df, datasource_name=datasource_name)
        elif isinstance(active_epochs_obj, (list, tuple)) and len(active_epochs_obj) >= 2:
            t_starts = np.asarray(active_epochs_obj[0])
            t_durations = np.asarray(active_epochs_obj[1])
            values = active_epochs_obj[2] if len(active_epochs_obj) > 2 else np.arange(len(t_starts))
            active_df = pd.DataFrame({"t_start": t_starts, "t_duration": t_durations, "t_end": t_starts + t_durations, "v": values})
            active_df = active_epochs_df_formatter(active_df)
            return IntervalsDatasource(active_df, datasource_name=datasource_name)
        else:
            raise NotImplementedError(f"build_render_time_epochs_datasource does not support type: {type(active_epochs_obj)}")
