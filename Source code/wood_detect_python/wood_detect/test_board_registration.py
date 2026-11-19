import unittest

import numpy as np

from board_registration import translation_between


class BoardRegistrationTest(unittest.TestCase):
    def test_local_views_recover_fraction_of_view_width(self):
        texture = np.random.default_rng(245).integers(0, 255, (300, 660), dtype=np.uint8)
        anchor = texture[:, :500]
        current = texture[:, 125:625]
        registration = translation_between(current, anchor)
        self.assertAlmostEqual(registration["shiftX"], 0.25, places=3)
        self.assertAlmostEqual(registration["shiftY"], 0.0, places=3)

    def test_unobservable_shift_is_rejected(self):
        blank = np.zeros((300, 500), dtype=np.uint8)
        with self.assertRaises(ValueError):
            translation_between(blank, blank)

