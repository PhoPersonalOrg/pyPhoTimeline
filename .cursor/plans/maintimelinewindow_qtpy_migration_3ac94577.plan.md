---
name: MainTimelineWindow qtpy migration
overview: Switch [MainTimelineWindow.py](pypho_timeline/widgets/TimelineWindow/MainTimelineWindow.py) from hardcoded `PyQt5` imports to `qtpy` so it follows the same binding as the rest of the package (`simple_timeline_widget`, `log_widget`, etc.) and works with PyQt6 or PyQt5 depending on `QT_API` / installed bindings.
todos:
  - id: imports-uic
    content: Swap PyQt5 imports for qtpy (QtWidgets + loadUi); drop unused symbols
    status: completed
  - id: exec-compat
    content: Use exec/exec_ compatibility in __main__ block
    status: completed
isProject: false
---

# MainTimelineWindow: PyQt5 → qtpy

## Current state

- [MainTimelineWindow.py](pypho_timeline/widgets/TimelineWindow/MainTimelineWindow.py) imports `PyQt5` for `uic`, widgets, gui, and core. The project already depends on `**qtpy>=2.0.0**` and `**pyqt6**` ([pyproject.toml](pyproject.toml)); other widgets use `qtpy` (e.g. [log_widget.py](pypho_timeline/widgets/log_widget.py) with `QtCore.Signal`, [simple_timeline_widget.py](pypho_timeline/widgets/simple_timeline_widget.py)).
- The class body only needs: `**QMainWindow**`, `**QVBoxLayout**`, `**QApplication**`, and `**loadUi**`. The long widget/gui/core import lists are unused (no `pyqtSignal` / `QPainter` / etc. in this file).

## Implementation

1. **Replace imports**
  - `from qtpy.uic import loadUi` (or `from qtpy import uic` and keep `uic.loadUi` — either is fine; prefer `loadUi` directly to match common qtpy examples).
  - `from qtpy import QtWidgets` and import only what is used: `QApplication`, `QMainWindow`, `QVBoxLayout` (single-line imports per your style).
2. **Load UI**
  - Change `self.ui = uic.loadUi(uiFile, self)` to `self.ui = loadUi(uiFile, self)` if using a direct `loadUi` import.
3. `**if __name__ == "__main__"` event loop**
  - PyQt6 uses `app.exec()`; PyQt5 uses `app.exec_()`. Mirror the existing project pattern in [timeline_overview_strip.py](pypho_timeline/widgets/timeline_overview_strip.py):
   `raise SystemExit(app.exec() if hasattr(app, "exec") else app.exec_())`
   (or the equivalent `sys.exit(...)` one-liner).

## Out of scope (unless you ask)

- **[main**.py](pypho_timeline/__main__.py) still uses `app.exec_()`; updating it would align the whole app with PyQt6 but is separate from this file-only request.
- Regenerating `.py` from `.ui` via a VSCode extension may reintroduce `PyQt5`; keep the hand-edited qtpy imports after regeneration or adjust the generator template.

## Verification

- Run the window entry path (`python -m pypho_timeline` or the `__main`__ block in this module after `uv sync`) with your intended `QT_API` (e.g. `pyqt6` per current dependencies) and confirm the UI loads and the log/toggle/actions still work.

