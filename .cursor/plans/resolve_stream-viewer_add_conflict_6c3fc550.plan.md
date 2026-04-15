---
name: Resolve stream-viewer add conflict
overview: Make the smallest possible dependency change in stream_viewer so uv can resolve pyPhoTimeline + stream_viewer together.
todos:
  - id: edit-stream-viewer-cython
    content: Update stream_viewer pyproject Cython constraint to remove conflict with dose-analysis-python.
    status: completed
  - id: retest-uv-add
    content: Re-run uv add for editable stream_viewer in pyPhoTimeline and verify solver success.
    status: in_progress
  - id: sync-and-smoke
    content: Run uv sync --all-extras and a basic stream_viewer import check.
    status: pending
isProject: false
---

# Minimal dependency fix for editable add

## What is blocking `uv add ..\stream_viewer --editable`
`pyPhoTimeline` depends on `dose-analysis-python`, which pins `Cython>=0.29.34,<0.30`, while `stream_viewer` currently requires `cython>=3.2.3`. This creates an unsatisfiable solver graph.

## Proposed minimal change
- Edit only one line in [c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\pyproject.toml](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\pyproject.toml).
- Change `"cython>=3.2.3"` to a compatible requirement that does not conflict with `dose-analysis-python` (recommended: `"cython>=0.29.34"`).
- Keep all other dependencies untouched to minimize blast radius.

## Validation steps after the edit
- From [c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline), rerun `uv add ..\stream_viewer --editable`.
- Run `uv sync --all-extras` to ensure full environment resolution still succeeds.
- Optionally run a basic import smoke check: `python -c "import stream_viewer; print('ok')"`.

## Notes on risk
- This is packaging-only scope (no code changes).
- If any part of `stream_viewer` truly requires Cython 3-specific behavior, we can follow up by moving Cython to a narrower optional/dev context, but only if needed after this minimal fix.