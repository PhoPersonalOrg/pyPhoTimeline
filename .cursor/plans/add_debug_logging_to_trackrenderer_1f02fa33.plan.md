---
name: Add debug logging to TrackRenderer
overview: Add comprehensive debug logging to TrackRenderer class to help diagnose why detailed views aren't dynamically updating. Logging will track viewport updates, interval visibility changes, cache operations, async fetch lifecycle, rendering operations, and error conditions.
todos: []
---

# Add Debug Logging to TrackRenderer

## Overview

Add robust debug logging throughout the `TrackRenderer` class to track the complete lifecycle of detail view updates. This will help diagnose issues with dynamic detail view updates by logging all state changes, operations, and data flows.

## Implementation Details

### File to Modify

- [`pypho_timeline/rendering/graphics/track_renderer.py`](pypho_timeline/rendering/graphics/track_renderer.py)

### Changes Required

1. **Add logging import and logger setup** (at top of file, after imports):

- Import Python's `logging` module
- Create a module-level logger: `logger = logging.getLogger(__name__)`
- This follows Python logging best practices

2. **Add logging to `__init__` method** (line 26-55):

- Log track initialization with track_id, datasource info
- Log detail_renderer type/availability
- Log async_fetcher connection status

3. **Add logging to `_update_overview` method** (line 58-82):

- Log when overview update starts
- Log number of intervals in overview
- Log overview item creation/removal
- Log any errors during overview update

4. **Add comprehensive logging to `update_viewport` method** (line 85-127):

- Log viewport change with start/end times
- Log number of intervals found in viewport
- Log which intervals are new vs. already visible
- Log cache hits (with cache_key)
- Log cache misses and async fetch requests (with cache_key)
- Log intervals leaving viewport (with cache_keys)
- Log cancellation requests
- Log final visible_intervals count

5. **Add logging to `_on_detail_data_ready` method** (line 130-151):

- Log when detail data arrives (track_id, cache_key)
- Log if data is for wrong track (early return)
- Log errors from async fetch
- Log if interval is still visible when data arrives
- Log if interval left viewport before data arrived (skipped render)
- Log successful rendering trigger

6. **Add logging to `_render_detail` method** (line 154-172):

- Log rendering start (cache_key, interval info)
- Log if clearing existing detail first
- Log detail_renderer type
- Log number of graphics objects created
- Log any errors during rendering

7. **Add logging to `_clear_detail` method** (line 175-184):

- Log clearing start (cache_key)
- Log number of graphics objects being cleared
- Log if cache_key not found in detail_graphics

8. **Add logging to `clear_all_details` method** (line 187-191):

- Log clearing all details
- Log number of intervals being cleared
- Log visible_intervals set clearing

9. **Add logging to `remove` method** (line 194-208):

- Log track removal start
- Log cleanup operations (details, overview, signal disconnection)

### Logging Levels and Format

- Use `logger.debug()` for detailed flow information (viewport changes, cache operations, rendering steps)
- Use `logger.info()` for important state changes (track added/removed, major operations)
- Use `logger.warning()` for unexpected but recoverable conditions (interval left viewport before data arrived)
- Use `logger.error()` for actual errors (rendering failures, fetch errors)

### Log Message Format

Include relevant context in log messages:

- Track ID for all messages
- Cache keys for interval-specific operations
- Viewport ranges for viewport updates
- Counts/sizes for collections
- Interval time ranges (t_start, t_duration) where relevant

### Example Log Messages

```javascript
DEBUG: TrackRenderer[track_id] Initialized with datasource type=X, detail_renderer=Y
DEBUG: TrackRenderer[track_id] update_viewport(start=100.0, end=200.0) - found 5 intervals
DEBUG: TrackRenderer[track_id] Interval cache_key='X' - cache HIT, rendering immediately
DEBUG: TrackRenderer[track_id] Interval cache_key='Y' - cache MISS, requesting async fetch
DEBUG: TrackRenderer[track_id] Interval cache_key='Z' - leaving viewport, clearing detail
DEBUG: TrackRenderer[track_id] Detail data ready for cache_key='Y' - rendering
DEBUG: TrackRenderer[track_id] Rendered detail for cache_key='Y' - created 3 graphics objects
WARNING: TrackRenderer[track_id] Detail data arrived for cache_key='X' but interval no longer visible
```



### Testing Considerations

After implementation, the logs should reveal:

- Whether viewport updates are being called
- Whether intervals are being detected correctly
- Whether cache is working (hits vs misses)
- Whether async fetches are being requested
- Whether detail data is arriving