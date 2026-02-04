"""Helper functions for datetime conversion and XDF header parsing.

This module provides utilities for converting between float timestamps and datetime objects,
and extracting reference datetimes from XDF file headers.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple, Dict, Any
import logging
import pandas as pd

logger = logging.getLogger(__name__)

# Unix epoch in UTC (timezone-aware)
UNIX_EPOCH_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)


def create_am_pm_date_axis(orientation='bottom'):
    """Create a DateAxisItem with 12-hour AM/PM time format.
    
    Args:
        orientation: Axis orientation ('bottom', 'top', 'left', 'right')
        
    Returns:
        Custom DateAxisItem instance with AM/PM formatting, or None if DateAxisItem is not available
    """
    try:
        import pyphoplacecellanalysis.External.pyqtgraph as pg
        from pyphoplacecellanalysis.External.pyqtgraph import DateAxisItem
        
        class AMPMDateAxisItem(DateAxisItem):
            """Custom DateAxisItem that displays time in 12-hour AM/PM format."""
            
            def tickStrings(self, values, scale, spacing):
                """Override to format tick labels in 12-hour AM/PM format."""
                # Convert timestamps to datetime objects
                dt_values = [datetime.fromtimestamp(value, tz=timezone.utc) for value in values]
                # Format datetime objects to 12-hour format with AM/PM
                # Use format like "01/09 02:33 PM" for date and time
                return [dt.strftime('%m/%d %I:%M %p') for dt in dt_values]
        
        return AMPMDateAxisItem(orientation=orientation)
    except (ImportError, AttributeError):
        # Fallback: try to get DateAxisItem directly from pg module
        try:
            import pyphoplacecellanalysis.External.pyqtgraph as pg
            if hasattr(pg, 'DateAxisItem'):
                class AMPMDateAxisItem(pg.DateAxisItem):
                    def tickStrings(self, values, scale, spacing):
                        dt_values = [datetime.fromtimestamp(value, tz=timezone.utc) for value in values]
                        return [dt.strftime('%m/%d %I:%M %p') for dt in dt_values]
                return AMPMDateAxisItem(orientation=orientation)
        except:
            pass
        # If all else fails, return None
        return None


def determine_timelike_value_format(value):
    """ Unfinished 
    #TODO 2026-02-04 02:47: - [ ] broken out of `get_reference_datetime_from_xdf_header` for reuse.
    """


    # Check the format of start_t (is it datetime, Unix timestamp, or relative seconds)?
    start_t_type = type(start_t)
    is_datetime = False
    is_unix_timestamp = False
    is_relative_seconds = False

    if isinstance(start_t, (pd.Timestamp, datetime)):
        is_datetime = True
    elif isinstance(start_t, (float, int)):
        # Heuristic: treat as Unix timestamp if > 10^9, otherwise relative seconds
        # (This threshold is approximately 2001-09-09 in seconds since epoch)
        if start_t > 1e9:
            is_unix_timestamp = True
        else:
            is_relative_seconds = True
    else:
        # Unknown format; handle accordingly or log warning if desired
        pass
    
    #TODO 2026-02-04 03:24: - [ ] Seperate implementation, more complete but with no heuristic and forcibly assumes timestamp format

    # Try to parse as datetime
    if isinstance(value, (int, float)):
        # Unix timestamp (seconds since epoch)
        try:
            dt = datetime.fromtimestamp(value, tz=timezone.utc)
            return dt
        except (ValueError, OSError):
            # Try as milliseconds if seconds fails
            try:
                dt = datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
                return dt
            except (ValueError, OSError):
                logger.warning(f"Could not parse timestamp value {value} as Unix timestamp")
                return None
    elif isinstance(value, str):
        # Try ISO format or other string formats
        try:
            # Try ISO format first
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            # Make timezone-aware if naive
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            # Try other common formats
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f']:
                try:
                    dt = datetime.strptime(value, fmt)
                    # Make timezone-aware (assume UTC)
                    dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except ValueError:
                    continue
            logger.warning(f"Could not parse datetime string: {value}")
            return None

    elif isinstance(value, datetime):
        # Make timezone-aware if naive
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    else:
        raise NotImplementedError(f'unexpected type for value: {type(value)}, value: {value}')

        


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
    if file_header is None:
        return None
    
    # Try various possible locations for recording start time
    possible_paths = [
        ['info', 'recording', 'start_time'],
        ['info', 'recording', 'start_time_s'],
        ['info', 'recording', 'startTime'],
        ['first_timestamp'],
        ['info', 'first_timestamp'],
        ['recording', 'start_time'],
    ]
    
    for path in possible_paths:
        try:
            value = file_header
            for key in path:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                    # XDF headers often have values as lists with single element
                    if isinstance(value, list) and len(value) > 0:
                        value = value[0]
                else:
                    value = None
                    break
            
            if value is not None:
                # Try to parse as datetime
                if isinstance(value, (int, float)):
                    # Unix timestamp (seconds since epoch)
                    try:
                        dt = datetime.fromtimestamp(value, tz=timezone.utc)
                        return dt
                    except (ValueError, OSError):
                        # Try as milliseconds if seconds fails
                        try:
                            dt = datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
                            return dt
                        except (ValueError, OSError):
                            logger.warning(f"Could not parse timestamp value {value} as Unix timestamp")
                            continue
                elif isinstance(value, str):
                    # Try ISO format or other string formats
                    try:
                        # Try ISO format first
                        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        # Make timezone-aware if naive
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        return dt
                    except ValueError:
                        # Try other common formats
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f']:
                            try:
                                dt = datetime.strptime(value, fmt)
                                # Make timezone-aware (assume UTC)
                                dt = dt.replace(tzinfo=timezone.utc)
                                return dt
                            except ValueError:
                                continue
                        logger.warning(f"Could not parse datetime string: {value}")
                        continue
                elif isinstance(value, datetime):
                    # Make timezone-aware if naive
                    if value.tzinfo is None:
                        value = value.replace(tzinfo=timezone.utc)
                    return value
        except (KeyError, TypeError, AttributeError) as e:
            continue
    
    logger.debug("Could not find recording start time in XDF header")
    return None


# ==================================================================================================================================================================================================================================================================================== #
# unix-timestamp-float <=> datetime                                                                                                                                                                                                                                                    #
# ==================================================================================================================================================================================================================================================================================== #
def datetime_to_unix_timestamp(dt: datetime) -> float:
    """Convert datetime to Unix timestamp (seconds since 1970-01-01 UTC).
    
    Reciprocal of `unix_timestamp_to_datetime`: round-tripping preserves the instant.
    This function safely handles both naive and timezone-aware datetimes.
    
    Args:
        dt: datetime object (naive or timezone-aware)
        
    Returns:
        Unix timestamp as float (seconds since epoch)
    """
    # If naive, assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    return dt.timestamp()


def unix_timestamp_to_datetime(ts: float) -> datetime:
    """Convert Unix timestamp (seconds since 1970-01-01 UTC) to timezone-aware UTC datetime.

    Reciprocal of `datetime_to_unix_timestamp`: round-tripping preserves the instant, i.e.
    datetime_to_unix_timestamp(datetime_from_unix_timestamp(ts)) == ts and
    datetime_from_unix_timestamp(datetime_to_unix_timestamp(dt)) represents the same moment as dt.
    These two functions are reciprocals of one another.

    Args:
        ts: Unix timestamp as float (seconds since epoch).

    Returns:
        Timezone-aware datetime in UTC.
    """
    return datetime.fromtimestamp(ts, tz=timezone.utc)


# ==================================================================================================================================================================================================================================================================================== #
# float <=> datetime                                                                                                                                                                                                                                                                   #
# ==================================================================================================================================================================================================================================================================================== #
def datetime_to_float(dt: datetime, reference_datetime: datetime) -> float:
    """Convert datetime back to float timestamp relative to reference.
    
    Args:
        dt: datetime object representing absolute time
        reference_datetime: Reference datetime object
        
    Returns:
        Float timestamp in seconds (relative to reference)
    """
    if reference_datetime is None:
        raise ValueError("reference_datetime cannot be None")
    delta = dt - reference_datetime
    return delta.total_seconds()


def float_to_datetime(timestamp: float, reference_datetime: datetime) -> datetime:
    """Convert a relative float timestamp to an absolute datetime.

    Note:
        The timeline system may pass datetime-like values through some paths (e.g. when
        operating in native datetime mode). In that case, this function will return the
        datetime-like value directly (normalized to timezone-aware UTC).
    
    Args:
        timestamp: Float timestamp in seconds (relative to reference)
        reference_datetime: Reference datetime object
        
    Returns:
        datetime object representing absolute time (timezone-aware, UTC)
    """
    if reference_datetime is None:
        raise ValueError("reference_datetime cannot be None")

    # If already datetime-like, return it directly (treat as absolute time).
    if isinstance(timestamp, (datetime, pd.Timestamp)):
        dt = pd.Timestamp(timestamp)
        if dt.tzinfo is None:
            dt = dt.tz_localize(timezone.utc)
        return dt.to_pydatetime()
    
    # Make reference_datetime timezone-aware if it's naive
    if reference_datetime.tzinfo is None:
        # Assume UTC if naive
        reference_datetime = reference_datetime.replace(tzinfo=timezone.utc)
    
    # Ensure numeric seconds
    seconds = float(timestamp)
    result = reference_datetime + timedelta(seconds=seconds)
    return result




def format_seconds_as_hhmmss(seconds: float, include_fractional: bool = True) -> str:
    """Format a duration or offset in seconds as HH:mm:ss or HH:mm:ss.fff.

    Args:
        seconds: Time in seconds (e.g. 3600.0 for one hour).
        include_fractional: If True, append .fff when there is a fractional part.

    Returns:
        String like "01:00:00" or "01:01:01.500".
    """
    total = abs(seconds)
    sign = "-" if seconds < 0 else ""
    h, r = divmod(int(total), 3600)
    m, s_int = divmod(r, 60)
    base = f"{sign}{h:02d}:{m:02d}:{s_int:02d}"
    if include_fractional:
        frac = total - int(total)
        if frac >= 1e-9:
            return f"{base}.{frac:.3f}"
    return base


def get_earliest_reference_datetime(file_headers: list, datasources: list) -> Optional[datetime]:
    """Get the earliest reference datetime from multiple sources.
    
    This function tries to extract reference datetimes from XDF file headers,
    and falls back to using the earliest timestamp from datasources if headers
    don't contain recording start times.
    
    Args:
        file_headers: List of XDF file header dictionaries
        datasources: List of TrackDatasource instances (for fallback)
        
    Returns:
        datetime object, or None if no reference can be determined
    """
    reference_datetimes = []
    
    # Try to get from XDF headers
    for file_header in file_headers:
        ref_dt = get_reference_datetime_from_xdf_header(file_header)
        if ref_dt is not None:
            reference_datetimes.append(ref_dt)
    
    # If we found any from headers, use the earliest one
    if reference_datetimes:
        return min(reference_datetimes)
    
    # Fallback: use earliest timestamp from datasources as Unix epoch reference
    # This assumes timestamps are relative to Unix epoch
    if datasources:
        earliest_timestamp = min([ds.total_df_start_end_times[0] for ds in datasources if ds is not None])
        # Use Unix epoch (1970-01-01 UTC) as reference (timezone-aware)
        return UNIX_EPOCH_UTC
    
    # Last resort: return Unix epoch (timezone-aware, UTC)
    logger.warning("No reference datetime found, using Unix epoch (1970-01-01 UTC)")
    return UNIX_EPOCH_UTC



def _normalize_datetime_to_utc_naive(series: pd.Series) -> pd.Series:
    """
    Normalize a datetime Series to naive UTC.
    - If aware: convert to UTC, then make naive.
    - If naive: assume Local Time, localize to system timezone, convert to UTC, then make naive.

    Usage:

        from pypho_timeline.utils.datetime_helpers import _normalize_datetime_to_utc_naive

    #TODO 2026-02-03 18:14: - [ ] This seems to mess up all the XDF stream dates, it isn't used on the video track at all and that's the only track with accurate datetimes

    """
    if series.empty:
        return series

    # Convert to datetime first to ensure properties exist
    series = pd.to_datetime(series, errors='coerce')
    
    # Check the first non-null value to determine if aware or naive
    first_valid = series.dropna().first_valid_index()
    if first_valid is None:
        return series
        
    first_val = series[first_valid]
    if first_val.tzinfo is None:
        # Naive -> Assume Local -> UTC
        # Get system local timezone
        local_tz = datetime.now().astimezone().tzinfo
        return series.dt.tz_localize(local_tz).dt.tz_convert('UTC').dt.tz_convert(None)
    else:
        # Aware -> UTC -> Naive
        return series.dt.tz_convert('UTC').dt.tz_convert(None)



