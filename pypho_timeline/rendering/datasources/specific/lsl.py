"""Minimal LSL connector for receiving live EEG data.

Design based on analysis of stream_viewer's LSLDataSource
(github.com/PhoPersonalOrg/stream_viewer/blob/main/stream_viewer/data/stream_lsl.py).

Key patterns borrowed from stream_viewer:
- ``pylsl.ContinuousResolver`` (managed by a QTimer) to discover streams.
- ``QTimer`` for non-blocking periodic polling rather than a blocking thread.
- Pre-allocated numpy destination buffer passed to ``pull_chunk(dest_obj=…)``
  to avoid repeated allocations; buffer is doubled when full (same strategy).
- ``proc_ALL`` processing flags on the inlet for clock correction, dejitter, etc.

Usage::

    from pypho_timeline.rendering.datasources.specific.lsl import (
        LSLStreamReceiver,
        LiveEEGTrackDatasource,
    )

    # --- receive raw data via Qt signals ---
    receiver = LSLStreamReceiver(stream_type='EEG')
    receiver.data_received.connect(my_slot)   # slot(timestamps, data)
    receiver.start()

    # --- or use the higher-level rolling-buffer datasource ---
    ds = LiveEEGTrackDatasource(stream_type='EEG', window_duration_s=30.0)
    ds.start()
    # ds.detailed_df is a pandas DataFrame with columns ['t', ch0, ch1, …]
    # ds.source_data_changed_signal is emitted on every new chunk
"""

from __future__ import annotations

import threading
import warnings
from typing import List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from qtpy import QtCore

try:
    import pylsl  # type: ignore

    _PYLSL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYLSL_AVAILABLE = False


# ============================================================================ #
# LSLStreamReceiver                                                             #
# ============================================================================ #


