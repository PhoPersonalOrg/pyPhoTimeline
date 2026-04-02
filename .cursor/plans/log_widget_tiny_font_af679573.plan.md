---
name: Log widget tiny font
overview: Shrink the log viewer’s monospace font by lowering the QFont point size on `log_display` only; controls keep the default application font unless you want those matched later.
todos:
  - id: shrink-log-font
    content: "In log_widget.py _setup_ui: set QFont point size from 9 to 6 for Consolas and Courier fallback on log_display."
    status: completed
isProject: false
---

# Tiny font for log widget

## Current behavior

In `[pypho_timeline/widgets/log_widget.py](C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\log_widget.py)`, the log body is the only place an explicit font is set:

```135:139:C:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\log_widget.py
        # Use monospace font for better log readability
        font = QtGui.QFont("Consolas", 9)
        if not font.exactMatch():
            font = QtGui.QFont("Courier", 9)
        self.log_display.setFont(font)
```

Search field, labels, and buttons use the default stylesheet/application font.

## Change

- Replace point size **9** with **6** for both `Consolas` and `Courier` fallback (typical “tiny” UI text on Windows; still readable for monospace logs). If 6 feels too small on your monitor, **7** is the obvious middle step—easy one-line tweak after you try it.

No new dependencies, no API changes, no changes to `QtLogHandler` or log formatting.

## Out of scope (unless you ask)

- Matching the toolbar controls to the same tiny size (would require `setFont` on the individual widgets or a parent `font`/stylesheet).

