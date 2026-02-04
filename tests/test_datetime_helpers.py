"""Unittest for datetime_to_unix_timestamp / datetime_from_unix_timestamp reciprocal."""

import unittest
from datetime import datetime, timezone, timedelta

from pypho_timeline.utils.datetime_helpers import datetime_to_unix_timestamp, unix_timestamp_to_datetime


class TestDatetimeUnixTimestampReciprocal(unittest.TestCase):
    """Verify reciprocal/identity of datetime_to_unix_timestamp and datetime_from_unix_timestamp."""

    def test_timestamp_roundtrip_identity(self):
        """ts -> datetime_from_unix_timestamp(ts) -> datetime_to_unix_timestamp(...) == ts."""
        for ts in (0.0, 1.5, 1738646400.25):
            roundtrip = datetime_to_unix_timestamp(unix_timestamp_to_datetime(ts))
            self.assertAlmostEqual(roundtrip, ts, places=9)

    def test_datetime_roundtrip_same_instant(self):
        """dt -> datetime_to_unix_timestamp(dt) -> datetime_from_unix_timestamp(...) represents same instant as dt."""
        naive_utc = datetime(2024, 2, 4, 12, 0, 0)
        aware_utc = datetime(2024, 2, 4, 12, 0, 0, tzinfo=timezone.utc)
        aware_est = datetime(2024, 2, 4, 7, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
        for dt in (naive_utc, aware_utc, aware_est):
            expected_ts = datetime_to_unix_timestamp(dt)
            roundtripped = unix_timestamp_to_datetime(datetime_to_unix_timestamp(dt))
            self.assertAlmostEqual(roundtripped.timestamp(), expected_ts, places=9)


if __name__ == "__main__":
    unittest.main()
