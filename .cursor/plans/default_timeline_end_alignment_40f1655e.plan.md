---
name: Default timeline end alignment
overview: The bottom overview minimap and main tracks follow the active time window from `SimpleTimelineWidget`. That window is currently initialized at `total_start_time` when `window_start_time` is omitted. Change the builder so the default window is aligned so its **end** matches the latest overview interval end across datasources (with sensible clamping), instead of starting at the earliest data boundary.
todos:
  - id: helper-max-end
    content: Add TimelineBuilder helper to compute max overview interval t_end across datasources (fallback None)
    status: completed
  - id: build-default-start
    content: In build_from_datasources datetime + float branches, replace total_start default with end-aligned clamped window_start_time when window_start_time is None
    status: completed
  - id: docstring
    content: Document new default for window_start_time in build_from_datasources
    status: completed
isProject: false
---

# Default scroll: align window end to last overview interval

## Root cause

In `[timeline_builder.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/timeline_builder.py)`, `build_from_datasources` sets the initial window when `window_start_time is None`:

```853:855:c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/timeline_builder.py
            # Calculate window start time if not provided
            if window_start_time is None:
                window_start_time = total_start_time
```

(and the analogous float branch at lines 873–875). That makes the viewport start at the **earliest** merged data start, which matches what you see on the overview strip.

The strip itself is rebuilt in `[simple_timeline_widget.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/simple_timeline_widget.py)` via `_rebuild_timeline_overview_strip`, which then calls `strip.set_viewport(...)` from the active window — so fixing the **initial window** in the builder updates both the main tracks and the minimap.

## Intended behavior

When `window_start_time` is omitted:

1. Compute **anchor end**: maximum `t_end` over all non-empty `get_overview_intervals()` dataframes across `datasources` (same source as the colored blocks in `[timeline_overview_strip.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/timeline_overview_strip.py)` `rebuild`). Derive `t_end` via the `t_end` column, or `t_start + t_duration` when needed. If no overview rows exist, fall back to `total_end_time`.
2. Let `window_duration` already be resolved (existing logic: full span in seconds with a 10 s minimum, or caller-provided).
3. Set the window so it **ends** at `min(anchor_end, total_end_time)` (cap to global end), then:

- `desired_start = effective_end - window_duration` (timedelta for datetime mode; float subtraction for float mode).
- **Clamp**: if `window_duration >= total_end - total_start`, keep `window_start = total_start` (only one valid full-span placement). Otherwise `window_start = max(total_start, min(desired_start, total_end - window_duration))` so the window stays within the global range.

This matches “align with the end of the last interval epoch” for typical cases where the visible duration is smaller than the full merged span; when the window already spans all data, behavior stays the same.

## Implementation

- Add a small private helper on `TimelineBuilder` (e.g. `_max_overview_interval_end(datasources)`) returning `None` if no interval ends found, else a value comparable with `total_end_time` / timestamps.
- In `build_from_datasources`, replace the `window_start_time = total_start_time` assignment in **both** the datetime and float branches with a call to shared logic that computes the clamped start from `anchor_end` and existing `total_`* / `window_duration`.
- Update the docstring for `window_start_time` to state the new default (end-aligned to latest overview interval end).
- No changes required to `TimelineOverviewStrip` or `_rebuild_timeline_overview_strip` if the initial `spikes_window` is correct.

## Notes

- Callers who still want the old behavior can pass `window_start_time=total_start_time` explicitly.
- Direct use of `SimpleTimelineWidget(...)` without the builder is unchanged unless those call sites also omit a deliberate start.

