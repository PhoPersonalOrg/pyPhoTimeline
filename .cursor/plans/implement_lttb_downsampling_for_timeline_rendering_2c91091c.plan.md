---
name: Implement LTTB Downsampling for Timeline Rendering
overview: Add efficient downsampling using LTTB (Largest-Triangle-Three-Buckets) algorithm in fetch_detailed_data() methods to reduce rendering load while preserving visual features. The downsampling will be based on interval duration with configurable points-per-second rate.
todos:
  - id: create_downsampling_utils
    content: Create pypho_timeline/utils/downsampling.py with LTTB algorithm and downsample_dataframe() function
    status: completed
  - id: modify_base_datasource
    content: Add downsampling parameters to IntervalProvidingTrackDatasource and implement in fetch_detailed_data()
    status: completed
    dependencies:
      - create_downsampling_utils
  - id: update_eeg_datasource
    content: Update EEGTrackDatasource.fetch_detailed_data() to use downsampling if needed
    status: completed
    dependencies:
      - modify_base_datasource
  - id: update_stream_processing
    content: Update perform_process_all_streams() to configure downsampling rates per stream type
    status: completed
    dependencies:
      - modify_base_datasource
  - id: test_downsampling
    content: Test downsampling with various interval durations and verify visual quality
    status: completed
    dependencies:
      - create_downsampling_utils
      - modify_base_datasource
---

# Implement LTTB Downsampling for Timeline Rendering

## Overview

Add efficient downsampling to reduce the number of data points rendered while preserving visual features. Downsampling will occur in `fetch_detailed_data()` methods (background thread) using the LTTB algorithm, with configurable points-per-second rate.

## Architecture

Data flow:

```javascript
fetch_detailed_data(interval) → downsample_dataframe() → cached downsampled data → render_detail()
```

The downsampling happens in the worker thread before caching, so:

- UI thread is not blocked
- Cached data is already optimized
- Less memory usage

## Implementation Steps

### 1. Create Downsampling Utility Module

**File:** `pypho_timeline/utils/downsampling.py` (new file)Create a utility module with:

- `downsample_dataframe()` function that:
- Takes DataFrame with 't' column and channel columns
- Uses LTTB algorithm for time-series downsampling
- Preserves all non-time columns
- Returns downsampled DataFrame
- `lttb_downsample()` function implementing LTTB algorithm
- Configurable `max_points_per_second` parameter (default: 1000-2000)

**LTTB Algorithm:**

- Divides data into buckets
- For each bucket, selects point that forms largest triangle with previous and next bucket
- Preserves visual features better than simple decimation

### 2. Modify BaseTrackDatasource.fetch_detailed_data()

**File:** `pypho_timeline/rendering/datasources/track_datasource.py`Add optional downsampling parameter to `IntervalProvidingTrackDatasource.__init__()`:

- `max_points_per_second: Optional[float] = 1000.0` - If None, no downsampling
- `enable_downsampling: bool = True` - Toggle downsampling on/off

Modify `fetch_detailed_data()` to:

- Calculate target point count: `max_points = int(interval['t_duration'] * max_points_per_second)`
- If data has more points than target, call `downsample_dataframe()`
- Return downsampled DataFrame

### 3. Update Specific Datasources

**Files to modify:**

- `pypho_timeline/rendering/datasources/specific/eeg.py` - `EEGTrackDatasource.fetch_detailed_data()`
- `pypho_timeline/rendering/datasources/modality_datasources.py` - Motion datasources if they override `fetch_detailed_data()`

Ensure all datasources that return DataFrames with 't' column benefit from downsampling.

### 4. Update perform_process_all_streams()

**File:** `pypho_timeline/widgets/simple_timeline_widget.py`When creating datasources (lines 420-467), optionally pass `max_points_per_second` parameter:

- For high-frequency data (EEG, Motion): 1000-2000 points/second
- For lower-frequency data: higher rate or None

## Technical Details

### LTTB Implementation

- Time complexity: O(n) where n is number of buckets
- Space complexity: O(n) for output
- Works best with sorted time-series data

### Downsampling Logic

```python
def downsample_dataframe(df: pd.DataFrame, max_points: int, time_col: str = 't') -> pd.DataFrame:
    if len(df) <= max_points:
        return df  # No downsampling needed
    
    # Sort by time
    df_sorted = df.sort_values(time_col)
    
    # Apply LTTB to each channel column
    # Preserve all non-time columns
    ...
```



### Points-per-Second Calculation

- Default: 1000 points/second
- For 1-second interval: max 1000 points
- For 10-second interval: max 10,000 points
- For 0.1-second interval: max 100 points

This ensures:

- Long intervals don't overwhelm renderer
- Short intervals maintain detail
- Configurable per datasource type

## Benefits

1. **Performance**: Reduces rendering time for large datasets
2. **Memory**: Less data cached and passed around
3. **Visual Quality**: LTTB preserves important features
4. **Flexibility**: Configurable per datasource
5. **Non-blocking**: Happens in worker thread

## Testing Considerations

- Verify downsampling preserves visual features
- Test with various interval durations