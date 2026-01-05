"""MotionPlotDetailRenderer - Renders motion data as line plots."""
from typing import List, Tuple, Any
import numpy as np
import pandas as pd
import pyphoplacecellanalysis.External.pyqtgraph as pg

from pypho_timeline.rendering.datasources.track_datasource import DetailRenderer
from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import GenericPlotDetailRenderer


## TODO: should implement/conform to `DetailRenderer`
## TODO: should inherit from `GenericPlotDetailRenderer`
class MotionPlotDetailRenderer(DetailRenderer):
    """Detail renderer for motion tracks that displays motion channels as line plots.
    
    Expects detail_data to be a DataFrame with columns ['t'] and channel columns
    (e.g., ['AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'GyroZ']).

    Usage:

        from pypho_timeline.rendering.detail_renderers.motion_plot_renderer import MotionPlotDetailRenderer
    """
    
    def __init__(self, pen_width=2, channel_names=['AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'GyroZ'], pen_colors=None):
        """Initialize the motion plot renderer.
        
        Args:
            pen_color: Default color for channels (used if channel_names is None, default: 'cyan')
            pen_width: Width of the plot lines (default: 2)
            channel_names: List of channel names to plot (default: ['AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'GyroZ'])
        """
        self.pen_colors = pen_colors
        self.pen_width = pen_width
        self.channel_names = channel_names
        
        # Generate distinct colors for each channel
        if (channel_names is not None) and (pen_colors is None):
            # Predefined palette of distinct colors
            color_palette = ['red', 'green', 'blue', 'yellow', 'magenta', 'cyan', 'orange', 'purple']
            # Cycle through palette if more channels than colors
            self.pen_colors = [color_palette[i % len(color_palette)] for i in range(len(channel_names))]
        else:
            self.pen_colors = None

    
    def render_detail(self, plot_item: pg.PlotItem, interval: pd.Series, detail_data: Any) -> List[pg.GraphicsObject]:
        """Render motion data as line plots for each channel.
        
        Args:
            plot_item: The pyqtgraph PlotItem to render into
            interval: The interval Series with 't_start' and 't_duration'
            detail_data: DataFrame with columns ['t'] and channel columns (e.g., ['AccX', 'AccY', ...])
            
        Returns:
            List of GraphicsObject items added (PlotDataItem)
        """
        if detail_data is None or len(detail_data) == 0:
            return []
        
        if not isinstance(detail_data, pd.DataFrame):
            raise TypeError(f"MotionPlotDetailRenderer expects DataFrame, got {type(detail_data)}")
        
        graphics_objects = []
        
        # Check required columns
        if 't' not in detail_data.columns or 'x' not in detail_data.columns:
            return []
        
        # Sort by time
        df_sorted = detail_data.sort_values('t')
        t_values = df_sorted['t'].values
        
        if (self.channel_names is not None):
            found_channel_names: List[str] = [k for k in self.channel_names if (k in df_sorted.columns)]
            found_all_channel_names: bool = len(found_channel_names) == len(self.channel_names)
            assert found_all_channel_names

            # Plot each channel with its distinct color
            for a_found_channel_name in found_channel_names:
                y_values = df_sorted[a_found_channel_name].values
                # Get the color for this channel based on its index in channel_names
                channel_index = self.channel_names.index(a_found_channel_name)
                channel_color = self.pen_colors[channel_index]
                pen = pg.mkPen(channel_color, width=self.pen_width)
                plot_data_item = pg.PlotDataItem(t_values, y_values, pen=pen, connect='finite', name=a_found_channel_name)
                plot_item.addItem(plot_data_item)
                graphics_objects.append(plot_data_item)
        else:
            # Fallback: use single pen_color if channel_names is None
            if 'x' in df_sorted.columns:
                x_values = df_sorted['x'].values
                pen = pg.mkPen(self.pen_color, width=self.pen_width)
                plot_data_item = pg.PlotDataItem(t_values, x_values, pen=pen, connect='finite')
                plot_item.addItem(plot_data_item)
                graphics_objects.append(plot_data_item)

        
        return graphics_objects
    
    def clear_detail(self, plot_item: pg.PlotItem, graphics_objects: List[pg.GraphicsObject]) -> None:
        """Remove motion plot graphics objects.
        
        Args:
            plot_item: The pyqtgraph PlotItem
            graphics_objects: List of GraphicsObject items to remove
        """
        for obj in graphics_objects:
            plot_item.removeItem(obj)
            if hasattr(obj, 'setParentItem'):
                obj.setParentItem(None)
    
    def get_detail_bounds(self, interval: pd.Series, detail_data: Any) -> Tuple[float, float, float, float]:
        """Get bounds for the motion plot.
        
        Args:
            interval: The interval Series with 't_start' and 't_duration'
            detail_data: DataFrame with motion data (columns: 't' and channel columns)
            
        Returns:
            Tuple of (x_min, x_max, y_min, y_max) where x is time and y is channel values
        """
        t_start = interval.get('t_start', 0.0)
        t_duration = interval.get('t_duration', 1.0)
        t_end = t_start + t_duration
        
        if detail_data is None or len(detail_data) == 0:
            return (t_start, t_end, 0.0, 1.0)
        
        if not isinstance(detail_data, pd.DataFrame):
            return (t_start, t_end, 0.0, 1.0)
        
        # Calculate y-axis bounds from all channel values
        if self.channel_names is not None:
            # Get all channel columns that exist in the data
            channel_columns = [col for col in self.channel_names if col in detail_data.columns]
            if channel_columns:
                # Find min/max across all channels
                y_min = min(detail_data[col].min() for col in channel_columns)
                y_max = max(detail_data[col].max() for col in channel_columns)
                # Add padding
                y_pad = (y_max - y_min) * 0.1 if y_max > y_min else 1.0
                return (t_start, t_end, y_min - y_pad, y_max + y_pad)
            else:
                # No channels found, use default bounds
                return (t_start, t_end, 0.0, 1.0)
        else:
            # Fallback: if channel_names is None, check for 'x' column
            if 'x' in detail_data.columns:
                x_min, x_max = detail_data['x'].min(), detail_data['x'].max()
                x_pad = (x_max - x_min) * 0.1 if x_max > x_min else 1.0
                return (t_start, t_end, x_min - x_pad, x_max + x_pad)
            else:
                return (t_start, t_end, 0.0, 1.0)


__all__ = ['MotionPlotDetailRenderer']

