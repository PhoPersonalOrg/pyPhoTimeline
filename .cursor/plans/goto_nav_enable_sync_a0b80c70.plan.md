---
name: GoTo nav enable sync
overview: Extend `_update_interval_jump_buttons_enabled` in `SimpleTimelineWidget` so it drives enable state for both toolbar interval buttons and the main window Goto menu actions, using the same rules as the underlying jump handlers (prev/next interval targets; earliest/latest only when the viewport would change).
todos:
  - id: extract-earliest-latest-targets
    content: Add _target_window_start_go_earliest/latest and refactor go_to_earliest_window / go_to_latest_window to use them
    status: completed
  - id: expand-update-enabled
    content: "Extend _update_interval_jump_buttons_enabled: prev/next + parent actionGoTo* sync + equality checks for earliest/latest"
    status: completed
isProject: false
---

# Sync all GoTo / jump control enable states

## Current behavior

- `[simple_timeline_widget.py](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/simple_timeline_widget.py)` only toggles `jump_prev_interval_button` / `jump_next_interval_button` using `[_interval_jump_prev_next_targets](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/simple_timeline_widget.py)` (lines 306–316).
- `[MainTimelineWindow.py](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/TimelineWindow/MainTimelineWindow.py)` wires `actionGoTo*` to `[jump_to_previous_interval](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/simple_timeline_widget.py)` / `[jump_to_next_interval](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/simple_timeline_widget.py)` / `[go_to_earliest_window](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/simple_timeline_widget.py)` / `[go_to_latest_window](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/simple_timeline_widget.py)` but never updates `setEnabled` on those actions.
- `_update_interval_jump_buttons_enabled` is already invoked when tracks change (`[setupUI](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/simple_timeline_widget.py)` lines 224–227) and after window moves (`[simulate_window_scroll](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/simple_timeline_widget.py)`, `[apply_active_window_from_plot_x](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/simple_timeline_widget.py)` lines 466, 495), so extending this one method keeps menu and toolbar in sync without new connection points in `[timeline_builder.py](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/timeline_builder.py)`.

## Enable rules (consistent with existing handlers)


| Control                  | Enabled when                                                                                                                                               |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Prev / GoTo prev         | `_interval_jump_prev_next_targets()[0] is not None` (unchanged)                                                                                            |
| Next / GoTo next         | `_interval_jump_prev_next_targets()[1] is not None` (unchanged)                                                                                            |
| Earliest / GoTo earliest | Computed target start for “go earliest” differs from `active_window_start_time` (so the action would actually scroll). If already at that target, disable. |
| Latest / GoTo latest     | Same for “go latest” target vs current `active_window_start_time`.                                                                                         |


Use `_scalar_to_sort_float` for comparisons and a small epsilon (e.g. `1e-6`) on the float axis so float/datetime cases stay consistent.

## Implementation steps

1. **DRY the scroll targets for earliest/latest**
  Extract the “new start” computation from `[go_to_earliest_window](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/simple_timeline_widget.py)` and `[go_to_latest_window](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/simple_timeline_widget.py)` into two private methods (e.g. `_target_window_start_go_earliest` / `_target_window_start_go_latest`) that return the same scalar/datetime `new_start` the public methods would pass to `simulate_window_scroll`. Implement `go_to_*` as `self.simulate_window_scroll(self._target_window_start_go_*())` so behavior cannot drift from the enable logic.
2. **Generalize `_update_interval_jump_buttons_enabled`** (optional rename to `_update_goto_nav_enabled` for clarity; call sites can stay as-is if you prefer zero churn at call sites):
  - Keep the existing `hasattr(self.ui, 'jump_prev_interval_button')` guard and prev/next toolbar updates.  
  - Walk `parent = self.parentWidget()` until `parent` is `None` or has `actionGoToPrev` (duck-type the main window; avoids importing `MainTimelineWindow` and works for any host that exposes those actions).  
  - Set `actionGoToPrev` / `actionGoToNext` / `actionGoToEarliest` / `actionGoToLatest` with the four booleans above (each guarded with `hasattr`).
3. **Optional UX polish**
  If the parent has only some actions (partial UI), `hasattr` per action keeps this safe.

## Files touched

- `[pypho_timeline/widgets/simple_timeline_widget.py](C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/simple_timeline_widget.py)` only: helpers for earliest/latest targets, refactor `go_to_`*, expand `_update_interval_jump_buttons_enabled`.

## Verification

- Open a timeline with interval tracks: prev/next disable at first/last interval; after scrolling, menu and toolbar match.  
- At viewport already clamped to earliest/latest range ends, earliest/latest menu entries and (if added later) buttons disable.  
- Embed `SimpleTimelineWidget` without a Goto host: updater no-ops on missing actions; toolbar still works.

