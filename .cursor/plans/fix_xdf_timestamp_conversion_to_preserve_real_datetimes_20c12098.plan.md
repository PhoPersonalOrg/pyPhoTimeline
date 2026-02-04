---
name: Fix XDF timestamp conversion to preserve real datetimes
overview: Fix timestamp conversion in XDF file processing so that each file's relative timestamps are converted to absolute datetimes using that file's reference, then normalized to a common reference (earliest file's reference) to ensure all datasources display correct absolute datetimes on the timeline.
todos:
  - id: update-imports
    content: Update imports in simple_timeline_widget.py to include datetime_to_float and get_reference_datetime_from_xdf_header
    status: pending
  - id: modify-function-signature
    content: Add file_headers parameter to perform_process_all_streams_multi_xdf function signature
    status: pending
  - id: extract-reference-datetimes
    content: Extract reference datetime from each file header and find earliest reference
    status: pending
  - id: convert-timestamps
    content: Convert each file's relative timestamps to absolute, then to relative using earliest reference
    status: pending
  - id: update-call-site
    content: Update timeline_builder.py to pass file_headers to perform_process_all_streams_multi_xdf
    status: pending
isProject: false
---

# Fix XDF Timestamp Conversion to Preserve Real Datetimes

## Problem

XDF files contain timestamps that are relative to each file's recording start time. When multiple XDF files are loaded, their timestamps are not being converted to use a common reference datetime, causing misalignment on the timeline. Each file has its own reference datetime in the header, but timestamps are being used as-is without proper conversion.

## Solution

Convert each file's relative timestamps to absolute datetimes using that file's reference datetime, then normalize all timestamps to use the earliest reference datetime as the common reference. This ensures:

- All datasources display correct absolute datetimes
- Timestamps are properly aligned across multiple files
- The internal float-based system (relative to reference) is preserved

## Changes Required

### 1. Update imports in `simple_timeline_widget.py`

- **File**: `pypho_timeline/widgets/simple_timeline_widget.py`
- Add `datetime_to_float` and `get_reference_datetime_from_xdf_header` to the imports from `datetime_helpers`
- **Location**: Line 16

### 2. Modify `perform_process_all_streams_multi_xdf` function

- **File**: `pypho_timeline/widgets/simple_timeline_widget.py`
- **Location**: Lines 421-610
- **Changes**:
  - Add `file_headers: Optional[List[dict]] = None` parameter to function signature
  - Extract reference datetime from each file header before processing streams
  - Find the earliest reference datetime across all files (this becomes the common reference)
  - For each stream, convert relative timestamps to absolute datetimes using that file's reference
  - Convert absolute datetimes back to relative timestamps using the earliest reference
  - Apply converted timestamps to both `intervals_df` and `time_series_df`
  - Add logging to show which reference datetime is being used

### 3. Update call site in `timeline_builder.py`

- **File**: `pypho_timeline/timeline_builder.py`
- **Location**: Line 151
- **Change**: Pass `file_headers=all_file_headers` to `perform_process_all_streams_multi_xdf`

## Implementation Details

### Timestamp Conversion Flow

1. For each XDF file, extract reference datetime from header using `get_reference_datetime_from_xdf_header()`
2. Find the earliest reference datetime across all files
3. For each stream in each file:

   - Get relative timestamps from stream (relative to that file's start)
   - Convert to absolute datetimes: `float_to_datetime(timestamp, file_reference_datetime)`
   - Convert back to relative timestamps: `datetime_to_float(absolute_datetime, earliest_reference_datetime)`

4. Store normalized timestamps in datasources (still as floats, but now relative to common reference)
5. Display uses `earliest_reference_datetime` to convert back to absolute datetimes for display

### Key Code Pattern

```python
# Extract reference datetimes
file_reference_datetimes = {}
for file_header, file_path in zip(file_headers, xdf_file_paths):
    ref_dt = get_reference_datetime_from_xdf_header(file_header)
    if ref_dt is not None:
        file_reference_datetimes[file_path] = ref_dt

# Find earliest reference
earliest_reference_datetime = min(file_reference_datetimes.values())

# Convert timestamps for each stream
file_ref_dt = file_reference_datetimes.get(file_path)
if file_ref_dt is not None and earliest_reference_datetime is not None:
    timestamps_absolute = [float_to_datetime(float(ts), file_ref_dt) for ts in timestamps]
    timestamps = np.array([datetime_to_float(dt, earliest_reference_datetime) for dt in timestamps_absolute])
```

## Benefits

- All datasources use the same reference datetime internally
- Timestamps are properly aligned across multiple XDF files
- Real absolute datetimes are preserved and displayed correctly
- Backward compatible with existing float-based timestamp system
- No changes needed to datasource classes or display code

## Testing

After implementation, verify:

- Multiple XDF files with different recording start times align correctly
- Timeline displays show correct absolute datetimes
- All tracks appear at their correct absolute time positions
- No timestamp misalignment between tracks from different files