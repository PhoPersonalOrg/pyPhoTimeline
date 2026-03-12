---
name: DateAxisItem day grid subclass
overview: Add a DateAxisItem subclass that always draws vertical grid lines at each day boundary by prepending a dedicated tick level in tickValues() and suppressing labels for that level via tickStrings(), while keeping normal date tick labels from the parent.
todos: []
isProject: false
---

# Custom DateAxisItem with per-day vertical grid

## Context

- In pyqtgraph, grid lines are drawn by [AxisItem.generateDrawSpecs](pypho_timeline/EXTERNAL/pyqtgraph/graphicsItems/AxisItem.py): for each level returned by `tickValues()`, it draws a line at every tick position. When `setGrid(True)` is used, those lines extend across the full view (vertical lines for a bottom/top axis).
- [DateAxisItem.tickValues()](pypho_timeline/EXTERNAL/pyqtgraph/graphicsItems/DateAxisItem.py) returns tick levels that depend on zoom (months, days, hours, etc.). There is no built-in “always show grid at every day” option.
- The project already uses custom date axes (e.g. [AMPMDateAxisItem](pypho_timeline/utils/datetime_helpers.py) and usage in [pyqtgraph_time_synchronized_widget.py](pypho_timeline/core/pyqtgraph_time_synchronized_widget.py)).

## Approach

Add a subclass in the same file as `DateAxisItem` that:

1. **Overrides `tickValues(minVal, maxVal, size)**`
  Call `super().tickValues(...)` to get the usual date tick levels, then compute day-boundary positions in the same coordinate system (using `DAY_SPACING` and `self.utcOffset` as in [ZoomLevel.tickValues](pypho_timeline/EXTERNAL/pyqtgraph/graphicsItems/DateAxisItem.py) and the existing `makeSStepper(DAY_SPACING)` logic). Prepend a single tick level containing only these day-boundary values so that grid lines are drawn at each day. Use a **sentinel spacing value** (e.g. a constant like `DAY_GRID_ONLY_SPACING = -1`) for this level so it can be detected in `tickStrings()`.
2. **Overrides `tickStrings(values, scale, spacing)**`
  When `spacing == DAY_GRID_ONLY_SPACING`, return a list of empty strings so that no labels are drawn for the day-grid level (avoiding a label on every day). Otherwise call `super().tickStrings(...)`.
3. **Day-boundary computation**
  Align with existing date-axis semantics: axis range is in the same “local” seconds space as the parent (UTC seconds plus `utcOffset` for display). First day boundary at or before `minVal`:
  - `first = ((minVal - self.utcOffset) // DAY_SPACING) * DAY_SPACING + self.utcOffset`
  - Then add `DAY_SPACING` until the next value would be > `maxVal`.
   Optionally cap the number of day lines (e.g. if count > 365) to avoid performance issues when the range is many years; if capped, either skip adding the level or thin to every Nth day. Plan can leave this as a possible follow-up unless you want it in scope.
4. **Placement and API**
  - Define the new class (e.g. `DateAxisItemWithDayGrid`) in [DateAxisItem.py](pypho_timeline/EXTERNAL/pyqtgraph/graphicsItems/DateAxisItem.py), after `DateAxisItem`.
  - Add it to `__all`__ and keep the same constructor signature as `DateAxisItem` (orientation, utcOffset, **kwargs) so callers can swap it in.
  - Document that the grid is visible only when the axis has grid enabled (e.g. `axis.setGrid(True)` or `plot.showGrid(x=True)`).

## Files to change

- **[pypho_timeline/EXTERNAL/pyqtgraph/graphicsItems/DateAxisItem.py](pypho_timeline/EXTERNAL/pyqtgraph/graphicsItems/DateAxisItem.py)**  
  - Add a module-level constant for the sentinel spacing (e.g. `DAY_GRID_ONLY_SPACING = -1`).
  - Add class `DateAxisItemWithDayGrid(DateAxisItem)` with:
    - `tickValues()`: compute day boundaries, prepend `(DAY_GRID_ONLY_SPACING, day_ticks)` to the list returned by `super().tickValues(...)`.
    - `tickStrings()`: if `spacing == DAY_GRID_ONLY_SPACING` return `[''] * len(values)`, else `return super().tickStrings(...)`.
  - Update `__all`__ to include the new class.

## Usage (for docs / callers)

Replace the bottom axis with the new class and enable grid:

```python
from pypho_timeline.EXTERNAL.pyqtgraph.graphicsItems.DateAxisItem import DateAxisItemWithDayGrid
axis = DateAxisItemWithDayGrid(orientation='bottom', utcOffset=...)
plot.setAxisItems({'bottom': axis})
plot.showGrid(x=True)
```

No changes to PlotItem or AxisItem grid logic are required; the existing “grid at every tick” behavior will draw the vertical day lines.

## Optional refinement

- **Wide ranges:** If the visible range spans many years, consider only adding the day-grid level when the number of days is below a threshold (e.g. 400), or adding a constructor argument to enable/disable the day grid or set a max-day limit.

