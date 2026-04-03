"""GenericPlotDetailRenderer - Generic renderer for arbitrary plot data."""
from typing import List, Mapping, Tuple, Any, Callable, Optional, Dict, Sequence
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import pyqtgraph as pg

from pypho_timeline.rendering.datasources.track_datasource import DetailRenderer
from pypho_timeline.rendering.helpers import ChannelNormalizationMode, ChannelNormalizationModeNormalizingMixin, normalize_channels


class GenericPlotDetailRenderer(DetailRenderer):
    """Generic detail renderer that uses a custom render function.
    
    This renderer allows users to provide their own rendering function for
    custom track types.

    from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import GenericPlotDetailRenderer

    """
    
    def __init__(self, render_fn: Callable[[pg.PlotItem, pd.DataFrame, Any], List[pg.GraphicsObject]],
                 clear_fn: Optional[Callable[[pg.PlotItem, List[pg.GraphicsObject]], None]] = None,
                 bounds_fn: Optional[Callable[[pd.DataFrame, Any], Tuple[float, float, float, float]]] = None):
        """Initialize the generic plot renderer.
        
        Args:
            render_fn: Function that renders detail data and returns list of GraphicsObjects
            clear_fn: Optional function to clear graphics objects (default: removes all items)
            bounds_fn: Optional function to compute detail bounds (default: uses interval bounds)
        """
        self.render_fn = render_fn
        self.clear_fn = clear_fn or self._default_clear
        self.bounds_fn = bounds_fn or self._default_bounds
    
    def render_detail(self, plot_item: pg.PlotItem, interval: pd.DataFrame, detail_data: Any) -> List[pg.GraphicsObject]:
        """Render detail data using the custom render function.
        
        Args:
            plot_item: The pyqtgraph PlotItem to render into
            interval: The interval DataFrame (single row) with 't_start' and 't_duration'
            detail_data: The detailed data (type depends on track type)
            
        Returns:
            List of GraphicsObject items added
        """
        return self.render_fn(plot_item, interval, detail_data)
    
    def clear_detail(self, plot_item: pg.PlotItem, graphics_objects: List[pg.GraphicsObject]) -> None:
        """Clear detail graphics using the custom clear function.
        
        Args:
            plot_item: The pyqtgraph PlotItem
            graphics_objects: List of GraphicsObject items to remove
        """
        self.clear_fn(plot_item, graphics_objects)
    
    def get_detail_bounds(self, interval: pd.DataFrame, detail_data: Any) -> Tuple[float, float, float, float]:
        """Get bounds for the detail view using the custom bounds function.
        
        Args:
            interval: The interval DataFrame (single row) with 't_start' and 't_duration'
            detail_data: The detailed data
            
        Returns:
            Tuple of (x_min, x_max, y_min, y_max)
        """
        return self.bounds_fn(interval, detail_data)
    
    def _default_clear(self, plot_item: pg.PlotItem, graphics_objects: List[pg.GraphicsObject]) -> None:
        """Default clear function that removes all graphics objects."""
        for obj in graphics_objects:
            plot_item.removeItem(obj)
            if hasattr(obj, 'setParentItem'):
                obj.setParentItem(None)
    
    def _default_bounds(self, interval: pd.DataFrame, detail_data: Any) -> Tuple[float, float, float, float]:
        """Default bounds function that uses interval bounds."""
        from datetime import datetime, timedelta
        t_start = interval['t_start'].iloc[0] if len(interval) > 0 and 't_start' in interval.columns else 0.0
        t_duration = interval['t_duration'].iloc[0] if len(interval) > 0 and 't_duration' in interval.columns else 1.0
        
        # Handle datetime objects for t_end calculation
        if isinstance(t_start, (datetime, pd.Timestamp)):
            t_end = t_start + timedelta(seconds=float(t_duration))
            # Convert to Unix timestamps for return value
            from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp
            t_start = datetime_to_unix_timestamp(t_start)
            t_end = datetime_to_unix_timestamp(t_end)
        else:
            t_end = t_start + t_duration
        
        y_offset = interval['series_vertical_offset'].iloc[0] if len(interval) > 0 and 'series_vertical_offset' in interval.columns else 0.0
        y_height = interval['series_height'].iloc[0] if len(interval) > 0 and 'series_height' in interval.columns else 1.0
        
        return (t_start, t_end, y_offset, y_offset + y_height)



