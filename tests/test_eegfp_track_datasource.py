"""Tests for EEGFPTrackDatasource (historical GFP band track).

Loads ``eeg.py`` in isolation (same pattern as ``test_multi_raw_eeg_datasource``) to avoid
importing ``specific/__init__.py`` (which pulls optional NeuroPy-dependent stacks).
"""

import importlib.util
import sys
import types
import unittest
from enum import Enum
from pathlib import Path

import numpy as np
import pandas as pd


def _have_qt_app() -> bool:
    try:
        from qtpy.QtWidgets import QApplication
        import sys as _sys
        app = QApplication.instance() or QApplication(_sys.argv[:1])
        return app is not None
    except Exception:
        return False


def _load_eeg_module_with_gfp_stub():
    generic_plot_renderer_module = types.ModuleType("pypho_timeline.rendering.detail_renderers.generic_plot_renderer")
    generic_plot_renderer_module.GenericPlotDetailRenderer = type("GenericPlotDetailRenderer", (), {})
    generic_plot_renderer_module.IntervalPlotDetailRenderer = type("IntervalPlotDetailRenderer", (), {})
    generic_plot_renderer_module.DataframePlotDetailRenderer = type("DataframePlotDetailRenderer", (), {})
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
    spec = importlib.util.spec_from_file_location("test_eegfp_isolated_eeg_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(_have_qt_app(), "Qt application not available")
class TestEEGFPTrackDatasource(unittest.TestCase):

    def test_get_detail_renderer_is_line_power_gfp_live_mode_off(self) -> None:
        mod = _load_eeg_module_with_gfp_stub()
        EEGFPTrackDatasource = mod.EEGFPTrackDatasource
        LinePowerGFPDetailRenderer = mod.LinePowerGFPDetailRenderer

        intervals_df = pd.DataFrame({"t_start": [0.0], "t_duration": [1.0]})
        t = np.linspace(0.0, 1.0, 64, endpoint=False)
        eeg_df = pd.DataFrame({"t": t, "AF3": np.sin(2 * np.pi * 10 * t), "F7": np.cos(2 * np.pi * 10 * t)})
        ds = EEGFPTrackDatasource(intervals_df=intervals_df, eeg_df=eeg_df, custom_datasource_name="EEG_Test_GFP", enable_downsampling=False, channel_names=["AF3", "F7"])
        r = ds.get_detail_renderer()
        self.assertIsInstance(r, LinePowerGFPDetailRenderer)
        self.assertFalse(r._live_mode)
        self.assertEqual(r.channel_names, ["AF3", "F7"])
        self.assertEqual(r._filter_order, 4)



if __name__ == "__main__":
    unittest.main()
