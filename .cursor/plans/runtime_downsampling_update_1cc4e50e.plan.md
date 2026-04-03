---
name: runtime downsampling update
overview: Add a datasource-level runtime API for updating downsampling settings on interval-backed tracks, and wire the existing refresh/cache path so visible detail redraws immediately with the new resolution.
todos:
  - id: add-datasource-setter
    content: Add a concise public downsampling update method to `IntervalProvidingTrackDatasource` for all interval-backed tracks.
    status: completed
  - id: wire-refresh-path
    content: Connect datasource change handling to clear affected detail state and re-render the current viewport automatically.
    status: completed
  - id: fix-cache-invalidation
    content: Make per-track detail cache invalidation reliable for runtime downsampling changes.
    status: completed
  - id: verify-notebook-usage
    content: Confirm the final API is a simple one-liner from notebook code and document the intended call pattern in code comments or docstring.
    status: completed
isProject: false
---

# Runtime Downsampling Update
## Goal
Add a concise datasource method for updating `max_points_per_second` / `enable_downsampling` at runtime for interval-backed tracks, with automatic invalidation and visible-track refresh so notebook callers do not need to manually clear caches or poke renderers.

## Main Changes
- Add a small public setter on [`C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/track_datasource.py`](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/track_datasource.py), likely on `IntervalProvidingTrackDatasource`, since EEG and Motion both inherit that path.
- Reuse the existing datasource change signal / renderer refresh infrastructure instead of inventing a notebook-only helper.
- Ensure async detail cache is invalidated when downsampling settings change, because the current detail cache key only depends on datasource name + interval time span, not the downsampling settings.

## Why This Placement
- Downsampling is implemented in [`track_datasource.py`](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/track_datasource.py) inside `fetch_detailed_data`, so the API should live with that state.
- Motion already has a mutation-style datasource API precedent (`set_bad_intervals(..., emit_changed=True)`) in [`C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/specific/motion.py`](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/specific/motion.py).
- The renderer already has the right “clear and redraw current viewport” behavior in [`C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/graphics/track_renderer.py`](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/graphics/track_renderer.py), especially `_trigger_visibility_render()`.

## Implementation Shape
- Add a public method on `IntervalProvidingTrackDatasource`, e.g. `set_downsampling(...)`, that:
  - updates `self.max_points_per_second`
  - updates `self.enable_downsampling`
  - emits `source_data_changed_signal`
- Extend the refresh path so this signal also invalidates detail cache and re-renders visible intervals for the affected track(s).
- Prefer targeted invalidation over full-cache clearing if practical; if the existing `AsyncDetailFetcher.clear_cache(track_id=...)` prefix logic is incompatible with current cache keys, fix that path as part of the change.

## Likely Files
- [`C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/track_datasource.py`](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/track_datasource.py)
- [`C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/graphics/track_renderer.py`](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/graphics/track_renderer.py)
- [`C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/mixins/track_rendering_mixin.py`](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/mixins/track_rendering_mixin.py)
- Possibly [`C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/async_detail_fetcher.py`](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/async_detail_fetcher.py) for selective cache clearing robustness.

## Key Risk To Address
- Current cache keys are built from interval identity only, so a runtime downsampling change will otherwise keep serving stale lower-resolution data from cache. The plan should explicitly solve that either by invalidation or by folding downsampling settings into cache identity.