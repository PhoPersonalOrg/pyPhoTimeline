"""AsyncDetailFetcher - Asynchronous data fetching for timeline track details.

This module provides async data fetching using Qt QThreadPool for fetching detailed
data when intervals scroll into the viewport.
"""
from typing import Dict, List, Optional, Callable, Any
from collections import OrderedDict
from threading import Lock
import pandas as pd
from qtpy import QtCore, QtWidgets

from pypho_timeline.rendering.datasources.track_datasource import TrackDatasource


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
    
    def cancel(self):
        """Mark this worker as cancelled."""
        with self._lock:
            self._cancelled = True
    
    def is_cancelled(self) -> bool:
        """Check if this worker has been cancelled."""
        with self._lock:
            return self._cancelled
    
    def run(self):
        """Execute the data fetch in the worker thread."""
        if self.is_cancelled():
            return
        
        try:
            detail_data = self.datasource.fetch_detailed_data(self.interval)
            
            if not self.is_cancelled():
                # Convert Series to DataFrame for DetailRenderer compatibility
                interval_df = self.interval.to_frame().T
                # Use QTimer.singleShot to ensure callback runs on main thread
                QtCore.QTimer.singleShot(0, lambda: self.callback(
                    self.track_id, self.cache_key, interval_df, detail_data, None
                ))
        except Exception as e:
            if not self.is_cancelled():
                # Convert Series to DataFrame for DetailRenderer compatibility
                interval_df = self.interval.to_frame().T
                QtCore.QTimer.singleShot(0, lambda: self.callback(
                    self.track_id, self.cache_key, interval_df, None, e
                ))


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
        self._thread_pool.setMaxThreadCount(max(4, self._thread_pool.maxThreadCount()))
    
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
        
        # Check cache first
        with self._lock:
            if cache_key in self._cache:
                # Cache hit - return immediately
                data = self._cache[cache_key]
                # Move to end (LRU)
                self._cache.move_to_end(cache_key)
                # Convert Series to DataFrame for DetailRenderer compatibility
                interval_df = interval.to_frame().T
                if callback:
                    QtCore.QTimer.singleShot(0, lambda: callback(track_id, cache_key, interval_df, data, None))
                else:
                    self.detail_data_ready.emit(track_id, cache_key, interval_df, data, None)
                return
            
            # Check if already pending
            if track_id in self._pending_workers:
                if cache_key in self._pending_workers[track_id]:
                    # Already fetching this interval
                    return
        
        # Create worker
        # Note: callback will receive DataFrame (converted in worker.run())
        worker_callback = callback or (lambda tid, ck, iv, d, e: self.detail_data_ready.emit(tid, ck, iv, d, e))
        worker = DetailFetchWorker(track_id, interval, datasource, cache_key, worker_callback)
        
        # Track pending worker
        with self._lock:
            if track_id not in self._pending_workers:
                self._pending_workers[track_id] = {}
            self._pending_workers[track_id][cache_key] = worker
        
        # Start worker
        self._thread_pool.start(worker)
    
    def _on_detail_fetched(self, track_id: str, cache_key: str, interval: pd.DataFrame, 
                          detail_data: Any, error: Optional[Exception]):
        """Handle when detail data is fetched (called from worker callback)."""
        with self._lock:
            # Remove from pending
            if track_id in self._pending_workers:
                if cache_key in self._pending_workers[track_id]:
                    del self._pending_workers[track_id][cache_key]
                    if not self._pending_workers[track_id]:
                        del self._pending_workers[track_id]
            
            # Cache the data if successful
            if error is None and detail_data is not None:
                self._cache[cache_key] = detail_data
                self._cache.move_to_end(cache_key)
                
                # Evict if cache too large
                while len(self._cache) > self.max_cache_size:
                    self._cache.popitem(last=False)  # Remove oldest
    
    def cancel_pending_fetches(self, track_id: str, interval_keys: List[str]):
        """Cancel pending fetches for specific intervals.
        
        Args:
            track_id: Track identifier
            interval_keys: List of cache keys for intervals to cancel
        """
        with self._lock:
            if track_id not in self._pending_workers:
                return
            
            for cache_key in interval_keys:
                if cache_key in self._pending_workers[track_id]:
                    worker = self._pending_workers[track_id][cache_key]
                    worker.cancel()
                    del self._pending_workers[track_id][cache_key]
            
            if not self._pending_workers[track_id]:
                del self._pending_workers[track_id]
    
    def cancel_all_pending_fetches(self, track_id: Optional[str] = None):
        """Cancel all pending fetches for a track, or all tracks if track_id is None.
        
        Args:
            track_id: Track identifier, or None to cancel all tracks
        """
        with self._lock:
            if track_id is None:
                # Cancel all
                for track_workers in self._pending_workers.values():
                    for worker in track_workers.values():
                        worker.cancel()
                self._pending_workers.clear()
            else:
                if track_id in self._pending_workers:
                    for worker in self._pending_workers[track_id].values():
                        worker.cancel()
                    del self._pending_workers[track_id]
    
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
                return self._cache[cache_key]
            return None
    
    def clear_cache(self, track_id: Optional[str] = None):
        """Clear cached data.
        
        Args:
            track_id: If provided, only clear cache entries for this track (requires cache_key format)
                     If None, clear all cache
        """
        with self._lock:
            if track_id is None:
                self._cache.clear()
            else:
                # Remove entries that start with track_id (assuming cache_key format includes track_id)
                keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{track_id}:")]
                for key in keys_to_remove:
                    del self._cache[key]
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics.
        
        Returns:
            Dictionary with 'size', 'max_size', 'pending_fetches' keys
        """
        with self._lock:
            pending_count = sum(len(workers) for workers in self._pending_workers.values())
            return {
                'size': len(self._cache),
                'max_size': self.max_cache_size,
                'pending_fetches': pending_count
            }


__all__ = ['AsyncDetailFetcher', 'DetailFetchWorker']

