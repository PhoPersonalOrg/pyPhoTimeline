"""EpochRenderingMixin - Mixin for rendering time intervals/epochs as rectangles on timeline tracks.

Refactored from pyphoplacecellanalysis for use in pypho_timeline.
"""
from __future__ import annotations
from copy import deepcopy
from typing import Dict, List, Tuple, Optional, Callable, Union, Any
import numpy as np
import pandas as pd

from qtpy import QtCore
from pyphocorehelpers.print_helpers import SimplePrintable, PrettyPrintable, iPythonKeyCompletingMixin
from pyphocorehelpers.DataStructure.dynamic_parameters import DynamicParameters
from pypho_timeline.utils.indexing_helpers import PandasHelpers

from pyphocorehelpers.DataStructure.general_parameter_containers import DebugHelper, VisualizationParameters, RenderPlots, RenderPlotsData
from pyphocorehelpers.gui.PhoUIContainer import PhoUIContainer
from pyphocorehelpers.gui.Qt.connections_container import ConnectionsContainer
from pyphocorehelpers.gui.Qt.ExceptionPrintingSlot import pyqtExceptionPrintingSlot

from pypho_timeline.rendering.graphics.interval_rects_item import IntervalRectsItem
from pypho_timeline.rendering.graphics.rectangle_helpers import RectangleRenderTupleHelpers
from pypho_timeline.rendering.helpers.render_rectangles_helper import Render2DEventRectanglesHelper
from pypho_timeline.rendering.mixins.live_window_monitoring_mixin import LiveWindowEventIntervalMonitoringMixin
import pyqtgraph as pg
from datetime import datetime
from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp

# Import IntervalsDatasource from external package (or use interface)
try:
    from pyphoplacecellanalysis.General.Model.Datasources.IntervalDatasource import IntervalsDatasource
except ImportError:
    # Fallback: define minimal interface if not available
    IntervalsDatasource = None

# Optional import for General2DRenderTimeEpochs (used for visualization updates)
try:
    from pyphoplacecellanalysis.GUI.PyQtPlot.Widgets.Mixins.RenderTimeEpochs.Specific2DRenderTimeEpochs import General2DRenderTimeEpochs
except ImportError:
    General2DRenderTimeEpochs = None

# Optional mixin - handle with try/except
try:
    from pyphoplacecellanalysis.GUI.PyQtPlot.Widgets.Mixins.ReprPrintableWidgetMixin import ReprPrintableItemMixin
except ImportError:
    # Fallback: create minimal stub if mixin not available
    class ReprPrintableItemMixin:
        pass


class RenderedEpochsItemsContainer(iPythonKeyCompletingMixin, DynamicParameters):
    """Wraps a list of plots and their rendered_rects_item for a given datasource/name.
    
    Note that the plots are only given by self.dynamically_added_attributes since the 'name' key exists.
    """
    def __init__(self, rendered_rects_item: IntervalRectsItem, target_plots_list: List, format_tooltip_fn=None, **kwargs):
        super(RenderedEpochsItemsContainer, self).__init__()
        if len(target_plots_list) == 1:
            a_plot = target_plots_list[0]
            self[a_plot] = rendered_rects_item  # no conflict, so can just return the original rendered_rects_item

        else:
            for a_plot in target_plots_list:
                # make an independent copy of the rendered_rects_item for each plot
                independent_data_copy = RectangleRenderTupleHelpers.copy_data(rendered_rects_item.data)
                self[a_plot] = IntervalRectsItem(data=independent_data_copy, format_tooltip_fn=format_tooltip_fn, **kwargs)
                ## Copy tooltip function
                if rendered_rects_item.format_item_tooltip_fn is not None:
                    self[a_plot].format_item_tooltip_fn = deepcopy(rendered_rects_item.format_item_tooltip_fn)


