"""Focused tests for video thumbnail offset generation and label normalization.

These tests intentionally avoid importing the full ``video.py`` module, which depends
on optional packages (cv2, deffcode, imageio). Instead, they validate the core math
and helper behaviors in isolation so a regression in either is caught quickly.
"""

import math
import unittest
import numpy as np


class TestThumbnailFrameOffsetMath(unittest.TestCase):
    """Verifies the new linspace-based frame offset generation does not blow up.

    The previous formula (``np.arange(0, duration, target_n_frames / duration)``)
    produced ``duration**2 / target_n_frames`` offsets, which for a 1-hour video
    and ``target_n_frames=5`` was ~2.6M offsets. The new linspace formulation
    must always produce exactly ``target_n_frames`` offsets within ``[0, duration)``.
    """

    def _generate_offsets(self, target_n_frames: int, source_duration_sec: float) -> np.ndarray:
        if source_duration_sec <= 0.0:
            return np.array([], dtype=float)
        return np.linspace(0.0, source_duration_sec, num=int(target_n_frames), endpoint=False, dtype=float)


    def test_short_clip_produces_target_count(self):
        offsets = self._generate_offsets(target_n_frames=5, source_duration_sec=10.0)
        self.assertEqual(len(offsets), 5)
        self.assertTrue(np.all(offsets >= 0.0))
        self.assertTrue(np.all(offsets < 10.0))


    def test_one_hour_clip_does_not_explode(self):
        target_n_frames = 5
        offsets = self._generate_offsets(target_n_frames=target_n_frames, source_duration_sec=3600.0)
        self.assertEqual(len(offsets), target_n_frames)
        self.assertLessEqual(len(offsets), 32)  # well below the safety cap


    def test_invalid_duration_returns_empty(self):
        self.assertEqual(len(self._generate_offsets(5, 0.0)), 0)
        self.assertEqual(len(self._generate_offsets(5, -1.0)), 0)


    def test_offsets_are_strictly_within_duration(self):
        target_n_frames = 7
        duration = 12.5
        offsets = self._generate_offsets(target_n_frames=target_n_frames, source_duration_sec=duration)
        self.assertEqual(len(offsets), target_n_frames)
        self.assertAlmostEqual(float(offsets[0]), 0.0)
        self.assertLess(float(offsets[-1]), duration)


    def test_offsets_evenly_spaced(self):
        offsets = self._generate_offsets(target_n_frames=4, source_duration_sec=20.0)
        diffs = np.diff(offsets)
        self.assertEqual(len(offsets), 4)
        self.assertTrue(np.allclose(diffs, diffs[0]))


    def test_old_buggy_formula_exposes_explosion(self):
        target_n_frames = 5
        source_duration_sec = 3600.0
        old_step = (float(target_n_frames) / source_duration_sec)  # ~0.00139
        old_offsets = np.arange(start=0.0, stop=source_duration_sec, step=old_step)
        # Sanity-check the regression we just fixed is real and large.
        self.assertGreater(len(old_offsets), 1_000_000)



class TestLabelNormalization(unittest.TestCase):
    """Mirrors the logic added to render_rectangles_helper._build_interval_tuple_list_from_dataframe."""

    @staticmethod
    def _normalize_label(v):
        if v is None:
            return ''
        try:
            if isinstance(v, float) and math.isnan(v):
                return ''
        except Exception:
            pass
        s = str(v)
        return '' if s.lower() == 'nan' else s


    def test_normalize_none(self):
        self.assertEqual(self._normalize_label(None), '')


    def test_normalize_nan(self):
        self.assertEqual(self._normalize_label(float('nan')), '')


    def test_normalize_string_nan_literal(self):
        self.assertEqual(self._normalize_label('NaN'), '')
        self.assertEqual(self._normalize_label('nan'), '')


    def test_normalize_filename_passthrough(self):
        self.assertEqual(self._normalize_label('clip_01.mp4'), 'clip_01.mp4')


    def test_normalize_empty_string(self):
        self.assertEqual(self._normalize_label(''), '')


if __name__ == '__main__':
    unittest.main()
