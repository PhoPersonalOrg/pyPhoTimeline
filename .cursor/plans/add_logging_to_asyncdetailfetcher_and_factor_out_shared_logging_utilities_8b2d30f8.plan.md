---
name: Add logging to AsyncDetailFetcher and factor out shared logging utilities
overview: Add comprehensive debug logging to AsyncDetailFetcher (similar to TrackRenderer) and create a shared logging utility module to eliminate code duplication and ensure consistent logging configuration across rendering components.
todos: []
---

# Add Logging to AsyncDetailFetcher and Factor Out Shared Logging Utilities

## Overview

Add robust debug logging to `AsyncDetailFetcher` and `DetailFetchWorker` to track the complete lifecycle of async detail fetching. Factor out common logging configuration code into a shared utility module to promote reuse and ensure consistent logging behavior across rendering components.

## Implementation Details

### Files to Create

1. **`pypho_timeline/utils/logging_util.py`** (NEW)

- Shared logging configuration utility
- Common formatter, handler setup
- Reusable configuration function

### Files to Modify

1. **`pypho_timeline/rendering/async_detail_fetcher.py`**

- Add comprehensive logging throughout
- Use shared logging utility
- Log worker lifecycle, fetch operations, cache operations

2. **`pypho_timeline/rendering/graphics/track_renderer.py`**

- Refactor to use shared logging utility
- Remove duplicate logging configuration code

3. **`pypho_timeline/utils/__init__.py`**

- Export new logging utility functions

4. **`pypho_timeline/__main__.py`**

- Update to use shared logging configuration

## Detailed Changes

### 1. Create Shared Logging Utility (`utils/logging_util.py`)

Create a new utility module with:

- **`configure_rendering_logging()`** function:
- Parameters: `log_level`, `log_file`, `log_to_console`, `log_to_file`, `logger_name` (optional)
- Default log file: `timeline_rendering.log` (shared across all rendering components)
- Sets up both console and file handlers with rotation
- Returns configured logger
- Prevents duplicate handlers
- **`get_rendering_logger()`** function:
- Returns a logger for a given module name
- Uses consistent naming convention: `pypho_timeline.rendering.*`
- **Shared formatter**:
- Consistent format: `'%(asctime)s - %(name)s - %(levelname)s - %(message)s'`
- Date format: `'%Y-%m-%d %H:%M:%S'`
- **File handler defaults**:
- RotatingFileHandler with 10MB max, 5 backups
- Default file: `timeline_rendering.log` in current directory

### 2. Add Logging to AsyncDetailFetcher

#### DetailFetchWorker class:

- **`__init__`**: Log worker creation with track_id, cache_key
- **`cancel()`**: Log cancellation
- **`is_cancelled()`**: Log cancellation checks (debug level)
- **`run()`**: 
- Log start of fetch operation
- Log cancellation checks
- Log call to `fetch_detailed_data()`
- Log data type/size returned
- Log callback scheduling
- Log errors with full exception info
- Log completion status

#### AsyncDetailFetcher class:

- **`__init__`**: Log initialization with max_cache_size, thread pool config
- **`fetch_detail_async()`**:
- Log fetch request (track_id, cache_key)
- Log cache hits (with cache_key)
- Log cache misses
- Log duplicate fetch detection
- Log worker creation and thread pool submission
- Log thread pool stats (active threads)
- **`_on_detail_fetched()`**: 
- Log when data is fetched
- Log cache storage
- Log cache eviction
- **`cancel_pending_fetches()`**: 
- Log cancellation requests
- Log number of workers cancelled
- **`cancel_all_pending_fetches()`**: 
- Log bulk cancellation
- **`get_cached_data()`**: 
- Log cache lookups (hits/misses)
- **`clear_cache()`**: 
- Log cache clearing operations
- **`get_cache_stats()`**: 
- Log cache statistics when requested

### 3. Refactor TrackRenderer Logging

- Replace `configure_track_renderer_logging()` with call to shared `configure_rendering_logging()`
- Update logger initialization to use `get_rendering_logger()`
- Ensure consistent log file location

### 4. Update Logging Configuration in `__main__.py`

- Replace track_renderer-specific logging config with shared utility
- Configure once for all rendering components
- Use default shared log file: `timeline_rendering.log`

## Logging Levels

- **DEBUG**: Detailed flow information (worker lifecycle, cache operations, fetch steps)
- **INFO**: Important state changes (initialization, major operations)
- **WARNING**: Unexpected but recoverable conditions (cancelled workers, cache misses)
- **ERROR**: Actual errors (fetch failures, exceptions)

## Log Message Format

All messages should include:

- Component identifier (track_id, cache_key)
- Operation being performed
- Relevant context (data sizes, thread counts, cache stats)
- Error details with full stack traces where appropriate

## Benefits

1. **Code Reuse**: Single source of truth for logging configuration
2. **Consistency**: All rendering components log to same file with same format
3. **Maintainability**: Changes to logging behavior only need to be made in one place
4. **Debugging**: Comprehensive visibility into async fetch pipeline
5. **Performance Monitoring**: Can track cache hit rates, fetch times, thread pool usage

## Testing Considerations

After implementation, logs should reveal:

- Whether workers are being created and started
- Whether `fetch_detailed_data()` is being called