class NowCurrentDatetimeLineRenderingMixin:
    """ renders little red "now" datetime lines in the active view

    """
    @pyqtExceptionPrintingSlot()
    def NowCurrentDatetimeLineRenderingMixin_on_init(self):
        """Perform any parameters setting/checking during init."""
        self.plots_data['now_lines'] = RenderPlotsData('NowCurrentDatetimeLineRenderingMixin')
        # Get current datetime
        self.plots_data['now_lines'].now_dt = datetime.now()
        # Convert to unix timestamp
        self.plots_data['now_lines'].now_timestamp = datetime_to_unix_timestamp(self.plots_data['now_lines'].now_dt)



    @pyqtExceptionPrintingSlot()
    def NowCurrentDatetimeLineRenderingMixin_on_setup(self):
        """Perform setup/creation of widget/graphical/data objects. Only the core objects are expected to exist on the implementor (root widget, etc)."""
        self.plots.now_lines = RenderPlots('NowCurrentDatetimeLineRenderingMixin')  # the container to hold the time rectangles
        # Create a thick red pen
        self.plots.now_lines.red_pen = pg.mkPen(color='red', width=3)
        self.plots.now_lines.now_line_items = {}
        # now_timestamp = self.plots_data['now_lines'].now_timestamp
        # vline = pg.InfiniteLine(angle=90, movable=False, pos=now_timestamp)
        # vline.setPen(self.plots.now_lines.red_pen)
        # plot_item.addItem(vline, ignoreBounds=True)
        # self.plots.now_lines.now_line_items[plot_item] = vline



    @pyqtExceptionPrintingSlot()
    def NowCurrentDatetimeLineRenderingMixin_on_buildUI(self):
        """Perform setup/creation of widget/graphical/data objects. Only the core objects are expected to exist on the implementor (root widget, etc)."""
        now_lines = self.plots_data.get('now_lines', None)
        if now_lines is None:
            ## needs init:
            self.NowCurrentDatetimeLineRenderingMixin_on_init()

        rendered_now_lines = getattr(self.plots, 'now_lines', None)
        if rendered_now_lines is None:
            ## needs setup:
            self.NowCurrentDatetimeLineRenderingMixin_on_setup()



    @pyqtExceptionPrintingSlot()
    def NowCurrentDatetimeLineRenderingMixin_on_destroy(self):
        """Perform teardown/destruction of anything that needs to be manually removed or released."""
        for plot_item, vline in self.plots.now_lines.now_line_items.items():
            if (plot_item is not None) and (vline is not None):
                # vline.setParent(None)
                plot_item.removeItem(vline)
        self.plots.now_lines.now_line_items = {} ## clear


    def add_new_now_line_for_plot_item(self, plot_item):
        """ creates a new now line for the specified plot_item if needed. 
        """
        vline = self.plots.now_lines.now_line_items.get(plot_item, None)
        if vline is None:
            ## build a new item:
            now_timestamp = self.plots_data['now_lines'].now_timestamp
            vline = pg.InfiniteLine(angle=90, movable=False, pos=now_timestamp)
            vline.setPen(pg.mkPen(self.plots.now_lines.red_pen))
            plot_item.addItem(vline, ignoreBounds=True)
            self.plots.now_lines.now_line_items[plot_item] = vline
        else:
            return vline ## return existing vline


    @pyqtExceptionPrintingSlot()
    def update_now_lines(self):
        """ called to refresh the now (current) datetime for all now line items and updates the lines themselves if they exist. """
        # Get current datetime
        self.plots_data['now_lines'].now_dt = datetime.now()
        # Convert to unix timestamp
        self.plots_data['now_lines'].now_timestamp = datetime_to_unix_timestamp(self.plots_data['now_lines'].now_dt)
        for plot_item, vline in self.plots.now_lines.now_line_items.items():
            if (plot_item is not None) and (vline is not None):
                vline.setPosition(self.plots_data['now_lines'].now_timestamp) ## moves the item



