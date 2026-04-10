"""TrackRenderingMixin - Mixin for rendering timeline tracks with async detail loading."""
from typing import Dict, Optional, List, Tuple, Any
import pandas as pd
from qtpy import QtCore
import pyqtgraph as pg
from pyqtgraph import SignalProxy

import phopymnehelper.type_aliases as types
from pyphocorehelpers.gui.Qt.ExceptionPrintingSlot import pyqtExceptionPrintingSlot
from pyphocorehelpers.DataStructure.general_parameter_containers import RenderPlotsData

from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource
from pypho_timeline.rendering.graphics.track_renderer import TrackRenderer
from pypho_timeline.rendering.async_detail_fetcher import AsyncDetailFetcher
from pypho_timeline.rendering.mixins.epoch_rendering_mixin import EpochRenderingMixin

from pypho_timeline.core.pyqtgraph_time_synchronized_widget import PyqtgraphTimeSynchronizedWidget


class TrackRenderingMixin(EpochRenderingMixin):
    """Mixin for rendering timeline tracks with overview intervals and async detail loading.
    
    Extends EpochRenderingMixin to add support for tracks that can load detailed data
    asynchronously when intervals scroll into the viewport.
    
    Requires:
        self.plots
        self.plots_data
        self.ui
        self.ui.connections
        
    Provides:
        self.plots_data['track_datasources']: RenderPlotsData
        self.plots.track_renderers: Dict[str, TrackRenderer]
        self.async_detail_fetcher: AsyncDetailFetcher
    """
    
    sigTrackAdded = QtCore.Signal(str)  # track_id
    sigTrackRemoved = QtCore.Signal(str)  # track_id
    sigTrackDetailLoaded = QtCore.Signal(str, pd.DataFrame, object)  # track_id, interval, detail_data
    
    @property
    def track_datasources(self) -> RenderPlotsData:
        """The track_datasources property. A RenderPlotsData object."""
        return self.plots_data['track_datasources']
    
    @property
    def track_renderers(self) -> Dict[str, TrackRenderer]:
        """The track_renderers property. Dictionary mapping track names to TrackRenderer instances."""
        return self.plots.track_renderers
    
    @property
    def async_detail_fetcher(self) -> AsyncDetailFetcher:
        """The async_detail_fetcher property."""
        return self.plots_data['async_detail_fetcher']

    @property
    def track_window_sync_groups(self) -> Dict[str, str]:
        """Map of track name to window sync group."""
        return self.plots_data['track_window_sync_groups']
    
    @pyqtExceptionPrintingSlot()
    def TrackRenderingMixin_on_init(self):
        """Perform any parameters setting/checking during init."""
        # Initialize parent
        self.EpochRenderingMixin_on_init()
        
        # Initialize track rendering data structures
        self.plots_data['track_datasources'] = RenderPlotsData('TrackRenderingMixin')
        self.plots_data['track_window_sync_groups'] = {}
        self.plots.track_renderers = {}
        
        # Create async detail fetcher
        self.plots_data['async_detail_fetcher'] = AsyncDetailFetcher(max_cache_size=100)
    
    @pyqtExceptionPrintingSlot()
    def TrackRenderingMixin_on_setup(self):
        """Perform setup/creation of widget/graphical/data objects."""
        # Initialize parent
        self.EpochRenderingMixin_on_setup()
        
        # Ensure async fetcher exists
        if 'async_detail_fetcher' not in self.plots_data:
            self.plots_data['async_detail_fetcher'] = AsyncDetailFetcher(max_cache_size=100)
        if 'track_window_sync_groups' not in self.plots_data:
            self.plots_data['track_window_sync_groups'] = {}
    
    @pyqtExceptionPrintingSlot()
    def TrackRenderingMixin_on_buildUI(self):
        """Perform setup/creation of widget/graphical/data objects."""
        # Initialize parent
        self.EpochRenderingMixin_on_buildUI()
        
        # Ensure track rendering is initialized
        if 'track_datasources' not in self.plots_data:
            self.TrackRenderingMixin_on_init()
        
        if not hasattr(self.plots, 'track_renderers'):
            self.plots.track_renderers = {}
        
        # Connect to viewport change signals if available
        # Try to connect to window_scrolled signal (from SpecificDockWidgetManipulatingMixin)
        if hasattr(self, 'window_scrolled'):
            if 'track_viewport_connection' not in self.ui.connections:
                self.ui.connections['track_viewport_connection'] = self.window_scrolled.connect(
                    self.TrackRenderingMixin_on_window_update
                )
        
        # Also connect to viewport changes via PlotItem if available
        # This will be set up per plot item when tracks are added
    
    @pyqtExceptionPrintingSlot()
    def TrackRenderingMixin_on_destroy(self):
        """Perform teardown/destruction of anything that needs to be manually removed."""
        # Remove all tracks
        for track_name in list(self.track_renderers.keys()):
            self.remove_track(track_name)
        
        # Clear async fetcher
        if 'async_detail_fetcher' in self.plots_data:
            self.async_detail_fetcher.cancel_all_pending_fetches()
            self.async_detail_fetcher.clear_cache()
        
        # Call parent destroy
        self.EpochRenderingMixin_on_destroy()
    

    def add_track(self, track_datasource: TrackDatasource, name: str, plot_item: Optional[pg.PlotItem] = None, window_sync_group: str = 'primary', **kwargs) -> TrackRenderer:
        """Add a new track to the timeline.
        
        Updates:
            self.track_datasources, self.track_renderers

        Args:
            track_datasource: TrackDatasource providing overview and detail data
            name: Unique name for this track
            plot_item: PlotItem to render into (if None, uses interval_rendering_plots[0])
            **kwargs: Additional configuration (height, colors, etc.)
            
        Returns:
            TrackRenderer instance for this track
        """
        ## try to find existing items first:
        extant_track_datasource: Optional[TrackDatasource] = self.track_datasources.get(name, None)
        track_renderer: Optional[TrackRenderer] = self.track_renderers.get(name, None)
        widget: PyqtgraphTimeSynchronizedWidget = self.ui.matplotlib_view_widgets.get(name, None)


        does_item_exist: bool = (extant_track_datasource is not None) and (track_renderer is not None) and (widget is not None)
        if (not does_item_exist):
            # Get plot item
            if plot_item is None:
                interval_plots = self.interval_rendering_plots
                if len(interval_plots) == 0:
                    raise ValueError("No interval rendering plots available. Override interval_rendering_plots property.")
                plot_item = interval_plots[0]
            
            # Store datasource
            self.track_datasources[name] = track_datasource
            self.set_track_window_sync_group(name, window_sync_group)
            
            # Create track renderer
            track_renderer = TrackRenderer(track_id=name, datasource=track_datasource, plot_item=plot_item, async_fetcher=self.async_detail_fetcher, **kwargs)
            
            # Connect signals
            track_renderer.detail_loaded.connect(lambda tid, iv, dd: self.sigTrackDetailLoaded.emit(tid, iv, dd))
            
            # Connect track renderer to widget if plot_item belongs to a PyqtgraphTimeSynchronizedWidget
            # This enables the options panel functionality
            # TODO 2025-01-06 - does this enable a strong reference cycle? _______________________________________________________________________________________________________________________________________________________________________________________________________________________ #
            # Connect to viewport changes via PlotItem's ViewBox
            viewbox = plot_item.getViewBox()
            if viewbox is not None:
                # Enable panning/zooming only on the x-axis
                viewbox.setMouseEnabled(x=True, y=False)
                viewbox.enableAutoRange(x=False, y=False) ## disable auto-ranging
                # viewbox.setXRange(300, 450)
                # viewbox.setYRange(0.0, 1.0)
                # viewbox.setAutoVisible(x=False, y=True)

                # Use SignalProxy to rate-limit viewport updates
                proxy_key = f'track_viewport_{name}'
                if proxy_key not in self.ui.connections:
                    proxy = SignalProxy(viewbox.sigRangeChanged, rateLimit=30, slot=lambda evt: self._on_plot_viewport_changed(name, evt)) # Limit to 30 updates per second
                    self.ui.connections[proxy_key] = proxy
                try:
                    if hasattr(self, 'ui') and hasattr(self.ui, 'matplotlib_view_widgets') and name in self.ui.matplotlib_view_widgets:
                        widget = self.ui.matplotlib_view_widgets[name]
                        if isinstance(widget, PyqtgraphTimeSynchronizedWidget):
                            widget.set_track_renderer(track_renderer)
                            if hasattr(self.ui, 'dynamic_docked_widget_container'):
                                dock_item = self.ui.dynamic_docked_widget_container.find_display_dock(identifier=name)
                                if dock_item is not None and hasattr(dock_item, 'updateWidgetsHaveOptionsPanel'):
                                    dock_item.updateWidgetsHaveOptionsPanel()
                except (ImportError, AttributeError, KeyError):
                    pass

            # Store renderer
            self.track_renderers[name] = track_renderer

            # Defer initial viewport update to avoid blocking UI during initialization
            # Use QTimer.singleShot(0) to schedule after current event loop iteration
            if viewbox is not None:
                def deferred_viewport_update():
                    x_range, y_range = viewbox.viewRange()
                    if len(x_range) == 2:
                        track_renderer.update_viewport(x_range[0], x_range[1])
                QtCore.QTimer.singleShot(0, deferred_viewport_update)

            # Emit signal
            self.sigTrackAdded.emit(name)

        else:
            print(f'WARN: item already exists!')


        
        return track_renderer
    
    
    def _on_plot_viewport_changed(self, track_name: str, evt):
        """Handle viewport change from a plot's ViewBox.
        
        Args:
            track_name: Name of the track
            evt: Event from SignalProxy(sigRangeChanged): tuple (viewbox, view_range, changed).
                 view_range is (x_range, y_range).
        """
        if getattr(self, '_applying_window_from_signal', False):
            return
        if track_name not in self.track_renderers:
            return
        # ViewBox.sigRangeChanged emits (self, viewRange, changed); SignalProxy forwards as single tuple
        _, view_range, _ = evt
        x_range, y_range = view_range
        if len(x_range) == 2:
            # Defer the update to avoid blocking the signal handler. Read x-range from the ViewBox
            # when the timer runs — not from evt — so programmatic jumps (interval prev/next) are not
            # overwritten by a stale closure after setXRange updated the plot.
            def deferred_update():
                if getattr(self, '_applying_window_from_signal', False):
                    return
                tr = self.track_renderers.get(track_name, None)
                if tr is None:
                    return
                vb = tr.plot_item.getViewBox() if tr.plot_item is not None else None
                if vb is None:
                    return
                vr = vb.viewRange()
                if len(vr) < 1 or len(vr[0]) != 2:
                    return
                x0, x1 = float(vr[0][0]), float(vr[0][1])
                if x0 > x1:
                    x0, x1 = x1, x0
                tr.update_viewport(x0, x1)
                if self.get_track_window_sync_group(track_name) != 'primary':
                    return
                apply_fn = getattr(self, 'apply_active_window_from_plot_x', None)
                if apply_fn is None:
                    return
                la0 = getattr(self, '_last_applied_plot_window_x0', None)
                la1 = getattr(self, '_last_applied_plot_window_x1', None)
                eps = max(1e-6, (x1 - x0) * 1e-12)
                if la0 is not None and la1 is not None and abs(x0 - la0) < eps and abs(x1 - la1) < eps:
                    return
                # Emit window_scrolled so overview strip / calendar / tables sync; sigViewportChanged uses block_signals True.
                apply_fn(x0, x1, False)
            QtCore.QTimer.singleShot(0, deferred_update)
    
    
    def remove_track(self, name: str):
        """Remove a track from the timeline.
        
        Args:
            name: Name of the track to remove
        """
        if name not in self.track_renderers:
            return
        
        # Remove renderer
        track_renderer = self.track_renderers[name]
        track_renderer.remove()
        del self.track_renderers[name]
        
        # Remove datasource
        if name in self.track_datasources:
            del self.track_datasources[name]
        self.track_window_sync_groups.pop(name, None)
        
        # Cancel pending fetches
        self.async_detail_fetcher.cancel_all_pending_fetches(name)
        
        # Emit signal
        self.sigTrackRemoved.emit(name)


    # LiveWindowEventIntervalMonitoringMixin Conformances
    def find_intervals_in_active_window(self, debug_print: bool = False) -> Dict[str, pd.DataFrame]:
        """Find interval and track datasource rows overlapping the active window.
        """
        limited_interval_dfs_output_column_names = ['t_start', 't_duration', 't_end']

        active_window_dt = getattr(getattr(self, 'spikes_window', None), 'active_time_window', None)
        if active_window_dt is not None:
            new_start_dt, new_end_dt = active_window_dt
        else:
            new_start_dt = getattr(self, 'active_window_start_time', None)
            new_end_dt = getattr(self, 'active_window_end_time', None)

        if new_start_dt is None or new_end_dt is None:
            return {}

        curr_window_start: float = self._window_value_to_signal_float(new_start_dt) # self._last_applied_plot_window_x0
        curr_window_end: float = self._window_value_to_signal_float(new_end_dt) # self._last_applied_plot_window_x1
        ## OUTPUTS: curr_window_start, curr_window_end


        ## BEGIN FUNCTION BODY:
        visible_intervals_dict: Dict[str, pd.DataFrame] = {}
        seen_datasource_names = set()

        ## `timeline.interval_datasource_names` is None for some reason even on a valid timeline object
        for datasource_name in self.interval_datasource_names:
            datasource = self.interval_datasources.get(datasource_name, None)
            if datasource is None or (not hasattr(datasource, 'get_updated_data_window')):
                continue
            # visible_intervals_dict[datasource_name] = datasource.get_updated_data_window(new_start_dt, new_end_dt)
            visible_intervals_dict[datasource_name] = datasource.get_updated_data_window(curr_window_start, curr_window_end)
            if (limited_interval_dfs_output_column_names is not None) and (visible_intervals_dict[datasource_name] is not None):
                visible_intervals_dict[datasource_name] = visible_intervals_dict[datasource_name][limited_interval_dfs_output_column_names] ## subset to the included columns
            seen_datasource_names.add(datasource_name)

        track_datasource_names = getattr(self.track_datasources, 'dynamically_added_attributes', [])
        for datasource_name in track_datasource_names:
            if datasource_name in seen_datasource_names:
                continue
            datasource = self.track_datasources.get(datasource_name, None)
            if datasource is None or (not hasattr(datasource, 'get_updated_data_window')):
                continue
            # visible_intervals_dict[datasource_name] = datasource.get_updated_data_window(new_start_dt, new_end_dt)
            visible_intervals_dict[datasource_name] = datasource.get_updated_data_window(curr_window_start, curr_window_end)
            if (limited_interval_dfs_output_column_names is not None) and (visible_intervals_dict[datasource_name] is not None):
                visible_intervals_dict[datasource_name] = visible_intervals_dict[datasource_name][limited_interval_dfs_output_column_names] ## subset to the included columns

        if debug_print:
            visible_counts_dict = {datasource_name: len(intervals_df) for datasource_name, intervals_df in visible_intervals_dict.items()}
            print(f'TrackRenderingMixin.find_intervals_in_active_window(...): {visible_counts_dict}')

        ## OUTPUTS: visible_intervals_dict
        return visible_intervals_dict


    @pyqtExceptionPrintingSlot(float, float)
    def TrackRenderingMixin_on_window_update(self, new_start: Optional[float] = None, new_end: Optional[float] = None):
        """Called when the viewport window changes. Updates all track renderers.
        
        Args:
            new_start: New start time of viewport
            new_end: New end time of viewport
        """
        if new_start is None or new_end is None:
            return

        self._schedule_track_group_window_update(window_sync_group='primary', new_start=new_start, new_end=new_end)
        self.EpochRenderingMixin_on_window_update(new_start, new_end)


    def set_track_window_sync_group(self, name: str, window_sync_group: str = 'primary'):
        """Register which window sync group controls a track renderer."""
        self.track_window_sync_groups[name] = window_sync_group


    def get_track_window_sync_group(self, name: str) -> str:
        """Get the window sync group for a track renderer."""
        return self.track_window_sync_groups.get(name, 'primary')


    def get_track_names_for_window_sync_group(self, window_sync_group: str = 'primary') -> List[str]:
        """Get all track names in a window sync group."""
        return [track_name for track_name in self.track_renderers.keys() if self.get_track_window_sync_group(track_name) == window_sync_group]


    def _schedule_track_group_window_update(self, window_sync_group: str = 'primary', new_start: Optional[float] = None, new_end: Optional[float] = None):
        """Schedule viewport updates for all renderers in a sync group."""
        if new_start is None or new_end is None:
            return

        grouped_track_items = [(track_name, track_renderer) for track_name, track_renderer in self.track_renderers.items() if self.get_track_window_sync_group(track_name) == window_sync_group]

        # Schedule each track's update asynchronously with small delays to prevent blocking.
        # This lets compare renderers opt out of the primary window while still sharing the same fetcher/cache.
        for idx, (track_name, track_renderer) in enumerate(grouped_track_items):
            def make_update_fn(renderer, start, end):
                def update_fn():
                    renderer.update_viewport(start, end)
                return update_fn
            # Stagger updates by 1ms per track to allow event loop processing between tracks
            QtCore.QTimer.singleShot(idx * 1, make_update_fn(track_renderer, new_start, new_end))
    
    
    def get_track(self, name: str) -> Optional[TrackRenderer]:
        """Get a track renderer by name.
        
        Args:
            name: Track name
            
        Returns:
            TrackRenderer instance or None if not found
        """
        return self.track_renderers.get(name, None)
    


    def get_track_tuple(self, name: str) -> Tuple[Optional[PyqtgraphTimeSynchronizedWidget], Optional[TrackRenderer], Optional[TrackDatasource]]:
        """Get a track renderer by name.

        Args:
            name: Track name

        Returns:
            TrackRenderer instance or None if not found
        """
        extant_track_datasource: Optional[TrackDatasource] = self.track_datasources.get(name, None)
        track_renderer: Optional[TrackRenderer] = self.track_renderers.get(name, None)
        widget: Optional[PyqtgraphTimeSynchronizedWidget] = self.ui.matplotlib_view_widgets.get(name, None)
        return widget, track_renderer, extant_track_datasource



    def get_all_track_names(self) -> List[str]:
        """Get list of all track names.
        
        Returns:
            List of track names
        """
        return list(self.track_renderers.keys())


__all__ = ['TrackRenderingMixin']

