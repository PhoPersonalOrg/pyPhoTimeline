---
name: Fix video detail and labels
overview: Resolve long-running background video thumbnail processing and restore filename label rendering for video intervals with minimal, focused changes.
todos:
  - id: fix-sampling
    content: Correct Deffcode frame offset generation and timestamp shaping in video datasource
    status: completed
  - id: add-safety-guards
    content: Add bounded sampling and concise diagnostics for background detail fetches
    status: in_progress
  - id: harden-label-render
    content: Harden video label formatter and label propagation for interval data
    status: pending
  - id: verify
    content: Run focused tests/manual checks for detail completion time and label visibility
    status: pending
isProject: false
---

# Fix Video Thumbnail Processing And Filename Labels

## Goals
- Ensure background video thumbnail detail fetches complete in predictable time.
- Ensure video filename labels reliably render for video interval rectangles.
- Add lightweight diagnostics so future regressions are obvious.

## Proposed Changes
- Update thumbnail sampling math in [`c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/specific/video.py`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/datasources/specific/video.py):
  - Replace the Deffcode frame-offset generation that currently uses `target_n_frames / source_duration_sec` as `np.arange` step.
  - Generate exactly `target_n_frames` offsets (for example via `np.linspace(..., num=target_n_frames, endpoint=False)`) and guard invalid/zero durations.
  - Keep timestamp output shape consistent with the CV2 branch (flat list/array of scalar timestamps).
- Add safety bounds in the same file for Deffcode extraction:
  - Hard-cap maximum sampled offsets processed per interval even if upstream math regresses.
  - Add concise logging of target frame count and actual sampled offsets count.
- Make overview filename labels more robust in [`c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/graphics/track_renderer.py`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/graphics/track_renderer.py):
  - Preserve existing video-specific formatter path, but make formatter tolerant of non-`IntervalRectsItemData` inputs (fallback extraction instead of always empty string).
  - Add debug-level instrumentation for “formatter returned empty label” cases.
- Ensure label data exists before rendering in [`c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/helpers/render_rectangles_helper.py`](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/rendering/helpers/render_rectangles_helper.py) and/or `video.py`:
  - Maintain `label` propagation from `video_file_path` whenever available.
  - Avoid silently creating intervals with missing labels where path data exists.
- Add/adjust focused tests in the rendering datasource area (new test file under project test tree):
  - Verify Deffcode offset generation returns bounded count and does not scale with video duration squared.
  - Verify video interval label formatter emits expected filename when label/path fields are present.

## Verification
- Manual: open a timeline with long video intervals and confirm background detail rendering completes quickly.
- Manual: verify filename labels are visible on video intervals in overview mode.
- Automated: run targeted tests for video datasource/renderer behavior and confirm no regressions in related rendering tests.

## Scope Notes
- Keep edits minimal and local to video datasource + label formatting paths.
- Do not modify notebook files.