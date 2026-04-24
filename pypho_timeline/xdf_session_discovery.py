"""Discover XDF recording files from lab directories via phopymnehelper HistoricalData."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Union

import pandas as pd
from phopymnehelper.historical_data import HistoricalData


@dataclass(frozen=True)
class XdfDiscoveryResult:
    xdf_paths: List[Path]
    file_comparison_df: pd.DataFrame


def discover_xdf_files_for_timeline(xdf_discovery_dirs: Union[Path, str, Sequence[Path]], n_most_recent: Optional[int] = None, recordings_extensions: Optional[List[str]] = None, csv_export_path: Optional[Path] = None) -> XdfDiscoveryResult:
    dirs: List[Path] = [Path(xdf_discovery_dirs)] if isinstance(xdf_discovery_dirs, (Path, str)) else [Path(p) for p in xdf_discovery_dirs]
    if len(dirs) == 0:
        return XdfDiscoveryResult(xdf_paths=[], file_comparison_df=pd.DataFrame())
    ext = recordings_extensions if recordings_extensions is not None else ['.xdf']
    discovered_xdf_files: List[Path] = HistoricalData.get_recording_files(recordings_dir=dirs, recordings_extensions=ext)
    if n_most_recent is not None:
        discovered_xdf_files = discovered_xdf_files[:n_most_recent]
    if len(discovered_xdf_files) == 0:
        return XdfDiscoveryResult(xdf_paths=[], file_comparison_df=pd.DataFrame())
    file_comparison_df: pd.DataFrame = HistoricalData.build_file_comparison_df(recording_files=discovered_xdf_files)
    xdf_paths: List[Path] = [Path(v) for v in file_comparison_df['src_file'].to_list()]
    if csv_export_path is not None:
        file_comparison_df.to_csv(csv_export_path)
    return XdfDiscoveryResult(xdf_paths=xdf_paths, file_comparison_df=file_comparison_df)
