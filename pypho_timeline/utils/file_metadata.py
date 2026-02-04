import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

import pandas as pd
from attrs import define


@define(slots=False)
class BaseFileMetadataParser:
    """
    Base parser for file folders: extracts datetime from filenames, file stat metadata,
    and optional type-specific metadata via overridable extract_file_metadata.
    Supports caching with configurable datetime columns.
    """

    @classmethod
    def extract_datetime_from_filename(cls, filename: str) -> Optional[datetime]:
        """
        Extract datetime from filename.

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
    def get_file_metadata(cls, file_path: Path) -> Dict[str, Any]:
        """
        Extract file size and modification time for cache validation.
        
        Returns:
            Dictionary with file_size and file_mtime.
        """
        try:
            stat = file_path.stat()
            return {
                'file_size': stat.st_size,
                'file_mtime': stat.st_mtime,
            }
        except Exception:
            return {'file_size': 0, 'file_mtime': 0.0}
    

    @classmethod
    def is_file_changed(cls, file_path: Path, cached_row: pd.Series) -> bool:
        """
        Check if a file has been modified since it was cached.

        Args:
            file_path: Path to the file
            cached_row: Cached row from DataFrame with cache_file_size and cache_file_mtime

        Returns:
            True if file was modified or doesn't exist, False otherwise.
        """
        if not file_path.exists():
            return True
        try:
            current_metadata = cls.get_file_metadata(file_path)
            # Cached row columns: cache_file_size, cache_file_mtime (used for cache validation)
            cached_size = cached_row.get('cache_file_size') if 'cache_file_size' in cached_row.index else 0
            cached_mtime = cached_row.get('cache_file_mtime') if 'cache_file_mtime' in cached_row.index else 0.0
            return (current_metadata['file_size'] != cached_size or 
                    abs(current_metadata['file_mtime'] - cached_mtime) > 0.1)  # 0.1 second tolerance
        except Exception:
            return True
    

    @classmethod
    def load_cache(cls, cache_path: Path, datetime_columns: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Load cached file metadata from CSV file.

        Args:
            cache_path: Path to the cache CSV file
            datetime_columns: Optional list of column names to parse as datetime.

        Returns:
            DataFrame with cached metadata, or empty DataFrame if cache doesn't exist or is corrupted.
        """
        if not cache_path.exists():
            return pd.DataFrame()
        try:
            df = pd.read_csv(cache_path)
            # Parse datetime columns (e.g. start_datetime_column, end_datetime_column)
            if datetime_columns:
                for col in datetime_columns:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col])
            return df
        except Exception:
            # Corrupted cache - return empty DataFrame
            return pd.DataFrame()
    

    @classmethod
    def save_cache(cls, df: pd.DataFrame, cache_path: Path) -> None:
        """
        Save file metadata DataFrame to cache CSV file.

        Args:
            df: DataFrame with file metadata to cache (columns depend on subclass, e.g. path_column, start_datetime_column, end_datetime_column, cache_file_size, cache_file_mtime)
            cache_path: Path where cache should be saved
        """
        if df.empty:
            return
        try:
            # Ensure parent directory exists
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            # Save to CSV
            df.to_csv(cache_path, index=False)
        except Exception:
            # Silently fail if we can't save cache
            pass
    
    
    @classmethod
    def extract_file_metadata(cls, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Extract type-specific metadata from a file. Subclasses override to provide
        actual extraction (e.g. video via cv2). Base implementation returns None.

        Returns:
            Dictionary with metadata (must include duration_metadata_key for folder parsing) or None.
        """
        return None
    

    @classmethod
    def parse_filesystem_folder(cls, folder_path: Path, included_file_extensions: List[str], use_cache: bool = True, force_rebuild: bool = False, cache_filename: str = "_metadata_cache.csv", path_column: str = "file_path", start_datetime_column: str = "start_datetime", end_datetime_column: str = "end_datetime", duration_metadata_key: str = "duration") -> pd.DataFrame:
        """
        Parse all files in a folder and return a DataFrame with metadata.
        Uses caching to speed up subsequent runs by only processing new or modified files.

        Args:
            folder_path: Path to folder containing files
            included_file_extensions: List of file extensions to process
            use_cache: If True, use cached metadata for unchanged files (default: True)
            force_rebuild: If True, ignore cache and rebuild from scratch (default: False)
            cache_filename: Name of cache file in folder (default: _metadata_cache.csv)
            path_column: Column name for file path in result (default: file_path)
            start_datetime_column: Column name for start datetime (default: start_datetime)
            end_datetime_column: Column name for end datetime (default: end_datetime)
            duration_metadata_key: Key in extract_file_metadata result for duration in seconds (default: duration)

        Returns:
            DataFrame with path_column, start_datetime_column, end_datetime_column,
            keys from extract_file_metadata, and cache_file_size, cache_file_mtime.
            Sorted by start_datetime_column.
        """
        folder_path = Path(folder_path)
        if not folder_path.exists():
            return pd.DataFrame()
        # Determine cache path (e.g. folder / "_metadata_cache.csv" or "_video_metadata_cache.csv")
        cache_path = folder_path / cache_filename
        # Load existing cache if enabled and not forcing rebuild; parse datetime columns (start_datetime_column, end_datetime_column)
        cached_df = pd.DataFrame()
        if use_cache and not force_rebuild:
            cached_df = cls.load_cache(cache_path, datetime_columns=[start_datetime_column, end_datetime_column])
        # Find all files matching included_file_extensions
        files = []
        for ext in included_file_extensions:
            files.extend(folder_path.glob(f"*{ext}"))
            files.extend(folder_path.glob(f"*{ext.upper()}"))
        if not files:
            # No files found - return empty DataFrame and clear cache if it exists
            if cache_path.exists() and use_cache:
                try:
                    cache_path.unlink()
                except Exception:
                    pass
            return pd.DataFrame()
        # Build dictionary of cached entries by file path (key: path_column value from cache)
        cached_by_path = {}
        if not cached_df.empty and path_column in cached_df.columns:
            for idx, row in cached_df.iterrows():
                file_path_str = row[path_column]
                cached_by_path[file_path_str] = row
        results = []
        for file_path in files:
            resolved_path = str(file_path.resolve())
            use_cached = False
            if use_cache and not force_rebuild and resolved_path in cached_by_path:
                cached_row = cached_by_path[resolved_path]
                if not cls.is_file_changed(file_path, cached_row):
                    # Use cached entry, but update cache metadata (cache_file_size, cache_file_mtime)
                    cached_entry = cached_row.to_dict()
                    current_metadata = cls.get_file_metadata(file_path)
                    cached_entry['cache_file_size'] = current_metadata['file_size']
                    cached_entry['cache_file_mtime'] = current_metadata['file_mtime']
                    results.append(cached_entry)
                    use_cached = True
            if not use_cached:
                # Extract datetime from filename
                start_datetime = cls.extract_datetime_from_filename(file_path.name)
                if start_datetime is None:
                    continue
                # Type-specific metadata (e.g. video_duration, video_fps; must include duration_metadata_key)
                metadata = cls.extract_file_metadata(file_path)
                if metadata is None:
                    continue
                # Get file metadata for cache validation
                file_metadata = cls.get_file_metadata(file_path)
                # Calculate end datetime from start + duration (duration_metadata_key in metadata)
                duration = metadata.get(duration_metadata_key, 0)
                end_datetime = start_datetime + timedelta(seconds=duration)
                # Build result row: path_column, start_datetime_column, end_datetime_column, **metadata, cache_file_size, cache_file_mtime
                result = {path_column: resolved_path, start_datetime_column: start_datetime, end_datetime_column: end_datetime, **metadata, 'cache_file_size': file_metadata['file_size'], 'cache_file_mtime': file_metadata['file_mtime']}
                results.append(result)
        if not results:
            # No valid files found - clear cache if it exists
            if cache_path.exists() and use_cache:
                try:
                    cache_path.unlink()
                except Exception:
                    pass
            return pd.DataFrame()
        # Create DataFrame
        df = pd.DataFrame(results)
        # Sort by start_datetime_column (e.g. video_start_datetime)
        df = df.sort_values(start_datetime_column).reset_index(drop=True)
        # Save updated cache
        if use_cache:
            cls.save_cache(df, cache_path)
        return df


__all__ = ['BaseFileMetadataParser']