class EpochRenderingMixin(NowCurrentDatetimeLineRenderingMixin, LiveWindowEventIntervalMonitoringMixin):
    """Implementors render Epochs/Intervals as little rectangles.
    
    Requires:
        self.plots
        self.plots_data
        
    Provides:
        self.plots_data['interval_datasources']: RenderPlotsData
        self.plots.rendered_epochs: RenderPlots
        self.ui
        self.ui.connections
    
    Known Conformances:
        RasterPlot2D: to render laps, PBEs, and more on the 2D plots

    Usage:
        ## Build a PBEs datasource:
        laps_interval_datasource = Specific2DRenderTimeEpochsHelper.build_Laps_render_time_epochs_datasource(curr_sess=sess, series_vertical_offset=42.0, series_height=1.0)
        new_PBEs_interval_datasource = Specific2DRenderTimeEpochsHelper.build_PBEs_render_time_epochs_datasource(curr_sess=sess, series_vertical_offset=43.0, series_height=1.0)
        
        ## General Adding:
        active_2d_plot.add_rendered_intervals(new_PBEs_interval_datasource, name='PBEs', child_plots=[background_static_scroll_plot_widget, main_plot_widget], debug_print=True)
        active_2d_plot.add_rendered_intervals(laps_interval_datasource, name='Laps', child_plots=[background_static_scroll_plot_widget, main_plot_widget], debug_print=True)
        
        ## Selectively Removing:
        active_2d_plot.remove_rendered_intervals(name='PBEs', child_plots_removal_list=[main_plot_widget])
        active_2d_plot.remove_rendered_intervals(name='PBEs')
        
        ## Clearing:
        active_2d_plot.clear_all_rendered_intervals()
    """

    sigOnIntervalEnteredWindow = QtCore.Signal(object)  # pyqtSignal(object)
    sigOnIntervalExitedindow = QtCore.Signal(object)
    sigRenderedIntervalsListChanged = QtCore.Signal(object)  # signal emitted whenever the list of rendered intervals changed (add/remove)

    @property
    def interval_rendering_plots(self):
        """Returns the list of child subplots/graphics (usually PlotItems) that participate in rendering intervals.
        
        MUST BE OVERRIDDEN in child classes.
        """
        raise NotImplementedError  # MUST OVERRIDE in child
        # return [self.plots.background_static_scroll_window_plot, self.plots.main_plot_widget] # for spike_raster_plt_2d
    
    @property
    def interval_datasources(self):
        """The interval_datasources property. A RenderPlotsData object."""
        return self.plots_data['interval_datasources']

    @property
    def interval_datasource_names(self):
        """The interval_datasources property."""
        return list(self.interval_datasources.dynamically_added_attributes)  # ['CustomPBEs', 'PBEs', 'Ripples', 'Laps', 'Replays', 'SessionEpochs']

    @property
    def interval_datasource_updating_connections(self):
        """The interval_datasource_updating_connections property. A ConnectionsContainer object."""
        return self.ui.connections
    
    @property
    def rendered_epochs(self):
        """The rendered_epochs property."""
        return self.plots.rendered_epochs
    
    @property
    def rendered_epoch_series_names(self):
        """The rendered_epoch_names property."""
        return [a_name for a_name in self.rendered_epochs.keys() if ((a_name != 'name') and (a_name != 'context'))]

    @pyqtExceptionPrintingSlot()
    def EpochRenderingMixin_on_init(self):
        """Perform any parameters setting/checking during init."""
        self.plots_data['interval_datasources'] = RenderPlotsData('EpochRenderingMixin')
        self.LiveWindowEventIntervalMonitoringMixin_on_init()
        self.NowCurrentDatetimeLineRenderingMixin_on_init()
        self._is_updating_from_widget = False  # Flag to prevent circular updates

    @pyqtExceptionPrintingSlot()
    def EpochRenderingMixin_on_setup(self):
        """Perform setup/creation of widget/graphical/data objects. Only the core objects are expected to exist on the implementor (root widget, etc)."""
        self.plots.rendered_epochs = RenderPlots('EpochRenderingMixin')  # the container to hold the time rectangles
        self.LiveWindowEventIntervalMonitoringMixin_on_setup()
        self.NowCurrentDatetimeLineRenderingMixin_on_setup()

    @pyqtExceptionPrintingSlot()
    def EpochRenderingMixin_on_buildUI(self):
        """Perform setup/creation of widget/graphical/data objects. Only the core objects are expected to exist on the implementor (root widget, etc)."""
        interval_datasources = self.plots_data.get('interval_datasources', None)
        if interval_datasources is None:
            ## needs init:
            self.EpochRenderingMixin_on_init()
            
        rendered_epochs = getattr(self.plots, 'rendered_epochs', None)
        if rendered_epochs is None:
            ## needs setup:
            self.EpochRenderingMixin_on_setup()
            
        # Adds the self.ui and self.ui.connections if they don't exist
        if not hasattr(self, 'ui'):
            # if the window has no .ui property, create one:
            setattr(self, 'ui', PhoUIContainer())
            
        if isinstance(self.ui, DynamicParameters):            
            # Need this workaround because hasattr fails for DynamicParameters/PhoUIContainer right now:
            self.ui.setdefault('connections', ConnectionsContainer())
        else:
            if not hasattr(self.ui, 'connections'):
                self.ui.connections = ConnectionsContainer()

        self.LiveWindowEventIntervalMonitoringMixin_on_buildUI()
        self.NowCurrentDatetimeLineRenderingMixin_on_buildUI()
        
        if len(self.interval_rendering_plots) > 0:
            for a_plot_item in self.interval_rendering_plots:
                if a_plot_item is not None:
                    self.add_new_now_line_for_plot_item(plot_item=a_plot_item)

    @pyqtExceptionPrintingSlot()
    def EpochRenderingMixin_on_destroy(self):
        """Perform teardown/destruction of anything that needs to be manually removed or released."""
        # TODO: REGISTER AND IMPLEMENT
        self.LiveWindowEventIntervalMonitoringMixin_on_destroy()
        self.NowCurrentDatetimeLineRenderingMixin_on_destroy()
        raise NotImplementedError

    @pyqtExceptionPrintingSlot(float, float)
    def EpochRenderingMixin_on_window_update(self, new_start=None, new_end=None):
        """Called to perform updates when the active window changes. Redraw, recompute data, etc."""
        self.LiveWindowEventIntervalMonitoringMixin_on_window_update(new_start, new_end)

    @pyqtExceptionPrintingSlot(object)
    def EpochRenderingMixin_on_window_update_rate_limited(self, evt):
        """Rate-limited version of on_window_update for use with pg.SignalProxy."""
        self.EpochRenderingMixin_on_window_update(*evt)

    def _block_datasource_signals(self):
        """Context manager to temporarily block datasource update signals during widget-driven updates."""
        class _SignalBlocker:
            def __init__(self, mixin):
                self.mixin = mixin
                self.blocked_datasources = {}
            def __enter__(self):
                self.mixin._is_updating_from_widget = True
                for name, ds in self.mixin.interval_datasources.items():
                    if hasattr(ds, 'source_data_changed_signal'):
                        # Block signals on the QObject (datasource), not on the signal itself
                        # blockSignals() blocks ALL signals from the object, which is what we want
                        self.blocked_datasources[name] = ds.blockSignals(True)
                return self
            def __exit__(self, *args):
                for name, was_blocked in self.blocked_datasources.items():
                    if name in self.mixin.interval_datasources:
                        # Restore previous blocking state on the datasource QObject
                        self.mixin.interval_datasources[name].blockSignals(was_blocked)
                self.mixin._is_updating_from_widget = False
        
        return _SignalBlocker(self)
    
    @pyqtExceptionPrintingSlot(object)
    def EpochRenderingMixin_on_interval_datasource_changed(self, datasource):
        """Emit our own custom signal when the general datasource update method returns."""
        if self._is_updating_from_widget:
            return  # Skip if update is from widget to prevent circular updates
        self.add_rendered_intervals(datasource, name=datasource.custom_datasource_name, debug_print=False)  # updates the rendered intervals on the change
        
    def add_rendered_intervals(self, interval_datasource: Union[pd.DataFrame, Any], name=None, child_plots=None, debug_print=False, **vis_kwargs):
        """Adds or updates the intervals specified by the interval_datasource to the plots.
        
        Inputs: 
            interval_datasource: IntervalDatasource or pd.DataFrame
            name: str, an optional but highly recommended string identifier like 'Laps'
            child_plots: an optional list of plots to add the intervals to. If None are specified, the defaults are used (defined by the implementor)
            
        Returns:
            returned_rect_items: a dictionary of tuples containing the newly created rect items and the plots they were added to.
            
        Uses: 'RectangleRenderTupleHelpers', 'RenderedEpochsItemsContainer', 'IntervalRectsItem', 'self._perform_add_render_item(...)'
        """
        # Handle DataFrame input by converting to datasource
        if isinstance(interval_datasource, pd.DataFrame):
            ## it's a dataframe, build a datasource
            # Optional import - TimeColumnAliasesProtocol from neuropy (only used if available)
            try:
                from neuropy.utils.mixins.time_slicing import TimeColumnAliasesProtocol
            except ImportError:
                TimeColumnAliasesProtocol = None
            
            interval_df: pd.DataFrame = deepcopy(interval_datasource)
            if IntervalsDatasource is not None and TimeColumnAliasesProtocol is not None:
                interval_df = TimeColumnAliasesProtocol.renaming_synonym_columns_if_needed(df=interval_df, required_columns_synonym_dict=IntervalsDatasource._time_column_name_synonyms)
                if General2DRenderTimeEpochs is not None:
                    interval_datasource = General2DRenderTimeEpochs.build_render_time_epochs_datasource(interval_df)
                else:
                    raise NotImplementedError("General2DRenderTimeEpochs not available - cannot convert DataFrame to datasource")
            else:
                raise NotImplementedError("IntervalsDatasource not available - cannot convert DataFrame to datasource")

        if IntervalsDatasource is not None:
            assert isinstance(interval_datasource, IntervalsDatasource), f"interval_datasource: must be an IntervalsDatasource object but instead is of type: {type(interval_datasource)}"
        
        if name is None:
            if hasattr(interval_datasource, 'custom_datasource_name'):
                print(f'WARNING: no name provided for rendered intervals. Defaulting to datasource name: "{interval_datasource.custom_datasource_name}"')
                name = interval_datasource.custom_datasource_name
            else:
                name = 'UnnamedIntervals'
            
        # Update the custom datasource name with the provided name
        if hasattr(interval_datasource, 'custom_datasource_name'):
            interval_datasource.custom_datasource_name = name
        
        rendered_intervals_list_did_change = False
        extant_datasource = self.interval_datasources.get(name, None)
        if extant_datasource is None:
            # no extant datasource with this name, create it:
            self.interval_datasources[name] = interval_datasource  # add new datasource.
            # Connect the source_data_changed_signal to handle changes to the datasource:
            if hasattr(interval_datasource, 'source_data_changed_signal'):
                self.interval_datasources[name].source_data_changed_signal.connect(self.EpochRenderingMixin_on_interval_datasource_changed)
            rendered_intervals_list_did_change = True

        else:
            # extant_datasource exists!
            if debug_print:
                print(f'WARNING: extant_datasource with the name ({name}) already exists. Attempting to update.')
            if extant_datasource == interval_datasource:
                # already the same datasource
                if debug_print:
                    print(f'\t already the same datasource. Continuing to try and update.')
            else:
                # Otherwise the datasource should be replaced:
                if debug_print:
                    print(f'\t replacing extant datasource.')
                # Disconnect the previous datasource from the update signal before replacing
                if hasattr(extant_datasource, 'source_data_changed_signal'):
                    try:
                        extant_datasource.source_data_changed_signal.disconnect(self.EpochRenderingMixin_on_interval_datasource_changed)
                    except (TypeError, RuntimeError):
                        pass  # Connection may not exist or already disconnected
                self.interval_datasources[name] = interval_datasource
                # Connect the source_data_changed_signal to handle changes to the datasource:
                if hasattr(interval_datasource, 'source_data_changed_signal'):
                    self.interval_datasources[name].source_data_changed_signal.connect(self.EpochRenderingMixin_on_interval_datasource_changed)
                        
        ## Update the visual properties if provided
        if len(vis_kwargs) > 0 and hasattr(interval_datasource, 'update_visualization_properties'):
            if General2DRenderTimeEpochs is not None:
                self.interval_datasources[name].update_visualization_properties(lambda active_df, **kwargs: General2DRenderTimeEpochs._update_df_visualization_columns(active_df, **(vis_kwargs | kwargs)))
        
        returned_rect_items = {}

        def _custom_format_tooltip_for_rect_data(rect_index: int, rect_data_tuple: Tuple) -> str:
            """Hover info text tooltip for each epoch in the `IntervalRectsItem`.
            
            Captures: name 
            rect_data_tuple = self.data[rect_index]
            start_t, series_vertical_offset, duration_t, series_height, pen, brush = rect_data_tuple
            """
            start_t, series_vertical_offset, duration_t, series_height, pen, brush = rect_data_tuple
            ## get the optional label field if `rect_data_tuple` is a `IntervalRectsItemData` instead of a plain tuple
            a_label = None
            if not isinstance(rect_data_tuple, Tuple):
                a_label = rect_data_tuple.label
            
            end_t = start_t + duration_t
            if a_label:
                tooltip_text = f"{a_label}\n{name}[{rect_index}]\nStart: {start_t:.3f}\nEnd: {end_t:.3f}\nDuration: {duration_t:.3f}"
            else:
                tooltip_text = f"{name}[{rect_index}]\nStart: {start_t:.3f}\nEnd: {end_t:.3f}\nDuration: {duration_t:.3f}"

            return tooltip_text

        # Build the rendered interval item:
        new_interval_rects_item: IntervalRectsItem = Render2DEventRectanglesHelper.build_IntervalRectsItem_from_interval_datasource(interval_datasource, format_tooltip_fn=deepcopy(_custom_format_tooltip_for_rect_data))
        new_interval_rects_item.format_item_tooltip_fn = deepcopy(_custom_format_tooltip_for_rect_data)
        
        ######### PLOTS:
        if child_plots is None:
            child_plots = self.interval_rendering_plots
        num_plot_items = len(child_plots)
        if debug_print:
            print(f'num_plot_items: {num_plot_items}')
        
        extant_rects_plot_items_container = self.rendered_epochs.get(name, None)
        if extant_rects_plot_items_container is not None:
            # extant plot exists!
            if debug_print:
                print(f'WARNING: extant_rects_plot_item with the name ({name}) already exists. removing.')
            assert isinstance(extant_rects_plot_items_container, RenderedEpochsItemsContainer), f"extant_rects_plot_item must be RenderedEpochsItemsContainer but type(extant_rects_plot_item): {type(extant_rects_plot_items_container)}"
            
            for a_plot in child_plots:
                if a_plot in extant_rects_plot_items_container:
                    # Update data in-place instead of remove/recreate
                    extant_rect_plot_item = extant_rects_plot_items_container[a_plot]
                    new_data = RectangleRenderTupleHelpers.copy_data(new_interval_rects_item.data)
                    extant_rect_plot_item.update_data(new_data)
                    # Preserve tooltip function
                    extant_rect_plot_item.format_item_tooltip_fn = deepcopy(_custom_format_tooltip_for_rect_data)
                    returned_rect_items[a_plot.objectName()] = dict(plot=a_plot, rect_item=extant_rect_plot_item)
                    # Adjust the bounds to fit any children:
                    EpochRenderingMixin.compute_bounds_adjustment_for_rect_item(a_plot, extant_rect_plot_item)
                else:
                    # New plot, add new item
                    independent_data_copy = RectangleRenderTupleHelpers.copy_data(new_interval_rects_item.data)
                    extant_rects_plot_items_container[a_plot] = IntervalRectsItem(data=independent_data_copy, format_tooltip_fn=deepcopy(_custom_format_tooltip_for_rect_data))
                    extant_rects_plot_items_container[a_plot].format_item_tooltip_fn = deepcopy(_custom_format_tooltip_for_rect_data)
                    self._perform_add_render_item(a_plot, extant_rects_plot_items_container[a_plot])
                    returned_rect_items[a_plot.objectName()] = dict(plot=a_plot, rect_item=extant_rects_plot_items_container[a_plot])
                    # Adjust the bounds to fit any children:
                    EpochRenderingMixin.compute_bounds_adjustment_for_rect_item(a_plot, extant_rects_plot_items_container[a_plot])
                    
        else:
            # Need to create a new RenderedEpochsItemsContainer with the items:
            self.rendered_epochs[name] = RenderedEpochsItemsContainer(new_interval_rects_item, child_plots, format_tooltip_fn=deepcopy(_custom_format_tooltip_for_rect_data))  # set the plot item
            for a_plot, a_rect_item in self.rendered_epochs[name].items():
                if not isinstance(a_rect_item, str):
                    if debug_print:
                        print(f'plotting item')
                    self._perform_remove_render_item(a_plot, a_rect_item)
                    self._perform_add_render_item(a_plot, a_rect_item)
                    returned_rect_items[a_plot.objectName()] = dict(plot=a_plot, rect_item=a_rect_item)
                    
                    # Adjust the bounds to fit any children:
                    EpochRenderingMixin.compute_bounds_adjustment_for_rect_item(a_plot, a_rect_item)

        if rendered_intervals_list_did_change:
            self.sigRenderedIntervalsListChanged.emit(self)  # Emit the intervals list changed signal when a truly new item is added

        return returned_rect_items 

    def remove_rendered_intervals(self, name, child_plots_removal_list=None, debug_print=False):
        """Removes the intervals specified by the interval_datasource to the plots.

        Inputs:
            name: the name of the rendered_repochs to remove.
            child_plots_removal_list: is not-None, a list of child plots can be specified and rects will only be removed from those plots.
        
        Returns:
            a list of removed items
        """
        extant_rects_plot_item = self.rendered_epochs[name]
        items_to_remove_from_rendered_epochs = []
        for a_plot, a_rect_item in extant_rects_plot_item.items():
            if not isinstance(a_plot, str):
                if child_plots_removal_list is not None:
                    if (a_plot in child_plots_removal_list):
                        # only remove if the plot is in the child plots:
                        self._perform_remove_render_item(a_plot, a_rect_item)
                        items_to_remove_from_rendered_epochs.append(a_plot)
                    else:
                        pass  # continue
                else:
                    # otherwise remove all
                    self._perform_remove_render_item(a_plot, a_rect_item)
                    items_to_remove_from_rendered_epochs.append(a_plot)
                
        ## remove the items from the list:
        for a_key_to_remove in items_to_remove_from_rendered_epochs:
            del extant_rects_plot_item[a_key_to_remove]  # remove the key from the RenderedEpochsItemsContainer
        
        if len(self.rendered_epochs[name]) == 0:
            # if the item is now empty, remove it and its and paired datasource
            if debug_print:
                print(f'self.rendered_epochs[{name}] now empty. Removing it and its datasource...')
            # Disconnect signal connection before removing datasource
            if name in self.interval_datasources:
                datasource = self.interval_datasources[name]
                if hasattr(datasource, 'source_data_changed_signal'):
                    try:
                        datasource.source_data_changed_signal.disconnect(self.EpochRenderingMixin_on_interval_datasource_changed)
                    except (TypeError, RuntimeError):
                        pass  # Connection may not exist or already disconnected
            del self.rendered_epochs[name]
            del self.interval_datasources[name]
            self.sigRenderedIntervalsListChanged.emit(self)  # Emit the intervals list changed signal when the item is removed
    
        return items_to_remove_from_rendered_epochs

    def clear_all_rendered_intervals(self, child_plots_removal_list=None, debug_print=False):
        """Removes all rendered rects - a batch version of removed_rendered_intervals(...)."""
        curr_rendered_epoch_names = self.rendered_epoch_series_names
        # the `self.rendered_epochs` is of type RenderPlots, and it has a 'name' and 'context' property that don't correspond to real outputs
        for a_name in curr_rendered_epoch_names:
            if (a_name != 'name') and (a_name != 'context'):
                if debug_print:
                    print(f'removing {a_name}...')
                self.remove_rendered_intervals(a_name, child_plots_removal_list=child_plots_removal_list, debug_print=debug_print)

    def get_all_rendered_intervals_dict(self, debug_print=False) -> Dict[str, Dict[str, IntervalRectsItem]]:
        """Returns a dictionary containing the hierarchy of all the members. Can optionally also print.
        
        Example:
            interval_info_dict = active_2d_plot.get_all_rendered_intervals_dict()
        """
        out_dict = {}
        rendered_epoch_names = self.interval_datasource_names
        if debug_print:
            print(f'rendered_epoch_names: {rendered_epoch_names}')
        for a_name in rendered_epoch_names:
            out_dict[a_name] = {}
            a_render_container = self.rendered_epochs[a_name]
            render_container_items = {key:value for key, value in a_render_container.items() if (not isinstance(key, str))}
            if debug_print:
                print(f'\tname: {a_name} - {len(render_container_items)} plots:')
            curr_plots_dict = {}
            
            for a_plot, a_rect_item in render_container_items.items():
                if isinstance(a_plot, str):
                    ## This is still happening due to the '__class__' item!
                    print(f'WARNING: there was an item in a_render_container of type string: (a_plot: {a_plot} <{type(a_plot)}>, a_rect_item: {type(a_rect_item)}')
                else:
                    if isinstance(a_rect_item, IntervalRectsItem):
                        num_intervals = len(a_rect_item.data)
                    else:
                        num_intervals = len(a_rect_item)  # for 3D plots, for example, we have a list of meshes which we will use len(...) to get the number of
                        
                    if debug_print:
                        print(f'\t\t{a_plot.objectName()}: plot[{num_intervals} intervals]')

                    curr_plots_dict[a_plot.objectName()] = a_rect_item

            out_dict[a_name] = curr_plots_dict
            
        if debug_print:
            print(f'out_dict: {out_dict}')

        return out_dict

    def update_rendered_intervals_visualization_properties(self, update_dict):
        """Updates the interval datasources (and thus the actual rendered rectangles) from the provided `update_dict`.

        Args:
            update_dict: Dictionary mapping interval names to visualization property dictionaries
        """
        for interval_key, interval_update_kwargs in update_dict.items():
            if interval_key in self.interval_datasources:
                # Extract visibility settings before updating datasource (handle both single dict and list of dicts)
                visibility_settings = None
                if isinstance(interval_update_kwargs, (list, tuple)):
                    ## list of update dicts - each item can have its own isVisible property
                    a_list_interval_update_kwargs = []
                    visibility_settings = []
                    for a_sub_interval_update_kwargs in interval_update_kwargs:
                        if not isinstance(a_sub_interval_update_kwargs, dict):
                            a_sub_interval_update_kwargs = a_sub_interval_update_kwargs.to_dict()  # deal with EpochDisplayConfig 
                        a_list_interval_update_kwargs.append(a_sub_interval_update_kwargs)
                        # Extract visibility from each item (can be None if not specified)
                        visibility_settings.append(a_sub_interval_update_kwargs.get('isVisible', None))
                    ## Update with list
                    if General2DRenderTimeEpochs is not None and hasattr(self.interval_datasources[interval_key], 'update_visualization_properties'):
                        for a_sub_interval_update_kwargs in a_list_interval_update_kwargs:
                            self.interval_datasources[interval_key].update_visualization_properties(lambda active_df, **kwargs: General2DRenderTimeEpochs._update_df_visualization_columns(active_df, **(a_sub_interval_update_kwargs | kwargs)))

                else:
                    ## single update item dict
                    if not isinstance(interval_update_kwargs, dict):
                        interval_update_kwargs = interval_update_kwargs.to_dict()  # deal with EpochDisplayConfig 
                    visibility_settings = interval_update_kwargs.get('isVisible', None)
                    if General2DRenderTimeEpochs is not None and hasattr(self.interval_datasources[interval_key], 'update_visualization_properties'):
                        self.interval_datasources[interval_key].update_visualization_properties(lambda active_df, **kwargs: General2DRenderTimeEpochs._update_df_visualization_columns(active_df, **(interval_update_kwargs | kwargs)))
                
                # Apply visibility setting to rendered items if provided
                if visibility_settings is not None and interval_key in self.rendered_epochs:
                    if isinstance(visibility_settings, list):
                        # List case: check if all non-None values are the same
                        non_none_visibilities = [v for v in visibility_settings if v is not None]
                        if len(non_none_visibilities) > 0:
                            # If all non-None values are the same, apply that visibility
                            if len(set(non_none_visibilities)) == 1:
                                is_visible = non_none_visibilities[0]
                                container = self.rendered_epochs[interval_key]
                                for a_plot, rect_item in container.items():
                                    if not isinstance(a_plot, str) and isinstance(rect_item, IntervalRectsItem):
                                        rect_item.setVisible(is_visible)
                    else:
                        # Single config case: apply directly
                        container = self.rendered_epochs[interval_key]
                        for a_plot, rect_item in container.items():
                            if not isinstance(a_plot, str) and isinstance(rect_item, IntervalRectsItem):
                                rect_item.setVisible(visibility_settings)
            else:
                print(f"WARNING: interval_key '{interval_key}' was not found in self.interval_datasources. Skipping update for unknown item.")

    @classmethod
    def compute_bounds_adjustment_for_rect_item(cls, a_plot, a_rect_item, should_apply_adjustment:bool=True, debug_print=False):
        """Adjusts plot bounds to fit the rectangle item.
        
        NOTE: 2D Only
        
        Inputs:
            a_plot: PlotItem or equivalent
            a_rect_item: IntervalRectsItem
            should_apply_adjustment: bool - If True, the adjustment is actually applied
        Returns:
            adjustment_needed: a float representing the difference of adjustment after adjusting or NONE if no changes needed
        """
        adjustment_needed = None
        curr_x_min, curr_x_max, curr_y_min, curr_y_max = cls.get_plot_view_range(a_plot, debug_print=False)
        if debug_print:
            print(f'compute_bounds_adjustment_for_rect_item(a_plot, a_rect_item):')
            print(f'\ta_plot.y: {curr_y_min}, {curr_y_max}')
            
        new_min_y_range, new_max_y_range = cls.get_added_rect_item_required_y_value(a_rect_item, debug_print=debug_print)
        if (new_max_y_range > curr_y_max):
            # needs adjustment
            adjustment_needed = (new_max_y_range - curr_y_max)
            if debug_print:
                print(f'\t needs adjustment: a_rect_item requested new y_max: {new_max_y_range}')
                    
        final_y_max = max(new_max_y_range, curr_y_max)
        
        if (new_min_y_range < curr_y_min):
            # needs adjustment
            if adjustment_needed is None:
                adjustment_needed = 0
            adjustment_needed = adjustment_needed + (new_min_y_range - curr_y_min)
            if debug_print:
                print(f'\t needs adjustment: a_rect_item requested new new_min_y_range: {new_min_y_range}')
        else:
            adjusted_y_min_range = new_min_y_range
    
        final_y_min = min(new_min_y_range, curr_y_min)
    
        if (adjustment_needed and should_apply_adjustment):
            a_plot.setYRange(final_y_min, final_y_max, padding=0)
    
        return adjustment_needed
    
    @staticmethod
    def get_added_rect_item_required_y_value(a_rect_item, debug_print=False):
        """Gets the required y-value range for a rectangle item.
        
        NOTE: 2D Only
        
        Usage:
            Only known to be used by .compute_bounds_adjustment_for_rect_item(...) above
        """
        curr_rect = a_rect_item.boundingRect()  # PyQt5.QtCore.QRectF(29.0, 43.0, 1683.0, 2.0)
        new_min_y_range = min(curr_rect.top(), curr_rect.bottom())
        new_max_y_range = max(curr_rect.top(), curr_rect.bottom())
        if debug_print:
            print(f'new_min_y_range: {new_min_y_range}')
            print(f'new_max_y_range: {new_max_y_range}')
        return new_min_y_range, new_max_y_range
    
    @staticmethod
    def get_plot_view_range(a_plot, debug_print=True):
        """Gets the current viewRange for the passed in plot.
        
        NOTE: 2D Only
      
        Inputs:
            a_plot: PlotItem
        Returns:
            (curr_x_min, curr_x_max, curr_y_min, curr_y_max)
        """
        curr_x_range, curr_y_range = a_plot.viewRange()  # [[30.0, 45.0], [-1.359252049028905, 41.3592520490289]]
        if debug_print:
            print(f'curr_x_range: {curr_x_range}, curr_y_range: {curr_y_range}')
        curr_x_min, curr_x_max = curr_x_range
        curr_y_min, curr_y_max = curr_y_range
        if debug_print:
            print(f'curr_x_min: {curr_x_min}, curr_x_max: {curr_x_max}, curr_y_min: {curr_y_min}, curr_y_max: {curr_y_max}')
        return (curr_x_min, curr_x_max, curr_y_min, curr_y_max)

    @classmethod
    def build_stacked_epoch_layout(cls, rendered_interval_heights, epoch_render_stack_height=40.0, interval_stack_location='below', debug_print=True):
        """Builds a stack layout for the list of specified epochs.

        Args:
            rendered_interval_heights: Array of height ratios for each interval
            epoch_render_stack_height: Total height of the stack
            interval_stack_location: 'below' or 'above'
            debug_print: Whether to print debug info

        Returns:
            (required_vertical_offsets, required_interval_heights)
        """
        normalized_interval_heights = rendered_interval_heights/np.sum(rendered_interval_heights)  # array([0.2, 0.2, 0.2, 0.2, 0.2])
        required_interval_heights = normalized_interval_heights * epoch_render_stack_height  # array([3.2, 3.2, 3.2, 3.2, 3.2])
        required_vertical_offsets = np.cumsum(required_interval_heights)  # array([ 3.2  6.4  9.6 12.8 16.])
        if interval_stack_location == 'below':
            required_vertical_offsets = required_vertical_offsets * -1.0  # make offsets negative if it's below the plot
        elif interval_stack_location == 'above':
            # if it's to be placed above the plot, we need to add the top of the plot to each of the offsets:
            required_vertical_offsets = required_vertical_offsets + 0.0  # TODO: get top of plot
        else:
            print(f"interval_stack_location: str must be either ('below' or 'above') but was {interval_stack_location}")
            raise NotImplementedError
        if debug_print:
            print(f'required_interval_heights: {required_interval_heights}, required_vertical_offsets: {required_vertical_offsets}')

        return required_vertical_offsets, required_interval_heights

