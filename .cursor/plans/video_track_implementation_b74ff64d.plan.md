---
name: Video Track Implementation
overview: Implement a complete video rendering track for pyPhoTimeline that parses video folders, extracts metadata, displays intervals on the timeline, and loads/renders video frames as thumbnails. This will integrate VideoMetadataParser functionality and actual video frame extraction.
todos:
  - id: add_opencv_dependency
    content: Add opencv-python to pyproject.toml dependencies
    status: completed
  - id: create_video_metadata_parser
    content: Create video_metadata.py with VideoMetadataParser class (copied/adapted from PhoOfflineEEGAnalysis)
    status: completed
  - id: create_helper_function
    content: Add video_metadata_to_intervals_df() helper function to convert VideoMetadataParser output to intervals_df format
    status: completed
    dependencies:
      - create_video_metadata_parser
  - id: update_video_track_datasource_init
    content: Update VideoTrackDatasource.__init__() to accept video_folder_path or video_df, parse videos, and use blue color scheme
    status: completed
    dependencies:
      - create_helper_function
  - id: implement_frame_loading
    content: Implement actual video frame loading in fetch_detailed_data() using cv2.VideoCapture
    status: completed
    dependencies:
      - update_video_track_datasource_init
  - id: update_thumbnail_renderer
    content: Enhance VideoThumbnailDetailRenderer to handle BGR->RGB conversion and improve frame rendering
    status: completed
    dependencies:
      - implement_frame_loading
  - id: update_exports
    content: Update __init__.py to export any new public APIs if needed
    status: completed
    dependencies:
      - update_thumbnail_renderer
---

# Video Track Implementation for pyPhoTimeline

## Overview

Implement a complete video rendering track system for `pyPhoTimeline` that:

1. Parses video folders and extracts metadata (datetime, duration, etc.)
2. Converts video metadata to timeline intervals (t_start, t_duration)
3. Displays video intervals on the timeline with blue color scheme
4. Loads and renders actual video frames as thumbnails in detail view

## Architecture

The implementation follows the existing `pyPhoTimeline` datasource pattern:

- `VideoMetadataParser`: Standalone class for parsing video folders (copied from PhoOfflineEEGAnalysis)
- `VideoTrackDatasource`: Extends `IntervalProvidingTrackDatasource` to provide video intervals
- `VideoThumbnailDetailRenderer`: Renders video frames as thumbnails (enhanced to load real frames)
- Helper function: Converts VideoMetadataParser output to intervals_df format

## Implementation Details

### 1. Add opencv-python dependency

**File**: `pyPhoTimeline/pyproject.toml`Add `opencv-python` to dependencies (or make it optional with a try/except import pattern).

### 2. Create VideoMetadataParser module

**File**: `pyPhoTimeline/pypho_timeline/rendering/datasources/specific/video_metadata.py` (new file)Copy and adapt `VideoMetadataParser` from `PhoOfflineEEGAnalysis/src/phoofflineeeganalysis/analysis/video_metadata.py`:

- Keep all core functionality (datetime extraction, metadata parsing, caching)
- Adapt imports to use `pyPhoTimeline` conventions
- Ensure function signatures are single-line per user preferences
- Keep the `@define(slots=False)` decorator pattern

Key methods:

- `extract_datetime_from_filename()`: Extract datetime from video filenames
- `extract_video_metadata()`: Extract metadata using cv2.VideoCapture
- `parse_video_folder()`: Main parsing method with caching support

### 3. Create helper function for DataFrame conversion

**File**: `pyPhoTimeline/pypho_timeline/rendering/datasources/specific/video.py`Add helper function to convert VideoMetadataParser output to intervals_df format:

```python
def video_metadata_to_intervals_df(video_df: pd.DataFrame, reference_timestamp: Optional[float] = None) -> pd.DataFrame:
    """Convert VideoMetadataParser output to intervals_df format.
    
    Args:
        video_df: DataFrame from VideoMetadataParser.parse_video_folder()
        reference_timestamp: Optional reference timestamp (Unix epoch seconds). 
                           If None, uses first video's start time as t=0.
    
    Returns:
        DataFrame with columns ['t_start', 't_duration', 'video_file_path', ...]
    """
```

Conversion logic:

