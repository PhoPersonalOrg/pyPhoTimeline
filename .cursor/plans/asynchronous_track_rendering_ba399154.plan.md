---
name: Asynchronous Track Rendering
overview: Make all track types render asynchronously so the UI remains responsive even when one track is slow or hanging. Each track's viewport update will be scheduled independently using Qt's event loop.
todos: []
---

# Asynchronous Track Rendering Implementation

## Problem

Currently, track viewport updates run synchronously, causing one slow track to block all others and freeze the UI. The `update_viewport()` method performs heavy operations like `get_updated_data_window()` synchronously on the main thread.

## Solution

Defer all track viewport updates to Qt's event loop using `QTimer.singleShot()`, allowing:

- Each track to process independently
- UI to remain responsive during updates
- One slow track to not block others

## Implementation

### 1. Make `TrackRenderer.update_viewport()` asynchronous

**File**: `pypho_timeline/rendering/graphics/track_renderer.py`

Wrap the entire viewport update logic in a deferred function that runs via `QTimer.singleShot(0, ...)`. This defers the heavy `get_updated_data_window()` call and all interval processing to the next event loop iteration.

**Changes**:

- Move all current `update_viewport()` logic into an inner `process_viewport_update()` function
- Have `update_viewport()` immediately schedule `process_viewport_update()` using `QtCore.QTimer.singleShot(0, process_viewport_update)`
- Keep the video track early-return optimization inside the deferred function

### 2. Make `TrackRenderingMixin_on_window_update()` schedule tracks asynchronously

**File**: `pypho_timeline/rendering/mixins/track_rendering_mixin.py`

Instead of calling `update_viewport()` synchronously for each track in a loop, schedule each track's update with a small staggered delay (1ms per track) to allow event loop processing between tracks.

**Changes**:

- Replace the synchronous loop with individual `QTimer.singleShot()` calls
- Use closure to capture track renderer and viewport parameters
- Stagger updates: `QtCore.QTimer.singleShot(idx * 1, update_fn)` where `idx` is the track index

### 3. Make `_on_plot_viewport_changed()` asynchronous

**File**: `pypho_timeline/rendering/mixins/track_rendering_mixin.py`

Defer the viewport update when triggered by individual plot viewport changes.

**Changes**:

- Wrap the `update_viewport()` call in a deferred function
- Use `QtCore.QTimer.singleShot(0, deferred_update)` to schedule it

## Benefits

1. **Non-blocking**: Heavy operations don't freeze the UI
2. **Independent processing**: Each track updates independently
3. **Responsive UI**: Event loop can process other events between track updates
4. **Universal**: Applies to all track types (video, position, EEG, etc.)

## Architecture Flow

```
Viewport Change Event
    ↓
TrackRenderingMixin_on_window_update()
    ↓
Schedule each track with QTimer.singleShot(idx * 1ms)
    ↓
[Event Loop processes other events]
    ↓
Track 1: update_viewport() → QTimer.singleShot(0) → process_viewport_update()
Track 2: update_viewport() → QTimer.singleShot(0) → process_viewport_update()
Track 3: update_viewport() → QTimer.singleShot(0) → process_viewport_update()
    ↓
Each track processes independently without blocking others
```

## Testing Considerations

- Verify UI remains responsive when one track has many intervals
- Confirm all tracks eventually update correctly
- Check that rapid viewport changes don't create excessive queued updates
- Ensure video tracks still skip detail processing correctly