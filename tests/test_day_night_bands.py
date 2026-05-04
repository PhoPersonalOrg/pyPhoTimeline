"""Unit tests for `build_day_night_intervals_df` (day/night band data helper)."""

import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from pypho_timeline.rendering.mixins.epoch_rendering_mixin import build_day_night_intervals_df


UTC = ZoneInfo("UTC")


def _utc_unix(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> float:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc).timestamp()


class TestBuildDayNightIntervalsDf(unittest.TestCase):
    """Verify segment generation, clipping, and overall ordering of the day/night dataframe."""


    def test_returns_empty_for_invalid_window(self):
        empty = build_day_night_intervals_df(10.0, 5.0, tz=UTC)
        self.assertTrue(empty.empty)
        self.assertEqual(list(empty.columns), ['t_start', 't_duration', 't_end', 'series_vertical_offset', 'series_height', 'pen', 'brush', 'label'])


    def test_two_full_days_in_utc_yields_alternating_day_night(self):
        win_start = _utc_unix(2026, 1, 5, 5)
        win_end = _utc_unix(2026, 1, 7, 5)
        df = build_day_night_intervals_df(win_start, win_end, tz=UTC)

        labels = df['label'].tolist()
        self.assertEqual(labels, ['Day', 'Night', 'Day', 'Night'])

        durations = df['t_duration'].tolist()
        self.assertEqual(durations, [16 * 3600.0, 8 * 3600.0, 16 * 3600.0, 8 * 3600.0])

        starts = df['t_start'].tolist()
        self.assertEqual(starts[0], win_start)
        self.assertEqual(starts[1], _utc_unix(2026, 1, 5, 21))
        self.assertEqual(starts[2], _utc_unix(2026, 1, 6, 5))
        self.assertEqual(starts[3], _utc_unix(2026, 1, 6, 21))
        self.assertEqual(starts[3] + durations[3], win_end)


    def test_clips_window_starting_mid_night(self):
        win_start = _utc_unix(2026, 1, 5, 23)
        win_end = _utc_unix(2026, 1, 6, 8)
        df = build_day_night_intervals_df(win_start, win_end, tz=UTC)

        self.assertEqual(df['label'].tolist(), ['Night', 'Day'])
        self.assertEqual(df['t_start'].tolist(), [win_start, _utc_unix(2026, 1, 6, 5)])
        self.assertEqual(df['t_duration'].tolist(), [6 * 3600.0, 3 * 3600.0])
        self.assertEqual(df['t_end'].iloc[-1], win_end)


    def test_y_geometry_is_propagated(self):
        win_start = _utc_unix(2026, 1, 5, 6)
        win_end = _utc_unix(2026, 1, 5, 8)
        df = build_day_night_intervals_df(win_start, win_end, tz=UTC, series_vertical_offset=-3.5, series_height=12.0)
        self.assertTrue((df['series_vertical_offset'] == -3.5).all())
        self.assertTrue((df['series_height'] == 12.0).all())


    def test_dst_spring_forward_in_america_detroit(self):
        tz = ZoneInfo("America/Detroit")
        win_start = pd.Timestamp(year=2026, month=3, day=7, hour=21, tz=tz).timestamp()
        win_end = pd.Timestamp(year=2026, month=3, day=8, hour=5, tz=tz).timestamp()
        df = build_day_night_intervals_df(win_start, win_end, tz=tz)

        self.assertEqual(df['label'].tolist(), ['Night'])
        self.assertEqual(df['t_duration'].iloc[0], 7 * 3600.0)


if __name__ == "__main__":
    unittest.main()
