---
name: QObject TimelineBuilder conformance
overview: "Bring `TimelineBuilder` in line with Qt/PySide expectations for `QObject` subclasses: import the base class and call `super().__init__(parent)` before other initialization, matching patterns already used in this package (e.g. `AsyncDetailFetcher`)."
todos:
  - id: import-qobject
    content: Add `from qtpy.QtCore import QObject` to timeline_builder.py imports
    status: completed
  - id: super-init
    content: Call `super().__init__(parent)` as first line of TimelineBuilder.__init__
    status: completed
  - id: docstring-parent
    content: "Update __init__ docstring: document `parent`; align log_to_console default text if desired"
    status: completed
  - id: verify-import
    content: Smoke-import TimelineBuilder via uv run python -c ...
    status: completed
isProject: false
---

# QObject subclass conformance for `TimelineBuilder`

## Problem

[`pypho_timeline/timeline_builder.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\timeline_builder.py) declares `class TimelineBuilder(QObject)` but:

1. **`QObject` is never imported** in the module (only `from qtpy import QtWidgets` appears). As written, the module should raise `NameError` when the class body executes unless something unusual injects `QObject` into the namespace. This is almost certainly an oversight.

2. **`__init__` does not call the `QObject` base initializer**, which breaks Qt’s object model (parent/child ownership, signals/slots metadata, etc.). Other QObjects in this repo call `super().__init__(parent)` first, e.g. [`async_detail_fetcher.py` lines 98–105](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\async_detail_fetcher.py).

## Intended changes (minimal)

1. **Add import** (consistent with nearby code that uses `qtpy`):

   - `from qtpy.QtCore import QObject`

   (Alternatively `from qtpy import QtCore` and inherit `QtCore.QObject`; either is fine; a direct `QObject` import keeps the class line readable.)

2. **At the very start of `TimelineBuilder.__init__`**, before assigning attributes or constructing `LogWidget`:

   - `super().__init__(parent)`

3. **Docstring touch-up** (same `__init__` block): document `parent` in the Args section (Qt convention: optional parent `QObject`). Optionally fix the mismatch where the docstring says `log_to_console` defaults to `True` but the signature uses `False` — small accuracy fix, same edit region.

## Optional follow-up (only if you want stricter ownership)

- Construct the log UI as a child of the builder: `LogWidget(parent=self)` **after** `super().__init__(parent)`, so the widget participates in the builder’s object tree when not reparented by docking code. This is behavior-adjacent; skip if you want the smallest possible diff.

## Call sites

All usages found are bare `TimelineBuilder()` with defaults ([`main_offline_timeline.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\main_offline_timeline.py), [`__main__.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\__main__.py), and internal helpers in `timeline_builder.py`). Adding `super().__init__(parent)` preserves existing behavior for `parent=None`.

## Verification

- Run a quick import check: `python -c "from pypho_timeline.timeline_builder import TimelineBuilder; TimelineBuilder()"` from the package environment (e.g. `uv run`) to confirm no `NameError` and clean startup.
