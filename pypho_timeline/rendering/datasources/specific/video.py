import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Callable, Union, Any
from qtpy import QtCore
import pyqtgraph as pg
from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, BaseTrackDatasource, IntervalProvidingTrackDatasource, DetailRenderer
from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import GenericPlotDetailRenderer

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from phopylslhelper.file_metadata_caching.video_metadata import VideoMetadataParser
from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp
        
from pypho_timeline.utils.logging_util import get_rendering_logger
logger = get_rendering_logger(__name__)


from deffcode import Sourcer ## for metadata extraction
from deffcode import FFdecoder
import imageio


class VideoDeffcodeHelpers:
    """ 
    from pypho_timeline.rendering.datasources.specific.video import VideoDeffcodeHelpers

    """
    included_primary_metadata_fields = ['source_video_framerate', 'source_duration_sec', 'approx_video_nframes']
    included_secondary_metadata_fields = ['source_extension', 'source_video_resolution', 'source_video_pixfmt', 'source_video_orientation', 'source_video_decoder']
    advanced_metadata_fields = ['source_video_bitrate', 'source_audio_bitrate', 'source_audio_samplerate', 'source_has_video', 'source_has_audio', 'source_has_image_sequence']

    @classmethod
    def fetch_video_metadata_for_cache(cls, a_video_file: Union[str, Path], debug_log_metadata: bool=False) -> Optional[Tuple[Dict, Dict]]:
        """
            vid_metadata, sourcer = VideoDeffcodeHelpers.fetch_video_metadata_for_cache(a_video_file=a_video_file, debug_log_metadata=False)

        """
        if isinstance(a_video_file, str):
            a_video_file = Path(a_video_file)

        video_file_str_path: str = a_video_file.as_posix()

        # initialize and formulate the decoder using suitable source
        sourcer = Sourcer(video_file_str_path).probe_stream()
        vid_metadata = sourcer.retrieve_metadata()

        if debug_log_metadata:
            # print metadata as `json.dump`
            logger.info(vid_metadata)
            # print(sourcer.retrieve_metadata(pretty_json=True))

        primary_vid_metadata = {k:v for k, v in vid_metadata.items() if k in cls.included_primary_metadata_fields}
        # secondary_vid_metadata =  {k:v for k, v in vid_metadata.items() if k in cls.included_primary_metadata_fields}
        return primary_vid_metadata, vid_metadata


    @classmethod
    def fetch_video_thumbnails_for_cache(cls, a_video_file: Union[str, Path], frame_offsets: List[float], save_output_thumbnail: bool=False):
        """
            frame_offsets = []
            frames_list = VideoDeffcodeHelpers.fetch_video_thumbnails_for_cache(a_video_file=a_video_file, frame_offsets=frame_offsets, save_output_thumbnail=False)

        """
        if isinstance(a_video_file, str):
            a_video_file = Path(a_video_file)

        video_file_str_path: str = a_video_file.as_posix()
        frames_list = []

        for i, a_frame_offset in enumerate(frame_offsets):
            a_frame_offset_string: str = str(float(a_frame_offset))
            # define the FFmpeg parameter to jump to 00:00:01.45(or 1s and 45msec)
            # in time in the video before it starts reading it and get one single frame
            a_ffparams = {"-ffprefixes": ["-ss", a_frame_offset_string], "-frames:v": 1}

            # initialize and formulate the decoder with suitable source
            a_decoder = FFdecoder(video_file_str_path, **a_ffparams).formulate()

            # grab the RGB24(default) frame from the decoder
            frame = next(a_decoder.generateFrame(), None)
            frames_list.append(frame)

            # check if frame is None
            if not(frame is None):                
                # Save our output
                if save_output_thumbnail:
                    thumbnail_path = a_video_file.with_suffix(f'_{a_frame_offset_string}_thumb.png')
                    imageio.imwrite(thumbnail_path, frame)
            else:
                raise ValueError(f"Something is wrong for frame: {a_frame_offset_string} with file {a_decoder}, a_ffparams: {a_ffparams}!")

            # terminate the decoder
            a_decoder.terminate()
        ## END for i, a_frame_offset in enumerate(frame_offsets)...

        return frames_list




    @classmethod
    def fetch_video_metadata_and_thumbnail_for_cache(cls, a_video_file: Union[str, Path], needs_metadata: bool = False, save_output_thumbnail: bool=False):
        """
            frame = VideoDeffcodeHelpers.fetch_video_metadata_and_thumbnail_for_cache(a_video_file=a_video_file, save_output_thumbnail=False)

        """
        if isinstance(a_video_file, str):
            a_video_file = Path(a_video_file)

        video_file_str_path: str = a_video_file.as_posix()

        if needs_metadata:
            # initialize and formulate the decoder using suitable source
            sourcer = Sourcer(video_file_str_path).probe_stream()

            # print metadata as `json.dump`
            logger.info(sourcer.retrieve_metadata(pretty_json=True))
            # print(sourcer.retrieve_metadata(pretty_json=True))

        # define the FFmpeg parameter to jump to 00:00:01.45(or 1s and 45msec)
        # in time in the video before it starts reading it and get one single frame
        ffparams = {"-ffprefixes": ["-ss", "00:00:01.45"], "-frames:v": 1}

        # initialize and formulate the decoder with suitable source
        decoder = FFdecoder(video_file_str_path, **ffparams).formulate()

        # grab the RGB24(default) frame from the decoder
        frame = next(decoder.generateFrame(), None)

        # check if frame is None
        if not(frame is None):
            # Save our output
            if save_output_thumbnail:
                thumbnail_path = a_video_file.with_suffix(f'_thumb.png')
                imageio.imwrite(thumbnail_path, frame)
        else:
            raise ValueError("Something is wrong!")

        # terminate the decoder
        decoder.terminate()
        return frame

