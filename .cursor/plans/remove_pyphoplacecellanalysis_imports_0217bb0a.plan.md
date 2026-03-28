---
name: Remove pyphoplacecellanalysis imports
overview: "Fix `ModuleNotFoundError: pyphoplacecellanalysis` by pointing vendored pyqtgraph extension modules at `pypho_timeline.EXTERNAL.pyqtgraph`, and harden `ColorButton` so parametertree/flowchart paths do not require that package."
todos:
  - id: swap-pg-imports
    content: Replace pyphoplacecellanalysis.External.pyqtgraph with pypho_timeline.EXTERNAL.pyqtgraph in DraggableGraphicsWidgetMixin, IntervalRectsItem, CustomIntervalRectsItem
    status: completed
  - id: colorbutton-fallback
    content: Add try/except in ColorButton.py for ColorPickerDialog vs QtWidgets.QColorDialog
    status: completed
  - id: verify-imports
    content: Run minimal python -c import checks for mixin, ColorButton, and pypho_timeline package
    status: completed
isProject: false
---

# Remove stray `pyphoplacecellanalysis` imports from pyPhoTimeline

## Cause

Your notebook imports `[PhoPyMNEHelper](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\motion_data.py)`, which pulls in `pypho_timeline.utils.datetime_helpers`. That loads `[pypho_timeline/__init__.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\__init__.py)`, which eagerly imports `[PyqtgraphTimeSynchronizedWidget](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\core\pyqtgraph_time_synchronized_widget.py)`, which imports `[DraggableGraphicsWidgetMixin](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph_extensions\mixins\DraggableGraphicsWidgetMixin.py)`. That mixin still does:

```python
import pyphoplacecellanalysis.External.pyqtgraph as pg
```

The project already vendors pyqtgraph under `pypho_timeline.EXTERNAL.pyqtgraph`; this is a leftover import from the upstream repo.

```mermaid
flowchart LR
  notebook --> PhoPyMNEHelper
  PhoPyMNEHelper --> motion_data
  motion_data --> pypho_timeline_utils
  pypho_timeline_utils --> pypho_timeline_init
  pypho_timeline_init --> PyqtgraphTimeSynchronizedWidget
  PyqtgraphTimeSynchronizedWidget --> DraggableGraphicsWidgetMixin
  DraggableGraphicsWidgetMixin --> badImport["pyphoplacecellanalysis..."]
```



## Changes (runtime imports)

**1. Replace pyqtgraph shim in three extension modules** — single-line change in each file, matching the pattern already used on the next line for `QtCore` / `QtGui` / `QtWidgets`:


| File                                                                                                                                                                            | Replace                                                                                                     |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `[DraggableGraphicsWidgetMixin.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph_extensions\mixins\DraggableGraphicsWidgetMixin.py)` | `import pyphoplacecellanalysis.External.pyqtgraph as pg` → `import pypho_timeline.EXTERNAL.pyqtgraph as pg` |
| `[IntervalRectsItem.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph_extensions\graphicsObjects\IntervalRectsItem.py)`              | same                                                                                                        |
| `[CustomIntervalRectsItem.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph_extensions\graphicsObjects\CustomIntervalRectsItem.py)`  | same                                                                                                        |


The remaining `pyphoplacecellanalysis...` strings in those files are inside **docstrings / comments** (usage examples and `related_items` metadata), not executed code — optional to rewrite later for documentation accuracy only.

**2. Harden `[ColorButton.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph\widgets\ColorButton.py)`** — it currently has a **hard** import:

```python
from pyphoplacecellanalysis.External.pyqt_color_picker.colorPickerDialog import ColorPickerDialog
```

This is pulled in by `[parametertree/parameterTypes/color.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph\parametertree\parameterTypes\color.py)` and `[flowchart/library/common.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph\flowchart\library\common.py)` whenever those features load. Fix: `try`/`except ImportError` — use `ColorPickerDialog` when present, otherwise `QtWidgets.QColorDialog()` with the same signal hooks already used (`currentColorChanged`, `rejected`, `colorSelected`, `setCurrentColor`, `open()`).

## Already safe (no change required)

- `[dock_display_configs.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\docking\dock_display_configs.py)`: `DisplayColorsEnum` is behind `try`/`except` with a local stub fallback.
- `[JoystickButton.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\EXTERNAL\pyqtgraph\widgets\JoystickButton.py)`: only a docstring reference.

## Verification

After edits, from the pyPhoTimeline env run a minimal import chain equivalent to the notebook:

- `python -c "from pypho_timeline.EXTERNAL.pyqtgraph_extensions.mixins.DraggableGraphicsWidgetMixin import DraggableGraphicsWidgetMixin"`
- `python -c "from pypho_timeline.EXTERNAL.pyqtgraph.widgets.ColorButton import ColorButton"`
- `uv run python -c "import pypho_timeline"` (or the project’s usual `uv sync --all-extras` workflow)

Re-run the notebook cell that imports `HistoricalData` + `SimpleTimelineWidget`.

## Optional follow-up (not required to fix this traceback)

- **PhoPyMNEHelper** `[motion_data.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\PhoPyMNEHelper\src\phopymnehelper\motion_data.py)` importing `pypho_timeline.utils.datetime_helpers` still triggers full `pypho_timeline` package init; if you want lighter coupling later, move the datetime helper to a tiny shared package or import a submodule that does not run `pypho_timeline/__init__.py`’s heavy exports (separate change).

