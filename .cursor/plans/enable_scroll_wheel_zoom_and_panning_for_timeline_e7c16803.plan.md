---
name: Enable scroll wheel zoom and panning for timeline
overview: Enable scroll wheel zooming and panning across all timeline tracks by enabling mouse interaction on plot items, adding wheel event handling to CustomViewBox, and implementing synchronized zooming across tracks.
todos:
  - id: enable_mouse_interaction
    content: Enable x-axis mouse interaction in PyqtgraphTimeSynchronizedWidget._buildGraphics() (line 206)
    status: completed
  - id: add_wheel_event_handler
    content: Add wheelEvent method to CustomViewBox class for scroll wheel zooming
    status: completed
  - id: implement_synchronized_zoom
    content: Implement synchronized zooming across tracks in TO_GLOBAL_DATA sync mode using X-axis linking
    status: completed
    dependencies:
      - enable_mouse_interaction
      - add_wheel_event_handler
---

# Enable Scroll Wheel Zooming and Panning for Timeline

## Overview

The timeline currently has mouse interaction disabled and lacks scroll wheel zoom support. This plan enables scroll wheel zooming and panning across all timeline tracks while maintaining the existing interaction model (left-click for timeline navigation, middle-click for panning, right-click for rectangular zoom).

## Current Issues

1. **Mouse interaction disabled**: In `PyqtgraphTimeSynchronizedWidget._buildGraphics()`, line 206 disables mouse interaction: `self.ui.root_plot.setMouseEnabled(x=False, y=False)`
2. **No wheel event handler**: `CustomViewBox` class doesn't override `wheelEvent` for scroll wheel zooming
3. **No synchronized zooming**: Tracks zoom independently; no mechanism to synchronize zoom across tracks

## Implementation Plan

### 1. Enable Mouse Interaction on Plot Items

**File**: `pypho_timeline/core/pyqtgraph_time_synchronized_widget.py`

- **Line 206**: Change `setMouseEnabled(x=False, y=False)` to `setMouseEnabled(x=True, y=False)`
- Enables horizontal (x-axis) mouse interaction for panning and zooming
- Keeps y-axis disabled to prevent vertical panning/zooming

### 2. Add Wheel Event Handler to CustomViewBox

**File**: `pypho_timeline/widgets/custom_graphics_layout_widget.py`

- **After line 263** (after `mouseDragEvent` method): Add new `wheelEvent` method:
  ```python
        def wheelEvent(self, ev, axis=None):
            """Handle mouse wheel events for zooming.
            
            Uses pyqtgraph's default wheel zoom behavior which zooms centered on mouse position.
            """
            if self._debug_print:
                print(f'CustomViewBox.wheelEvent(ev: {ev}, axis={axis})')
            
            # Use default pyqtgraph wheel zoom behavior
            # This will zoom centered on the mouse position
            super().wheelEvent(ev, axis=axis)
            ev.accept()
  ```




### 3. Implement Synchronized Zooming Across Tracks

**File**: `pypho_timeline/docking/specific_dock_widget_mixin.py`

- **In `add_new_embedded_pyqtgraph_render_plot_widget` method** (after line 125, before return):
- Add logic to link X-axes of tracks that are in `TO_GLOBAL_DATA` sync mode
- This will synchronize zooming across all tracks that share the same global data view

Implementation approach:

- When a new track is added with `sync_mode=TO_GLOBAL_DATA`, link its X-axis to other tracks with the same sync mode
- Use pyqtgraph's `setXLink()` method to create linked axes
- Store linked plot items to manage the linking relationships

**Alternative simpler approach** (if linking becomes complex):

- Add a signal to `CustomViewBox` that emits on zoom events
- Connect this signal to update all other tracks' X-ranges when one track zooms
- This gives more control but requires more code

### 4. Ensure Proper Mouse Mode Configuration

**File**: `pypho_timeline/widgets/custom_graphics_layout_widget.py`

- **Line 155**: The `setMouseMode(self.RectMode)` is appropriate for right-click rectangular zoom
- Verify that wheel events work correctly with this mode (they should, as wheel events are separate from drag events)
- The existing `mouseDragEvent` implementation already handles:
- Right-click: Rectangular zoom (line 196-199)
- Left-click: Timeline navigation via `sigLeftDrag` (line 200-239)
- Middle-click: Panning (line 241-256)

## Testing Considerations

- Test scroll wheel zooming on individual tracks
- Test synchronized zooming across multiple tracks in `TO_GLOBAL_DATA` mode
- Verify that left-click drag still works for timeline navigation
- Verify that middle-click panning still works
- Verify that right-click rectangular zoom still works
- Test with tracks in different sync modes (`NO_SYNC`, `TO_WINDOW`, `TO_GLOBAL_DATA`)

## Files to Modify

1. `pypho_timeline/core/pyqtgraph_time_synchronized_widget.py` - Enable mouse interaction
2. `pypho_timeline/widgets/custom_graphics_layout_widget.py` - Add wheel event handler
3. `pypho_timeline/docking/specific_dock_widget_mixin.py` - Implement synchronized zooming (optional, can be added in a follow-up if needed)

## Notes