# ==================================================================================================================================================================================================================================================================================== #
# Helper function to convert VideoMetadataParser output to intervals_df format                                                                                                                                                                                                       #
# ==================================================================================================================================================================================================================================================================================== #

def video_metadata_to_intervals_df(video_df: pd.DataFrame, reference_timestamp: Optional[float] = None, use_absolute_datetime_track_mode: bool = True) -> pd.DataFrame:
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
    

    if (not use_absolute_datetime_track_mode):
        # Convert datetime to timestamp
        timestamps = video_df['video_start_datetime'].values.astype('datetime64[ns]').astype(np.float64) / 1e9
        # # Calculate t_start relative to reference or first video
        if reference_timestamp is None:
            reference_timestamp = float(timestamps[0])    
        t_start_values = timestamps - reference_timestamp

    else:
        ## absolute mode - matching the other tracks that use absolute datetimes
        if (reference_timestamp is not None):
            print(f'WARN: reference_timestamp is not None (reference_timestamp: {reference_timestamp}) but will be ignored because we are using absolute datetimes like the other tracks.')
        # t_start_values = video_df['video_start_datetime'].values ## matching the other tracks that use absolute datetimes
        starts = video_df['video_start_datetime']
        t_start_values = pd.to_datetime(starts).apply(lambda dt: dt.tz_localize('UTC') if dt.tzinfo is None else dt).values

    ## OUTPUTS: t_start_values

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
        debug(f"VideoThumbnailDetailRenderer.render_detail(plot_item: {plot_item}, interval: {interval}, detail_data: {detail_data})")
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
            img_item.setRect(QtCore.QRectF(
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
        
        # Convert t_start and t_end to Unix timestamps if they're datetime objects
        if isinstance(t_start, (datetime, pd.Timestamp)):
            t_start = datetime_to_unix_timestamp(t_start)
        if isinstance(t_end, (datetime, pd.Timestamp)):
            t_end = datetime_to_unix_timestamp(t_end)

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
    @property
    def video_metadata_df(self) -> pd.DataFrame:
        """The video_metadata_df property."""
        return self.df.drop(columns=['pen', 'brush', 'series_vertical_offset', 'series_height'], inplace=False).copy()

    # @video_metadata_df.setter
    # def video_metadata_df(self, value):
    #     self._video_metadata_df = value
    
    def __init__(self, video_intervals_df: Optional[pd.DataFrame] = None, video_folder_path: Optional[Path] = None, video_df: Optional[pd.DataFrame] = None, video_paths: Optional[List[Union[Path, str]]] = None, 
            custom_datasource_name: Optional[str] = None, reference_timestamp: Optional[float] = None, frames_per_second: float = 10.0, thumbnail_size: Optional[Tuple[int, int]] = (128, 128), use_vispy_renderer: bool = False):
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

        self.video_folder_path = video_folder_path
        
        # Override visualization properties (parent sets blue, we want blue; parent sets height=1.0, we want 50.0)
        self.intervals_df['series_height'] = 50.0
        
        # Create pens and brushes with blue color (matching PhoOfflineEEGAnalysis)
        color = pg.mkColor(100, 150, 200, 255)
        color.setAlphaF(0.78)  # 150/255 ≈ 0.588
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

    @classmethod
    def init_from_saved_metadata_csv(cls, parsed_video_out_file_path: Path, custom_datasource_name: Optional[str] = None, frames_per_second: float = 10.0, thumbnail_size: Optional[Tuple[int, int]] = (128, 128), use_vispy_renderer: bool = False) -> "VideoTrackDatasource":
        """ Initialize from the exported video metadata .csv saved previously via `parsed_video_out_file_path = video_track_datasource.save_metadata_csv()`.

        Usage:
            from pypho_timeline.rendering.datasources.specific.video import VideoTrackDatasource
            # After saving: 

            parsed_video_out_parent_path = Path('C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoOfflineEEGAnalysis/output')
            parsed_video_out_file_path: Path = video_ds.save_metadata_csv(parsed_video_out_parent_path=parsed_video_out_parent_path)

            video_ds: VideoTrackDatasource = VideoTrackDatasource.init_from_saved_metadata_csv(parsed_video_out_file_path=parsed_video_out_file_path)

        """
        parsed_video_out_file_path = Path(parsed_video_out_file_path)
        if not parsed_video_out_file_path.exists():
            raise FileNotFoundError(f"Metadata CSV not found: {parsed_video_out_file_path}")
        df = pd.read_csv(parsed_video_out_file_path)
        if df.empty:
            return cls(video_intervals_df=pd.DataFrame(), custom_datasource_name=custom_datasource_name or "VideoTrack", frames_per_second=frames_per_second, thumbnail_size=thumbnail_size, use_vispy_renderer=use_vispy_renderer)
        if 't_start' in df.columns:
            t_start = df['t_start']
            if pd.api.types.is_string_dtype(t_start) or (t_start.dtype == object and t_start.iloc[0] is not None and isinstance(t_start.iloc[0], str)):
                df['t_start'] = pd.to_datetime(t_start, utc=True)
            else:
                df['t_start'] = pd.to_numeric(t_start, errors='coerce')
        if 't_duration' in df.columns:
            df['t_duration'] = pd.to_numeric(df['t_duration'], errors='coerce')
        if 'video_file_path' in df.columns:
            df['video_file_path'] = df['video_file_path'].astype(str)
        return cls(video_intervals_df=df, custom_datasource_name=custom_datasource_name, frames_per_second=frames_per_second, thumbnail_size=thumbnail_size, use_vispy_renderer=use_vispy_renderer)


    def fetch_detailed_data(self, interval: pd.Series) -> dict:
        """Fetch video frames for an interval using cv2.VideoCapture.
        
        Args:
            interval: Series with at least 't_start', 't_duration', and 'video_file_path'
            
        Returns:
            Dictionary with 'frames' (list of numpy arrays) and 'timestamps' (array)
        """
        use_VideoDeffcode: bool = True
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
        

        # Calculate frame extraction parameters
        interval_start = interval['t_start']
        interval_duration = interval['t_duration']
        target_n_frames: int = max(1, int(interval_duration * self.frames_per_second))

        # Extract frames
        frames = []
        timestamps = []

        try:
            if use_VideoDeffcode:
                info(f'USING VideoDeffcode:')
                primary_vid_metadata, vid_metadata = VideoDeffcodeHelpers.fetch_video_metadata_for_cache(a_video_file=video_path, debug_log_metadata=False)
                source_duration_sec: float = primary_vid_metadata['source_duration_sec']
                info(f'\tsource_duration_sec: {source_duration_sec}')
                source_step_sec: float = (float(target_n_frames) / source_duration_sec)
                info(f'\tsource_step_sec: {source_step_sec}')
                # frame = VideoDeffcodeHelpers.fetch_video_metadata_and_thumbnail_for_cache(a_video_file=video_path, needs_metadata=False, save_output_thumbnail=False)
                frame_offsets_sec = np.arange(start=0.0, stop=source_duration_sec, step=source_step_sec)
                info(f'frame_offsets: {frame_offsets_sec}')
                frames = VideoDeffcodeHelpers.fetch_video_thumbnails_for_cache(a_video_file=video_path, frame_offsets=frame_offsets_sec, save_output_thumbnail=False)
                # Calculate timestamp relative to interval start
                # frame_time_in_video = frame_idx / video_fps
                timestamps.append(interval_start + frame_offsets_sec)

                return {'frames': frames, 'timestamps': np.array(timestamps)}


            else:
                ## USING CV2:
                info(f'USING CV2:')
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

                # Calculate frame indices to extract
                frame_indices = np.linspace(0, (total_frames - 1), target_n_frames, dtype=int)
                            
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
                ## END for frame_idx in frame_indices
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
                    return f"video_{video_path}_{mtime}_{base_key}"
            except Exception:
                pass
        return f"video_{base_key}"


    def save_metadata_csv(self, parsed_video_out_parent_path: Optional[Path]=None, parsed_video_out_file_path: Optional[Path]=None) -> Path:
        """ saves the video metadata out to a .csv file """
        video_metadata_df: pd.DataFrame = self.video_metadata_df.copy() # self.df.copy().drop(columns=['pen', 'brush', 'series_vertical_offset', 'series_height'], inplace=False)
        video_metadata_df

        if parsed_video_out_file_path is None:
            # parsed_video_out_path: Path = Path(r'C:\Users\pho\repos\ACTIVE_DEV\PhoOfflineEEGAnalysis\output').resolve()
            # parsed_video_out_path: Path = Path(r'C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoOfflineEEGAnalysis/output').resolve()
            if parsed_video_out_parent_path is None:
                if self.video_folder_path is not None:
                    parsed_video_out_parent_path = self.video_folder_path
                    if isinstance(parsed_video_out_parent_path, str):
                        parsed_video_out_path = Path(parsed_video_out_parent_path)
                else:
                    parsed_video_out_parent_path = Path('output').resolve()

            # parsed_video_out_path: Path = Path(r'C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoOfflineEEGAnalysis/output').resolve()

            assert parsed_video_out_parent_path.exists(), f"parsed_video_out_parent_path: '{parsed_video_out_parent_path}' does not exist."
            assert parsed_video_out_parent_path.is_dir(), f"parsed_video_out_parent_path: '{parsed_video_out_parent_path}' is not a dir."
            
            today_str: str = datetime.now().strftime("%Y-%m-%d")
            parsed_video_out_file_path = parsed_video_out_parent_path.joinpath(f'{today_str}_parsed_videos.csv')

        assert parsed_video_out_file_path is not None

        print(f'writing video metadata csv out to "{parsed_video_out_file_path}"...')
        video_metadata_df.to_csv(parsed_video_out_file_path)
        print(f'\tdone.')
        return parsed_video_out_file_path


__all__ = ['VideoThumbnailDetailRenderer', 'VideoTrackDatasource', 'video_metadata_to_intervals_df']
