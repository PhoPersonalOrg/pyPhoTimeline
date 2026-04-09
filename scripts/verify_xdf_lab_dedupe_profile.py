"""One-shot check: LabRecorderXDF.init_from_lab_recorder_xdf_file is invoked once per file per perform_process call (not once per stream). Also prints a short cProfile summary."""

from __future__ import annotations

import cProfile
import io
import pstats
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from pypho_timeline.rendering.datasources.stream_to_datasources import perform_process_all_streams_multi_xdf


def _make_eeg(n_samples: int = 4):
    ch = 14
    return {'info': {'name': ['Epoc X'], 'type': ['EEG'], 'channel_count': [ch], 'nominal_srate': [[128.0]]}, 'time_stamps': np.linspace(0.0, float(n_samples - 1) / 128.0, n_samples), 'time_series': np.zeros((n_samples, ch))}


def _make_motion(n_samples: int = 4):
    ch = 6
    return {'info': {'name': ['Epoc X Motion'], 'type': ['SIGNAL'], 'channel_count': [ch], 'nominal_srate': [[16.0]]}, 'time_stamps': np.linspace(0.0, float(n_samples - 1) / 16.0, n_samples), 'time_series': np.zeros((n_samples, ch))}


def main() -> None:
    calls = {'n': 0}

    def fake_init(*args, **kwargs):
        calls['n'] += 1
        m = MagicMock()
        m.datasets_dict = {}
        return m

    with tempfile.TemporaryDirectory() as d:
        xdf_path = Path(d) / 'session.xdf'
        xdf_path.write_bytes(b'x')
        header = {'info': {'datetime': ['2025-01-01T00:00:00+0000']}}
        streams = [_make_eeg(), _make_motion()]
        pr = cProfile.Profile()
        with patch('phopymnehelper.historical_data.HistoricalData.build_file_comparison_df', return_value=pd.DataFrame()):
            with patch('phopymnehelper.xdf_files.LabRecorderXDF.init_from_lab_recorder_xdf_file', side_effect=fake_init):
                pr.enable()
                perform_process_all_streams_multi_xdf([streams], [xdf_path], file_headers=[header], enable_raw_xdf_processing=True)
                pr.disable()
    assert calls['n'] == 1, f'expected 1 LabRecorderXDF load for 2 streams 1 file, got {calls["n"]}'
    print('LabRecorderXDF.init_from_lab_recorder_xdf_file calls:', calls['n'])
    buf = io.StringIO()
    pstats.Stats(pr, stream=buf).sort_stats('cumtime').print_stats(12)
    print(buf.getvalue())


if __name__ == '__main__':
    main()
