---
name: unix detail timestamps
overview: Standardize `pypho_timeline` internal detailed timestamps on Unix-second floats, remove datetime-based slicing/rendering paths, and keep datetime usage only at ingest/display boundaries to eliminate the current offset bug class and simplify the code.
todos:
  - id: audit-builders
    content: Normalize all detailed-data builders to emit Unix-second float `t` columns consistently.
    status: completed
  - id: replace-slicing
    content: Replace datetime-based detail slicing and render-time filtering with float interval bounds throughout datasource and renderer code.
    status: completed
  - id: simplify-renderers
    content: Remove no-longer-needed datetime branches from detail renderers, table sync, and downsampling helpers where safe.
    status: completed
  - id: validate-alignment
    content: Validate TextLogger/annotations alignment and run focused regression checks for timeline rendering and table sync.
    status: completed
isProject: false
---

# Standardize Detailed Timestamps To Unix Floats

## Goal
Make `pypho_timeline` use Unix-second floats as the canonical internal time representation for detailed data and interval slicing across [C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\). Keep native datetime objects only for UI formatting and boundary conversions.

## Core Changes
- Update [C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\datasources\stream_to_datasources.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\datasources\stream_to_datasources.py) so detailed `time_series_df['t']` stays as Unix-second floats instead of being round-tripped through `unix_timestamp_to_datetime(...)`, `pd.to_datetime(...)`, and `ts_index.values`.
- Refactor [C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\datasources\track_datasource.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\datasources\track_datasource.py) to slice detailed data using float interval bounds (`t_start` / `t_end`) rather than `t_start_dt` / `t_end_dt` datetime bridge columns. Remove the current datetime-only coupling comment and dead dtype-coercion logic.
- Align the second-pass detail filter in [C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\graphics\track_renderer.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\graphics\track_renderer.py) with the same float-based interval convention so fetch-time and render-time filtering behave identically.
- Convert MNE/raw-derived detailed frames in [C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\timeline_builder.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\timeline_builder.py) to emit float `t` columns for EEG, motion, and annotation/log detail data instead of `pd.Timestamp` values.

## Simplification Pass
- Simplify detail renderers that currently branch on datetime `t` handling:
  - [C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\detail_renderers\generic_plot_renderer.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\detail_renderers\generic_plot_renderer.py)
  - [C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\detail_renderers\log_text_plot_renderer.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\detail_renderers\log_text_plot_renderer.py)
  - [C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\datasources\specific\eeg.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\datasources\specific\eeg.py)
  - [C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\datasources\specific\motion.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\datasources\specific\motion.py)
- Keep interval and UI-facing datetime conversions where they are still genuinely needed, especially in [C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\utils\datetime_helpers.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\utils\datetime_helpers.py), but narrow their responsibility to boundary conversion and display formatting instead of internal storage.
- Simplify [C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\dataframe_table_widget.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\dataframe_table_widget.py) if its viewport filtering still branches on datetime-valued `t`.
- Remove or reduce dead code paths in [C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\utils\downsampling.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\utils\downsampling.py) that only exist to normalize datetime-like `t` values when the package now guarantees numeric time columns internally.

## Consistency Rules
- Canonical internal representation:
  - `detailed_df['t']`: Unix-second float
  - `intervals_df['t_start']`, `intervals_df['t_end']`, `t_duration`: Unix-second floats / seconds
- Datetime objects remain allowed only for:
  - converting relative stream/raw times to absolute Unix floats at ingest
  - plot label / crosshair / calendar / display formatting
  - external metadata surfaces where human-readable datetimes are intentionally exposed
- Ensure cache keys continue to be stable after the migration, preferably deriving from float `t_start` + `t_duration` consistently.

## Validation
- Verify the original `TextLogger` alignment issue no longer reproduces across multi-XDF sessions.
- Sanity-check EEG, motion, annotations, and any table-track syncing after the refactor.
- Run targeted tests around runtime downsampling and any timeline/calendar/table behavior touched by time filtering.
- Add or update focused tests only where they protect the float-time invariant or catch the previous offset regression.

## Key Risk To Watch
The main risk is mixed representations during the migration. The implementation should avoid any intermediate state where detailed `t` is float in some builders and datetime in others, or where fetch-time filtering uses `< t_end` but render-time filtering still uses datetime `<= t_end_dt`.