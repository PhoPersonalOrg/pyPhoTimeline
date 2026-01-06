"""AsyncDetailFetcher - Asynchronous data fetching for timeline track details.

This module provides async data fetching using Qt QThreadPool for fetching detailed
data when intervals scroll into the viewport.
"""
from typing import Dict, List, Optional, Callable, Any
from collections import OrderedDict
from threading import Lock
import logging
import pandas as pd
from qtpy import QtCore, QtWidgets

from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource
from pypho_timeline.utils.logging_util import get_rendering_logger

logger = get_rendering_logger(__name__)


class DetailFetchWorker(QtCore.QRunnable):
    """Worker runnable for fetching detailed data in a background thread."""
    
    def __init__(self, track_id: str, interval: pd.Series, datasource: TrackDatasource, 
                 cache_key: str, callback: Callable):
        super().__init__()
        self.track_id = track_id
        self.interval = interval
        self.datasource = datasource
        self.cache_key = cache_key
        self.callback = callback
        self._cancelled = False
        self._lock = Lock()
        
        t_start = interval.get('t_start', None)
        t_duration = interval.get('t_duration', None)
        t_start_str = f"{t_start:.3f}" if t_start is not None else "?"
        t_duration_str = f"{t_duration:.3f}" if t_duration is not None else "?"
        logger.debug(f"DetailFetchWorker[{track_id}] __init__ - created for cache_key='{cache_key}' (t_start={t_start_str}, t_duration={t_duration_str})")
    
    def cancel(self):
        """Mark this worker as cancelled."""
        with self._lock:
            if not self._cancelled:
                logger.debug(f"DetailFetchWorker[{self.track_id}] cancel() - cancelling worker for cache_key='{self.cache_key}'")
            self._cancelled = True
    
    def is_cancelled(self) -> bool:
        """Check if this worker has been cancelled."""
        with self._lock:
            cancelled = self._cancelled
        if cancelled:
            logger.debug(f"DetailFetchWorker[{self.track_id}] is_cancelled() - worker for cache_key='{self.cache_key}' is cancelled")
        return cancelled
    
    def run(self):
        """Execute the data fetch in the worker thread."""
        logger.debug(f"DetailFetchWorker[{self.track_id}] run() - starting for cache_key='{self.cache_key}'")
        
        if self.is_cancelled():
            logger.debug(f"DetailFetchWorker[{self.track_id}] run() - cancelled before start, aborting")
            return
        
        try:
            datasource_type = type(self.datasource).__name__
            logger.debug(f"DetailFetchWorker[{self.track_id}] run() - calling fetch_detailed_data() for cache_key='{self.cache_key}', datasource={datasource_type}")
            
            detail_data = self.datasource.fetch_detailed_data(self.interval)
            
            # Log data type and size
            if detail_data is None:
                data_info = "None"
            elif hasattr(detail_data, '__len__'):
                data_info = f"type={type(detail_data).__name__}, size={len(detail_data)}"
            else:
                data_info = f"type={type(detail_data).__name__}"
            logger.debug(f"DetailFetchWorker[{self.track_id}] run() - fetch_detailed_data() returned: {data_info}")
            
            if not self.is_cancelled():
                # Convert Series to DataFrame for DetailRenderer compatibility
                interval_df = self.interval.to_frame().T
                logger.debug(f"DetailFetchWorker[{self.track_id}] run() - scheduling callback for cache_key='{self.cache_key}'")
                # Use QTimer.singleShot to ensure callback runs on main thread
                QtCore.QTimer.singleShot(0, lambda: self.callback(
                    self.track_id, self.cache_key, interval_df, detail_data, None
                ))
                logger.debug(f"DetailFetchWorker[{self.track_id}] run() - callback scheduled for cache_key='{self.cache_key}'")
            else:
                logger.debug(f"DetailFetchWorker[{self.track_id}] run() - cancelled after fetch, not scheduling callback")
        except Exception as e:
            logger.error(f"DetailFetchWorker[{self.track_id}] run() - error fetching data for cache_key='{self.cache_key}': {e}", exc_info=True)
            if not self.is_cancelled():
                # Convert Series to DataFrame for DetailRenderer compatibility
                interval_df = self.interval.to_frame().T
                logger.debug(f"DetailFetchWorker[{self.track_id}] run() - scheduling error callback for cache_key='{self.cache_key}'")
                QtCore.QTimer.singleShot(0, lambda: self.callback(
                    self.track_id, self.cache_key, interval_df, None, e
                ))
            else:
                logger.debug(f"DetailFetchWorker[{self.track_id}] run() - cancelled after error, not scheduling error callback")


