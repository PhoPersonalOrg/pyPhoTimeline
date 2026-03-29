---
name: XDF discovery extraction
overview: Add a small `pypho_timeline` module that encapsulates `HistoricalData.get_recording_files` → optional `n_most_recent` slice → `build_file_comparison_df` → ordered `Path` list (plus optional CSV export). Refactor `TimelineBuilder._build_discovered_xdf_paths` and `main_offline_timeline.main()` to call it so discovery is reusable after a timeline exists and stays in sync with refresh.
todos:
  - id: add-xdf-session-discovery-module
    content: Add pypho_timeline/xdf_session_discovery.py with XdfDiscoveryResult dataclass, discover_* function, HistoricalData optional import, empty-dir handling, optional CSV export
    status: completed
  - id: delegate-timeline-builder
    content: Refactor TimelineBuilder._build_discovered_xdf_paths to call the new function
    status: completed
  - id: refactor-main-offline
    content: Replace main_offline_timeline discovery block with call to new function; keep CSV path/timestamp logic in main
    status: completed
isProject: false
---

# Extract XDF session discovery into a reusable function

## Current state

- `[main_offline_timeline.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/main_offline_timeline.py)` (lines 99–167) runs directory setup, `HistoricalData.get_recording_files`, slices with `n_most_recent_sessions_to_preprocess`, `HistoricalData.build_file_comparison_df`, optional CSV export, then builds `final_xdf_paths` from `src_file`.
- `[timeline_builder.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/timeline_builder.py)` already implements the **same** XDF path logic in private `_build_discovered_xdf_paths` (lines 176–187), used by `refresh_from_directories()` (line 221).

Duplication means any fix or behavior change must be edited in two places; the script cannot import the builder’s private method for a pure “discovery only” call.

## Proposed design

### 1. New module: `pypho_timeline/xdf_session_discovery.py`

- **Function** (name can be `discover_xdf_files_for_timeline` or similar): parameters aligned with current usage:
  - `xdf_discovery_dirs`: `Path | Sequence[Path]` → normalized `List[Path]`
  - `n_most_recent: Optional[int]` — `None` keeps all (same as `list[:None]`)
  - `recordings_extensions: Optional[List[str]]` — default `[".xdf"]`
  - `csv_export_path: Optional[Path]` — if set, `file_comparison_df.to_csv(csv_export_path)` (caller supplies timestamped filename, preserving current `[get_now_time_str](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/main_offline_timeline.py)` behavior)
  - Optional `verbose` / `print` flag only if you want to avoid adding `print` in the library; otherwise keep logging out of this helper unless you already use a module logger elsewhere.
- **Return value**: a small `@dataclass` (e.g. `XdfDiscoveryResult`) with at least:
  - `xdf_paths: List[Path]` — resolved from `file_comparison_df["src_file"]` as today
  - `file_comparison_df: pd.DataFrame` — full metadata for callers that need it
- **Dependencies**: mirror `[timeline_builder.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/timeline_builder.py)` — `try/except ImportError` for `HistoricalData`, and raise a clear `ImportError` when discovery runs without `phopymnehelper`.
- **Empty dirs**: if normalized dir list is empty, return empty paths and an empty DataFrame (or consistent empty structure) without calling `HistoricalData`, matching the spirit of `_build_discovered_xdf_paths` early-return.

### 2. Refactor `TimelineBuilder._build_discovered_xdf_paths`

- Replace the method body with a call to the new function and return `result.xdf_paths`.
- Keeps `refresh_from_directories()` behavior identical while fixing a single implementation site.

### 3. Refactor `main_offline_timeline.main()`

- Replace the inline block (roughly lines 134–167) with one call to the new function, passing:
  - discovery dirs: `[lab_recorder_output_path, pho_log_to_LSL_recordings_path]`
  - `n_most_recent=n_most_recent_sessions_to_preprocess`
  - `csv_export_path=xdf_file_cache_filepath` (still built with `get_now_time_str` + export directory as now)
- Use `result.xdf_paths` as `final_xdf_paths` for `build_from_xdf_files`.

### 4. Using discovery *after* a timeline exists

No new merge logic is strictly required for the extraction itself:

- **Compare**: `result = discover_xdf_files_for_timeline(...)` then diff `result.xdf_paths` against a `set` of paths you passed to `build_from_xdf_files` (or maintain yourself).
- **Apply updates**: Existing `[TimelineBuilder.refresh_from_directories()](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/timeline_builder.py)` already re-runs the same discovery (via `_build_discovered_xdf_paths`) and loads only **new** XDFs not in `_loaded_xdf_paths`, with stream allow/block lists from `set_refresh_config`. Ensure `set_refresh_config` is called at startup (already done in `main()` lines 179–180).

Optional follow-up (only if you want ergonomics): a public `TimelineBuilder` method that returns `XdfDiscoveryResult` using `_refresh_config` parameters, so callers do not re-plumb paths — not required for the stated “standalone function” goal.

## Files to touch


| File                                                                                                                                            | Change                                                                       |
| ----------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| New `[pypho_timeline/xdf_session_discovery.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/xdf_session_discovery.py)` | Dataclass + discovery function                                               |
| `[pypho_timeline/timeline_builder.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/timeline_builder.py)`               | `_build_discovered_xdf_paths` delegates to new module                        |
| `[main_offline_timeline.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/main_offline_timeline.py)`                                   | Replace duplicated block with single call; docstring can mention the new API |


## Out of scope (unless you ask)

- Exporting the new symbol from package `__all__` in `[pypho_timeline/__init__.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/__init__.py)` (can import from `pypho_timeline.xdf_session_discovery` directly).
- Changing refresh semantics (e.g. reloading dropped files or handling `n_most_recent` shrinking the window) — extraction preserves current behavior.

