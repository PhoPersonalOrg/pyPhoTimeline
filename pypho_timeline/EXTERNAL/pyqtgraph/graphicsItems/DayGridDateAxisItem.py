"""
DateAxisItem subclass that draws a vertical grid line at each day boundary.
Enable the grid via setGrid(True) or the plot's showGrid(x=True).
"""

from .DateAxisItem import DateAxisItem
from . import DateAxisItem as _date_axis_module

DAY_GRID_ONLY_SPACING = -1
DAY_SPACING = _date_axis_module.DAY_SPACING

__all__ = ['DateAxisItemWithDayGrid']


class DateAxisItemWithDayGrid(DateAxisItem):
    """
    DateAxisItem that always draws a vertical grid line at each day boundary.
    Tick labels remain the same as the parent (adaptive date/time format).
    Call setGrid(True) on this axis (or showGrid(x=True) on the plot) to show the grid.
    """

    def tickValues(self, minVal, maxVal, size):
        levels = super(DateAxisItemWithDayGrid, self).tickValues(minVal, maxVal, size)
        first = ((minVal - self.utcOffset) // DAY_SPACING) * DAY_SPACING + self.utcOffset
        day_ticks = []
        t = first
        while t <= maxVal:
            day_ticks.append(t)
            t += DAY_SPACING
        if day_ticks:
            levels.insert(0, (DAY_GRID_ONLY_SPACING, day_ticks))
        return levels



    def tickStrings(self, values, scale, spacing):
        if spacing == DAY_GRID_ONLY_SPACING:
            return [''] * len(values)
        return super(DateAxisItemWithDayGrid, self).tickStrings(values, scale, spacing)
