---
name: Fix pg.Point TypeError
overview: The crash happens because the slim vendored pyqtgraph package never exports the `Point` class on the `pg` namespace, so `pg.Point` is the `Point` submodule and is not callable. Fix by restoring the export or by avoiding `pg.Point` at the call sites.
todos:
  - id: uncomment-point-export
    content: Uncomment `from .Point import Point` in pypho_timeline/EXTERNAL/pyqtgraph/__init__.py (recommended)
    status: completed
  - id: verify-video-track
    content: Re-run add_video_track / interval overview path to confirm labels build without TypeError
    status: completed
isProject: false
---

# Fix `TypeError: 'module' object is not callable` on `pg.Point`

## Cause

- [`AlignableTextItem.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\_embed\AlignableTextItem.py) uses `import pypho_timeline.EXTERNAL.pyqtgraph as pg` and calls `self.setAnchor(pg.Point(0.5, 0))` in `CustomRectBoundedTextItem.updatePosition` (around line 382).
- In [`pypho_timeline/EXTERNAL/pyqtgraph/__init__.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph\__init__.py), the stock line that binds the class is **commented out**:

```170:170:c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph\__init__.py
# from .Point import Point
```

- With that line absent, the name `Point` on the `pyqtgraph` package resolves to the **submodule** [`Point.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph\Point.py) (same as `import pyqtgraph.Point`), so `pg.Point(...)` tries to call a module.
- [`TextItem.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph\graphicsItems\TextItem.py) is unaffected: it does `from ..Point import Point` and `setAnchor` already accepts a sequence (`Point(anchor)` in `setAnchor`).

```3:5:c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph\graphicsItems\TextItem.py
from .. import functions as fn
from ..Point import Point
from ..Qt import QtCore, QtGui, QtWidgets
```

## Recommended fix (single line, restores `pg` API)

Uncomment the export in the vendored root `__init__.py`:

- Change `# from .Point import Point` to `from .Point import Point` in [`pypho_timeline/EXTERNAL/pyqtgraph/__init__.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph\__init__.py) (same location as upstream pyqtgraph).

This makes `pg.Point` the real class for the whole project (matches user expectations and upstream pyqtgraph).

**Risk check:** `Point.py` only imports `.Qt`; graphics items already pull `Point` via relative imports, so this should not introduce a new circular import.

## Alternative (no `__init__.py` change)

If you prefer not to touch the vendored package surface:

1. In [`pypho_timeline/_embed/AlignableTextItem.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\_embed\AlignableTextItem.py), replace `self.setAnchor(pg.Point(0.5, 0))` with `self.setAnchor((0.5, 0))` (documented anchor format on `TextItem`).
2. Same for [`pypho_timeline/EXTERNAL/pyqtgraph_extensions/graphicsItems/TextItem/AlignableTextItem.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph_extensions\graphicsItems/TextItem\AlignableTextItem.py): `self.setAnchor((0.5, 0.5))` instead of `pg.Point(0.5, 0.5)` (line ~293).

Only two active call sites use `pg.Point(` in this repo (per search).

## Verification

- Re-run the notebook cell that calls `timeline.add_video_track(...)` (or a minimal import + `IntervalRectsItem` / `TrackRenderer` path that rebuilds labels).
- Optionally `python -c "import pypho_timeline.EXTERNAL.pyqtgraph as pg; print(pg.Point(0.5,0))"` to confirm `pg.Point` is the class.
