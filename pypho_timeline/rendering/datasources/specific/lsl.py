"""LSL (Lab Streaming Layer) live-stream datasources for EEG and Motion data.

This module provides:
  - ``LSLStreamReceiver`` -- a QObject that polls one or more LSL inlets using a
    QTimer, accumulates samples into a pre-allocated ring buffer, and emits
    ``data_received(channel_names, timestamps, samples)`` whenever new data arrive.
  - ``LiveEEGTrackDatasource`` -- wraps an ``LSLStreamReceiver`` and implements the
    :class:`~pypho_timeline.rendering.datasources.track_datasource.TrackDatasource`
    protocol so the live EEG stream can be added directly to a
    :class:`~pypho_timeline.widgets.simple_timeline_widget.SimpleTimelineWidget`.
  - ``LiveMotionTrackDatasource`` -- the same but for motion (IMU) streams.

Usage::

    from pypho_timeline.rendering.datasources.specific.lsl import (
        LSLStreamReceiver,
        LiveEEGTrackDatasource,
        LiveMotionTrackDatasource,
    )

    # Receive EEG from any stream whose type == 'EEG'
    eeg_receiver = LSLStreamReceiver(stream_type='EEG')
    eeg_ds = LiveEEGTrackDatasource(receiver=eeg_receiver, buffer_seconds=300.0)

    # Receive motion from a stream named 'EmotivMotion'
    motion_receiver = LSLStreamReceiver(stream_name='EmotivMotion')
    motion_ds = LiveMotionTrackDatasource(receiver=motion_receiver, buffer_seconds=300.0)

    eeg_receiver.start()
    motion_receiver.start()
"""

from __future__ import annotations

import time
from collections import deque
from typing import List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from qtpy import QtCore

try:
    import pylsl  # type: ignore
    _PYLSL_AVAILABLE = True
except ImportError:
    pylsl = None  # type: ignore
    _PYLSL_AVAILABLE = False

from pypho_timeline.rendering.datasources.track_datasource import IntervalProvidingTrackDatasource
from pypho_timeline.rendering.datasources.specific.eeg import EEGPlotDetailRenderer
from pypho_timeline.rendering.datasources.specific.motion import MotionPlotDetailRenderer
from pypho_timeline.rendering.helpers import ChannelNormalizationMode


# ─────────────────────────────────────────────────────────────────────────────
# LSLStreamReceiver
# ─────────────────────────────────────────────────────────────────────────────

