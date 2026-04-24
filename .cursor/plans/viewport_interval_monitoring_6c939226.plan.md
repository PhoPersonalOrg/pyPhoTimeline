---
name: viewport interval monitoring
overview: Verify and minimally complete the live-window interval monitoring path for `EpochRenderingMixin`/`TrackRenderingMixin` so viewport interval enter/exit detection actually runs.
todos:
  - id: pick-datasource-scope
    content: Decide whether live-window monitoring should cover only `interval_datasources` or also `track_datasources`.
    status: completed
  - id: implement-window-query
    content: Implement `find_intervals_in_active_window()` using the current active window and datasource `get_updated_data_window(...)`.
    status: completed
  - id: chain-window-update
    content: Forward `TrackRenderingMixin_on_window_update()` into `EpochRenderingMixin_on_window_update()` after track renderer updates.
    status: completed
isProject: false
---

# Viewport Interval Monitoring

## Findings
- `LiveWindowEventIntervalMonitoringMixin` is only partially integrated. `find_intervals_in_active_window()` is still abstract in `pypho_timeline/rendering/mixins/live_window_monitoring_mixin.py` and is not overridden anywhere.
- `TrackRenderingMixin_on_window_update()` is the real viewport update hook wired from `window_scrolled`, but it does not forward to `EpochRenderingMixin_on_window_update()`. That means the live-window mixin never runs during normal scrolling.
- `TrackRenderer.update_viewport()` already has its own separate per-track viewport interval detection for async detail loading, so the missing mixin path is mainly a generic interval enter/exit event path, not the existing track-detail loader.

## Minimum Change
- Add a concrete `find_intervals_in_active_window()` implementation on the lowest practical concrete layer, preferably `pypho_timeline/rendering/mixins/track_rendering_mixin.py` or `pypho_timeline/widgets/simple_timeline_widget.py`.
- Use the current active window (`self.active_window_start_time` / `self.active_window_end_time` or `self.spikes_window.active_time_window`) and query each datasource with `get_updated_data_window(start, end)`.
- Return a `Dict[str, pd.DataFrame]` keyed by datasource name.
- In `TrackRenderingMixin_on_window_update()`, after `_schedule_track_group_window_update(...)`, call `self.EpochRenderingMixin_on_window_update(new_start, new_end)` so the live-window mixin receives the same window changes.

## Suggested Scope
- Prefer checking `self.interval_datasources` if the goal is to support intervals added through `add_rendered_intervals(...)`.
- If you also want track overview intervals to participate, either include `self.track_datasources` too or decide that track visibility remains owned by `TrackRenderer`.
- Keep this first pass minimal: do not refactor signal names, teardown, or duplicate signal declarations unless you specifically want cleanup.

## Optional Cleanup
- Fix `sigOnIntervalExitedindow` typo for readability.
- Store the signal connections created in `LiveWindowEventIntervalMonitoringMixin_on_buildUI()` if you want symmetrical teardown later.
- Remove or implement the `NotImplementedError` in `EpochRenderingMixin_on_destroy()` separately, since it is unrelated to viewport interval detection but can break destruction paths.
