---
name: Restore Dose Curve Track Build-and-Add Helper
overview: Replace the stub `DoseTrackDatasource.build_dose_curve_track` with a working classmethod that builds the dose-curve datasource from a timeline's text-log track and adds it to the timeline as a new track, restoring notebook-callable functionality lost when `DosePlotDetailRenderer` was removed.
todos:
  - id: implement-build-and-add
    content: Replace the stub `build_dose_curve_track` classmethod with a working implementation that calls `init_from_timeline_text_log_tracks` and `timeline_builder.update_timeline`.
    status: completed
  - id: verify-imports
    content: Confirm `TYPE_CHECKING` imports for `SimpleTimelineWidget` and `TimelineBuilder` are present (or add them) in `dose.py`.
    status: completed
  - id: validate
    content: Run lints and a syntax check on the edited `dose.py`.
    status: completed
isProject: false
---

# Restore Dose Curve Track Build-and-Add Helper

## Context
The original `DosePlotDetailRenderer` overlaid dose curves inline within the `LOG_EventBoard` track's detail view, so no separate track was needed. After its removal, dose curves are gone from the auto-load flow. `DoseTrackDatasource.init_from_timeline_text_log_tracks(...)` builds the datasource but does not add it to the timeline.

The notebook used to call a `build_dose_curve_track(timeline, complete_curve_df, ...)` helper that did both. The current `dose.py` has a stub classmethod `build_dose_curve_track` (line 145-148) that just raises `NotImplementedError`.

## Approach
Replace the stub at [`pypho_timeline/rendering/datasources/specific/dose.py`](pypho_timeline/rendering/datasources/specific/dose.py#L145) with a working classmethod that mirrors the established `add_spectrogram_tracks_for_channel_groups` pattern (already used by both `eeg.py` and `dose.py`):

```python
@classmethod
def build_dose_curve_track(cls, timeline: "SimpleTimelineWidget", timeline_builder: "TimelineBuilder", track_name: str='DOSE_CURVES_Computed', source_track_name: str='LOG_TextLogger', backend: str='scipy', max_events: int=120, follow_h_after_last: float=12.0, *, update_time_range: bool=False, skip_existing_names: bool=True) -> Optional["DoseTrackDatasource"]:
    """Build dose curves from `timeline`'s text-log track and add as a new track via `timeline_builder.update_timeline`."""
    if skip_existing_names and (track_name in timeline.track_datasources):
        logger.debug("build_dose_curve_track: skip existing track %r", track_name)
        return cast(Optional["DoseTrackDatasource"], timeline.track_datasources.get(track_name))
    dose_curve_ds = cls.init_from_timeline_text_log_tracks(timeline=timeline, track_name=track_name, source_track_name=source_track_name, backend=backend, max_events=max_events, follow_h_after_last=follow_h_after_last)
    timeline_builder.update_timeline(timeline, [dose_curve_ds], update_time_range=update_time_range)
    return dose_curve_ds
```

## Notebook Usage
After this change the notebook can call:

```python
dose_curve_ds = DoseTrackDatasource.build_dose_curve_track(timeline=timeline, timeline_builder=builder, source_track_name='LOG_EventBoard')
```

`init_from_timeline_text_log_tracks` remains available for callers who only want the datasource without adding the track.

## Implementation Notes
- Keep the existing `init_from_timeline_text_log_tracks` unchanged.
- The `TYPE_CHECKING` imports for `SimpleTimelineWidget` and `TimelineBuilder` already exist in the file (per the `add_spectrogram_tracks_for_channel_groups` references); no new imports needed beyond confirming they're present.
- Default `source_track_name='LOG_TextLogger'` matches `init_from_timeline_text_log_tracks`; users override to `'LOG_EventBoard'` for XDF EventBoard streams.

## Validation
- `ReadLints` on the edited `dose.py`.
- Targeted syntax/import check via `uv run python -c "import ast; ast.parse(open(...).read())"`.