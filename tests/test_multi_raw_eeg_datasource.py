"""Tests for multi-session EEG datasource behavior."""

import importlib.util
import sys
import types
import unittest
from enum import Enum
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    def test_add_spectrogram_tracks_for_channel_groups_builds_named_children_and_calls_update_timeline(self):
        mod = _load_eeg_module()
        EEGTrackDatasource = mod.EEGTrackDatasource
        SpectrogramChannelGroupConfig = mod.SpectrogramChannelGroupConfig

        intervals_df = pd.DataFrame({"t_start": [0.0], "t_duration": [10.0]})
        eeg_df = pd.DataFrame({"t": [0.0, 5.0], "AF3": [1.0, 2.0]})
        ds = EEGTrackDatasource(intervals_df=intervals_df, eeg_df=eeg_df, custom_datasource_name="EEG_MyStream", enable_downsampling=False, channel_names=["AF3"])
        ds.raw_datasets_dict = {"a": [object()]}

        captured = []

        class _TB:
            def update_timeline(self, timeline, datasources, update_time_range=True):
                captured.append((timeline, list(datasources), update_time_range))

        class _TL:
            track_datasources = {}

        tl = _TL()
        tb = _TB()
        spec_results = [{"ch_names": ["AF3"], "freqs": [1.0], "t": [0.0], "Sxx": __import__("numpy").array([[[1.0]]])}]

        with patch.object(mod, "compute_multiraw_spectrogram_results", return_value=spec_results):
            out = ds.add_spectrogram_tracks_for_channel_groups([SpectrogramChannelGroupConfig(name="G1", channels=["AF3"])], tl, tb, update_time_range=False, skip_existing_names=True)

        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].custom_datasource_name, "EEG_Spectrogram_MyStream_G1")
        self.assertEqual(out[0].group_config.name, "G1")
        self.assertEqual(out[0].group_config.channels, ["AF3"])
        self.assertEqual(len(captured), 1)
        self.assertIs(captured[0][0], tl)
        self.assertEqual(captured[0][1], out)
        self.assertFalse(captured[0][2])
        self.assertIs(ds._spectrogram_child_datasources[-1], out[0])

    def test_add_spectrogram_tracks_for_channel_groups_none_groups_single_track_and_skips_existing(self):
        mod = _load_eeg_module()
        EEGTrackDatasource = mod.EEGTrackDatasource

        intervals_df = pd.DataFrame({"t_start": [0.0], "t_duration": [10.0]})
        eeg_df = pd.DataFrame({"t": [0.0], "AF3": [1.0]})
        ds = EEGTrackDatasource(intervals_df=intervals_df, eeg_df=eeg_df, custom_datasource_name="EEG_X", enable_downsampling=False, channel_names=["AF3"])
        ds.raw_datasets_dict = {"a": [object()]}

        class _TB:
            def __init__(self):
                self.calls = 0

            def update_timeline(self, timeline, datasources, update_time_range=True):
                self.calls += 1

        class _TL:
            def __init__(self):
                self.track_datasources = {}

        tl = _TL()
        tb = _TB()
        spec_results = [{"ch_names": ["AF3"]}]

        with patch.object(mod, "compute_multiraw_spectrogram_results", return_value=spec_results):
            out1 = ds.add_spectrogram_tracks_for_channel_groups(None, tl, tb, update_time_range=True, skip_existing_names=True)
            tl.track_datasources["EEG_Spectrogram_X"] = MagicMock()
            out2 = ds.add_spectrogram_tracks_for_channel_groups(None, tl, tb, skip_existing_names=True)

        self.assertEqual(len(out1), 1)
        self.assertEqual(out1[0].custom_datasource_name, "EEG_Spectrogram_X")
        self.assertIsNone(out1[0].group_config)
        self.assertEqual(tb.calls, 1)
        self.assertEqual(out2, [])

