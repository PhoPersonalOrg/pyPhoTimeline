"""LogTextDataFramePlotDetailRenderer - Renders text log events as text labels."""
from typing import List, Optional, Tuple, Any
import numpy as np
import pandas as pd
import pyphoplacecellanalysis.External.pyqtgraph as pg

from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import DataframePlotDetailRenderer


class LogTextDataFramePlotDetailRenderer(DataframePlotDetailRenderer):
    """Detail renderer for text log events that displays messages as text labels.
    
    Expects detail_data to be a DataFrame with columns ['t', 'message'].
    Text labels are positioned at their time coordinates and displayed vertically.
    
    Usage:
        from pypho_timeline.rendering.detail_renderers.log_text_plot_renderer import LogTextDataFramePlotDetailRenderer
        
        renderer = LogTextDataFramePlotDetailRenderer(text_color='white', text_size=10)
    """
    
    def __init__(self, channel_names: Optional[List[str]]=None, text_color='white', text_size=10, text_rotation=90, y_position=0.5, anchor=(0, 0.5)):
        """Initialize the text log plot renderer.
        
        Args:
            text_color: Color for text labels (default: 'white')
            text_size: Font size in points (default: 10)
            text_rotation: Rotation angle in degrees (default: 90 for vertical)
            y_position: Y-coordinate for text placement (default: 0.5)
            anchor: Text anchor point as (x, y) tuple (default: (0, 0.5) for left-center)
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
    
    def render_detail(self, plot_item: pg.PlotItem, interval: pd.DataFrame, detail_data: Any) -> List[pg.GraphicsObject]:
        """Render text log events as text labels.
        
        Args:
            plot_item: The pyqtgraph PlotItem to render into
            interval: The interval DataFrame (single row) with 't_start' and 't_duration'
            detail_data: DataFrame with columns ['t', 'message']
            
        Returns:
            List of GraphicsObject items added (TextItem)
        """
        if detail_data is None or len(detail_data) == 0:
            return []
        
        if not isinstance(detail_data, pd.DataFrame):
            raise TypeError(f"LogTextDataFramePlotDetailRenderer expects DataFrame, got {type(detail_data)}")
        
        graphics_objects = []
        
        # Check required columns
        if 't' not in detail_data.columns or 'message' not in detail_data.columns:
            return []
        
        # Sort by time
        df_sorted = detail_data.sort_values('t')
        
        # Create a TextItem for each message
        for idx, row in df_sorted.iterrows():
            t_value = float(row['t'])
            message = str(row['message'])
            
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
            detail_data: DataFrame with text log data (columns: 't' and 'message')
            
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
            t_end = t_start + t_duration
        
        # Text logs don't have numeric y-values, so use fixed y-bounds
        return (t_start, t_end, 0.0, 1.0)


__all__ = ['LogTextDataFramePlotDetailRenderer']

