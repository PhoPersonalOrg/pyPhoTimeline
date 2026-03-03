"""Tests for the minimal LSL connector.

These tests run without a real LSL stream by mocking pylsl entirely.
The conftest.py ensures heavy/unavailable external deps are stubbed.

The test suite covers:
 - LSLStreamReceiver construction and lifecycle (start / stop)
 - _read_channel_names static helper
 - Rolling-buffer logic inside LiveEEGTrackDatasource
 - LiveEEGTrackDatasource with simulated data injected directly
   (no real Qt event-loop required for the data-buffer tests)
"""

import sys
import time
import threading
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Minimal pylsl stand-in (used when the real C extension is absent)
# ---------------------------------------------------------------------------

class _MockPylsl:
    cf_string = 6
    cf_int8 = 1
    cf_int16 = 2
    cf_int32 = 3
    cf_int64 = 4
    cf_float32 = 7
    cf_double64 = 8
    cf_undefined = 0
    proc_ALL = 1

    class ContinuousResolver:
        def __init__(self, pred=""):
            self._results = []
        def results(self):
            return list(self._results)

    class StreamInlet:
        def __init__(self, info, max_buflen=2, max_chunklen=0, processing_flags=0):
            self._info = info
        def pull_chunk(self, dest_obj=None, max_samples=None):
            return [], []
        def flush(self):
            return 0
        def close_stream(self):
            pass
        def info(self):
            return self._info


# Inject mock pylsl before any lsl.py import if the real one is missing
try:
    import pylsl  # noqa: F401
except ImportError:
    sys.modules['pylsl'] = _MockPylsl  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stream_info(n_chans=4, srate=256.0, cf_value=7):
    """Return a mock that behaves like pylsl.StreamInfo."""
    mock_info = MagicMock()
    mock_info.channel_count.return_value = n_chans
    mock_info.nominal_srate.return_value = srate
    mock_info.channel_format.return_value = cf_value
    mock_info.name.return_value = "MockEEG"

    # Build channel-label XML chain
    ch_nodes = []
    for idx in range(n_chans):
        node = MagicMock()
        node.child_value.side_effect = lambda key, _i=idx: f"CH{_i}" if key == "label" else ""
        ch_nodes.append(node)
    for i in range(n_chans - 1):
        ch_nodes[i].next_sibling.return_value = ch_nodes[i + 1]
    sentinel = MagicMock()
    sentinel.child_value.return_value = ""
    ch_nodes[-1].next_sibling.return_value = sentinel

    channels_node = MagicMock()
    channels_node.child.return_value = ch_nodes[0]
    desc_node = MagicMock()
    desc_node.child.return_value = channels_node
    mock_info.desc.return_value = desc_node
    return mock_info


def _ensure_qt_app():
    """Create a QCoreApplication (headless-safe) if none exists."""
    try:
        from qtpy import QtCore
        if QtCore.QCoreApplication.instance() is None:
            QtCore.QCoreApplication(sys.argv[:1])
    except Exception:
        pass


def _get_lsl_classes():
    from pypho_timeline.rendering.datasources.specific.lsl import (
        LSLStreamReceiver,
        LiveEEGTrackDatasource,
    )
    return LSLStreamReceiver, LiveEEGTrackDatasource


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReadChannelNames(unittest.TestCase):
    """Static helper: parse channel labels from stream XML description."""

    @classmethod
    def setUpClass(cls):
        _ensure_qt_app()
        cls.LSLStreamReceiver, _ = _get_lsl_classes()

    def test_labels_extracted(self):
        info = _make_stream_info(n_chans=4)
        names = self.LSLStreamReceiver._read_channel_names(info, 4)
        self.assertEqual(names, ["CH0", "CH1", "CH2", "CH3"])

    def test_fallback_to_index_when_no_label(self):
        info = _make_stream_info(n_chans=2)
        # Patch child_value to always return empty label
        ch_nodes = []
        for i in range(2):
            node = MagicMock()
            node.child_value.return_value = ""
            ch_nodes.append(node)
        ch_nodes[0].next_sibling.return_value = ch_nodes[1]
        sentinel = MagicMock()
        sentinel.child_value.return_value = ""
        ch_nodes[1].next_sibling.return_value = sentinel
        channels_node = MagicMock()
        channels_node.child.return_value = ch_nodes[0]
        desc_node = MagicMock()
        desc_node.child.return_value = channels_node
        info.desc.return_value = desc_node
        names = self.LSLStreamReceiver._read_channel_names(info, 2)
        self.assertEqual(names, ["0", "1"])


class TestLSLStreamReceiverLifecycle(unittest.TestCase):
    """Basic lifecycle and property tests for LSLStreamReceiver."""

    @classmethod
    def setUpClass(cls):
        _ensure_qt_app()
        cls.LSLStreamReceiver, _ = _get_lsl_classes()

    def test_initial_state(self):
        r = self.LSLStreamReceiver(stream_type="EEG")
        self.assertFalse(r.is_connected)
        self.assertEqual(r.channel_names, [])
        self.assertIsNone(r.stream_info)

    def test_stop_before_start_is_safe(self):
        r = self.LSLStreamReceiver(stream_type="EEG")
        r.stop()  # must not raise

    def test_custom_name_accepted(self):
        r = self.LSLStreamReceiver(stream_type="EEG", stream_name="Muse")
        self.assertFalse(r.is_connected)

    def test_create_inlet_sets_connected(self):
        r = self.LSLStreamReceiver(stream_type="EEG")
        info = _make_stream_info(n_chans=4)
        pylsl_mod = sys.modules.get('pylsl', _MockPylsl)
        with patch.object(pylsl_mod, 'StreamInlet', _MockPylsl.StreamInlet):
            r._create_inlet(info)
        self.assertTrue(r.is_connected)
        self.assertEqual(r._channel_names, ["CH0", "CH1", "CH2", "CH3"])


