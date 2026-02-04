import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

import cv2
import pandas as pd
from attrs import define
from pypho_timeline.utils.file_metadata import BaseFileMetadataParser


@define(slots=False)
class VideoMetadataParser(BaseFileMetadataParser):
    """
    Parses video folders and extracts metadata including datetime from filenames.

    Usage:
        from pypho_timeline.utils.video_metadata import VideoMetadataParser

        folder_path = Path(r"M:\\ScreenRecordings\\EyeTrackerVR_Recordings")
        df = VideoMetadataParser.parse_video_folder(folder_path)
        print(df)
    """
    
    @classmethod
    def extract_datetime_from_filename(cls, filename: str) -> Optional[datetime]:
        """
        Extract datetime from video filename.
        
        Examples:
            'Debut_2025-07-03T230155.mp4' -> datetime(2025, 7, 3, 23, 1, 55)
            'Video_2025-12-25T120000.avi' -> datetime(2025, 12, 25, 12, 0, 0)
        """
        # Pattern to match: Debut_2025-07-03T230155 or similar
        candidates = re.findall(r'\d{4}[-_]?\d{2}[-_]?\d{2}[ T_-]?\d{2}[:\-]?\d{2}[:\-]?\d{2}', filename)
        for cand in candidates:
            normalized = cand.replace("_", "T").replace(" ", "T")
            for fmt in [
                "%Y-%m-%dT%H-%M-%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H%M%S",
                "%Y%m%dT%H%M%S",
                "%Y%m%d_%H%M%S",
                "%Y%m%d-%H%M%S",
                "%Y%m%d%H%M%S"
            ]:
                try:
                    return datetime.strptime(normalized, fmt)
                except ValueError:
                    continue
        return None
    
    
    @classmethod
    def get_file_metadata(cls, video_path: Path) -> Dict[str, Any]:
        """
        Extract file size and modification time for cache validation.

        Returns:
            Dictionary with file_size and file_mtime.
        """
        return super().get_file_metadata(video_path)


    @classmethod
    def is_video_changed(cls, video_path: Path, cached_row: pd.Series) -> bool:
        """
        Check if a video file has been modified since it was cached.

        Args:
            video_path: Path to the video file
            cached_row: Cached row from DataFrame with cache_file_size and cache_file_mtime

        Returns:
            True if file was modified or doesn't exist, False otherwise.
        """
        return super().is_file_changed(video_path, cached_row)


    @classmethod
    def load_cache(cls, cache_path: Path) -> pd.DataFrame:
        """
        Load cached video metadata from CSV file.

        Args:
            cache_path: Path to the cache CSV file
            
        Returns:
            DataFrame with cached metadata, or empty DataFrame if cache doesn't exist or is corrupted.
        """
        return super().load_cache(cache_path, datetime_columns=['video_start_datetime', 'video_end_datetime'])


    @classmethod
    def extract_video_metadata(cls, video_path: Path) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from a video file using cv2.VideoCapture.

        Returns:
            Dictionary with video metadata or None if extraction fails.
        """
        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                return None
            num_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = num_frames / fps if fps > 0 else 0.0
            file_size = video_path.stat().st_size
            cap.release()
            return {'video_num_frames': num_frames, 'video_fps': fps, 'video_width': width, 'video_height': height, 'video_duration': duration, 'video_file_size': file_size}
        except Exception:
            return None


    @classmethod
    def extract_file_metadata(cls, file_path: Path) -> Optional[Dict[str, Any]]:
        """Delegate to extract_video_metadata so base parse_filesystem_folder can use it."""
        return cls.extract_video_metadata(file_path)


    @classmethod
    def parse_video_folder(cls, folder_path: Path, video_extensions: List[str] = ['.mp4', '.avi', '.mov', '.mkv', '.wmv'], use_cache: bool = True, force_rebuild: bool = False) -> pd.DataFrame:
        """
        Parse all videos in a folder and return a DataFrame with metadata.
        Uses caching to speed up subsequent runs by only processing new or modified videos.

        Args:
            folder_path: Path to folder containing videos
            video_extensions: List of video file extensions to process
            use_cache: If True, use cached metadata for unchanged videos (default: True)
            force_rebuild: If True, ignore cache and rebuild from scratch (default: False)

        Returns:
            DataFrame with columns:
            - video_start_datetime: Parsed datetime from filename
            - video_duration: Duration in seconds
            - video_end_datetime: Calculated end datetime
            - video_num_frames: Total number of frames
            - video_fps: Frames per second
            - video_width: Video width in pixels
            - video_height: Video height in pixels
            - video_file_path: Full path to video file
            - video_file_size: File size in bytes
            - cache_file_size: File size used for cache validation
            - cache_file_mtime: File modification time used for cache validation

        DataFrame is sorted by video_start_datetime.
        """
        return cls.parse_filesystem_folder(folder_path, included_file_extensions=video_extensions, use_cache=use_cache, force_rebuild=force_rebuild, cache_filename="_video_metadata_cache.csv", path_column="video_file_path", start_datetime_column="video_start_datetime", end_datetime_column="video_end_datetime", duration_metadata_key="video_duration")


__all__ = ['VideoMetadataParser']