class AsyncDetailFetcher(QtCore.QObject):
    """Manages asynchronous fetching of detailed data for timeline tracks.
    
    Uses Qt QThreadPool to fetch detailed data in background threads, with caching
    and cancellation support for intervals that leave the viewport.
    """
    
    # Signal emitted when detail data is ready
    detail_data_ready = QtCore.Signal(str, str, pd.DataFrame, object, object)  # track_id, cache_key, interval, data, error
    
    def __init__(self, max_cache_size: int = 100, parent=None):
        """Initialize the async detail fetcher.
        
        Args:
            max_cache_size: Maximum number of cached detail data items (LRU eviction)
            parent: Parent QObject
        """
        super().__init__(parent)
        self.max_cache_size = max_cache_size
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._pending_workers: Dict[str, Dict[str, DetailFetchWorker]] = {}  # track_id -> {cache_key -> worker}
        self._lock = Lock()
        self._thread_pool = QtCore.QThreadPool.globalInstance()
        max_threads = max(4, self._thread_pool.maxThreadCount())
        self._thread_pool.setMaxThreadCount(max_threads)
        
        logger.info(f"AsyncDetailFetcher __init__ - initialized with max_cache_size={max_cache_size}, max_threads={max_threads}")
    
    def fetch_detail_async(self, track_id: str, interval: pd.Series, 
                          datasource: TrackDatasource, callback: Optional[Callable] = None):
        """Queue an async fetch for detailed data.
        
        Args:
            track_id: Unique identifier for the track
            interval: Series with at least 't_start' and 't_duration' columns
            datasource: TrackDatasource to fetch from
            callback: Optional callback function(track_id, cache_key, interval, data, error)
                     If None, the detail_data_ready signal will be emitted instead
        """
        cache_key = datasource.get_detail_cache_key(interval)
        logger.debug(f"AsyncDetailFetcher.fetch_detail_async(track_id={track_id}, cache_key='{cache_key}')")
        
        # Check cache first
        with self._lock:
            if cache_key in self._cache:
                # Cache hit - return immediately
                data = self._cache[cache_key]
                # Move to end (LRU)
                self._cache.move_to_end(cache_key)
                logger.debug(f"AsyncDetailFetcher.fetch_detail_async() - cache HIT for cache_key='{cache_key}', returning immediately")
                # Convert Series to DataFrame for DetailRenderer compatibility
                interval_df = interval.to_frame().T
                if callback:
                    logger.debug(f"AsyncDetailFetcher.fetch_detail_async() - using callback for cache_key='{cache_key}'")
                    QtCore.QTimer.singleShot(0, lambda: callback(track_id, cache_key, interval_df, data, None))
                else:
                    logger.debug(f"AsyncDetailFetcher.fetch_detail_async() - emitting detail_data_ready signal for cache_key='{cache_key}'")
                    self.detail_data_ready.emit(track_id, cache_key, interval_df, data, None)
                return
            
            # Check if already pending
            if track_id in self._pending_workers:
                if cache_key in self._pending_workers[track_id]:
                    # Already fetching this interval
                    logger.debug(f"AsyncDetailFetcher.fetch_detail_async() - duplicate fetch request for cache_key='{cache_key}', already pending")
                    return
        
        logger.debug(f"AsyncDetailFetcher.fetch_detail_async() - cache MISS for cache_key='{cache_key}', creating worker")
        
        # Create worker
        # Note: callback will receive DataFrame (converted in worker.run())
        if callback:
            worker_callback = callback
            logger.debug(f"AsyncDetailFetcher.fetch_detail_async() - using provided callback for cache_key='{cache_key}'")
        else:
            def signal_emitter(tid, ck, iv, d, e):
                logger.debug(f"AsyncDetailFetcher - worker callback emitting detail_data_ready signal for track_id={tid}, cache_key='{ck}'")
                self.detail_data_ready.emit(tid, ck, iv, d, e)
            worker_callback = signal_emitter
            logger.debug(f"AsyncDetailFetcher.fetch_detail_async() - using signal emitter for cache_key='{cache_key}'")
        
        worker = DetailFetchWorker(track_id, interval, datasource, cache_key, worker_callback)
        
        # Track pending worker
        with self._lock:
            if track_id not in self._pending_workers:
                self._pending_workers[track_id] = {}
            self._pending_workers[track_id][cache_key] = worker
        
        # Start worker
        active_threads = self._thread_pool.activeThreadCount()
        logger.debug(f"AsyncDetailFetcher.fetch_detail_async() - starting worker for cache_key='{cache_key}', activeThreads={active_threads}")
        self._thread_pool.start(worker)
    
    def _on_detail_fetched(self, track_id: str, cache_key: str, interval: pd.DataFrame, 
                          detail_data: Any, error: Optional[Exception]):
        """Handle when detail data is fetched (called from worker callback)."""
        logger.debug(f"AsyncDetailFetcher._on_detail_fetched(track_id={track_id}, cache_key='{cache_key}', error={error is not None})")
        
        with self._lock:
            # Remove from pending
            if track_id in self._pending_workers:
                if cache_key in self._pending_workers[track_id]:
                    del self._pending_workers[track_id][cache_key]
                    logger.debug(f"AsyncDetailFetcher._on_detail_fetched() - removed from pending workers for cache_key='{cache_key}'")
                    if not self._pending_workers[track_id]:
                        del self._pending_workers[track_id]
            
            # Cache the data if successful
            if error is None and detail_data is not None:
                self._cache[cache_key] = detail_data
                self._cache.move_to_end(cache_key)
                logger.debug(f"AsyncDetailFetcher._on_detail_fetched() - cached data for cache_key='{cache_key}', cache_size={len(self._cache)}")
                
                # Evict if cache too large
                evicted_count = 0
                while len(self._cache) > self.max_cache_size:
                    self._cache.popitem(last=False)  # Remove oldest
                    evicted_count += 1
                if evicted_count > 0:
                    logger.debug(f"AsyncDetailFetcher._on_detail_fetched() - evicted {evicted_count} entries from cache")
    
    def cancel_pending_fetches(self, track_id: str, interval_keys: List[str]):
        """Cancel pending fetches for specific intervals.
        
        Args:
            track_id: Track identifier
            interval_keys: List of cache keys for intervals to cancel
        """
        logger.debug(f"AsyncDetailFetcher.cancel_pending_fetches(track_id={track_id}, num_keys={len(interval_keys)})")
        
        with self._lock:
            if track_id not in self._pending_workers:
                logger.debug(f"AsyncDetailFetcher.cancel_pending_fetches() - no pending workers for track_id={track_id}")
                return
            
            cancelled_count = 0
            for cache_key in interval_keys:
                if cache_key in self._pending_workers[track_id]:
                    worker = self._pending_workers[track_id][cache_key]
                    worker.cancel()
                    del self._pending_workers[track_id][cache_key]
                    cancelled_count += 1
                    logger.debug(f"AsyncDetailFetcher.cancel_pending_fetches() - cancelled worker for cache_key='{cache_key}'")
            
            if not self._pending_workers[track_id]:
                del self._pending_workers[track_id]
            
            logger.debug(f"AsyncDetailFetcher.cancel_pending_fetches() - cancelled {cancelled_count} workers for track_id={track_id}")
    
    def cancel_all_pending_fetches(self, track_id: Optional[str] = None):
        """Cancel all pending fetches for a track, or all tracks if track_id is None.
        
        Args:
            track_id: Track identifier, or None to cancel all tracks
        """
        logger.info(f"AsyncDetailFetcher.cancel_all_pending_fetches(track_id={track_id})")
        
        with self._lock:
            if track_id is None:
                # Cancel all
                total_cancelled = 0
                for track_workers in self._pending_workers.values():
                    for worker in track_workers.values():
                        worker.cancel()
                        total_cancelled += 1
                self._pending_workers.clear()
                logger.debug(f"AsyncDetailFetcher.cancel_all_pending_fetches() - cancelled all {total_cancelled} workers across all tracks")
            else:
                if track_id in self._pending_workers:
                    cancelled_count = len(self._pending_workers[track_id])
                    for worker in self._pending_workers[track_id].values():
                        worker.cancel()
                    del self._pending_workers[track_id]
                    logger.debug(f"AsyncDetailFetcher.cancel_all_pending_fetches() - cancelled {cancelled_count} workers for track_id={track_id}")
                else:
                    logger.debug(f"AsyncDetailFetcher.cancel_all_pending_fetches() - no pending workers for track_id={track_id}")
    
    def get_cached_data(self, cache_key: str) -> Optional[Any]:
        """Get cached detail data if available.
        
        Args:
            cache_key: Cache key for the interval
            
        Returns:
            Cached data if available, None otherwise
        """
        with self._lock:
            if cache_key in self._cache:
                # Move to end (LRU)
                self._cache.move_to_end(cache_key)
                logger.debug(f"AsyncDetailFetcher.get_cached_data() - cache HIT for cache_key='{cache_key}'")
                return self._cache[cache_key]
            logger.debug(f"AsyncDetailFetcher.get_cached_data() - cache MISS for cache_key='{cache_key}'")
            return None
    
    def clear_cache(self, track_id: Optional[str] = None):
        """Clear cached data.
        
        Args:
            track_id: If provided, only clear cache entries for this track (requires cache_key format)
                     If None, clear all cache
        """
        logger.info(f"AsyncDetailFetcher.clear_cache(track_id={track_id})")
        
        with self._lock:
            if track_id is None:
                cache_size = len(self._cache)
                self._cache.clear()
                logger.debug(f"AsyncDetailFetcher.clear_cache() - cleared all {cache_size} cache entries")
            else:
                # Remove entries that start with track_id (assuming cache_key format includes track_id)
                keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{track_id}:")]
                for key in keys_to_remove:
                    del self._cache[key]
                logger.debug(f"AsyncDetailFetcher.clear_cache() - cleared {len(keys_to_remove)} cache entries for track_id={track_id}")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics.
        
        Returns:
            Dictionary with 'size', 'max_size', 'pending_fetches' keys
        """
        with self._lock:
            pending_count = sum(len(workers) for workers in self._pending_workers.values())
            stats = {
                'size': len(self._cache),
                'max_size': self.max_cache_size,
                'pending_fetches': pending_count
            }
            logger.debug(f"AsyncDetailFetcher.get_cache_stats() - {stats}")
            return stats


__all__ = ['AsyncDetailFetcher', 'DetailFetchWorker']

