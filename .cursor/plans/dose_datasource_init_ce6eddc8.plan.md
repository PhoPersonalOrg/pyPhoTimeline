---
name: dose datasource init
overview: Finish the `DoseTrackDatasource.init_from_timeline_text_log_tracks` path so it builds the dose-curve dataframe datasource directly from the timeline text log, and disable unrelated unfinished methods copied from other datasource implementations.
todos:
  - id: fix-class-base-init
    content: Adjust `DoseTrackDatasource` inheritance and constructor to be a dataframe-backed datasource for computed dose curves.
    status: completed
  - id: finish-text-log-init
    content: Complete `init_from_timeline_text_log_tracks` with default track names, text-log parsing, curve computation, interval construction, and datasource return.
    status: completed
  - id: disable-unfinished-methods
    content: Comment out unfinished non-init methods and remove the `DosePlotDetailRenderer` wiring from `DoseTrackDatasource`.
    status: completed
  - id: verify-dose-file
    content: Run a lightweight import/syntax check and inspect lints for `dose.py`.
    status: in_progress
isProject: false
---

# DoseTrackDatasource Init Plan

Update `[pypho_timeline/rendering/datasources/specific/dose.py](pypho_timeline/rendering/datasources/specific/dose.py)` only.

Core implementation:
- Change `DoseTrackDatasource` to inherit from the datasource base it actually uses, likely `RawProvidingTrackDatasource`, instead of `DataframePlotDetailRenderer`.
- Make `__init__` store both `recordSeries_df` and `complete_curve_df`, derive the rendered curve dataframe (`['t'] + curve channels`), and pass that dataframe to the datasource superclass as `detailed_df`.
- Replace `DosePlotDetailRenderer` usage with a standard `DataframePlotDetailRenderer` from `get_detail_renderer`, using the AMPH and monoamine normalization groups already drafted in the notebook-derived code.
- Finish `init_from_timeline_text_log_tracks(timeline, track_name='DOSE_CURVES_Computed', source_track_name='LOG_TextLogger', ...)` so it:
  - copies `txt_log_ds.detailed_df` without needing `deepcopy`,
  - creates/uses a `dt` column from `t` and `timeline.reference_datetime`,
  - parses `msg` entries matching numeric `plus` dose tokens into `recordSeries_df`,
  - computes `complete_curve_df` via `ComputationTimeBlock.init_from_start_end_date(...)`,
  - builds `intervals_df` from the curve `t` span,
  - returns `cls(...)` with `channel_names=curve_channel_names` and `enable_downsampling=False`.

Cleanup:
- Stop exporting/using `DosePlotDetailRenderer`; leave it commented or otherwise clearly marked unused rather than wiring it into `DoseTrackDatasource`.
- Comment out unfinished copied methods that are not part of this init path and currently reference undefined symbols or EEG-specific behavior, including `build_dose_curve_track`, `try_extract_raw_datasets_dict`, custom `compute`/post-compute methods, and spectrogram helper methods.
- Keep `num_sessions` and `get_detail_cache_key` if they still work through the datasource base.

Verification:
- Run a syntax/import check for `pypho_timeline.rendering.datasources.specific.dose` if the local environment can import project dependencies.
- Run lints for the edited file and fix any issues introduced by the change.