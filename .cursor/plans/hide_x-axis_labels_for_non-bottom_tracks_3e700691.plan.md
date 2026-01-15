---
name: Hide x-axis labels for non-bottom tracks
overview: Hide x-axis labels and tick values for all timeline tracks except the bottom-most one to reduce visual clutter when multiple tracks are displayed.
todos:
  - id: hide-xaxis-timeline-builder
    content: Modify _add_tracks_to_timeline in timeline_builder.py to hide x-axis for all tracks except the last one after adding all tracks
    status: completed
  - id: hide-xaxis-video-track
    content: Modify add_video_track in simple_timeline_widget.py to hide x-axis if there are other tracks and this is not the last one
    status: completed
---

# Hide x-axis labels for non-bottom tracks

## Overview

When multiple tracks are added to the timeline, hide the x-axis labels and tick values for all tracks except the bottom-most one, since they are redundant and create visual clutter.

## Implementation

### Changes Required

1. **`pypho_timeline/timeline_builder.py`** - `_add_tracks_to_timeline` method:

- After the loop that adds all tracks (after line 453), add logic to:
- Get all plot items from `timeline.ui.matplotlib_view_widgets`
- Hide the x-axis (labels and ticks) for all plot items except the last one
- Use `plot_item.hideAxis('bottom')` to hide the x-axis
- The last track in the dictionary will be the bottom-most since tracks are added sequentially with `dockAddLocationOpts=['bottom']`

2. **`pypho_timeline/widgets/simple_timeline_widget.py`** - `add_video_track` method:

- After adding the track (after line 188), check if there are other tracks
- If this is not the last track, hide the x-axis using `plot_item.hideAxis('bottom')`
- This ensures consistency when tracks are added individually

### Technical Details

- PyQtGraph's `hideAxis('bottom')` will hide both the axis label and tick values
- The bottom-most track is determined by the order in `timeline.ui.matplotlib_view_widgets` - the last item added will be at the bottom
- When tracks are added via `_add_tracks_to_timeline`, they're added sequentially, so the last one in the datasources list will be the bottom-most
- For `add_video_track`, we need to check if there are other tracks and determine if this is the last one

### Edge Cases

- If only one track exists, show the x-axis (no change needed)
- If tracks are removed, the remaining bottom-most track should show the x-axis (may need to add logic in `remove_track` or handle dynamically)
- When tracks are added via `update_timeline`, the same logic should apply

## Files to Modify

1. `pypho_timeline/timeline_builder.py` - Modify `_add_tracks_to_timeline` method
2. `pypho_timeline/widgets/simple_timeline_widget.py` - Modify `add_video_track` method (optional, for consistency)