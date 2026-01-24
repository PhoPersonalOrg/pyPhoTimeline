import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Callable, Union, Any
import pyphoplacecellanalysis.External.pyqtgraph as pg
from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, BaseTrackDatasource, IntervalProvidingTrackDatasource, DetailRenderer
from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import GenericPlotDetailRenderer

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from pypho_timeline.utils.video_metadata import VideoMetadataParser


# ==================================================================================================================================================================================================================================================================================== #
# Helper function to convert VideoMetadataParser output to intervals_df format                                                                                                                                                                                                       #
# ==================================================================================================================================================================================================================================================================================== #

def video_metadata_to_intervals_df(video_df: pd.DataFrame, reference_timestamp: Optional[float] = None) -> pd.DataFrame:
    """Convert VideoMetadataParser output to intervals_df format.
    
    Args:
        video_df: DataFrame from VideoMetadataParser.parse_video_folder()
        reference_timestamp: Optional reference timestamp (Unix epoch seconds). 
                           If None, uses first video's start time as t=0.
    
    Returns:
        DataFrame with columns ['t_start', 't_duration', 'video_file_path', ...]
    """
    if video_df.empty:
        return pd.DataFrame()
    
    # Convert datetime to Unix timestamp (float seconds)
    if 'video_start_datetime' not in video_df.columns:
        return pd.DataFrame()
    
    # Convert datetime to timestamp
    timestamps = video_df['video_start_datetime'].values.astype('datetime64[ns]').astype(np.float64) / 1e9
    
    # Calculate t_start relative to reference or first video
    if reference_timestamp is None:
        reference_timestamp = float(timestamps[0])
    
    t_start_values = timestamps - reference_timestamp
    
    # Create intervals_df
    intervals_df = pd.DataFrame({
        't_start': t_start_values,
        't_duration': video_df['video_duration'].values if 'video_duration' in video_df.columns else 0.0,
        'video_file_path': video_df['video_file_path'].values if 'video_file_path' in video_df.columns else '',
    })
    
    # Preserve all other metadata columns
    metadata_cols = [col for col in video_df.columns if col not in ['video_start_datetime', 'video_end_datetime', 'video_duration', 'video_file_path']]
    for col in metadata_cols:
        intervals_df[col] = video_df[col].values
    
    return intervals_df


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
    
    def __init__(self, thumbnail_height: float = 50.0, spacing: float = 0.1, thumbnail_size: Optional[Tuple[int, int]] = None):
        """Initialize the video thumbnail renderer.
        
        Args:
            thumbnail_height: Height of each thumbnail in plot coordinates (default: 50.0)
            spacing: Spacing between thumbnails as fraction of interval duration (default: 0.1)
            thumbnail_size: Optional (width, height) tuple for resizing frames. If None, uses original size.
        """
        self.thumbnail_height = thumbnail_height
        self.spacing = spacing
        self.thumbnail_size = thumbnail_size
    
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
            frame: Frame data as numpy array (BGR from cv2 or RGB)
            
        Returns:
            Image array ready for ImageItem (RGB format), or None if invalid
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
                # Assume BGR from cv2, convert to RGB
                if CV2_AVAILABLE:
                    img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                else:
                    img = frame
            elif frame.shape[2] == 4:
                # RGBA - assume BGRA from cv2, convert to RGBA
                if CV2_AVAILABLE:
                    img = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGBA)
                else:
                    img = frame
            else:
                return None
        else:
            return None
        
        # Resize if thumbnail_size is specified
        if self.thumbnail_size is not None and CV2_AVAILABLE:
            width, height = self.thumbnail_size
            if img.ndim == 3:
                img = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)
            elif img.ndim == 2:
                img = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)
                img = img[:, :, np.newaxis]
        
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
    """TrackDatasource for video data.
    
    Inherits from IntervalProvidingTrackDatasource and implements video-specific
    detail rendering for displaying video intervals with async detail loading.

    Usage:

        from pypho_timeline.rendering.datasources.specific.video import VideoTrackDatasource
        from pathlib import Path
        
        # Option 1: Parse from folder
        video_ds = VideoTrackDatasource(video_folder_path=Path("path/to/videos"))
        
        # Option 2: Use pre-parsed DataFrame
        video_df = VideoMetadataParser.parse_video_folder(Path("path/to/videos"))
        video_ds = VideoTrackDatasource(video_df=video_df)
        
        # Option 3: Use intervals DataFrame directly
        video_ds = VideoTrackDatasource(video_intervals_df=intervals_df)
        
        # Option 4: Use list of video file paths
        video_ds = VideoTrackDatasource(video_paths=[Path("video1.mp4"), Path("video2.mp4")])
    """
    
    def __init__(self, video_intervals_df: Optional[pd.DataFrame] = None, video_folder_path: Optional[Path] = None, video_df: Optional[pd.DataFrame] = None, video_paths: Optional[List[Union[Path, str]]] = None, custom_datasource_name: Optional[str] = None, reference_timestamp: Optional[float] = None, frames_per_second: float = 10.0, thumbnail_size: Optional[Tuple[int, int]] = (128, 128), use_vispy_renderer: bool = False):
        """Initialize with video intervals.
        
        Args:
            video_intervals_df: DataFrame with columns ['t_start', 't_duration', 'video_file_path'] (optional, if provided, other args ignored)
            video_folder_path: Path to folder containing videos (will be parsed using VideoMetadataParser)
            video_df: Pre-parsed DataFrame from VideoMetadataParser.parse_video_folder() (optional)
            video_paths: List of video file paths (Path objects or strings) to parse individually
            custom_datasource_name: Custom name for this datasource (optional)
            reference_timestamp: Optional reference timestamp for time conversion (default: first video start time)
            frames_per_second: Target frame rate for thumbnail extraction (default: 10.0)
            thumbnail_size: Optional (width, height) tuple for resizing frames (default: (128, 128))
            use_vispy_renderer: If True, use high-performance vispy renderer instead of pyqtgraph (default: False)
        """
        # Determine which input method to use
        if video_intervals_df is not None:
            # Direct intervals DataFrame provided
            intervals_df = video_intervals_df.copy()
        elif video_paths is not None:
            # Parse from list of video file paths
            if not CV2_AVAILABLE:
                raise ImportError("opencv-python is required for video parsing. Install with: pip install opencv-python")
            # Parse each video file individually
            results = []
            for video_path in video_paths:
                video_path = Path(video_path)
                if not video_path.exists():
                    continue
                # Extract datetime from filename
                video_start_datetime = VideoMetadataParser.extract_datetime_from_filename(video_path.name)
                if video_start_datetime is None:
                    # If no datetime in filename, use file modification time as fallback
                    try:
                        video_start_datetime = datetime.fromtimestamp(video_path.stat().st_mtime)
                    except Exception:
                        continue
                # Extract video metadata
                metadata = VideoMetadataParser.extract_video_metadata(video_path)
                if metadata is None:
                    continue
                # Get file metadata
                file_metadata = VideoMetadataParser.get_file_metadata(video_path)
                # Calculate end datetime
                video_end_datetime = video_start_datetime + timedelta(seconds=metadata['video_duration'])
                # Build result row
                result = {
                    'video_start_datetime': video_start_datetime,
                    'video_duration': metadata['video_duration'],
                    'video_end_datetime': video_end_datetime,
                    'video_num_frames': metadata['video_num_frames'],
                    'video_fps': metadata['video_fps'],
                    'video_width': metadata['video_width'],
                    'video_height': metadata['video_height'],
                    'video_file_path': str(video_path.resolve()),
                    'video_file_size': metadata['video_file_size'],
                    'cache_file_size': file_metadata['file_size'],
                    'cache_file_mtime': file_metadata['file_mtime'],
                }
                results.append(result)
            if not results:
                intervals_df = pd.DataFrame()
            else:
                # Create DataFrame and convert to intervals_df format
                video_df_parsed = pd.DataFrame(results)
                video_df_parsed = video_df_parsed.sort_values('video_start_datetime').reset_index(drop=True)
                intervals_df = video_metadata_to_intervals_df(video_df_parsed, reference_timestamp=reference_timestamp)
        elif video_folder_path is not None:
            # Parse from folder
            if not CV2_AVAILABLE:
                raise ImportError("opencv-python is required for video parsing. Install with: pip install opencv-python")
            video_df_parsed = VideoMetadataParser.parse_video_folder(video_folder_path)
            if video_df_parsed.empty:
                intervals_df = pd.DataFrame()
            else:
                intervals_df = video_metadata_to_intervals_df(video_df_parsed, reference_timestamp=reference_timestamp)
        elif video_df is not None:
            # Use pre-parsed DataFrame
            intervals_df = video_metadata_to_intervals_df(video_df, reference_timestamp=reference_timestamp)
        else:
            raise ValueError("Must provide one of: video_intervals_df, video_folder_path, video_df, or video_paths")
        
        if custom_datasource_name is None:
            custom_datasource_name = "VideoTrack"
        super().__init__(intervals_df, detailed_df=None, custom_datasource_name=custom_datasource_name)

        # Override visualization properties (parent sets blue, we want blue; parent sets height=1.0, we want 50.0)
        self.intervals_df['series_height'] = 50.0
        
        # Create pens and brushes with blue color (matching PhoOfflineEEGAnalysis)
        color = pg.mkColor(100, 150, 200, 255)
        color.setAlphaF(0.588)  # 150/255 ≈ 0.588
        pen = pg.mkPen(color, width=1)
        brush = pg.mkBrush(color)
        self.intervals_df['pen'] = [pen] * len(self.intervals_df)
        self.intervals_df['brush'] = [brush] * len(self.intervals_df)
        
        # Add label column with filename extracted from video_file_path
        if 'video_file_path' in self.intervals_df.columns:
            self.intervals_df['label'] = self.intervals_df['video_file_path'].apply(lambda path: Path(path).name if path else '')
        else:
            self.intervals_df['label'] = ''
        
        # Store configuration for frame loading
        self.frames_per_second = frames_per_second
        self.thumbnail_size = thumbnail_size
        
        # Store vispy renderer flag
        self.use_vispy_renderer = use_vispy_renderer
    
    def fetch_detailed_data(self, interval: pd.Series) -> dict:
        """Fetch video frames for an interval using cv2.VideoCapture.
        
        Args:
            interval: Series with at least 't_start', 't_duration', and 'video_file_path'
            
        Returns:
            Dictionary with 'frames' (list of numpy arrays) and 'timestamps' (array)
        """
        if not CV2_AVAILABLE:
            # Fallback to synthetic frames if cv2 not available
            n_frames = max(1, int(interval['t_duration'] * self.frames_per_second))
            frames = []
            for i in range(n_frames):
                frame = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
                frames.append(frame)
            return {'frames': frames, 'timestamps': np.linspace(interval['t_start'], interval['t_start'] + interval['t_duration'], n_frames)}
        
        # Get video file path
        video_file_path = interval.get('video_file_path', '')
        if not video_file_path:
            return {'frames': [], 'timestamps': np.array([])}
        
        video_path = Path(video_file_path)
        if not video_path.exists():
            return {'frames': [], 'timestamps': np.array([])}
        
        try:
            # Open video
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                return {'frames': [], 'timestamps': np.array([])}
            
            # Get video properties
            video_fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if video_fps <= 0 or total_frames == 0:
                cap.release()
                return {'frames': [], 'timestamps': np.array([])}
            
            # Calculate frame extraction parameters
            interval_start = interval['t_start']
            interval_duration = interval['t_duration']
            target_n_frames = max(1, int(interval_duration * self.frames_per_second))
            
            # Calculate frame indices to extract
            frame_indices = np.linspace(0, total_frames - 1, target_n_frames, dtype=int)
            
            # Extract frames
            frames = []
            timestamps = []
            
            for frame_idx in frame_indices:
                # Seek to frame
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                
                if ret and frame is not None:
                    # Resize if thumbnail_size is specified
                    if self.thumbnail_size is not None:
                        width, height = self.thumbnail_size
                        frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
                    
                    frames.append(frame)
                    # Calculate timestamp relative to interval start
                    frame_time_in_video = frame_idx / video_fps
                    timestamps.append(interval_start + frame_time_in_video)
            
            cap.release()
            
            return {'frames': frames, 'timestamps': np.array(timestamps)}
            
        except Exception as e:
            # Return empty frames on error
            return {'frames': [], 'timestamps': np.array([])}
    
    def get_detail_renderer(self):
        """Get detail renderer for video."""
        return VideoThumbnailDetailRenderer(thumbnail_height=50.0, spacing=0.1, thumbnail_size=self.thumbnail_size)
    
    def get_detail_cache_key(self, interval: pd.Series) -> str:
        """Get cache key for interval."""
        base_key = super().get_detail_cache_key(interval)
        video_path = interval.get('video_file_path', '')
        if video_path:
            # Include file path and modification time in cache key for better cache invalidation
            try:
                path_obj = Path(video_path)
                if path_obj.exists():
                    mtime = path_obj.stat().st_mtime
                    return f"video_{video_path}_{mtime:.3f}_{base_key}"
            except Exception:
                pass
        return f"video_{base_key}"


__all__ = ['VideoThumbnailDetailRenderer', 'VideoTrackDatasource', 'video_metadata_to_intervals_df']
