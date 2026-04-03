"""Tests for runtime downsampling updates on interval-backed datasources."""

import sys
import unittest
from collections import OrderedDict
from unittest.mock import patch

import pandas as pd


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
        _app = QApplication.instance() or QApplication(sys.argv[:1])
        return _app is not None
    except Exception:
        return False


@unittest.skipUnless(_have_qt_app(), "qtpy / Qt application not available")
class TestRuntimeDownsamplingUpdates(unittest.TestCase):
    def setUp(self):
        from pypho_timeline.rendering.async_detail_fetcher import AsyncDetailFetcher
        from pypho_timeline.rendering.datasources.track_datasource import IntervalProvidingTrackDatasource

        self._fetcher_cls = AsyncDetailFetcher
        self._datasource_cls = IntervalProvidingTrackDatasource

    def _make_datasource(self):
        intervals_df = pd.DataFrame({"t_start": [1_700_000_000.0], "t_duration": [1.0]})
        detailed_df = pd.DataFrame({"t": pd.to_datetime(["2024-01-01T00:00:00Z"])})
        return self._datasource_cls(intervals_df=intervals_df, detailed_df=detailed_df, custom_datasource_name="EEG_Test", max_points_per_second=10.0, enable_downsampling=True)

    def test_set_downsampling_updates_values_and_emits_signal(self):
        ds = self._make_datasource()
        fired = []

        ds.source_data_changed_signal.connect(lambda: fired.append(1))
        did_change = ds.set_downsampling(max_points_per_second=50.0)

        self.assertTrue(did_change)
        self.assertEqual(ds.max_points_per_second, 50.0)
        self.assertTrue(ds.enable_downsampling)
        self.assertEqual(len(fired), 1)

    def test_set_downsampling_supports_disabling_without_signal_when_unchanged(self):
        ds = self._make_datasource()
        fired = []

        ds.source_data_changed_signal.connect(lambda: fired.append(1))
        ds.set_downsampling(enable_downsampling=False, max_points_per_second=None)
        did_change = ds.set_downsampling(enable_downsampling=False, max_points_per_second=None)

        self.assertFalse(did_change)
        self.assertIsNone(ds.max_points_per_second)
        self.assertFalse(ds.enable_downsampling)
        self.assertEqual(len(fired), 1)

    def test_clear_cache_matches_runtime_cache_prefixes(self):
        class _FakeThreadPool:
            def __init__(self):
                self._max_thread_count = 4

            def maxThreadCount(self):
                return self._max_thread_count

            def setMaxThreadCount(self, count):
                self._max_thread_count = count

        with patch("pypho_timeline.rendering.async_detail_fetcher.QtCore.QThreadPool.globalInstance", return_value=_FakeThreadPool()):
            fetcher = self._fetcher_cls(max_cache_size=4)
        fetcher._cache = OrderedDict(
            [
                ("EEG_Test_1.0_1.0", object()),
                ("EEG_Test:legacy", object()),
                ("OtherTrack_1.0_1.0", object()),
            ]
        )

        fetcher.clear_cache("EEG_Test")

        self.assertNotIn("EEG_Test_1.0_1.0", fetcher._cache)
        self.assertNotIn("EEG_Test:legacy", fetcher._cache)
        self.assertIn("OtherTrack_1.0_1.0", fetcher._cache)
