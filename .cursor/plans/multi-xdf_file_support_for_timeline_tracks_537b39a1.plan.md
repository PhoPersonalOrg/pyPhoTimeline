---
name: Multi-XDF file support for timeline tracks
overview: Extend the timeline system to support loading data from multiple XDF files, merging streams by name across files while preserving absolute timestamps. Each track will aggregate data from all matching stream names across all loaded XDF files.
todos:
  - id: extend_timeline_builder
    content: Add build_from_xdf_files() method to TimelineBuilder that accepts List[Path] and processes multiple XDF files
    status: completed
  - id: create_stream_merger
    content: Create merge_streams_by_name() helper function to group streams by name across multiple XDF files
    status: completed
  - id: extend_stream_processor
    content: Create perform_process_all_streams_multi_xdf() function that processes streams from multiple files and merges by stream name
    status: completed
  - id: add_eeg_merging
    content: Add from_multiple_sources() class method to EEGTrackDatasource to merge data from multiple streams
    status: completed
  - id: add_motion_merging
    content: Add from_multiple_sources() class method to MotionTrackDatasource to merge data from multiple streams
    status: completed
  - id: add_position_merging
    content: Add from_multiple_sources() class method to PositionTrackDatasource to merge data from multiple streams
    status: completed
  - id: add_generic_merging
    content: Add from_multiple_sources() support to IntervalProvidingTrackDatasource for generic/log tracks
    status: completed
  - id: update_time_range_calc
    content: Ensure timeline time range calculations work correctly with merged datasources spanning multiple files
    status: completed
  - id: maintain_backward_compat
    content: Ensure build_from_xdf_file() continues to work and optionally uses new multi-file infrastructure internally
    status: completed
---

# Multi-XDF File Support Plan

## Current Architecture Analysis

The current implementation processes a single XDF file:

- `TimelineBuilder.build_from_xdf_file()` loads one XDF file via `pyxdf.load_xdf()`
- `perform_process_all_streams()` processes streams and creates one datasource per stream
- Each datasource contains data from a single stream in a single XDF file
- Tracks are created directly from datasources

## Design Decisions

Based on user requirements:

- **Merge Strategy**: Merge by stream name (e.g., all "Epoc X EEG" streams from different files → one track)
- **Time Synchronization**: Use absolute timestamps (preserve original timestamps from each file)

## Implementation Plan

### 1. Extend TimelineBuilder API

**File**: `pypho_timeline/timeline_builder.py`

- Add new method `build_from_xdf_files(xdf_file_paths: List[Path], ...)` that accepts multiple XDF file paths
- Keep existing `build_from_xdf_file()` for backward compatibility (can call new method internally)
- The new method should:
        - Load all XDF files
        - Process streams from all files
        - Merge streams by name across files
        - Build timeline from merged datasources

### 2. Extend Stream Processing

**File**: `pypho_timeline/widgets/simple_timeline_widget.py`

- Modify `perform_process_all_streams()` to accept an optional parameter indicating source file information
- Create a new function `perform_process_all_streams_multi_xdf(streams_list: List[List], xdf_file_paths: List[Path])` that:
        - Takes a list of stream lists (one per XDF file) and corresponding file paths
        - Groups streams by name across all files
        - For each unique stream name, collects all matching streams from all files
        - Creates merged datasources that aggregate data from multiple files

### 3. Enhance Datasources for Multi-File Support

**Files**:

- `pypho_timeline/rendering/datasources/specific/eeg.py`
- `pypho_timeline/rendering/datasources/specific/motion.py`
- `pypho_timeline/rendering/datasources/specific/position.py`
- `pypho_timeline/rendering/datasources/track_datasource.py`

Each datasource class needs to support merging data from multiple sources:

- **EEGTrackDatasource**: Merge multiple `eeg_df` DataFrames and `intervals_df` DataFrames
- **MotionTrackDatasource**: Merge multiple `motion_df` DataFrames and `intervals_df` DataFrames  
- **PositionTrackDatasource**: Merge multiple `position_df` DataFrames and `intervals_df` DataFrames
- **IntervalProvidingTrackDatasource**: Support merging `detailed_df` and `intervals_df` from multiple sources

**Approach**:

- Add a class method or factory function like `from_multiple_sources()` that:
        - Takes a list of (intervals_df, detailed_df) tuples
        - Concatenates DataFrames using `pd.concat()` with proper sorting
        - Preserves absolute timestamps (no time shifting)
        - Merges intervals appropriately
        - Handles duplicate/overlapping intervals if needed

