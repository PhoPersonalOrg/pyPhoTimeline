---
name: Convert interval Series to DataFrame in DetailRenderer
overview: "Convert all `interval: pd.Series` type annotations to `interval: pd.DataFrame` in the `DetailRenderer` protocol and all its implementation classes, and update all interval access patterns to work with DataFrames."
todos:
  - id: "1"
    content: "Update DetailRenderer protocol in track_datasource.py: change interval parameter types in render_detail() and get_detail_bounds() methods"
    status: completed
  - id: "2"
    content: "Update GenericPlotDetailRenderer: change interval types and update _default_bounds() access patterns"
    status: completed
    dependencies:
      - "1"
  - id: "3"
    content: "Update IntervalPlotDetailRenderer: change interval types and update all interval.get() calls"
    status: completed
    dependencies:
      - "1"
  - id: "4"
    content: "Update MotionPlotDetailRenderer: change interval types and update interval access in get_detail_bounds()"
    status: completed
    dependencies:
      - "1"
  - id: "5"
    content: "Update PositionPlotDetailRenderer: change interval types and update interval.get() calls"
    status: completed
    dependencies:
      - "1"
  - id: "6"
    content: "Update VideoThumbnailDetailRenderer: change interval types and update all interval access patterns"
    status: completed
    dependencies:
      - "1"
  - id: "7"
    content: "Update TrackRenderer: change interval types in _render_detail() and _on_detail_data_ready(), and convert Series to DataFrame in update_viewport()"
    status: completed
    dependencies:
      - "1"
      - "2"
      - "3"
      - "4"
      - "5"
      - "6"
  - id: "8"
    content: "Update AsyncDetailFetcher: change interval types in DetailFetchWorker, fetch_detail_async(), and signal definition"
    status: completed
    dependencies:
      - "1"
---

# Convert interval Series to DataFrame in DetailRenderer

## Overview

Convert all `interval: pd.Series` parameters to `interval: pd.DataFrame` in the `DetailRenderer` protocol and all implementation classes. This requires updating type annotations, docstrings, and all interval value access patterns throughout the codebase.

## Files to Modify

### 1. Protocol Definition

- **[pypho_timeline/rendering/datasources/track_datasource.py](pypho_timeline/rendering/datasources/track_datasource.py)**
- Update `DetailRenderer` protocol methods:
    - `render_detail(interval: pd.Series, ...)` → `render_detail(interval: pd.DataFrame, ...)`
    - `get_detail_bounds(interval: pd.Series, ...)` → `get_detail_bounds(interval: pd.DataFrame, ...)`
- Update docstrings to reflect DataFrame instead of Series

### 2. Detail Renderer Implementations

#### 2.1 Generic Plot Renderer

- **[pypho_timeline/rendering/detail_renderers/generic_plot_renderer.py](pypho_timeline/rendering/detail_renderers/generic_plot_renderer.py)**
- `GenericPlotDetailRenderer.render_detail()`: Change parameter type and update `_default_bounds()` helper
- `GenericPlotDetailRenderer.get_detail_bounds()`: Change parameter type
- `GenericPlotDetailRenderer._default_bounds()`: Change parameter type and update access patterns:
    - `interval.get('t_start', 0.0)` → `interval['t_start'].iloc[0] if len(interval) > 0 else 0.0 `(or use `.get()` with fallback)
    - Similar updates for `t_duration`, `series_vertical_offset`, `series_height`
- `IntervalPlotDetailRenderer.render_detail()`: Change parameter type
- `IntervalPlotDetailRenderer.get_detail_bounds()`: Change parameter type and update all `interval.get()` calls

#### 2.2 Motion Plot Renderer

- **[pypho_timeline/rendering/detail_renderers/motion_plot_renderer.py](pypho_timeline/rendering/detail_renderers/motion_plot_renderer.py)**
- `MotionPlotDetailRenderer.render_detail()`: Change parameter type
- `MotionPlotDetailRenderer.get_detail_bounds()`: Change parameter type and update interval access:
    - Handle `interval is None` case (already present)
    - Update `interval.get('t_start', ...)` calls to DataFrame access

