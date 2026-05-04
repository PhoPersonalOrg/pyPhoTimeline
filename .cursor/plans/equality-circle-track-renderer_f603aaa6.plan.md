---
name: equality-circle-track-renderer
overview: Add a minimal custom detail renderer for `Epoc X eQuality` tracks that plots per-channel quality as color-coded circles, while keeping existing datasource wiring and channel options behavior.
todos:
  - id: add-eegq-circle-renderer
    content: Add `EEGQualityCircleDetailRenderer` to `generic_plot_renderer.py` with discrete quality color mapping and stacked-lane circle rendering.
    status: completed
  - id: wire-renderer-builder
    content: Update `_build_eeg_quality_detail_renderer()` in `stream_to_datasources.py` to return the new renderer.
    status: completed
  - id: verify-behavior
    content: Verify on an `Epoc X eQuality` dataset that circles render correctly and channel visibility still works.
    status: completed
isProject: false
---

# Add eQuality Circle Plot Renderer

## Goal
Render `Epoc X eQuality` tracks as stacked channel lanes where each timestamp is shown as a circle and color encodes discrete quality (0–4 buckets), with minimal code churn.

## Minimal-change approach
- Keep the existing stream detection and datasource path for EEG quality in [C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/stream_to_datasources.py](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/stream_to_datasources.py).
- Replace only the detail renderer returned by `_build_eeg_quality_detail_renderer()`.
- Implement a specialized renderer by subclassing `DataframePlotDetailRenderer` in [C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/detail_renderers/generic_plot_renderer.py](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/detail_renderers/generic_plot_renderer.py).

## Planned code changes
- Add `EEGQualityCircleDetailRenderer` class in `generic_plot_renderer.py`:
  - Reuse existing channel selection and visibility behavior (`channel_names`, `channel_visibility`).
  - In `render_detail(...)`, draw one `ScatterPlotItem` per channel lane:
    - x = `t`
    - y = fixed lane baseline for that channel (stacked-lane layout)
    - symbol = circle
    - brush per point from discrete quality mapping
  - Keep cleanup/bounds behavior via existing base implementation (only override methods if required).
- Add a small helper in that class for value→color mapping (discrete buckets):
  - `0/1 -> red`, `2 -> orange`, `3 -> yellow`, `>=4 -> green`, invalid/NaN -> gray.
- Update `_build_eeg_quality_detail_renderer()` in `stream_to_datasources.py` to instantiate `EEGQualityCircleDetailRenderer` instead of generic line-based `DataframePlotDetailRenderer`.

## Why this is minimal
- No datasource schema changes.
- No timeline/track renderer plumbing changes.
- No changes to stream identification (`_is_eeg_quality_stream`) or channel naming logic.
- Only two touched files in `pyPhoTimeline`.

## Validation steps
- Load an XDF containing `Epoc X eQuality`.
- Confirm `EEGQ_*` track opens and renders circles (not lines).
- Toggle channel visibility in track options and confirm circles for hidden channels disappear.
- Spot-check color mapping against known quality samples (0..4).