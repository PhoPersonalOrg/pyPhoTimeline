"""Tests for pypho_timeline.rendering.datasources.specific.lsl.

These tests exercise the pure data-structure logic of the LSL module without
requiring real LSL hardware or a running Qt application.  Qt-dependent tests
are skipped unless a QApplication can be created.
"""

import time
import unittest
from datetime import datetime, timezone

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers to decide whether heavy deps are available
# ---------------------------------------------------------------------------

def _have_qt() -> bool:
    try:
        from qtpy import QtCore  # noqa: F401
        return True
    except Exception:
        return False


def _have_qt_app() -> bool:
    if not _have_qt():
        return False
    try:
        from qtpy.QtWidgets import QApplication  # noqa: F401
        import sys
        _app = QApplication.instance() or QApplication(sys.argv[:1])
        return _app is not None
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Tests for _make_stub_intervals_df (pandas-only, no Qt)
# ---------------------------------------------------------------------------

class TestMakeStubIntervalsDF(unittest.TestCase):
    """Verify _make_stub_intervals_df builds a valid single-row DataFrame."""

    def setUp(self):
        try:
            from pypho_timeline.rendering.datasources.specific.lsl import (
                _make_stub_intervals_df,
            )
            self._fn = _make_stub_intervals_df
        except ImportError as exc:
            self.skipTest(f"lsl module not importable: {exc}")

    def test_single_arg_creates_row(self):
        """Single t_start → row with t_duration >= 1."""
        df = self._fn(1000.0)
        self.assertEqual(len(df), 1)
        self.assertIn("t_start", df.columns)
        self.assertIn("t_duration", df.columns)
        self.assertIn("t_end", df.columns)
        self.assertGreaterEqual(float(df["t_duration"].iloc[0]), 1.0)

    def test_two_args_duration(self):
        """t_start and t_end → correct duration."""
        df = self._fn(1000.0, 1005.0)
        self.assertAlmostEqual(float(df["t_duration"].iloc[0]), 5.0, places=6)
        self.assertAlmostEqual(float(df["t_end"].iloc[0]), 1005.0, places=6)

    def test_same_start_end_clamps_to_one(self):
        """When t_start == t_end the duration is clamped to 1.0."""
        df = self._fn(1000.0, 1000.0)
        self.assertGreaterEqual(float(df["t_duration"].iloc[0]), 1.0)


# ---------------------------------------------------------------------------
# Tests for _LiveRingBuffer (Qt-dependent)
# ---------------------------------------------------------------------------

