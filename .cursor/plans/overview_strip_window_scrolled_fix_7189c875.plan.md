---
name: Overview strip window_scrolled fix
overview: Emit `window_scrolled` when the overview minimap commits a viewport change so primary plots and `_last_applied` stay aligned with drag, preventing immediate reset of `CustomLinearRegionItem` by the deferred plot handler.
todos:
  - id: connect-overview-commit
    content: Change sigViewportChanged connect to apply_active_window_from_plot_x(x0,x1,False) in simple_timeline_widget.py add_timeline_overview_strip
    status: completed
isProject: false
---

# Fix overview strip viewport not sticking (emit `window_scrolled` on commit)

## Cause

`[add_timeline_overview_strip](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\simple_timeline_widget.py)` connects `strip.sigViewportChanged` to `apply_active_window_from_plot_x` with the default `**block_signals=True**`. That updates in-memory window state but **does not** emit `[window_scrolled](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\simple_timeline_widget.py)`. Primary `ViewBox` ranges therefore stay stale; `[TrackRenderingMixin._on_plot_viewport_changed](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\mixins\track_rendering_mixin.py)` soon calls `apply_active_window_from_plot_x(..., False)` with the **old** plot range, emits `window_scrolled`, and `[strip.set_viewport](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\timeline_overview_strip.py)` **undoes** the user drag.

## Fix (single connection change)

In `[simple_timeline_widget.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\simple_timeline_widget.py)` (~line 744), replace:

```python
strip.sigViewportChanged.connect(self.apply_active_window_from_plot_x)
```

with:

```python
strip.sigViewportChanged.connect(lambda x0, x1: self.apply_active_window_from_plot_x(x0, x1, False))
```

Committed overview edits then match plot-driven navigation: update canonical state, emit `window_scrolled`, drive `[on_window_changed` / `setXRange](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\core\pyqtgraph_time_synchronized_widget.py)`, `[TrackRenderingMixin_on_window_update](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\mixins\track_rendering_mixin.py)`, and `strip.set_viewport` (region update uses blocked signals on the item, so no loop from `sigViewportChanged`).

## Regression check (manual)

- Drag/resize overview region: it should stay put and primary tracks should match the new range.
- Pan primary track: overview region should still follow `window_scrolled` → `set_viewport`.
- Calendar/table `window_scrolled` listeners should stay in sync after overview edits.

