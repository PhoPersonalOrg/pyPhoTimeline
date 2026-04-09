"""Discover XDF recording files from lab directories via phopymnehelper HistoricalData."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence, Union

import pandas as pd

try:
    from phopymnehelper.historical_data import HistoricalData
except ImportError:
    HistoricalData = None


@dataclass(frozen=True)
class XdfDiscoveryResult:
    xdf_paths: List[Path]
    file_comparison_df: pd.DataFrame


def select_most_recent_xdf_file(xdf_paths: Sequence[Union[Path, str]]) -> Optional[Path]:
    """Return the most recently modified XDF path from candidates, or None."""
    valid_paths: List[Path] = []
    for candidate in xdf_paths:
        p = Path(candidate)
        if p.exists() and p.is_file():
            valid_paths.append(p)
    if len(valid_paths) == 0:
        return None
    return max(valid_paths, key=lambda p: (p.stat().st_mtime_ns, str(p)))


def derive_reference_datetime_from_file_metadata(file_path: Union[Path, str], file_comparison_df: Optional[pd.DataFrame] = None) -> Optional[datetime]:
    """Derive best-effort recording reference datetime when XDF header metadata is missing.

    Order of preference:
      1) `meas_datetime` from `file_comparison_df` (if available)
      2) file mtime (UTC), which works for actively recording/open files
    """
    path = Path(file_path)
    has_valid_comparison_df = (file_comparison_df is not None) and (len(file_comparison_df) > 0) and ('src_file' in file_comparison_df.columns)
    if has_valid_comparison_df:
        try:
            resolved_target = str(path.resolve())
            resolved_sources = file_comparison_df['src_file'].map(lambda s: str(Path(s).resolve()))
            found_file_df_matches = file_comparison_df[resolved_sources == resolved_target]
            if len(found_file_df_matches) >= 1:
                meas_datetime = found_file_df_matches.iloc[0].get('meas_datetime', None)
                if pd.notna(meas_datetime):
                    ts = pd.Timestamp(meas_datetime)
                    if ts.tzinfo is None:
                        ts = ts.tz_localize('UTC')
                    else:
                        ts = ts.tz_convert('UTC')
                    return ts.to_pydatetime()
        except (OSError, TypeError, ValueError):
            pass
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def discover_xdf_files_for_timeline(xdf_discovery_dirs: Union[Path, str, Sequence[Path]], n_most_recent: Optional[int] = None, recordings_extensions: Optional[List[str]] = None, csv_export_path: Optional[Path] = None) -> XdfDiscoveryResult:
    dirs: List[Path] = [Path(xdf_discovery_dirs)] if isinstance(xdf_discovery_dirs, (Path, str)) else [Path(p) for p in xdf_discovery_dirs]
    if len(dirs) == 0:
        return XdfDiscoveryResult(xdf_paths=[], file_comparison_df=pd.DataFrame())
    if HistoricalData is None:
        raise ImportError("HistoricalData is not available. XDF discovery requires phopymnehelper.")
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
