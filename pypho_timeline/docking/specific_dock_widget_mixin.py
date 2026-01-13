from typing import Optional, Tuple, Any, Dict
from copy import deepcopy
import numpy as np
import pandas as pd
from qtpy import QtCore

from pyphoplacecellanalysis.External.pyqtgraph.dockarea.Dock import Dock
import pyphoplacecellanalysis.External.pyqtgraph as pg
from pyphocorehelpers.function_helpers import function_attributes

from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode
from pypho_timeline.core.pyqtgraph_time_synchronized_widget import PyqtgraphTimeSynchronizedWidget
from pypho_timeline.docking.dock_display_configs import CustomDockDisplayConfig, CustomCyclicColorsDockDisplayConfig, NamedColorScheme, FigureWidgetDockDisplayConfig


class SpecificDockWidgetManipulatingMixin:
    """Mixin providing methods for creating and managing specific types of timeline tracks (intervals, rasters, etc.)
    
    This mixin provides high-level methods for preparing and adding timeline tracks.
    It requires the implementing class to have:
    - `self.ui.dynamic_docked_widget_container`: A widget implementing DynamicDockDisplayAreaContentMixin
    - `self.ui.matplotlib_view_widgets`: Dict[str, PyqtgraphTimeSynchronizedWidget] - storage for track widgets
    - `self.ui.connections`: Dict[str, Any] - storage for signal connections
    - `self.window_scrolled`: QtCore.Signal(float, float) - signal emitted when time window changes
    - `self.total_data_start_time`: float - start time of all data
    - `self.total_data_end_time`: float - end time of all data
    - `self.spikes_window`: Object with `active_window_start_time`, `active_window_end_time`, `total_df_start_end_times` attributes
    
    Usage:
        class MyTimelineWidget(SpecificDockWidgetManipulatingMixin, QtWidgets.QWidget):
            def __init__(self):
                self.ui = PhoUIContainer()
                self.ui.dynamic_docked_widget_container = NestedDockAreaWidget()
                self.ui.matplotlib_view_widgets = {}
                self.ui.connections = {}
                self.window_scrolled = QtCore.Signal(float, float)
                # ... initialize other required attributes
    """
    
    def on_toggle_timeline_sync_mode(self, an_item, mode_name):
        """ Called to update the sync mode
        mode_name: str - one of 'Generic' (TO_WINDOW), 'to_global_data' (TO_GLOBAL_DATA), or 'no_sync' (NO_SYNC)
        """
        print(f'on_toggle_timeline_sync_mode(an_item: {an_item}, mode_name: {mode_name})')
        identifier_name = an_item._name
        print(f'\tidentifier_name: "{identifier_name}"')
        
        # Convert mode_name string to SynchronizedPlotMode enum
        if mode_name == 'Generic':
            sync_mode: SynchronizedPlotMode = SynchronizedPlotMode.TO_WINDOW
        elif mode_name == 'to_global_data':
            sync_mode: SynchronizedPlotMode = SynchronizedPlotMode.TO_GLOBAL_DATA
        elif mode_name == 'no_sync':
            sync_mode: SynchronizedPlotMode = SynchronizedPlotMode.NO_SYNC
        else:
            print(f'\tWARNING: Unknown mode_name "{mode_name}", defaulting to TO_WINDOW')
            sync_mode: SynchronizedPlotMode = SynchronizedPlotMode.TO_WINDOW
        
        print(f'\tsync_mode: {sync_mode}')
        self.sync_matplotlib_render_plot_widget(identifier_name, sync_mode=sync_mode)
        print('\tdone.')


    @function_attributes(short_name=None, tags=['pyqtgraph_render_widget', 'dynamic_ui', 'group_matplotlib_render_plot_widget', 'pyqtgraph', 'docked_widget', 'context-menu'], input_requires=[], output_provides=[], uses=['PyqtgraphTimeSynchronizedWidget'], used_by=[], creation_date='2024-12-31 03:35', related_items=['add_new_matplotlib_render_plot_widget'])
    def add_new_embedded_pyqtgraph_render_plot_widget(self, name='pyqtgraph_view_widget', dockSize=(500,50), dockAddLocationOpts=['bottom'], display_config:CustomDockDisplayConfig=None, sync_mode:Optional[SynchronizedPlotMode]=None) -> Tuple[PyqtgraphTimeSynchronizedWidget, Any, Any, Dock]:
        """ creates a new dynamic PyqtgraphTimeSynchronizedWidget, a container widget that holds a pyqtgraph-based figure, and adds it as a row to the main layout
        
        based off of `add_new_matplotlib_render_plot_widget`, but to support embedded pyqtgraph plots instead of matplotlib plots
        
        emit an event so the parent can call `self.update_scrolling_event_filters()` to add the new item
        Uses: self.ui.matplotlib_view_widgets
        
        Usage:
        
            a_time_sync_pyqtgraph_widget, root_graphics_layout_widget, plot_item, dDisplayItem = self.add_new_embedded_pyqtgraph_render_plot_widget(name='test_pyqtgraph_view_widget', dockSize=(500,50), sync_mode='')
            
        """
        
        dDisplayItem = self.ui.dynamic_docked_widget_container.find_display_dock(identifier=name) # Dock
        if dDisplayItem is None:
            # No extant matplotlib_view_widget and display_dock currently, create a new one:
            ## TODO: hardcoded single-widget: used to be named `self.ui.matplotlib_view_widget`
            # Get reference_datetime from parent if available (for datetime axis alignment)
            reference_datetime = getattr(self, 'reference_datetime', None)
            self.ui.matplotlib_view_widgets[name] = PyqtgraphTimeSynchronizedWidget(name=name, reference_datetime=reference_datetime) # Matplotlib widget directly
            self.ui.matplotlib_view_widgets[name].setObjectName(name)

            if display_config is None:
                display_config = FigureWidgetDockDisplayConfig(showCloseButton=True, showCollapseButton=False, showGroupButton=False)
                
            should_hide_title: bool = getattr(display_config, 'hideTitleBar', False)
            
            _, dDisplayItem = self.ui.dynamic_docked_widget_container.add_display_dock(name, dockSize=dockSize, display_config=display_config,
                                                                                    widget=self.ui.matplotlib_view_widgets[name], dockAddLocationOpts=dockAddLocationOpts, autoOrientation=False, hideTitle=should_hide_title)
            dDisplayItem.setOrientation('horizontal', force=True)
            dDisplayItem.updateStyle()
            dDisplayItem.update()
            
            ## Add the plot:
            root_graphics_layout_widget = self.ui.matplotlib_view_widgets[name].getRootGraphicsLayoutWidget()
            plot_item = self.ui.matplotlib_view_widgets[name].getRootPlotItem()

            ## Build custom right-click context menu:
            if hasattr(self, '_menuContextAddRenderable') and (self._menuContextAddRenderable is not None):
                try:
                    from pyphoplacecellanalysis.GUI.Qt.Menus.LocalMenus_AddRenderable.LocalMenus_AddRenderable import LocalMenus_AddRenderable
                    LocalMenus_AddRenderable._helper_append_custom_menu_to_widget_context_menu_universal(parent_widget=plot_item, additional_menu=self._menuContextAddRenderable)
                except ImportError:
                    pass  # Optional feature

            ## emit the signal
            if hasattr(self, 'sigEmbeddedMatplotlibDockWidgetAdded'):
                self.sigEmbeddedMatplotlibDockWidgetAdded.emit(self, dDisplayItem, self.ui.matplotlib_view_widgets[name])
            if hasattr(self, 'sigDockAdded'):
                self.sigDockAdded.emit(self, dDisplayItem) ## sigDockAdded signal to indicate new dock has been added


        else:
            # Already had the widget
            print(f'already had the valid pyqtgraph view widget and its display dock. Returning extant.')
            root_graphics_layout_widget = self.ui.matplotlib_view_widgets[name].getRootGraphicsLayoutWidget()
            plot_item = self.ui.matplotlib_view_widgets[name].getRootPlotItem()

        if sync_mode is not None:
            ## sync up the widgets
            self.sync_matplotlib_render_plot_widget(identifier=name, sync_mode=sync_mode)
            
            # Link X-axes for synchronized zooming across tracks in TO_GLOBAL_DATA mode
            if sync_mode == SynchronizedPlotMode.TO_GLOBAL_DATA:
                # Find the first TO_GLOBAL_DATA track to use as the master for X-axis linking
                # All TO_GLOBAL_DATA tracks will be linked together for synchronized zooming
                master_plot_item = None
                for other_name, other_widget in self.ui.matplotlib_view_widgets.items():
                    if other_name != name:  # Don't link to itself
                        other_plot_item = other_widget.getRootPlotItem()
                        if other_plot_item is not None:
                            # Check if this track is already linked to a master
                            # linkedView is on the ViewBox, not the PlotItem
                            other_viewbox = other_plot_item.getViewBox()
                            if other_viewbox is not None:
                                linked_viewbox = other_viewbox.linkedView(pg.ViewBox.XAxis)
                                if linked_viewbox is not None:
                                    # This track is already linked, find the master PlotItem
                                    # Search for the PlotItem that contains this ViewBox
                                    for search_name, search_widget in self.ui.matplotlib_view_widgets.items():
                                        search_plot = search_widget.getRootPlotItem()
                                        if search_plot is not None and search_plot.getViewBox() == linked_viewbox:
                                            master_plot_item = search_plot
                                            break
                                    if master_plot_item is not None:
                                        break
                            # Use this track as potential master (first TO_GLOBAL_DATA track found)
                            if master_plot_item is None:
                                master_plot_item = other_plot_item
                
                # Link this track's X-axis to the master (or it becomes the master if first)
                if master_plot_item is not None:
                    plot_item.setXLink(master_plot_item)
                # If no master found, this track becomes the master (no linking needed)
            
        return self.ui.matplotlib_view_widgets[name], root_graphics_layout_widget, plot_item, dDisplayItem
    

    @function_attributes(short_name=None, tags=['matplotlib_render_widget', 'dynamic_ui', 'group_matplotlib_render_plot_widget', 'sync'], input_requires=[], output_provides=[], uses=[], used_by=[], creation_date='2023-10-17 13:27', related_items=[])
    def sync_matplotlib_render_plot_widget(self, identifier, sync_mode=SynchronizedPlotMode.TO_WINDOW):
        """ syncs a matplotlib render plot widget with a specified identifier with either the global window, the active time window, or disables sync with the main timeline. 
        
        Requires:
        - `self.ui.matplotlib_view_widgets`: Dict[str, PyqtgraphTimeSynchronizedWidget]
        - `self.ui.connections`: Dict[str, Any] - storage for signal connections
        - `self.window_scrolled`: QtCore.Signal(float, float) - signal emitted when time window changes
        - `self.spikes_window`: Object with `active_window_start_time`, `active_window_end_time`, `total_df_start_end_times` attributes
        """
        # Requires specifying the identifier
        active_matplotlib_view_widget = self.ui.matplotlib_view_widgets.get(identifier, None)
        if active_matplotlib_view_widget is not None:
            if sync_mode.name == SynchronizedPlotMode.NO_SYNC.name:
                # disable syncing
                sync_connection = self.ui.connections.get(identifier, None)
                if sync_connection is not None:
                    # have an existing sync connection, need to disconnect it.
                    print(f'disconnecting window_scrolled for "{identifier}"')
                    self.window_scrolled.disconnect(sync_connection)
                    # print(f'WARNING: connection exists!')
                    self.ui.connections[identifier] = None
                    del self.ui.connections[identifier] # remove the connection after disconnecting it.

                return None
            elif sync_mode.name == SynchronizedPlotMode.TO_GLOBAL_DATA.name:
                ## Synchronize just once to the global data:
                # disable active window syncing if it's enabled:
                sync_connection = self.ui.connections.get(identifier, None)
                if sync_connection is not None:
                    # have an existing sync connection, need to disconnect it.
                    print(f'\tdisconnecting window_scrolled for "{identifier}"')
                    self.window_scrolled.disconnect(sync_connection)
                    # print(f'WARNING: connection exists!')
                    self.ui.connections[identifier] = None
                    del self.ui.connections[identifier] # remove the connection after disconnecting it.

                # Perform Initial (one-time) update from source -> controlled:
                if hasattr(self, 'spikes_window') and hasattr(self.spikes_window, 'total_df_start_end_times'):
                    active_matplotlib_view_widget.on_window_changed(self.spikes_window.total_df_start_end_times[0], self.spikes_window.total_df_start_end_times[1])
                elif hasattr(self, 'total_data_start_time') and hasattr(self, 'total_data_end_time'):
                    active_matplotlib_view_widget.on_window_changed(self.total_data_start_time, self.total_data_end_time)
                else:
                    print(f'WARNING: Cannot sync to global data - missing required attributes (spikes_window.total_df_start_end_times or total_data_start_time/total_data_end_time)')
                return None

            elif sync_mode.name == SynchronizedPlotMode.TO_WINDOW.name:
                # Perform Initial (one-time) update from source -> controlled:
                if hasattr(self, 'spikes_window') and hasattr(self.spikes_window, 'active_window_start_time'):
                    active_matplotlib_view_widget.on_window_changed(self.spikes_window.active_window_start_time, self.spikes_window.active_window_end_time)
                elif hasattr(self, 'active_window_start_time') and hasattr(self, 'active_window_end_time'):
                    active_matplotlib_view_widget.on_window_changed(self.active_window_start_time, self.active_window_end_time)
                else:
                    print(f'WARNING: Cannot sync to window - missing required attributes (spikes_window.active_window_start_time/active_window_end_time or active_window_start_time/active_window_end_time)')
                
                if hasattr(self, 'window_scrolled'):
                    sync_connection = self.window_scrolled.connect(active_matplotlib_view_widget.on_window_changed)
                    self.ui.connections[identifier] = sync_connection # add the connection to the connections array
                    return sync_connection # return the connection
                else:
                    print(f'WARNING: Cannot sync to window - missing window_scrolled signal')
                    return None
            else:
                raise NotImplementedError(f'Unknown sync_mode: {sync_mode}')

        else:
            print(f'WARNING: active_matplotlib_view_widget with identifier "{identifier}" was not found!')
            return None


    @function_attributes(short_name=None, tags=['interval', 'tracks', 'pyqtgraph', 'specific', 'dynamic_ui', 'group_matplotlib_render_plot_widget'], input_requires=[], output_provides=[], uses=['self.add_new_embedded_pyqtgraph_render_plot_widget'], used_by=[], creation_date='2025-01-09 10:50', related_items=[])
    def prepare_pyqtgraph_intervalPlot_tracks(self, enable_interval_overview_track: bool = False, should_remove_all_and_re_add: bool=True, name_modifier_suffix: str='', should_link_to_main_plot_widget:bool=True, interval_dock_max_height: int=89, sync_mode:SynchronizedPlotMode=None, debug_print=False):
        """ adds to separate pyqtgraph-backed tracks to the timeline for rendering intervals, and updates `self.params.custom_interval_rendering_plots` so the intervals are rendered on these new tracks in addition to any normal ones
        
        enable_interval_overview_track: bool: if True, renders a track to show all the intervals during the sessions (overview) in addition to the track for the intervals within the current active window
        should_remove_all_and_re_add: bool: if True, all intervals are removed from all plots and then re-added (safer) method
        
        Updates:
            self.params.custom_interval_rendering_plots (if self.params exists)

        This should be a separate file, and there should be multiple classes of tracks (raster, intervals, etc) 
            
        Usage:
            _interval_tracks_out_dict = self.prepare_pyqtgraph_intervalPlot_tracks(enable_interval_overview_track=True, should_remove_all_and_re_add=True, should_link_to_main_plot_widget=False)
                        
            interval_window_dock_config, intervals_dock, intervals_time_sync_pyqtgraph_widget, intervals_root_graphics_layout_widget, intervals_plot_item = _interval_tracks_out_dict['intervals']
            if 'interval_overview' in _interval_tracks_out_dict:
                interval_overview_window_dock_config, intervals_overview_dock, intervals_overview_time_sync_pyqtgraph_widget, intervals_overview_root_graphics_layout_widget, intervals_overview_plot_item = _interval_tracks_out_dict['interval_overview']
                intervals_overview_plot_item.setXRange(self.total_data_start_time, self.total_data_end_time, padding=0) ## global frame
                    
                
        """
        import pyphoplacecellanalysis.External.pyqtgraph as pg

        if sync_mode is None:
            sync_mode = SynchronizedPlotMode.TO_WINDOW
            
        _interval_tracks_out_dict = {}
        if enable_interval_overview_track:
            intervals_overview_dock_config = CustomCyclicColorsDockDisplayConfig(named_color_scheme=NamedColorScheme.grey, showCloseButton=False, showTimelineSyncModeButton=False, corner_radius='0px', hideTitleBar=True)
            overview_identifier_name = f'interval_overview{name_modifier_suffix}'
            intervals_overview_time_sync_pyqtgraph_widget, intervals_overview_root_graphics_layout_widget, intervals_overview_plot_item, intervals_overview_dock = self.add_new_embedded_pyqtgraph_render_plot_widget(name=overview_identifier_name, dockSize=(500, 60), display_config=intervals_overview_dock_config)
            if (interval_dock_max_height is not None) and (interval_dock_max_height > 0):
                intervals_overview_dock.setMaximumHeight(interval_dock_max_height)
            _interval_tracks_out_dict[overview_identifier_name] = (intervals_overview_dock_config, intervals_overview_dock, intervals_overview_time_sync_pyqtgraph_widget, intervals_overview_root_graphics_layout_widget, intervals_overview_plot_item)
            if hasattr(self, 'total_data_start_time') and hasattr(self, 'total_data_end_time'):
                # Convert to datetime then Unix timestamp if reference_datetime is available
                if hasattr(self, 'reference_datetime') and self.reference_datetime is not None:
                    from pypho_timeline.utils.datetime_helpers import float_to_datetime, datetime_to_unix_timestamp
                    dt_start = float_to_datetime(self.total_data_start_time, self.reference_datetime)
                    dt_end = float_to_datetime(self.total_data_end_time, self.reference_datetime)
                    # Convert datetime to Unix timestamp for PyQtGraph (DateAxisItem expects timestamps but displays as dates)
                    unix_start = datetime_to_unix_timestamp(dt_start)
                    unix_end = datetime_to_unix_timestamp(dt_end)
                    intervals_overview_plot_item.setXRange(unix_start, unix_end, padding=0)
                else:
                    intervals_overview_plot_item.setXRange(self.total_data_start_time, self.total_data_end_time, padding=0) ## global frame
            

        ## Enables creating a new pyqtgraph-based track to display the intervals/epochs
        interval_window_dock_config = CustomCyclicColorsDockDisplayConfig(named_color_scheme=NamedColorScheme.grey, showCloseButton=False, corner_radius='0px', hideTitleBar=True)
        identifier_name = f'intervals{name_modifier_suffix}'
        intervals_time_sync_pyqtgraph_widget, intervals_root_graphics_layout_widget, intervals_plot_item, intervals_dock = self.add_new_embedded_pyqtgraph_render_plot_widget(name=identifier_name, dockSize=(10, 4), display_config=interval_window_dock_config)
        if (interval_dock_max_height is not None) and (interval_dock_max_height > 0):
            intervals_dock.setMaximumHeight(interval_dock_max_height)
            
        if hasattr(self, 'params') and hasattr(self.params, 'custom_interval_rendering_plots'):
            self.params.custom_interval_rendering_plots.append(intervals_plot_item) # = [self.plots.background_static_scroll_window_plot, self.plots.main_plot_widget, intervals_plot_item]
        elif hasattr(self, 'params'):
            self.params.custom_interval_rendering_plots = [intervals_plot_item]

        if enable_interval_overview_track:
            if hasattr(self, 'params') and hasattr(self.params, 'custom_interval_rendering_plots'):
                self.params.custom_interval_rendering_plots.append(intervals_overview_plot_item)
            

        _interval_tracks_out_dict[identifier_name] = (interval_window_dock_config, intervals_dock, intervals_time_sync_pyqtgraph_widget, intervals_root_graphics_layout_widget, intervals_plot_item)

        if should_link_to_main_plot_widget and hasattr(self, 'plots') and hasattr(self.plots, 'main_plot_widget') and (self.plots.main_plot_widget is not None):
            main_plot_widget = self.plots.main_plot_widget # PlotItem
            intervals_plot_item.setXLink(main_plot_widget) # works to synchronize the main zoomed plot (current window) with the epoch_rect_separate_plot (rectangles plotter)
        else:
            ## setup the synchronization:
            if enable_interval_overview_track and (overview_identifier_name is not None):
                self.sync_matplotlib_render_plot_widget(overview_identifier_name, sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA) # Sync it with the active window:

            # 2025-05-12 - more modern syncing ___________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________ #
            self.sync_matplotlib_render_plot_widget(identifier_name, sync_mode=sync_mode) # Sync it with the active window:
            
            if 'button_action_callbacks' not in intervals_dock.connections:
                intervals_dock.connections['button_action_callbacks'] = {} ## initialize to new
            _out_connections = intervals_dock.connections['button_action_callbacks']
            _prev_conn = _out_connections.pop(identifier_name, None)
            if _prev_conn is not None:
                intervals_dock.sigToggleTimelineSyncModeClicked.disconnect(_prev_conn)
                _prev_conn = None

            assert identifier_name == intervals_dock._name
            # sync_connection = _out_connections.get(identifier_name, None)
            if hasattr(self, 'on_toggle_timeline_sync_mode'):
                _out_connections[identifier_name] = intervals_dock.sigToggleTimelineSyncModeClicked.connect(self.on_toggle_timeline_sync_mode)
            # dock_item.connections['button_action_callbacks'].update(_out_connections)
            intervals_dock.connections['button_action_callbacks'] = _out_connections


        return _interval_tracks_out_dict

