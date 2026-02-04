---
name: vispy video track renderer
overview: Implement a high-performance vispy-based renderer for video epoch rectangles that integrates with the existing TrackRenderer architecture, using instanced rendering for efficient real-time updates aligned on a datetime axis.
todos:
  - id: create_vispy_renderer
    content: Create VispyVideoEpochRenderer class with SceneCanvas and ViewBox setup
    status: completed
  - id: implement_instanced_visual
    content: Implement InstancedEpochQuadVisual with shader-based instanced rendering
    status: completed
    dependencies:
      - create_vispy_renderer
  - id: datetime_axis
    content: Implement datetime axis with proper tick formatting and conversion
    status: completed
    dependencies:
      - create_vispy_renderer
  - id: viewport_culling
    content: Add viewport culling to only render visible epochs
    status: completed
    dependencies:
      - implement_instanced_visual
  - id: integrate_track_renderer
    content: Integrate vispy renderer with TrackRenderer for data management
    status: completed
    dependencies:
      - create_vispy_renderer
      - datetime_axis
  - id: update_video_datasource
    content: Add use_vispy_renderer option to VideoTrackDatasource
    status: completed
  - id: update_timeline_widget
    content: Update SimpleTimelineWidget.add_video_track() to support vispy option
    status: completed
    dependencies:
      - integrate_track_renderer
      - update_video_datasource
  - id: performance_optimizations
    content: Implement buffer reuse, batch updates, and rate limiting
    status: completed
    dependencies:
      - implement_instanced_visual
      - viewport_culling
---

# VisPy Video Track Renderer Implementation

## Overview

Create a new high-performance vispy-based renderer for video epoch rectangles that displays video intervals (start, stop) as rectangles aligned on a datetime axis. The renderer will use vispy's instanced rendering capabilities for efficient real-time updates, following best practices from the vispy realtime data tutorial.

## Architecture

The implementation will create a new renderer class that integrates with the existing `TrackRenderer` architecture while using vispy for GPU-accelerated rendering:

```
VideoTrackDatasource (existing)
    ↓
TrackRenderer (existing - data management)
    ↓
VispyVideoEpochRenderer (new - vispy rendering)
    ↓
vispy SceneCanvas with instanced quad visual
```

## Implementation Plan

### 1. Create VispyVideoEpochRenderer Class

**File**: `pypho_timeline/rendering/graphics/vispy_video_epoch_renderer.py`

Create a new renderer class that:

- Uses vispy's `SceneCanvas` and `ViewBox` for the rendering area
- Implements instanced quad rendering for all video epoch rectangles
- Handles datetime-to-float conversion for X-axis alignment
- Updates efficiently when viewport changes or data updates

Key components:

- `VispyVideoEpochRenderer`: Main renderer class managing the vispy canvas
- `InstancedEpochQuadVisual`: Custom vispy Visual using instanced rendering for rectangles
- Datetime axis handling with proper tick formatting
- Integration with existing `TrackRenderer` for data management

### 2. Create InstancedEpochQuadVisual

**File**: `pypho_timeline/rendering/graphics/vispy_video_epoch_renderer.py`

Implement a custom vispy Visual that:

- Uses instanced rendering (single draw call for all rectangles)
- Accepts per-instance attributes: x_start, x_width, y, height, color
- Uses a unit quad mesh with per-instance transforms
- Handles GPU buffer updates efficiently (only upload changed data)
- Supports viewport culling (only render visible epochs)

Shader structure:

- Vertex shader: Transform unit quad by instance attributes (shift + scale)
- Fragment shader: Simple color output
- Use `divisor=1` for instanced attributes

### 3. Datetime Axis Integration

**File**: `pypho_timeline/rendering/graphics/vispy_video_epoch_renderer.py`

Implement datetime axis handling:

- Convert datetime to float (Unix timestamp or relative to reference_datetime)
- Use vispy's `AxisVisual` with custom tick formatter
- Format tick labels as readable dates (e.g., "2024-01-15 10:30:00")
- Handle timezone-aware datetimes if needed
- Support pan/zoom on datetime axis

### 4. Integrate with TrackRenderer

**File**: `pypho_timeline/rendering/graphics/track_renderer.py`

Modify `TrackRenderer` to support vispy rendering:

