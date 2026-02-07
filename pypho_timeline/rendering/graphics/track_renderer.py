"""TrackRenderer - Manages overview rectangles and detail overlays for timeline tracks."""
import numpy as np
from typing import Dict, List, Optional, Set, Any
import logging
from datetime import datetime
import pandas as pd
from qtpy import QtCore
import pyphoplacecellanalysis.External.pyqtgraph as pg

from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, DetailRenderer
from pypho_timeline.rendering.graphics.interval_rects_item import IntervalRectsItem, IntervalRectsItemData
from pypho_timeline.rendering.async_detail_fetcher import AsyncDetailFetcher, _format_interval_for_log, _format_time_value_for_log
from pypho_timeline.rendering.helpers.render_rectangles_helper import Render2DEventRectanglesHelper
from pypho_timeline.utils.logging_util import get_rendering_logger

# Import VideoTrackDatasource for type checking
try:
    from pypho_timeline.rendering.datasources.specific.video import VideoTrackDatasource
except ImportError:
    VideoTrackDatasource = None

# Import vispy renderer
try:
    from pypho_timeline.rendering.graphics.vispy_video_epoch_renderer import VispyVideoEpochRenderer, VISPY_AVAILABLE
except ImportError:
    VispyVideoEpochRenderer = None
    VISPY_AVAILABLE = False

logger = get_rendering_logger(__name__)


