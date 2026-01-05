---
name: Finish EEG Implementation
overview: Complete the implementation of EEGPlotDetailRenderer and EEGTrackDatasource by fixing bugs, ensuring all methods are properly implemented, and verifying consistency with similar implementations like MotionPlotDetailRenderer.
todos: []
---

# Finish Implementing EEGPlotDetailRenderer and EEGTrackDatasource

## Issues Identified

1. **Bug in `EEGPlotDetailRenderer.render_detail()`**: Line 118 references `self.pen_color` which doesn't exist as an instance variable. This occurs in the fallback case when `channel_names is None`.
2. **TODO Comment**: There's a TODO suggesting `EEGPlotDetailRenderer` should inherit from `GenericPlotDetailRenderer`, but `MotionPlotDetailRenderer` has the same TODO and doesn't implement it. The current direct inheritance from `DetailRenderer` protocol is functional.
3. **Completeness Check**: Verify all required methods are implemented and match the pattern used by `MotionPlotDetailRenderer` and `MotionTrackDatasource`.

## Implementation Plan

### 1. Fix Bug in `EEGPlotDetailRenderer.render_detail()`

**File**: [`pyPhoTimeline/pypho_timeline/rendering/datasources/specific/eeg.py`](pyPhoTimeline/pypho_timeline/rendering/datasources/specific/eeg.py)**Issue**: Lines 114-121 contain a fallback case that references `self.pen_color` which is never defined. The `__init__` method only sets `self.pen_colors` (plural).**Fix**:

- Add a default `pen_color` parameter to `__init__` for the fallback case
- Or use a default color when `channel_names is None` and `pen_colors is None`
- Update the fallback rendering logic to use the correct attribute

**Current problematic code** (lines 114-121):

```python
else:
    # Fallback: use single pen_color if channel_names is None
    if 'x' in df_sorted.columns:
        x_values = df_sorted['x'].values
        pen = pg.mkPen(self.pen_color, width=self.pen_width)  # BUG: self.pen_color doesn't exist
        plot_data_item = pg.PlotDataItem(t_values, x_values, pen=pen, connect='finite')
        plot_item.addItem(plot_data_item)
        graphics_objects.append(plot_data_item)
```



### 2. Ensure Consistency with MotionPlotDetailRenderer

Compare the implementation with `MotionPlotDetailRenderer` to ensure:

- Same error handling patterns
- Same bounds calculation logic
- Same clear_detail implementation
- Consistent parameter handling

### 3. Verify EEGTrackDatasource Completeness

**File**: [`pyPhoTimeline/pypho_timeline/rendering/datasources/specific/eeg.py`](pyPhoTimeline/pypho_timeline/rendering/datasources/specific/eeg.py)Verify that `EEGTrackDatasource` has all required methods:

- ✅ `__init__` - implemented
- ✅ `get_detail_renderer()` - implemented  
- ✅ `get_detail_cache_key()` - implemented

Compare with `MotionTrackDatasource` to ensure consistency.

### 4. Optional: Address TODO Comment

The TODO suggests inheriting from `GenericPlotDetailRenderer`, but:

- `GenericPlotDetailRenderer` is designed to wrap functions, not for traditional inheritance
- `MotionPlotDetailRenderer` has the same TODO and doesn't implement it
- The current implementation works correctly (after bug fix)

**Decision**: Keep current structure for now, but ensure the TODO is either:

- Removed if not needed, or
- Updated with a note explaining why it's deferred

## Files to Modify

1. `pyPhoTimeline/pypho_timeline/rendering/datasources/specific/eeg.py`

- Fix `self.pen_color` bug in `render_detail()` method
- Add default `pen_color` parameter to `__init__` if needed
- Verify all methods are complete

## Testing Considerations

After implementation, verify:

- EEGPlotDetailRenderer can render EEG channels correctly