---
name: Fix EXTERNAL imports for pyPhoTimeline
overview: Update all imports in pypho_timeline/EXTERNAL/pyqtgraph and pypho_timeline/EXTERNAL/pyqtgraph_extensions so they use pyqtgraph (and, where needed, pypho_timeline) only, with no references to pyPhoPlaceCellAnalysis.
todos:
  - id: todo-1772402874663-2dqok86ke
    content: ""
    status: pending
  - id: dockarea-dock-py
    content: "dockarea/Dock.py: Replace both SynchronizedPlotMode imports with pypho_timeline.core.synchronized_plot_mode"
    status: completed
  - id: dockarea-upstream-qt
    content: "Qt/__init__.py: In docstring replace pyphoplacecellanalysis.External.pyqtgraph.Qt with pyqtgraph.Qt"
    status: completed
isProject: false
---

# Fix EXTERNAL pyqtgraph / pyqtgraph_extensions imports for pyPhoTimeline embedding

## Scope

- **In scope:** All Python files under [pypho_timeline/EXTERNAL/pyqtgraph](pypho_timeline/EXTERNAL/pyqtgraph) and [pypho_timeline/EXTERNAL/pyqtgraph_extensions](pypho_timeline/EXTERNAL/pyqtgraph_extensions). Replace every reference to `pyphoplacecellanalysis.External.pyqtgraph` or `pyphoplacecellanalysis.External.pyqtgraph_extensions` (and any other `pyPhoPlaceCellAnalysis` / `pyphoplacecellanalysis` references) so the embedded copy is self-contained for pyPhoTimeline.
- **Out of scope (not in the two folders):** [pypho_timeline/_embed/AlignableTextItem.py](pypho_timeline/_embed/AlignableTextItem.py) still has `from pyphoplacecellanalysis.External.pyqtgraph_extensions...` in a docstring and a lazy import; consider updating that file separately for consistency.

## Import strategy

- **pyqtgraph:** pyPhoTimeline already depends on `pyqtgraph>=0.13.7` and uses `import pyqtgraph as pg` elsewhere. Use `**pyqtgraph`** (and `from pyqtgraph...`) everywhere in EXTERNAL so the embedded examples and library code resolve to the same dependency.
- **pyqtgraph_extensions:** This tree lives under EXTERNAL and has **no `__init__.py`** files, so it is not currently a package. To support clean absolute imports without `pyPhoPlaceCellAnalysis`, make it a package under pyPhoTimeline and use `**pypho_timeline.EXTERNAL.pyqtgraph_extensions**` as the canonical name (see “Package layout” below).
- **SynchronizedPlotMode in Dock.py:** pyPhoTimeline defines `SynchronizedPlotMode` in [pypho_timeline/core/synchronized_plot_mode.py](pypho_timeline/core/synchronized_plot_mode.py). Use `**from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode`** in [pypho_timeline/EXTERNAL/pyqtgraph/dockarea/Dock.py](pypho_timeline/EXTERNAL/pyqtgraph/dockarea/Dock.py) instead of the pyPhoPlaceCellAnalysis GUI import.

## Package layout for pyqtgraph_extensions

- Add `**pypho_timeline/EXTERNAL/__init__.py`** and `**pypho_timeline/EXTERNAL/pyqtgraph_extensions/__init__.py`** (and `__init__.py` in subpackages that are imported: e.g. `mixins/`, `graphicsItems/`, `graphicsItems/TextItem/`, `graphicsItems/LabelItem/`, `PlotItem/`, `PlotWidget/`) so that `pypho_timeline.EXTERNAL.pyqtgraph_extensions` is a valid package.
- In [pyproject.toml](pyproject.toml), extend `[tool.setuptools]` **packages** to include the EXTERNAL packages (e.g. add `"pypho_timeline.EXTERNAL"`, `"pypho_timeline.EXTERNAL.pyqtgraph_extensions"`, and any subpackages, or use `setuptools.find_packages()` so they are installed and importable).

## Changes by location

### 1. EXTERNAL/pyqtgraph (library and non-example code)


