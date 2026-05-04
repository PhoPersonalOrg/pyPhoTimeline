---
name: dose datasource replacement
overview: Remove the legacy `DosePlotDetailRenderer` and simplify the EventBoard branch in `stream_to_datasources.py` to use the plain log renderer. `DoseTrackDatasource` is a computed datasource built post-timeline-load via `init_from_timeline_text_log_tracks`, not from raw XDF stream data.
todos:
  - id: remove-renderer
    content: Delete `DosePlotDetailRenderer` and renderer-only imports/constants from `dose.py`.
    status: completed
  - id: add-helper
    content: No new classmethod needed — `DoseTrackDatasource.init_from_timeline_text_log_tracks(timeline, source_track_name='LOG_EventBoard')` already covers the post-load path.
    status: cancelled
  - id: wire-streams
    content: Remove `_build_dose_curve_records_detail_renderer` and EventBoard special-casing from `stream_to_datasources.py`; EventBoard falls through to the same plain log renderer path as all other log streams.
    status: completed
  - id: validate
    content: Run targeted checks and lints on the edited Python files.
    status: completed
isProject: false
---

# Dose Datasource Replacement

## Scope
- Edit only Python source files, not notebooks.
- ~~Remove the unused `DosePlotDetailRenderer` block from `dose.py`.~~ **Done.**
- Update [`pypho_timeline/rendering/datasources/stream_to_datasources.py`](pypho_timeline/rendering/datasources/stream_to_datasources.py) to remove the now-dead `_build_dose_curve_records_detail_renderer` function and the EventBoard special-case that used it.

## Revised Understanding
`DoseTrackDatasource` is a *computed* datasource — it is never built directly from raw XDF stream data. The EventBoard XDF stream contains text-log messages that happen to encode dose events, but the PK/PD curve computation is a separate step done after the timeline is loaded. The correct entry point is:

```python
dose_curve_ds = DoseTrackDatasource.init_from_timeline_text_log_tracks(timeline, source_track_name='LOG_EventBoard')
```

Therefore `perform_process_all_streams_multi_xdf` should treat EventBoard exactly like any other log stream: build an `IntervalProvidingTrackDatasource` with the plain `LogTextDataFramePlotDetailRenderer`.

## Implementation Approach
- Delete `_build_dose_curve_records_detail_renderer()` from `stream_to_datasources.py`.
- Remove the `if stream_name == 'EventBoard':` branch; EventBoard now falls through to `_build_log_detail_renderer()` like every other log stream.
- No changes to `dose.py` or `DoseTrackDatasource` are needed beyond the already-completed renderer removal.

## Validation
- Run a targeted import/compile check for the edited modules.
- Run `ReadLints` on the edited files and fix any introduced diagnostics.