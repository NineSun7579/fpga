import math
import random
import unittest
from fractions import Fraction

from golden import MAX_SCALE, Q16, affine_lane, affine_word, pack, rounded_value


class AffineGoldenTests(unittest.TestCase):
    def test_negative_operand_survives_until_output(self):
        self.assertEqual(affine_lane(127, 64, Q16, Q16, 128, 64, 100), 99)
        self.assertEqual(affine_lane(80, 160, Q16, Q16, 128, 128, 128), 112)
        self.assertEqual(affine_lane(0, 0, Q16, Q16, 128, 128, 128), 0)

    def test_different_domains(self):
        # (-20)*0.5 + 30*1.5 + 80 = 115.
        self.assertEqual(affine_lane(80, 70, Q16 // 2, 3 * Q16 // 2,
                                     100, 40, 80), 115)

    def test_signed_half_ties_and_neighbors(self):
        for delta, expected in ((-3, -1), (-2, -1), (-1, 0),
                                (0, 0), (1, 1), (2, 1), (3, 2)):
            self.assertEqual(rounded_value(delta + 3, 0, Q16 // 2, 0,
                                           3, 0, 0), expected)
        for scale, expected in ((32767, 0), (32768, 1), (32769, 1)):
            self.assertEqual(affine_lane(1, 0, scale, 0, 0, 0, 0), expected)
        self.assertEqual(affine_lane(0, 0, 32768, 0, 1, 0, 1), 1)

    def test_extreme_scales_and_saturation(self):
        self.assertEqual(affine_lane(255, 255, MAX_SCALE, MAX_SCALE,
                                     0, 0, 0), 255)
        self.assertEqual(affine_lane(0, 0, MAX_SCALE, MAX_SCALE,
                                     255, 255, 255), 0)
        self.assertEqual(affine_lane(255, 0, MAX_SCALE, MAX_SCALE,
                                     0, 255, 117), 117)
        self.assertEqual(affine_lane(255, 0, MAX_SCALE, MAX_SCALE - Q16,
                                     0, 255, 0), 255)

    def test_requantization_and_lane_order(self):
        a = pack([0, 63, 128, 255])
        b = pack([255, 0, 42, 99])
        self.assertEqual(affine_word(a, b, Q16 // 2, 0, 128, 200, 100, 4),
                         pack([36, 68, 100, 164]))
        self.assertEqual(affine_word(a, pack([200] * 4), Q16 // 2, MAX_SCALE,
                                     128, 200, 100, 4), pack([36, 68, 100, 164]))

    def test_fraction_oracle_random(self):
        # Independently round an exact rational; never use float or byte wrapping.
        rng = random.Random(0xAF16)
        for _ in range(5000):
            qa, qb, za, zb, zo = [rng.randrange(256) for _ in range(5)]
            sa, sb = rng.getrandbits(32), rng.getrandbits(32)
            rational = (Fraction((qa - za) * sa, Q16)
                        + Fraction((qb - zb) * sb, Q16) + zo)
            expected = math.floor(rational + Fraction(1, 2))
            self.assertEqual(rounded_value(qa, qb, sa, sb, za, zb, zo), expected)
            self.assertEqual(affine_lane(qa, qb, sa, sb, za, zb, zo),
                             min(255, max(0, expected)))

    def test_reject_invalid_inputs(self):
        with self.assertRaises(ValueError):
            affine_lane(256, 0, 0, 0, 0, 0, 0)
        with self.assertRaises(ValueError):
            affine_lane(0, 0, 1 << 32, 0, 0, 0, 0)
        with self.assertRaises(ValueError):
            affine_word(256, 0, 0, 0, 0, 0, 0, 1)


if __name__ == "__main__":
    unittest.main()
