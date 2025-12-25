"""LiveWindowEventIntervalMonitoringMixin - Mixin for tracking intervals entering/exiting viewport.

Refactored from pyphoplacecellanalysis for use in pypho_timeline.
"""
from copy import deepcopy
from typing import Dict, List, Tuple, Optional
import pandas as pd

from qtpy import QtCore
from pyphocorehelpers.gui.Qt.ExceptionPrintingSlot import pyqtExceptionPrintingSlot
from pypho_timeline.utils.indexing_helpers import PandasHelpers

# Optional mixin - handle with try/except
try:
    from pyphoplacecellanalysis.GUI.PyQtPlot.Widgets.Mixins.ReprPrintableWidgetMixin import ReprPrintableItemMixin
except ImportError:
    # Fallback: create minimal stub if mixin not available
    class ReprPrintableItemMixin:
        pass


class LiveWindowEventIntervalMonitoringMixin(ReprPrintableItemMixin):
    """Implementors receive signals when the live viewport window changes, indicating that one of their items is entering/exiting the viewport.
    
    Sets:
        self._active_window_visible_intervals_dict
        
    Implementors must:
        self.LiveWindowEventIntervalMonitoringMixin_on_window_update(new_start, new_end)
        self.find_intervals_in_active_window() -> Dict[str, pd.DataFrame]
    """
    sigOnIntervalEnteredWindow = QtCore.Signal(object)  # pyqtSignal(object)
    sigOnIntervalExitedindow = QtCore.Signal(object)
    
    @pyqtExceptionPrintingSlot()
    def LiveWindowEventIntervalMonitoringMixin_on_init(self):
        """Perform any parameters setting/checking during init."""
        self._active_window_visible_intervals_dict = {}

    @pyqtExceptionPrintingSlot()
    def LiveWindowEventIntervalMonitoringMixin_on_setup(self):
        """Perform setup/creation of widget/graphical/data objects. Only the core objects are expected to exist on the implementor (root widget, etc)."""
        pass

    @pyqtExceptionPrintingSlot()
    def LiveWindowEventIntervalMonitoringMixin_on_buildUI(self):
        """Perform setup/creation of widget/graphical/data objects. Only the core objects are expected to exist on the implementor (root widget, etc)."""
        if not hasattr(self, '_active_window_visible_intervals_dict'):
            self.LiveWindowEventIntervalMonitoringMixin_on_init()
            self.LiveWindowEventIntervalMonitoringMixin_on_setup()
            
        connections = {}
        connections['LiveWindowEventIntervalMonitoringMixin_entered'] = self.sigOnIntervalEnteredWindow.connect(self.on_visible_event_intervals_added)
        connections['LiveWindowEventIntervalMonitoringMixin_exited'] = self.sigOnIntervalExitedindow.connect(self.on_visible_event_intervals_removed)

    @pyqtExceptionPrintingSlot()
    def LiveWindowEventIntervalMonitoringMixin_on_destroy(self):
        """Perform teardown/destruction of anything that needs to be manually removed or released."""
        pass

    @pyqtExceptionPrintingSlot(float, float)
    def LiveWindowEventIntervalMonitoringMixin_on_window_update(self, new_start=None, new_end=None):
        """Called to perform updates when the active window changes. Redraw, recompute data, etc."""
        self.on_visible_intervals_changed()
            
    @pyqtExceptionPrintingSlot(object)
    def LiveWindowEventIntervalMonitoringMixin_on_window_update_rate_limited(self, evt):
        self.LiveWindowEventIntervalMonitoringMixin_on_window_update(*evt)

    @property
    def active_window_visible_intervals_dict(self):
        """The active_window_visible_intervals_dict property."""
        return self._active_window_visible_intervals_dict
    @active_window_visible_intervals_dict.setter
    def active_window_visible_intervals_dict(self, value):
        self._active_window_visible_intervals_dict = value

    def find_intervals_in_active_window(self, debug_print=False) -> Dict[str, pd.DataFrame]:
        """Find intervals that are currently in the active window.
        
        Must be implemented by subclasses.
        
        Returns:
            Dict[str, pd.DataFrame]: Dictionary mapping interval series names to DataFrames of intervals in the active window
        """
        raise NotImplementedError(f'Implementors must override!')

    @pyqtExceptionPrintingSlot()
    def on_visible_intervals_changed(self):
        """Called to get the changes after intervals are updated."""
        print(f'LiveWindowEventIntervalMonitoringMixin.on_visible_intervals_changed()')
        all_live_window_included_intervals_dict = self.find_intervals_in_active_window()

        curr_all_live_window_visible_interval_changes_dict: Dict[str, Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]] = {}  # current changes dict

        added_rows_dict: Dict[str, pd.DataFrame] = {}
        removed_rows_dict: Dict[str, pd.DataFrame] = {}

        for dataseries_name, intervals_df in all_live_window_included_intervals_dict.items():
            extant_intervals_df = self.active_window_visible_intervals_dict.get(dataseries_name, PandasHelpers.empty_df_like(intervals_df))
            
            # INPUTS: intervals_df, extant_intervals_df
            curr_all_live_window_visible_interval_changes_dict[dataseries_name] = PandasHelpers.get_df_row_changes(potentially_updated_df=intervals_df, prev_df=extant_intervals_df) 
            (added_rows, same_rows, removed_rows) = curr_all_live_window_visible_interval_changes_dict[dataseries_name]
            if len(added_rows) > 0:
                added_rows_dict[dataseries_name] = added_rows
            if len(removed_rows) > 0:
                removed_rows_dict[dataseries_name] = removed_rows

        # OUTPUTS: curr_all_live_window_visible_interval_changes_dict
        # done with update
        self.active_window_visible_intervals_dict = deepcopy(all_live_window_included_intervals_dict)
        if len(added_rows_dict) > 0:
            self.sigOnIntervalEnteredWindow.emit(added_rows_dict)
        if len(removed_rows_dict) > 0:
            self.sigOnIntervalExitedindow.emit(removed_rows_dict)

    @pyqtExceptionPrintingSlot(object)
    def on_visible_event_intervals_added(self, added_rows):
        """Called when intervals enter the active window."""
        print(f'LiveWindowEventIntervalMonitoringMixin.on_visible_event_intervals_added(added_rows: {added_rows})')
        
    @pyqtExceptionPrintingSlot(object)
    def on_visible_event_intervals_removed(self, removed_rows):
        """Called when intervals exit the active window."""
        print(f'LiveWindowEventIntervalMonitoringMixin.visible_event_intervals_removed(removed_rows: {removed_rows})')

