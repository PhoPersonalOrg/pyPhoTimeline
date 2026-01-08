"""TrackRenderer - Manages overview rectangles and detail overlays for timeline tracks."""
from typing import Dict, List, Optional, Set, Any
import logging
import pandas as pd
from qtpy import QtCore
import pyphoplacecellanalysis.External.pyqtgraph as pg

from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, DetailRenderer
from pypho_timeline.rendering.graphics.interval_rects_item import IntervalRectsItem, IntervalRectsItemData
from pypho_timeline.rendering.async_detail_fetcher import AsyncDetailFetcher
from pypho_timeline.rendering.helpers.render_rectangles_helper import Render2DEventRectanglesHelper
from pypho_timeline.utils.logging_util import get_rendering_logger

# Import VideoTrackDatasource for type checking
try:
    from pypho_timeline.rendering.datasources.specific.video import VideoTrackDatasource
except ImportError:
    VideoTrackDatasource = None

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
        
        # Detail rendering state
        self.detail_renderer: DetailRenderer = datasource.get_detail_renderer()
        self.detail_graphics: Dict[str, List[pg.GraphicsObject]] = {}  # cache_key -> graphics objects
        self.visible_intervals: Set[str] = set()  # Set of cache keys currently in viewport
        
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
            
            # Build IntervalRectsItem from overview data
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
            
            # Build the interval rects item
            self.overview_rects_item = Render2DEventRectanglesHelper.build_IntervalRectsItem_from_interval_datasource(
                self.datasource, format_label_fn=format_label_fn
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
        logger.debug(f"TrackRenderer[{self.track_id}] update_viewport(start={viewport_start:.3f}, end={viewport_end:.3f})")
        
        # Get intervals in viewport
        intervals_df = self.datasource.get_updated_data_window(viewport_start, viewport_end) # TODO 2025-01-07 - Not all datasources use dataframes
        num_intervals = len(intervals_df)
        logger.debug(f"TrackRenderer[{self.track_id}] update_viewport() - found {num_intervals} intervals in viewport")
        
        # Determine which intervals are now visible
        new_visible_keys = set()
        cache_hits = 0
        cache_misses = 0
        already_visible = 0
        
        for idx, interval_series in intervals_df.iterrows():
            # Convert Series to single-row DataFrame for DetailRenderer methods
            interval_df = intervals_df.iloc[[idx]]
            cache_key = self.datasource.get_detail_cache_key(interval_series)
            new_visible_keys.add(cache_key)
            
            # If not already visible and not already loaded, fetch detail
            if cache_key not in self.visible_intervals:
                # Check cache first
                cached_data = self.async_fetcher.get_cached_data(cache_key)
                if cached_data is not None:
                    # Use cached data immediately
                    cache_hits += 1
                    t_start = interval_series.get('t_start', None)
                    t_duration = interval_series.get('t_duration', None)
                    t_start_str = f"{t_start:.3f}" if t_start is not None else "?"
                    t_duration_str = f"{t_duration:.3f}" if t_duration is not None else "?"
                    logger.debug(f"TrackRenderer[{self.track_id}] Interval cache_key='{cache_key}' (t_start={t_start_str}, t_duration={t_duration_str}) - cache HIT, rendering immediately")
                    self._render_detail(interval_df, cache_key, cached_data)
                else:
                    # Skip detail fetching for video tracks for now
                    if VideoTrackDatasource is not None and isinstance(self.datasource, VideoTrackDatasource):
                        logger.debug(f"TrackRenderer[{self.track_id}] Interval cache_key='{cache_key}' - skipping detail fetch for video track")
                        cache_misses += 1
                    else:
                        # Fetch asynchronously (still pass Series for datasource compatibility)
                        cache_misses += 1
                        t_start = interval_series.get('t_start', None)
                        t_duration = interval_series.get('t_duration', None)
                        t_start_str = f"{t_start:.3f}" if t_start is not None else "?"
                        t_duration_str = f"{t_duration:.3f}" if t_duration is not None else "?"
                        logger.debug(f"TrackRenderer[{self.track_id}] Interval cache_key='{cache_key}' (t_start={t_start_str}, t_duration={t_duration_str}) - cache MISS, requesting async fetch")
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
    

    def _on_detail_data_ready(self, track_id: str, cache_key: str, interval: pd.DataFrame, 
                             detail_data: Any, error: Optional[Exception]):
        """Handle when detail data is ready (called from async fetcher signal).
        
        Args:
            track_id: Track identifier
            cache_key: Cache key for the interval
            interval: The interval DataFrame (single row)
            detail_data: The fetched detail data
            error: Error if fetch failed, None otherwise
        """
        logger.debug(f"TrackRenderer[{self.track_id}] _on_detail_data_ready(track_id={track_id}, cache_key='{cache_key}')")
        
        if track_id != self.track_id:
            logger.debug(f"TrackRenderer[{self.track_id}] _on_detail_data_ready() - data for wrong track (expected {self.track_id}, got {track_id}), ignoring")
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
            
            graphics_objects = self.detail_renderer.render_detail(
                self.plot_item, interval, detail_data
            )
            
            num_graphics = len(graphics_objects) if graphics_objects is not None else 0
            logger.debug(f"TrackRenderer[{self.track_id}] Rendered detail for cache_key='{cache_key}' - created {num_graphics} graphics objects")
            
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
        
        self.visible_intervals.clear()
        logger.debug(f"TrackRenderer[{self.track_id}] clear_all_details() - cleared visible_intervals set")
    

    def remove(self):
        """Remove this track renderer and clean up all graphics."""
        logger.info(f"TrackRenderer[{self.track_id}] remove() - starting track removal")
        
        # Clear all details
        self.clear_all_details()
        
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
        self.visible_intervals.clear()
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

