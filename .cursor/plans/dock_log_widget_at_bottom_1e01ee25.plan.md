---
name: Dock log widget at bottom
overview: Add logic to dock the TimelineBuilder's log_widget at the bottom of the timeline window by default when it's not None. This will integrate the log widget into the timeline interface instead of showing it as a separate window.
todos:
  - id: dock-log-widget
    content: Add logic in build_from_datasources to dock log_widget at bottom of timeline if it's not None
    status: completed
---

# Dock Log Widget at Bottom of Timeline Window

## Overview

When `TimelineBuilder` creates a timeline widget, if `self.log_widget` is not None, dock it at the bottom of the timeline window by default. This integrates the log widget into the timeline interface.

## Implementation Details

### Changes to `timeline_builder.py`

1. **Modify `build_from_datasources` method** (lines 301-362):

- After the timeline is created, configured, and shown (after line 353)
- Add a check: if `self.log_widget is not None`
- If true, dock the log widget using the timeline's dock container:
- Call `timeline.ui.dynamic_docked_widget_container.add_display_dock()` 
- Use identifier `'log_widget'`
- Pass `widget=self.log_widget`
- Set `dockSize` to a reasonable size like `(800, 200)` for a log panel
- Set `dockAddLocationOpts=['bottom']` to dock at the bottom
- Hide the standalone log widget window (call `self.log_widget.hide()` or `self.log_widget.setParent(timeline)`) since it will be embedded in the dock

2. **Consider other build methods**:

- The same logic should apply to all build methods that return a `SimpleTimelineWidget`
- Since `build_from_xdf_file`, `build_from_xdf_files`, `build_from_streams`, and `build_from_video` all call `build_from_datasources`, the change in `build_from_datasources` will cover all cases

### Code Location

- File: [`pypho_timeline/timeline_builder.py`](pypho_timeline/timeline_builder.py)
- Method: `build_from_datasources` (around line 353, after `timeline.show()`)

### Implementation Notes

- The log widget should be docked after all tracks are added, ensuring it appears at the very bottom
- The dock container is accessible via `timeline.ui.dynamic_docked_widget_container` which implements `DynamicDockDisplayAreaContentMixin` with the `add_display_dock` method
- The log widget is already created in `TimelineBuilder.__init__` (line 63), so we just need to dock it when a timeline is built
- If the log widget was shown as a standalone window (line 77), we should hide it when docking it to avoid duplicate windows