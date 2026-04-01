---
name: go_to_earliest_window wiring
overview: Add `go_to_earliest_window()` on `SimpleTimelineWidget` as the time-symmetric counterpart to `go_to_latest_window()`, then route `MainTimelineWindow`’s **Go to → Earliest** action through it (same pattern as Latest).
todos:
  - id: add-go-to-earliest-method
    content: Add `go_to_earliest_window` after `go_to_latest_window` in simple_timeline_widget.py (datetime + float branches, docstring)
    status: completed
  - id: wire-main-window
    content: Replace `_on_go_to_earliest` body with `go_to_earliest_window()` + hasattr mirror of `_on_go_to_latest`
    status: completed
isProject: false
---

# Implement and connect `go_to_earliest_window`

## Current state

- `[MainTimelineWindow.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\TimelineWindow\MainTimelineWindow.py)`: `actionGoToEarliest` is already connected to `_on_go_to_earliest`, but that handler calls `simulate_window_scroll(tw.total_data_start_time)` directly after duck-typing `simulate_window_scroll` / `total_data_start_time`.
- `[go_to_latest_window](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\simple_timeline_widget.py)` (lines 347–361): preserves window duration, aligns the **end** to `total_data_end_time`, and clamps **start** up to `total_data_start_time` if needed, then calls `simulate_window_scroll(new_start)`.

For a long viewport (duration larger than the data span), scrolling only to `total_data_start_time` preserves duration but can leave the window ending **after** `total_data_end_time`. The symmetric fix is to shift the window left when necessary, then apply the same lower clamp as Latest.

## 1. `SimpleTimelineWidget.go_to_earliest_window`

**File:** `[pypho_timeline/widgets/simple_timeline_widget.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\simple_timeline_widget.py)`

Add a new method **immediately after** `go_to_latest_window` (before the split-docks section):

- **Datetime / `pd.Timestamp` branch** (match `go_to_latest_window`’s `isinstance` checks):
  - `duration = active_window_end_time - active_window_start_time`
  - `new_start = total_data_start_time`
  - If `new_start + duration > total_data_end_time`: `new_start = total_data_end_time - duration`
  - If `new_start < total_data_start_time`: `new_start = total_data_start_time`
  - `simulate_window_scroll(new_start)`
- **Numeric branch:** same logic using `float(...)` on bounds (mirror the Latest float branch at 356–361).

**Docstring:** State that the viewport **start** is aligned to `total_data_start_time` when possible, duration is preserved, and if the window would extend past `total_data_end_time`, the start is moved earlier; if that would go before `total_data_start_time`, clamp start to `total_data_start_time` (parallel to Latest’s end alignment + clamp).

No change to `simulate_window_scroll` itself.

## 2. `MainTimelineWindow._on_go_to_earliest`

**File:** `[pypho_timeline/widgets/TimelineWindow/MainTimelineWindow.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\TimelineWindow\MainTimelineWindow.py)`

Align with `_on_go_to_latest`:

```python
def _on_go_to_earliest(self):
    tw = self.timeline_widget
    if tw is None:
        return
    if hasattr(tw, "go_to_earliest_window"):
        tw.go_to_earliest_window()
```

Remove the direct `simulate_window_scroll` / `total_data_start_time` duck-type path so there is a single API on the widget (consistent with Latest).

## Verification

- Manually: short window vs full span — earliest should match previous behavior (start at data start).
- Manually: window duration **greater** than `total_data_end - total_data_start` — earliest and latest should both reduce to the same clamped range (both methods converge to the same `new_start` in that edge case, analogous to Latest’s behavior).

