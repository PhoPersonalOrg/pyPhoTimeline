"""Timeline detail view: stacked GFP traces per standard EEG band (shared math with stream_viewer LinePowerVis)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import pyqtgraph as pg

from phopymnehelper.analysis.computations.gfp_band_power import BAND_COLORS_RGB, STANDARD_EEG_FREQUENCY_BANDS, bandpass_filter_channels, baseline_rescale, bootstrap_gfp_ci, dataframe_to_channel_matrix, estimate_sample_rate_from_t, global_field_power
from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp


LANE_HEIGHT = 1.0
LANE_GAP = 0.15

_DEFAULT_EEG_CHANNELS = ['AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4']

_MAX_GFP_RESAMPLE_POINTS = 300_000


def _resample_channels_uniform_grid(t_vec: np.ndarray, data_mat: np.ndarray, nominal_srate: float, max_points: int = _MAX_GFP_RESAMPLE_POINTS) -> Tuple[np.ndarray, np.ndarray, float]:
    """Linearly interpolate multi-channel data onto a uniform time grid at ~nominal_srate (capped for long windows).

    Timeline ``detailed_df`` is often downsampled for display; band-pass GFP needs a rate high enough
    that Nyquist exceeds gamma. Returns ``(t_uniform, data_out, effective_srate)``.
    """
    t0, t1 = float(t_vec[0]), float(t_vec[-1])
    if t1 <= t0 or not np.isfinite(nominal_srate) or nominal_srate <= 0:
        return t_vec, data_mat, float(estimate_sample_rate_from_t(t_vec))
    n_target = max(2, int(np.ceil((t1 - t0) * nominal_srate)) + 1)
    n_new = max(2, min(n_target, max_points))
    t_uniform = np.linspace(t0, t1, n_new, dtype=float)
    srate_eff = float(nominal_srate) if n_target <= max_points else float(n_new - 1) / (t1 - t0)
    t_src = t_vec.astype(float, copy=False)
    out = np.empty((data_mat.shape[0], n_new), dtype=float)
    for ch_ix in range(data_mat.shape[0]):
        row = np.asarray(data_mat[ch_ix, :], dtype=float)
        finite = np.isfinite(row)
        if not np.any(finite):
            out[ch_ix, :] = 0.0
            continue
        if np.all(finite):
            out[ch_ix, :] = np.interp(t_uniform, t_src, row, left=float(row[0]), right=float(row[-1]))
        else:
            ts, ys = t_src[finite], row[finite]
            out[ch_ix, :] = np.interp(t_uniform, ts, ys, left=float(ys[0]), right=float(ys[-1]))
    return t_uniform, out, srate_eff


class LinePowerGFPDetailRenderer:
    """Renders band-limited Global Field Power in horizontal lanes (Theta→Gamma).

    Expects ``detail_data`` as a DataFrame with column ``t`` (seconds or unix) and EEG channel columns.
    Filtering, GFP, baseline, and optional bootstrap CI use :mod:`phopymnehelper.analysis.computations.gfp_band_power`.

    Set ``live_mode=True`` for real-time tracks: disables bootstrap CI for performance.
    """

    def __init__(self, channel_names: Optional[Sequence[str]] = None, filter_order: int = 4, n_bootstrap: int = 100, baseline_start: Optional[float] = None, baseline_end: Optional[float] = 0.0, show_confidence: bool = False, line_width: float = 0.5, live_mode: bool = False, nominal_srate: Optional[float] = None, **kwargs):
        _ = kwargs
        self.channel_names = list(channel_names) if channel_names else list(_DEFAULT_EEG_CHANNELS)
        self._filter_order = int(filter_order)
        self._n_bootstrap = max(10, int(n_bootstrap))
        self._baseline_start = baseline_start
        self._baseline_end = baseline_end
        self._line_width = float(line_width)
        self._live_mode = bool(live_mode)
        self._show_confidence = False if self._live_mode else bool(show_confidence)
        self._nominal_srate: Optional[float] = float(nominal_srate) if nominal_srate is not None and nominal_srate > 0 else None
        self._filter_cache: dict = {}
        self._last_srate: Optional[float] = None



    def render_detail(self, plot_item: pg.PlotItem, interval: pd.DataFrame, detail_data: Any) -> List[pg.GraphicsObject]:
        graphics_objects: List[pg.GraphicsObject] = []
        if detail_data is None or not isinstance(detail_data, pd.DataFrame) or len(detail_data) == 0:
            return graphics_objects
        if 't' not in detail_data.columns:
            return graphics_objects
        df = detail_data.sort_values('t').reset_index(drop=True)
        ch_found = [c for c in self.channel_names if c in df.columns]
        if not ch_found:
            return graphics_objects
        data_mat, t_vec = dataframe_to_channel_matrix(df, ch_found)
        if data_mat.size == 0 or t_vec.size < 2:
            return graphics_objects
        if interval is not None and len(interval) > 0 and 't_start' in interval.columns:
            row = interval.iloc[0]
            raw_start = row['t_start']
            t_dur = float(row.get('t_duration', 0.0) or 0.0)
            if isinstance(raw_start, (datetime, pd.Timestamp)):
                t_lo = float(datetime_to_unix_timestamp(raw_start))
            else:
                t_lo = float(raw_start)
            t_hi = t_lo + t_dur if t_dur > 0 else float(np.max(t_vec))
            m = (t_vec >= t_lo) & (t_vec <= t_hi)
            if np.any(m):
                t_vec = t_vec[m]
                data_mat = data_mat[:, m]
        if t_vec.size < 2:
            return graphics_objects
        if self._nominal_srate is not None:
            t_vec, data_mat, srate = _resample_channels_uniform_grid(t_vec, data_mat, self._nominal_srate)
        else:
            srate = estimate_sample_rate_from_t(t_vec)
        if self._last_srate != srate:
            self._filter_cache = {}
            self._last_srate = float(srate)
        nyq = srate / 2.0
        n_lanes = 0
        for band_idx, (band_name, fmin, fmax) in enumerate(STANDARD_EEG_FREQUENCY_BANDS):
            if fmin >= nyq:
                continue
            y0 = float(n_lanes * (LANE_HEIGHT + LANE_GAP))
            n_lanes += 1
            filtered_data = bandpass_filter_channels(data_mat, fmin, fmax, srate, self._filter_order, self._filter_cache)
            gfp = global_field_power(filtered_data)
            gfp = baseline_rescale(gfp, t_vec, self._baseline_start, self._baseline_end)
            color = BAND_COLORS_RGB[band_idx]
            pen = pg.mkPen(color=color, width=self._line_width)
            if self._show_confidence:
                ci_lo_raw, ci_hi_raw = bootstrap_gfp_ci(filtered_data, self._n_bootstrap)
                ci_lo = baseline_rescale(ci_lo_raw, t_vec, self._baseline_start, self._baseline_end)
                ci_hi = baseline_rescale(ci_hi_raw, t_vec, self._baseline_start, self._baseline_end)
                curve_lo = gfp - ci_lo
                curve_hi = gfp + ci_hi
                stack = np.concatenate([gfp, curve_lo, curve_hi])
            else:
                stack = gfp
            gmin = float(np.nanmin(stack))
            gmax = float(np.nanmax(stack))
            span = (gmax - gmin) if (gmax > gmin) else 1.0

            def to_lane(y: np.ndarray) -> np.ndarray:
                return y0 + (y - gmin) / span * 0.9 * LANE_HEIGHT

            y_main = to_lane(gfp)
            curve = pg.PlotCurveItem(t_vec, y_main, pen=pen, connect='finite', name=f'{band_name} GFP')
            plot_item.addItem(curve)
            graphics_objects.append(curve)
            if self._show_confidence:
                y_lo = to_lane(curve_lo)
                y_hi = to_lane(curve_hi)
                pci = pg.mkPen((*color, 80), width=0)
                cu = pg.PlotCurveItem(t_vec, y_hi, pen=pci)
                cl = pg.PlotCurveItem(t_vec, y_lo, pen=pci)
                fb = pg.FillBetweenItem(cl, cu, brush=pg.mkBrush(color=(*color, 50)))
                plot_item.addItem(cl)
                plot_item.addItem(cu)
                plot_item.addItem(fb)
                graphics_objects.extend([cl, cu, fb])
        if n_lanes > 0:
            y_top = n_lanes * (LANE_HEIGHT + LANE_GAP)
            plot_item.setYRange(0, y_top, padding=0.02)
        return graphics_objects



    def clear_detail(self, plot_item: pg.PlotItem, graphics_objects: List[pg.GraphicsObject]) -> None:
        if not graphics_objects:
            return
        for obj in graphics_objects:
            if obj is None:
                continue
            try:
                plot_item.removeItem(obj)
                if hasattr(obj, 'setParentItem'):
                    obj.setParentItem(None)
            except (AttributeError, RuntimeError):
                pass



    def get_detail_bounds(self, interval: pd.DataFrame, detail_data: Any) -> Tuple[float, float, float, float]:
        t_start: float
        t_end: float
        if detail_data is not None and isinstance(detail_data, pd.DataFrame) and len(detail_data) > 0 and 't' in detail_data.columns:
            t_min = detail_data['t'].min()
            t_max = detail_data['t'].max()
            if isinstance(t_min, (datetime, pd.Timestamp)):
                t_start = float(datetime_to_unix_timestamp(t_min))
                t_end = float(datetime_to_unix_timestamp(t_max))
            else:
                t_start = float(t_min)
                t_end = float(t_max)
        elif interval is not None and len(interval) > 0 and 't_start' in interval.columns:
            row = interval.iloc[0]
            raw_start = row['t_start']
            t_dur = float(row.get('t_duration', 1.0) or 1.0)
            if isinstance(raw_start, (datetime, pd.Timestamp)):
                t_start = float(datetime_to_unix_timestamp(raw_start))
                t_end = t_start + t_dur
            else:
                t_start = float(raw_start)
                t_end = t_start + t_dur
        else:
            t_start, t_end = 0.0, 1.0
        nb = len(STANDARD_EEG_FREQUENCY_BANDS)
        y_max = float(nb * (LANE_HEIGHT + LANE_GAP))
        return (t_start, t_end, 0.0, y_max)