- Convert `video_start_datetime` to Unix timestamp (float seconds)
- Calculate `t_start` relative to reference or first video
- Set `t_duration` from `video_duration` column
- Preserve metadata columns (video_file_path, fps, resolution, etc.)

### 4. Update VideoTrackDatasource

**File**: `pyPhoTimeline/pypho_timeline/rendering/datasources/specific/video.py`Enhance `VideoTrackDatasource.__init__()` to accept:

- `video_intervals_df`: DataFrame (existing behavior)
- `video_folder_path`: Path to folder (new - will parse using VideoMetadataParser)
- `video_df`: Pre-parsed DataFrame from VideoMetadataParser (new)

Update initialization:

- If `video_folder_path` provided, call `VideoMetadataParser.parse_video_folder()`
- Convert to intervals_df using helper function
- Store video_file_path in intervals_df for frame loading
- Use blue color scheme (matching PhoOfflineEEGAnalysis)

### 5. Implement actual video frame loading

**File**: `pyPhoTimeline/pypho_timeline/rendering/datasources/specific/video.py`Update `VideoTrackDatasource.fetch_detailed_data()`:

- Read `video_file_path` from interval Series
- Use cv2.VideoCapture to load video file
- Extract frames at regular intervals (e.g., 10 fps or configurable)
- Calculate frame timestamps relative to interval start
- Return dict with 'frames' (list of numpy arrays) and 'timestamps' (array)
- Handle errors gracefully (return empty frames if video can't be loaded)

Frame extraction logic:

- Open video with cv2.VideoCapture
- Get video FPS and frame count
- Sample frames at target rate (e.g., every N frames or every X seconds)
- Convert frames to uint8 format (BGR to RGB if needed)
- Resize frames to reasonable thumbnail size (e.g., 128x128 or configurable)

### 6. Update VideoThumbnailDetailRenderer

**File**: `pyPhoTimeline/pypho_timeline/rendering/datasources/specific/video.py`Enhance `VideoThumbnailDetailRenderer`:

- Ensure it properly handles BGR to RGB conversion for cv2 frames
- Add configurable thumbnail size parameters
- Improve frame positioning and spacing logic

### 7. Update color scheme

**File**: `pyPhoTimeline/pypho_timeline/rendering/datasources/specific/video.py`Change color from green to blue:

- Update `VideoTrackDatasource.__init__()` to use blue color
- Match the blue shade from PhoOfflineEEGAnalysis: `(100, 150, 200, 255)` for pen, `(100, 150, 200, 150)` for brush

### 8. Update **init**.py exports

**File**: `pyPhoTimeline/pypho_timeline/rendering/datasources/specific/__init__.py`Add export for `VideoMetadataParser` if needed (or keep it internal to video.py).

## Data Flow

```javascript
VideoMetadataParser.parse_video_folder()
    ↓
video_df (with video_start_datetime, video_duration, video_file_path, ...)
    ↓
video_metadata_to_intervals_df()
    ↓
intervals_df (with t_start, t_duration, video_file_path, ...)
    ↓
VideoTrackDatasource(intervals_df)
    ↓
Timeline rendering (overview intervals)
    ↓
User zooms/clicks interval
    ↓
fetch_detailed_data(interval)
    ↓
cv2.VideoCapture loads frames
    ↓
VideoThumbnailDetailRenderer.render_detail()
    ↓
Thumbnails displayed on timeline
```



## Files to Modify

1. `pyPhoTimeline/pyproject.toml` - Add opencv-python dependency
2. `pyPhoTimeline/pypho_timeline/rendering/datasources/specific/video.py` - Major updates
3. `pyPhoTimeline/pypho_timeline/rendering/datasources/specific/__init__.py` - Update exports if needed

## Files to Create

1. `pyPhoTimeline/pypho_timeline/rendering/datasources/specific/video_metadata.py` - VideoMetadataParser class

## Testing Considerations

- Test with various video formats (mp4, avi, mov, mkv)
- Test datetime extraction from different filename patterns
- Test frame loading with videos of different resolutions
- Test caching behavior (modify video file, verify cache updates)
- Test error handling (missing files, corrupted videos, etc.)

## Notes

- Follow pyPhoTimeline code style (single-line function signatures when possible)