"""VideoThumbnailDetailRenderer - Renders video frames as thumbnails."""
from typing import List, Tuple, Any, Optional
import numpy as np
import pandas as pd
import pyphoplacecellanalysis.External.pyqtgraph as pg
from pypho_timeline.rendering.datasources.track_datasource import DetailRenderer
from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import GenericPlotDetailRenderer

## TODO: should implement/conform to `DetailRenderer`
## TODO: should inherit from `GenericPlotDetailRenderer`
class VideoThumbnailDetailRenderer(DetailRenderer):
    """Detail renderer for video tracks that displays video frames as thumbnails.
    
    Expects detail_data to be either:
    - A numpy array of shape (n_frames, height, width, channels) or (n_frames, height, width)
    - A list of numpy arrays (one per frame)
    - A dictionary with 'frames' key containing frame data and optional 'timestamps' key
    """
    
    def __init__(self, thumbnail_height: float = 50.0, spacing: float = 0.1):
        """Initialize the video thumbnail renderer.
        
        Args:
            thumbnail_height: Height of each thumbnail in plot coordinates (default: 50.0)
            spacing: Spacing between thumbnails as fraction of interval duration (default: 0.1)
        """
        self.thumbnail_height = thumbnail_height
        self.spacing = spacing
    
    def render_detail(self, plot_item: pg.PlotItem, interval: pd.Series, detail_data: Any) -> List[pg.GraphicsObject]:
        """Render video frames as thumbnails.
        
        Args:
            plot_item: The pyqtgraph PlotItem to render into
            interval: The interval Series with 't_start' and 't_duration'
            detail_data: Video frame data (see class docstring for formats)
            
        Returns:
            List of GraphicsObject items added (ImageItem objects)
        """
        if detail_data is None:
            return []
        
        graphics_objects = []
        t_start = interval.get('t_start', 0.0)
        t_duration = interval.get('t_duration', 1.0)
        
        # Parse detail_data format
        frames = None
        timestamps = None
        
        if isinstance(detail_data, dict):
            frames = detail_data.get('frames', None)
            timestamps = detail_data.get('timestamps', None)
        elif isinstance(detail_data, (list, tuple)):
            frames = detail_data
        elif isinstance(detail_data, np.ndarray):
            # Assume shape is (n_frames, height, width, channels) or (n_frames, height, width)
            if detail_data.ndim >= 3:
                frames = [detail_data[i] for i in range(len(detail_data))]
            else:
                return []  # Invalid shape
        else:
            return []  # Unknown format
        
        if frames is None or len(frames) == 0:
            return []
        
        # Calculate thumbnail positions
        n_frames = len(frames)
        if n_frames == 0:
            return []
        
        # Distribute thumbnails across the interval
        total_spacing = t_duration * self.spacing
        available_width = t_duration - total_spacing
        thumbnail_width = available_width / n_frames if n_frames > 0 else t_duration
        
        # Get y position (center of interval vertically)
        y_center = interval.get('series_vertical_offset', 0.0) + interval.get('series_height', self.thumbnail_height) / 2.0
        y_bottom = y_center - self.thumbnail_height / 2.0
        
        # Render each frame
        for i, frame in enumerate(frames):
            if frame is None:
                continue
            
            # Calculate x position
            x_start = t_start + i * (thumbnail_width + total_spacing / max(1, n_frames - 1))
            
            # Convert frame to image format if needed
            img_data = self._prepare_frame_image(frame)
            if img_data is None:
                continue
            
            # Create ImageItem
            img_item = pg.ImageItem(img_data)
            
            # Set position and size
            img_item.setRect(pg.QtCore.QRectF(
                x_start, y_bottom, 
                thumbnail_width, self.thumbnail_height
            ))
            
            # Add to plot
            plot_item.addItem(img_item)
            graphics_objects.append(img_item)
        
        return graphics_objects
    
    def _prepare_frame_image(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Prepare a frame for display as an image.
        
        Args:
            frame: Frame data as numpy array
            
        Returns:
            Image array ready for ImageItem, or None if invalid
        """
        if not isinstance(frame, np.ndarray):
            return None
        
        # Handle different input formats
        if frame.ndim == 2:
            # Grayscale (height, width) -> (height, width, 1)
            img = frame[:, :, np.newaxis]
        elif frame.ndim == 3:
            if frame.shape[2] == 1:
                # Grayscale with channel dimension
                img = frame
            elif frame.shape[2] == 3:
                # RGB
                img = frame
            elif frame.shape[2] == 4:
                # RGBA
                img = frame
            else:
                return None
        else:
            return None
        
        # Normalize to 0-255 if needed
        if img.dtype != np.uint8:
            if img.max() <= 1.0:
                img = (img * 255).astype(np.uint8)
            else:
                img = np.clip(img, 0, 255).astype(np.uint8)
        
        return img
    
    def clear_detail(self, plot_item: pg.PlotItem, graphics_objects: List[pg.GraphicsObject]) -> None:
        """Remove video thumbnail graphics objects.
        
        Args:
            plot_item: The pyqtgraph PlotItem
            graphics_objects: List of GraphicsObject items to remove
        """
        for obj in graphics_objects:
            plot_item.removeItem(obj)
            if hasattr(obj, 'setParentItem'):
                obj.setParentItem(None)
    
    def get_detail_bounds(self, interval: pd.Series, detail_data: Any) -> Tuple[float, float, float, float]:
        """Get bounds for the video thumbnails.
        
        Args:
            interval: The interval Series with 't_start' and 't_duration'
            detail_data: Video frame data
            
        Returns:
            Tuple of (x_min, x_max, y_min, y_max)
        """
        t_start = interval.get('t_start', 0.0)
        t_duration = interval.get('t_duration', 1.0)
        t_end = t_start + t_duration
        
        y_center = interval.get('series_vertical_offset', 0.0) + interval.get('series_height', self.thumbnail_height) / 2.0
        y_min = y_center - self.thumbnail_height / 2.0
        y_max = y_center + self.thumbnail_height / 2.0
        
        return (t_start, t_end, y_min, y_max)


__all__ = ['VideoThumbnailDetailRenderer']

