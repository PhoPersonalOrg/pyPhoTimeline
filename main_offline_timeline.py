"""live_lsl_timeline.py -- Live timeline with LSL EEG + Motion data and backscroll.

This script creates a PyQt timeline window that:
  1. Connects to live LSL EEG and Motion streams.
  2. Displays both streams as scrolling tracks inside a
     :class:`~pypho_timeline.widgets.simple_timeline_widget.SimpleTimelineWidget`.
  3. Supports **backscroll**: left-click-drag the viewport to inspect historical
     data while streaming continues in the background.
  4. Provides a **"⟳ Sync to Live"** button that snaps the view back to the most
     recent data when the user is done scrolling.

Usage::

    python live_lsl_timeline.py

Optional arguments (environment variables / edit the constants below):
  - EEG_STREAM_TYPE   : LSL type to match for EEG  (default: 'EEG')
  - EEG_STREAM_NAME   : LSL name to match for EEG  (default: None → any EEG type)
  - MOTION_STREAM_TYPE: LSL type for motion/IMU     (default: 'Accelerometer')
  - MOTION_STREAM_NAME: LSL name for motion/IMU     (default: None)
  - BUFFER_SECONDS    : seconds of data to keep     (default: 300)
  - WINDOW_SECONDS    : viewport width in seconds   (default: 10)

Running without live hardware
------------------------------
If no LSL streams are available the script still opens and shows an empty
timeline.  Use a tool like ``labrecorder`` or the ``pylsl`` stream-outlet
examples to inject test streams, or see the ``simulate_eeg`` function defined
at the bottom of this file.
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import os
import sys
import time
from datetime import timezone, datetime
from typing import Optional

import numpy as np
import pandas as pd
from qtpy import QtCore, QtWidgets
import pyqtgraph as pg

from pyphocorehelpers.gui.Qt.ExceptionPrintingSlot import pyqtExceptionPrintingSlot

from pypho_timeline.widgets.simple_timeline_widget import SimpleTimelineWidget
from pypho_timeline.rendering.datasources.specific.lsl import (
    LSLStreamReceiver,
    LiveEEGTrackDatasource,
    LiveMotionTrackDatasource,
)
from pypho_timeline.core.synchronized_plot_mode import SynchronizedPlotMode


# ─────────────────────────────────────────────────────────────────────────────
# Configuration constants (override via environment variables)
# ─────────────────────────────────────────────────────────────────────────────

EEG_STREAM_TYPE: Optional[str] = os.environ.get("EEG_STREAM_TYPE", "EEG") or None
EEG_STREAM_NAME: Optional[str] = os.environ.get("EEG_STREAM_NAME") or None
MOTION_STREAM_TYPE: Optional[str] = os.environ.get("MOTION_STREAM_TYPE", "Accelerometer") or None
MOTION_STREAM_NAME: Optional[str] = os.environ.get("MOTION_STREAM_NAME") or None
BUFFER_SECONDS: float = float(os.environ.get("BUFFER_SECONDS", "300"))
WINDOW_SECONDS: float = float(os.environ.get("WINDOW_SECONDS", "10"))


# ─────────────────────────────────────────────────────────────────────────────
# Live Timeline Window
# ─────────────────────────────────────────────────────────────────────────────


class OfflineTimeline(QtWidgets.QMainWindow):
    """Main window hosting a live EEG + Motion timeline with backscroll.

    Parameters
    ----------
    eeg_datasource:
        Live EEG datasource (already connected to a receiver).
    motion_datasource:
        Live Motion datasource (already connected to a receiver).
    window_seconds:
        Width of the visible time window in seconds.
    buffer_seconds:
        Total buffer duration – the user can scroll this far into the past.
    parent:
        Optional Qt parent.
    """

    def __init__(self, eeg_datasource: LiveEEGTrackDatasource, motion_datasource: LiveMotionTrackDatasource, window_seconds: float = WINDOW_SECONDS, buffer_seconds: float = BUFFER_SECONDS, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Live LSL Timeline – EEG & Motion (backscroll enabled)")
        self.resize(1200, 600)

        self._eeg_ds = eeg_datasource
        self._motion_ds = motion_datasource
        self._window_seconds = window_seconds
        self._buffer_seconds = buffer_seconds
        self._is_live = True  # True = viewport follows the live head

        # ── central widget ──────────────────────────────────────────────
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root_layout = QtWidgets.QVBoxLayout(central)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(4)

        # ── toolbar ─────────────────────────────────────────────────────
        toolbar = self._build_toolbar()
        root_layout.addWidget(toolbar)

        # ── timeline widget ──────────────────────────────────────────────
        now = time.time()

        self._timeline = builder.build_from_xdf_files(xdf_file_paths=demo_xdf_paths,
        # stream_allowlist=[r"EEG.*", r"MOTION.*"],
        #  stream_allowlist=[r'Epoc X*', r'Epoc X Motion*'], # , 'WhisperLiveLogger', 'Epoc X eQuality', 'TextLogger', 'EventBoard'
        # stream_allowlist=[r'Epoc X', r'Epoc X Motion*'], # , 'WhisperLiveLogger', 'Epoc X eQuality', 'TextLogger', 'EventBoard'
        # stream_blocklist=['WhisperLiveLogger', 'Epoc X eQuality', 'TextLogger', 'EventBoard']
        stream_blocklist=['Epoc X Motion', 'Epoc X eQuality'],
        ) 
        
        self._timeline = SimpleTimelineWidget(
            total_start_time=now - buffer_seconds,
            total_end_time=now + window_seconds,
            window_duration=window_seconds,
            window_start_time=now - window_seconds,
            add_example_tracks=False,
            reference_datetime=None,
        )
        root_layout.addWidget(self._timeline)

        # ── add tracks ──────────────────────────────────────────────────
        self._add_tracks()

        # ── status bar ──────────────────────────────────────────────────
        self._status_label = QtWidgets.QLabel("Waiting for LSL streams…")
        self.statusBar().addWidget(self._status_label)

        # ── live-follow timer (fires every 200 ms) ───────────────────────
        self._follow_timer = QtCore.QTimer(self)
        self._follow_timer.setInterval(200)
        self._follow_timer.timeout.connect(self._advance_live_window)
        self._follow_timer.start()

        # Connect "data arrived" signals to refresh status
        eeg_datasource.new_data_available.connect(self._on_eeg_data)
        motion_datasource.new_data_available.connect(self._on_motion_data)

    # ------------------------------------------------------------------ #
    # UI builders
    # ------------------------------------------------------------------ #

    def _build_toolbar(self) -> QtWidgets.QWidget:
        bar = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)

        self._live_btn = QtWidgets.QPushButton("⟳ Sync to Live")
        self._live_btn.setToolTip(
            "Snap the viewport back to the present (live) time.\n"
            "The view will then follow incoming data automatically."
        )
        self._live_btn.setCheckable(True)
        self._live_btn.setChecked(True)
        self._live_btn.toggled.connect(self._on_live_btn_toggled)
        layout.addWidget(self._live_btn)

        self._window_label = QtWidgets.QLabel(f"Window: {self._window_seconds:.0f} s")
        layout.addWidget(self._window_label)

        layout.addStretch()

        info = QtWidgets.QLabel(
            "Drag the plot to backscroll · Scroll-wheel to zoom · "
            "Press 'Sync to Live' to return"
        )
        info.setStyleSheet("color: grey; font-size: 10px;")
        layout.addWidget(info)

        return bar

    def _add_tracks(self) -> None:
        """Add EEG and Motion tracks to the timeline."""
        now = time.time()

        # ── EEG track ──────────────────────────────────────────────────
        eeg_widget, _rg, eeg_plot, _dock = self._timeline.add_new_embedded_pyqtgraph_render_plot_widget(
            name="Live EEG",
            dockSize=(1200, 200),
            dockAddLocationOpts=["bottom"],
            sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA,
        )
        eeg_plot.setXRange(now - self._window_seconds, now, padding=0)
        eeg_plot.setYRange(0, 1, padding=0)
        eeg_plot.setLabel("left", "EEG")
        eeg_plot.hideAxis("left")
        eeg_plot.setLabel("bottom", "Time (LSL clock)")
        self._timeline.add_track(self._eeg_ds, name="Live EEG", plot_item=eeg_plot)
        self._eeg_plot = eeg_plot

        # ── Motion track ────────────────────────────────────────────────
        motion_widget, _rg2, motion_plot, _dock2 = self._timeline.add_new_embedded_pyqtgraph_render_plot_widget(
            name="Live Motion",
            dockSize=(1200, 150),
            dockAddLocationOpts=["bottom"],
            sync_mode=SynchronizedPlotMode.TO_GLOBAL_DATA,
        )
        motion_plot.setXRange(now - self._window_seconds, now, padding=0)
        motion_plot.setYRange(0, 1, padding=0)
        motion_plot.setLabel("left", "IMU")
        motion_plot.hideAxis("left")
        motion_plot.setLabel("bottom", "Time (LSL clock)")
        self._timeline.add_track(self._motion_ds, name="Live Motion", plot_item=motion_plot)
        self._motion_plot = motion_plot

        # Detect user-initiated pan/zoom → exit live-follow mode
        for plot in (eeg_plot, motion_plot):
            vb = plot.getViewBox()
            if vb is not None:
                vb.sigRangeChangedManually.connect(self._on_user_panned)

    # ------------------------------------------------------------------ #
    # Live-follow logic
    # ------------------------------------------------------------------ #

    @pyqtExceptionPrintingSlot()
    def _advance_live_window(self) -> None:
        """Move the viewport to follow the live head (only when in live mode)."""
        if not self._is_live:
            return

        # Use the latest timestamp from either datasource
        t_live = self._eeg_ds.live_timestamp or self._motion_ds.live_timestamp
        if t_live is None:
            t_live = time.time()

        t_start = t_live - self._window_seconds
        t_end = t_live

        # Update both plots without triggering sigRangeChangedManually.
        # Note: setXRange() is a programmatic change and does NOT emit
        # sigRangeChangedManually, so no signal blocking is needed here.
        for plot in (self._eeg_plot, self._motion_plot):
            plot.setXRange(t_start, t_end, padding=0)


    @pyqtExceptionPrintingSlot()
    def _on_user_panned(self) -> None:
        """Called when the user manually drags/zooms → enter backscroll mode."""
        if self._is_live:
            self._is_live = False
            self._live_btn.blockSignals(True)
            self._live_btn.setChecked(False)
            self._live_btn.blockSignals(False)
            self._status_label.setText(
                "Backscrolling – press '⟳ Sync to Live' to return to live view"
            )

    @pyqtExceptionPrintingSlot(bool)
    def _on_live_btn_toggled(self, checked: bool) -> None:
        """Toggle live-follow mode from the toolbar button."""
        self._is_live = checked
        if checked:
            self._advance_live_window()
            self._status_label.setText("Live – following incoming data")
        else:
            self._status_label.setText(
                "Backscrolling – press '⟳ Sync to Live' to return to live view"
            )

    # ------------------------------------------------------------------ #
    # Data-arrival callbacks
    # ------------------------------------------------------------------ #

    @pyqtExceptionPrintingSlot()
    def _on_eeg_data(self) -> None:
        ts = self._eeg_ds.live_timestamp
        if ts is not None and self._is_live:
            self._status_label.setText(
                f"Live  |  EEG @ {_fmt_ts(ts)}  |  "
                f"Motion @ {_fmt_ts(self._motion_ds.live_timestamp)}"
            )

    @pyqtExceptionPrintingSlot()
    def _on_motion_data(self) -> None:
        ts = self._motion_ds.live_timestamp
        if ts is not None and self._is_live:
            self._status_label.setText(
                f"Live  |  EEG @ {_fmt_ts(self._eeg_ds.live_timestamp)}  |  "
                f"Motion @ {_fmt_ts(ts)}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Optional: synthetic test-stream helpers (no hardware required)
# ─────────────────────────────────────────────────────────────────────────────


def _start_synthetic_eeg_outlet(n_channels: int = 14, sfreq: float = 128.0, stream_name: str = "SyntheticEEG") -> object:
    """Push a synthetic EEG outlet via pylsl (for local testing).

    Returns the :class:`pylsl.StreamOutlet` (keep a reference to prevent GC).
    Runs in the calling thread; call from a ``QThread`` or ``threading.Thread``
    if you do not want it to block.
    """
    try:
        import pylsl  # type: ignore
    except ImportError:
        print("pylsl not available – cannot create synthetic EEG outlet")
        return None

    ch_names = [
        "AF3", "F7", "F3", "FC5", "T7", "P7", "O1",
        "O2", "P8", "T8", "FC6", "F4", "F8", "AF4",
    ][:n_channels]
    info = pylsl.StreamInfo(stream_name, "EEG", n_channels, sfreq, "float32", "synthetic-eeg-001")
    chans = info.desc().append_child("channels")
    for ch in ch_names:
        c = chans.append_child("channel")
        c.append_child_value("label", ch)
    outlet = pylsl.StreamOutlet(info, chunk_size=32, max_buffered=360)
    print(f"[synthetic EEG] outlet '{stream_name}' created  ({n_channels} ch @ {sfreq} Hz)")
    return outlet


def _push_synthetic_samples(outlet: object, n_channels: int = 14, sfreq: float = 128.0) -> None:
    """Continuously push synthetic EEG samples (blocking; run in a thread)."""
    try:
        import pylsl  # type: ignore
    except ImportError:
        return

    interval = 1.0 / sfreq
    t = 0.0
    while True:
        sample = [float(np.sin(2 * np.pi * 10.0 * t + i * 0.5)) + 0.05 * np.random.randn()
                  for i in range(n_channels)]
        outlet.push_sample(sample)
        t += interval
        time.sleep(interval)


def _start_synthetic_motion_outlet(stream_name: str = "SyntheticMotion", sfreq: float = 32.0) -> object:
    """Push a synthetic IMU outlet via pylsl (for local testing)."""
    try:
        import pylsl  # type: ignore
    except ImportError:
        print("pylsl not available – cannot create synthetic Motion outlet")
        return None

    ch_names = ["AccX", "AccY", "AccZ", "GyroX", "GyroY", "GyroZ"]
    n_channels = len(ch_names)
    info = pylsl.StreamInfo(stream_name, "Accelerometer", n_channels, sfreq, "float32", "synthetic-motion-001")
    chans = info.desc().append_child("channels")
    for ch in ch_names:
        c = chans.append_child("channel")
        c.append_child_value("label", ch)
    outlet = pylsl.StreamOutlet(info, chunk_size=8, max_buffered=360)
    print(f"[synthetic Motion] outlet '{stream_name}' created  ({n_channels} ch @ {sfreq} Hz)")
    return outlet


def _push_synthetic_motion_samples(outlet: object, sfreq: float = 32.0) -> None:
    """Continuously push synthetic IMU samples (blocking; run in a thread)."""
    interval = 1.0 / sfreq
    t = 0.0
    while True:
        sample = [
            np.sin(2 * np.pi * 0.5 * t),               # AccX
            np.cos(2 * np.pi * 0.5 * t),               # AccY
            9.81 + 0.1 * np.random.randn(),             # AccZ (gravity)
            0.1 * np.sin(2 * np.pi * 1.0 * t),         # GyroX
            0.1 * np.cos(2 * np.pi * 1.0 * t),         # GyroY
            0.05 * np.random.randn(),                   # GyroZ
        ]
        outlet.push_sample(sample)
        t += interval
        time.sleep(interval)


# ─────────────────────────────────────────────────────────────────────────────
# Utility
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_ts(ts: Optional[float]) -> str:
    if ts is None:
        return "–"
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%H:%M:%S.%f")[:-3]


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────


def main(use_synthetic: bool = False) -> int:
    """Launch the live LSL timeline.

    Parameters
    ----------
    use_synthetic:
        If ``True``, start in-process synthetic LSL outlets so the timeline
        can be demonstrated without real hardware.  Requires ``pylsl``.
    """
    app = pg.mkQApp("LiveLSLTimeline")

    # ── optional synthetic data sources ────────────────────────────────
    _synthetic_threads = []
    if use_synthetic:
        try:
            import threading
            eeg_outlet = _start_synthetic_eeg_outlet()
            if eeg_outlet is not None:
                t = threading.Thread(target=_push_synthetic_samples,
                                     args=(eeg_outlet,), daemon=True)
                t.start()
                _synthetic_threads.append(t)

            motion_outlet = _start_synthetic_motion_outlet()
            if motion_outlet is not None:
                t2 = threading.Thread(target=_push_synthetic_motion_samples,
                                      args=(motion_outlet,), daemon=True)
                t2.start()
                _synthetic_threads.append(t2)

            # Give outlets a moment to become discoverable
            time.sleep(0.5)
        except Exception as exc:
            print(f"Warning: could not start synthetic streams: {exc}")

    # ── EEG receiver + datasource ───────────────────────────────────────
    eeg_receiver = LSLStreamReceiver(
        stream_type=EEG_STREAM_TYPE,
        stream_name=EEG_STREAM_NAME if not use_synthetic else "SyntheticEEG",
        poll_interval_ms=100,
    )
    eeg_ds = LiveEEGTrackDatasource(
        receiver=eeg_receiver,
        buffer_seconds=BUFFER_SECONDS,
        custom_datasource_name="Live EEG",
    )

    # ── Motion receiver + datasource ────────────────────────────────────
    motion_receiver = LSLStreamReceiver(
        stream_type=MOTION_STREAM_TYPE,
        stream_name=MOTION_STREAM_NAME if not use_synthetic else "SyntheticMotion",
        poll_interval_ms=100,
    )
    motion_ds = LiveMotionTrackDatasource(
        receiver=motion_receiver,
        buffer_seconds=BUFFER_SECONDS,
        channel_names=["AccX", "AccY", "AccZ", "GyroX", "GyroY", "GyroZ"],
        custom_datasource_name="Live Motion",
    )

    # ── main window ─────────────────────────────────────────────────────
    window: LiveLSLTimeline = LiveLSLTimeline(
        eeg_datasource=eeg_ds,
        motion_datasource=motion_ds,
        window_seconds=WINDOW_SECONDS,
        buffer_seconds=BUFFER_SECONDS,
    )
    window.show()

    # ── start receivers after the window is shown ────────────────────────
    eeg_receiver.start()
    motion_receiver.start()

    return app.exec_()


if __name__ == "__main__":
    # Pass --synthetic to start without real LSL hardware
    use_synthetic = "--synthetic" in sys.argv
    sys.exit(main(use_synthetic=use_synthetic))
