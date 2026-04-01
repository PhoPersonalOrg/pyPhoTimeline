---
name: Motion RawProviding subclass
overview: Make `MotionTrackDatasource` inherit from `RawProvidingTrackDatasource` (same pattern as `EEGTrackDatasource`), threading optional `lab_obj` and `raw_datasets` through `__init__` and `from_multiple_sources`. Optionally wire XDF merge path so motion tracks receive those handles like EEG does.
todos:
  - id: motion-imports-base
    content: "motion.py: __future__ annotations, TYPE_CHECKING, RawProviding import, subclass + __init__ super call with lab_obj/raw_datasets"
    status: completed
  - id: motion-from-multiple
    content: "motion.py: extend from_multiple_sources with lab_obj/raw_datasets -> cls(...)"
    status: completed
  - id: stream-wire-motion
    content: "stream_to_datasources.py: pass lab_obj and motion raw list into MotionTrackDatasource.from_multiple_sources (merge path)"
    status: completed
isProject: false
---

# MotionTrackDatasource as RawProvidingTrackDatasource

## Context

`[RawProvidingTrackDatasource](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/track_datasource.py)` is a thin subclass of `IntervalProvidingTrackDatasource` that adds `lab_xdf_obj` / `raw_datasets` (backed by `_lab_xdf_obj` / `_raw_datasets`) and passes `lab_obj` + `raw_datasets` into `super().__init__`. No overrides of detail fetching or cache keys—behavior stays interval-based.

`[MotionTrackDatasource](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/specific/motion.py)` (lines 347–516) today subclasses `IntervalProvidingTrackDatasource` directly and calls `super().__init__(intervals_df, detailed_df=motion_df, ...)` without `detail_renderer` (still correct under `RawProvidingTrackDatasource`, which defaults `detail_renderer=None`).

Reference implementation: `[EEGTrackDatasource](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/specific/eeg.py)` (`__init__` forwards `lab_obj=...`, `raw_datasets=...` to `super().__init__`; `from_multiple_sources` passes the same into `cls(...)`).

## Code changes

### 1. `[motion.py](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/specific/motion.py)`

- Add `from __future__ import annotations` as the **first** line (matches `[eeg.py](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/specific/eeg.py)` / `[track_datasource.py](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/track_datasource.py)`) so `LabRecorderXDF` / `mne.io.Raw` type hints in signatures do not require runtime imports.
- Add `from typing import TYPE_CHECKING` (if not present) and:

```python
if TYPE_CHECKING:
    import mne
    from phopymnehelper.xdf_files import LabRecorderXDF
```

- Replace import `IntervalProvidingTrackDatasource` with `RawProvidingTrackDatasource` on the existing `track_datasource` import line (only used for this class).
- Change base class to `RawProvidingTrackDatasource`.
- Update class/docstring to say it extends `RawProvidingTrackDatasource` / optional lab + raw handles (mirror EEG wording briefly).
- Extend `__init__` with `lab_obj: Optional[LabRecorderXDF] = None`, `raw_datasets: Optional[List[mne.io.Raw]] = None` (after existing params, before `parent`), and call:

`super().__init__(intervals_df, detailed_df=motion_df, custom_datasource_name=custom_datasource_name, max_points_per_second=max_points_per_second, enable_downsampling=enable_downsampling, lab_obj=lab_obj, raw_datasets=raw_datasets, parent=parent)`

  Omit `detail_renderer` so it stays `None` (motion still uses `get_detail_renderer()` override).

- Extend `from_multiple_sources` with the same optional `lab_obj` and `raw_datasets` and pass them into the final `cls(...)` alongside existing motion-specific kwargs.

No changes needed to `get_detail_cache_key`, `get_detail_renderer`, or `set_bad_intervals`: MRO still reaches `IntervalProvidingTrackDatasource.get_detail_cache_key` via `super()`.

### 2. (Recommended) `[stream_to_datasources.py](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/stream_to_datasources.py)` merged XDF path

Today the motion branch builds `raws_dict` / `lab_obj` but only uses `motion_raws[0]` for bad-interval heuristics; it never attaches `lab_obj` or motion raws to the datasource. EEG already passes `lab_obj=lab_obj, raw_datasets=eeg_raw_datasets` into `[EEGTrackDatasource.from_multiple_sources](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/stream_to_datasources.py)` (~464–465).

Align motion with that pattern: compute `motion_raw_datasets = raws_dict.get(DataModalityType.MOTION.value, []) if raws_dict else None` (or reuse the list already fetched for bad-interval logic) and pass `lab_obj=lab_obj, raw_datasets=motion_raw_datasets` into `MotionTrackDatasource.from_multiple_sources(...)` at ~430. Call sites that omit these args remain valid (defaults `None`).

Single-file motion construction (~146) can stay unchanged unless you later have `lab_obj` in that code path.

## Verification

- Run analyzer/tests you normally use on `pypho_timeline` (e.g. `uv run` pytest or `mypy` if configured).
- Smoke: `isinstance(motion_ds, RawProvidingTrackDatasource)` and `isinstance(motion_ds, IntervalProvidingTrackDatasource)` both True; `lab_xdf_obj` / `raw_datasets` readable when wired from merge path.

## Non-goals

- Changing motion detail rendering to read from MNE `Raw` instead of `motion_df` (not requested; `raw_datasets` is optional storage for downstream use, same as EEG).
- Modifying `RawProvidingTrackDatasource` itself.

