"""Minimal live LSL datasources used by tests and live timeline widgets."""

from __future__ import annotations

import threading
from typing import List, Optional

import numpy as np
import pandas as pd
from qtpy import QtCore

from pypho_timeline.rendering.datasources.track_datasource import BaseTrackDatasource


class LSLStreamReceiver(QtCore.QObject):
    """Small wrapper around ``pylsl.StreamInlet`` for live sample ingestion."""

    data_received = QtCore.Signal(object, object)

    def __init__(self, stream_type: str = "EEG", stream_name: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.stream_type = stream_type
        self.stream_name = stream_name
        self.stream_info = None
        self._inlet = None
        self._channel_names: List[str] = []
        self.is_connected = False


    @property
    def channel_names(self) -> List[str]:
        return list(self._channel_names)


    @staticmethod
    def _read_channel_names(info, n_channels: int) -> List[str]:
        names: List[str] = []
        try:
            channel = info.desc().child("channels").child("channel")
            for idx in range(n_channels):
                label = channel.child_value("label") if channel is not None else ""
                names.append(str(label) if label else str(idx))
                channel = channel.next_sibling() if channel is not None else None
        except Exception:
            names = [str(idx) for idx in range(n_channels)]
        return names


    def _create_inlet(self, info):
        import pylsl
        self.stream_info = info
        self._inlet = pylsl.StreamInlet(info, max_buflen=2, max_chunklen=0, processing_flags=getattr(pylsl, "proc_ALL", 0))
        n_channels = int(info.channel_count())
        self._channel_names = self._read_channel_names(info, n_channels)
        self.is_connected = True
        return self._inlet


    def stop(self):
        if self._inlet is not None:
            try:
                self._inlet.close_stream()
            except Exception:
                pass
        self._inlet = None
        self.is_connected = False


class LiveEEGTrackDatasource(BaseTrackDatasource):
    """Rolling dataframe datasource for live EEG samples."""

    def __init__(self, stream_type: str = "EEG", stream_name: Optional[str] = None, window_duration_s: float = 5.0, custom_datasource_name: str = "LiveEEG"):
        super().__init__()
        self.custom_datasource_name = custom_datasource_name
        self.stream_type = stream_type
        self.stream_name = stream_name
        self.window_duration_s = float(window_duration_s)
        self._receiver = LSLStreamReceiver(stream_type=stream_type, stream_name=stream_name)
        self._receiver.data_received.connect(self._on_data_received)
        self._channel_names: List[str] = []
        self._lock = threading.RLock()
        self.detailed_df = pd.DataFrame()
        self.intervals_df = pd.DataFrame(columns=["t_start", "t_duration"])


    @property
    def df(self) -> pd.DataFrame:
        return self.intervals_df


    @property
    def time_column_names(self) -> list:
        return ["t_start", "t_duration"]


    @property
    def total_df_start_end_times(self):
        with self._lock:
            if self.detailed_df.empty:
                return 0.0, 0.0
            return float(self.detailed_df["t"].min()), float(self.detailed_df["t"].max())


    def _on_data_received(self, timestamps, data):
        timestamps = np.asarray(timestamps, dtype=float)
        data = np.asarray(data)
        if data.ndim == 1:
            data = data.reshape(1, -1)
        if data.shape[1] != len(timestamps) and data.shape[0] == len(timestamps):
            data = data.T
        channel_names = self._channel_names or self._receiver.channel_names or [f"CH{idx}" for idx in range(data.shape[0])]
        records = {"t": timestamps}
        for idx, name in enumerate(channel_names[:data.shape[0]]):
            records[name] = data[idx]
        new_df = pd.DataFrame(records)
        with self._lock:
            self.detailed_df = pd.concat([self.detailed_df, new_df], ignore_index=True)
            newest = float(self.detailed_df["t"].max())
            cutoff = newest - self.window_duration_s
            self.detailed_df = self.detailed_df[self.detailed_df["t"] >= cutoff].reset_index(drop=True)
            start = float(self.detailed_df["t"].min())
            end = float(self.detailed_df["t"].max())
            self.intervals_df = pd.DataFrame([{"t_start": start, "t_duration": end - start}])
        self.source_data_changed_signal.emit()


    def fetch_detailed_data(self, interval, *args, **kwargs) -> pd.DataFrame:
        start = float(interval["t_start"])
        end = start + float(interval.get("t_duration", 0.0))
        with self._lock:
            df = self.detailed_df.copy()
        if "t" not in df.columns:
            return df
        return df[(df["t"] >= start) & (df["t"] <= end)].reset_index(drop=True)

