---
name: DosePlotDetailRenderer completion
overview: Fix the broken `DosePlotDetailRenderer` in [dose.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/specific/dose.py), align EventBoard dose parsing with `DoseNoteFragmentParser` expectations (per-day notes), compute PK/PD curves via `PySbPKPD_DA_NE_DoseCurveModel`, and draw them with pyqtgraph—without calling matplotlib `plot()`/`plt.show()`.
todos:
  - id: refactor-inherit
    content: Subclass LogTextDataFramePlotDetailRenderer; trim broken render_detail block and align __init__ (model defaults, curve_keys, backend=scipy).
    status: completed
  - id: daily-parse
    content: Build Dict[datetime,str] from EventBoard rows grouped by US/Eastern calendar date; call DoseNoteFragmentParser.parse_dose_note; handle empty/exception.
    status: completed
  - id: pg-curves
    content: compute() -> map t_h+t0 to unix; add PlotDataItems; extend get_detail_bounds for y-range; never call matplotlib plot().
    status: completed
  - id: smoke-test
    content: Smoke-test import + render_detail with small synthetic DataFrame (parseable dose lines + t).
    status: completed
isProject: false
---

# Complete `DosePlotDetailRenderer` for EventBoard dose curves

## Current state

- [`stream_to_datasources.py`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/stream_to_datasources.py) already selects `DosePlotDetailRenderer` for `stream_name == 'EventBoard'` (via `_build_dose_curve_records_detail_renderer()`), with `LOG_{stream_name}` datasource and `modality_channels_dict['LOG']` columns (same as other log streams).
- [`dose.py`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/specific/dose.py) `DosePlotDetailRenderer.render_detail` is **not runnable**: dead code at ~156–162 (`parsed_record_df` / `active_model` undefined, stray `txt_df.str.`, `message` / `text_parts` ordering), duplicate local imports, and `self.active_model.plot()` which routes to matplotlib [`plotCurves` → `plt.show()`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/Dose-Analysis-Python/src/dose_analysis_python/DoseCurveCalculation/pysb_pkpd_da_ne_monoamine.py)—wrong for an embedded pyqtgraph detail view.
- [`LogTextDataFramePlotDetailRenderer`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/detail_renderers/log_text_plot_renderer.py) already implements the EventBoard text + vertical lines pattern cleanly.

## Design choices

1. **Inheritance** — Change `DosePlotDetailRenderer` to subclass `LogTextDataFramePlotDetailRenderer` (not `DataframePlotDetailRenderer`) so `render_detail` / `clear_detail` / docstrings stay consistent with EventBoard UX: keep per-event text + optional `InfiniteLine`s, then add curve geometry on top (curves at default z, vlines at `-10` as today, text on top).

2. **Parsing input for `DoseNoteFragmentParser.parse_dose_note`** — [`parse_dose_note`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/Dose-Analysis-Python/src/dose_analysis_python/FileImportExport/DoseImporter.py) accepts either a **string** (single `note_day_date`, defaulting to “today”) or a **`Dict[datetime, str]`** keyed by calendar day. EventBoard rows span real days with unix `t`; a single concatenated string without the right `note_day_date` will mis-assign times. **Build `daily_note_dict`**: group rows by **calendar date** derived from each row’s `t` (convert unix → datetime, use a fixed timezone consistent with the importer—**`US/Eastern`** matches `parse_dose_note_to_records`, which `tz_localize`s the index to `US/Eastern`). For each day, join that day’s log lines with newlines (same shape as the notebook examples).

3. **Computation** — After `parsed_record_df, _, (parsed_quanta, _) = DoseNoteFragmentParser.parse_dose_note(...)`:
   - If either side is empty or parsing raises, **skip curves** and still render log text/lines.
   - Instantiate `PySbPKPD_DA_NE_DoseCurveModel(recordSeries=parsed_record_df, quanta=parsed_quanta, max_events=..., follow_h_after_last=...)` with defaults stored on the renderer (constructor params mirroring current intent, e.g. `max_events`, `follow_h_after_last`).
   - Call **`compute()`** (updates `self.state`). Force a **SciPy backend** for the embedded UI unless you explicitly want PySB/BNG: set `model.parameters['backend'] = 'scipy'` before `compute()` (see [`BaseDoseCurveModel.compute`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/Dose-Analysis-Python/src/dose_analysis_python/DoseCurveCalculation/BaseDoseCurveModel.py) and [`simulate_da_ne_monoamine_pysb`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/Dose-Analysis-Python/src/dose_analysis_python/DoseCurveCalculation/pysb_pkpd_da_ne_monoamine.py) `backend` behavior).
   - Wrap `compute()` / `merge_positive_dose_events` failures (`ValueError` for no positive doses, etc.) in try/except + logger so the dock still shows raw events.

4. **Plotting in pyqtgraph** — Do **not** call `plot()` / `plotCurves` from the library.
   - Read `t_h`, `y_dict`, `meta` from `curve_dict` / `model.state` after `compute()`.
   - Map model time to timeline unix: `t0 = meta["t0"]` (pandas `Timestamp`), convert to unix with the same helper used elsewhere: [`datetime_to_unix_timestamp`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/utils/datetime_helpers.py) (handle tz-aware `t0` consistently—convert to UTC or normalize before converting so it matches stream `t` encoding).
   - `t_x = t0_unix + t_h * 3600.0`.
   - Add one `pg.PlotDataItem(t_x, y, pen=...)` per selected trace. Default subset: a small readable set from `STATE_NAMES_7` (e.g. `AMPH_blood`, `DA_str`, `NE_pfc`); optional constructor arg `curve_keys: Optional[List[str]]` to override.
   - Append all new items to the same `graphics_objects` list returned for `clear_detail`.

5. **`get_detail_bounds`** — Override: start from `LogTextDataFramePlotDetailRenderer.get_detail_bounds` for **x** (interval / detail `t` range). For **y**, when curves exist, set `y_min`/`y_max` from the union of plotted `y` arrays (finite values only) plus padding; when no curves, keep `(0.0, 1.0)`. Optionally bump text `y_position` when curves are drawn so labels sit in the upper band (constructor default or scale from computed `y_max`).

6. **Cleanup** — Remove the broken mid-function block, remove redundant imports inside `render_detail`, fix class/docstring references (currently mention EEG / wrong import path). Keep `__all__` export. Preserve user style rules: single-line calls where possible, two blank lines between methods.

7. **Verification** — Run a quick import / `render_detail` smoke test (minimal fake `detail_data` DataFrame with `t` + log column and a few parseable dose lines). No notebook edits.

## Optional follow-up (out of scope unless you want parity)

- `TimelineBuilder._process_xdf_streams` references `perform_process_single_xdf_file_all_streams` without a visible definition in-repo; if `build_from_streams` is used, that path may need the same EventBoard renderer wiring as `perform_process_all_streams_multi_xdf`. This is independent of finishing `dose.py` for the multi-XDF path you already use.