| File                                                                                                           | Change                                                                                                                                                                                                                  |
| -------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Qt/**init**.py](pypho_timeline/EXTERNAL/pyqtgraph/Qt/__init__.py)                                             | Docstring: replace "pyphoplacecellanalysis.External.pyqtgraph.Qt" with "pyqtgraph.Qt".                                                                                                                                  |
| [flowchart/Flowchart.py](pypho_timeline/EXTERNAL/pyqtgraph/flowchart/Flowchart.py)                             | `package='pyphoplacecellanalysis.External.pyqtgraph.flowchart'` → `package='pyqtgraph.flowchart'`.                                                                                                                      |
| [imageview/ImageView.py](pypho_timeline/EXTERNAL/pyqtgraph/imageview/ImageView.py)                             | `package='pyphoplacecellanalysis.External.pyqtgraph.imageview'` → `package='pyqtgraph.imageview'`.                                                                                                                      |
| [widgets/RemoteGraphicsView.py](pypho_timeline/EXTERNAL/pyqtgraph/widgets/RemoteGraphicsView.py)               | `_import('pyphoplacecellanalysis.External.pyqtgraph')` → `_import('pyqtgraph')`; `_import('pyphoplacecellanalysis.External.pyqtgraph.widgets.RemoteGraphicsView')` → `_import('pyqtgraph.widgets.RemoteGraphicsView')`. |
| [multiprocess/processes.py](pypho_timeline/EXTERNAL/pyqtgraph/multiprocess/processes.py)                       | Docstring: "pyphoplacecellanalysis.External.pyqtgraph" → "pyqtgraph".                                                                                                                                                   |
| [exporters/CSVExporter.py](pypho_timeline/EXTERNAL/pyqtgraph/exporters/CSVExporter.py)                         | All four top-level imports: `pyphoplacecellanalysis.External.pyqtgraph` → `pyqtgraph`.                                                                                                                                  |
| [GraphicsScene/exportDialog.py](pypho_timeline/EXTERNAL/pyqtgraph/GraphicsScene/exportDialog.py)               | `package='pyphoplacecellanalysis.External.pyqtgraph.GraphicsScene'` → `package='pyqtgraph.GraphicsScene'`.                                                                                                              |
| [graphicsItems/ViewBox/ViewBoxMenu.py](pypho_timeline/EXTERNAL/pyqtgraph/graphicsItems/ViewBox/ViewBoxMenu.py) | `package='pyphoplacecellanalysis.External.pyqtgraph.graphicsItems.ViewBox'` → `package='pyqtgraph.graphicsItems.ViewBox'`.                                                                                              |
| [canvas/Canvas.py](pypho_timeline/EXTERNAL/pyqtgraph/canvas/Canvas.py)                                         | `package='pyphoplacecellanalysis.External.pyqtgraph.canvas'` → `package='pyqtgraph.canvas'`.                                                                                                                            |
| [dockarea/Dock.py](pypho_timeline/EXTERNAL/pyqtgraph/dockarea/Dock.py)                                         | Replace both `from pyphoplacecellanalysis.GUI.PyQtPlot.Widgets.SpikeRasterWidgets.Spike2DRaster import SynchronizedPlotMode` with `from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode`.        |
| [widgets/JoystickButton.py](pypho_timeline/EXTERNAL/pyqtgraph/widgets/JoystickButton.py)                       | Docstring: replace pyphoplacecellanalysis.External.pyqtgraph references with pyqtgraph.                                                                                                                                 |


### 2. EXTERNAL/pyqtgraph/examples (and subdirs)

- **Bulk replace:** In every example file under `EXTERNAL/pyqtgraph/examples/` (including subdirs like `optics/`, `verlet_chain/`, `cx_freeze/`, `py2exe/`): replace `pyphoplacecellanalysis.External.pyqtgraph` with `pyqtgraph` in all import and docstring lines. This affects many files (e.g. Plotting.py, ViewBox.py, RemoteGraphicsView.py, parametertree.py, Flowchart.py, ConsoleWidget.py, ImageView.py, VideoTemplate_*.py, etc.).
- **Comments that add sys.path for pyPhoPlaceCellAnalysis:** In examples that currently add the parent path to import from “pyphoplacecellanalysis” (e.g. ParameterTreeWidget.py, DockPlanningHelperWidget.py, EpochsEditorItem.py, BinnedImageRenderingWindow.py, DockPlanningHelperWindow.py), remove or reword those comments and the sys.path manipulation so they do not reference pyPhoPlaceCellAnalysis. For examples that **also** import from `pyphoplacecellanalysis.GUI` (e.g. `DockPlanningHelperWidget`, `ParameterTreeWidget`, `EpochsEditorItem`, `BinnedImageRenderingWindow`, `DockPlanningHelperWindow`): either (a) remove the pyPhoPlaceCellAnalysis-only import and guard the example with a try/except or comment that the full demo requires that package, or (b) remove/simplify the example so it only uses pyqtgraph (and, if applicable, pypho_timeline). Choose one approach and apply consistently.
- **cx_freeze/setup.py:** Use `import pyqtgraph` (not `pyphoplacecellanalysis.External.pyqtgraph`); then `pg_folder = Path(pyqtgraph.__file__).parent` (variable name is correct).
- **cx_freeze/plotTest.py, py2exe/plotTest.py:** Same as other examples: use `pyqtgraph` imports.

### 3. EXTERNAL/pyqtgraph_extensions

- **Make package:** Add `__init__.py` under EXTERNAL and EXTERNAL/pyqtgraph_extensions (and any imported subpackages: mixins, graphicsItems, graphicsItems/TextItem, graphicsItems/LabelItem, PlotItem, PlotWidget) so that `pypho_timeline.EXTERNAL.pyqtgraph_extensions` is importable.
- **Replace imports:** In every file under EXTERNAL/pyqtgraph_extensions:
  - `import pyphoplacecellanalysis.External.pyqtgraph as pg` → `import pyqtgraph as pg`.
  - `from pyphoplacecellanalysis.External.pyqtgraph_extensions....` → `from pypho_timeline.EXTERNAL.pyqtgraph_extensions....` (or use relative imports where appropriate, e.g. `from ..mixins.SelectableItemMixin import SelectableItemMixin` from within `graphicsItems/TextItem/`).
- **Files to update (from grep):**
  - [mixins/SelectableItemMixin.py](pypho_timeline/EXTERNAL/pyqtgraph_extensions/mixins/SelectableItemMixin.py): pg import + lazy re-import of SelectableItemMixin (use relative or `pypho_timeline.EXTERNAL.pyqtgraph_extensions.mixins.SelectableItemMixin`).
  - [graphicsItems/LabelItem/ClickableLabelItem.py](pypho_timeline/EXTERNAL/pyqtgraph_extensions/graphicsItems/LabelItem/ClickableLabelItem.py): pg + SelectableItemMixin + lazy SelectableLabelItem.
  - [graphicsItems/TextItem/AlignableTextItem.py](pypho_timeline/EXTERNAL/pyqtgraph_extensions/graphicsItems/TextItem/AlignableTextItem.py): pg + SelectableItemMixin + lazy CustomRectBoundedTextItem.
  - [graphicsItems/TextItem/SelectableTextItem.py](pypho_timeline/EXTERNAL/pyqtgraph_extensions/graphicsItems/TextItem/SelectableTextItem.py): SelectableItemMixin + lazy SelectableTextItem.
  - [PlotItem/SelectablePlotItem.py](pypho_timeline/EXTERNAL/pyqtgraph_extensions/PlotItem/SelectablePlotItem.py): pg + lazy SelectablePlotItem.
  - [PlotWidget/CustomPlotWidget.py](pypho_timeline/EXTERNAL/pyqtgraph_extensions/PlotWidget/CustomPlotWidget.py): docstring and try/except import block; use `pypho_timeline.EXTERNAL.pyqtgraph_extensions.PlotWidget.CustomPlotWidget` (or relative) and remove pyPhoPlaceCellAnalysis refs.
  - [trapezoid_callout.py](pypho_timeline/EXTERNAL/pyqtgraph_extensions/trapezoid_callout.py): docstring and lazy imports; use `pypho_timeline.EXTERNAL.pyqtgraph_extensions.trapezoid_callout` (or self-import) so there are no pyPhoPlaceCellAnalysis references.

### 4. setuptools

- In [pyproject.toml](pyproject.toml), ensure EXTERNAL and pyqtgraph_extensions are installed as part of the pypho_timeline package (e.g. add the appropriate package names to `tool.setuptools.packages` or switch to a find_packages-based list that includes `pypho_timeline.EXTERNAL` and its subpackages).

## Verification

- After edits, run: `grep -r "pyphoplacecellanalysis\|pyPhoPlaceCellAnalysis" pypho_timeline/EXTERNAL/` (or equivalent) and confirm no matches in the two folders.
- Run the test suite / a minimal import of `pyqtgraph` and `pypho_timeline.EXTERNAL.pyqtgraph_extensions` (and a widget that uses Dock + SynchronizedPlotMode) to ensure nothing is broken.

## TODO: Dockarea and upstream dependencies only

Required updates so that **only** the dockarea module and what it imports are free of pyPhoPlaceCellAnalysis references:

1. **[pypho_timeline/EXTERNAL/pyqtgraph/dockarea/Dock.py](pypho_timeline/EXTERNAL/pyqtgraph/dockarea/Dock.py)**
  Replace both occurrences of  
   `from pyphoplacecellanalysis.GUI.PyQtPlot.Widgets.SpikeRasterWidgets.Spike2DRaster import SynchronizedPlotMode`  
   with  
   `from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode`  
   (lines ~1027 and ~1094).
2. **[pypho_timeline/EXTERNAL/pyqtgraph/Qt/init.py](pypho_timeline/EXTERNAL/pyqtgraph/Qt/__init__.py)** (upstream dependency of dockarea)
  In the module docstring, replace  
   `pyphoplacecellanalysis.External.pyqtgraph.Qt`  
   with  
   `pyqtgraph.Qt`.

No other dockarea files (DockArea.py, DockDrop.py, Container.py, **init**.py) or their direct upstreams (e.g. widgets.VerticalLabel) contain pyPhoPlaceCellAnalysis references.

## Optional follow-up

- Update [pypho_timeline/_embed/AlignableTextItem.py](pypho_timeline/_embed/AlignableTextItem.py) so its docstring and lazy import use `pypho_timeline.EXTERNAL.pyqtgraph_extensions` (or the chosen canonical name) instead of `pyphoplacecellanalysis.External.pyqtgraph_extensions`, so the whole codebase is consistent.

