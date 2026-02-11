---
name: Timeline track interaction constraints
overview: Analysis of where plot/track user interaction constraints are set and verification that middle-click drag pans the timeline left/right only (no y-axis change) across all synced tracks.
todos: []
isProject: false
---

# Timeline track interaction constraints analysis

## Where user interaction constraints are set

### 1. Middle-click pan (x-only, y unchanged)

**Location:** [pypho_timeline/widgets/custom_graphics_layout_widget.py](pypho_timeline/widgets/custom_graphics_layout_widget.py) — `CustomViewBox.mouseDragEvent` (lines 241–256).

- **Current behavior:** Middle-click drag is already implemented as **x-only pan**:
  - On drag: `current_pos = self.mapSceneToView(ev.pos())`, `delta_x = current_pos.x() - self._drag_start_pos.x()`, then `self.translateBy(x=-delta_x, y=0)` so the y-axis is explicitly unchanged.
  - Cursor is set to `ClosedHandCursor` during drag and restored on finish.
- **Conclusion:** No change needed here; middle-click already pans left/right only and does not affect y.

### 2. ViewBox mouse enable flags (lock y for pan/zoom)

**Location 1 — Track plots (all timeline tracks):** [pypho_timeline/rendering/mixins/track_rendering_mixin.py](pypho_timeline/rendering/mixins/track_rendering_mixin.py) (lines 162–166).

- When a track is added, the plot’s ViewBox is configured with:
  - `viewbox = plot_item.getViewBox()`
  - `viewbox.setMouseEnabled(x=True, y=False)`
- This disables y for default ViewBox drag/pan behavior so only x is driven by mouse. Together with `CustomViewBox`’s custom middle-click handling, this keeps y untouched.

**Location 2 — Root plot of each widget:** [pypho_timeline/core/pyqtgraph_time_synchronized_widget.py](pypho_timeline/core/pyqtgraph_time_synchronized_widget.py) (line 237).

- During UI build, the root plot (each timeline track widget’s main plot) has:
  - `self.ui.root_plot.setMouseEnabled(x=True, y=False)` (PlotItem forwards to its ViewBox in pyqtgraph).
- Same effect: y is disabled for default interactions.

**Location 3 — Override that can re-enable y:** [pypho_timeline/core/pyqtgraph_time_synchronized_widget.py](pypho_timeline/core/pyqtgraph_time_synchronized_widget.py) (line 525).

- Inside `add_crosshairs()`:
  - `plot_item.getViewBox().setMouseEnabled(x=True, y=True)` is called.
- This is used when crosshairs are enabled on the root plot (see line 585: `add_crosshairs(plot_item=root_plot_item, ...)`). That **re-enables y** for that track’s ViewBox and can allow default drag/zoom to affect the y-axis, contradicting “do not affect the y-axis for any of the plots/tracks.”
- **Recommendation:** For timeline tracks, keep y disabled. Change this to `setMouseEnabled(x=True, y=False)` so crosshairs (which rely on mouse-move, not pan/zoom) still work while pan/zoom remain x-only. If a future non-timeline plot needs y interaction, that can be a separate branch (e.g. only set `y=True` when the plot is not a timeline track).

### 3. Other CustomViewBox behavior (for completeness)

- **Left-click drag:** Emits `sigLeftDrag` for timeline navigation (slider); does not call default pan (lines 203–242).
- **Right-click drag:** Calls `super().mouseDragEvent(ev, axis=axis)` — rectangular zoom (lines 199–201).
- **Initial mode:** `CustomViewBox.__init__` sets `self.setMouseMode(self.RectMode)` (line 155).

So the only interaction that pans the view is middle-click, and it is already x-only.

### 4. Timeline sync (pan propagates to all tracks)

**Location:** [pypho_timeline/docking/specific_dock_widget_mixin.py](pypho_timeline/docking/specific_dock_widget_mixin.py) (lines 128–157).

- For `SynchronizedPlotMode.TO_GLOBAL_DATA`, track plot items are X-linked: `plot_item.setXLink(master_plot_item)`.
- When one track’s ViewBox pans (e.g. via `CustomViewBox` middle-click and `translateBy`), its X range changes; pyqtgraph’s linked views update so all linked track ViewBoxes share the same X range. So panning one track pans the entire timeline.

---

## Summary


| Concern                        | Where set                                                                                                             | Status                                                                                     |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Middle-click = x-only pan      | `CustomViewBox.mouseDragEvent` (custom_graphics_layout_widget.py)                                                     | Already correct: `translateBy(x=-delta_x, y=0)`.                                           |
| Default drag does not affect y | `viewbox.setMouseEnabled(x=True, y=False)` in track_rendering_mixin + root plot in pyqtgraph_time_synchronized_widget | Correct for all tracks and root plot.                                                      |
| Override that re-enables y     | `add_crosshairs` in pyqtgraph_time_synchronized_widget (line 525)                                                     | **Fix:** Use `setMouseEnabled(x=True, y=False)` so timeline tracks never allow y pan/zoom. |
| Pan sync across tracks         | `setXLink(master_plot_item)` in specific_dock_widget_mixin                                                            | Correct; middle-click pan on any track moves the whole timeline.                           |


**Single code change recommended:** In [pypho_timeline/core/pyqtgraph_time_synchronized_widget.py](pypho_timeline/core/pyqtgraph_time_synchronized_widget.py), line 525, change `plot_item.getViewBox().setMouseEnabled(x=True, y=True)` to `plot_item.getViewBox().setMouseEnabled(x=True, y=False)` so that when crosshairs are added to a timeline track, the “no y-axis interaction” rule is preserved while keeping crosshair mouse-move behavior.