@unittest.skipUnless(_have_qt(), "qtpy / Qt not available")
class TestLiveRingBuffer(unittest.TestCase):
    """Verify _LiveRingBuffer accumulates and trims data correctly."""

    def setUp(self):
        try:
            from pypho_timeline.rendering.datasources.specific.lsl import (
                _LiveRingBuffer,
            )
            self._cls = _LiveRingBuffer
        except ImportError as exc:
            self.skipTest(f"lsl module not importable: {exc}")

    def _make_chunk(self, t_start: float, n: int, n_ch: int = 3):
        ts = np.linspace(t_start, t_start + n / 100.0, n, dtype=np.float64)
        samples = np.random.randn(n, n_ch).astype(np.float64)
        return ts, samples

    def test_empty_buffer_returns_empty_df(self):
        buf = self._cls(["A", "B", "C"], buffer_seconds=60.0)
        df = buf.to_dataframe()
        self.assertTrue(df.empty)
        self.assertIn("t", df.columns)

    def test_append_and_retrieve(self):
        buf = self._cls(["A", "B", "C"], buffer_seconds=60.0)
        ts, samp = self._make_chunk(1000.0, 50, 3)
        buf.append(ts, samp, ["A", "B", "C"])
        df = buf.to_dataframe()
        self.assertEqual(len(df), 50)
        self.assertListEqual(list(df.columns), ["t", "A", "B", "C"])

    def test_latest_timestamp(self):
        buf = self._cls(["A"], buffer_seconds=60.0)
        ts, samp = self._make_chunk(500.0, 10, 1)
        buf.append(ts, samp, ["A"])
        self.assertAlmostEqual(buf.latest_timestamp, ts[-1], places=9)

    def test_earliest_timestamp(self):
        buf = self._cls(["A"], buffer_seconds=60.0)
        ts, samp = self._make_chunk(500.0, 10, 1)
        buf.append(ts, samp, ["A"])
        self.assertAlmostEqual(buf.earliest_timestamp, ts[0], places=9)

    def test_trimming_removes_old_data(self):
        buf = self._cls(["A"], buffer_seconds=1.0)
        # First chunk: t = 0..0.5
        ts1, s1 = self._make_chunk(0.0, 50, 1)
        buf.append(ts1, s1, ["A"])
        # Second chunk: t = 2..2.5 (gap > 1 s → first chunk should be trimmed)
        ts2, s2 = self._make_chunk(2.0, 50, 1)
        buf.append(ts2, s2, ["A"])
        # The old chunk (ending at ~0.5) is older than (latest - 1.0) = ~1.5
        df = buf.to_dataframe()
        # All remaining timestamps should be >= 2.0 - 1.0 = 1.0
        self.assertTrue((df["t"] >= 1.0).all(), msg=f"Oldest t={df['t'].min():.3f}")

    def test_get_window(self):
        buf = self._cls(["X", "Y"], buffer_seconds=300.0)
        ts, samp = self._make_chunk(1000.0, 100, 2)
        buf.append(ts, samp, ["X", "Y"])
        window_df = buf.get_window(1000.0, 1000.5)
        # All timestamps should be within the requested window
        self.assertTrue((window_df["t"] >= 1000.0).all())
        self.assertTrue((window_df["t"] <= 1000.5).all())
        self.assertGreater(len(window_df), 0)

    def test_channel_rename_resets_buffer(self):
        buf = self._cls(["A", "B"], buffer_seconds=60.0)
        ts, samp = self._make_chunk(1000.0, 10, 2)
        buf.append(ts, samp, ["A", "B"])
        # Now send data with different channel names → buffer should reset
        ts2, samp2 = self._make_chunk(1010.0, 5, 2)
        buf.append(ts2, samp2, ["X", "Y"])
        df = buf.to_dataframe()
        # Only 5 samples in the new-named buffer
        self.assertEqual(len(df), 5)
        self.assertIn("X", df.columns)
        self.assertNotIn("A", df.columns)


# ---------------------------------------------------------------------------
# Tests for LSLStreamReceiver (Qt-dependent, no real LSL needed)
# ---------------------------------------------------------------------------

@unittest.skipUnless(_have_qt(), "qtpy / Qt not available")
class TestLSLStreamReceiverConstruction(unittest.TestCase):
    """Verify LSLStreamReceiver can be constructed and started without pylsl."""

    def setUp(self):
        try:
            from pypho_timeline.rendering.datasources.specific.lsl import (
                LSLStreamReceiver,
            )
            self._cls = LSLStreamReceiver
        except ImportError as exc:
            self.skipTest(f"lsl module not importable: {exc}")

    def test_default_construction(self):
        recv = self._cls()
        self.assertFalse(recv.is_connected)
        self.assertEqual(recv.channel_names, [])

    def test_type_filter_construction(self):
        recv = self._cls(stream_type="EEG")
        self.assertEqual(recv.stream_type, "EEG")

    def test_name_filter_construction(self):
        recv = self._cls(stream_name="MyStream")
        self.assertEqual(recv.stream_name, "MyStream")

    def test_start_without_pylsl_emits_warning(self):
        """start() must not raise even when pylsl is absent."""
        import warnings
        recv = self._cls()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            try:
                recv.start()
            except Exception as exc:
                self.fail(f"start() raised unexpectedly: {exc}")
        recv.stop()

    def test_stop_before_start_is_safe(self):
        recv = self._cls()
        try:
            recv.stop()
        except Exception as exc:
            self.fail(f"stop() before start raised: {exc}")


