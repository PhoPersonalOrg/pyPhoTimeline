---
name: Implement LogTextDataFramePlotDetailRenderer
overview: Create a new `LogTextDataFramePlotDetailRenderer` class that inherits from `DataframePlotDetailRenderer` to render text log events as vertical text labels positioned at their time coordinates in the timeline plot.
todos: []
---

# Implement LogTextDataFramePlotDetailRenderer

## Overview

Create a new detail renderer for text log events that displays text messages as vertical labels at their time positions. This renderer will inherit from `DataframePlotDetailRenderer` and override the rendering logic to display text instead of numeric line plots.

## Implementation Details

### File Location

Create the new class in: [`pypho_timeline/rendering/detail_renderers/generic_plot_renderer.py`](pypho_timeline/rendering/detail_renderers/generic_plot_renderer.py)

### Class Structure

The `LogTextDataFramePlotDetailRenderer` class will:

1. **Inherit from `DataframePlotDetailRenderer`** to reuse common functionality
2. **Override `render_detail()`** to render text labels instead of line plots
3. **Override `get_detail_bounds()`** to handle text data appropriately
4. **Inherit `clear_detail()`** from parent (no changes needed)

### Data Format

- Expects DataFrame with columns: `['t', 'message']`
- `t`: float - time coordinate for each text event
- `message`: str - text content to display

### Rendering Implementation

1. **Text Label Rendering**:

- Use `pg.TextItem` from pyqtgraph to render each text message
- Position labels at their time coordinates (`t` values)
- Display text vertically (rotated 90 degrees) or horizontally based on configuration
- Use configurable text color and size

2. **Y-Position Strategy**:

- Since text logs don't have numeric y-values, distribute labels vertically
- Options:
    - Stack labels at fixed y-positions (0.0, 0.1, 0.2, etc.)
    - Use a single y-position (e.g., 0.5) for all labels
    - Auto-distribute based on available space

3. **Configuration Parameters**:

- `text_color`: Color for text labels (default: 'white' or 'cyan')
- `text_size`: Font size (default: 10)
- `text_rotation`: Rotation angle in degrees (default: 90 for vertical)
- `y_position`: Y-coordinate for text placement (default: 0.5)
- `anchor`: Text anchor point (default: (0, 0.5) for left-center)

### Methods to Override

#### `render_detail()`

- Validate DataFrame has `['t', 'message']` columns
- Sort by time
- Create `pg.TextItem` for each row
- Position each text item at `(t, y_position)`
- Add all text items to plot_item
- Return list of GraphicsObjects

#### `get_detail_bounds()`

- Extract time bounds from `detail_data['t'] `or `interval`
- Use fixed y-bounds (e.g., 0.0 to 1.0) since text doesn't have numeric y-values
- Return `(t_start, t_end, 0.0, 1.0)`

### Integration

1. **Export in `__init__.py`**:

- Add `LogTextDataFramePlotDetailRenderer` to [`pypho_timeline/rendering/detail_renderers/__init__.py`](pypho_timeline/rendering/detail_renderers/__init__.py)

2. **Update `__all__` in generic_plot_renderer.py**:

- Add `'LogTextDataFramePlotDetailRenderer'` to the `__all__` list

### Code Structure

```python
class LogTextDataFramePlotDetailRenderer(DataframePlotDetailRenderer):
    """Detail renderer for text log events that displays messages as text labels.
    
    Expects detail_data to be a DataFrame with columns ['t', 'message'].
    """
    
    def __init__(self, text_color='white', text_size=10, text_rotation=90, 
                 y_position=0.5, anchor=(0, 0.5)):
        # Initialize with minimal parent params (channel_names=None to skip line plotting)
        super().__init__(pen_width=1, channel_names=None, normalize=False)
        self.text_color = text_color
        self.text_size = text_size
        self.text_rotation = text_rotation
        self.y_position = y_position
        self.anchor = anchor
    
    def render_detail(self, plot_item, interval, detail_data):
        # Validate and process text data
        # Create TextItem for each message
        # Position at (t, y_position)
        # Return list of TextItems
    
    def get_detail_bounds(self, interval, detail_data):
        # Extract time bounds
        # Return (t_start, t_end, 0.0, 1.0)
```



### Testing Considerations

- Test with empty DataFrame
- Test with single text event
- Test with multiple text events at different times
- Test with missing 't' or 'message' columns
- Verify text labels appear at correct time positions
- Verify text is readable and properly rotated

## Files to Modify

1. [`pypho_timeline/rendering/detail_renderers/generic_plot_renderer.py`](pypho_timeline/rendering/detail_renderers/generic_plot_renderer.py)

- Add `LogTextDataFramePlotDetailRenderer` class
- Update `__all__` export list