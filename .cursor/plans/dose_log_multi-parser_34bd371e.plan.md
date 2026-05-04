---
name: Dose log multi-parser
overview: Replace the transcript-only regex path in `DoseTrackDatasource` with the same dose-sample parsing cascade as [lsl_monitor.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/Dose-Analysis-Python/src/dose_analysis_python/service/lsl_monitor.py), and extend timeline initialization to accept one or many source log track names (e.g. `LOG_TextLogger`, `LOG_EventBoard`) by merging rows before parsing.
todos:
  - id: import-parse
    content: Import parse_lsl_dose_sample from dose_analysis_python.service.lsl_monitor; add row-wise helper that builds recordSeries_df (multi-event flatten, US/Eastern tz)
    status: completed
  - id: replace-regex-parser
    content: Replace _perform_parse_message_logs_to_dose_events with new helper; wire init_from_timeline_text_log_tracks to use it
    status: completed
  - id: multi-track-api
    content: Extend init_from_timeline_text_log_tracks + build_dose_curve_track to accept str | Sequence[str], concat+sort dfs, validate tracks exist
    status: completed
  - id: docstrings-verify
    content: Update docstrings; add minimal tests or document manual verification matrix (EventBoard/JSON/transcript/note/bare)
    status: completed
isProject: false
---

# Unify dose text-log parsing with LSL monitor

## Context

- [`lsl_monitor.py`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/Dose-Analysis-Python/src/dose_analysis_python/service/lsl_monitor.py) parses dose events via **`parse_lsl_dose_sample`** (lines 99–121): JSON markers → EventBoard `DOSE_*|...|...` → transcript “N plus” → note fragments (with `-`) → bare numeric token. Stream **name** does not select the parser; **message shape** does.
- [`dose.py`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/specific/dose.py) today only implements the **transcript** branch in `_perform_parse_message_logs_to_dose_events` (regex `plus`, lines 96–114). That misses EventBoard lines, JSON lines, note-style lines, and bare tokens unless they happen to match `plus`.

`pyPhoTimeline` already depends on `dose-analysis-python` ([`pyproject.toml`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pyproject.toml)), so we can call the shared parser instead of duplicating private helpers from `lsl_monitor.py`.

## What stays unchanged

- **`DoseTrackDatasource.__init__`** ([line 47](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/specific/dose.py)): still takes pre-built `intervals_df` / `recordSeries_df` / `complete_curve_df`. No need to add stream-name parameters there; the behavior change belongs to **factory / parsing** helpers and `init_from_timeline_text_log_tracks` / `build_dose_curve_track`.

## Implementation

### 1. Reuse `parse_lsl_dose_sample` from dose-analysis-python

- Import `parse_lsl_dose_sample` from `dose_analysis_python.service.lsl_monitor`.
- Map each returned `DoseEventCreate` to the existing `recordSeries_df` shape: index = `event_time`, columns `recordDoseValue`, `modifier`, `medication` (same as today). **Flatten** so one log row can yield **multiple** events (JSON arrays, `parse_dose_note_to_records`).

### 2. Replace `_perform_parse_message_logs_to_dose_events`

- New method (name e.g. `_text_log_rows_to_record_series_df`) that:
  - Requires `msg` and a wall-clock column (reuse current flow: `dt` from `float_to_datetime` + index as today).
  - For each row: `sample_time` = that row’s `dt` as a **timezone-aware** `datetime` (mirror current end of `_perform_parse_message_logs_to_dose_events`: normalize to `US/Eastern` so `DoseEventCreate` validators and downstream `ComputationTimeBlock.init_from_start_end_date(..., tz=...)` stay consistent).
  - Call `parse_lsl_dose_sample(sample=row["msg"], sample_time=sample_time, default_medication="AMPH")` (or add an optional `default_medication` parameter on the classmethods if you want it configurable without touching `__init__`).
  - Skip rows that return an empty list (same as monitor “ignored” samples).
- Remove or narrow the old regex-only implementation to avoid two sources of truth.

### 3. Support multiple source tracks (API)

- Change **`source_track_name`** on `init_from_timeline_text_log_tracks` and **`build_dose_curve_track`** to accept **`Union[str, Sequence[str]]`** (keep name `source_track_name` for backward compatibility, or introduce `source_track_names` and deprecate the singular — prefer **one** parameter: e.g. `source_track_names: Union[str, Sequence[str]] = "LOG_TextLogger"` and accept a bare string as a single-element case).
- Implementation:
  - Normalize to a list of names.
  - For each name, if the track exists on `timeline`, load `detailed_df`, ensure `t` / `dt` like today, optionally tag with `_source_track` for debugging (optional, can omit to minimize diff).
  - **`pd.concat`** all frames, **`sort_values("dt")`**, then run the new row-wise parser on the combined frame.
  - If **no** configured track exists: raise a clear `ValueError` listing requested names vs available `timeline.track_datasources` keys.
- **Duplicates**: merging `LOG_TextLogger` and `LOG_EventBoard` may double-count the same dose. Document this; optionally add a later `dedupe` flag (e.g. drop duplicate index + dose) — not required for the first cut unless you want it in scope.

### 4. Docs / call sites

- Update docstrings in `init_from_timeline_text_log_tracks` and `build_dose_curve_track` to state that parsing matches live LSL dose monitoring and that multiple log tracks can be passed as a sequence.
- No notebook edits unless you ask (per your rule).

## Verification

- Add a small **unit test** in `pyPhoTimeline` (if a tests package exists) or rely on manual checks: rows shaped like EventBoard (`DOSE_AMPH_...|Dose 10+|2024-...`), JSON, `10 plus`, note with `-`, and bare `10+` should all produce rows in `recordSeries_df`.
- Run existing dose-related tests in `Dose-Analysis-Python` unchanged (parser already covered there indirectly).

## Dependency note

If importing `dose_analysis_python.service.lsl_monitor` ever pulls unwanted side effects, an alternative is to move `parse_lsl_dose_sample` (+ `_sample_to_text`) into a neutral module (e.g. `dose_analysis_python.parsing.lsl_dose_text.py`) in a follow-up; initial implementation should prefer **import reuse** to match your reference file exactly.
