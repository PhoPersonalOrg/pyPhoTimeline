"""Helper functions for datetime conversion and XDF header parsing.

This module provides utilities for converting between float timestamps and datetime objects,
and extracting reference datetimes from XDF file headers.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any, Union
import logging
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

UNIX_EPOCH_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)
DISPLAY_TIMEZONE = ZoneInfo("America/New_York")


def _to_utc_datetime(dt: datetime) -> datetime:
    """Return a timezone-aware UTC datetime."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_display_timezone(dt: datetime) -> datetime:
    """Convert a datetime to the configured display timezone."""
    return _to_utc_datetime(dt).astimezone(DISPLAY_TIMEZONE)


def datetime_to_unix_timestamp(dt: datetime) -> float:
    """Convert a datetime to a Unix timestamp."""
    return _to_utc_datetime(dt).timestamp()


def unix_timestamp_to_datetime(timestamp: Union[int, float]) -> datetime:
    """Convert a Unix timestamp to a UTC datetime."""
    return datetime.fromtimestamp(float(timestamp), tz=timezone.utc)


def float_to_datetime(t: Union[int, float], reference_datetime: datetime) -> datetime:
    """Convert elapsed seconds from a reference datetime to a datetime."""
    return _to_utc_datetime(reference_datetime) + timedelta(seconds=float(t))


def datetime_to_float(dt: datetime, reference_datetime: datetime) -> float:
    """Convert a datetime to elapsed seconds from a reference datetime."""
    return (_to_utc_datetime(dt) - _to_utc_datetime(reference_datetime)).total_seconds()

logger = logging.getLogger(__name__)

def create_am_pm_date_axis(orientation='bottom'):
    """Create a DateAxisItem with 12-hour AM/PM time format.
    
    Args:
        orientation: Axis orientation ('bottom', 'top', 'left', 'right')
        
    Returns:
        Custom DateAxisItem instance with AM/PM formatting, or None if DateAxisItem is not available
    """
    try:
        import pypho_timeline.EXTERNAL.pyqtgraph as pg
        from pyqtgraph import DateAxisItem

        class AMPMDateAxisItem(DateAxisItem):
            """Custom DateAxisItem that displays time in 12-hour AM/PM format."""
            
            def tickStrings(self, values, scale, spacing):
                """Override to format tick labels in 12-hour AM/PM format."""
                # Convert timestamps to datetime objects
                dt_values = [to_display_timezone(datetime.fromtimestamp(value, tz=timezone.utc)) for value in values]
                # Format datetime objects to 12-hour format with AM/PM
                # Use format like "01/09 02:33 PM" for date and time
                return [dt.strftime('%m/%d %I:%M %p') for dt in dt_values]
        
        return AMPMDateAxisItem(orientation=orientation)
    except (ImportError, AttributeError):
        # Fallback: try to get DateAxisItem directly from pg module
        try:
            import pypho_timeline.EXTERNAL.pyqtgraph as pg
            if hasattr(pg, "DateAxisItem"):
                class AMPMDateAxisItem(pg.DateAxisItem):
                    def tickStrings(self, values, scale, spacing):
                        dt_values = [to_display_timezone(datetime.fromtimestamp(value, tz=timezone.utc)) for value in values]
                        return [dt.strftime('%m/%d %I:%M %p') for dt in dt_values]
                return AMPMDateAxisItem(orientation=orientation)
        except:
            pass
        # If all else fails, return None
        return None

def get_reference_datetime_from_xdf_header(file_header: dict) -> Optional[datetime]:
    """Extract reference datetime from XDF file header.
    
    Args:
        file_header: XDF file header dictionary from pyxdf.load_xdf()
        
    Returns:
        datetime object if found, None otherwise
        
    The function checks multiple possible locations in the XDF header:
    - file_header['info']['recording']['start_time']
    - file_header['info']['recording']['start_time_s']
    - file_header['first_timestamp']
    - Other common locations
    """
    from phopymnehelper.xdf_files import LabRecorderXDF
    return LabRecorderXDF.get_reference_datetime_from_xdf_header(file_header=file_header)


def get_earliest_reference_datetime(reference_datetimes: List[Optional[datetime]]) -> Optional[datetime]:
    """Return the earliest non-empty reference datetime."""
    valid_datetimes = [_to_utc_datetime(dt) for dt in reference_datetimes if dt is not None]
    if not valid_datetimes:
        return None
    return min(valid_datetimes)



