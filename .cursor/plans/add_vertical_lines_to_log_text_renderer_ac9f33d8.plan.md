---
name: Add vertical lines to log text renderer
overview: Add thin vertical lines at each message time coordinate in LogTextDataFramePlotDetailRenderer, in addition to the existing text labels. The lines will span the visible y-range for efficient rendering.
todos: []
---

# Add Vertical Lines to Log Text Renderer

## Overview

Enhance `LogTextDataFramePlotDetailRenderer` to draw thin vertical lines at each message's time coordinate, in addition to the existing text labels. This will provide visual markers that make it easier to identify message timestamps.

## Implementation Details

### File to Modify

- [`pyPhoTimeline/pypho_timeline/rendering/detail_renderers/log_text_plot_renderer.py`](H:\TEMP\Spike3DEnv_ExploreUpgrade\Spike3DWorkEnv\pyPhoTimeline\pypho_timeline\rendering\detail_renderers\log_text_plot_renderer.py)

### Changes Required

1. **Add vertical line styling parameters to `__init__`** (lines 26-46):

- Add `line_color` parameter (default: same as `text_color` or a subtle color like 'gray')
- Add `line_width` parameter (default: 1 for thin lines)
- Add `enable_lines` parameter (default: True) to allow disabling lines if needed
- Store these as instance variables

2. **Modify `render_detail` method** (lines 48-130):

- In the loop that creates text items (lines 93-128), also create a vertical line for each message
- Use `pg.InfiniteLine(angle=90, movable=False, pos=t_value)` to create vertical lines
- Set pen properties using `setPen()` with the configured color and width
- Add each line to `plot_item` and append to `graphics_objects` list
- Position lines at the same x-coordinate (`t_value`) as the corresponding text label

3. **Efficiency Considerations**:

- Use `pg.InfiniteLine` which is optimized for drawing lines that span the entire view
- Lines will automatically span the full y-range of the plot
- Create lines in the same loop as text items to minimize iterations

### Implementation Pattern

The vertical lines will be created using:

```python
vline = pg.InfiniteLine(angle=90, movable=False, pos=t_value)
vline.setPen(pg.mkPen(color=self.line_color, width=self.line_width))
plot_item.addItem(vline, ignoreBounds=True)
graphics_objects.append(vline)
```

This pattern follows the existing usage in [`pypho_timeline/core/pyqtgraph_time_synchronized_widget.py`](H:\TEMP\Spike3DEnv_ExploreUpgrade\Spike3DWorkEnv\pyPhoTimeline\pypho_timeline\core\pyqtgraph_time_synchronized_widget.py) (lines 449-450).

### Backward Compatibility