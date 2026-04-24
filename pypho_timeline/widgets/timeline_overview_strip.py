"""Stacked overview strip: interval preview per track; plot view is non-interactive, viewport region is draggable."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Callable, List, Optional, Tuple

import numpy as np
import pandas as pd
from qtpy import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

from pypho_timeline.rendering.graphics.interval_rects_item import IntervalRectsItem
from pypho_timeline.rendering.helpers.render_rectangles_helper import Render2DEventRectanglesHelper
from pypho_timeline.utils.datetime_helpers import create_am_pm_date_axis, datetime_to_unix_timestamp

from pypho_timeline.EXTERNAL.pyqtgraph_extensions.graphicsObjects.CustomLinearRegionItem import CustomLinearRegionItem
from pypho_timeline.EXTERNAL.pyqtgraph_extensions.mixins.DraggableGraphicsWidgetMixin import MouseInteractionCriteria

logger = logging.getLogger(__name__)


def _scalar_to_plot_x(t: Any) -> float:
    if isinstance(t, (datetime, pd.Timestamp)):
        return float(datetime_to_unix_timestamp(t))
    if isinstance(t, (np.floating, np.integer)):
        return float(t)
    return float(t)


def _duration_to_seconds(d: Any) -> float:
    if d is None or (isinstance(d, float) and np.isnan(d)):
        return 0.0
    if isinstance(d, (timedelta, pd.Timedelta)):
        return float(d.total_seconds())
    return float(d)


class TimelineOverviewStrip(pg.PlotWidget):
    """Minimap: one horizontal band per primary track (overview intervals only) and a user-adjustable ``CustomLinearRegionItem`` for the viewport.

    Interaction: left-drag the shaded band (or middle button with class defaults) to translate; left-drag the vertical edge handles to resize.

    ``sigViewportChanged(x0, x1)`` is emitted when the user **finishes** a drag or resize (commit). ``sigViewportLiveChanged(x0, x1)`` is emitted **during** dragging for scrubbing-style updates. Embedders such as ``SimpleTimelineWidget`` should connect only ``sigViewportChanged`` to the main window unless they intentionally want live coupling (to avoid ``set_viewport`` feedback every frame).

    The plot does not pan or zoom; plot x is Unix seconds when using the date axis."""

    sigViewportChanged = QtCore.Signal(float, float)
    sigViewportLiveChanged = QtCore.Signal(float, float)


    def __init__(self, reference_datetime: Optional[datetime] = None, row_height_px: int = 20, band_margin: float = 0.12, parent: Optional[QtWidgets.QWidget] = None):
        axis_bottom = create_am_pm_date_axis(orientation='bottom') if reference_datetime is not None else None
        super().__init__(parent=parent, axisItems={'bottom': axis_bottom} if axis_bottom is not None else {})
        self.reference_datetime = reference_datetime
        self._row_height_px = max(16, int(row_height_px))
        self._band_margin = float(band_margin)
        self._intervals_item: Optional[IntervalRectsItem] = None
        end_lines_crit = MouseInteractionCriteria(drag=lambda ev: ev.button() == QtCore.Qt.MouseButton.LeftButton, hover=lambda ev: ev.acceptDrags(QtCore.Qt.MouseButton.LeftButton), click=lambda ev: ev.button() == QtCore.Qt.MouseButton.RightButton)
        self._viewport_region = CustomLinearRegionItem(values=(0.0, 1.0), orientation='vertical', pen=pg.mkPen(color=(40, 90, 200), width=1), brush=QtGui.QColor(80, 140, 255, 70), hoverBrush=QtGui.QColor(80, 140, 255, 90), hoverPen=pg.mkPen('#f00'), clipItem=self.getPlotItem(), movable=True, removable=False, endLinesMouseInteractionCriteria=end_lines_crit)
        self._viewport_region.setObjectName('scroll_window_region')
        self._viewport_region.setZValue(120)
        self.addItem(self._viewport_region, ignoreBounds=True)
        self._viewport_region.sigRegionChanged.connect(lambda _r: self._read_clamp_emit_viewport(True))
        self._viewport_region.sigRegionChangeFinished.connect(lambda _r: self._read_clamp_emit_viewport(False))
        pi = self.getPlotItem()
        pi.setMenuEnabled(False)
        pi.hideButtons()
        pi.showGrid(x=True, y=True, alpha=0.35)
        vb = self.getViewBox()
        vb.setMouseEnabled(False, False)
        vb.enableAutoRange(axis='xy', enable=False)
        # vb.setAutoPan(x=False, y=False)
        self.setBackground('w')
        self.showAxis('left', True)


    def _read_clamp_emit_viewport(self, live: bool) -> None:
        r0, r1 = self._viewport_region.getRegion()
        x_lo, x_hi = (float(r0), float(r1)) if r0 <= r1 else (float(r1), float(r0))
        vb = self.getViewBox()
        try:
            xl = vb.state['limits']['xLimits']
            xmin_lim, xmax_lim = xl[0], xl[1]
        except (KeyError, TypeError, IndexError):
            xmin_lim, xmax_lim = None, None
        clamped = False
        if xmin_lim is not None and xmax_lim is not None and xmax_lim > xmin_lim:
            span = x_hi - x_lo
            if x_lo < xmin_lim:
                x_lo = float(xmin_lim)
                x_hi = x_lo + span
                clamped = True
            if x_hi > xmax_lim:
                x_hi = float(xmax_lim)
                x_lo = x_hi - span
                clamped = True
            if x_lo < xmin_lim:
                x_lo = float(xmin_lim)
                clamped = True
            if x_hi < x_lo:
                x_hi = x_lo + 1e-9
                clamped = True
            self._viewport_region.blockSignals(True)
            self._viewport_region.setRegion([x_lo, x_hi])
            self._viewport_region.blockSignals(False)
        mode = 'live' if live else 'committed'
        logger.debug("_read_clamp_emit_viewport: mode=%s getRegion=(%s,%s) limits=(%s,%s) clamped=%s emit [%s, %s]", mode, r0, r1, xmin_lim, xmax_lim, clamped, x_lo, x_hi)
        if live:
            self.sigViewportLiveChanged.emit(x_lo, x_hi)
        else:
            self.sigViewportChanged.emit(x_lo, x_hi)


    def set_viewport(self, x_start: float, x_end: float) -> None:
        """Set the viewport region from the main timeline (plot x). Does not emit ``sigViewportChanged`` or ``sigViewportLiveChanged`` (signals blocked during ``setRegion``)."""
        x0, x1 = (float(x_start), float(x_end)) if x_start <= x_end else (float(x_end), float(x_start))
        logger.debug("set_viewport: request [%s, %s] normalized [%s, %s] (signals blocked)", x_start, x_end, x0, x1)
        self._viewport_region.blockSignals(True)
        self._viewport_region.setRegion([x0, x1])
        self._viewport_region.blockSignals(False)



    def rebuild(self, primary_track_names: List[str], get_datasource: Callable[[str], Any], fallback_x_range: Tuple[float, float]) -> None:
        """Rebuild merged interval graphics and axes for the given primary tracks."""
        tuples: List[Any] = []
        x_mins: List[float] = []
        x_maxs: List[float] = []
        labels_major = []
        for row_i, name in enumerate(primary_track_names):
            labels_major.append((row_i + 0.5, self._truncate_label(name)))
            ds = get_datasource(name)
            if ds is None:
                continue
            try:
                tse = ds.total_df_start_end_times
                if tse is not None and len(tse) == 2:
                    a, b = _scalar_to_plot_x(tse[0]), _scalar_to_plot_x(tse[1])
                    x_mins.append(min(a, b))
                    x_maxs.append(max(a, b))
            except Exception:
                pass
            try:
                overview_df = ds.get_overview_intervals()
            except Exception:
                continue
            if overview_df is None or overview_df.empty or ('t_start' not in overview_df.columns):
                continue
            prep = self._prepare_overview_dataframe(overview_df, row_i)
            if prep is None or prep.empty:
                continue
            try:
                tuples.extend(Render2DEventRectanglesHelper._build_interval_tuple_list_from_dataframe(prep))
            except Exception:
                continue

        # END for row_i, name in enumerate(primary_track_names)...

        n = len(primary_track_names)
        if n == 0:
            self.setMinimumHeight(self._row_height_px + 24)
            x0, x1 = float(fallback_x_range[0]), float(fallback_x_range[1])
            if x1 <= x0:
                x1 = x0 + 1.0
            self.setYRange(0, 1, padding=0)
            self.getAxis('left').setTicks([[]])
            self._swap_intervals_item([])
            self.setXRange(x0, x1, padding=0.01)
            self.getViewBox().setLimits(xMin=x0, xMax=x1, yMin=0, yMax=1)
            return
        self.setMinimumHeight(max(self._row_height_px, min(480, self._row_height_px * n + 28)))
        self.setYRange(0, n, padding=0)
        left_ticks = [labels_major] if labels_major else [[]]
        self.getAxis('left').setTicks(left_ticks)
        self._swap_intervals_item(tuples)
        if x_mins and x_maxs:
            x0, x1 = min(x_mins), max(x_maxs)
        else:
            x0, x1 = float(fallback_x_range[0]), float(fallback_x_range[1])
        if x1 <= x0:
            x1 = x0 + 1.0
        pad = (x1 - x0) * 0.01 + 1e-9
        self.setXRange(x0 - pad, x1 + pad, padding=0)
        self.getViewBox().setLimits(xMin=x0 - pad, xMax=x1 + pad, yMin=0, yMax=n)



    def _truncate_label(self, name: str, max_len: int = 24) -> str:
        s = str(name)
        return s if len(s) <= max_len else s[: max_len - 1] + '…'



    def _prepare_overview_dataframe(self, overview_df: pd.DataFrame, row_i: int) -> Optional[pd.DataFrame]:
        df = overview_df.copy()
        m = self._band_margin
        h = max(0.05, 1.0 - 2.0 * m)
        y_off = float(row_i) + m
        n = len(df)
        if 't_duration' not in df.columns and 't_end' in df.columns:
            ts = [_scalar_to_plot_x(v) for v in df['t_start'].values]
            te = [_scalar_to_plot_x(v) for v in df['t_end'].values]
            df['t_duration'] = [max(0.0, te[j] - ts[j]) for j in range(n)]
        elif 't_duration' in df.columns:
            df['t_duration'] = [_duration_to_seconds(df['t_duration'].iloc[j]) for j in range(n)]
        else:
            return None
        default_pen = pg.mkPen(60, 60, 60, width=1)
        default_brush = pg.mkBrush(120, 160, 220, 95)
        if 'pen' not in df.columns:
            df['pen'] = [default_pen] * n
        if 'brush' not in df.columns:
            df['brush'] = [default_brush] * n
        df['series_vertical_offset'] = y_off
        df['series_height'] = h
        return df



    def _swap_intervals_item(self, data: list) -> None:
        if self._intervals_item is not None:
            try:
                self.removeItem(self._intervals_item)
            except Exception:
                pass
            self._intervals_item = None
        if not data:
            return
        item = IntervalRectsItem(data, format_tooltip_fn=lambda *_a: '')
        item.clickable = False
        item.setAcceptHoverEvents(False)
        item.setZValue(10)
        self.addItem(item)
        self._intervals_item = item


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    strip = TimelineOverviewStrip()
    strip.rebuild([], lambda _n: None, (0.0, 3600.0))
    strip.set_viewport(500.0, 1500.0)
    status = QtWidgets.QLabel('Drag the shaded band (translate) or left-drag edges (resize).')
    status.setWordWrap(True)

    def _on_live(x0: float, x1: float) -> None:
        status.setText(f'Live: {x0:.2f} .. {x1:.2f}  (release for committed)')

    def _on_finished(x0: float, x1: float) -> None:
        status.setText(f'Committed: {x0:.2f} .. {x1:.2f}')

    strip.sigViewportLiveChanged.connect(_on_live)
    strip.sigViewportChanged.connect(_on_finished)
    container = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(container)
    layout.addWidget(strip)
    layout.addWidget(status)
    container.resize(720, 220)
    container.show()
    raise SystemExit(app.exec() if hasattr(app, 'exec') else app.exec_())

