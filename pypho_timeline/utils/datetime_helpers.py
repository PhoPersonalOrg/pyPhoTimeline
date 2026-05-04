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
# from phopylslhelper.datetime_helpers import float_to_datetime, datetime_to_unix_timestamp, to_display_timezone, _to_utc_datetime, UNIX_EPOCH_UTC, DISPLAY_TIMEZONE
from phopylslhelper.datetime_helpers import *

logger = logging.getLogger(__name__)

# Unix epoch in UTC (timezone-aware)
UNIX_EPOCH_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)
DISPLAY_TIMEZONE = ZoneInfo("America/Detroit")


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