"""IntervalPlotDetailRenderer - Renders position data as line plots."""
## TODO: should inherit from `GenericPlotDetailRenderer`
class IntervalPlotDetailRenderer(DetailRenderer):
    """Detail renderer for position tracks that displays position as a line plot.
    
    Expects detail_data to be a DataFrame with columns ['t', 'x', 'y'] or ['t', 'x'].
    """
    
    def __init__(self, pen_color='cyan', pen_width=2, y_column='y'):
        """Initialize the position plot renderer.
        
        Args:
            pen_color: Color for the position line (default: 'cyan')
            pen_width: Width of the position line (default: 2)
            y_column: Column name for y-coordinate (default: 'y', use None for 1D position)
        """
        self.pen_color = pen_color
        self.pen_width = pen_width
        self.y_column = y_column
    

    def render_detail(self, plot_item: pg.PlotItem, interval: pd.DataFrame, detail_data: Any) -> List[pg.GraphicsObject]:
        """Render position data as a line plot.
        
        Args:
            plot_item: The pyqtgraph PlotItem to render into
            interval: The interval DataFrame (single row) with 't_start' and 't_duration'
            detail_data: DataFrame with columns ['t', 'x', 'y'] or ['t', 'x']
            
        Returns:
            List of GraphicsObject items added (PlotDataItem)
        """
        if detail_data is None or len(detail_data) == 0:
            return []
        
        if not isinstance(detail_data, pd.DataFrame):
            raise TypeError(f"IntervalPlotDetailRenderer expects DataFrame, got {type(detail_data)}")
        
        graphics_objects = []
        
        # Check required columns
        if 't' not in detail_data.columns or 'x' not in detail_data.columns:
            return []
        
        # Sort by time
        df_sorted = detail_data.sort_values('t')
        
        t_values = df_sorted['t'].to_numpy(dtype=float, copy=False)
        
        x_values = df_sorted['x'].values
        
        if self.y_column is not None and self.y_column in df_sorted.columns:
            # 2D position plot
            y_values = df_sorted[self.y_column].values
            pen = pg.mkPen(self.pen_color, width=self.pen_width)
            plot_data_item = pg.PlotDataItem(x_values, y_values, pen=pen, connect='finite')
            plot_item.addItem(plot_data_item)
            graphics_objects.append(plot_data_item)
        else:
            # 1D position plot (x vs time)
            pen = pg.mkPen(self.pen_color, width=self.pen_width)
            plot_data_item = pg.PlotDataItem(t_values, x_values, pen=pen, connect='finite')
            plot_item.addItem(plot_data_item)
            graphics_objects.append(plot_data_item)
        
        return graphics_objects
    

    def clear_detail(self, plot_item: pg.PlotItem, graphics_objects: List[pg.GraphicsObject]) -> None:
        """Remove position plot graphics objects.
        
        Args:
            plot_item: The pyqtgraph PlotItem
            graphics_objects: List of GraphicsObject items to remove
        """
        for obj in graphics_objects:
            plot_item.removeItem(obj)
            if hasattr(obj, 'setParentItem'):
                obj.setParentItem(None)
    

    def get_detail_bounds(self, interval: pd.DataFrame, detail_data: Any) -> Tuple[float, float, float, float]:
        """Get bounds for the position plot. Always returns float bounds (Unix timestamps for time axis).
        
        Args:
            interval: The interval DataFrame (single row) with 't_start' and 't_duration'
            detail_data: DataFrame with position data
            
        Returns:
            Tuple of (x_min, x_max, y_min, y_max)
        """
        def _interval_to_float_bounds(interval: pd.DataFrame) -> Tuple[float, float]:
            t_start = interval['t_start'].iloc[0] if len(interval) > 0 and 't_start' in interval.columns else 0.0
            t_duration = interval['t_duration'].iloc[0] if len(interval) > 0 and 't_duration' in interval.columns else 1.0
            if isinstance(t_start, (datetime, pd.Timestamp)):
                from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp
                t_start_float = datetime_to_unix_timestamp(t_start)
                dur_sec = float(t_duration) if not isinstance(t_duration, (timedelta, pd.Timedelta)) else t_duration.total_seconds()
                return (float(t_start_float), float(t_start_float + dur_sec))
            t_start_float = float(t_start)
            dur_sec = float(t_duration) if not isinstance(t_duration, (timedelta, pd.Timedelta)) else t_duration.total_seconds()
            return (t_start_float, float(t_start_float + dur_sec))

        if detail_data is None or len(detail_data) == 0:
            x_min, x_max = _interval_to_float_bounds(interval)
            return (x_min, x_max, 0.0, 1.0)
        if not isinstance(detail_data, pd.DataFrame):
            x_min, x_max = _interval_to_float_bounds(interval)
            return (x_min, x_max, 0.0, 1.0)
        t_min, t_max = _interval_to_float_bounds(interval)
        if self.y_column is not None and self.y_column in detail_data.columns:
            x_min, x_max = detail_data['x'].min(), detail_data['x'].max()
            y_min, y_max = detail_data[self.y_column].min(), detail_data[self.y_column].max()
            x_pad = (x_max - x_min) * 0.1 if x_max > x_min else 1.0
            y_pad = (y_max - y_min) * 0.1 if y_max > y_min else 1.0
            return (x_min - x_pad, x_max + x_pad, y_min - y_pad, y_max + y_pad)
        else:
            x_min, x_max = detail_data['x'].min(), detail_data['x'].max()
            x_pad = (x_max - x_min) * 0.1 if x_max > x_min else 1.0
            return (t_min, t_max, x_min - x_pad, x_max + x_pad)





