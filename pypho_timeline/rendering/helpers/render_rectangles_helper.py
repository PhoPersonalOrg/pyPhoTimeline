"""Render2DEventRectanglesHelper - Static helper for building interval rectangle items.

Refactored from pyphoplacecellanalysis for use in pypho_timeline.
"""
from copy import deepcopy
from typing import Tuple
from datetime import datetime
import numpy as np
import pandas as pd

# Optional import - Epoch from neuropy (only used if available)
try:
    from neuropy.core import Epoch
except ImportError:
    Epoch = None

import pyphoplacecellanalysis.External.pyqtgraph as pg
from pypho_timeline.rendering.graphics.interval_rects_item import IntervalRectsItem, IntervalRectsItemData

# Import IntervalsDatasource from external package (or use interface)
try:
    from pyphoplacecellanalysis.General.Model.Datasources.IntervalDatasource import IntervalsDatasource
except ImportError:
    # Fallback: define minimal interface if not available
    IntervalsDatasource = None


class Render2DEventRectanglesHelper:
    """Static helper that adds interval/epoch rectangles to 2D raster plots.
    
    Also has the full implementation of Bursts (which are plotted as rectangles per-neuron, 
    which hasn't been updated to the new EpochRenderingMixin format yet).
    """
    
    ##################################################
    ## Common METHODS
    ##################################################
    _required_interval_visualization_columns = ['t_start', 't_duration', 'series_vertical_offset', 'series_height', 'pen', 'brush']
    
    @classmethod
    def _build_interval_tuple_list_from_dataframe(cls, df: pd.DataFrame):
        """Build the tuple list required for rendering intervals: fields are (start_t, series_vertical_offset, duration_t, series_height, pen, brush).
        
        Inputs:
            df: a Pandas.DataFrame with the columns ['t_start', 't_duration', 'series_vertical_offset', 'series_height', 'pen', 'brush']
        Returns:
            a list of tuples with fields (start_t, series_vertical_offset, duration_t, series_height, pen, brush)
        """    
        ## Validate that it has all required columns:
        assert np.isin(cls._required_interval_visualization_columns, df.columns).all(), f"dataframe is missing required columns:\n Required: {cls._required_interval_visualization_columns}, current: {df.columns} "
        # Convert datetime t_start values to Unix timestamps for rendering
        if pd.api.types.is_datetime64_any_dtype(df['t_start']) or df['t_start'].apply(lambda x: isinstance(x, (datetime, pd.Timestamp))).any():
            from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp
            df = df.copy()
            df['t_start'] = df['t_start'].apply(
                lambda x: datetime_to_unix_timestamp(x) if isinstance(x, (datetime, pd.Timestamp)) else x
            )
        if 'label' in df.columns:
            return [IntervalRectsItemData(*row) for row in zip(df.t_start, df.series_vertical_offset, df.t_duration, df.series_height, df.pen, df.brush, df.label)]
        else:
            ## most basic
            return [IntervalRectsItemData(*row) for row in zip(df.t_start, df.series_vertical_offset, df.t_duration, df.series_height, df.pen, df.brush)]

    @classmethod
    def build_IntervalRectsItem_from_epoch(cls, epochs, dataframe_vis_columns_function, debug_print=False, **kwargs):
        """Builds an appropriate IntervalRectsItem from any Epoch object and a function that is passed the converted dataframe and adds the visualization specific columns: ['series_vertical_offset', 'series_height', 'pen', 'brush']
        
        Input:
            epochs: Either a neuropy.core.Epoch object (if neuropy is available) OR dataframe with the columns ['t_start', 't_duration']
            dataframe_vis_columns_function: callable that takes a pd.DataFrame that adds the remaining required columns to the dataframe if needed.
        
        Returns:
            IntervalRectsItem
        """
        if Epoch is not None and isinstance(epochs, Epoch):
            # if it's an Epoch, convert it to a dataframe
            raw_df = epochs.to_dataframe()
            active_df = pd.DataFrame({'t_start':raw_df.start.copy(), 't_duration':raw_df.duration.copy()}) # still will need columns ['series_vertical_offset', 'series_height', 'pen', 'brush'] added later

        elif isinstance(epochs, pd.DataFrame):
            # already a dataframe
            active_df = epochs.copy()
        else:
            raise NotImplementedError
        
        active_df = dataframe_vis_columns_function(active_df)
        
        ## build the output tuple list: fields are (start_t, series_vertical_offset, duration_t, series_height, pen, brush).
        curr_IntervalRectsItem_interval_tuples = cls._build_interval_tuple_list_from_dataframe(active_df)
        ## build the IntervalRectsItem
        return IntervalRectsItem(curr_IntervalRectsItem_interval_tuples, **kwargs)
    
    # MAIN METHOD to build datasource ____________________________________________________________________________________ #
    @classmethod
    def build_IntervalRectsItem_from_interval_datasource(cls, interval_datasource, **kwargs):
        """Builds an appropriate IntervalRectsItem from any IntervalsDatasource object 
        
        Input:
            interval_datasource: IntervalsDatasource (or compatible object with .df property)
            **kwargs: Additional arguments passed to IntervalRectsItem constructor
                     (e.g., format_tooltip_fn, format_label_fn, detail_render_callback)
        Returns:
            IntervalRectsItem
        """        
        if IntervalsDatasource is not None and not isinstance(interval_datasource, IntervalsDatasource):
            # Try to use it anyway if it has the required interface
            if not hasattr(interval_datasource, 'df'):
                raise TypeError(f"interval_datasource must have a .df property, but got {type(interval_datasource)}")
        
        active_df = interval_datasource.df
        ## build the output tuple list: fields are (start_t, series_vertical_offset, duration_t, series_height, pen, brush).
        curr_IntervalRectsItem_interval_tuples = cls._build_interval_tuple_list_from_dataframe(active_df)
        ## build the IntervalRectsItem (pass through all kwargs including detail_render_callback)
        return IntervalRectsItem(curr_IntervalRectsItem_interval_tuples, **kwargs)
    
    
    ##################################################
    ## Spike Events METHODS
    ##################################################
                
    ## Debugging rectangles:
    @staticmethod
    def _simple_debugging_rects_data(series_start_offsets):
        """Generates a simple set of test rectangles
        
        Args:
            series_start_offsets: List of vertical offset values
        """
        # Have series_offsets which are centers and series_start_offsets which are bottom edges:
        curr_border_color = pg.mkColor('r')
        curr_border_color.setAlphaF(0.8)
        
        curr_fill_color = pg.mkColor('w')
        curr_fill_color.setAlphaF(0.2)

        # build pen/brush from color
        curr_series_pen = pg.mkPen(curr_border_color)
        curr_series_brush = pg.mkBrush(curr_fill_color)
        
        data = []
        step_x_offset = 0.5
        for i in np.arange(len(series_start_offsets)):
            curr_x_pos = (40.0+(step_x_offset*float(i)))
            data.append((curr_x_pos, series_start_offsets[i], 0.5, 1.0, curr_series_pen, curr_series_brush))
        return data

