---
name: fix-now-line-update
overview: Replace the incorrect `InfiniteLine` API call in now-line updates and verify line creation/update works from notebook usage.
todos:
  - id: patch-mixin-api-call
    content: Replace `setPosition` with `setPos` in now-line update method.
    status: completed
  - id: runtime-smoke-check
    content: Verify creation/update path in notebook runs without exceptions and now-line items exist.
    status: completed
isProject: false
---

# Fix Now-Line Update Crash

## Goal
Resolve the runtime error in `update_now_lines()` where `InfiniteLine` is updated with a non-existent method, and ensure notebook usage works as expected.

## Targeted Changes
- Update [`c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/mixins/epoch_rendering_mixin.py`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/mixins/epoch_rendering_mixin.py):
  - In `NowCurrentDatetimeLineRenderingMixin.update_now_lines`, replace `vline.setPosition(...)` with `vline.setPos(...)`.
  - Keep the rest of the logic unchanged (minimal edit).

## Validation
- In notebook/runtime, call now-line creation + update path and confirm no exception:
  - Ensure now-lines exist (non-zero `len(timeline.plots.now_lines.now_line_items)`).
  - Run `timeline.update_now_lines()` and verify lines move without errors.
- Optional smoke check: pan/scroll timeline and re-run update to confirm continued behavior.

## Notes
- This is a direct API mismatch fix (`pyqtgraph.InfiniteLine` positioning) and should be low-risk.
- No notebook file edits required for this fix.