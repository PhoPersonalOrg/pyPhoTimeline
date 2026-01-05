---
name: Generalize DataframePlotDetailRenderer
overview: Make DataframePlotDetailRenderer more flexible by adding optional normalization, auto-detection of channels, and improved error handling while maintaining backward compatibility.
todos: []
---

# Generalize DataframePlotDetailRenderer

## Overview

Generalize `DataframePlotDetailRenderer` in [`pyPhoTimeline/pypho_timeline/rendering/detail_renderers/generic_plot_renderer.py`](pyPhoTimeline/pypho_timeline/rendering/detail_renderers/generic_plot_renderer.py) to be more flexible and reusable. The renderer currently has hard-coded assumptions that limit its generality.

## Current Issues

1. **Hard assertion** (lines 293-294): Requires ALL channels in `channel_names` to exist in the DataFrame
2. **No auto-detection**: Cannot automatically detect channels from DataFrame columns
3. **Always normalizes**: No option to disable normalization (currently always normalizes to 0-1)
4. **EEG-specific documentation**: Docstrings contain EEG-specific examples instead of generic examples
5. **Inconsistent defaults**: Default `channel_names=['x', 'y', 'z']` doesn't match docstring examples

## Changes Required

### 1. Add Optional Normalization Parameter

- Add `normalize: bool = True` parameter to `__init__` method (line 216)
- Make normalization conditional in `render_detail` method (lines 295-302)
- When `normalize=False`, plot raw channel values (similar to `MotionPlotDetailRenderer`)

### 2. Add Auto-Detection of Channels

- When `channel_names=None`, automatically detect all numeric columns except 't'
- Update `__init__` to handle `channel_names: Optional[List[str]] = None`
- In `render_detail`, if `channel_names is None`, auto-detect from DataFrame columns
- Generate colors for auto-detected channels

### 3. Improve Error Handling

- Keep assertion for "all channels required" only when `channel_names` is explicitly provided
- When auto-detecting, handle empty channel list gracefully
- Add informative error messages

### 4. Update Documentation

- Remove EEG-specific references from docstrings
- Update usage examples to be generic
- Fix inconsistency between default `channel_names=['x', 'y', 'z']` and docstring examples
- Clarify normalization behavior in docstrings

### 5. Update Method Signatures

- Update `__init__` signature: `def **init**(self, pen_width=2, channel_names: Optional[List[str]]=None, pen_colors=None, pen_color='cyan', normalize: bool = True)`
- Update type hints to use `Optional[List[str]] `for `channel_names`

### 6. Update `get_detail_bounds` Method

- Handle auto-detected channels case (when `channel_names is None`)
- Ensure bounds calculation works with both normalized and raw values

## Implementation Details

### Auto-Detection Logic

```python
if channel_names is None:
    # Auto-detect: all numeric columns except 't'
    numeric_cols = detail_data.select_dtypes(include=[np.number]).columns.tolist()
    channel_names = [col for col in numeric_cols if col != 't']
```



### Normalization Logic

```python
if self.normalize:
    # Normalize to 0-1 range (current behavior)
    channel_df = df_sorted[found_channel_names].astype(float)
    min_vals = channel_df.min(skipna=True)
    max_vals = channel_df.max(skipna=True)
    ranges = max_vals - min_vals
    ranges = ranges.replace(0, 1).fillna(1)
    normalized_channel_df = (channel_df - min_vals) / ranges
    y_values = normalized_channel_df[a_found_channel_name].values
else:
    # Use raw values
    y_values = df_sorted[a_found_channel_name].values
```



### Assertion Logic

```python
# Only assert all channels required when channel_names was explicitly provided
if self.channel_names is not None:  # Explicitly provided
    found_all_channel_names: bool = len(found_channel_names) == len(self.channel_names)
    assert found_all_channel_names, f"Missing channels: {set(self.channel_names) - set(found_channel_names)}"
```



## Files to Modify

- [`pyPhoTimeline/pypho_timeline/rendering/detail_renderers/generic_plot_renderer.py`](pyPhoTimeline/pypho_timeline/rendering/detail_renderers/generic_plot_renderer.py) (lines 203-404)

## Backward Compatibility