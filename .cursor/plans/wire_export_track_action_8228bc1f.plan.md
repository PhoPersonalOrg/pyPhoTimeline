---
name: Wire Export Track Action
overview: Implement `actionExport_track_as` in `MainTimelineWindow` as a passthrough to `SimpleTimelineWidget`, and add timeline-side export logic that writes all tracks as separate PDF files using a save dialog defaulting to `.pdf`.
todos:
  - id: wire-main-window-action
    content: Connect `actionExport_track_as` and add `_on_export_track_as` passthrough in `MainTimelineWindow.py`.
    status: completed
  - id: add-timeline-export-api
    content: Implement export-all-tracks PDF method(s) in `simple_timeline_widget.py` using save dialog base path and per-track filenames.
    status: completed
  - id: verify-behavior
    content: Validate cancel/success/error paths and run lints on touched files.
    status: completed
isProject: false
---

# Implement Export Track Passthrough

## Scope
Add menu wiring in [c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\TimelineWindow\MainTimelineWindow.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\TimelineWindow\MainTimelineWindow.py) and implement export behavior in [c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\simple_timeline_widget.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\simple_timeline_widget.py).

## Implementation Steps
- Wire `actionExport_track_as` in `MainTimelineWindow.initUI()` to a new handler (matching existing action wiring patterns already used for navigation and open-file actions).
- Add `MainTimelineWindow._on_export_track_as()` that:
  - safely resolves `tw = self.timeline_widget`
  - exits early if timeline is unavailable
  - calls a timeline passthrough method (new method on `SimpleTimelineWidget`) inside `try/except`
  - reports failures with logging + `QMessageBox.warning(...)` for user-visible feedback.
- Add a new `SimpleTimelineWidget` method to perform export-all-tracks workflow:
  - open `QFileDialog.getSaveFileName(...)` with default filter `PDF (*.pdf);;All files (*.*)`
  - treat selected file as a base path and export each track as `<base_stem>_<sanitized_track_name>.pdf`
  - iterate over `self.ui.matplotlib_view_widgets` to export each track widget separately
  - return list of written paths for caller feedback/logging.
- Add an internal helper in `SimpleTimelineWidget` for per-track PDF export to keep logic small and testable (resolve widget/plot surface and render to PDF via Qt paint/printer pipeline).
- Add optional success feedback in `MainTimelineWindow` (info dialog summarizing how many files were written) and keep behavior no-op when user cancels.

## Notes
- Existing save/export-adjacent patterns in `SimpleTimelineWidget` (e.g., `_on_save_track_options_clicked`) will be reused for dialog/flow consistency.
- File naming will avoid invalid filename characters by sanitizing track IDs.
- Minimal edits only: no UI file changes required since `actionExport_track_as` already exists in the menu.

## Validation
- Trigger `File -> Export track as...` and confirm save dialog defaults to `.pdf`.
- Confirm all visible tracks are exported as separate PDF files with suffixed track names.
- Confirm canceling the dialog causes no errors.
- Run lints for edited files and fix any introduced diagnostics.