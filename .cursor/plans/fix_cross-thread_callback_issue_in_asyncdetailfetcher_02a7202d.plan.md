---
name: Fix cross-thread callback issue in AsyncDetailFetcher
overview: Fix the issue where QTimer.singleShot is called from worker threads, preventing callbacks from executing. Replace with proper Qt cross-thread communication mechanism to ensure callbacks execute on the main thread.
todos: []
---

# Fix Cross-Thread Callback Issue in AsyncDetailFetcher

## Problem

The `DetailFetchWorker.run()` method calls `QtCore.QTimer.singleShot(0, ...)` from a worker thread to schedule callbacks on the main thread. However, `QTimer.singleShot` doesn't work when called from worker threads because it requires the main thread's event loop. This causes callbacks to never execute, signals to never emit, and detail rendering to never occur.

## Root Cause

- `DetailFetchWorker.run()` executes in a background thread (via QThreadPool)
- `QTimer.singleShot(0, lambda: self.callback(...))` is called from the worker thread
- QTimer requires the main thread's event loop to function
- The scheduled callbacks never execute, so the `detail_data_ready` signal never emits

## Solution

Use Qt's signal/slot mechanism with `Qt.QueuedConnection` to properly marshal the callback to the main thread. The worker will emit a signal that the AsyncDetailFetcher handles on the main thread.

## Implementation Details

### Files to Modify

1. **`pypho_timeline/rendering/async_detail_fetcher.py`**

- Add a signal to `DetailFetchWorker` for completion
- Modify `run()` to emit signal instead of using QTimer
- Connect worker signal to AsyncDetailFetcher slot on main thread
- Handle signal emission in AsyncDetailFetcher to call callback/emit detail_data_ready

### Detailed Changes

#### 1. Modify DetailFetchWorker class

- **Add signal**: `finished = QtCore.Signal(str, str, pd.DataFrame, object, object)` (track_id, cache_key, interval, data, error)
- **Modify `__init__`**: Store reference to AsyncDetailFetcher or use a different mechanism
- **Modify `run()`**: 
- Remove `QTimer.singleShot` calls
- Emit `finished` signal with results instead
- Signal will automatically be queued to main thread via Qt.QueuedConnection

#### 2. Modify AsyncDetailFetcher class

- **Add slot method**: `_on_worker_finished(track_id, cache_key, interval, data, error)`
- This will be called on the main thread when worker emits signal
- Call the original callback or emit `detail_data_ready` signal
- Update cache and pending workers tracking
- **Modify `fetch_detail_async()`**:
- Connect worker's `finished` signal to `_on_worker_finished` slot
- Use `Qt.QueuedConnection` to ensure it runs on main thread
- Remove callback parameter passing to worker (handle in AsyncDetailFetcher)

#### 3. Alternative Simpler Approach

Instead of adding signals to the worker (which requires making it a QObject), we can:

- Have the worker store results in a thread-safe way
- Use `QMetaObject.invokeMethod` on AsyncDetailFetcher (a QObject) to call a method on the main thread
- Or use a custom signal on AsyncDetailFetcher that the worker triggers

Actually, the simplest approach: Make DetailFetchWorker inherit from QObject (in addition to QRunnable) so it can emit signals, or create a helper QObject that emits signals.

#### 4. Recommended Implementation

**Option A: Make DetailFetchWorker a QObject (preferred)**

- Change inheritance to `QtCore.QObject, QtCore.QRunnable`
- Add `finished` signal
- Emit signal from `run()` method
- Connect signal in `fetch_detail_async()` with `Qt.QueuedConnection`

**Option B: Use QMetaObject.invokeMethod**

- Keep worker as QRunnable
- In `run()`, use `QMetaObject.invokeMethod` to call a method on AsyncDetailFetcher
- AsyncDetailFetcher method handles callback on main thread

**Option C: Store results and use QTimer on main thread**

- Worker stores results in a thread-safe queue/dict
- AsyncDetailFetcher polls or uses a signal to check for completed workers
- Schedule callback using QTimer from main thread

## Recommended: Option A

Make `DetailFetchWorker` inherit from both `QObject` and `QRunnable`, add a `finished` signal, and connect it to AsyncDetailFetcher's slot with `Qt.QueuedConnection`. This is the most Qt-idiomatic solution.

## Changes Required

1. **DetailFetchWorker class**:

- Change: `class DetailFetchWorker(QtCore.QRunnable):` → `class DetailFetchWorker(QtCore.QObject, QtCore.QRunnable):`
- Add: `finished = QtCore.Signal(str, str, pd.DataFrame, object, object)`
- Modify `__init__`: Call `super().__init__()` for QObject
- Modify `run()`: Replace `QTimer.singleShot` with `self.finished.emit(...)`
- Remove: `callback` parameter (handle in AsyncDetailFetcher)

2. **AsyncDetailFetcher class**:

- Add: `_on_worker_finished(track_id, cache_key, interval, data, error)` slot method
- Modify `fetch_detail_async()`: 
    - Connect worker's `finished` signal to `_on_worker_finished` with `Qt.QueuedConnection`
    - Store callback in a dict keyed by cache_key if needed
- In `_on_worker_finished`: Call callback or emit `detail_data_ready` signal, update cache

3. **Update logging**:

- Log signal emission in worker
- Log signal reception in AsyncDetailFetcher slot
- Log callback execution

## Testing

After implementation, logs should show:

- Worker emitting `finished` signal