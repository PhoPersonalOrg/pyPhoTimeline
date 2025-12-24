"""TrackRenderer - Manages overview rectangles and detail overlays for timeline tracks."""
from typing import Dict, List, Optional, Set, Any
import pandas as pd
from qtpy import QtCore
import pyphoplacecellanalysis.External.pyqtgraph as pg

from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource, DetailRenderer
from pypho_timeline.rendering.graphics.interval_rects_item import IntervalRectsItem
from pypho_timeline.rendering.async_detail_fetcher import AsyncDetailFetcher
from pypho_timeline.rendering.helpers.render_rectangles_helper import Render2DEventRectanglesHelper


class TrackRenderer(QtCore.QObject):
    """Manages rendering of a single track with overview intervals and detail overlays.
    
    This class handles:
    - Rendering overview intervals as rectangles
    - Monitoring viewport changes to detect intervals entering/exiting
    - Triggering async fetches for detailed data
    - Overlaying detailed views on top of overview rectangles
    """
    
    # Signal emitted when detail data is loaded for an interval
    detail_loaded = QtCore.Signal(str, pd.Series, object)  # track_id, interval, detail_data
    
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
        
        # Connect to async fetcher
        self.async_fetcher.detail_data_ready.connect(self._on_detail_data_ready)
        
        # Initialize overview rendering
        self._update_overview()
    
    def _update_overview(self):
        """Update the overview interval rectangles."""
        # Get overview intervals
        overview_df = self.datasource.get_overview_intervals()
        
        # Build IntervalRectsItem from overview data
        # The datasource should provide visualization columns, but if not, we need to add them
        if 'series_vertical_offset' not in overview_df.columns:
            # Default vertical positioning
            overview_df = overview_df.copy()
            overview_df['series_vertical_offset'] = 0.0
            overview_df['series_height'] = 1.0
        
        # Build the interval rects item
        self.overview_rects_item = Render2DEventRectanglesHelper.build_IntervalRectsItem_from_interval_datasource(
            self.datasource
        )
        
        # Remove old overview if exists
        if self.overview_rects_item is not None and self.overview_rects_item in self.plot_item.listDataItems():
            self.plot_item.removeItem(self.overview_rects_item)
        
        # Add new overview
        if self.overview_rects_item is not None:
            self.plot_item.addItem(self.overview_rects_item)
    
    def update_viewport(self, viewport_start: float, viewport_end: float):
        """Update viewport and trigger detail fetches for visible intervals.
        
        Args:
            viewport_start: Start time of viewport
            viewport_end: End time of viewport
        """
        # Get intervals in viewport
        intervals_df = self.datasource.get_updated_data_window(viewport_start, viewport_end)
        
        # Determine which intervals are now visible
        new_visible_keys = set()
        for _, interval in intervals_df.iterrows():
            cache_key = self.datasource.get_detail_cache_key(interval)
            new_visible_keys.add(cache_key)
            
            # If not already visible and not already loaded, fetch detail
            if cache_key not in self.visible_intervals:
                # Check cache first
                cached_data = self.async_fetcher.get_cached_data(cache_key)
                if cached_data is not None:
                    # Use cached data immediately
                    self._render_detail(interval, cache_key, cached_data)
                else:
                    # Fetch asynchronously
                    self.async_fetcher.fetch_detail_async(
                        self.track_id, interval, self.datasource
                    )
        
        # Cancel fetches for intervals that left viewport
        intervals_that_left = self.visible_intervals - new_visible_keys
        if intervals_that_left:
            interval_keys_list = list(intervals_that_left)
            self.async_fetcher.cancel_pending_fetches(self.track_id, interval_keys_list)
            
            # Clear detail graphics for intervals that left
            for cache_key in intervals_that_left:
                self._clear_detail(cache_key)
        
        # Update visible intervals set
        self.visible_intervals = new_visible_keys
    
    def _on_detail_data_ready(self, track_id: str, cache_key: str, interval: pd.Series, 
                             detail_data: Any, error: Optional[Exception]):
        """Handle when detail data is ready (called from async fetcher signal).
        
        Args:
            track_id: Track identifier
            cache_key: Cache key for the interval
            interval: The interval Series
            detail_data: The fetched detail data
            error: Error if fetch failed, None otherwise
        """
        if track_id != self.track_id:
            return  # Not for this track
        
        if error is not None:
            print(f"Error fetching detail data for interval {cache_key}: {error}")
            return
        
        # Only render if still in viewport
        if cache_key in self.visible_intervals:
            self._render_detail(interval, cache_key, detail_data)
            self.detail_loaded.emit(self.track_id, interval, detail_data)
    
    def _render_detail(self, interval: pd.Series, cache_key: str, detail_data: Any):
        """Render detailed view for an interval.
        
        Args:
            interval: The interval Series
            cache_key: Cache key for this interval
            detail_data: The detail data to render
        """
        # Clear any existing detail for this interval
        if cache_key in self.detail_graphics:
            self._clear_detail(cache_key)
        
        # Render using detail renderer
        graphics_objects = self.detail_renderer.render_detail(
            self.plot_item, interval, detail_data
        )
        
        # Store graphics objects for cleanup
        self.detail_graphics[cache_key] = graphics_objects
    
    def _clear_detail(self, cache_key: str):
        """Clear detailed view for an interval.
        
        Args:
            cache_key: Cache key for the interval to clear
        """
        if cache_key in self.detail_graphics:
            graphics_objects = self.detail_graphics[cache_key]
            self.detail_renderer.clear_detail(self.plot_item, graphics_objects)
            del self.detail_graphics[cache_key]
    
    def clear_all_details(self):
        """Clear all detail graphics."""
        for cache_key in list(self.detail_graphics.keys()):
            self._clear_detail(cache_key)
        self.visible_intervals.clear()
    
    def remove(self):
        """Remove this track renderer and clean up all graphics."""
        # Clear all details
        self.clear_all_details()
        
        # Remove overview
        if self.overview_rects_item is not None:
            self.plot_item.removeItem(self.overview_rects_item)
            self.overview_rects_item = None
        
        # Disconnect from async fetcher
        try:
            self.async_fetcher.detail_data_ready.disconnect(self._on_detail_data_ready)
        except (TypeError, RuntimeError):
            pass  # Already disconnected
    
    def get_overview_bounds(self) -> Optional[tuple]:
        """Get the bounds of the overview rectangles.
        
        Returns:
            Tuple of (x_min, x_max, y_min, y_max) or None if no overview
        """
        if self.overview_rects_item is None:
            return None
        
        rect = self.overview_rects_item.boundingRect()
        return (rect.left(), rect.right(), rect.top(), rect.bottom())


__all__ = ['TrackRenderer']