### 4. Stream Merging Logic

**File**: `pypho_timeline/widgets/simple_timeline_widget.py`

Create helper function `merge_streams_by_name(streams_by_file: Dict[str, List]) -> Dict[str, List]`:

- Input: Dictionary mapping file paths to their stream lists
- Output: Dictionary mapping stream names to lists of streams (from different files)
- Groups streams by `stream['info']['name'][0]` across all files

### 5. Data Merging Implementation

For each track type, implement merging:

**EEG/Motion/Position tracks**:

```python
# Pseudo-code for merging
all_intervals = []
all_detailed_data = []

for stream in streams_with_same_name:
    intervals_df = create_intervals_from_stream(stream)
    detailed_df = create_detailed_df_from_stream(stream)
    all_intervals.append(intervals_df)
    all_detailed_data.append(detailed_df)

merged_intervals = pd.concat(all_intervals, ignore_index=True).sort_values('t_start')
merged_detailed = pd.concat(all_detailed_data, ignore_index=True).sort_values('t')
```

**Video tracks**: Video datasources are typically not from XDF files, but if they are, merge similarly.

**Log/Text tracks**: Merge similarly to EEG/Motion.

### 6. Time Range Calculation

**File**: `pypho_timeline/timeline_builder.py`

Update `build_from_datasources()` to handle merged datasources:

- `total_df_start_end_times` should span the earliest start to latest end across all merged data
- Window duration/start calculations should account for the full merged time range

### 7. Track Naming

**File**: `pypho_timeline/widgets/simple_timeline_widget.py`

- Keep existing naming: `{TYPE}_{stream_name}` (e.g., "EEG_Epoc X EEG")
- When multiple files contribute to the same stream name, the track name remains the same
- Optionally add metadata to track about source files (for debugging/info)

### 8. Backward Compatibility

- Keep `build_from_xdf_file()` unchanged (calls new method with single file)
- Keep `perform_process_all_streams()` signature compatible (can add optional parameters)
- Existing code using single XDF files should continue to work

## Implementation Details

### Key Functions to Modify/Create

1. **TimelineBuilder.build_from_xdf_files()** (new)

            - Accepts `List[Path] `instead of single `Path`
            - Loads all XDF files
            - Calls multi-file stream processor
            - Builds timeline from merged datasources

2. **perform_process_all_streams_multi_xdf()** (new)

            - Takes list of (streams, file_path) tuples
            - Groups streams by name
            - Creates merged datasources per stream name
            - Returns same format as current function

3. **Datasource.from_multiple_sources()** (new class methods)

            - Each datasource class gets a factory method
            - Merges intervals and detailed data
            - Creates single datasource instance

4. **merge_streams_by_name()** (new helper)

            - Groups streams across files by name
            - Returns organized structure for processing

### Data Flow

```
Multiple XDF Files
    ↓
Load all files (pyxdf.load_xdf for each)
    ↓
Group streams by name across files
    ↓
For each unique stream name:
 - Collect all matching streams
 - Extract intervals_df and detailed_df from each
 - Merge using pd.concat()
 - Create single datasource
    ↓
Build timeline from merged datasources
```

### Testing Considerations

- Test with 2+ XDF files containing same stream names
- Test with XDF files containing different stream names
- Test with overlapping vs non-overlapping time ranges
- Test backward compatibility with single XDF file
- Verify absolute timestamps are preserved
- Verify intervals are correctly merged

## Files to Modify

1. `pypho_timeline/timeline_builder.py` - Add `build_from_xdf_files()` method
2. `pypho_timeline/widgets/simple_timeline_widget.py` - Add multi-file stream processing
3. `pypho_timeline/rendering/datasources/specific/eeg.py` - Add merging support
4. `pypho_timeline/rendering/datasources/specific/motion.py` - Add merging support
5. `pypho_timeline/rendering/datasources/specific/position.py` - Add merging support
6. `pypho_timeline/rendering/datasources/track_datasource.py` - Add base merging utilities

## Migration Path

1. Implement new multi-file methods alongside existing single-file methods
2. Update `build_from_xdf_file()` to use new infrastructure internally
3. Add tests for multi-file scenarios
4. Update documentation/examples to show multi-file usage