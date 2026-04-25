---
name: dose datasource replacement
overview: Remove the legacy `DosePlotDetailRenderer` and route EventBoard dose streams through `DoseTrackDatasource` so dose curves are represented as the specialized datasource instead of a log detail renderer.
todos:
  - id: remove-renderer
    content: Delete `DosePlotDetailRenderer` and renderer-only imports/constants from `dose.py`.
    status: completed
  - id: add-helper
    content: Add a `DoseTrackDatasource` helper for building from EventBoard interval/detail DataFrames without a timeline object.
    status: in_progress
  - id: wire-streams
    content: Update EventBoard handling in `stream_to_datasources.py` to create `DoseTrackDatasource` and remove `_build_dose_curve_records_detail_renderer`.
    status: pending
  - id: validate
    content: Run targeted checks and lints on the edited Python files.
    status: pending
isProject: false
---

# Dose Datasource Replacement

## Scope
- Edit only Python source files, not notebooks.
- Remove the unused `DosePlotDetailRenderer` block from [`pypho_timeline/rendering/datasources/specific/dose.py`](pypho_timeline/rendering/datasources/specific/dose.py).
- Remove imports/constants that only existed for that renderer, while preserving imports used by `DoseTrackDatasource`.
- Update [`pypho_timeline/rendering/datasources/stream_to_datasources.py`](pypho_timeline/rendering/datasources/stream_to_datasources.py) so `EventBoard` log streams create a `DoseTrackDatasource` instead of an `IntervalProvidingTrackDatasource` with `DosePlotDetailRenderer`.

## Implementation Approach
- Add a small `DoseTrackDatasource` classmethod for the non-timeline path, likely `init_from_text_log_dfs(intervals_df, detailed_txt_log_df, ...)`, reusing the existing parse/compute logic from `init_from_timeline_text_log_tracks`.
- In `perform_process_all_streams_multi_xdf`, concatenate EventBoard `all_detailed_dfs`, derive `dt` from absolute unix `t` values, and construct `DoseTrackDatasource` with a name like `DOSE_CURVES_EventBoard` or `DOSE_CURVES_Computed`.
- Keep non-EventBoard logs on the existing `LogTextDataFramePlotDetailRenderer` path.
- If an EventBoard stream has no parseable dose records, log a warning and fall back to the regular log datasource rather than breaking XDF loading.

## Validation
- Run a targeted import/compile check for the edited modules.
- Run `ReadLints` on the edited files and fix any introduced diagnostics.