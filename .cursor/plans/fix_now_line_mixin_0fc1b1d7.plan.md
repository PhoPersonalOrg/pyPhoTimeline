---
name: fix now line mixin
overview: Stabilize `NowCurrentDatetimeLineRenderingMixin` by fixing the line-creation method contract and verifying the mixin lifecycle methods operate safely when used by `EpochRenderingMixin`.
todos:
  - id: patch-return-contract
    content: Make `add_new_now_line_for_plot_item(...)` always return `vline` and clarify docstring.
    status: completed
  - id: run-targeted-checks
    content: Run lint/smoke validation for mixin lifecycle and now-line updates.
    status: completed
  - id: report-results
    content: Summarize what changed and whether the class now behaves correctly.
    status: completed
isProject: false
---

# Fix NowCurrentDatetimeLineRenderingMixin

## Findings
- In [`c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/mixins/epoch_rendering_mixin.py`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/mixins/epoch_rendering_mixin.py), `add_new_now_line_for_plot_item(...)` returns an existing line in the `else` path but returns nothing when it creates a new line.
- That inconsistent return contract can cause downstream `None` handling bugs for any caller expecting an `InfiniteLine` object regardless of create-vs-reuse path.

## Proposed Changes
- Update `add_new_now_line_for_plot_item(...)` to always return the `vline` it manages (both when newly created and when already present).
- Keep behavior otherwise unchanged (same item creation, pen setup, and storage in `self.plots.now_lines.now_line_items`).
- Add a short method doc clarification to state that the method always returns the line instance.

## Validation
- Run targeted checks in the same repo:
  - static/lint check for the touched file
  - a minimal runtime smoke path that calls mixin lifecycle in order (`on_init` -> `on_setup` -> `add_new_now_line_for_plot_item` -> `update_now_lines`) on an implementing widget.
- Confirm no behavioral regressions for existing callers in `EpochRenderingMixin_on_buildUI`.

## Scope Control
- Do not modify notebook files.
- Keep edits minimal and confined to the mixin file unless a direct call-site adjustment is required by return-type usage.