class LSLStreamReceiver(QtCore.QObject):
    """Poll an LSL stream with a QTimer and emit buffered samples.

    The receiver uses a :class:`pylsl.ContinuousResolver` to locate matching
    streams and opens a :class:`pylsl.StreamInlet` when one is found.  A
    ``QTimer`` fires at ``poll_interval_ms`` (default 100 ms) to drain the
    inlet's internal buffer via :meth:`pylsl.StreamInlet.pull_chunk`.

    Parameters
    ----------
    stream_type:
        LSL stream type to match (e.g. ``'EEG'``, ``'Accelerometer'``).
        Pass ``None`` to skip the type filter.
    stream_name:
        LSL stream name to match (e.g. ``'EmotivEPOC+'``).
        Pass ``None`` to skip the name filter.
    poll_interval_ms:
        How often (in milliseconds) to poll the LSL inlet for new data.
    max_chunk_samples:
        Pre-allocated row count for the ``pull_chunk`` buffer.
    resolve_timeout:
        Seconds to wait each time the resolver is queried.
    parent:
        Optional Qt parent.

    Signals
    -------
    data_received(channel_names, timestamps, samples)
        Emitted when new samples are available.  ``timestamps`` is a 1-D
        ``numpy.ndarray`` of LSL timestamps (float64) and ``samples`` is a 2-D
        ``numpy.ndarray`` of shape ``(n_samples, n_channels)``.
    stream_found(stream_info)
        Emitted when the target stream has been connected.
    stream_lost()
        Emitted when the stream becomes unavailable.
    """

    data_received = QtCore.Signal(list, object, object)  # channel_names, timestamps, samples
    stream_found = QtCore.Signal(object)   # pylsl.StreamInfo
    stream_lost = QtCore.Signal()

    def __init__(
        self,
        stream_type: Optional[str] = None,
        stream_name: Optional[str] = None,
        poll_interval_ms: int = 100,
        max_chunk_samples: int = 1024,
        resolve_timeout: float = 0.0,
        parent: Optional[QtCore.QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.stream_type = stream_type
        self.stream_name = stream_name
        self.poll_interval_ms = poll_interval_ms
        self.max_chunk_samples = max_chunk_samples
        self.resolve_timeout = resolve_timeout

        self._inlet: Optional[object] = None  # pylsl.StreamInlet or None
        self._channel_names: List[str] = []
        self._n_channels: int = 0

        # Pre-allocate pull_chunk buffers (avoids allocation inside timer slot)
        self._chunk_buf: Optional[np.ndarray] = None
        self._ts_buf: Optional[np.ndarray] = None

        self._resolver: Optional[object] = None  # pylsl.ContinuousResolver

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._poll)

        # Resolve timer – re-checks for the stream every second when disconnected
        self._resolve_timer = QtCore.QTimer(self)
        self._resolve_timer.setInterval(1000)
        self._resolve_timer.timeout.connect(self._try_connect)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    @property
    def channel_names(self) -> List[str]:
        """Channel names once the stream is connected (empty before that)."""
        return list(self._channel_names)

    @property
    def is_connected(self) -> bool:
        """True if the LSL inlet is open."""
        return self._inlet is not None

    def start(self) -> None:
        """Start background polling.  Triggers stream resolution immediately."""
        if not _PYLSL_AVAILABLE:
            import warnings
            warnings.warn(
                "pylsl is not installed – LSLStreamReceiver will not receive data. "
                "Install it with: pip install pylsl",
                RuntimeWarning,
                stacklevel=2,
            )
            return
        self._try_connect()
        self._resolve_timer.start()

    def stop(self) -> None:
        """Stop polling and release the LSL inlet."""
        self._timer.stop()
        self._resolve_timer.stop()
        if self._inlet is not None:
            try:
                self._inlet.close_stream()
            except Exception:
                pass
            self._inlet = None
            self.stream_lost.emit()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _build_predicate(self) -> str:
        """Build an XPATH predicate string for the resolver."""
        parts: List[str] = []
        if self.stream_type:
            parts.append(f"type='{self.stream_type}'")
        if self.stream_name:
            parts.append(f"name='{self.stream_name}'")
        return " and ".join(parts) if parts else "type!=''"  # match anything if no filters

    @QtCore.Slot()
    def _try_connect(self) -> None:
        """Attempt to resolve and open an LSL inlet."""
        if not _PYLSL_AVAILABLE or self._inlet is not None:
            return
        try:
            predicate = self._build_predicate()
            results = pylsl.resolve_bypred(predicate, 1, timeout=self.resolve_timeout)
        except Exception:
            return

        if not results:
            return

        info = results[0]
        try:
            self._inlet = pylsl.StreamInlet(info, max_buflen=360, recover=True)
            self._n_channels = info.channel_count()
            self._channel_names = self._read_channel_names(info)
            # Pre-allocate buffers
            self._chunk_buf = np.zeros((self.max_chunk_samples, self._n_channels), dtype=np.float64)
            self._ts_buf = np.zeros(self.max_chunk_samples, dtype=np.float64)
            self._timer.start(self.poll_interval_ms)
            self.stream_found.emit(info)
        except Exception:
            self._inlet = None

    @staticmethod
    def _read_channel_names(info: object) -> List[str]:
        """Extract channel labels from pylsl StreamInfo XML."""
        names: List[str] = []
        try:
            chans = info.desc().child("channels").child("channel")
            while chans.empty() is False:
                names.append(chans.child_value("label") or chans.child_value("name") or f"ch{len(names)}")
                chans = chans.next_sibling("channel")
        except Exception:
            pass
        n = info.channel_count()
        while len(names) < n:
            names.append(f"ch{len(names)}")
        return names[:n]

    @QtCore.Slot()
    def _poll(self) -> None:
        """Drain the LSL inlet and emit data_received."""
        if self._inlet is None or self._chunk_buf is None:
            return
        try:
            samples, timestamps = self._inlet.pull_chunk(
                timeout=0.0,
                max_samples=self.max_chunk_samples,
                dest_obj=self._chunk_buf,
            )
        except Exception:
            # Inlet may have become invalid (stream lost)
            self._inlet = None
            self._timer.stop()
            self.stream_lost.emit()
            return

        n = len(timestamps)
        if n == 0:
            return

        ts_arr = np.asarray(timestamps[:n], dtype=np.float64)
        samp_arr = np.asarray(samples[:n], dtype=np.float64)
        self.data_received.emit(self._channel_names, ts_arr, samp_arr)


# ─────────────────────────────────────────────────────────────────────────────
# Shared ring-buffer helper
# ─────────────────────────────────────────────────────────────────────────────

class _LiveRingBuffer:
    """Thread-safe ring buffer that keeps the most recent ``buffer_seconds`` of data.

    Parameters
    ----------
    channel_names:
        Names of the data channels (excluding the time column).
    buffer_seconds:
        Maximum duration of data to retain, in seconds.
    """

    def __init__(self, channel_names: List[str], buffer_seconds: float = 300.0) -> None:
        self._channel_names = list(channel_names)
        self._buffer_seconds = buffer_seconds
        # deque of (timestamps_1d, samples_2d) pairs
        self._chunks: deque = deque()
        self._total_samples: int = 0
        self._lock = QtCore.QMutex()

    # ------------------------------------------------------------------ #
    # Write path
    # ------------------------------------------------------------------ #

    def append(self, timestamps: np.ndarray, samples: np.ndarray, channel_names: List[str]) -> None:
        """Append new samples.  Trims old data automatically."""
        if len(timestamps) == 0:
            return

        # If the channel list has changed, update and reset.
        if channel_names != self._channel_names:
            self._channel_names = list(channel_names)
            self._chunks.clear()
            self._total_samples = 0

        locker = QtCore.QMutexLocker(self._lock)  # noqa: F841
        self._chunks.append((timestamps.copy(), samples.copy()))
        self._total_samples += len(timestamps)
        self._trim()

    def _trim(self) -> None:
        """Remove chunks older than buffer_seconds from the front."""
        if not self._chunks:
            return
        # Use the latest timestamp as reference
        latest_ts = self._chunks[-1][0][-1]
        cutoff = latest_ts - self._buffer_seconds
        while self._chunks:
            oldest_ts = self._chunks[0][0]
            if oldest_ts[-1] < cutoff:
                removed = len(oldest_ts)
                self._chunks.popleft()
                self._total_samples -= removed
            else:
                break

    # ------------------------------------------------------------------ #
    # Read path
    # ------------------------------------------------------------------ #

    def to_dataframe(self) -> pd.DataFrame:
        """Return all buffered data as a DataFrame with columns ``['t'] + channel_names``."""
        locker = QtCore.QMutexLocker(self._lock)  # noqa: F841
        if not self._chunks:
            return pd.DataFrame(columns=["t"] + self._channel_names)
        ts_parts: List[np.ndarray] = []
        samp_parts: List[np.ndarray] = []
        for ts, samp in self._chunks:
            ts_parts.append(ts)
            samp_parts.append(samp)
        all_ts = np.concatenate(ts_parts)
        all_samp = np.concatenate(samp_parts, axis=0)
        df = pd.DataFrame(all_samp, columns=self._channel_names)
        df.insert(0, "t", all_ts)
        return df

    def get_window(self, t_start: float, t_end: float) -> pd.DataFrame:
        """Return a DataFrame slice covering ``[t_start, t_end]``."""
        df = self.to_dataframe()
        if df.empty:
            return df
        mask = (df["t"] >= t_start) & (df["t"] <= t_end)
        return df.loc[mask].reset_index(drop=True)

    @property
    def latest_timestamp(self) -> Optional[float]:
        """The most recent LSL timestamp in the buffer, or ``None`` if empty."""
        locker = QtCore.QMutexLocker(self._lock)  # noqa: F841
        if not self._chunks:
            return None
        return float(self._chunks[-1][0][-1])

    @property
    def earliest_timestamp(self) -> Optional[float]:
        """The oldest LSL timestamp in the buffer, or ``None`` if empty."""
        locker = QtCore.QMutexLocker(self._lock)  # noqa: F841
        if not self._chunks:
            return None
        return float(self._chunks[0][0][0])

    @property
    def channel_names(self) -> List[str]:
        return list(self._channel_names)


# ─────────────────────────────────────────────────────────────────────────────
# LiveEEGTrackDatasource
# ─────────────────────────────────────────────────────────────────────────────

class LiveEEGTrackDatasource(IntervalProvidingTrackDatasource):
    """Live EEG track datasource backed by an :class:`LSLStreamReceiver`.

    Keeps a rolling buffer of the last ``buffer_seconds`` of EEG data.  The
    single interval it exposes spans the entire buffer, growing in real time as
    more data arrive.

    Parameters
    ----------
    receiver:
        An :class:`LSLStreamReceiver` (already constructed, not yet started).
    buffer_seconds:
        How many seconds of history to retain.  Default 300 (5 minutes).
    channel_names:
        Override channel names.  If ``None`` the names are taken from the LSL
        stream info once connected.
    custom_datasource_name:
        Human-readable name shown in the UI.
    """

    # Signal emitted whenever new LSL samples have been appended to the buffer
    new_data_available = QtCore.Signal()

    def __init__(
        self,
        receiver: LSLStreamReceiver,
        buffer_seconds: float = 300.0,
        channel_names: Optional[List[str]] = None,
        custom_datasource_name: Optional[str] = None,
    ) -> None:
        # Build a stub intervals_df so the parent is happy at construction time
        stub_intervals = _make_stub_intervals_df(time.time())
        super().__init__(
            intervals_df=stub_intervals,
            detailed_df=None,
            custom_datasource_name=custom_datasource_name or "LiveEEG",
        )

        self._buffer_seconds = buffer_seconds
        self._channel_names: List[str] = list(channel_names) if channel_names else []
        self._ring: _LiveRingBuffer = _LiveRingBuffer(self._channel_names, buffer_seconds)

        self._receiver = receiver
        receiver.data_received.connect(self._on_data_received)
        receiver.stream_found.connect(self._on_stream_found)

    # ------------------------------------------------------------------ #
    # Slots
    # ------------------------------------------------------------------ #

    @QtCore.Slot(object)
    def _on_stream_found(self, info: object) -> None:
        ch_names = self._receiver.channel_names
        if ch_names:
            self._channel_names = ch_names
            self._ring = _LiveRingBuffer(ch_names, self._buffer_seconds)

    @QtCore.Slot(list, object, object)
    def _on_data_received(
        self,
        channel_names: List[str],
        timestamps: np.ndarray,
        samples: np.ndarray,
    ) -> None:
        self._ring.append(timestamps, samples, channel_names)
        self._update_intervals()
        self.new_data_available.emit()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _update_intervals(self) -> None:
        """Rebuild the single intervals_df row from the current buffer extent."""
        t0 = self._ring.earliest_timestamp
        t1 = self._ring.latest_timestamp
        if t0 is None or t1 is None:
            return
        self.intervals_df = _make_stub_intervals_df(t0, t1)

    # ------------------------------------------------------------------ #
    # TrackDatasource protocol
    # ------------------------------------------------------------------ #

    @property
    def total_df_start_end_times(self) -> Tuple[float, float]:
        t0 = self._ring.earliest_timestamp
        t1 = self._ring.latest_timestamp
        if t0 is None or t1 is None:
            now = time.time()
            return (now, now)
        return (float(t0), float(t1))

    def fetch_detailed_data(self, interval: pd.Series) -> pd.DataFrame:
        """Return buffered data slice for the requested interval."""
        t_start = float(interval.get("t_start", 0.0))
        t_duration = float(interval.get("t_duration", 0.0))
        t_end = t_start + t_duration
        return self._ring.get_window(t_start, t_end)

    def get_detail_renderer(self) -> EEGPlotDetailRenderer:
        ch_names = self._channel_names or ["ch0"]
        return EEGPlotDetailRenderer(
            pen_width=1,
            channel_names=ch_names,
            fallback_normalization_mode=ChannelNormalizationMode.GROUPMINMAXRANGE,
            normalize=True,
            normalize_over_full_data=False,
        )

    # ------------------------------------------------------------------ #
    # Live-data helpers used by the live timeline
    # ------------------------------------------------------------------ #

    @property
    def live_timestamp(self) -> Optional[float]:
        """Most recent LSL timestamp in the buffer."""
        return self._ring.latest_timestamp

    def get_full_buffer_df(self) -> pd.DataFrame:
        """Return the entire ring-buffer as a DataFrame."""
        return self._ring.to_dataframe()


# ─────────────────────────────────────────────────────────────────────────────
# LiveMotionTrackDatasource
# ─────────────────────────────────────────────────────────────────────────────

class LiveMotionTrackDatasource(IntervalProvidingTrackDatasource):
    """Live Motion/IMU track datasource backed by an :class:`LSLStreamReceiver`.

    Identical in structure to :class:`LiveEEGTrackDatasource` but uses the
    :class:`~pypho_timeline.rendering.datasources.specific.motion.MotionPlotDetailRenderer`.

    Parameters
    ----------
    receiver:
        An :class:`LSLStreamReceiver` configured for a motion/IMU stream.
    buffer_seconds:
        How many seconds of history to retain.  Default 300.
    channel_names:
        Override channel names (e.g. ``['AccX','AccY','AccZ','GyroX','GyroY','GyroZ']``).
    custom_datasource_name:
        Human-readable name shown in the UI.
    """

    new_data_available = QtCore.Signal()

    def __init__(
        self,
        receiver: LSLStreamReceiver,
        buffer_seconds: float = 300.0,
        channel_names: Optional[List[str]] = None,
        custom_datasource_name: Optional[str] = None,
    ) -> None:
        stub_intervals = _make_stub_intervals_df(time.time())
        super().__init__(
            intervals_df=stub_intervals,
            detailed_df=None,
            custom_datasource_name=custom_datasource_name or "LiveMotion",
        )

        self._buffer_seconds = buffer_seconds
        self._channel_names: List[str] = list(channel_names) if channel_names else []
        self._ring: _LiveRingBuffer = _LiveRingBuffer(self._channel_names, buffer_seconds)

        self._receiver = receiver
        receiver.data_received.connect(self._on_data_received)
        receiver.stream_found.connect(self._on_stream_found)

    @QtCore.Slot(object)
    def _on_stream_found(self, info: object) -> None:
        ch_names = self._receiver.channel_names
        if ch_names:
            self._channel_names = ch_names
            self._ring = _LiveRingBuffer(ch_names, self._buffer_seconds)

    @QtCore.Slot(list, object, object)
    def _on_data_received(
        self,
        channel_names: List[str],
        timestamps: np.ndarray,
        samples: np.ndarray,
    ) -> None:
        self._ring.append(timestamps, samples, channel_names)
        self._update_intervals()
        self.new_data_available.emit()

    def _update_intervals(self) -> None:
        t0 = self._ring.earliest_timestamp
        t1 = self._ring.latest_timestamp
        if t0 is None or t1 is None:
            return
        self.intervals_df = _make_stub_intervals_df(t0, t1)

    @property
    def total_df_start_end_times(self) -> Tuple[float, float]:
        t0 = self._ring.earliest_timestamp
        t1 = self._ring.latest_timestamp
        if t0 is None or t1 is None:
            now = time.time()
            return (now, now)
        return (float(t0), float(t1))

    def fetch_detailed_data(self, interval: pd.Series) -> pd.DataFrame:
        t_start = float(interval.get("t_start", 0.0))
        t_duration = float(interval.get("t_duration", 0.0))
        t_end = t_start + t_duration
        return self._ring.get_window(t_start, t_end)

    def get_detail_renderer(self) -> MotionPlotDetailRenderer:
        ch_names = self._channel_names or ["ch0"]
        return MotionPlotDetailRenderer(pen_width=1, channel_names=ch_names)

    @property
    def live_timestamp(self) -> Optional[float]:
        return self._ring.latest_timestamp

    def get_full_buffer_df(self) -> pd.DataFrame:
        return self._ring.to_dataframe()


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_stub_intervals_df(t_start: float, t_end: Optional[float] = None) -> pd.DataFrame:
    """Create a minimal single-row intervals DataFrame."""
    if t_end is None:
        t_end = t_start + 1.0
    duration = max(float(t_end) - float(t_start), 1.0)
    return pd.DataFrame(
        {
            "t_start": [float(t_start)],
            "t_duration": [duration],
            "t_end": [float(t_end)],
        }
    )


__all__ = [
    "LSLStreamReceiver",
    "LiveEEGTrackDatasource",
    "LiveMotionTrackDatasource",
]
