---
name: Eastern timezone display
overview: Switch all timeline display formatting from UTC to America/New_York (automatic EDT/EST) while keeping internal timestamps in UTC/Unix for synchronization and data integrity.
todos:
  - id: tz-helper
    content: Add centralized America/New_York display timezone helper in datetime utilities.
    status: completed
  - id: axis-format
    content: Update shared AM/PM DateAxis tick formatting to display Eastern time.
    status: completed
  - id: hover-format
    content: Update track hover/crosshair datetime strings to use Eastern display conversion.
    status: completed
  - id: video-format
    content: Update vispy video datetime tick formatter to use Eastern display conversion.
    status: completed
  - id: calendar-boundaries
    content: Shift calendar day/hour boundary calculations to Eastern-local time.
    status: completed
  - id: verify
    content: Run lint and functional verification across key tracks.
    status: completed
isProject: false
---

# Eastern Time Display Plan

## Goal

Render all user-facing timeline datetimes in Eastern Time (`America/New_York`, DST-aware), while leaving internal math/storage in UTC/Unix timestamps.

## Targeted Changes

- Update shared datetime display formatting in `[C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\utils\datetime_helpers.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\utils\datetime_helpers.py)`:
  - Add a single display-timezone source (`ZoneInfo('America/New_York')`).
  - Add a small helper that converts a UTC/naive datetime to display timezone for labels.
  - Update `create_am_pm_date_axis()` tick label formatting to convert each tick datetime into Eastern before `strftime`.
- Propagate the display-timezone helper to hover/overlay labels in `[C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\graphics\track_renderer.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\graphics\track_renderer.py)` so crosshair time readouts match axis timezone.
- Update VisPy video track tick formatting in `[C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\graphics\vispy_video_epoch_renderer.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\graphics\vispy_video_epoch_renderer.py)` to use the same display-timezone helper.
- Align calendar track day/hour boundary rendering in `[C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\timeline_calendar_widget.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\timeline_calendar_widget.py)` to Eastern-local day starts (instead of fixed UTC day boundaries), so visual separators and labels remain consistent with track axes.

## Validation

- Run timeline with representative tracks (EEG, spectrogram, motion, video).
- Confirm x-axis tick labels show Eastern local times (with correct DST behavior).
- Confirm crosshair/hover labels match axis times.
- Confirm day separators in calendar align with Eastern midnight transitions.
- Quick lint pass on edited files only.

## Scope Guardrails

- No changes to datasource timestamp storage or synchronization semantics.
- No migration of persisted data; display-only timezone conversion.

