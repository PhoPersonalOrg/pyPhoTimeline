---
name: Convert time axes to datetime
overview: Convert all x (time) axes for timeline tracks from float seconds to datetime axes, using XDF file header recording start time as the reference datetime when available.
todos: []
---

# Convert Time Axes to Datetime Axes

## Overview

Convert all x (time) axes for timeline tracks from float seconds to datetime axes. **Critical requirement**: All tracks must use a single, consistent absolute datetime reference to maintain real-time alignment, even when tracks start/stop independently. The reference datetime will be extracted from XDF file headers when available, with fallback options for other data sources.

## Key Changes

### 1. Add Datetime Reference Management (CRITICAL: Single Reference for Alignment)

- **File**: `pypho_timeline/timeline_builder.py`
  - Extract reference datetime from XDF file headers in `build_from_xdf_files()`
  - **Use a single reference datetime for the entire timeline** - this ensures all tracks align in real time
  - For multiple XDF files: Use the earliest recording start time as the common reference
  - Store reference datetime in `TimelineBuilder` instance and pass to `SimpleTimelineWidget`
  - All tracks in a timeline must use the same reference datetime for proper alignment
  - Handle fallback when XDF header doesn't have recording start time (use Unix epoch or earliest timestamp across all datasources)

### 2. Update SimpleTimelineWidget

- **File**: `pypho_timeline/widgets/simple_timeline_widget.py`
  - Add `reference_datetime` parameter to `__init__()`
  - Store reference datetime as instance attribute
  - Convert time values when setting ranges and labels

### 3. Configure PyQtGraph DateAxisItem

- **File**: `pypho_timeline/core/pyqtgraph_time_synchronized_widget.py`
  - Replace standard bottom axis with `pg.DateAxisItem` in `_buildGraphics()`
  - Update `on_window_changed()` to convert float times to datetime before setting ranges
  - Ensure all time operations use datetime-aware values

### 4. Update Timeline Builder Track Creation

- **File**: `pypho_timeline/timeline_builder.py`
  - In `_add_tracks_to_timeline()`, configure axes with datetime formatting
  - Convert `setXRange()` calls to use datetime values
  - Update `setLabel()` to use datetime format instead of 's' units

### 5. Update Other Axis Configuration Points

- **Files to update**:
  - `pypho_timeline/widgets/simple_timeline_widget.py` - `add_video_track()` method
  - `pypho_timeline/__main__.py` - Main entry point axis configuration
  - `pypho_timeline/docking/specific_dock_widget_mixin.py` - Overview plot axes
  - `pypho_timeline/docking/dynamic_dock_display_area.py` - Widget axis configuration

### 6. Helper Functions

- **New file**: `pypho_timeline/utils/datetime_helpers.py`
  - `get_reference_datetime_from_xdf_header(file_header)` - Extract datetime from XDF header
  - `float_to_datetime(timestamp, reference_datetime)` - Convert float to datetime
  - `datetime_to_float(dt, reference_datetime)` - Convert datetime back to float (for internal calculations)

### 7. Handle Edge Cases (Maintaining Real-Time Alignment)

- **Multiple XDF files**: Use the earliest reference datetime across all files as the common reference point
- **Mixed data sources**: When combining XDF and video tracks, use the earliest available reference datetime
- **Video-only timelines**: Use Unix epoch or configurable reference (must be consistent across all video tracks)
- **Missing XDF header info**: Fallback to Unix epoch (1970-01-01) or use earliest timestamp across all datasources
- **Track start/stop independence**: Tracks can have different start/stop times, but all use the same reference datetime for alignment
- **Maintain backward compatibility**: Internal calculations can still use float seconds (relative to reference), but display uses datetime

## Implementation Details

### PyQtGraph DateAxisItem Usage

```python
from pyphoplacecellanalysis.External.pyqtgraph import DateAxisItem
axis = DateAxisItem(orientation='bottom')
plot_item.setAxisItems({'bottom': axis})
```

### Time Conversion Pattern (Ensuring Alignment)

- Store reference datetime as `datetime.datetime` object (single instance shared across all tracks)
- Convert float timestamps to datetime: `reference_datetime + timedelta(seconds=timestamp)`
- **All tracks use the same reference_datetime** - this ensures real-time alignment
- Use datetime values for axis ranges and labels (display layer)
- Keep internal calculations in float seconds for performance (data layer)
- When tracks start at different times, their timestamps are converted using the same reference, so they appear at correct absolute positions on the datetime axis

### XDF Header Parsing

- Check `file_header` for recording start time
- Common locations: `file_header['info']['recording']['start_time']` or similar
- Parse ISO format or Unix timestamp format as needed