class DataframePlotDetailRenderer(ChannelNormalizationModeNormalizingMixin, DetailRenderer):
    """Detail renderer for dataframe tracks that displays dataframe channels as line plots.
    
    Expects detail_data to be a DataFrame with columns ['t'] and channel columns.
    Channels can be explicitly specified or auto-detected from numeric columns.

    Usage:
        from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import DataframePlotDetailRenderer

        # Auto-detect channels from DataFrame
        renderer = DataframePlotDetailRenderer()
        
        # Explicitly specify channels
        renderer = DataframePlotDetailRenderer(channel_names=['x', 'y', 'z'])
        
        # Disable normalization to plot raw values
        renderer = DataframePlotDetailRenderer(channel_names=['AccX', 'AccY'], normalize=False)
    """
    
    def __init__(self, pen_width=2, channel_names: Optional[List[str]]=None, pen_colors=None, pen_color='white',
                 fallback_normalization_mode: ChannelNormalizationMode = ChannelNormalizationMode.NONE,
                 normalization_mode_dict: Optional[Dict[Sequence[str], ChannelNormalizationMode]] = None,
                 arbitrary_bounds: Optional[Mapping[str, Tuple[float, float]]] = None,
                 normalize: bool = True, normalize_over_full_data: bool = True, normalization_reference_df: Optional[pd.DataFrame] = None,
                 **kwargs,
                 ):
        """Initialize the dataframe plot renderer.
        
        Args:
            pen_width: Width of the plot lines (default: 2)
            channel_names: Optional list of channel names to plot. If None, auto-detects all numeric columns except 't' (default: None)
            pen_colors: Optional list of colors for each channel (default: None, auto-generated)
            pen_color: Default color for channels (used if channel_names is None and single channel, default: 'cyan')
            normalize: If True, normalize all channels to 0-1 range. If False, plot raw values (default: True)
        """
        self.pen_color = pen_color
        self.pen_colors = pen_colors
        self.pen_width = pen_width


        # Preserve original channel_names semantics (None means auto-detect)
        original_channel_names = channel_names
        self.channel_names = original_channel_names
        # Initialize shared normalization configuration via the mixin
        ChannelNormalizationModeNormalizingMixin.__init__(self, channel_names=(channel_names or []), fallback_normalization_mode=fallback_normalization_mode, normalization_mode_dict=normalization_mode_dict, arbitrary_bounds=arbitrary_bounds, normalize=normalize, normalize_over_full_data=normalize_over_full_data, normalization_reference_df=normalization_reference_df, **kwargs)
        # Restore auto-detect sentinel (mixin does not rely on self.channel_names when we pass channel_names explicitly to compute_normalized_channels)
        self.channel_names = original_channel_names


        # Generate distinct colors for each channel if channel_names is provided
        # (If None, colors will be generated during render_detail when channels are auto-detected)
        if (channel_names is not None) and (pen_colors is None):
            # Predefined palette of distinct colors
            # Generate enough distinct colors for all Dataframe channels using matplotlib's colormap
            import matplotlib.pyplot as plt
            import matplotlib
            num_channels = len(channel_names)
            # Use a rainbow colormap suitable for black/dark backgrounds. 
            # 'nipy_spectral' and 'turbo' are perceptually uniform and good for this.
            cmap = plt.get_cmap('nipy_spectral')
            color_palette = [matplotlib.colors.to_hex(cmap(i / max(num_channels-1, 1))) for i in range(num_channels)]
            # Cycle through palette if more channels than colors
            self.pen_colors = [color_palette[i % len(color_palette)] for i in range(len(channel_names))]
        else:
            self.pen_colors = None

    
    def render_detail(self, plot_item: pg.PlotItem, interval: pd.DataFrame, detail_data: Any) -> List[pg.GraphicsObject]:
        """Render dataframe channels as line plots.
        
        Args:
            plot_item: The pyqtgraph PlotItem to render into
            interval: The interval DataFrame (single row) with 't_start' and 't_duration'
            detail_data: DataFrame with columns ['t'] and channel columns
            
        Returns:
            List of GraphicsObject items added (PlotDataItem)

        Usage:
            a_track_name: str = 'MOTION_Epoc X Dataframe'
            a_renderer = timeline.track_renderers[a_track_name]
            a_detail_renderer = a_renderer.detail_renderer # DataframePlotDetailRenderer 
            a_ds = timeline.track_datasources[a_track_name]
            interval = a_ds.get_overview_intervals()

            dDisplayItem = timeline.ui.dynamic_docked_widget_container.find_display_dock(identifier=a_track_name) # Dock
            a_widget = timeline.ui.matplotlib_view_widgets[a_track_name] # PyqtgraphTimeSynchronizedWidget 
            a_root_graphics_layout_widget = a_widget.getRootGraphicsLayoutWidget()
            a_plot_item = a_widget.getRootPlotItem()

            graphics_objects = a_detail_renderer.render_detail(plot_item=a_plot_item, interval=None, detail_data=a_ds.detailed_df) # List[PlotDataItem]

        """
        if detail_data is None or len(detail_data) == 0:
            return []
        
        if not isinstance(detail_data, pd.DataFrame):
            raise TypeError(f"DataframePlotDetailRenderer expects DataFrame, got {type(detail_data)}")
        
        graphics_objects = []
        
        # Check required columns
        if 't' not in detail_data.columns:
            return []
        
        # Sort by time
        df_sorted = detail_data.sort_values('t')
        
        t_values = df_sorted['t'].to_numpy(dtype=float, copy=False)

        # Clamp x-values to owning interval bounds to prevent visual drift
        if interval is not None and len(interval) > 0 and 't_start' in interval.columns and 't_duration' in interval.columns and len(t_values) > 0:
            from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp
            _t_start_raw = interval['t_start'].iloc[0]
            _t_dur = float(interval['t_duration'].iloc[0])
            _t_start_unix = float(datetime_to_unix_timestamp(_t_start_raw)) if isinstance(_t_start_raw, (datetime, pd.Timestamp)) else float(_t_start_raw)
            _t_end_unix = _t_start_unix + _t_dur
            in_interval_mask = np.logical_and(t_values >= _t_start_unix, t_values <= _t_end_unix)
            if np.any(in_interval_mask):
                t_values = t_values[in_interval_mask]
                df_sorted = df_sorted.iloc[in_interval_mask]
            elif len(t_values) > 1:
                t_values = np.linspace(_t_start_unix, _t_end_unix, num=len(t_values), endpoint=True)

        if len(t_values) == 0:
            return graphics_objects

        # Auto-detect channels if channel_names is None
        if self.channel_names is None:
            # Auto-detect: all numeric columns except 't'
            numeric_cols = df_sorted.select_dtypes(include=[np.number]).columns.tolist()
            channel_names_to_use = [col for col in numeric_cols if col != 't']
            if len(channel_names_to_use) == 0:
                return []  # No channels found
            # Generate colors for auto-detected channels
            if self.pen_colors is None:
                import matplotlib.pyplot as plt
                import matplotlib
                num_channels = len(channel_names_to_use)
                cmap = plt.get_cmap('nipy_spectral')
                color_palette = [matplotlib.colors.to_hex(cmap(i / max(num_channels-1, 1))) for i in range(num_channels)]
                pen_colors_to_use = [color_palette[i % len(color_palette)] for i in range(len(channel_names_to_use))]
            else:
                # Use provided colors, cycling if there are more channels than colors
                pen_colors_to_use = [self.pen_colors[i % len(self.pen_colors)] for i in range(len(channel_names_to_use))]
        else:
            # Use explicitly provided channel names
            channel_names_to_use = self.channel_names
            found_channel_names: List[str] = [k for k in channel_names_to_use if (k in df_sorted.columns)]
            # Only assert all channels required when channel_names was explicitly provided
            found_all_channel_names: bool = len(found_channel_names) == len(channel_names_to_use)
            if not found_all_channel_names:
                missing_channels = set(channel_names_to_use) - set(found_channel_names)
                raise ValueError(f"Missing channels: {missing_channels}")
            channel_names_to_use = found_channel_names
            pen_colors_to_use = self.pen_colors if self.pen_colors is not None else [self.pen_color] * len(channel_names_to_use)
        
        # Filter channels based on visibility if channel_visibility is set
        if hasattr(self, 'channel_visibility') and self.channel_visibility:
            original_channel_names_to_use = channel_names_to_use.copy()
            channel_names_to_use = [ch for ch in channel_names_to_use if self.channel_visibility.get(ch, True)]
            # Update pen_colors_to_use to match filtered channels
            if self.channel_names is not None and self.pen_colors is not None:
                # Rebuild pen_colors_to_use based on filtered channels, preserving original order
                filtered_pen_colors = []
                for ch in channel_names_to_use:
                    if ch in self.channel_names:
                        idx = self.channel_names.index(ch)
                        if idx < len(self.pen_colors):
                            filtered_pen_colors.append(self.pen_colors[idx])
                        else:
                            filtered_pen_colors.append(self.pen_color)
                    else:
                        filtered_pen_colors.append(self.pen_color)
                pen_colors_to_use = filtered_pen_colors
            elif self.channel_names is None:
                # Auto-detected channels: rebuild pen_colors_to_use based on filtered order
                filtered_pen_colors = []
                for ch in channel_names_to_use:
                    if ch in original_channel_names_to_use:
                        orig_idx = original_channel_names_to_use.index(ch)
                        if orig_idx < len(pen_colors_to_use):
                            filtered_pen_colors.append(pen_colors_to_use[orig_idx])
                        else:
                            filtered_pen_colors.append(self.pen_color)
                    else:
                        filtered_pen_colors.append(self.pen_color)
                pen_colors_to_use = filtered_pen_colors
            elif len(pen_colors_to_use) > len(channel_names_to_use):
                # Truncate pen_colors_to_use to match filtered channels (simple case)
                pen_colors_to_use = pen_colors_to_use[:len(channel_names_to_use)]

        # Normalize channels if requested using shared mixin helper
        if self.normalize:
            normalized_channel_df, (y_min, y_max) = self.compute_normalized_channels(detail_df=df_sorted, channel_names=channel_names_to_use)
            use_normalized = True
        else:
            use_normalized = False
            

        # Plot each channel with its distinct color
        for idx, channel_name in enumerate(channel_names_to_use):
            if use_normalized:
                y_values = normalized_channel_df[channel_name].values
            else:
                y_values = df_sorted[channel_name].values
            
            # Get the color for this channel
            if self.channel_names is not None:
                # Use color based on original channel_names index
                channel_index = self.channel_names.index(channel_name)
                channel_color = pen_colors_to_use[channel_index] if len(pen_colors_to_use) > channel_index else self.pen_color
            else:
                # Use color based on auto-detected order
                channel_color = pen_colors_to_use[idx] if idx < len(pen_colors_to_use) else self.pen_color
            
            pen = pg.mkPen(channel_color, width=self.pen_width)
            plot_data_item = pg.PlotDataItem(t_values, y_values, pen=pen, connect='finite', name=channel_name)
            plot_item.addItem(plot_data_item)
            graphics_objects.append(plot_data_item)
        
        return graphics_objects
    

    def clear_detail(self, plot_item: pg.PlotItem, graphics_objects: List[pg.GraphicsObject]) -> None:
        """Remove dataframe plot graphics objects.
        
        Args:
            plot_item: The pyqtgraph PlotItem
            graphics_objects: List of GraphicsObject items to remove
        """
        if graphics_objects is None:
            return
        
        for obj in graphics_objects:
            if obj is None:
                continue
            try:
                plot_item.removeItem(obj)
                if hasattr(obj, 'setParentItem'):
                    obj.setParentItem(None)
            except (AttributeError, RuntimeError):
                # Item may have already been removed or is invalid
                pass

                
    
    def get_detail_bounds(self, interval: pd.DataFrame, detail_data: Any) -> Tuple[float, float, float, float]:
        """Get bounds for the dataframe plot.
        
        Args:
            interval: The interval DataFrame (single row) with 't_start' and 't_duration'
            detail_data: DataFrame with dataframe data (columns: 't' and channel columns)
            
        Returns:
            Tuple of (x_min, x_max, y_min, y_max) where x is time and y is channel values
        """
        has_valid_detail_data: bool = (detail_data is not None) and isinstance(detail_data, pd.DataFrame) and (len(detail_data) > 0)
        if (interval is None) or (len(interval) == 0):
            # If interval is None or empty, attempt to determine t_start and t_end from detail_data
            if has_valid_detail_data:
                # Try to get time column: use 't' if present, otherwise index values if they look like times
                if 't' in detail_data.columns:
                    t_min = detail_data['t'].min()
                    t_max = detail_data['t'].max()
                    # Convert datetime to Unix timestamp if needed
                    if isinstance(t_min, (datetime, pd.Timestamp)):
                        from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp
                        t_start = datetime_to_unix_timestamp(t_min)
                        t_end = datetime_to_unix_timestamp(t_max)
                    else:
                        t_start = float(t_min)
                        t_end = float(t_max)
                else:
                    # Fallback: use DataFrame index if it is numeric and sorted
                    try:
                        idx = detail_data.index
                        if hasattr(idx, 'dtype') and np.issubdtype(idx.dtype, np.number):
                            t_start = float(idx.min())
                            t_end = float(idx.max())
                        else:
                            t_start = 0.0
                            t_end = 1.0
                    except Exception:
                        t_start = 0.0
                        t_end = 1.0
            else:
                raise ValueError(f'has_valid_detail_data is False')
                # t_start = 0.0
                # t_end = 1.0

            t_duration = t_end - t_start
        else:
            ## interval is provided
            t_start = interval['t_start'].iloc[0] if len(interval) > 0 and 't_start' in interval.columns else 0.0
            t_duration = interval['t_duration'].iloc[0] if len(interval) > 0 and 't_duration' in interval.columns else 1.0
            t_end = t_start + t_duration
        
        if detail_data is None or len(detail_data) == 0:
            return (t_start, t_end, 0.0, 1.0)
        
        if not isinstance(detail_data, pd.DataFrame):
            return (t_start, t_end, 0.0, 1.0)
        
        # Determine which channel columns to use
        if self.channel_names is None:
            # Auto-detect: all numeric columns except 't'
            numeric_cols = detail_data.select_dtypes(include=[np.number]).columns.tolist()
            channel_columns = [col for col in numeric_cols if col != 't']
        else:
            # Get all channel columns that exist in the data
            channel_columns = [col for col in self.channel_names if col in detail_data.columns]
        
        if channel_columns:
            # Find min/max across all channels
            y_min = min(detail_data[col].min() for col in channel_columns)
            y_max = max(detail_data[col].max() for col in channel_columns)
            # Add padding
            y_pad = (y_max - y_min) * 0.1 if y_max > y_min else 1.0
            return (t_start, t_end, (y_min - y_pad), (y_max + y_pad))
        else:
            # No channels found, use default bounds
            return (t_start, t_end, 0.0, 1.0)




__all__ = ['GenericPlotDetailRenderer', 'IntervalPlotDetailRenderer', 'DataframePlotDetailRenderer']