- Add optional `use_vispy` parameter to `__init__`
- When `use_vispy=True` for video tracks, create `VispyVideoEpochRenderer` instead of `IntervalRectsItem`
- Keep existing data management logic (viewport updates, interval tracking)
- Bridge between `update_viewport()` and vispy renderer updates

Integration points:

- `_update_overview()`: Create vispy renderer instead of IntervalRectsItem
- `update_viewport()`: Call vispy renderer's update method with visible intervals
- `remove()`: Clean up vispy canvas properly

### 5. Update VideoTrackDatasource

**File**: `pypho_timeline/rendering/datasources/specific/video.py`

Add option to use vispy renderer:

- Add `use_vispy_renderer: bool = False` parameter to `__init__`
- Store flag for renderer selection
- Modify `get_detail_renderer()` to return appropriate renderer (or None for vispy)

### 6. Add Vispy Dependencies

**File**: `pyproject.toml`

Ensure vispy is in dependencies:

- Add `vispy>=0.14.0` to dependencies (already present in uv.lock, verify version)
- Document vispy requirement for video track rendering

### 7. Performance Optimizations

**File**: `pypho_timeline/rendering/graphics/vispy_video_epoch_renderer.py`

Implement performance best practices:

- **Viewport culling**: Only render epochs overlapping visible time window
- **Buffer reuse**: Pre-allocate GPU buffers, only update changed data
- **Batch updates**: Accumulate multiple changes before triggering redraw
- **Rate limiting**: Use timers/signals to limit update frequency
- **Minimal redraws**: Only redraw when data changes or viewport changes
- **GPU state optimization**: Use appropriate blend modes, disable depth testing for 2D

### 8. Integration with SimpleTimelineWidget

**File**: `pypho_timeline/widgets/simple_timeline_widget.py`

Update `add_video_track()` to support vispy option:

- Add `use_vispy: bool = False` parameter
- Pass flag to `VideoTrackDatasource`
- Ensure vispy canvas is properly embedded in Qt widget hierarchy
- Handle widget resizing and layout properly

### 9. Testing and Validation

Create test/example:

- Verify instanced rendering works with many epochs (1000+)
- Test datetime axis formatting and pan/zoom
- Verify real-time updates when viewport changes
- Performance profiling to ensure smooth 60fps rendering
- Test with various video epoch configurations

## Key Implementation Details

### Instanced Rendering Pattern

```python
# Unit quad vertices (two triangles)
unit_quad = np.array([
    [0.0, 0.0], [1.0, 0.0], [1.0, 1.0],  # First triangle
    [0.0, 0.0], [1.0, 1.0], [0.0, 1.0]   # Second triangle
], dtype=np.float32)

# Per-instance attributes (divisor=1)
shifts = np.array([[x_start, y], ...])  # Position
sizes = np.array([[width, height], ...])  # Size
colors = np.array([[r, g, b, a], ...])  # Color
```

### Datetime Conversion

```python
def datetime_to_float(dt, reference_datetime):
    """Convert datetime to float for vispy rendering."""
    if reference_datetime is None:
        return dt.timestamp()  # Unix timestamp
    else:
        return (dt - reference_datetime).total_seconds()
```

### Update Strategy

- On viewport change: Filter epochs to visible range, update instance buffers
- On data change: Rebuild instance buffers, trigger redraw
- Use Qt signals/timers for thread-safe updates from data management layer

## Files to Create/Modify

1. **New**: `pypho_timeline/rendering/graphics/vispy_video_epoch_renderer.py` - Main vispy renderer implementation
2. **Modify**: `pypho_timeline/rendering/graphics/track_renderer.py` - Add vispy renderer support
3. **Modify**: `pypho_timeline/rendering/datasources/specific/video.py` - Add use_vispy_renderer option
4. **Modify**: `pypho_timeline/widgets/simple_timeline_widget.py` - Add vispy option to add_video_track()
5. **Verify**: `pyproject.toml` - Ensure vispy dependency

## Success Criteria

- Video epochs render as rectangles aligned on datetime axis
- Smooth 60fps rendering with 1000+ epochs
- Efficient viewport updates (only visible epochs rendered)
- Proper datetime axis formatting and interaction
- Integration with existing TrackRenderer data management
- No performance degradation compared to pyqtgraph version