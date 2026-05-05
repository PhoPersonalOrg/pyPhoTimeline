---
name: Single PDF export wiring
overview: Wire the two File-menu PDF actions to the main window with passthrough handlers, and add `SimpleTimelineWidget.export_all_tracks_as_single_pdf()` that renders all track widgets into one tall PDF while keeping the existing per-track multi-file behavior on the separate menu action.
todos:
  - id: wire-main-window
    content: Replace actionExport_track_as wiring with actionExportSingle_PDF_file + actionseparate_PDF_per_track handlers in MainTimelineWindow.initUI and add _on_export_single_pdf_file / _on_export_separate_pdf_per_track.
    status: completed
  - id: stacked-pdf-widget
    content: Add SimpleTimelineWidget.export_all_tracks_as_single_pdf() with save dialog and QPdfWriter/QPrinter single-page vertical stack; keep export_all_tracks_as_pdf for per-track files.
    status: completed
isProject: false
---

# Single vs separate PDF export

## Current state

- [MainTimelineWindow.ui](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\TimelineWindow\MainTimelineWindow.ui) already defines `menuExport_track_as` with children `actionExportSingle_PDF_file` and `actionseparate_PDF_per_track` (no `actionExport_track_as`).
- [MainTimelineWindow.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\TimelineWindow\MainTimelineWindow.py) `initUI()` still connects `actionExport_track_as` (lines 91–92), which is **not** present on the loaded UI, so **no PDF menu item is connected today**.
- [simple_timeline_widget.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\simple_timeline_widget.py) implements `export_track_widget_to_pdf` (one widget → one file) and `export_all_tracks_as_pdf` (save dialog once, then one PDF per track with `stem_{sanitized_track}.pdf`).

## Target behavior

| Menu action | Main window | Timeline widget |
|-------------|-------------|-----------------|
| `actionExportSingle_PDF_file` | New handler: resolve `self.timeline_widget`, call new method | New `export_all_tracks_as_single_pdf()` → one save dialog, one PDF with all tracks **stacked top-to-bottom** |
| `actionseparate_PDF_per_track` | Rename/refactor existing `_on_export_track_as` to match | Keep `export_all_tracks_as_pdf()` as-is |

## Implementation

### 1. [MainTimelineWindow.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\TimelineWindow\MainTimelineWindow.py) — `initUI`

- Remove the `actionExport_track_as` block.
- If `actionExportSingle_PDF_file` exists: `triggered.connect(self._on_export_single_pdf_file)` (name can match your preference).
- If `actionseparate_PDF_per_track` exists: `triggered.connect(self._on_export_separate_pdf_per_track)`.

### 2. [MainTimelineWindow.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\TimelineWindow\MainTimelineWindow.py) — handlers

- **`_on_export_separate_pdf_per_track`**: Same body as current `_on_export_track_as` (guard `timeline_widget` + `export_all_tracks_as_pdf`, try/except, success `QMessageBox` with count/parent folder). Adjust dialog title string if desired (e.g. “separate PDF per track”).
- **`_on_export_single_pdf_file`**: Same pattern but call `tw.export_all_tracks_as_single_pdf()` (or the exact name you choose), `hasattr` check for that method, success message with the single output path.

### 3. [simple_timeline_widget.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\simple_timeline_widget.py) — `export_all_tracks_as_single_pdf`

- **Order**: Iterate `track_names = list(self.track_renderers.keys())` (same order as separate export).
- **Dialog**: `QFileDialog.getSaveFileName` with a title like “Export timeline as single PDF”, default `timeline_export.pdf`, same filter as `export_all_tracks_as_pdf`.
- **Early exit**: No tracks or user cancels → return `None` or empty (match return type you use in the handler; `Optional[Path]` is clear).
- **Rendering strategy** (one document, vertical stack):
  - Resolve each `widget` from `self.ui.matplotlib_view_widgets.get(track_name)`; skip or error if missing (same as single-track export).
  - Compute a **single page** layout: `page_w = max(widget.width())` over tracks (minimum 1), `gap` a few pixels; for each track compute scaled height so each track is drawn at **uniform width** `page_w` (scale = `page_w / widget.width()`), then `page_h = sum(scaled_heights) + gaps`.
  - Use **`QPdfWriter` when available** (same pattern as `export_track_widget_to_pdf`): before `painter.begin`, set page size to match `page_w` × `page_h` in logical units (e.g. `setPageSize(QPagedPaintDevice.PageSize.Custom)` + `setPageSizeMM` using mm from pixels at `writer.resolution()`, or the Qt6 `QPageSize` API if the project already uses it—keep consistent with your Qt/qtpy version).
  - `QPainter.begin(device)`, then for each track: `painter.save()`, `translate(0, y_cursor)`, `scale(s, s)`, `widget.render(painter)`, `restore()`, advance `y_cursor`.
  - **Fallback** when `QPdfWriter` is missing: use `QPrinter` with `setOutputFormat(PdfFormat)` and set a custom paper size in mm matching `page_w`/`page_h`, same paint loop.
- Optionally **factor** a tiny shared helper for “open PDF paint device for path” used by both single-track and stacked export to avoid duplicating the QPrinter fallback, only if it stays minimal.

### 4. Tests / manual check

- File → Export track as… → **single PDF file**: one file, stacked tracks in visual order.
- **separate PDF per track**: unchanged multi-file behavior and naming.

## Notes

- No `.ui` edits required unless you want copy/tooltip tweaks; actions already exist.
- Very tall timelines produce large page heights; PDF allows large pages, but if you ever hit engine limits, the fallback would be multi-page (out of scope unless you see failures).