class LSLStreamReceiver(QtCore.QObject):
    """Minimal, performant LSL receiver for live EEG (or any numerical) data.

    Uses the same QTimer-based polling strategy as stream_viewer's
    ``LSLDataSource``:

    1. A ``ContinuousResolver`` is checked every *resolver_interval_ms* ms.
    2. Once a matching stream is found a ``StreamInlet`` is created and
       a second timer starts pulling data every *poll_interval_ms* ms.
    3. ``pull_chunk(dest_obj=…)`` is used with a pre-allocated numpy buffer
       to avoid Python heap allocations on each frame.

    Signals
    -------
    data_received(timestamps, data)
        Emitted when new samples arrive.
        *timestamps*: shape ``(n_samples,)`` – LSL clock values.
        *data*: shape ``(n_channels, n_samples)``.
    stream_connected(stream_name)
        Emitted once the ``StreamInlet`` is successfully created.
    stream_disconnected()
        Emitted when the inlet is closed/lost.
    """

    data_received = QtCore.Signal(np.ndarray, np.ndarray)
    stream_connected = QtCore.Signal(str)
    stream_disconnected = QtCore.Signal()

    # pylsl channel-format → numpy dtype (populated on first use)
    _CF_MAP: dict = {}

    def __init__(
        self,
        stream_type: str = "EEG",
        stream_name: Optional[str] = None,
        poll_interval_ms: int = 50,
        resolver_interval_ms: int = 500,
        buffer_duration_s: float = 2.0,
        parent: Optional[QtCore.QObject] = None,
    ) -> None:
        """
        Parameters
        ----------
        stream_type:
            LSL stream type filter (e.g. ``'EEG'``).  Pass ``''`` to
            match any type.
        stream_name:
            Optional LSL stream name prefix filter.
        poll_interval_ms:
            How often (ms) to pull data from the inlet.  Default 50 ms
            gives ~20 Hz update rate (actual EEG sample rate is higher;
            we just batch-collect buffered samples).
        resolver_interval_ms:
            How often (ms) to re-check the resolver.
        buffer_duration_s:
            Size of the LSL inlet's internal ring buffer in seconds.
        parent:
            Optional Qt parent object.
        """
        if not _PYLSL_AVAILABLE:
            raise ImportError(
                "pylsl is required for LSLStreamReceiver. "
                "Install with: pip install pylsl"
            )
        super().__init__(parent)

        self._stream_type = stream_type
        self._stream_name = stream_name
        self._buffer_duration = buffer_duration_s

        self._inlet: Optional["pylsl.StreamInlet"] = None
        self._pull_buffer: Optional[np.ndarray] = None
        self._stream_info: Optional["pylsl.StreamInfo"] = None
        self._channel_names: List[str] = []

        # Build ContinuousResolver predicate (same logic as stream_viewer)
        parts: List[str] = []
        if stream_type:
            parts.append(f"type='{stream_type}'")
        if stream_name:
            parts.append(f"starts-with(name,'{stream_name}')")
        pred = " and ".join(parts)
        self._resolver: Optional["pylsl.ContinuousResolver"] = (
            pylsl.ContinuousResolver(pred=pred)
        )

        # Timer: resolve stream
        self._resolver_timer = QtCore.QTimer(self)
        self._resolver_timer.setInterval(resolver_interval_ms)
        self._resolver_timer.timeout.connect(self._try_resolve)

        # Timer: pull data
        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.setInterval(poll_interval_ms)
        self._poll_timer.timeout.connect(self._pull_data)

    # ---------------------------------------------------------------------- #
    # Public API                                                               #
    # ---------------------------------------------------------------------- #

    def start(self) -> None:
        """Begin stream discovery (and data pulling once connected)."""
        self._resolver_timer.start()

    def stop(self) -> None:
        """Stop all timers and close the inlet."""
        self._resolver_timer.stop()
        self._poll_timer.stop()
        if self._inlet is not None:
            try:
                self._inlet.close_stream()
            except Exception:
                pass
            self._inlet = None
            self.stream_disconnected.emit()

    @property
    def is_connected(self) -> bool:
        """``True`` when a ``StreamInlet`` has been established."""
        return self._inlet is not None

    @property
    def channel_names(self) -> List[str]:
        """Channel labels from stream metadata (empty list until connected)."""
        return list(self._channel_names)

    @property
    def stream_info(self) -> Optional["pylsl.StreamInfo"]:
        """The connected stream's ``pylsl.StreamInfo``, or ``None``."""
        return self._stream_info

    # ---------------------------------------------------------------------- #
    # Private helpers                                                          #
    # ---------------------------------------------------------------------- #

    @QtCore.Slot()
    def _try_resolve(self) -> None:
        """Check resolver results; create inlet when a stream is found."""
        if self._inlet is not None or self._resolver is None:
            return
        results = self._resolver.results()
        if not results:
            return
        if len(results) > 1:
            warnings.warn(
                f"LSLStreamReceiver: multiple streams matched, using first "
                f"('{results[0].name()}').",
                stacklevel=2,
            )
        self._create_inlet(results[0])
        self._resolver_timer.stop()
        self._resolver = None
        self.stream_connected.emit(self._stream_info.name())
        self._poll_timer.start()

    def _create_inlet(self, stream_info: "pylsl.StreamInfo") -> None:
        """Create ``StreamInlet`` and pre-allocate pull buffer."""
        self._stream_info = stream_info
        n_chans = stream_info.channel_count()
        srate = stream_info.nominal_srate()
        cf = stream_info.channel_format()

        # Build dtype map lazily
        if not self._CF_MAP:
            self._CF_MAP.update(
                {
                    pylsl.cf_string: "str",
                    pylsl.cf_int8: "int8",
                    pylsl.cf_int16: "int16",
                    pylsl.cf_int32: "int32",
                    pylsl.cf_int64: "int64",
                    pylsl.cf_float32: "float32",
                    pylsl.cf_double64: "float64",
                    pylsl.cf_undefined: "float32",
                }
            )
        dtype = self._CF_MAP.get(cf, "float32")

        if cf == pylsl.cf_string or srate == 0:
            # Irregular / string stream — no pre-allocated buffer
            self._pull_buffer = None
            max_chunklen = 0
            max_buflen = max(int(self._buffer_duration), 1)
        else:
            # Pre-allocate buffer: enough for ~0.1 s, rounded to next power of 2
            buf_samps = max(1, int(np.ceil(0.1 * srate)))
            buf_samps = 1 << (buf_samps - 1).bit_length()
            self._pull_buffer = np.zeros((buf_samps, n_chans), dtype=dtype)
            max_chunklen = 1  # see stream_viewer comment on liblsl issue #96
            max_buflen = max(int(self._buffer_duration), 1)

        self._inlet = pylsl.StreamInlet(
            stream_info,
            max_buflen=max_buflen,
            max_chunklen=max_chunklen,
            processing_flags=pylsl.proc_ALL,
        )

        self._channel_names = self._read_channel_names(stream_info, n_chans)

        # Flush any stale samples (stream_viewer's pattern)
        self._inlet.pull_chunk()
        self._inlet.flush()

    @staticmethod
    def _read_channel_names(
        stream_info: "pylsl.StreamInfo", n_chans: int
    ) -> List[str]:
        """Extract channel labels from the stream's XML description."""
        names: List[str] = []
        ch = stream_info.desc().child("channels").child("channel")
        for k in range(n_chans):
            label = ch.child_value("label")
            names.append(label if label else str(k))
            ch = ch.next_sibling()
        return names

    @QtCore.Slot()
    def _pull_data(self) -> None:
        """Pull buffered samples from the inlet and emit ``data_received``."""
        if self._inlet is None:
            return

        if self._pull_buffer is None:
            # String / irregular stream path
            data_list, timestamps = self._inlet.pull_chunk()
            if not timestamps:
                return
            data = np.array(data_list, order="F").T
        else:
            _, timestamps = self._inlet.pull_chunk(
                dest_obj=self._pull_buffer.data,
                max_samples=self._pull_buffer.shape[0],
            )
            n = len(timestamps)
            if n == 0:
                return
            # Copy before buffer may be overwritten on next poll
            data = self._pull_buffer[:n].T.copy()  # (n_chans, n_samples)

            # Double buffer size if it was completely full (stream_viewer pattern)
            if n == self._pull_buffer.shape[0]:
                self._pull_buffer = np.zeros(
                    (self._pull_buffer.shape[0] * 2, self._pull_buffer.shape[1]),
                    dtype=self._pull_buffer.dtype,
                )

        self.data_received.emit(np.array(timestamps, dtype=float), data)