#### 2.3 Position Plot Renderer

- **[pypho_timeline/rendering/detail_renderers/position_plot_renderer.py](pypho_timeline/rendering/detail_renderers/position_plot_renderer.py)**
- `PositionPlotDetailRenderer.render_detail()`: Change parameter type
- `PositionPlotDetailRenderer.get_detail_bounds()`: Change parameter type and update all `interval.get()` calls

#### 2.4 Video Thumbnail Renderer

- **[pypho_timeline/rendering/detail_renderers/video_thumbnail_renderer.py](pypho_timeline/rendering/detail_renderers/video_thumbnail_renderer.py)**
- `VideoThumbnailDetailRenderer.render_detail()`: Change parameter type and update:
    - `interval.get('t_start', 0.0)` → DataFrame access
    - `interval.get('series_vertical_offset', ...)` → DataFrame access
    - `interval.get('series_height', ...)` → DataFrame access
- `VideoThumbnailDetailRenderer.get_detail_bounds()`: Change parameter type and update interval access

### 3. Supporting Code Updates (Required for Functionality)

#### 3.1 Track Renderer

- **[pypho_timeline/rendering/graphics/track_renderer.py](pypho_timeline/rendering/graphics/track_renderer.py)**
- `_render_detail(interval: pd.Series, ...)`: Change to `interval: pd.DataFrame`
- `_on_detail_data_ready(..., interval: pd.Series, ...)`: Change to `interval: pd.DataFrame`
- `update_viewport()`: When calling `_render_detail()`, convert Series from `iterrows()` to DataFrame:
    - Change `for _, interval in intervals_df.iterrows():` to pass `intervals_df.iloc[[idx]]` or create single-row DataFrame

#### 3.2 Async Detail Fetcher

- **[pypho_timeline/rendering/async_detail_fetcher.py](pypho_timeline/rendering/async_detail_fetcher.py)**
- `DetailFetchWorker.__init__(interval: pd.Series, ...)`: Change to `interval: pd.DataFrame`
- `fetch_detail_async(interval: pd.Series, ...)`: Change to `interval: pd.DataFrame`
- `detail_data_ready` signal: Change `pd.Series` to `pd.DataFrame` in signal definition
- `_on_detail_fetched(interval: pd.Series, ...)`: Change to `interval: pd.DataFrame`

## Implementation Details

### Interval Access Pattern Changes

**Current (Series):**

```python
t_start = interval.get('t_start', 0.0)
t_duration = interval.get('t_duration', 1.0)
y_offset = interval.get('series_vertical_offset', 0.0)
```

**New (DataFrame - single row expected):**

```python
# Option 1: Direct access with iloc (assumes single row)
t_start = interval['t_start'].iloc[0] if len(interval) > 0 and 't_start' in interval.columns else 0.0
t_duration = interval['t_duration'].iloc[0] if len(interval) > 0 and 't_duration' in interval.columns else 1.0

# Option 2: Helper function for cleaner code
def get_interval_value(df: pd.DataFrame, col: str, default: Any) -> Any:
    if len(df) == 0 or col not in df.columns:
        return default
    return df[col].iloc[0]

t_start = get_interval_value(interval, 't_start', 0.0)
```

**Note:** Since intervals are expected to be single-row DataFrames, we can use `.iloc[0]` after checking the DataFrame is not empty.

### Null/None Handling

Some implementations (e.g., `MotionPlotDetailRenderer.get_detail_bounds()`) already handle `interval is None`. These should continue to work, but may need updates if the calling code changes how None is passed.

## Testing Considerations

- Verify that single-row DataFrames work correctly with all renderers
- Ensure backward compatibility if any code still passes Series (may need conversion helper)
- Test edge cases: empty DataFrames, missing columns, None intervals

## Notes

- The `TrackDatasource` protocol methods (`fetch_detailed_data`, `get_detail_cache_key`) also use `pd.Series` but are outside the scope of this change