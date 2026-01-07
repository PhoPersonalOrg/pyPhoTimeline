import numpy as np
import pandas as pd
# from qtpy import QtWidgets, QtCore
from typing import Dict, List, Tuple, Optional, Callable, Union, Any
import pyphoplacecellanalysis.External.pyqtgraph as pg
# from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode
# from pypho_timeline.docking.nested_dock_area_widget import NestedDockAreaWidget
# from pypho_timeline.docking.specific_dock_widget_mixin import SpecificDockWidgetManipulatingMixin
# from pypho_timeline.docking.dock_display_configs import CustomCyclicColorsDockDisplayConfig, NamedColorScheme
# from pypho_timeline.core.pyqtgraph_time_synchronized_widget import PyqtgraphTimeSynchronizedWidget
# from pypho_timeline.rendering.graphics.interval_rects_item import IntervalRectsItem, IntervalRectsItemData
from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, BaseTrackDatasource, IntervalProvidingTrackDatasource, DetailRenderer
from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import GenericPlotDetailRenderer


# ==================================================================================================================================================================================================================================================================================== #
# VideoThumbnailDetailRenderer - Renders video frames as thumbnails.                                                                                                                                                                                                                              #
# ==================================================================================================================================================================================================================================================================================== #

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
    
    def render_detail(self, plot_item: pg.PlotItem, interval: pd.DataFrame, detail_data: Any) -> List[pg.GraphicsObject]:
        """Render video frames as thumbnails.
        
        Args:
            plot_item: The pyqtgraph PlotItem to render into
            interval: The interval DataFrame (single row) with 't_start' and 't_duration'
            detail_data: Video frame data (see class docstring for formats)
            
        Returns:
            List of GraphicsObject items added (ImageItem objects)
        """
        if detail_data is None:
            return []
        
        graphics_objects = []
        t_start = interval['t_start'].iloc[0] if len(interval) > 0 and 't_start' in interval.columns else 0.0
        t_duration = interval['t_duration'].iloc[0] if len(interval) > 0 and 't_duration' in interval.columns else 1.0
        
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
        y_offset = interval['series_vertical_offset'].iloc[0] if len(interval) > 0 and 'series_vertical_offset' in interval.columns else 0.0
        y_height = interval['series_height'].iloc[0] if len(interval) > 0 and 'series_height' in interval.columns else self.thumbnail_height
        y_center = y_offset + y_height / 2.0
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
    
    def get_detail_bounds(self, interval: pd.DataFrame, detail_data: Any) -> Tuple[float, float, float, float]:
        """Get bounds for the video thumbnails.
        
        Args:
            interval: The interval DataFrame (single row) with 't_start' and 't_duration'
            detail_data: Video frame data
            
        Returns:
            Tuple of (x_min, x_max, y_min, y_max)
        """
        t_start = interval['t_start'].iloc[0] if len(interval) > 0 and 't_start' in interval.columns else 0.0
        t_duration = interval['t_duration'].iloc[0] if len(interval) > 0 and 't_duration' in interval.columns else 1.0
        t_end = t_start + t_duration
        
        y_offset = interval['series_vertical_offset'].iloc[0] if len(interval) > 0 and 'series_vertical_offset' in interval.columns else 0.0
        y_height = interval['series_height'].iloc[0] if len(interval) > 0 and 'series_height' in interval.columns else self.thumbnail_height
        y_center = y_offset + y_height / 2.0
        y_min = y_center - self.thumbnail_height / 2.0
        y_max = y_center + self.thumbnail_height / 2.0
        
        return (t_start, t_end, y_min, y_max)


# ==================================================================================================================================================================================================================================================================================== #
# VideoTrackDatasource                                                                                                                                                                                                                                                                   #
# ==================================================================================================================================================================================================================================================================================== #

class VideoTrackDatasource(IntervalProvidingTrackDatasource):
    """Example TrackDatasource for video data.
    
    Inherits from IntervalProvidingTrackDatasource and implements video-specific
    detail rendering for displaying video intervals with async detail loading.

    Usage:

        from pypho_timeline.rendering.datasources.specific.video import VideoTrackDatasource
    """
    
    def __init__(self, video_intervals_df: pd.DataFrame, custom_datasource_name: Optional[str]=None):
        """Initialize with video intervals.
        
        Args:
            video_intervals_df: DataFrame with columns ['t_start', 't_duration', 'video_path']
        """
        if custom_datasource_name is None:
            custom_datasource_name = "VideoTrack"
        super().__init__(video_intervals_df, detailed_df=None, custom_datasource_name=custom_datasource_name)

        # Override visualization properties (parent sets blue, we want green; parent sets height=1.0, we want 50.0)
        self.intervals_df['series_height'] = 50.0
        
        # Create pens and brushes with green color
        color = pg.mkColor('green')
        color.setAlphaF(0.3)
        pen = pg.mkPen(color, width=1)
        brush = pg.mkBrush(color)
        self.intervals_df['pen'] = [pen] * len(self.intervals_df)
        self.intervals_df['brush'] = [brush] * len(self.intervals_df)
    
    def fetch_detailed_data(self, interval: pd.Series) -> dict:
        """Fetch video frames for an interval (simulated with random images)."""
        # In a real implementation, this would load video frames
        # For demo, generate synthetic frame data
        n_frames = max(1, int(interval['t_duration'] * 10))  # 10 fps
        frames = []
        for i in range(n_frames):
            # Generate a simple colored frame
            frame = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
            frames.append(frame)
        return {'frames': frames, 'timestamps': np.linspace(interval['t_start'], interval['t_start'] + interval['t_duration'], n_frames)}
    
    def get_detail_renderer(self):
        """Get detail renderer for video."""
        return VideoThumbnailDetailRenderer(thumbnail_height=50.0, spacing=0.1)
    
    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get cache key for interval."""
        return f"video_{interval['t_start']:.3f}_{interval['t_duration']:.3f}"


__all__ = ['VideoThumbnailDetailRenderer', 'VideoTrackDatasource']

