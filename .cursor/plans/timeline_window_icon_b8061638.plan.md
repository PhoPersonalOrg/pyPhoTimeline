---
name: Timeline window icon
overview: Use Qt’s window icon API (`QIcon` + `setWindowIcon`) and ship the `.ico`/`.png` inside the `pypho_timeline` package so the title bar and taskbar show your branding for the main window, standalone widget demos, and the live LSL window.
todos:
  - id: package-icons
    content: Add pypho_timeline/resources/ with .ico + .png; extend setuptools package-data in pyproject.toml
    status: completed
  - id: helper-qicon
    content: Add pypho_timeline/utils/window_icon.py (path resolve, QIcon, ico then png)
    status: completed
  - id: wire-windows
    content: Call setWindowIcon from MainTimelineWindow, SimpleTimelineWidget.__init__, LiveLSLTimeline
    status: completed
  - id: optional-app-icon
    content: "Optional: QApplication.setWindowIcon once for dialogs"
    status: completed
isProject: false
---

# Timeline window application icon

## How it works in Qt

- **Per window**: `[QWidget.setWindowIcon(QIcon)](https://doc.qt.io/qt-6/qwidget.html#windowIcon-prop)` sets the icon for that **top-level** window (title bar, taskbar entry on Windows, alt-tab, etc.).
- **Default for the whole app**: `QApplication.setWindowIcon(QIcon)` sets the fallback icon for windows that do not set their own (and can help some system UI stay consistent). Optional follow-up if you want dialogs to match without touching each window.
- **File choice**: On Windows, loading from `**[.ico](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/icons/pyPhoTimeline_Icon_Screenshot.ico)`** is ideal (multi-size). `**[.png](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/icons/pyPhoTimeline_Icon_Screenshot.png)**` works as a fallback via `QIcon(path)`.

## Current code paths


| Entry                                                                                             | Class                                                                                                                                                  | Where                                                                                                                                                |
| ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TimelineBuilder` XDF / datasource UI                                                             | `[MainTimelineWindow](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/TimelineWindow/MainTimelineWindow.py)`             | Created in `[timeline_builder.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/timeline_builder.py)` (~972); no icon today. |
| `__main__.py` / `[main.py](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/main.py)` demos | `[SimpleTimelineWidget](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/simple_timeline_widget.py)` shown with `.show()` | Top-level `QWidget` → needs its own `setWindowIcon`.                                                                                                 |
| Live LSL                                                                                          | `[LiveLSLTimeline](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/live_lsl_timeline.py)` (`QMainWindow`)                                       | Embeds `.SimpleTimelineWidget`; the **outer** `QMainWindow` owns the taskbar icon → set icon there.                                                  |


`setWindowIcon` on an **embedded** `SimpleTimelineWidget` is a no-op in Qt (not a window), so calling it from the widget’s `__init__` is safe and only affects standalone use.

## Implementation plan

1. **Ship assets inside the installable package**
  - Add a folder such as `[pypho_timeline/resources/](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline)` and copy (or move) `pyPhoTimeline_Icon_Screenshot.ico` and `.png` from the repo’s `[icons/](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/icons)` into it.  
  - Extend `[pyproject.toml](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pyproject.toml)` `[tool.setuptools.package-data]` so `pypho_timeline` includes those files (e.g. explicit paths under `resources/`), matching how only `py.typed` is bundled today.
2. **Small helper to resolve path and build `QIcon`**
  - New module e.g. `pypho_timeline/utils/window_icon.py`: resolve directory from `Path(__file__)`, prefer `.ico` if present else `.png`, return `qtpy.QtGui.QIcon(str(path))` (or null icon if missing — avoids hard failures in odd installs).
3. **Apply icon in the three owner types**
  - `[MainTimelineWindow.initUI](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/TimelineWindow/MainTimelineWindow.py)`: `self.setWindowIcon(...)`.  
  - `[SimpleTimelineWidget.__init_](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/pypho_timeline/widgets/simple_timeline_widget.py)_`: after UI setup, `self.setWindowIcon(...)` (standalone demos).  
  - `[LiveLSLTimeline.__init__](c:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/pyPhoTimeline/live_lsl_timeline.py)`: `self.setWindowIcon(...)`.
4. **Optional (same PR or later)**
  - Once, after `QApplication` exists: `QApplication.instance().setWindowIcon(icon)` so message boxes / file dialogs inherit the same icon. Easiest place: end of `MainTimelineWindow.initUI` and/or the first demo `main()` after `mkQApp` — or a single `ensure_default_app_icon()` with a module flag to avoid redundant work.

## Out of scope / notes

- **Frozen executables (PyInstaller etc.)**: you still set the `**.exe` icon** in the packager; runtime `QIcon` is separate but complementary.  
- **Embedding in other apps**: host app should set its own `QMainWindow` icon; library code only sets icons for library-owned top-level windows unless you also call `QApplication.setWindowIcon`.

