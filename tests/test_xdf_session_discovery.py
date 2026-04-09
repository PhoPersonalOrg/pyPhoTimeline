"""Tests for active XDF discovery helpers."""

from __future__ import annotations

from datetime import timezone
from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
import sys

import pandas as pd


_MODULE_PATH = Path(__file__).resolve().parents[1] / "pypho_timeline" / "xdf_session_discovery.py"
_SPEC = spec_from_file_location("pypho_timeline_xdf_session_discovery", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)


def test_select_most_recent_xdf_file_prefers_latest_mtime(tmp_path):
    older = tmp_path / "older.xdf"
    newer = tmp_path / "newer.xdf"
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    os.utime(older, ns=(1_000_000_000, 1_000_000_000))
    os.utime(newer, ns=(2_000_000_000, 2_000_000_000))

    selected = _MODULE.select_most_recent_xdf_file([older, newer])

    assert selected == newer


def test_derive_reference_datetime_prefers_meas_datetime_then_falls_back_to_mtime(tmp_path):
    xdf_path = tmp_path / "active_recording.xdf"
    xdf_path.write_bytes(b"partial-xdf")
    expected_metadata_dt = pd.Timestamp("2026-04-09T12:00:00Z")
    df = pd.DataFrame({"src_file": [str(xdf_path)], "meas_datetime": [expected_metadata_dt]})

    resolved = _MODULE.derive_reference_datetime_from_file_metadata(file_path=xdf_path, file_comparison_df=df)

    assert resolved is not None
    assert pd.Timestamp(resolved) == expected_metadata_dt

    resolved_from_stat = _MODULE.derive_reference_datetime_from_file_metadata(file_path=xdf_path, file_comparison_df=pd.DataFrame())

    assert resolved_from_stat is not None
    assert resolved_from_stat.tzinfo == timezone.utc