class TestLiveEEGTrackDatasourceBuffer(unittest.TestCase):
    """Rolling-buffer logic in LiveEEGTrackDatasource."""

    @classmethod
    def setUpClass(cls):
        _ensure_qt_app()
        _, cls.LiveEEGTrackDatasource = _get_lsl_classes()

    def _make_ds(self, window_s=5.0):
        ds = self.LiveEEGTrackDatasource(
            stream_type="EEG",
            window_duration_s=window_s,
        )
        ds._channel_names = ["CH0", "CH1", "CH2", "CH3"]
        ds._receiver._channel_names = ["CH0", "CH1", "CH2", "CH3"]
        return ds

    # -- initial state -------------------------------------------------------

    def test_initial_detailed_df_empty(self):
        ds = self._make_ds()
        self.assertEqual(len(ds.detailed_df), 0)

    # -- data ingestion ------------------------------------------------------

    def test_data_received_populates_df(self):
        ds = self._make_ds(window_s=10.0)
        n_chans, n_samples = 4, 100
        t0 = 1_700_000_000.0
        ts = t0 + np.arange(n_samples) / 256.0
        data = np.random.randn(n_chans, n_samples).astype(np.float32)
        ds._on_data_received(ts, data)

        self.assertIn("t", ds.detailed_df.columns)
        for ch in ["CH0", "CH1", "CH2", "CH3"]:
            self.assertIn(ch, ds.detailed_df.columns)
        self.assertEqual(len(ds.detailed_df), n_samples)

    def test_rolling_window_trims_old_samples(self):
        window_s = 2.0
        ds = self._make_ds(window_s=window_s)
        srate, n_chans = 256.0, 4
        t0 = 1_700_000_000.0

        # Inject 5 s then 1 more second
        for offset, dur in [(0.0, 5.0), (5.0, 1.0)]:
            n = int(dur * srate)
            ts = t0 + offset + np.arange(n) / srate
            d = np.ones((n_chans, n), dtype=np.float32)
            ds._on_data_received(ts, d)

        t_span = ds.detailed_df["t"].max() - ds.detailed_df["t"].min()
        self.assertAlmostEqual(t_span, window_s, delta=1.0 / srate + 0.01)

    def test_intervals_df_updated(self):
        ds = self._make_ds(window_s=5.0)
        t0 = 1_700_000_000.0
        ts = t0 + np.arange(50) / 100.0
        ds._on_data_received(ts, np.zeros((4, 50), dtype=np.float32))
        self.assertEqual(len(ds.intervals_df), 1)
        self.assertAlmostEqual(ds.intervals_df["t_start"].iloc[0], t0, places=3)

    def test_total_df_start_end_times(self):
        ds = self._make_ds(window_s=10.0)
        t0 = 1_700_000_000.0
        ts = t0 + np.arange(20) / 10.0
        ds._on_data_received(ts, np.zeros((4, 20), dtype=np.float32))
        start, end = ds.total_df_start_end_times
        self.assertAlmostEqual(start, t0, places=3)
        self.assertAlmostEqual(end, ts[-1], places=3)

    # -- fetch detail --------------------------------------------------------

    def test_fetch_detailed_data_filters_by_interval(self):
        ds = self._make_ds(window_s=10.0)
        t0, srate = 1_700_000_000.0, 100.0
        ts = t0 + np.arange(200) / srate
        ds._on_data_received(ts, np.random.randn(4, 200).astype(np.float32))

        interval = pd.Series({"t_start": t0, "t_duration": 0.5})
        result = ds.fetch_detailed_data(interval)
        self.assertGreater(len(result), 0)
        self.assertLessEqual(result["t"].max(), t0 + 0.5 + 1e-9)

    # -- signals -------------------------------------------------------------

    def test_source_data_changed_signal_emitted(self):
        ds = self._make_ds()
        fired = []
        ds.source_data_changed_signal.connect(lambda: fired.append(1))
        ds._on_data_received(
            np.array([1_700_000_000.0]),
            np.zeros((4, 1), dtype=np.float32),
        )
        self.assertEqual(len(fired), 1)

    # -- thread safety -------------------------------------------------------

    def test_thread_safety_concurrent_read_write(self):
        """fetch_detailed_data (reader thread) during _on_data_received (main thread)."""
        ds = self._make_ds(window_s=5.0)
        t0, srate, n_chans = 1_700_000_000.0, 256.0, 4
        errors = []

        def _writer():
            for i in range(20):
                n = 50
                ts = t0 + i * n / srate + np.arange(n) / srate
                ds._on_data_received(ts, np.random.randn(n_chans, n).astype(np.float32))
                time.sleep(0.001)

        def _reader():
            iv = pd.Series({"t_start": t0, "t_duration": 1.0})
            for _ in range(50):
                try:
                    ds.fetch_detailed_data(iv)
                except Exception as exc:
                    errors.append(exc)
                time.sleep(0.0005)

        w = threading.Thread(target=_writer)
        r = threading.Thread(target=_reader)
        r.start(); w.start()
        w.join(timeout=5); r.join(timeout=5)
        self.assertEqual(errors, [], f"Concurrency errors: {errors}")


if __name__ == "__main__":
    unittest.main()