class TrackRenderer(QtCore.QObject):
    """Manages rendering of a single track with overview intervals and detail overlays.
    
    This class handles:
    - Rendering overview intervals as rectangles
    - Monitoring viewport changes to detect intervals entering/exiting
    - Triggering async fetches for detailed data
    - Overlaying detailed views on top of overview rectangles
    """
    
    # Signal emitted when detail data is loaded for an interval
    detail_loaded = QtCore.Signal(str, pd.DataFrame, object)  # track_id, interval, detail_data
    
    def __init__(self, track_id: str, datasource: TrackDatasource, plot_item: pg.PlotItem,
                 async_fetcher: AsyncDetailFetcher, parent=None):
        """Initialize the track renderer.
        
        Args:
            track_id: Unique identifier for this track
            datasource: TrackDatasource providing overview and detail data
            plot_item: pyqtgraph PlotItem to render into
            async_fetcher: AsyncDetailFetcher for fetching detailed data
            parent: Parent QObject
        """
        super().__init__(parent)
        self.track_id = track_id
        self.datasource = datasource
        self.plot_item = plot_item
        self.async_fetcher = async_fetcher
        
        # Overview rendering
        self.overview_rects_item: Optional[IntervalRectsItem] = None
        self.vispy_renderer: Optional[VispyVideoEpochRenderer] = None
        self.use_vispy = False
        
        # Detail rendering state
        self.detail_renderer: DetailRenderer = datasource.get_detail_renderer()
        self.detail_graphics: Dict[str, List[pg.GraphicsObject]] = {}  # cache_key -> graphics objects
        self.visible_intervals: Set[str] = set()  # Set of cache keys currently in viewport
        self._overview_df: Optional[pd.DataFrame] = None  # Store overview intervals for mapping rectangle indices
        
        # Channel visibility state (for channel-based renderers)
        self.channel_visibility: Dict[str, bool] = {}
        self._options_panel = None  # Reference to options panel if available
        
        # Initialize channel visibility from detail renderer if it has channel_names
        if hasattr(self.detail_renderer, 'channel_names') and self.detail_renderer.channel_names is not None:
            channel_names = self.detail_renderer.channel_names
            self.channel_visibility = {channel: True for channel in channel_names}
            logger.debug(f"TrackRenderer[{self.track_id}] Initialized channel visibility for {len(channel_names)} channels")
        
        # Log initialization
        datasource_type = type(datasource).__name__
        detail_renderer_type = type(self.detail_renderer).__name__ if self.detail_renderer is not None else "None"
        logger.info(f"TrackRenderer[{self.track_id}] Initialized with datasource type={datasource_type}, detail_renderer={detail_renderer_type}")
        
        # Check if we should use vispy renderer for video tracks
        if VideoTrackDatasource is not None and isinstance(self.datasource, VideoTrackDatasource):
            if hasattr(self.datasource, 'use_vispy_renderer') and self.datasource.use_vispy_renderer:
                if VISPY_AVAILABLE and VispyVideoEpochRenderer is not None:
                    self.use_vispy = True
                    logger.info(f"TrackRenderer[{self.track_id}] Using vispy renderer for video track")
                else:
                    logger.warning(f"TrackRenderer[{self.track_id}] vispy requested but not available, falling back to pyqtgraph")
        
        # Connect to async fetcher
        self.async_fetcher.detail_data_ready.connect(self._on_detail_data_ready)
        logger.debug(f"TrackRenderer[{self.track_id}] Connected to async_fetcher.detail_data_ready signal")
        
        # Initialize overview rendering
        self._update_overview()
    

    def _update_overview(self):
        """Update the overview interval rectangles."""
        logger.debug(f"TrackRenderer[{self.track_id}] _update_overview() - starting")
        try:
            # Get overview intervals
            overview_df = self.datasource.get_overview_intervals()
            num_intervals = len(overview_df)
            logger.debug(f"TrackRenderer[{self.track_id}] _update_overview() - found {num_intervals} intervals in overview")
            
            # Store overview_df for mapping rectangle indices to intervals
            self._overview_df = overview_df.copy()
            
            # Use vispy renderer if enabled
            if self.use_vispy and VispyVideoEpochRenderer is not None:
                # Get reference datetime from plot_item's parent widget if available
                reference_datetime = None
                try:
                    # Try to get reference_datetime from timeline widget
                    parent_widget = self.plot_item.parentItem()
                    if parent_widget is not None:
                        # Traverse up to find timeline widget
                        while parent_widget is not None:
                            if hasattr(parent_widget, 'reference_datetime'):
                                reference_datetime = parent_widget.reference_datetime
                                break
                            parent_widget = parent_widget.parentItem()
                except Exception:
                    pass
                
                # Create or update vispy renderer
                if self.vispy_renderer is None:
                    # Get reference datetime from timeline widget if available
                    # Try to get from plot_item's parent hierarchy
                    timeline_widget = None
                    try:
                        # Try to find timeline widget by traversing parent chain
                        current = self.plot_item
                        while current is not None:
                            if hasattr(current, 'reference_datetime'):
                                reference_datetime = current.reference_datetime
                                timeline_widget = current
                                break
                            # Try to get parent
                            if hasattr(current, 'parentItem'):
                                current = current.parentItem()
                            elif hasattr(current, 'parent'):
                                current = current.parent()
                            else:
                                break
                    except Exception as e:
                        logger.debug(f"TrackRenderer[{self.track_id}] Could not find reference_datetime: {e}")
                    
                    # Get parent widget for embedding (vispy canvas needs Qt widget parent)
                    parent_widget = None
                    try:
                        # Try to get the actual Qt widget from plot_item
                        viewbox = self.plot_item.getViewBox()
                        if viewbox is not None:
                            # Get the GraphicsView widget
                            if hasattr(viewbox, 'parent'):
                                parent_widget = viewbox.parent()
                            # Try alternative: get widget from plot_item
                            if parent_widget is None and hasattr(self.plot_item, 'parent'):
                                parent_widget = self.plot_item.parent()
                    except Exception as e:
                        logger.debug(f"TrackRenderer[{self.track_id}] Could not get parent widget: {e}")
                    
                    self.vispy_renderer = VispyVideoEpochRenderer(
                        parent_widget=parent_widget,
                        reference_datetime=reference_datetime,
                        max_epochs=10000
                    )
                    logger.info(f"TrackRenderer[{self.track_id}] Created vispy renderer")
                    
                    # Embed the vispy canvas widget into the plot_item's viewbox
                    # Note: vispy and pyqtgraph use different rendering backends (OpenGL vs QPainter)
                    # so we need to overlay or replace the plot_item content with the vispy canvas
                    try:
                        vispy_canvas_widget = self.vispy_renderer.get_canvas_widget()
                        if vispy_canvas_widget is not None:
                            # Get the GraphicsView widget that contains the plot_item
                            viewbox = self.plot_item.getViewBox()
                            graphics_view = None
                            if viewbox is not None:
                                # Try to get the GraphicsView widget
                                if hasattr(viewbox, 'parent'):
                                    parent = viewbox.parent()
                                    # GraphicsView is typically the parent of ViewBox
                                    if parent is not None:
                                        graphics_view = parent
                            
                            # If we found a GraphicsView, try to overlay the vispy canvas
                            if graphics_view is not None:
                                try:
                                    # Set the vispy canvas as a child of the graphics view
                                    vispy_canvas_widget.setParent(graphics_view)
                                    # Make it fill the entire graphics view area
                                    # Convert QRectF to QRect for setGeometry
                                    from qtpy import QtCore
                                    rect = graphics_view.rect()
                                    if isinstance(rect, QtCore.QRectF):
                                        # Convert QRectF to QRect
                                        vispy_canvas_widget.setGeometry(
                                            int(rect.x()), int(rect.y()), 
                                            int(rect.width()), int(rect.height())
                                        )
                                    else:
                                        vispy_canvas_widget.setGeometry(rect)
                                    vispy_canvas_widget.raise_()  # Bring to front
                                    vispy_canvas_widget.show()
                                    logger.info(f"TrackRenderer[{self.track_id}] Embedded vispy canvas widget into graphics view")
                                except Exception as embed_error:
                                    logger.warning(f"TrackRenderer[{self.track_id}] Could not embed vispy canvas: {embed_error}")
                                    # Fallback: just show the canvas
                                    vispy_canvas_widget.show()
                            else:
                                # Fallback: just show the canvas (might appear as separate window)
                                vispy_canvas_widget.show()
                                logger.warning(f"TrackRenderer[{self.track_id}] Could not find graphics view, showing vispy canvas as standalone")
                    except Exception as e:
                        logger.warning(f"TrackRenderer[{self.track_id}] Could not embed vispy canvas widget: {e}", exc_info=True)
                
                # Update vispy renderer with intervals
                self.vispy_renderer.update_epochs(overview_df)
                logger.debug(f"TrackRenderer[{self.track_id}] Updated vispy renderer with {num_intervals} intervals")
                return
            
            # Build IntervalRectsItem from overview data (pyqtgraph fallback)
            # The datasource should provide visualization columns, but if not, we need to add them
            if 'series_vertical_offset' not in overview_df.columns:
                # Default vertical positioning
                overview_df = overview_df.copy()
                overview_df['series_vertical_offset'] = 0.0
                overview_df['series_height'] = 1.0
                logger.debug(f"TrackRenderer[{self.track_id}] _update_overview() - added default visualization columns")
            
            # Create format_label_fn for video tracks to display filename
            format_label_fn = None
            if VideoTrackDatasource is not None and isinstance(self.datasource, VideoTrackDatasource):
                def video_label_formatter(rect_index: int, rect_data_tuple) -> str:
                    """Format label for video track intervals - extracts filename from label field."""
                    if isinstance(rect_data_tuple, IntervalRectsItemData):
                        return rect_data_tuple.label if rect_data_tuple.label else ''
                    return ''
                format_label_fn = video_label_formatter
            
            # Create detail render callback if detail renderer is available
            detail_render_callback = None
            if self.detail_renderer is not None:
                def detail_render_callback_fn(rect_index: int, rect_data: IntervalRectsItemData):
                    """Callback to render detailed view for a specific interval rectangle.
                    
                    Args:
                        rect_index: Index of the rectangle in IntervalRectsItem.data
                        rect_data: IntervalRectsItemData for the rectangle
                    """
                    logger.info(f"TrackRenderer[{self.track_id}] detail_render_callback called for rect_index={rect_index}")
                    
                    # Get the corresponding interval from overview_df
                    if self._overview_df is None or rect_index >= len(self._overview_df):
                        logger.warning(f"TrackRenderer[{self.track_id}] Invalid rect_index={rect_index} for overview_df length={len(self._overview_df) if self._overview_df is not None else 0}")
                        return
                    
                    # Get interval as Series
                    interval_series = self._overview_df.iloc[rect_index]
                    
                    # Convert to single-row DataFrame for _render_detail
                    interval_df = self._overview_df.iloc[[rect_index]]
                    
                    # Get cache key
                    cache_key = self.datasource.get_detail_cache_key(interval_series)
                    logger.debug(f"TrackRenderer[{self.track_id}] detail_render_callback - cache_key='{cache_key}'")
                    
                    # Add to visible_intervals to prevent it from being cleared
                    self.visible_intervals.add(cache_key)
                    
                    # Check if detail data is already cached
                    cached_data = self.async_fetcher.get_cached_data(cache_key)
                    if cached_data is not None:
                        # Render immediately with cached data
                        logger.debug(f"TrackRenderer[{self.track_id}] detail_render_callback - using cached data for cache_key='{cache_key}'")
                        self._render_detail(interval_df, cache_key, cached_data)
                        self.detail_loaded.emit(self.track_id, interval_df, cached_data)
                    else:
                        # Fetch asynchronously
                        logger.debug(f"TrackRenderer[{self.track_id}] detail_render_callback - fetching detail data asynchronously for cache_key='{cache_key}'")
                        self.async_fetcher.fetch_detail_async(self.track_id, interval_series, self.datasource)
                        # Note: _on_detail_data_ready will be called when data is ready
                
                detail_render_callback = detail_render_callback_fn
            
            # Build the interval rects item
            self.overview_rects_item = Render2DEventRectanglesHelper.build_IntervalRectsItem_from_interval_datasource(
                self.datasource, format_label_fn=format_label_fn, detail_render_callback=detail_render_callback
            )
            
            # Remove old overview if exists
            if self.overview_rects_item is not None and self.overview_rects_item in self.plot_item.listDataItems():
                self.plot_item.removeItem(self.overview_rects_item)
                logger.debug(f"TrackRenderer[{self.track_id}] _update_overview() - removed old overview item")
            
            # Add new overview
            if self.overview_rects_item is not None:
                self.plot_item.addItem(self.overview_rects_item)
                logger.debug(f"TrackRenderer[{self.track_id}] _update_overview() - added new overview item")
            else:
                logger.warning(f"TrackRenderer[{self.track_id}] _update_overview() - overview_rects_item is None after build")
        except Exception as e:
            logger.error(f"TrackRenderer[{self.track_id}] _update_overview() - error: {e}", exc_info=True)
            raise
    

    def update_viewport(self, viewport_start: float, viewport_end: float):
        """Update viewport and trigger detail fetches for visible intervals.
        
        Args:
            viewport_start: Start time of viewport
            viewport_end: End time of viewport

        TODO 2025-01-07 -- This is where I think I should remove the details if the detail view widget is too dense/too small.

        """
        # Defer the actual processing to avoid blocking the UI thread
        # This allows other tracks to continue processing even if this one is slow
        def process_viewport_update():
            logger.debug(f"TrackRenderer[{self.track_id}] update_viewport(start={_format_time_value_for_log(viewport_start)}, end={_format_time_value_for_log(viewport_end)})")
            
            # Optimize for video tracks: skip detail fetching entirely
            is_video_track = VideoTrackDatasource is not None and isinstance(self.datasource, VideoTrackDatasource)
            
            # For video tracks, update vispy renderer viewport if using vispy
            if is_video_track:
                if self.use_vispy and self.vispy_renderer is not None:
                    # Update vispy renderer viewport
                    self.vispy_renderer.set_viewport(viewport_start, viewport_end)
                    logger.debug(f"TrackRenderer[{self.track_id}] update_viewport() - updated vispy renderer viewport")
                # Just update visible_intervals to empty set to prevent any detail fetching
                # Video tracks only show overview rectangles, no detail overlays
                self.visible_intervals.clear()
                logger.debug(f"TrackRenderer[{self.track_id}] update_viewport() - video track, skipping detail processing")
                return
            
            # Get intervals in viewport (only for non-video tracks)
            intervals_df = self.datasource.get_updated_data_window(viewport_start, viewport_end) # TODO 2025-01-07 - Not all datasources use dataframes
            num_intervals = len(intervals_df)
            logger.debug(f"TrackRenderer[{self.track_id}] update_viewport() - found {num_intervals} intervals in viewport")
            
            # Determine which intervals are now visible
            new_visible_keys = set()
            cache_hits = 0
            cache_misses = 0
            already_visible = 0
            
            # For non-video tracks, do full detail fetching logic
            for idx, interval_series in intervals_df.iterrows():
                # Convert Series to single-row DataFrame for DetailRenderer methods
                interval_df = intervals_df.iloc[[idx]]
                cache_key = self.datasource.get_detail_cache_key(interval_series)
                new_visible_keys.add(cache_key)
                
                # If not already visible and not already loaded, fetch detail
                if cache_key not in self.visible_intervals:
                    # Check cache first for non-video tracks
                    cached_data = self.async_fetcher.get_cached_data(cache_key)
                    if cached_data is not None:
                        cache_hits += 1
                        logger.debug(f"TrackRenderer[{self.track_id}] Interval cache_key='{cache_key}' ({_format_interval_for_log(interval_series)}) - cache HIT, rendering immediately")
                        self._render_detail(interval_df, cache_key, cached_data)
                    else:
                        cache_misses += 1
                        logger.debug(f"TrackRenderer[{self.track_id}] Interval cache_key='{cache_key}' ({_format_interval_for_log(interval_series)}) - cache MISS, requesting async fetch")
                        self.async_fetcher.fetch_detail_async(self.track_id, interval_series, self.datasource) ## I believe after this asynchronously completes, `self._on_detail_data_ready` is called.
                else:
                    already_visible += 1
            ## END for idx, interval_series in intervals_df.iterrows()...
            logger.debug(f"TrackRenderer[{self.track_id}] update_viewport() - intervals: {already_visible} already visible, {cache_hits} cache hits, {cache_misses} cache misses")
            
            # Cancel fetches for intervals that left viewport
            intervals_that_left = self.visible_intervals - new_visible_keys
            if intervals_that_left:
                interval_keys_list = list(intervals_that_left)
                logger.debug(f"TrackRenderer[{self.track_id}] update_viewport() - {len(intervals_that_left)} intervals leaving viewport: {interval_keys_list}")
                self.async_fetcher.cancel_pending_fetches(self.track_id, interval_keys_list)
                
                # Clear detail graphics for intervals that left
                for cache_key in intervals_that_left:
                    self._clear_detail(cache_key) ## this is this being called for all intervals?
            
            # Update visible intervals set
            self.visible_intervals = new_visible_keys
            logger.debug(f"TrackRenderer[{self.track_id}] update_viewport() - visible_intervals count: {len(self.visible_intervals)}")
        
        # Schedule the actual processing to run asynchronously
        # Use QTimer.singleShot(0) to defer to next event loop iteration
        QtCore.QTimer.singleShot(0, process_viewport_update)
    

    def _on_detail_data_ready(self, track_id: str, cache_key: str, interval: pd.DataFrame, detail_data: Any, error: Optional[Exception]):
        """Handle when detail data is ready (called from async fetcher signal).
        
        Args:
            track_id: Track identifier
            cache_key: Cache key for the interval
            interval: The interval DataFrame (single row)
            detail_data: The fetched detail data
            error: Error if fetch failed, None otherwise
        """
        logger.debug(f"TrackRenderer[{self.track_id}] _on_detail_data_ready(track_id={track_id}, cache_key='{cache_key}')")
        # g.graphics.track_renderer - DEBUG - TrackRenderer[EEG_Epoc X] Rendered detail for cache_key='EEG_Epoc X_0.000_0.000' - created 14 graphics objects
        # 2026-02-03 11:27:20 - pypho_timeline.rendering.graphics.track_renderer - DEBUG - TrackRenderer[MOTION_Epoc X Motion] _on_detail_data_ready(track_id='EEG_Epoc X', cache_key='EEG_Epoc X_0.000_0.000')
        # 2026-02-03 11:27:20 - pypho_timeline.rendering.graphics.track_renderer - DEBUG - TrackRenderer[MOTION_Epoc X Motion] _on_detail_data_ready() - data for wrong track (expected 'MOTION_Epoc X Motion', got 'EEG_Epoc X'), ignoring

        if track_id != self.track_id:
            logger.debug(f"TrackRenderer[{self.track_id}] _on_detail_data_ready() - data for wrong track (expected '{self.track_id},' got '{track_id}'), ignoring")
            return  # Not for this track
        
        if error is not None:
            logger.error(f"TrackRenderer[{self.track_id}] Error fetching detail data for interval cache_key='{cache_key}': {error}", exc_info=error)
            return
        
        # Only render if still in viewport
        if cache_key in self.visible_intervals:
            logger.debug(f"TrackRenderer[{self.track_id}] Detail data ready for cache_key='{cache_key}' - interval still visible, rendering")
            self._render_detail(interval, cache_key, detail_data)
            self.detail_loaded.emit(self.track_id, interval, detail_data)
        else:
            logger.warning(f"TrackRenderer[{self.track_id}] Detail data arrived for cache_key='{cache_key}' but interval no longer visible (not in visible_intervals), skipping render")
    

    def _render_detail(self, interval: pd.DataFrame, cache_key: str, detail_data: Any):
        """Render detailed view for an interval.
        
        Args:
            interval: The interval DataFrame (single row)
            cache_key: Cache key for this interval
            detail_data: The detail data to render
        """
        if len(interval) > 0:
            t_start = interval.iloc[0].get('t_start', None)
            t_duration = interval.iloc[0].get('t_duration', None)

            ## datetime converted versions for filtering `detailed_df`
            t_start_dt = interval.iloc[0].get('t_start_dt', None)
            t_end_dt = interval.iloc[0].get('t_end_dt', None)

            if ((t_start_dt is not None) and (t_end_dt is not None) and isinstance(detail_data, pd.DataFrame)):
                ## filter detail_data down to the current interval range... I hope this is right at least, I think it could be so long as `interval` is the data interval to render and not the viewport or somethings
                logger.debug(f"TrackRenderer[{self.track_id}] _render_detail - filtering df down to correct interval range: (t_start_dt='{t_start_dt}', t_end_dt={t_end_dt}, t_start={t_start})")
                detail_data = detail_data[np.logical_and((detail_data['t'] >= t_start_dt), (detail_data['t'] <= t_end_dt))] 
                
                
            t_start_str = f"{t_start:.3f}" if t_start is not None else "?"
            t_duration_str = f"{t_duration:.3f}" if t_duration is not None else "?"
        else:
            t_start_str = "?"
            t_duration_str = "?"
        logger.debug(f"TrackRenderer[{self.track_id}] _render_detail(cache_key='{cache_key}', t_start={t_start_str}, t_duration={t_duration_str}) - starting")
        
        # Clear any existing detail for this interval
        if cache_key in self.detail_graphics:
            logger.debug(f"TrackRenderer[{self.track_id}] _render_detail() - clearing existing detail for cache_key='{cache_key}'")
            self._clear_detail(cache_key)
        
        try:
            # Render using detail renderer
            detail_renderer_type = type(self.detail_renderer).__name__ if self.detail_renderer is not None else "None"
            logger.debug(f"TrackRenderer[{self.track_id}] _render_detail() - using detail_renderer type={detail_renderer_type}")
            
            # Set channel visibility on renderer if it supports it
            # Always set it if detail renderer has channel_names (it should support visibility)
            if hasattr(self.detail_renderer, 'channel_names') and self.detail_renderer.channel_names is not None:
                self.detail_renderer.channel_visibility = self.channel_visibility.copy()
                logger.debug(f"TrackRenderer[{self.track_id}] _render_detail() - set channel_visibility on detail_renderer: {self.channel_visibility}")
            
            # Where the main rendering occurs ____________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________ #
            graphics_objects = self.detail_renderer.render_detail(
                self.plot_item, interval, detail_data
            )
            
            num_graphics = len(graphics_objects) if graphics_objects is not None else 0
            logger.debug(f"TrackRenderer[{self.track_id}] _render_detail() - Rendered detail for cache_key='{cache_key}' - created {num_graphics} graphics objects")
            
            # Store graphics objects for cleanup
            self.detail_graphics[cache_key] = graphics_objects
        except Exception as e:
            logger.error(f"TrackRenderer[{self.track_id}] _render_detail() - error rendering detail for cache_key='{cache_key}': {e}", exc_info=True)
            raise
    

    def _clear_detail(self, cache_key: str):
        """Clear detailed view for an interval.
        
        Args:
            cache_key: Cache key for the interval to clear
        """
        logger.debug(f"TrackRenderer[{self.track_id}] _clear_detail(cache_key='{cache_key}') - starting")
        
        if cache_key in self.detail_graphics:
            graphics_objects = self.detail_graphics[cache_key]
            num_graphics = len(graphics_objects) if graphics_objects is not None else 0
            logger.debug(f"TrackRenderer[{self.track_id}] _clear_detail() - clearing {num_graphics} graphics objects for cache_key='{cache_key}'")
            self.detail_renderer.clear_detail(self.plot_item, graphics_objects)
            del self.detail_graphics[cache_key]
        else:
            logger.debug(f"TrackRenderer[{self.track_id}] _clear_detail() - cache_key='{cache_key}' not found in detail_graphics, nothing to clear")
    

    def clear_all_details(self):
        """Clear all detail graphics."""
        num_intervals = len(self.detail_graphics)
        logger.info(f"TrackRenderer[{self.track_id}] clear_all_details() - clearing {num_intervals} intervals")
        
        for cache_key in list(self.detail_graphics.keys()):
            self._clear_detail(cache_key)
        
        self.visible_intervals.clear() ## cleared the visible intervals too
        logger.debug(f"TrackRenderer[{self.track_id}] clear_all_details() - cleared visible_intervals set")
    

    def remove(self):
        """Remove this track renderer and clean up all graphics."""
        logger.info(f"TrackRenderer[{self.track_id}] remove() - starting track removal")
        
        # Clear all details
        self.clear_all_details()
        
        # Remove vispy renderer if used
        if self.vispy_renderer is not None:
            logger.debug(f"TrackRenderer[{self.track_id}] remove() - removing vispy renderer")
            self.vispy_renderer.remove()
            self.vispy_renderer = None
        
        # Remove overview
        if self.overview_rects_item is not None:
            logger.debug(f"TrackRenderer[{self.track_id}] remove() - removing overview item")
            self.plot_item.removeItem(self.overview_rects_item)
            self.overview_rects_item = None
        
        # Disconnect from async fetcher
        try:
            self.async_fetcher.detail_data_ready.disconnect(self._on_detail_data_ready)
            logger.debug(f"TrackRenderer[{self.track_id}] remove() - disconnected from async_fetcher signal")
        except (TypeError, RuntimeError) as e:
            logger.debug(f"TrackRenderer[{self.track_id}] remove() - signal already disconnected: {e}")
        
        logger.info(f"TrackRenderer[{self.track_id}] remove() - track removal complete")
    
    
    def get_overview_bounds(self) -> Optional[tuple]:
        """Get the bounds of the overview rectangles.
        
        Returns:
            Tuple of (x_min, x_max, y_min, y_max) or None if no overview
        """
        if self.use_vispy and self.vispy_renderer is not None:
            # Get bounds from vispy renderer
            if self.vispy_renderer.current_epochs_data:
                epochs_df = pd.DataFrame(self.vispy_renderer.current_epochs_data)
                if len(epochs_df) > 0:
                    # Check if t_start is datetime and convert to float if needed
                    x_min_val = epochs_df['t_start'].min()
                    if isinstance(x_min_val, (datetime, pd.Timestamp)):
                        x_min = x_min_val.timestamp() if hasattr(x_min_val, 'timestamp') else pd.Timestamp(x_min_val).timestamp()
                    else:
                        x_min = float(x_min_val)
                    
                    # Calculate x_max
                    if pd.api.types.is_datetime64_any_dtype(epochs_df['t_start']):
                        x_max_val = (epochs_df['t_start'] + pd.to_timedelta(epochs_df['t_duration'], unit='s')).max()
                        x_max = x_max_val.timestamp() if hasattr(x_max_val, 'timestamp') else pd.Timestamp(x_max_val).timestamp()
                    else:
                        x_max = float((epochs_df['t_start'] + epochs_df['t_duration']).max())
                    
                    y_min = float(epochs_df['series_vertical_offset'].min())
                    y_max = float((epochs_df['series_vertical_offset'] + epochs_df['series_height']).max())
                    return (x_min, x_max, y_min, y_max)
            return None
        
        if self.overview_rects_item is None:
            return None
        
        rect = self.overview_rects_item.boundingRect()
        return (rect.left(), rect.right(), rect.top(), rect.bottom())
    

    # Options Panel Implementation _______________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________ #
    def on_options_changed(self):
        """Update visibility state for a channel and re-render visible intervals.
        
        Args:
            channel_name: Name of the channel
            is_visible: True to show channel, False to hide
        """
        logger.info(f"TrackRenderer[{self.track_id}] on_options_changed()")


    def on_options_accepted(self):
        """Apply the current visibility state from the options panel and re-render visible intervals.
        
        This is called when the user presses OK in the options dialog. It reads the current
        visibility state from the options panel and applies it to all channels, then triggers
        a re-render of all visible intervals.
        """
        logger.info(f"TrackRenderer[{self.track_id}] on_options_accepted() - applying visibility changes from options panel")
        
        # Get current visibility state from options panel
        if self._options_panel is None:
            logger.warning(f"TrackRenderer[{self.track_id}] on_options_accepted() - no options panel available")
            return
        
        # Check if panel has get_visibility_state method (TrackChannelVisibilityOptionsPanel)
        if not hasattr(self._options_panel, 'get_visibility_state'):
            logger.debug(f"TrackRenderer[{self.track_id}] on_options_accepted() - options panel does not support visibility state")
            return
        
        new_visibility_state = self._options_panel.get_visibility_state()
        logger.info(f"TrackRenderer[{self.track_id}] on_options_accepted() - got visibility state from panel: {new_visibility_state}")
        
        # Check if any channels changed
        has_changes = False
        for channel_name, is_visible in new_visibility_state.items():
            if channel_name in self.channel_visibility:
                old_visible = self.channel_visibility[channel_name]
                if old_visible != is_visible:
                    has_changes = True
                    self.channel_visibility[channel_name] = is_visible
                    logger.info(f"TrackRenderer[{self.track_id}] Channel '{channel_name}' visibility changed from {old_visible} to {is_visible}")
        
        if not has_changes:
            logger.debug(f"TrackRenderer[{self.track_id}] on_options_accepted() - no visibility changes detected")
            return
        
        # Trigger re-render with updated visibility (using shared helper method)
        self._trigger_visibility_render()


    def on_options_rejected(self):
        """Update visibility state for a channel and re-render visible intervals.
        
        Args:
            channel_name: Name of the channel
            is_visible: True to show channel, False to hide
        """
        logger.info(f"TrackRenderer[{self.track_id}] on_options_rejected()")


    def _trigger_visibility_render(self):
        """Helper method to clear all visible detail graphics and trigger re-render after visibility changes."""
        # Clear all visible detail graphics
        logger.warning(f"TrackRenderer[{self.track_id}] _trigger_visibility_render()")
        visible_cache_keys = list(self.visible_intervals)
        logger.debug(f"TrackRenderer[{self.track_id}] Clearing {len(visible_cache_keys)} intervals for re-render after visibility change")
        
        for cache_key in visible_cache_keys:
            self._clear_detail(cache_key)
        
        # Clear visible_intervals so update_viewport() will treat all intervals as new and re-fetch/re-render them
        self.visible_intervals.clear() ## this seems uneeded and relies on update_viewport to rebuild them
        logger.debug(f"TrackRenderer[{self.track_id}] Cleared visible_intervals to force re-fetch on next update_viewport()")
        
        # Trigger viewport update to re-render with new visibility
        # This will re-fetch intervals and render with filtered channels
        if self.plot_item is not None:
            viewbox = self.plot_item.getViewBox()
            if viewbox is not None:
                x_range, y_range = viewbox.viewRange()
                if len(x_range) == 2:
                    self.update_viewport(x_range[0], x_range[1])



    def update_channel_visibility(self, channel_name: str, is_visible: bool):
        """Update visibility state for a channel and re-render visible intervals.
        
        Args:
            channel_name: Name of the channel
            is_visible: True to show channel, False to hide
        """
        logger.info(f"TrackRenderer[{self.track_id}] update_channel_visibility(channel_name: {channel_name}, is_visible: {is_visible})")

        if channel_name not in self.channel_visibility:
            logger.warning(f"TrackRenderer[{self.track_id}] update_channel_visibility() - channel '{channel_name}' not found in channel_visibility")
            return
        
        old_visible = self.channel_visibility[channel_name]
        if old_visible == is_visible:
            return  # No change
        
        self.channel_visibility[channel_name] = is_visible
        logger.info(f"TrackRenderer[{self.track_id}] Channel '{channel_name}' visibility changed to {is_visible}")
        
        # Update options panel if available
        if self._options_panel is not None:
            self._options_panel.set_visibility_state({channel_name: is_visible}, emit_signals=False)
        
        # Trigger re-render
        self._trigger_visibility_render()
    
    
    def set_options_panel(self, options_panel):
        """Set the options panel reference for bidirectional updates.
        
        Args:
            options_panel: TrackChannelVisibilityOptionsPanel instance
        """
        self._options_panel = options_panel


__all__ = ['TrackRenderer']