# ---------------------------------------------------------------------------
# Tests for LiveEEGTrackDatasource and LiveMotionTrackDatasource
# ---------------------------------------------------------------------------

@unittest.skipUnless(_have_qt(), "qtpy / Qt not available")
class TestLiveDatasourceConstruction(unittest.TestCase):
    """Verify live datasources can be constructed with a stub receiver."""

    def setUp(self):
        try:
            from pypho_timeline.rendering.datasources.specific.lsl import (
                LSLStreamReceiver,
                LiveEEGTrackDatasource,
                LiveMotionTrackDatasource,
            )
            self._recv_cls = LSLStreamReceiver
            self._eeg_cls = LiveEEGTrackDatasource
            self._motion_cls = LiveMotionTrackDatasource
        except ImportError as exc:
            self.skipTest(f"lsl module not importable: {exc}")

    def test_eeg_datasource_construction(self):
        recv = self._recv_cls(stream_type="EEG")
        ds = self._eeg_cls(receiver=recv, buffer_seconds=60.0,
                           custom_datasource_name="TestEEG")
        self.assertEqual(ds.custom_datasource_name, "TestEEG")
        self.assertIsNone(ds.live_timestamp)
        t0, t1 = ds.total_df_start_end_times
        # When empty, start == end ≈ now
        self.assertAlmostEqual(t0, t1, delta=2.0)

    def test_motion_datasource_construction(self):
        recv = self._recv_cls(stream_type="Accelerometer")
        ds = self._motion_cls(receiver=recv, buffer_seconds=60.0,
                              channel_names=["AccX", "AccY", "AccZ"],
                              custom_datasource_name="TestMotion")
        self.assertEqual(ds.custom_datasource_name, "TestMotion")
        self.assertIsNone(ds.live_timestamp)

    def test_eeg_get_full_buffer_df_empty(self):
        recv = self._recv_cls()
        ds = self._eeg_cls(receiver=recv, buffer_seconds=60.0)
        df = ds.get_full_buffer_df()
        self.assertTrue(df.empty)

    def test_eeg_ingest_samples_via_signal(self):
        """Simulate data arriving via data_received signal and check buffer."""
        recv = self._recv_cls()
        ch_names = ["AF3", "F7", "O1"]
        ds = self._eeg_cls(receiver=recv, buffer_seconds=60.0,
                           channel_names=ch_names)

        n = 50
        ts = np.linspace(1000.0, 1000.5, n, dtype=np.float64)
        samples = np.random.randn(n, len(ch_names)).astype(np.float64)

        # Emit signal directly (simulating what the timer slot does)
        recv.data_received.emit(ch_names, ts, samples)

        df = ds.get_full_buffer_df()
        self.assertEqual(len(df), n)
        self.assertIn("t", df.columns)
        for ch in ch_names:
            self.assertIn(ch, df.columns)

    def test_eeg_fetch_detailed_data_returns_window(self):
        recv = self._recv_cls()
        ch_names = ["AF3", "F7"]
        ds = self._eeg_cls(receiver=recv, buffer_seconds=60.0,
                           channel_names=ch_names)
        n = 100
        ts = np.linspace(1000.0, 1001.0, n, dtype=np.float64)
        samples = np.random.randn(n, 2).astype(np.float64)
        recv.data_received.emit(ch_names, ts, samples)

        interval = pd.Series({"t_start": 1000.0, "t_duration": 0.5,
                               "t_end": 1000.5, "t_start_dt": pd.Timestamp("2024-01-01"),
                               "t_end_dt": pd.Timestamp("2024-01-01")})
        result = ds.fetch_detailed_data(interval)
        self.assertFalse(result.empty)
        self.assertTrue((result["t"] >= 1000.0).all())
        self.assertTrue((result["t"] <= 1000.5).all())


if __name__ == "__main__":
    unittest.main()
