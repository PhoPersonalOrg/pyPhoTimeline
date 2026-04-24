---
name: parallelize-xdf-loading
overview: Parallelize XDF file loading and per-file stream filtering in `TimelineBuilder.build_from_xdf_files` while preserving existing behavior, ordering, and error handling semantics.
todos:
  - id: add-parallel-load-helper
    content: Add private per-file XDF load+filter helper in `timeline_builder.py` returning indexed result metadata.
    status: completed
  - id: replace-sequential-loop
    content: Replace sequential `for xdf_file_path in xdf_file_paths` loop with bounded `ThreadPoolExecutor` flow and ordered result reconstruction.
    status: completed
  - id: preserve-logging-and-errors
    content: Keep equivalent logging and skip-on-failure semantics for per-file errors without aborting the overall batch.
    status: completed
  - id: validate-behavior
    content: Verify output list alignment/order and run lints on `timeline_builder.py`.
    status: completed
isProject: false
---

# Parallelize XDF Load + Filter

## Goal
Replace the sequential XDF loading loop in [`C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/timeline_builder.py`](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/timeline_builder.py) with a bounded parallel implementation that performs both `pyxdf.load_xdf(...)` and stream allow/block filtering per file concurrently.

## Why this shape
The downstream call `perform_process_all_streams_multi_xdf(...)` expects aligned positional lists (`streams_list`, `xdf_file_paths`, `file_headers`). The implementation must therefore:
- preserve input ordering among successful loads
- skip failed loads consistently across all three lists
- keep filtering semantics unchanged

Essential current flow:

```381:419:C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/timeline_builder.py
# Load all XDF files
all_streams_by_file = []
all_file_headers = []
all_loaded_xdf_file_paths = []

for xdf_file_path in xdf_file_paths:
    ...
    streams, file_header = pyxdf.load_xdf(str(xdf_file_path))
    ...
    if (stream_allowlist is not None) or (stream_blocklist is not None):
        streams = self._filter_streams_by_name(...)
    all_streams_by_file.append(streams)
    all_file_headers.append(file_header)
    all_loaded_xdf_file_paths.append(xdf_file_path)
```

## Implementation steps
1. Add a small private helper in `TimelineBuilder` (same file) that loads and filters one file, returning a structured tuple/dict with:
   - input index
   - `xdf_file_path`
   - `streams`
   - `file_header`
   - optional error object/message
2. Use `concurrent.futures.ThreadPoolExecutor` + `as_completed` in `build_from_xdf_files` to submit one worker per file with bounded worker count (`min(len(xdf_file_paths), os.cpu_count() or 4)`), tuned for I/O-heavy disk reads.
3. Keep logging for each file load attempt, success, and failure; include file path and resulting stream names after load/filter.
4. Reassemble successful results in original input order (using stored index) before populating:
   - `all_streams_by_file`
   - `all_file_headers`
   - `all_loaded_xdf_file_paths`
5. Preserve existing skip-on-error behavior (`OSError`, `FileExistsError`, `FileNotFoundError`) and make worker-level exception handling consistent so one file failure does not abort the full batch.
6. Leave all downstream processing untouched (`perform_process_all_streams_multi_xdf`, timeline assembly, title generation, datetime extraction).

## Validation
- Run the existing XDF load path with multiple files and verify:
  - no regression in merged stream output
  - identical behavior when one file fails
  - allowlist/blocklist still applied per file
  - output order remains deterministic by original `xdf_file_paths` input order
- Run lint diagnostics for edited file and resolve any new issues.
