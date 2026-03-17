---
name: local-time-timeline-fix
overview: Normalize all timeline timestamps to a consistent local-time interpretation for naive datetimes, then convert to UTC epoch for plotting so track data and the red "now" line align correctly.
todos:
  - id: normalize-naive-datetimes
    content: Implement local-time normalization helper and use it in datetime_to_unix_timestamp for scalar/vector paths
    status: completed
  - id: fix-now-line-timebase
    content: Update now-line generation to use timezone-aware current time compatible with conversion contract
    status: completed
  - id: restore-datetime-axis-init
    content: Remove forced reference_datetime nulling and keep datetime-axis setup active when applicable
    status: completed
  - id: validate-local-alignment
    content: Run notebook/timeline checks to confirm session placement, now-line alignment, and local axis labels
    status: completed
isProject: false
---

# Local Time Alignment Fix Plan

## Goal

Make all tracks and the red `now` marker use the same time basis by treating naive datetimes as local time (user display timezone), then converting consistently to UTC epoch seconds for plotting.

## Scope

- Core datetime conversion helpers
- Red `now` line timestamp generation
- Timeline datetime-axis enablement and range initialization
- Verification in the notebook workflow

## Files To Update

- [pypho_timeline/utils/datetime_helpers.py](pypho_timeline/utils/datetime_helpers.py)
- [pypho_timeline/rendering/mixins/epoch_rendering_mixin.py](pypho_timeline/rendering/mixins/epoch_rendering_mixin.py)
- [pypho_timeline/timeline_builder.py](pypho_timeline/timeline_builder.py)
- (Validate behavior in) [testing_notebook.ipynb](testing_notebook.ipynb)

## Implementation Steps

1. **Add a single local-normalization helper in datetime utilities**
  - In `datetime_helpers`, introduce one internal function used by conversions:
    - If datetime is naive: localize to `DISPLAY_TIMEZONE`
    - If datetime is aware: preserve instant and convert as needed
  - Use that helper inside `datetime_to_unix_timestamp` for both scalar and vector paths, so naive values are no longer assumed UTC.
2. **Keep conversion contracts explicit and symmetric**
  - Ensure `datetime_to_unix_timestamp` always returns absolute epoch seconds.
  - Ensure `unix_timestamp_to_datetime` remains UTC-aware output (as canonical internal representation), with display-local conversion happening only in UI formatting (`to_display_timezone`).
3. **Fix red `now` line source timestamp**
  - In `epoch_rendering_mixin`, replace naive `datetime.now()` usage with timezone-aware now in UTC (or normalize through helper before conversion).
  - This removes offset mismatch between `now` and track x-values.
4. **Re-enable datetime axis path in timeline construction**
  - In `timeline_builder`, remove/replace forced `reference_datetime = None` override so datetime-axis formatting can activate when data are datetime-based.
  - Keep initialization logic consistent with absolute datetime tracks.
5. **Verify end-to-end alignment behavior**
  - Validate that most recent sessions are no longer ahead of the red line.
  - Confirm bottom axis labels match local timezone consistently.
  - Confirm interval rectangles and detailed traces remain aligned after conversion changes.

## Verification Checklist

- Open recent recording and confirm session endpoints relative to red `now` line.
- Compare one known event timestamp against displayed axis label in local time.
- Pan/zoom and ensure no jump/drift from timezone conversion.
- Check lints for touched files and resolve introduced issues only.

