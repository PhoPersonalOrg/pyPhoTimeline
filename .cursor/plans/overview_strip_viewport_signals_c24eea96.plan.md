---
name: Overview strip viewport signals
overview: "Forward `CustomLinearRegionItem` live region updates to a dedicated widget signal, keep committed updates on `sigViewportChanged`, refactor shared clamp/emit logic, and add a runnable `__main__` demo. Optional: document interaction (left-drag pan vs edges)."
todos:
  - id: refactor-clamp-emit
    content: Add sigViewportLiveChanged; refactor clamp/emit into _read_clamp_emit_viewport(live); wire sigRegionChanged + sigRegionChangeFinished
    status: completed
  - id: docstrings
    content: Update TimelineOverviewStrip docstring for signals and left-drag / edge-resize behavior
    status: completed
  - id: main-demo
    content: Add if __name__ == '__main__' block with QApplication, rebuild empty strip, signal handlers, show/exec
    status: completed
isProject: false
---

# TimelineOverviewStrip: adjustable region + signals + `__main__`

## Current behavior

- `[timeline_overview_strip.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\timeline_overview_strip.py)` builds a `**CustomLinearRegionItem**` with `movable=True` and custom `**end_lines_crit**` so **left-button** drags resize the vertical edges (instead of the class default right-button on handles). The filled band uses the class default (**left / middle** translate). This is already “user-adjustable” in principle.
- Only `**sigRegionChangeFinished`** is connected (line 55), so `**sigRegionChanged`** (continuous updates while dragging) is not surfaced at the widget level.
- `[CustomLinearRegionItem](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph_extensions\graphicsObjects\CustomLinearRegionItem.py)` and base `[LinearRegionItem](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph\graphicsItems\LinearRegionItem.py)` emit `**sigRegionChanged**` during line/body moves and `**sigRegionChangeFinished**` when a gesture completes.

## Design choice: two signals (avoid feedback while dragging)

`[simple_timeline_widget.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\simple_timeline_widget.py)` connects `**strip.sigViewportChanged` → `apply_active_window_from_plot_x**`, which emits `**window_scrolled` → `strip.set_viewport**`. That path calls `**setRegion**` on every emission.

If `**sigViewportChanged**` were fired on every `**sigRegionChanged**` during a drag, `**set_viewport**` could repeatedly reset the region while the user is still dragging, causing jitter or fighting the gesture. So:

- Keep `**sigViewportChanged(float, float)**` for **committed** changes: connect to `**sigRegionChangeFinished`** only (current semantics; still runs clamp logic).
- Add `**sigViewportLiveChanged(float, float)`** (name can be adjusted): connect to `**sigRegionChanged**`, same normalized/clamp path as today, for subscribers that want **scrubbing** updates without forcing that through the main timeline loop unless they choose to.

Document in the class docstring that integrators like `SimpleTimelineWidget` should keep using `**sigViewportChanged`** only unless they explicitly want live coupling.

## Implementation steps (single file focus)

**File:** `[pypho_timeline/widgets/timeline_overview_strip.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\timeline_overview_strip.py)`

1. **Declare** `sigViewportLiveChanged = QtCore.Signal(float, float)` next to `sigViewportChanged`.
2. **Refactor** the body of `_on_viewport_region_change_finished` into a private helper, e.g. `_read_clamp_emit_viewport(live: bool)`, that:
  - Reads `getRegion()`, normalizes `(x_lo, x_hi)`.
  - Applies the same **ViewBox x limit** clamp and optional `**setRegion`** correction with `**blockSignals(True)`** on `_viewport_region` as today.
  - Emits `**sigViewportLiveChanged**` if `live` else `**sigViewportChanged**`.
3. **Wire signals:**
  - `sigRegionChanged` → `_read_clamp_emit_viewport(live=True)` (thin slot or `functools.partial`).
  - `sigRegionChangeFinished` → `_read_clamp_emit_viewport(live=False)` (replace current `_on_viewport_region_change_finished` body).
4. **Docstring** updates: mention **live vs committed** signals; briefly note **left** drag on band (translate), **left** on edges (resize) given current `MouseInteractionCriteria`.

## `if __name__ == "__main__"` example

At the bottom of the same file (after the class), add a minimal **Qt** entry point using **qtpy** (already imported):

- Create `QApplication`.
- Instantiate `TimelineOverviewStrip()` (no `reference_datetime` needed for a trivial demo).
- Call `**rebuild([], lambda _n: None, (0.0, 3600.0))`** so the strip has empty rows but a valid **x** range and limits (see existing `n == 0` branch in `rebuild`).
- Connect `**sigViewportChanged`** and `**sigViewportLiveChanged`** to e.g. print or a `**QLabel**` / status text.
- `**strip.show()**` and `**app.exec()**` (or `exec_()` depending on qtpy backend).

No new dependencies; no changes required to `**simple_timeline_widget.py**` unless you later decide to subscribe to the live signal.

## Verification (manual)

- Run `python -m pypho_timeline.widgets.timeline_overview_strip` or `python path/to/timeline_overview_strip.py` (exact invocation depends on package layout); drag the shaded band and edges and confirm **live** prints/streaming updates and **finished** fires on release.
- In the full app, confirm **overview → main** sync still behaves as before (`**sigViewportChanged`** only).

