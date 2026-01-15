"""TrackRenderingMixin - Mixin for rendering timeline tracks with async detail loading."""
from typing import Dict, Optional, List
import pandas as pd
from qtpy import QtCore
import pyphoplacecellanalysis.External.pyqtgraph as pg

from pyphocorehelpers.gui.Qt.ExceptionPrintingSlot import pyqtExceptionPrintingSlot
from pyphocorehelpers.DataStructure.general_parameter_containers import RenderPlotsData
from pyphocorehelpers.gui.PhoUIContainer import PhoUIContainer

from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource
from pypho_timeline.rendering.graphics.track_renderer import TrackRenderer
from pypho_timeline.rendering.async_detail_fetcher import AsyncDetailFetcher
from pypho_timeline.rendering.mixins.epoch_rendering_mixin import EpochRenderingMixin


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
    sigTrackDetailLoaded = QtCore.Signal(str, pd.Series, object)  # track_id, interval, detail_data
    
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
    
    @pyqtExceptionPrintingSlot()
    def TrackRenderingMixin_on_init(self):
        """Perform any parameters setting/checking during init."""
        # Initialize parent
        self.EpochRenderingMixin_on_init()
        
        # Initialize track rendering data structures
        self.plots_data['track_datasources'] = RenderPlotsData('TrackRenderingMixin')
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
    
    def add_track(self, track_datasource: TrackDatasource, name: str, plot_item: Optional[pg.PlotItem] = None, **kwargs) -> TrackRenderer:
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
        # Get plot item
        if plot_item is None:
            interval_plots = self.interval_rendering_plots
            if len(interval_plots) == 0:
                raise ValueError("No interval rendering plots available. Override interval_rendering_plots property.")
            plot_item = interval_plots[0]
        
        # Store datasource
        self.track_datasources[name] = track_datasource
        
        # Create track renderer
        track_renderer = TrackRenderer(
            track_id=name,
            datasource=track_datasource,
            plot_item=plot_item,
            async_fetcher=self.async_detail_fetcher
        )
        
        # Connect signals
        track_renderer.detail_loaded.connect(
            lambda tid, iv, dd: self.sigTrackDetailLoaded.emit(tid, iv, dd)
        )
        
        # Connect to viewport changes via PlotItem's ViewBox
        viewbox = plot_item.getViewBox()
        if viewbox is not None:
            # Use SignalProxy to rate-limit viewport updates
            from pyphoplacecellanalysis.External.pyqtgraph import SignalProxy
            proxy_key = f'track_viewport_{name}'
            if proxy_key not in self.ui.connections:
                proxy = SignalProxy(
                    viewbox.sigRangeChanged,
                    rateLimit=30,  # Limit to 30 updates per second
                    slot=lambda evt: self._on_plot_viewport_changed(name, evt)
                )
                self.ui.connections[proxy_key] = proxy
        
        # Store renderer
        self.track_renderers[name] = track_renderer
        
        # Connect track renderer to widget if plot_item belongs to a PyqtgraphTimeSynchronizedWidget
        # This enables the options panel functionality
        # TODO 2025-01-06 - does this enable a strong reference cycle? _______________________________________________________________________________________________________________________________________________________________________________________________________________________ #
        try:
            from pypho_timeline.core.pyqtgraph_time_synchronized_widget import PyqtgraphTimeSynchronizedWidget
            # Try to find the parent widget that contains this plot_item
            # The plot_item is part of a GraphicsLayoutWidget, which is part of PyqtgraphTimeSynchronizedWidget
            graphics_layout = plot_item.parentItem()
            if graphics_layout is not None:
                # Find the widget by traversing up the parent chain or searching
                # Actually, we can search for widgets in the timeline that match the track name
                if hasattr(self, 'ui') and hasattr(self.ui, 'matplotlib_view_widgets'):
                    widget_name = name
                    if widget_name in self.ui.matplotlib_view_widgets:
                        widget = self.ui.matplotlib_view_widgets[widget_name]
                        if isinstance(widget, PyqtgraphTimeSynchronizedWidget):
                            widget.set_track_renderer(track_renderer)
        except (ImportError, AttributeError, KeyError):
            # If widget connection fails, continue without options panel
            pass
        
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
        
        return track_renderer
    
    
    def _on_plot_viewport_changed(self, track_name: str, evt):
        """Handle viewport change from a plot's ViewBox.
        
        Args:
            track_name: Name of the track
            evt: Event from ViewBox.sigRangeChanged (contains (x_range, y_range))
        """
        if track_name not in self.track_renderers:
            return
        
        x_range, y_range = evt
        if len(x_range) == 2:
            # Defer the update to avoid blocking the signal handler
            def deferred_update():
                self.track_renderers[track_name].update_viewport(x_range[0], x_range[1])
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
        
        # Cancel pending fetches
        self.async_detail_fetcher.cancel_all_pending_fetches(name)
        
        # Emit signal
        self.sigTrackRemoved.emit(name)


    @pyqtExceptionPrintingSlot(float, float)
    def TrackRenderingMixin_on_window_update(self, new_start: Optional[float] = None, new_end: Optional[float] = None):
        """Called when the viewport window changes. Updates all track renderers.
        
        Args:
            new_start: New start time of viewport
            new_end: New end time of viewport
        """
        if new_start is None or new_end is None:
            return
        
        # Schedule each track's update asynchronously with small delays to prevent blocking
        # This ensures the UI remains responsive even if one track is slow
        for idx, (track_name, track_renderer) in enumerate(self.track_renderers.items()):
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
    

    def get_all_track_names(self) -> List[str]:
        """Get list of all track names.
        
        Returns:
            List of track names
        """
        return list(self.track_renderers.keys())


__all__ = ['TrackRenderingMixin']

