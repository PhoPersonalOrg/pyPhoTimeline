"""LogTextDataFramePlotDetailRenderer - Renders text log events as text labels."""
from typing import List, Optional, Tuple, Any
from datetime import datetime
import numpy as np
import pandas as pd
import pypho_timeline.EXTERNAL.pyqtgraph as pg

from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import DataframePlotDetailRenderer


class LogTextDataFramePlotDetailRenderer(DataframePlotDetailRenderer):
    """Detail renderer for text log events that displays messages as text labels.
    
    Expects detail_data to be a DataFrame with columns ['t'] and channel columns (default: ['message']).
    Text labels are positioned at their time coordinates and displayed vertically.
    
    Usage:
        from pypho_timeline.rendering.detail_renderers.log_text_plot_renderer import LogTextDataFramePlotDetailRenderer
        
        # Use default channel 'message'
        renderer = LogTextDataFramePlotDetailRenderer(text_color='white', text_size=10)
        
        # Use custom channel names
        renderer = LogTextDataFramePlotDetailRenderer(channel_names=['log_message', 'level'], text_color='white', text_size=10)
    """
    
    def __init__(self, channel_names: Optional[List[str]]=None, text_color='white', text_size=10, text_rotation=90, y_position=0.0, anchor=(0.5, 0.5), line_color=None, line_width=1, enable_lines=True):
        """Initialize the text log plot renderer.
        
        Args:
            channel_names: Optional list of channel names to display. If None, defaults to ['message'] (default: None)
            text_color: Color for text labels (default: 'white')
            text_size: Font size in points (default: 10)
            text_rotation: Rotation angle in degrees (default: 90 for vertical)
            y_position: Y-coordinate for text placement (default: 0.5)
            anchor: Text anchor point as (x, y) tuple (default: (0, 0.5) for left-center)  A value of (0,0) sets the upper-left corner of the text box to be at the position specified by setPos(), while a value of (1,1) sets the lower-right corner.
            line_color: Color for vertical lines. If None, defaults to text_color (default: None)
            line_width: Width of vertical lines in pixels (default: 1)
            enable_lines: Whether to draw vertical lines at message times (default: True)
        """
        if channel_names is None:
            channel_names = ['message']

        # Initialize parent with minimal params to skip line plotting logic
        super().__init__(pen_width=1, channel_names=channel_names, normalize=False)
        self.text_color = text_color
        self.text_size = text_size
        self.text_rotation = text_rotation
        self.y_position = y_position
        self.anchor = anchor
        self.line_color = line_color if line_color is not None else text_color
        self.line_width = line_width
        self.enable_lines = enable_lines
    

    def render_detail(self, plot_item: pg.PlotItem, interval: pd.DataFrame, detail_data: Any) -> List[pg.GraphicsObject]:
        """Render text log events as text labels with optional vertical lines.
        
        Args:
            plot_item: The pyqtgraph PlotItem to render into
            interval: The interval DataFrame (single row) with 't_start' and 't_duration'
            detail_data: DataFrame with columns ['t'] and channel columns (default: ['message'])
            
        Returns:
            List of GraphicsObject items added (InfiniteLine and TextItem)
        """
        if detail_data is None or len(detail_data) == 0:
            return []
        
        if not isinstance(detail_data, pd.DataFrame):
            raise TypeError(f"LogTextDataFramePlotDetailRenderer expects DataFrame, got {type(detail_data)}")
        
        graphics_objects = []
        
        # Check required columns
        if 't' not in detail_data.columns:
            return []
        
        # Determine which channel columns to use
        channel_names_to_use = self.channel_names
        if channel_names_to_use is None:
            # Auto-detect: all non-numeric columns except 't'
            non_numeric_cols = detail_data.select_dtypes(exclude=[np.number]).columns.tolist()
            channel_names_to_use = [col for col in non_numeric_cols if col != 't']
            if len(channel_names_to_use) == 0:
                return []  # No channels found
        else:
            # Use explicitly provided channel names
            found_channel_names: List[str] = [k for k in channel_names_to_use if (k in detail_data.columns)]
            # Only assert all channels required when channel_names was explicitly provided
            found_all_channel_names: bool = len(found_channel_names) == len(channel_names_to_use)
            if not found_all_channel_names:
                missing_channels = set(channel_names_to_use) - set(found_channel_names)
                raise ValueError(f"Missing channels: {missing_channels}")
            channel_names_to_use = found_channel_names
        
        # Sort by time
        df_sorted = detail_data.sort_values('t')

        # # Compute interval bounds as unix seconds so we can clamp log events
        # interval_t_start_unix: Optional[float] = None
        # interval_t_end_unix: Optional[float] = None
        # if interval is not None and len(interval) > 0 and 't_start' in interval.columns and 't_duration' in interval.columns:
        #     from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp
        #     _t_start_raw = interval['t_start'].iloc[0]
        #     _t_dur = float(interval['t_duration'].iloc[0])
        #     interval_t_start_unix = float(datetime_to_unix_timestamp(_t_start_raw)) if isinstance(_t_start_raw, (datetime, pd.Timestamp)) else float(_t_start_raw)
        #     interval_t_end_unix = interval_t_start_unix + _t_dur

        # Create a TextItem for each row, displaying all channel values
        for idx, row in df_sorted.iterrows():
            t_value = float(row['t'])

            # # Skip events that fall outside the owning interval bounds
            # if interval_t_start_unix is not None and interval_t_end_unix is not None:
            #     if t_value < interval_t_start_unix or t_value > interval_t_end_unix:
            #         continue
            
            # Create vertical line at message time if enabled
            if self.enable_lines:
                vline = pg.InfiniteLine(angle=90, movable=False, pos=t_value)
                vline.setPen(pg.mkPen(color=self.line_color, width=self.line_width))
                vline.setZValue(-10)  # Render lines behind text labels
                plot_item.addItem(vline, ignoreBounds=True)
                graphics_objects.append(vline)
            
            # Combine all channel values into a single text string
            text_parts = []
            for channel_name in channel_names_to_use:
                channel_value = str(row[channel_name])
                if len(channel_names_to_use) > 1:
                    text_parts.append(f"{channel_name}: {channel_value}")
                else:
                    text_parts.append(channel_value)
            
            message = " | ".join(text_parts)
            
            # Create text item
            text_item = pg.TextItem(
                text=message,
                color=self.text_color,
                anchor=self.anchor
            )
            
            # Set font size
            font = text_item.textItem.font()
            font.setPointSize(self.text_size)
            text_item.textItem.setFont(font)
            
            # Set position
            text_item.setPos(t_value, self.y_position)
            
            # Set rotation if needed
            if self.text_rotation != 0:
                text_item.setRotation(self.text_rotation)
            
            # Add to plot
            plot_item.addItem(text_item)
            graphics_objects.append(text_item)
        
        return graphics_objects
    

    def get_detail_bounds(self, interval: pd.DataFrame, detail_data: Any) -> Tuple[float, float, float, float]:
        """Get bounds for the text log plot.
        
        Args:
            interval: The interval DataFrame (single row) with 't_start' and 't_duration'
            detail_data: DataFrame with text log data (columns: 't' and channel columns)
            
        Returns:
            Tuple of (x_min, x_max, y_min, y_max) where x is time and y is fixed (0.0 to 1.0)
        """
        has_valid_detail_data: bool = (detail_data is not None) and isinstance(detail_data, pd.DataFrame) and (len(detail_data) > 0)
        if (interval is None) or (len(interval) == 0):
            # If interval is None or empty, attempt to determine t_start and t_end from detail_data
            if has_valid_detail_data:
                # Try to get time column: use 't' if present
                if 't' in detail_data.columns:
                    t_start = float(detail_data['t'].min())
                    t_end = float(detail_data['t'].max())
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
            
            t_duration = t_end - t_start
        else:
            ## interval is provided
            t_start = interval['t_start'].iloc[0] if len(interval) > 0 and 't_start' in interval.columns else 0.0
            t_duration = interval['t_duration'].iloc[0] if len(interval) > 0 and 't_duration' in interval.columns else 1.0
            
            # Handle datetime objects for t_end calculation
            if isinstance(t_start, (datetime, pd.Timestamp)):
                from datetime import timedelta
                t_end = t_start + timedelta(seconds=float(t_duration))
                # Convert to Unix timestamp for return value
                from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp
                t_start = datetime_to_unix_timestamp(t_start)
                t_end = datetime_to_unix_timestamp(t_end)
            else:
                t_end = t_start + t_duration
        
        # Ensure t_start and t_end are floats (Unix timestamps) for return value
        if isinstance(t_start, (datetime, pd.Timestamp)):
            from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp
            t_start = datetime_to_unix_timestamp(t_start)
        if isinstance(t_end, (datetime, pd.Timestamp)):
            from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp
            t_end = datetime_to_unix_timestamp(t_end)
        
        # Text logs don't have numeric y-values, so use fixed y-bounds
        return (t_start, t_end, 0.0, 1.0)


__all__ = ['LogTextDataFramePlotDetailRenderer']