# ============================================================================ #
# LiveEEGTrackDatasource                                                        #
# ============================================================================ #


class LiveEEGTrackDatasource(QtCore.QObject):
    """TrackDatasource that buffers live LSL EEG data for timeline display.

    Wraps :class:`LSLStreamReceiver` and maintains a rolling window of
    recent samples.  As new data arrives, ``source_data_changed_signal`` is
    emitted so that a connected timeline widget can refresh.

    Implements the ``TrackDatasource`` protocol so it can be used directly
    with pyPhoTimeline's track-rendering system (e.g. ``add_eeg_track``).

    The :py:attr:`detailed_df` attribute is rebuilt on every new chunk; it has
    columns ``['t', <ch0>, <ch1>, …]`` with float timestamps.

    Usage::

        ds = LiveEEGTrackDatasource(stream_type='EEG', window_duration_s=30.0)
        ds.start()
        timeline.add_eeg_track("Live EEG", eeg_datasource=ds)
    """

    # Qt signals (requires QObject as base class)
    source_data_changed_signal = QtCore.Signal()

    def __init__(
        self,
        stream_type: str = "EEG",
        stream_name: Optional[str] = None,
        window_duration_s: float = 30.0,
        poll_interval_ms: int = 50,
        custom_datasource_name: Optional[str] = None,
        parent: Optional[QtCore.QObject] = None,
    ) -> None:
        """
        Parameters
        ----------
        stream_type:
            LSL stream type to search for (e.g. ``'EEG'``).
        stream_name:
            Optional LSL stream name prefix filter.
        window_duration_s:
            Size of the rolling data buffer in seconds.
        poll_interval_ms:
            How often (ms) the underlying receiver polls the inlet.
        custom_datasource_name:
            Human-readable identifier for this datasource.
        parent:
            Optional Qt parent object.
        """
        super().__init__(parent)

        self.custom_datasource_name: str = (
            custom_datasource_name or f"LiveEEG_{stream_type}"
        )
        self._window_duration_s = window_duration_s

        # Lock protecting detailed_df / intervals_df from worker-thread reads
        self._data_lock = threading.Lock()
        # Rolling buffer
        self._ts_buf: np.ndarray = np.empty(0, dtype=float)
        self._data_buf: Optional[np.ndarray] = None  # shape (n_chans, n_total)
        self._channel_names: List[str] = []

        # Public DataFrame attributes (TrackDatasource protocol)
        self.detailed_df: pd.DataFrame = pd.DataFrame({"t": pd.Series(dtype=float)})
        import time as _time

        t_now = _time.time()
        self.intervals_df: pd.DataFrame = pd.DataFrame(
            {
                "t_start": [t_now],
                "t_duration": [window_duration_s],
                "t_end": [t_now + window_duration_s],
                "series_vertical_offset": [0.0],
                "series_height": [1.0],
            }
        )

        self._receiver = LSLStreamReceiver(
            stream_type=stream_type,
            stream_name=stream_name,
            poll_interval_ms=poll_interval_ms,
        )
        self._receiver.data_received.connect(self._on_data_received)
        self._receiver.stream_connected.connect(self._on_stream_connected)

    # ---------------------------------------------------------------------- #
    # Public API                                                               #
    # ---------------------------------------------------------------------- #

    def start(self) -> None:
        """Start the LSL receiver (stream discovery + data polling)."""
        self._receiver.start()

    def stop(self) -> None:
        """Stop the LSL receiver."""
        self._receiver.stop()

    @property
    def is_connected(self) -> bool:
        """``True`` once the LSL inlet has been created."""
        return self._receiver.is_connected

    @property
    def channel_names(self) -> List[str]:
        """Current channel names (empty until connected)."""
        return list(self._channel_names)

    # ---------------------------------------------------------------------- #
    # TrackDatasource protocol implementation                                  #
    # ---------------------------------------------------------------------- #

    @property
    def df(self) -> pd.DataFrame:
        """The intervals DataFrame (TrackDatasource protocol)."""
        with self._data_lock:
            return self.intervals_df.copy()

    @property
    def time_column_names(self) -> List[str]:
        """Time-related column names (TrackDatasource protocol)."""
        return ["t_start", "t_duration", "t_end"]

    @property
    def total_df_start_end_times(self) -> Tuple[float, float]:
        with self._data_lock:
            if self._ts_buf.size == 0:
                import time as _t

                now = _t.time()
                return (now, now + self._window_duration_s)
            return (float(self._ts_buf[0]), float(self._ts_buf[-1]))

    def get_overview_intervals(self) -> pd.DataFrame:
        with self._data_lock:
            return self.intervals_df.copy()

    def get_updated_data_window(self, new_start, new_end) -> pd.DataFrame:
        with self._data_lock:
            return self.intervals_df.copy()

    def fetch_detailed_data(self, interval: pd.Series) -> pd.DataFrame:
        """Return the EEG DataFrame slice for *interval* (thread-safe)."""
        with self._data_lock:
            if self.detailed_df is None or len(self.detailed_df) == 0:
                return pd.DataFrame({"t": pd.Series(dtype=float)})
            df = self.detailed_df.copy()

        # Filter to the requested interval
        if hasattr(interval, "get"):
            t_start_val = interval.get("t_start", self._ts_buf[0] if self._ts_buf.size else 0.0)
            t_dur = interval.get("t_duration", self._window_duration_s)
        else:
            t_start_val = getattr(interval, "t_start", self._ts_buf[0] if self._ts_buf.size else 0.0)
            t_dur = getattr(interval, "t_duration", self._window_duration_s)
        t_end_val = t_start_val + t_dur
        mask = (df["t"] >= t_start_val) & (df["t"] <= t_end_val)
        return df[mask]

    def get_detail_renderer(self):
        """Return an :class:`~pypho_timeline.rendering.datasources.specific.eeg.EEGPlotDetailRenderer`."""
        from pypho_timeline.rendering.datasources.specific.eeg import (
            EEGPlotDetailRenderer,
        )

        ch = self._channel_names if self._channel_names else None
        return EEGPlotDetailRenderer(pen_width=1, channel_names=ch)

    # ---------------------------------------------------------------------- #
    # Qt slots                                                                 #
    # ---------------------------------------------------------------------- #

    @QtCore.Slot(str)
    def _on_stream_connected(self, stream_name: str) -> None:
        """Record channel names when the inlet is first established."""
        self._channel_names = list(self._receiver.channel_names)
        print(
            f"[LiveEEGTrackDatasource] Connected to LSL stream "
            f"'{stream_name}' ({len(self._channel_names)} channels)"
        )

    @QtCore.Slot(np.ndarray, np.ndarray)
    def _on_data_received(
        self, timestamps: np.ndarray, data: np.ndarray
    ) -> None:
        """Append new samples to the rolling buffer; rebuild DataFrame."""
        if timestamps.size == 0:
            return

        with self._data_lock:
            # Concatenate new timestamps / data onto the rolling buffer
            self._ts_buf = np.concatenate([self._ts_buf, timestamps])
            if self._data_buf is None:
                self._data_buf = data
            else:
                self._data_buf = np.concatenate([self._data_buf, data], axis=1)

            # Trim samples that fall outside the rolling window
            t_cutoff = timestamps[-1] - self._window_duration_s
            if t_cutoff > self._ts_buf[0]:
                keep = self._ts_buf >= t_cutoff
                self._ts_buf = self._ts_buf[keep]
                self._data_buf = self._data_buf[:, keep]

            # Rebuild detailed_df
            ch_names = (
                self._channel_names
                if self._channel_names
                else [str(i) for i in range(self._data_buf.shape[0])]
            )
            df_dict = {"t": self._ts_buf}
            for i, ch in enumerate(ch_names):
                df_dict[ch] = self._data_buf[i]
            self.detailed_df = pd.DataFrame(df_dict)

            # Keep intervals_df in sync with the current window
            t_start = float(self._ts_buf[0])
            t_end = float(self._ts_buf[-1])
            self.intervals_df = pd.DataFrame(
                {
                    "t_start": [t_start],
                    "t_duration": [t_end - t_start],
                    "t_end": [t_end],
                    "series_vertical_offset": [0.0],
                    "series_height": [1.0],
                }
            )

        self.source_data_changed_signal.emit()


__all__ = ["LSLStreamReceiver", "LiveEEGTrackDatasource"]
