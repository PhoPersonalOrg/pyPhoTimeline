"""Tests for multi-session EEG datasource behavior."""

import importlib.util
import sys
import types
import unittest
from enum import Enum
from pathlib import Path
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


class _FakeRaw:
    def __init__(self, label: str, start: str):
        self.label = label
        self.info = {"meas_date": pd.Timestamp(start, tz="UTC")}


def _load_eeg_module():
    generic_plot_renderer_module = types.ModuleType("pypho_timeline.rendering.detail_renderers.generic_plot_renderer")
    generic_plot_renderer_module.GenericPlotDetailRenderer = type("GenericPlotDetailRenderer", (), {})
    helpers_module = types.ModuleType("pypho_timeline.rendering.helpers")

    class _ChannelNormalizationMode(Enum):
        GROUPMINMAXRANGE = "group"
        INDIVIDUAL = "individual"
        NONE = "none"

    class _ChannelNormalizationModeNormalizingMixin:
        def __init__(self, *args, **kwargs):
            pass

    helpers_module.ChannelNormalizationMode = _ChannelNormalizationMode
    helpers_module.ChannelNormalizationModeNormalizingMixin = _ChannelNormalizationModeNormalizingMixin
    sys.modules[generic_plot_renderer_module.__name__] = generic_plot_renderer_module
    sys.modules[helpers_module.__name__] = helpers_module
    module_path = Path(__file__).resolve().parents[1] / "pypho_timeline" / "rendering" / "datasources" / "specific" / "eeg.py"
    spec = importlib.util.spec_from_file_location("test_multi_raw_eeg_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(_have_qt_app(), "qtpy / Qt application not available")
class TestMultiRawEEGDatasource(unittest.TestCase):
    def test_mask_bad_eeg_channels_by_interval_rows_masks_only_matching_session_rows(self):
        EEGTrackDatasource = _load_eeg_module().EEGTrackDatasource

        intervals_df = pd.DataFrame({"t_start": [0.0, 10.0], "t_duration": [10.0, 10.0], "t_end": [10.0, 20.0]})
        eeg_df = pd.DataFrame({"t": [0.0, 5.0, 10.0, 15.0], "AF3": [1.0, 2.0, 3.0, 4.0], "F7": [10.0, 20.0, 30.0, 40.0]})
        ds = EEGTrackDatasource(intervals_df=intervals_df, eeg_df=eeg_df, custom_datasource_name="EEG_Test", enable_downsampling=False, channel_names=["AF3", "F7"])

        ds.mask_bad_eeg_channels_by_interval_rows([["AF3"], ["F7"]], ds.intervals_df)

        self.assertTrue(ds.detailed_df.loc[ds.detailed_df["t"] < 10.0, "AF3"].isna().all())
        self.assertEqual(ds.detailed_df.loc[ds.detailed_df["t"] < 10.0, "F7"].tolist(), [10.0, 20.0])
        self.assertEqual(ds.detailed_df.loc[ds.detailed_df["t"] >= 10.0, "AF3"].tolist(), [3.0, 4.0])
        self.assertTrue(ds.detailed_df.loc[ds.detailed_df["t"] >= 10.0, "F7"].isna().all())
        self.assertEqual(ds.channel_names, ["AF3", "F7"])

    def test_compute_multiraw_spectrogram_results_uses_all_sorted_raws_and_pads_unmatched_intervals(self):
        compute_multiraw_spectrogram_results = _load_eeg_module().compute_multiraw_spectrogram_results

        intervals_df = pd.DataFrame({"t_start": [0.0, 10.0, 20.0], "t_duration": [10.0, 10.0, 10.0]})
        raw_datasets_dict = {"later": [_FakeRaw("later", "2024-01-02T00:00:00Z")], "earlier": [_FakeRaw("earlier", "2024-01-01T00:00:00Z")]}

        with patch("phopymnehelper.analysis.computations.eeg_registry.run_eeg_computations_graph", side_effect=lambda raw, session, goals: {"spectogram": {"ch_names": [raw.label]}}), patch("phopymnehelper.analysis.computations.eeg_registry.session_fingerprint_for_raw_or_path", side_effect=lambda raw: raw.label):
            results = compute_multiraw_spectrogram_results(intervals_df, raw_datasets_dict)

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["ch_names"], ["earlier"])
        self.assertEqual(results[1]["ch_names"], ["later"])
        self.assertIsNone(results[2])

    def test_spectrogram_datasource_uses_union_of_channel_names_and_no_first_result_fallback(self):
        EEGSpectrogramTrackDatasource = _load_eeg_module().EEGSpectrogramTrackDatasource

        intervals_df = pd.DataFrame({"t_start": [0.0, 10.0], "t_duration": [10.0, 10.0], "t_end": [10.0, 20.0]})
        ds = EEGSpectrogramTrackDatasource(intervals_df=intervals_df, spectrogram_results=[{"ch_names": ["F7"]}, {"ch_names": ["AF3"]}], custom_datasource_name="EEG_Spec_Test")

        self.assertEqual(ds.get_spectrogram_ch_names(), ["AF3", "F7"])
        self.assertIsNone(ds.fetch_detailed_data(pd.Series({"t_start": 999.0, "t_duration": 1.0})))

