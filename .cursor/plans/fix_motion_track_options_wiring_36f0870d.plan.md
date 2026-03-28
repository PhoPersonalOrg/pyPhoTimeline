---
name: Fix motion track options wiring
overview: Fix channel visibility from the dock options UI by building the options panel after `add_track` installs the real `TrackRenderer`, and correct the checkbox handler so visibility booleans are computed once from Qt `stateChanged`.
todos:
  - id: reorder-timeline-builder
    content: "In timeline_builder._add_tracks_to_timeline: remove early set_track_renderer(detail) + getOptionsPanel/dock refresh; after add_track, call getOptionsPanel + dock refresh"
    status: completed
  - id: fix-checkbox-handler
    content: "In track_options_panels.TrackChannelVisibilityOptionsPanel: pass raw state to _on_checkbox_changed; compute is_visible once vs CheckState.Checked"
    status: completed
isProject: false
---

# Fix motion track options panel → TrackRenderer wiring

## Problem (short)

`[getOptionsPanel()](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\core\pyqtgraph_time_synchronized_widget.py)` only connects `channelVisibilityChanged` → `TrackRenderer.update_channel_visibility` and `set_options_panel` when `self._track_renderer` is already a `**TrackRenderer**` (has `detail_renderer`). `[_add_tracks_to_timeline](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\timeline_builder.py)` currently sets the widget to the `**DetailRenderer**` only, calls `getOptionsPanel()` **before** `[timeline.add_track](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\mixins\track_rendering_mixin.py)`, which is when the mixin assigns the real `TrackRenderer`. The panel is created once (`options_panel is None`), so wiring never runs.

```mermaid
sequenceDiagram
  participant TB as timeline_builder
  participant W as PyqtgraphTimeSynchronizedWidget
  participant GP as getOptionsPanel
  participant AT as add_track
  participant TR as TrackRenderer

  TB->>W: set_track_renderer(DetailRenderer)
  TB->>GP: getOptionsPanel
  Note over GP: track_renderer is None; no visibility connect
  TB->>AT: add_track
  AT->>W: set_track_renderer(TrackRenderer)
  Note over W: panel already exists; no second GP
```



## Changes (minimal)

### 1. Reorder and drop the misleading detail-only `set_track_renderer` — [timeline_builder.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\timeline_builder.py)

Inside `_add_tracks_to_timeline` loop (≈1345–1395):

- **Remove** `track_widget.set_track_renderer(a_detail_renderer)` — it only makes `getOptionsPanel` treat the widget as detail-only; `[add_track` already calls `widget.set_track_renderer(track_renderer)](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\mixins\track_rendering_mixin.py)` with the full renderer.
- **Remove** the block that immediately follows today: `track_widget.optionsPanel = track_widget.getOptionsPanel()` plus `updateWidgetsHaveOptionsPanel` / `update` / `updateTitleBar` from that early position.
- **After** `timeline.add_track(datasource, name=a_track_name, plot_item=a_plot_item)` (and keep all existing `a_plot_item` x/y setup **before** `add_track` as today), **insert**:
  - `track_widget.optionsPanel = track_widget.getOptionsPanel()`
  - the same dock refresh trio: `a_dock.updateWidgetsHaveOptionsPanel()`, `a_dock.update()`, and the existing `updateTitleBar` guard.

This keeps x-range and axis setup order unchanged; only options wiring moves to after the track exists.

### 2. Fix checkbox → visibility boolean — [track_options_panels.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\track_options_panels.py)

The lambda already passes `state == QtCore.Qt.CheckState.Checked` (a **bool**), but `_on_checkbox_changed` compares that to `CheckState.Checked` again, which breaks checked/unchecked on many bindings.

- Change the `stateChanged` connection to pass `**state`** through:  
`lambda state, ch=channel_name: self._on_checkbox_changed(ch, state)`
- In `_on_checkbox_changed`, set  
`is_visible = (state == QtCore.Qt.CheckState.Checked)`  
(single source of truth; `state` is what `QCheckBox.stateChanged` emits under qtpy).

Optional: tighten the type hint/docstring for the second parameter to reflect `int`/enum-like state from Qt.

## Verification

- Build a timeline with a motion track via `TimelineBuilder` / `_add_tracks_to_uncertain: Open track options, toggle Gyro off, OK: plot should hide channels; toggling back on should show them.
- Notebook: `motion_track.update_channel_visibility(...)` should behave as before.

No new dependencies; two small edits total.