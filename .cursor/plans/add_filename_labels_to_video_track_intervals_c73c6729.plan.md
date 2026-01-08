---
name: Add filename labels to video track intervals
overview: Add filename labels to video track interval rectangles that display the video filename as small text inside each interval rect, with automatic truncation. Labels should be visible in both overview and detailed view modes.
todos:
  - id: add-label-column-video-datasource
    content: Add 'label' column to VideoTrackDatasource.intervals_df containing filename extracted from video_file_path
    status: completed
  - id: add-format-label-fn-track-renderer
    content: Add format_label_fn parameter to build_IntervalRectsItem_from_interval_datasource() call in TrackRenderer._update_overview() for VideoTrackDatasource instances
    status: completed
    dependencies:
      - add-label-column-video-datasource
---

# Add Filename Labels to Video Track Intervals

## Overview

Video tracks should display their filename as small text inside each interval rectangle. The text should automatically truncate to fit within the rect bounds and should be visible in both overview and detailed view modes.

## Implementation

### 1. Add label column to VideoTrackDatasource intervals

**File**: `pypho_timeline/rendering/datasources/specific/video.py`In `VideoTrackDatasource.__init__()`, after setting visualization properties (around line 387), add a 'label' column to `self.intervals_df` that contains the filename extracted from `video_file_path`:

- Extract filename from `video_file_path` using `Path(video_file_path).name`
- Add this as a 'label' column to `self.intervals_df`
- The label will be automatically included in the `IntervalRectsItemData` objects when building the interval rects

### 2. Add format_label_fn to TrackRenderer for video tracks

**File**: `pypho_timeline/rendering/graphics/track_renderer.py`In `TrackRenderer._update_overview()` (around line 97), detect if the datasource is a `VideoTrackDatasource` and pass a `format_label_fn` parameter to `build_IntervalRectsItem_from_interval_datasource()`:

- Import `VideoTrackDatasource` at the top of the file
- Check if `isinstance(self.datasource, VideoTrackDatasource)`
- If true, create a `format_label_fn` that extracts the label from the `IntervalRectsItemData` object
- The function should return the label string (which will be automatically truncated by `CustomRectBoundedTextItem`)

### 3. Ensure labels work in both overview and detailed views

The existing `IntervalRectsItem` label rendering system already handles:

- Text truncation via `CustomRectBoundedTextItem` (automatically truncates to fit rect bounds)
- Visibility in all zoom levels (labels are part of the overview rects item, not detail overlays)

No additional changes needed - labels will automatically appear in both overview and detailed views since they're part of the base `IntervalRectsItem`.

## Technical Details

- The `_build_interval_tuple_list_from_dataframe()` method in `Render2DEventRectanglesHelper` already checks for a 'label' column and includes it in `IntervalRectsItemData` objects
- `CustomRectBoundedTextItem` handles text truncation automatically based on the rect bounds
- Labels are rendered as part of the overview rectangles, so they persist across all zoom levels
- The label format function receives `rect_index` and `rect_data_tuple` (which can be an `IntervalRectsItemData` with a `label` attribute)

## Files to Modify